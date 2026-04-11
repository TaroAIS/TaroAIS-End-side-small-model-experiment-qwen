#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

root = Path.cwd()
tiny_path = root / "smoke_data" / "minilongbench_tiny.jsonl"
rows = [json.loads(line) for line in tiny_path.read_text(encoding="utf-8").splitlines() if line.strip()]

def expand(src_rows, n, prefix):
    out = []
    for idx in range(n):
        row = dict(src_rows[idx % len(src_rows)])
        row["id"] = "{}_{}".format(prefix, idx + 1)
        row["meta"] = dict(row.get("meta", {}))
        row["meta"]["source"] = "local:smoke_data/minilongbench_tiny.jsonl"
        row["meta"]["source_split"] = prefix
        out.append(row)
    return out

targets = {
    "data/main_eval/longbench_3tasks_test.jsonl": expand(rows, 12, "canonical"),
    "data/main_eval/longbench_3tasks_dev100.jsonl": expand(rows, 12, "dev"),
    "data/main_eval/longbench_3tasks_holdout100.jsonl": expand(rows, 12, "holdout"),
    "data/train_ext/combined_train.jsonl": expand(rows, 30, "train"),
    "data/train_ext/combined_valid.jsonl": expand(rows, 12, "valid"),
}

for rel_path, data in targets.items():
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

manifest_dir = root / "data" / "manifests"
manifest_dir.mkdir(parents=True, exist_ok=True)
(manifest_dir / "dataset_versions.json").write_text(
    json.dumps(
        {
            "generated_by": "scripts/cmd/prepare_offline.sh",
            "mode": "offline_smoke",
            "datasets": {k: len(v) for k, v in targets.items()},
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print("offline data layout prepared")
PY
