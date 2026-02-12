#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

echo "[preflight] checking formal dependencies and backends..."

"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

import requests
import yaml

import matplotlib  # noqa
import pandas  # noqa

ROOT = Path.cwd()

# Check remote dataset availability.
hf_api = "https://huggingface.co/api/datasets/linggm/MiniLongBench"
resp = requests.get(hf_api, timeout=20)
resp.raise_for_status()

cfg_paths = [ROOT / "configs" / "baseline_rag.yaml", ROOT / "configs" / "agent.yaml"]
for cfg_path in cfg_paths:
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    backend = str(cfg.get("model", {}).get("backend", "local")).lower()
    model_name = cfg.get("model", {}).get("name_or_path", "")
    if backend == "local":
        base_url = cfg.get("local_backend", {}).get("base_url", "http://localhost:11434/v1")
        endpoint = base_url.rstrip("/") + "/models"
        check = requests.get(endpoint, timeout=10)
        check.raise_for_status()
        payload = check.json() if check.headers.get("content-type", "").startswith("application/json") else {}
        ids = []
        for item in payload.get("data", []):
            if isinstance(item, dict):
                ids.append(item.get("id", ""))
        if ids and model_name and model_name not in ids:
            raise RuntimeError(
                "model '{}' not listed by local backend '{}'. available={}".format(
                    model_name, endpoint, json.dumps(ids[:20], ensure_ascii=False)
                )
            )
    elif backend == "hf":
        import transformers  # noqa
    else:
        raise RuntimeError("unsupported backend in {}: {}".format(cfg_path, backend))

print("[preflight] formal checks passed")
PY
