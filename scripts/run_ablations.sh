#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_MODE="${RUN_MODE:-formal}"
RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"

DATASET="${1:-data/main_eval/longbench_3tasks_test.jsonl}"
INDEX_DIR="${2:-data/index}"
OUT_DIR="results/ablations"
REPORT_DIR="report/ablations"

mkdir -p "$OUT_DIR" "$REPORT_DIR"

"$PYTHON_BIN" run_agent.py --config configs/agent_iterative_off.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/iterative_off.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_memory_sliding.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/memory_sliding.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_refine_gate_relaxed.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/refine_gate_relaxed.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_budget_tight.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/budget_tight.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_forced_retrieve_off.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/forced_retrieve_off.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"
"$PYTHON_BIN" run_agent.py --config configs/agent_early_stop_off.yaml --dataset "$DATASET" --index_dir "$INDEX_DIR" --out "$OUT_DIR/early_stop_off.jsonl" --run_mode "$RUN_MODE" --retrieval_scope "$RETRIEVAL_SCOPE"

"$PYTHON_BIN" evaluate.py --gold "$DATASET" --pred \
  "$OUT_DIR/iterative_off.jsonl" \
  "$OUT_DIR/memory_sliding.jsonl" \
  "$OUT_DIR/refine_gate_relaxed.jsonl" \
  "$OUT_DIR/budget_tight.jsonl" \
  "$OUT_DIR/forced_retrieve_off.jsonl" \
  "$OUT_DIR/early_stop_off.jsonl" \
  --out_dir "$REPORT_DIR" \
  --run_mode "$RUN_MODE"

echo "ablations done -> $OUT_DIR"
