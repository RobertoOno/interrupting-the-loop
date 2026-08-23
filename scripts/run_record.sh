#!/bin/sh
# Record attempt on beat-the-average: arms E then D, 600 samples each, sequential.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit; R=runs/frontier/record; mkdir -p $R
COMMON="--model $M --chat --max-tokens 1400 --temp 0.8 --gens 50 --samples 6 --islands 2"
echo "RECORD START $(date)"
$PY scripts/frontier_search.py --problem beatavg $COMMON --memory schema --agenda --novelty behavior --repel-prompt --out $R/beatavg_E600 > $R/beatavg_E600.log 2>&1
echo "E DONE $(date)"
$PY scripts/frontier_search.py --problem beatavg $COMMON --novelty behavior --repel-prompt --out $R/beatavg_D600 > $R/beatavg_D600.log 2>&1
echo "RECORD DONE $(date)"
