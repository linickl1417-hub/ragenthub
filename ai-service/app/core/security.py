"""Access control: API-key authentication and per-caller rate limiting.

Both are opt-in and controlled by environment variables:

    API_KEY                  # empty = auth disabled (development mode)
    RATE_LIMIT_PER_MINUTE    # 0 = rate limiting disabled

The API key is compared in constant time. The rate limiter uses the shared
cache backend, so with RATE_LIMIT_PER_MINUTE and CACHE_BACKEND=redis the budget
is enforced across replicas rather than per process.
"""
from __future__ import annotations

import hmac
import logging
import time

from fastapi import Header, HTTPException, Request, status

from app.config import settings
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

# Endpoints that must stay reachable without a key: probes and the static UI.
OPEN_PATHS = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/web",
)


def is_open_path(path: str) -> bool:
    """Exact match, or a sub-path of a listed prefix.

    "/" is handled separately: treating it as a prefix would make every path
    look open (``"anything".startswith("/")`` is always true).
    """
    if path == "/":
        return True
    return any(path == p or path.startswith(f"{p}/") for p in OPEN_PATHS)


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Reject requests that do not carry the configured API key."""
    if not settings.api_key:
        return  # development mode

    presented = x_api_key
    if not presented and authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()

    if not presented or not hmac.compare_digest(presented, settings.api_key):
        logger.warning("Rejected request with missing/invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": 'ApiKey realm="ragenthub"'},
        )


def caller_identity(request: Request) -> str:
    """Identify the caller for rate limiting: API key first, then client IP."""
    key = request.headers.get("x-api-key")
    if key:
        return f"key:{key[:16]}"
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return f"key:{auth[7:23]}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def check_rate_limit(identity: str) -> tuple[bool, int]:
    """Fixed one-minute window counter. Returns (allowed, retry_after_seconds).

    The key is scoped to the current minute, so the counter resets on the
    boundary. ``Retry-After`` is the time left in that window, not the key TTL
    (the TTL is longer on purpose so a key never disappears mid-window).
    """
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return True, 0

    now = time.time()
    window = int(now // 60)
    reset_in = int(60 - (now % 60))
    key = f"ratelimit:{identity}:{window}"
    cache = get_cache()

    try:
        count = cache.incr(key, ttl=90)
    except Exception:  # noqa: BLE001 - never fail a request because the limiter broke
        logger.warning("Rate limiter unavailable, allowing request")
        return True, 0

    if count > limit:
        return False, max(1, reset_in)

    return True, 0
