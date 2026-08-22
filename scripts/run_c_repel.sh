#!/bin/sh
# Chain B: C-repel. Waits for chain A (CEXT DONE), then DPO adapter on cycle-5 attract lineage pairs,
# generation on held-out (cycle-5 seeds) + far, analysis.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; ROOT=runs/dream_c
while ! grep -q "CEXT DONE" $ROOT/nohup_ext.log 2>/dev/null; do sleep 120; done
echo "REPEL START $(date)"
$PY scripts/consolidate.py select --out $ROOT/pool_attract_c5 --mode pairs --k 40 --sft $ROOT/pairs_repel_c5/pairs.jsonl 2>&1 | grep -v Warning | tail -1
N=$(wc -l < $ROOT/pairs_repel_c5/pairs.jsonl); IT=$(( (4 * N + 1) / 2 )); [ $IT -lt 40 ] && IT=40
caffeinate -is $PY scripts/dpo_lora.py --pairs $ROOT/pairs_repel_c5/pairs.jsonl --adapter-path $ROOT/adapter_repel_c5 --iters $IT --pairs-per-step 2 --beta 0.1 --lr 1e-5 2>&1 | grep -v Warning | grep -E "Iter|saved|rror"
caffeinate -is $PY scripts/consolidate.py gen --arm repel --cycle 5 --adapter $ROOT/adapter_repel_c5 --variants heldout --n 3 --tokens 1200 --seed 5 --out $ROOT/repel_c5 2>&1 | grep --line-buffered -v Warning
$PY scripts/consolidate.py verify --out $ROOT/repel_c5 2>&1 | grep -v Warning | tail -1
caffeinate -is $PY scripts/consolidate.py gen --arm far_repel --cycle 5 --adapter $ROOT/adapter_repel_c5 --variants far --n 3 --tokens 1200 --seed 9 --out $ROOT/far_repel 2>&1 | grep --line-buffered -v Warning
$PY scripts/consolidate.py verify --out $ROOT/far_repel 2>&1 | grep -v Warning | tail -1
$PY scripts/consolidate_repel_analysis.py > $ROOT/analysis_repel.log 2>&1
echo "REPEL DONE $(date)"
