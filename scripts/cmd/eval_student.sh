#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ "${RUN_MODE:-formal}" == "smoke" ]]; then
  DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
else
  DATASET="${DATASET:-data/main_eval/longbench_3tasks_test.jsonl}"
fi

"$PYTHON_BIN" scripts/eval_student_controller.py \
  --agent_config configs/agent.yaml \
  --dataset "$DATASET" \
  --checkpoint checkpoints/student \
  --out_dir report_student/ \
  --run_mode "$RUN_MODE"
