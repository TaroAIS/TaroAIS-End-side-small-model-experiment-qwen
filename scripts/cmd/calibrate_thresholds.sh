#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

RUN_MODE="${RUN_MODE:-formal}"
RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"
SEEDS="${SEEDS:-42 123 2026}"
OUT_ROOT="${OUT_ROOT:-report_calibration}"
INDEX_DIR="${INDEX_DIR:-data/index}"
DATASET="${DATASET:-data/main_eval/longbench_3tasks_test.jsonl}"

BASELINE_CONFIGS=(
  "configs/baseline_rag.yaml"
  "configs/baseline_budget_matched.yaml"
  "configs/baseline_single_round_strong.yaml"
)
AGENT_CONFIGS=(
  "configs/agent.yaml"
  "configs/agent_iterative_off.yaml"
  "configs/agent_budget_tight.yaml"
)

if [[ "$RUN_MODE" == "formal" ]]; then
  bash scripts/cmd/preflight_formal.sh
  if [[ ! -f "$DATASET" ]]; then
    bash scripts/cmd/prepare_remote_strict.sh
  fi
  if [[ "$RETRIEVAL_SCOPE" == "global" && ! -f "${INDEX_DIR}/index_meta.json" ]]; then
    bash scripts/cmd/index.sh
  fi
fi

mkdir -p "$OUT_ROOT"

for seed in $SEEDS; do
  seed_dir="${OUT_ROOT}/seed_${seed}"
  mkdir -p "$seed_dir"
  pred_files=()

  for cfg in "${BASELINE_CONFIGS[@]}"; do
    stem="$(basename "$cfg" .yaml)"
    out_path="${seed_dir}/${stem}.jsonl"
    "$PYTHON_BIN" run_baseline_rag.py \
      --config "$cfg" \
      --dataset "$DATASET" \
      --index_dir "$INDEX_DIR" \
      --out "$out_path" \
      --run_mode "$RUN_MODE" \
      --retrieval_scope "$RETRIEVAL_SCOPE" \
      --seed "$seed"
    pred_files+=("$out_path")
  done

  for cfg in "${AGENT_CONFIGS[@]}"; do
    stem="$(basename "$cfg" .yaml)"
    out_path="${seed_dir}/${stem}.jsonl"
    "$PYTHON_BIN" run_agent.py \
      --config "$cfg" \
      --dataset "$DATASET" \
      --index_dir "$INDEX_DIR" \
      --out "$out_path" \
      --run_mode "$RUN_MODE" \
      --retrieval_scope "$RETRIEVAL_SCOPE" \
      --seed "$seed"
    pred_files+=("$out_path")
  done

  "$PYTHON_BIN" evaluate.py \
    --gold "$DATASET" \
    --pred "${pred_files[@]}" \
    --out_dir "$seed_dir" \
    --run_mode "$RUN_MODE" \
    --task_breakdown \
    --run_tag "seed_${seed}"
done

"$PYTHON_BIN" scripts/summarize_calibration_runs.py \
  --input_root "$OUT_ROOT" \
  --out_dir "$OUT_ROOT"
