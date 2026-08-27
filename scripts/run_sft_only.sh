#!/bin/sh
# SFT-only control (pre-registered PLANO 2026-08-27): the anchored-repulsion arm
# minus the DPO term — same pairs, same 80 iters, same lr, same alpha, same seeds
# and the same heldout/far generations as run_c_repel2.sh. Question: which half
# concentrates the policy at the classic level?
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; ROOT=runs/dream_c; PAIRS=$ROOT/pairs_repel_c5/pairs.jsonl
echo "SFT-ONLY START $(date)"
caffeinate -is $PY scripts/dpo_lora.py --pairs $PAIRS --adapter-path $ROOT/adapter_sft_only_c5 --iters 80 --pairs-per-step 2 --beta 0.1 --lr 1e-5 --alpha 1.0 --sft-only 2>&1 | grep -v Warning | grep -E "Iter|saved|rror"
caffeinate -is $PY scripts/consolidate.py gen --arm sft_only --cycle 5 --adapter $ROOT/adapter_sft_only_c5 --variants heldout --n 3 --tokens 1200 --seed 5 --out $ROOT/sft_only_c5 2>&1 | grep --line-buffered -v Warning
$PY scripts/consolidate.py verify --out $ROOT/sft_only_c5 2>&1 | grep -v Warning | tail -1
caffeinate -is $PY scripts/consolidate.py gen --arm far_sft_only --cycle 5 --adapter $ROOT/adapter_sft_only_c5 --variants far --n 3 --tokens 1200 --seed 9 --out $ROOT/far_sft_only 2>&1 | grep --line-buffered -v Warning
$PY scripts/consolidate.py verify --out $ROOT/far_sft_only 2>&1 | grep -v Warning | tail -1
echo "SFT-ONLY DONE $(date)"
