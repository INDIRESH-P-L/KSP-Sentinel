"""Redis-backed brute-force lockout, with an in-memory fallback that actually
respects TTLs (unlike redis/cache.py's fallback, which stores values forever with no
expiry -- fine for a demo data cache, not usable for a ban that must eventually lift).

Policy: 5 failed logins from the same IP within 5 minutes -> that IP is banned for
24 hours. A successful login clears the IP's failure counter. Tracked by IP rather
than username so a distributed attacker rotating usernames against one IP is still
caught, and so a legitimate user isn't locked out by someone else guessing their
username from a different IP.
"""
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ksp-brute-force")

FAIL_WINDOW_SECONDS = 5 * 60
FAIL_THRESHOLD = 5
BAN_SECONDS = 24 * 60 * 60

try:
    import redis
    _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _redis = redis.from_url(_redis_url, socket_timeout=2)
    _redis.ping()
    _HAS_REDIS = True
    logger.info("brute_force: connected to Redis.")
except Exception as e:
    _HAS_REDIS = False
    logger.warning(f"brute_force: Redis unavailable, using in-memory fallback (single-process only). {e}")

# {key: (value:int, expires_at:float)} -- only used when Redis is unavailable.
_memory_store: dict[str, tuple[int, float]] = {}


def _mem_get(key: str) -> int | None:
    entry = _memory_store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() >= expires_at:
        del _memory_store[key]
        return None
    return value


def _mem_incr(key: str, ttl_seconds: int) -> int:
    current = _mem_get(key) or 0
    new_value = current + 1
    # Preserve original expiry on repeated increments within the window, same as
    # Redis INCR+EXPIRE-if-new below -- otherwise every failed attempt would push the
    # ban window out indefinitely instead of it being a fixed 5-minute rolling count.
    existing = _memory_store.get(key)
    expires_at = existing[1] if existing and existing[1] > time.time() else time.time() + ttl_seconds
    _memory_store[key] = (new_value, expires_at)
    return new_value


def _mem_set(key: str, value: int, ttl_seconds: int) -> None:
    _memory_store[key] = (value, time.time() + ttl_seconds)


def _mem_delete(key: str) -> None:
    _memory_store.pop(key, None)


def _fail_key(ip: str) -> str:
    return f"login_fail_ip:{ip}"


def _ban_key(ip: str) -> str:
    return f"banned_ip:{ip}"


def is_banned(ip: str) -> bool:
    if _HAS_REDIS:
        try:
            return _redis.exists(_ban_key(ip)) > 0
        except Exception as e:
            logger.error(f"brute_force: Redis is_banned check failed, failing open: {e}")
            return False  # fail open on infra error -- don't lock out the whole app because Redis hiccuped
    return _mem_get(_ban_key(ip)) is not None


def record_failed_login(ip: str) -> None:
    """Increments the IP's failure count; bans the IP if it crosses the threshold."""
    if _HAS_REDIS:
        try:
            pipe = _redis.pipeline()
            pipe.incr(_fail_key(ip))
            pipe.expire(_fail_key(ip), FAIL_WINDOW_SECONDS, nx=True)  # only set TTL on first increment
            count, _ = pipe.execute()
            if count >= FAIL_THRESHOLD:
                _redis.setex(_ban_key(ip), BAN_SECONDS, 1)
                logger.warning(f"brute_force: IP {ip} banned for {BAN_SECONDS}s after {count} failed logins.")
        except Exception as e:
            logger.error(f"brute_force: Redis record_failed_login failed: {e}")
        return

    count = _mem_incr(_fail_key(ip), FAIL_WINDOW_SECONDS)
    if count >= FAIL_THRESHOLD:
        _mem_set(_ban_key(ip), 1, BAN_SECONDS)
        logger.warning(f"brute_force: IP {ip} banned for {BAN_SECONDS}s after {count} failed logins.")


def clear_failed_logins(ip: str) -> None:
    """Called on successful login -- resets the failure counter (does not lift an
    already-active ban; a banned IP stays banned for the full window even if it
    eventually supplies correct credentials, since that's also what a compromised-
    credentials brute force looks like from the outside)."""
    if _HAS_REDIS:
        try:
            _redis.delete(_fail_key(ip))
        except Exception as e:
            logger.error(f"brute_force: Redis clear_failed_logins failed: {e}")
        return
    _mem_delete(_fail_key(ip))
