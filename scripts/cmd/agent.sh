#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" run_agent.py \
  --config configs/agent.yaml \
  --dataset data/minilongbench_test.jsonl \
  --index_dir data/index \
  --out results/edge_agent.jsonl \
  --run_mode "$RUN_MODE" \
  --retrieval_scope "$RETRIEVAL_SCOPE"
