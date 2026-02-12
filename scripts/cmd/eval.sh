#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" evaluate.py \
  --gold data/minilongbench_test.jsonl \
  --pred results/baseline_rag.jsonl results/edge_agent.jsonl \
  --out_dir report/
