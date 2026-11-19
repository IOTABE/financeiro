from __future__ import annotations

from django.core.cache import cache

from .audit import client_ip


def check_rate_limit(
    request,
    *,
    key: str,
    limit: int,
    window_seconds: int,
    identifier: str | None = None,
) -> bool:
    """Return True when the request is allowed, False when the limit is hit."""
    if limit <= 0:
        return True
    identity = identifier or client_ip(request) or "unknown"
    cache_key = f"ratelimit:{key}:{identity}"
    try:
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, timeout=window_seconds)
            return True
        if int(current) >= limit:
            return False
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, int(current) + 1, timeout=window_seconds)
        return True
    except Exception:
        # Fail open on cache outage: availability over strict throttling.
        return True
