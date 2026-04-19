#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

mkdir -p docs

"$PYTHON_BIN" binance_spot_candle_analyzer.py \
  --quote-assets USDT \
  --log-file scan_log_usdt.txt \
  > scan_results_usdt.csv \
  2> scan_err_usdt.txt

"$PYTHON_BIN" build_scan_html.py \
  --input scan_results_usdt.csv \
  --output docs/index.html

echo "Daily scan completed. Public page file: docs/index.html"