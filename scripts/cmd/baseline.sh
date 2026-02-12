#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" run_baseline_rag.py \
  --config configs/baseline_rag.yaml \
  --dataset data/minilongbench_test.jsonl \
  --index_dir data/index \
  --out results/baseline_rag.jsonl
