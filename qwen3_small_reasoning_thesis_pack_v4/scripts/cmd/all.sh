#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

bash scripts/cmd/prepare_remote.sh
bash scripts/cmd/index.sh
bash scripts/cmd/baseline.sh
bash scripts/cmd/agent.sh
bash scripts/cmd/eval.sh
bash scripts/cmd/ablations.sh
bash scripts/cmd/distill.sh
bash scripts/cmd/train_student.sh
bash scripts/cmd/eval_student.sh
