#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

EXTRA_ARGS=()
if [[ "$RUN_MODE" == "formal" ]]; then
  EXTRA_ARGS+=(--prefer_real)
fi

"$PYTHON_BIN" train_student.py \
  --config configs/train_qlora.yaml \
  --train data/student_train.jsonl \
  --out_dir checkpoints/student \
  --run_mode "$RUN_MODE" \
  "${EXTRA_ARGS[@]}"
