#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" scripts/build_corpus.py \
  --in data/minilongbench_train.jsonl \
  --out data/corpus_chunks.jsonl \
  --index_dir data/index/
