#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_MODE="${RUN_MODE:-formal}"
RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"

DATASET="${1:-data/minilongbench_test.jsonl}"
INDEX_DIR="${2:-data/index}"
OUT_DIR="results/ablations"
REPORT_DIR="report"

mkdir -p "$OUT_DIR" "$REPORT_DIR"

"$PYTHON_BIN" run_agent.py --config configs/agent_think_off.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/think_off.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_iterative_off.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/iterative_off.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_memory_sliding.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/memory_sliding.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_inj_defense_off.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/inj_defense_off.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"

"$PYTHON_BIN" evaluate.py --gold "$DATASET" --pred \
  "$OUT_DIR/think_off.jsonl" \
  "$OUT_DIR/iterative_off.jsonl" \
  "$OUT_DIR/memory_sliding.jsonl" \
  "$OUT_DIR/inj_defense_off.jsonl" \
  --out_dir "$REPORT_DIR" \
  --run_mode "$RUN_MODE"

echo "ablations done -> $OUT_DIR"
