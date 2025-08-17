from fastapi import Header, HTTPException, Request
from typing import Optional

from app.core.config import settings


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


