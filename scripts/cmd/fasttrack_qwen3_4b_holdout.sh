#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

DATASET="${DATASET:-data/main_eval/longbench_3tasks_holdout100.jsonl}"
INDEX_DIR="${INDEX_DIR:-data/index}"
OUT_DIR="${OUT_DIR:-results}"
REPORT_DIR="${REPORT_DIR:-report/fasttrack_holdout100_qwen3_4b}"

"$PYTHON_BIN" run_baseline_rag.py \
  --config configs/baseline_rag_qwen3_4b.yaml \
  --dataset "$DATASET" \
  --index_dir "$INDEX_DIR" \
  --out "$OUT_DIR/fasttrack_holdout100_baseline_rag_qwen3_4b.jsonl" \
  --run_mode "${RUN_MODE:-formal}" \
  --retrieval_scope "${RETRIEVAL_SCOPE:-sample}"

"$PYTHON_BIN" run_baseline_rag.py \
  --config configs/baseline_single_round_strong_qwen3_4b.yaml \
  --dataset "$DATASET" \
  --index_dir "$INDEX_DIR" \
  --out "$OUT_DIR/fasttrack_holdout100_baseline_single_round_strong_qwen3_4b.jsonl" \
  --run_mode "${RUN_MODE:-formal}" \
  --retrieval_scope "${RETRIEVAL_SCOPE:-sample}"

"$PYTHON_BIN" run_agent.py \
  --config configs/agent_qwen3_4b_fast.yaml \
  --dataset "$DATASET" \
  --index_dir "$INDEX_DIR" \
  --out "$OUT_DIR/fasttrack_holdout100_agent_qwen3_4b_fast.jsonl" \
  --run_mode "${RUN_MODE:-formal}" \
  --retrieval_scope "${RETRIEVAL_SCOPE:-sample}"

"$PYTHON_BIN" evaluate.py \
  --gold "$DATASET" \
  --pred \
  "$OUT_DIR/fasttrack_holdout100_baseline_rag_qwen3_4b.jsonl" \
  "$OUT_DIR/fasttrack_holdout100_baseline_single_round_strong_qwen3_4b.jsonl" \
  "$OUT_DIR/fasttrack_holdout100_agent_qwen3_4b_fast.jsonl" \
  --out_dir "$REPORT_DIR" \
  --run_mode "${RUN_MODE:-formal}"
