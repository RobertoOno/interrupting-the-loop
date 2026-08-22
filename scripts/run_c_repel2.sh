#!/bin/sh
# Anchored repulsion (RPO-style DPO + SFT anchor) and early-stopped DPO, on the cycle-5 pairs.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; ROOT=runs/dream_c; PAIRS=$ROOT/pairs_repel_c5/pairs.jsonl
echo "REPEL2 START $(date)"
run_arm() { # name iters alpha
  caffeinate -is $PY scripts/dpo_lora.py --pairs $PAIRS --adapter-path $ROOT/adapter_$1_c5 --iters $2 --pairs-per-step 2 --beta 0.1 --lr 1e-5 --alpha $3 2>&1 | grep -v Warning | grep -E "Iter|saved|rror"
  caffeinate -is $PY scripts/consolidate.py gen --arm $1 --cycle 5 --adapter $ROOT/adapter_$1_c5 --variants heldout --n 3 --tokens 1200 --seed 5 --out $ROOT/$1_c5 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $ROOT/$1_c5 2>&1 | grep -v Warning | tail -1
  caffeinate -is $PY scripts/consolidate.py gen --arm far_$1 --cycle 5 --adapter $ROOT/adapter_$1_c5 --variants far --n 3 --tokens 1200 --seed 9 --out $ROOT/far_$1 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $ROOT/far_$1 2>&1 | grep -v Warning | tail -1
}
run_arm repel_anch 80 1.0
run_arm repel_early 20 0.0
$PY scripts/consolidate_repel_analysis.py > $ROOT/analysis_repel2.log 2>&1
echo "REPEL2 DONE $(date)"
