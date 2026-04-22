#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

REPORT_DIR="${REPORT_DIR:-report/formal_paper_canonical_s42_current}"
OUT_DIR="${OUT_DIR:-${REPORT_DIR}/paper_figures}"

"$PYTHON_BIN" scripts/render_paper_figures.py \
  --report_dir "$REPORT_DIR" \
  --out_dir "$OUT_DIR"
