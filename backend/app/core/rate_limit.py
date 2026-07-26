"""Shared slowapi Limiter instance, plus a manual global rate-limit check.

Uses Redis-backed storage when Redis is reachable (survives restarts, shared across
worker processes), and falls back to slowapi's in-memory storage otherwise --
checked once at import time the same way redis/cache.py and brute_force.py do, so
rate limiting still works on a machine with no Redis running (like this one) instead
of crashing the app at startup.

`limiter` (the `@limiter.limit("N/period")` decorator) is used directly on
login/verify-otp/chatbot for their tighter per-route limits -- verified working via
isolated TestClient runs (a 3/minute-decorated route correctly returns
200,200,200,429,429,429).

The blanket "100/minute per IP across the whole API" requirement is NOT implemented
via slowapi's `default_limits` + `SlowAPIMiddleware`: that combination silently never
triggers on this FastAPI/Starlette version for any route that isn't itself
individually `@limiter.limit()`-decorated (confirmed by isolated reproduction -- an
undecorated route with `default_limits=["3/minute"]` returned 200 six times in a
row). Rather than ship a "security control" that's provably a no-op, the global limit
is enforced by check_global_rate_limit() below, applied in main.py's middleware,
using the exact same proven counter-with-TTL approach as brute_force.py.
"""
import os
import time
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ksp-rate-limit")

GLOBAL_LIMIT_PER_MINUTE = 100
_WINDOW_SECONDS = 60

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_storage_uri = None
_redis_client = None

if _redis_url and _redis_url.strip() and _redis_url.lower() != "memory":
    try:
        import redis
        _redis_client = redis.from_url(_redis_url, socket_timeout=2)
        _redis_client.ping()
        _storage_uri = _redis_url
        logger.info("rate_limit: using Redis-backed limiter storage.")
    except Exception as e:
        _redis_client = None
        logger.warning(f"rate_limit: Redis unavailable, using in-memory limiter storage (single-process only). {e}")
else:
    logger.info("rate_limit: REDIS_URL disabled, using in-memory limiter storage (single-process only).")

limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)

# {ip: (count:int, window_expires_at:float)} -- in-memory fallback for the global check.
_global_mem_counts: dict[str, tuple[int, float]] = {}


def check_global_rate_limit(client_ip: str) -> bool:
    """Returns True if the request is allowed, False if this IP should get a 429.
    Fixed 60s window, reset by whichever request first lands after expiry."""
    if _redis_client is not None:
        try:
            key = f"global_rate:{client_ip}"
            pipe = _redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, _WINDOW_SECONDS, nx=True)
            count, _ = pipe.execute()
            return count <= GLOBAL_LIMIT_PER_MINUTE
        except Exception as e:
            logger.error(f"rate_limit: Redis global check failed, failing open: {e}")
            return True  # infra error shouldn't take the whole API down

    now = time.time()
    entry = _global_mem_counts.get(client_ip)
    if entry is None or now >= entry[1]:
        _global_mem_counts[client_ip] = (1, now + _WINDOW_SECONDS)
        return True
    count, expires_at = entry
    count += 1
    _global_mem_counts[client_ip] = (count, expires_at)
    return count <= GLOBAL_LIMIT_PER_MINUTE
