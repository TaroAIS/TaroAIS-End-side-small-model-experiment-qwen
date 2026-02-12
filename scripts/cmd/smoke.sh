#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

RUN_MODE=smoke RETRIEVAL_SCOPE=sample bash scripts/run_smoke.sh
