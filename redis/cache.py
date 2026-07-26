import os
import json
import logging
from typing import Optional, Any
from dotenv import load_dotenv

load_dotenv()

# Logger
logger = logging.getLogger("ksp-cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if REDIS_URL and REDIS_URL.strip() and REDIS_URL.lower() != "memory":
    try:
        import redis
        redis_client = redis.from_url(REDIS_URL, socket_timeout=2)
        # Ping to check if alive
        redis_client.ping()
        HAS_REDIS = True
        logger.info("Connected to Redis Cache server successfully.")
    except Exception as e:
        HAS_REDIS = False
        logger.warning(f"Redis is unavailable, using in-memory local dict cache fallback. Error: {e}")
else:
    HAS_REDIS = False
    logger.info("REDIS_URL disabled, using in-memory local dict cache fallback.")

# Local dictionary cache fallback
_memory_cache = {}

def get_cache(key: str) -> Optional[Any]:
    """Retrieves JSON object from cache"""
    if HAS_REDIS:
        try:
            val = redis_client.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
    else:
        return _memory_cache.get(key)
    return None

def set_cache(key: str, value: Any, expire_seconds: int = 3600) -> bool:
    """Stores object in cache as JSON"""
    if HAS_REDIS:
        try:
            redis_client.setex(key, expire_seconds, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
    else:
        _memory_cache[key] = value
        return True
    return False

def clear_cache():
    """Wipes the cache"""
    if HAS_REDIS:
        try:
            redis_client.flushdb()
        except Exception:
            pass
    else:
        global _memory_cache
        _memory_cache = {}
