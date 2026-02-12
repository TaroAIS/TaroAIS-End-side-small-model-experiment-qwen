#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" scripts/eval_student_controller.py \
  --agent_config configs/agent.yaml \
  --dataset data/minilongbench_test.jsonl \
  --checkpoint checkpoints/student \
  --out_dir report_student/
