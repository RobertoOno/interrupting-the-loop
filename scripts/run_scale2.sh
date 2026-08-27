#!/bin/sh
# Scale test (pre-registered PLANO 2026-08-27; the review's "minimum experiment"):
# does BD hold its parsimony advantage at 5x budget, and does B alone compound?
# beatavg, 600 samples (50 gens x 6 x 2), arms B / BD / E, seeds 21/22/23.
# Waits for HINT DONE. Marker: SCALE2 DONE.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit; R=runs/frontier/scale2; mkdir -p $R
until grep -q "HINT DONE" runs/frontier/hint_chain.log; do sleep 600; done
COMMON="--model $M --chat --max-tokens 1400 --temp 0.8 --gens 50 --samples 6 --islands 2"
B="--memory schema"
BD="--memory schema --novelty behavior --repel-prompt"
E="--memory schema --agenda --novelty behavior --repel-prompt"
echo "SCALE2 START $(date)"
for s in 21 22 23; do
  for arm in B BD E; do
    out=$R/${arm}_s$s
    if [ -f "$out.log" ] && grep -q "DONE best" "$out.log"; then echo "skip $arm s$s"; continue; fi
    eval flags=\$$arm
    echo "run $arm s$s $(date)"
    caffeinate -is $PY scripts/frontier_search.py --problem beatavg $COMMON --seed $s $flags --out $out > $out.log 2>&1
  done
done
echo "SCALE2 DONE $(date)"
