#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

export RUN_MODE="${RUN_MODE:-formal}"
export RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"

if [[ "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: RUN_MODE=formal RETRIEVAL_SCOPE=sample bash scripts/cmd/student_branch.sh

This entrypoint runs the frozen student branch only:
  distill -> train_student -> eval_student
EOF
  exit 0
fi

bash scripts/cmd/distill.sh
bash scripts/cmd/train_student.sh
bash scripts/cmd/eval_student.sh
