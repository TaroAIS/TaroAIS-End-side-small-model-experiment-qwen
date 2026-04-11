#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ "${RUN_MODE:-formal}" == "smoke" ]]; then
  DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
else
  DATASET="${DATASET:-data/main_eval/longbench_3tasks_test.jsonl}"
fi

INDEX_DIR="${INDEX_DIR:-data/index}"

"$PYTHON_BIN" run_baseline_rag.py \
  --config configs/baseline_budget_matched.yaml \
  --dataset "$DATASET" \
  --index_dir "$INDEX_DIR" \
  --out results/baseline_budget_matched.jsonl \
  --run_mode "$RUN_MODE" \
  --retrieval_scope "$RETRIEVAL_SCOPE"

"$PYTHON_BIN" run_baseline_rag.py \
  --config configs/baseline_single_round_strong.yaml \
  --dataset "$DATASET" \
  --index_dir "$INDEX_DIR" \
  --out results/baseline_single_round_strong.jsonl \
  --run_mode "$RUN_MODE" \
  --retrieval_scope "$RETRIEVAL_SCOPE"
