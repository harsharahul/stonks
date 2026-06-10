import hmac
import logging
from fastapi import Header, HTTPException, Request
from typing import Optional
from datetime import datetime, timezone as tz

from app.core.config import settings

logger = logging.getLogger(__name__)


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if settings.API_KEY:
        if not x_api_key or x_api_key != settings.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


class SimpleRateLimiter:
    def __init__(self, limit_per_minute: int = 120):
        self.limit = limit_per_minute
        self.window_requests = {}

    def _key(self, client_ip: str) -> str:
        from time import time
        current_minute = int(time() // 60)
        return f"{client_ip}:{current_minute}"

    def allow(self, client_ip: str) -> bool:
        if not settings.ENABLE_RATE_LIMIT:
            return True
        from time import time
        k = self._key(client_ip)
        self.window_requests.setdefault(k, 0)
        if self.window_requests[k] >= settings.RATE_LIMIT_PER_MINUTE:
            return False
        self.window_requests[k] += 1
        # cleanup old windows opportunistically
        if len(self.window_requests) > 10000:
            current_prefix = k.split(":")[1]
            self.window_requests = {kk: vv for kk, vv in self.window_requests.items() if kk.endswith(current_prefix)}
        return True


rate_limiter = SimpleRateLimiter()


async def enforce_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return True


# ---------------------------------------------------------------------------
# OIDC / User auth dependencies
# ---------------------------------------------------------------------------

def _extract_bearer_token(request: Request) -> Optional[str]:
    """Pull the JWT from the Authorization: Bearer <token> header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    return None


async def get_optional_user(request: Request):
    """
    Try to resolve the current user from a Bearer token.
    Returns a User ORM object if authenticated, None otherwise.
    Never raises — safe to use on public endpoints.
    """
    from app.core.auth import validate_token, extract_user_info
    from app.core.database import SessionLocal
    from app.models.user import User

    token = _extract_bearer_token(request)
    if not token:
        return None

    try:
        claims = await validate_token(token)
    except Exception:
        return None

    user_info = extract_user_info(claims)
    if not user_info["provider_user_id"]:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.provider_user_id == user_info["provider_user_id"]
        ).first()

        if user is None:
            # Auto-create on first login
            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
            # M1: timing-safe comparison for admin email check
            email_lower = user_info["email"].lower()
            role = "admin" if any(
                hmac.compare_digest(email_lower, ae) for ae in admin_emails
            ) else "user"
            user = User(
                email=user_info["email"],
                name=user_info["name"] or user_info["email"],
                avatar_url=user_info["avatar_url"] or None,
                auth_provider="authentik",
                provider_user_id=user_info["provider_user_id"],
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            # M4: log auto-creation
            logger.info(f"Auto-created user: {user_info['email']}, role={role}")

        # Update last_login
        user.last_login_at = datetime.now(tz.utc)
        if user_info["name"] and user.name != user_info["name"]:
            user.name = user_info["name"]
        if user_info["avatar_url"] and user.avatar_url != user_info["avatar_url"]:
            user.avatar_url = user_info["avatar_url"]

        # Re-elect admin on every login (promote-only): heals config drift when
        # an email is added to ADMIN_EMAILS after the user row already exists.
        # Demotion stays a deliberate manual act.
        if user.role != "admin":
            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
            email_lower = user.email.lower()
            if any(hmac.compare_digest(email_lower, ae) for ae in admin_emails):
                user.role = "admin"
                logger.info(f"Promoted user to admin via ADMIN_EMAILS: {user.email}")
        db.commit()
        db.refresh(user)

        # Detach from session so it can be used outside
        db.expunge(user)
        return user
    finally:
        db.close()


def is_oidc_configured() -> bool:
    """C2: Raise on partial OIDC config — both must be set or both unset."""
    issuer = bool(settings.OIDC_ISSUER_URL)
    client = bool(settings.OIDC_CLIENT_ID)
    if issuer != client:
        raise ValueError("OIDC_ISSUER_URL and OIDC_CLIENT_ID must both be set or both unset")
    return issuer and client


async def get_current_user(request: Request):
    """
    Require an authenticated user. Raises 401 if not authenticated.
    When OIDC is not configured (local dev), raises 401 — callers that need
    graceful fallback should use get_optional_user instead.
    """
    user = await get_optional_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(request: Request):
    """
    Require an authenticated admin user. Raises 401/403 accordingly.
    C1: Only bypass auth in development environment when OIDC is not configured.
    """
    if not is_oidc_configured():
        if settings.ENVIRONMENT != "development":
            raise HTTPException(status_code=401, detail="Authentication not configured")
        return None  # Allow through in development only

    user = await get_current_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
