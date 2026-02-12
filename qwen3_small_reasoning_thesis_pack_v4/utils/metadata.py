import os
import platform
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from utils.io import ensure_dir, write_json
from utils.schema import validate_record


def _get_git_commit(repo_dir):
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _get_ram_gb():
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        total = pages * page_size
        return round(total / (1024.0 ** 3), 2)
    except Exception:
        return 0.0


def _seed_values(seed):
    val = int(seed)
    random.seed(val)
    return {"python": val, "numpy": val, "torch": val}


def write_run_metadata(
    run_dir,
    schema_path,
    config_paths,
    model_info,
    hardware,
    seed=42,
    notes="",
    repo_dir=".",
):
    run_dir = Path(run_dir)
    ensure_dir(run_dir)
    run_id = run_dir.name
    metadata = {
        "run_id": run_id,
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _get_git_commit(repo_dir),
        "config_paths": [str(p) for p in config_paths],
        "model_info": model_info,
        "hardware": {
            "gpu_name": hardware.get("gpu_name", "unknown"),
            "gpu_mem_mb": float(hardware.get("gpu_mem_mb", 0.0)),
            "cpu": hardware.get("cpu", platform.processor() or platform.machine()),
            "ram_gb": float(hardware.get("ram_gb", _get_ram_gb())),
        },
        "seeds": _seed_values(seed),
        "notes": notes,
    }
    from utils.io import read_json

    schema = read_json(schema_path)
    validate_record(metadata, schema, context="run_metadata")
    write_json(run_dir / "metadata.json", metadata)
    return metadata


def snapshot_configs(config_paths, out_dir):
    out_dir = Path(out_dir)
    ensure_dir(out_dir)
    saved = []
    for cfg in config_paths:
        src = Path(cfg)
        if not src.exists():
            continue
        dst = out_dir / src.name
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        saved.append(str(dst))
    return saved
