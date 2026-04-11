#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

export RUN_MODE="${RUN_MODE:-formal}"
export RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"

bash scripts/cmd/distill.sh
bash scripts/cmd/train_student.sh
bash scripts/cmd/eval_student.sh
