"""缓存抽象：memory（默认） / redis（可选）"""
from __future__ import annotations
import json
import time
from app.config import settings


class _MemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        expire_at, val = item
        if expire_at < time.time():
            self._store.pop(key, None)
            return None
        return json.loads(val)

    def set(self, key: str, value, ttl: int = 300):
        self._store[key] = (time.time() + ttl, json.dumps(value, ensure_ascii=False))


class _RedisCache:
    def __init__(self, url: str):
        import redis
        self._r = redis.from_url(url)

    def get(self, key: str):
        v = self._r.get(key)
        return json.loads(v) if v else None

    def set(self, key: str, value, ttl: int = 300):
        self._r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)


_singleton = None


def get_cache():
    global _singleton
    if _singleton is None:
        if settings.cache_backend == "redis":
            _singleton = _RedisCache(settings.redis_url)
        else:
            _singleton = _MemoryCache()
    return _singleton
