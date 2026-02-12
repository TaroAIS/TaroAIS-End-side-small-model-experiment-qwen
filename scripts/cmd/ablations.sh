#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

bash scripts/run_ablations.sh data/minilongbench_test.jsonl data/index
