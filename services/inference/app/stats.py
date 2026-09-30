"""In-process service metrics for the ops console (latency percentiles, cache and fallback rates)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

import numpy as np


class Stats:
    def __init__(self, window: int = 2000) -> None:
        self.started = time.time()
        self._lat: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self._times: deque = deque(maxlen=20000)
        self.counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, endpoint: str, ms: float) -> None:
        with self._lock:
            self._lat[endpoint].append(ms)
            self._times.append(time.time())
            self.counts[f"requests:{endpoint}"] += 1

    def incr(self, name: str) -> None:
        with self._lock:
            self.counts[name] += 1

    def snapshot(self) -> dict:
        with self._lock:
            now = time.time()
            latency = {}
            for ep, vals in self._lat.items():
                a = np.fromiter(vals, dtype=float)
                latency[ep] = {"n": len(a), "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95)),
                               "p99": float(np.percentile(a, 99))}
            hits, misses = self.counts.get("cache_hit", 0), self.counts.get("cache_miss", 0)
            return {
                "uptime_seconds": now - self.started,
                "requests_last_minute": sum(1 for t in self._times if t > now - 60),
                "latency_ms": latency,
                "cache_hit_rate": hits / (hits + misses) if hits + misses else None,
                "counts": dict(self.counts),
            }
