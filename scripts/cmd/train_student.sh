#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" train_student.py \
  --config configs/train_qlora.yaml \
  --train data/student_train.jsonl \
  --out_dir checkpoints/student
