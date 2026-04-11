#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

"$PYTHON_BIN" scripts/prepare_longbench_3tasks.py \
  --out_test data/main_eval/longbench_3tasks_test.jsonl \
  --source_meta data/manifests/longbench_3tasks_source.json \
  --registry data/manifests/dataset_registry.json

"$PYTHON_BIN" scripts/prepare_task_ext_corpus.py \
  --out_root data/train_ext \
  --registry data/manifests/dataset_registry.json \
  --versions data/manifests/dataset_versions.json

"$PYTHON_BIN" scripts/build_combined_ext_sets.py \
  --single_doc_dir data/train_ext/single_doc \
  --multi_doc_dir data/train_ext/multi_doc \
  --code_dir data/train_ext/code_qa \
  --out_train data/train_ext/combined_train.jsonl \
  --out_valid data/train_ext/combined_valid.jsonl \
  --manifest data/manifests/combined_ext_manifest.json

"$PYTHON_BIN" scripts/build_main_eval_sets_v2.py \
  --valid data/train_ext/combined_valid.jsonl \
  --canonical data/main_eval/longbench_3tasks_test.jsonl \
  --out_dev data/main_eval/longbench_3tasks_dev100.jsonl \
  --out_holdout data/main_eval/longbench_3tasks_holdout100.jsonl \
  --manifest data/manifests/main_eval_split_manifest.json
