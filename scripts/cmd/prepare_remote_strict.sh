#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" scripts/prepare_minilongbench.py \
  --mode remote \
  --split all \
  --strict_remote \
  --out data/minilongbench_{split}.jsonl \
  --source_meta data/minilongbench_source.json
