#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ "${RUN_MODE:-formal}" == "smoke" ]]; then
  GOLD_DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
else
  GOLD_DATASET="${DATASET:-data/main_eval/longbench_3tasks_test.jsonl}"
fi

PRED_FILES=("results/baseline_rag.jsonl")
if [[ -f results/baseline_budget_matched.jsonl ]]; then
  PRED_FILES+=("results/baseline_budget_matched.jsonl")
fi
if [[ -f results/baseline_single_round_strong.jsonl ]]; then
  PRED_FILES+=("results/baseline_single_round_strong.jsonl")
fi
PRED_FILES+=("results/edge_agent.jsonl")

"$PYTHON_BIN" evaluate.py \
  --gold "$GOLD_DATASET" \
  --pred "${PRED_FILES[@]}" \
  --out_dir report/ \
  --run_mode "$RUN_MODE" \
  --task_breakdown
