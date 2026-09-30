"""Response cache: Redis when REDIS_URL is set, otherwise an in-process TTL cache."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict

log = logging.getLogger(__name__)


class MemoryCache:
    def __init__(self, ttl: int, max_items: int = 20000) -> None:
        self.ttl, self.max_items = ttl, max_items
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            hit = self._data.get(key)
            if not hit or hit[0] < time.monotonic():
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return json.loads(hit[1])

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, json.dumps(value))
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisCache:
    def __init__(self, url: str, ttl: int) -> None:
        import redis

        self.ttl = ttl
        self.r = redis.Redis.from_url(url, socket_timeout=0.05, socket_connect_timeout=0.2)

    def get(self, key: str):
        try:
            raw = self.r.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:  # cache must never take the service down
            log.warning("redis get failed: %s", e)
            return None

    def set(self, key: str, value) -> None:
        try:
            self.r.setex(key, self.ttl, json.dumps(value))
        except Exception as e:
            log.warning("redis set failed: %s", e)

    def clear(self) -> None:
        try:
            for k in self.r.scan_iter("rec:*"):
                self.r.delete(k)
        except Exception as e:
            log.warning("redis clear failed: %s", e)


def make_cache(url: str, ttl: int):
    if url:
        try:
            c = RedisCache(url, ttl)
            c.r.ping()
            log.info("Using Redis cache at %s", url)
            return c
        except Exception as e:
            log.warning("Redis unavailable (%s); falling back to in-memory cache", e)
    return MemoryCache(ttl)
