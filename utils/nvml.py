
class NvmlMonitor(object):
    def __init__(self, sample_ms=200):
        self.sample_ms = int(sample_ms)
        self.series = []
        self.enabled = False
        self._handle = None
        try:
            import pynvml  # noqa

            self._pynvml = pynvml
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.enabled = True
        except Exception:
            self._pynvml = None
            self.enabled = False

    def sample(self):
        if not self.enabled:
            return 0.0
        try:
            info = self._pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            mb = float(info.used) / (1024.0 * 1024.0)
            self.series.append(mb)
            return mb
        except Exception:
            return 0.0

    def summary(self):
        if not self.series:
            self.sample()
        if not self.series:
            return {"peak": 0.0, "mean": 0.0, "series": []}
        peak = max(self.series)
        mean = sum(self.series) / float(len(self.series))
        return {"peak": float(peak), "mean": float(mean), "series": list(self.series)}

    def close(self):
        if self.enabled and self._pynvml is not None:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass
