#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

RUN_MODE="${RUN_MODE:-formal}"
RETRIEVAL_SCOPE="${RETRIEVAL_SCOPE:-sample}"
PER_SOURCE="${PER_SOURCE:-50}"
SEED="${SEED:-42}"
OUT_DATA_DIR="${OUT_DATA_DIR:-data/main_eval/code_generalization}"
OUT_MANIFEST="${OUT_MANIFEST:-data/manifests/code_generalization_appendix_manifest.json}"
PY_VALID="${PY_VALID:-data/train_ext/code_qa/repobench_python_valid.jsonl}"
JAVA_VALID="${JAVA_VALID:-data/train_ext/code_qa/repobench_java_valid.jsonl}"
INDEX_DIR="${INDEX_DIR:-data/index}"
RESULT_ROOT="${RESULT_ROOT:-results/code_generalization_appendix}"
REPORT_ROOT="${REPORT_ROOT:-report_code_generalization}"
BASELINE_CONFIG="${BASELINE_CONFIG:-configs/baseline_rag.yaml}"
AGENT_CONFIG="${AGENT_CONFIG:-configs/agent.yaml}"

if [[ ! -f "$PY_VALID" || ! -f "$JAVA_VALID" ]]; then
  echo "missing RepoBench appendix sources; expected:"
  echo "  - $PY_VALID"
  echo "  - $JAVA_VALID"
  echo "run scripts/prepare_task_ext_corpus.py or prepare_remote_strict.sh first"
  exit 1
fi

"$PYTHON_BIN" scripts/build_code_generalization_subset.py \
  --python_valid "$PY_VALID" \
  --java_valid "$JAVA_VALID" \
  --out_dir "$OUT_DATA_DIR" \
  --manifest "$OUT_MANIFEST" \
  --per_source "$PER_SOURCE" \
  --seed "$SEED"

mkdir -p "$RESULT_ROOT" "$REPORT_ROOT"

for split in repobench_python_appendix repobench_java_appendix code_generalization_appendix; do
  DATASET="${OUT_DATA_DIR}/${split}.jsonl"
  SPLIT_RESULT_DIR="${RESULT_ROOT}/${split}"
  SPLIT_REPORT_DIR="${REPORT_ROOT}/${split}"
  mkdir -p "$SPLIT_RESULT_DIR" "$SPLIT_REPORT_DIR"

  "$PYTHON_BIN" run_baseline_rag.py \
    --config "$BASELINE_CONFIG" \
    --dataset "$DATASET" \
    --index_dir "$INDEX_DIR" \
    --out "${SPLIT_RESULT_DIR}/baseline_rag.jsonl" \
    --run_mode "$RUN_MODE" \
    --retrieval_scope "$RETRIEVAL_SCOPE" \
    --seed "$SEED"

  "$PYTHON_BIN" run_agent.py \
    --config "$AGENT_CONFIG" \
    --dataset "$DATASET" \
    --index_dir "$INDEX_DIR" \
    --out "${SPLIT_RESULT_DIR}/edge_agent.jsonl" \
    --run_mode "$RUN_MODE" \
    --retrieval_scope "$RETRIEVAL_SCOPE" \
    --seed "$SEED"

  "$PYTHON_BIN" evaluate.py \
    --gold "$DATASET" \
    --pred "${SPLIT_RESULT_DIR}/baseline_rag.jsonl" "${SPLIT_RESULT_DIR}/edge_agent.jsonl" \
    --out_dir "$SPLIT_REPORT_DIR" \
    --run_mode "$RUN_MODE" \
    --task_breakdown \
    --run_tag "$split"
done

echo "code generalization appendix done -> ${REPORT_ROOT}"
