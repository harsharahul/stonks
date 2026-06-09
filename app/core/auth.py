"""
OIDC JWT validation for Authentik
- Fetches and caches JWKS keys from Authentik's well-known endpoint
- Validates JWT signature, expiry, issuer, audience
- Extracts user claims (sub, email, name, picture)
"""
import logging
import time
from typing import Dict, Any
from urllib.parse import urlparse

import httpx
from jose import jwt, JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

# JWKS cache: { "keys": [...], "fetched_at": float }
_jwks_cache: Dict[str, Any] = {}
_JWKS_CACHE_TTL = 6 * 3600  # 6 hours


async def _fetch_oidc_discovery() -> dict:
    """Fetch and cache the full OpenID Connect discovery document."""
    issuer_url = settings.OIDC_ISSUER_URL.rstrip("/")
    oidc_config_url = f"{issuer_url}/.well-known/openid-configuration"

    async with httpx.AsyncClient(timeout=10) as client:
        config_resp = await client.get(oidc_config_url)
        config_resp.raise_for_status()
        return config_resp.json()


async def _fetch_jwks() -> list:
    """Fetch JWKS from Authentik's well-known endpoint, with caching."""
    now = time.time()
    if _jwks_cache and (now - _jwks_cache.get("fetched_at", 0)) < _JWKS_CACHE_TTL:
        return _jwks_cache["keys"]

    oidc_config = await _fetch_oidc_discovery()
    jwks_uri = oidc_config["jwks_uri"]

    # Cache the canonical issuer from the discovery doc (may differ in trailing slash)
    _jwks_cache["issuer"] = oidc_config.get("issuer", settings.OIDC_ISSUER_URL)

    # C3: Validate JWKS URI matches issuer domain and uses HTTPS
    issuer_host = urlparse(settings.OIDC_ISSUER_URL).netloc
    jwks_host = urlparse(jwks_uri).netloc
    if jwks_host != issuer_host:
        raise ValueError(f"JWKS URI domain {jwks_host} does not match issuer {issuer_host}")
    if not jwks_uri.startswith("https://"):
        raise ValueError("JWKS URI must use HTTPS")

    async with httpx.AsyncClient(timeout=10) as client:
        jwks_resp = await client.get(jwks_uri)
        jwks_resp.raise_for_status()
        keys = jwks_resp.json().get("keys", [])

    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    logger.info(f"JWKS refreshed: {len(keys)} key(s) from {jwks_uri}")
    return keys


def _get_cached_jwks() -> list:
    """Return cached JWKS synchronously (used as fallback)."""
    return _jwks_cache.get("keys", [])


async def validate_token(token: str) -> Dict[str, Any]:
    """
    Validate an Authentik access or ID token.
    Returns the decoded claims dict on success.
    Raises ValueError with a descriptive message on failure.
    """
    from app.api.dependencies import is_oidc_configured
    if not is_oidc_configured():
        raise ValueError("OIDC is not configured on this server")

    try:
        keys = await _fetch_jwks()
    except Exception as e:
        logger.warning(f"JWKS fetch failed, trying cache: {e}")
        keys = _get_cached_jwks()
        if not keys:
            raise ValueError("Cannot validate token: JWKS unavailable") from e

    # Use the canonical issuer from the discovery document (preserves trailing slash)
    issuer = _jwks_cache.get("issuer", settings.OIDC_ISSUER_URL)

    # C4: Always enforce audience validation — fall back to client_id if OIDC_AUDIENCE not set
    expected_audience = settings.OIDC_AUDIENCE or settings.OIDC_CLIENT_ID

    try:
        claims = jwt.decode(
            token,
            keys,
            algorithms=["RS256", "ES256"],
            issuer=issuer,
            audience=expected_audience,
            options={"verify_aud": True},
        )
    except JWTError as e:
        raise ValueError(f"Token validation failed: {e}") from e

    return claims


def extract_user_info(claims: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract standardised user fields from OIDC claims.
    Authentik uses standard OpenID Connect claim names.
    """
    return {
        "provider_user_id": claims.get("sub", ""),
        "email": claims.get("email", ""),
        "name": claims.get("name") or claims.get("preferred_username", ""),
        "avatar_url": claims.get("picture", ""),
    }
