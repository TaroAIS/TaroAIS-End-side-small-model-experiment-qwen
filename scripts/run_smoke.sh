#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p results report_tiny || true

echo "[1/3] Run baseline on smoke data"
"$PYTHON_BIN" run_baseline_rag.py --config configs/baseline_rag.yaml --dataset smoke_data/minilongbench_tiny.jsonl --out results/baseline_tiny.jsonl

echo "[2/3] Run edge agent on smoke data"
"$PYTHON_BIN" run_agent.py --config configs/agent.yaml --dataset smoke_data/minilongbench_tiny.jsonl --out results/edge_agent_tiny.jsonl

echo "[3/3] Evaluate and generate report"
"$PYTHON_BIN" evaluate.py --gold smoke_data/minilongbench_tiny.jsonl --pred results/baseline_tiny.jsonl results/edge_agent_tiny.jsonl --out_dir report_tiny/

echo "Smoke test finished. Check report_tiny/."
