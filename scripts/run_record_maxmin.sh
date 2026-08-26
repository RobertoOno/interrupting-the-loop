#!/bin/sh
# Record attempt on maxmin16 (pre-registered PLANO 2026-08-26 ~03:40):
# local arms B then D at 600 samples (sequential, one model process);
# the Claude arm is launched separately in parallel (API-only, guard-exempt).
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit; R=runs/frontier/record; mkdir -p $R
COMMON="--model $M --chat --max-tokens 1400 --temp 0.8 --gens 50 --samples 6 --islands 2 --seed 2"
echo "RECORD-MAXMIN START $(date)"
$PY scripts/frontier_search.py --problem maxmin16 $COMMON --memory schema --out $R/maxmin16_B600 > $R/maxmin16_B600.log 2>&1
echo "B600 DONE $(date)"
$PY scripts/frontier_search.py --problem maxmin16 $COMMON --novelty behavior --repel-prompt --out $R/maxmin16_D600 > $R/maxmin16_D600.log 2>&1
echo "RECORD-MAXMIN DONE $(date)"
