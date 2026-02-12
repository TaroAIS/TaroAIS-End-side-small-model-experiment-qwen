import time
from contextlib import contextmanager


class PhaseTimer(object):
    def __init__(self):
        self._start = time.perf_counter()
        self.phases = {}

    @contextmanager
    def phase(self, name):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.phases[name] = self.phases.get(name, 0.0) + elapsed_ms

    def add_ms(self, name, elapsed_ms):
        self.phases[name] = self.phases.get(name, 0.0) + float(elapsed_ms)

    def summary(self):
        total = (time.perf_counter() - self._start) * 1000.0
        return {
            "total": float(total),
            "llm": float(self.phases.get("llm", 0.0)),
            "retrieval": float(self.phases.get("retrieval", 0.0)),
            "overhead": float(self.phases.get("overhead", 0.0)),
        }


def percentile(values, pct):
    if not values:
        return 0.0
    if pct <= 0:
        return float(min(values))
    if pct >= 100:
        return float(max(values))
    s = sorted(float(v) for v in values)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return float(d0 + d1)
