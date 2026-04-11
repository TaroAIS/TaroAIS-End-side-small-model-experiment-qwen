#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

DATASET="${DATASET:-data/train_ext/combined_train.jsonl}"

"$PYTHON_BIN" scripts/distill_controller_data.py \
  --teacher_config configs/teacher_distill.yaml \
  --dataset "$DATASET" \
  --out data/student_train.jsonl \
  --run_mode "$RUN_MODE"
