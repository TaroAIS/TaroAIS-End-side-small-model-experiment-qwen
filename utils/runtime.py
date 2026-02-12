import os
import platform
from datetime import datetime
from pathlib import Path

from utils.io import ensure_dir


def project_root():
    return Path(__file__).resolve().parents[1]


def schema_path(name):
    return project_root() / "schemas" / name


def create_run_dir(base_dir="results"):
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(base_dir) / ("run_" + ts)
    ensure_dir(run_dir)
    return run_dir


def detect_hardware():
    gpu_name = "none"
    gpu_mem_mb = 0.0
    try:
        import pynvml

        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(h).decode("utf-8")
        info = pynvml.nvmlDeviceGetMemoryInfo(h)
        gpu_mem_mb = float(info.total) / (1024.0 * 1024.0)
        pynvml.nvmlShutdown()
    except Exception:
        pass

    return {
        "gpu_name": gpu_name,
        "gpu_mem_mb": gpu_mem_mb,
        "cpu": platform.processor() or platform.machine(),
    }
