#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

RUN_MODE="${RUN_MODE:-formal}"
RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"
SEEDS="${SEEDS:-42 123 2026}"
OUT_ROOT="${OUT_ROOT:-report_key}"
INDEX_DIR="${INDEX_DIR:-data/index}"
BASELINE_CONFIG="${BASELINE_CONFIG:-configs/baseline_rag.yaml}"
AGENT_CONFIG="${AGENT_CONFIG:-configs/agent.yaml}"

if [[ "$RUN_MODE" == "smoke" ]]; then
  DATASET="${DATASET:-smoke_data/minilongbench_tiny.jsonl}"
else
  DATASET="${DATASET:-data/minilongbench_test.jsonl}"
fi

if [[ "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: RUN_MODE=formal RETRIEVAL_SCOPE=sample SEEDS="42 123 2026" bash scripts/cmd/bench_key_tasks.sh

Env:
  RUN_MODE=smoke|formal            default: formal
  RETRIEVAL_SCOPE=sample|global    default: sample
  SEEDS="42 123 2026"              default: 3 seeds
  OUT_ROOT=report_key              output root
  DATASET=...                      default depends on RUN_MODE
  INDEX_DIR=data/index
  BASELINE_CONFIG=configs/baseline_rag.yaml
  AGENT_CONFIG=configs/agent.yaml
EOF
  exit 0
fi

mkdir -p "$OUT_ROOT"

if [[ "$RUN_MODE" == "formal" ]]; then
  bash scripts/cmd/preflight_formal.sh
  if [[ ! -f data/minilongbench_test.jsonl ]]; then
    bash scripts/cmd/prepare_remote_strict.sh
  fi
  if [[ "$RETRIEVAL_SCOPE" == "global" && ! -f "${INDEX_DIR}/index_meta.json" ]]; then
    bash scripts/cmd/index.sh
  fi
fi

METRICS_LIST=()
TASK_LIST=()
KEY_LIST=()

for seed in $SEEDS; do
  seed_tag="seed_${seed}"
  out_dir="${OUT_ROOT}/${seed_tag}"
  mkdir -p "$out_dir"

  baseline_out="${out_dir}/baseline_rag.jsonl"
  agent_out="${out_dir}/edge_agent.jsonl"

  "$PYTHON_BIN" run_baseline_rag.py \
    --config "$BASELINE_CONFIG" \
    --dataset "$DATASET" \
    --index_dir "$INDEX_DIR" \
    --out "$baseline_out" \
    --run_mode "$RUN_MODE" \
    --retrieval_scope "$RETRIEVAL_SCOPE" \
    --seed "$seed"

  "$PYTHON_BIN" run_agent.py \
    --config "$AGENT_CONFIG" \
    --dataset "$DATASET" \
    --index_dir "$INDEX_DIR" \
    --out "$agent_out" \
    --run_mode "$RUN_MODE" \
    --retrieval_scope "$RETRIEVAL_SCOPE" \
    --seed "$seed"

  "$PYTHON_BIN" evaluate.py \
    --gold "$DATASET" \
    --pred "$baseline_out" "$agent_out" \
    --out_dir "$out_dir" \
    --run_mode "$RUN_MODE" \
    --task_breakdown \
    --key_tasks multi_doc_qa code_qa \
    --key_agg macro \
    --run_tag "$seed_tag"

  METRICS_LIST+=("${out_dir}/metrics_table.csv")
  TASK_LIST+=("${out_dir}/task_metrics.csv")
  KEY_LIST+=("${out_dir}/key_task_summary.csv")
done

"$PYTHON_BIN" scripts/aggregate_seed_runs.py \
  --metrics "${METRICS_LIST[@]}" \
  --task_metrics "${TASK_LIST[@]}" \
  --key_summary "${KEY_LIST[@]}" \
  --out_dir "$OUT_ROOT" \
  --key_tasks multi_doc_qa code_qa \
  --key_agg macro \
  --baseline_method baseline_rag \
  --agent_method edge_agent \
  --min_delta_f1 0.03 \
  --max_latency_ratio 1.5 \
  --max_retrieval_ratio 1.8

echo "key-task benchmark done -> ${OUT_ROOT}"
