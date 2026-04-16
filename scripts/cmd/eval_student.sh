#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ "${RUN_MODE:-formal}" == "smoke" ]]; then
  HOLDOUT_DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
  CANONICAL_DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
else
  HOLDOUT_DATASET="${HOLDOUT_DATASET:-data/main_eval/longbench_3tasks_holdout100.jsonl}"
  CANONICAL_DATASET="${CANONICAL_DATASET:-data/main_eval/longbench_3tasks_test.jsonl}"
fi

"$PYTHON_BIN" scripts/eval_student_controller.py \
  --agent_config configs/agent.yaml \
  --dataset "$HOLDOUT_DATASET" \
  --checkpoint checkpoints/student \
  --out_dir report_student/holdout100 \
  --run_mode "$RUN_MODE"

"$PYTHON_BIN" scripts/eval_student_controller.py \
  --agent_config configs/agent.yaml \
  --dataset "$CANONICAL_DATASET" \
  --checkpoint checkpoints/student \
  --out_dir report_student/canonical \
  --run_mode "$RUN_MODE"
