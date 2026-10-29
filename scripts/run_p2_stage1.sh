#!/bin/sh
# Programa 2, stage 1 (pre-registered PLANO 2026-09-03): direct transplants for one proposer.
#   sh scripts/run_p2_stage1.sh opus|kimi   (opus needs AWS_PROFILE=main-account; kimi reads the OpenRouter key file)
# Opus: effort low, 8000 tokens (effort medium/high spent the whole budget thinking and returned no text: smokes 2-4).
set -u
cd "$(dirname "$0")/.." || exit 1
M="$1"; OUT=runs/p2/stage1; mkdir -p "$OUT"
PY=.venv/bin/python; export PYTHONPATH=src
EXTRA=""; [ "$M" = "opus" ] && EXTRA="--effort low --max-tokens 8000"
$PY scripts/transfer_correspond.py --target sumdiff3 --arm D --model "$M" --attempts 2 --workers 4 --out stage1 $EXTRA
$PY scripts/transfer_correspond.py --target sumdiff3 --arm C2 --model "$M" --attempts 1 --workers 4 --out stage1 $EXTRA
[ "$M" = "kimi" ] && $PY scripts/transfer_correspond.py --target sumdiff3 --arm C1 --out stage1
echo "CM-DONE $M"
