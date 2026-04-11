#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ "${RUN_MODE:-formal}" == "smoke" ]]; then
  DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
else
  DATASET="${DATASET:-data/main_eval/longbench_3tasks_test.jsonl}"
fi
INDEX_DIR="${INDEX_DIR:-data/index}"

bash scripts/run_ablations.sh "$DATASET" "$INDEX_DIR"
