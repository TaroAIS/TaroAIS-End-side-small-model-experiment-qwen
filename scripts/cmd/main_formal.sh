#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

export RUN_MODE="formal"
export RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"

bash scripts/cmd/preflight_formal.sh
bash scripts/cmd/prepare_remote_strict.sh
bash scripts/cmd/index.sh
bash scripts/cmd/baseline.sh
bash scripts/cmd/compare_controls.sh
bash scripts/cmd/agent.sh
bash scripts/cmd/eval.sh
bash scripts/cmd/ablations.sh
