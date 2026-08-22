#!/bin/sh
# Battery N (tails): qd (SFT on quality-diversity elites) and repel_mode (anchored DPO: chosen = non-clone
# elites, rejected = best-fit clones), held-out (seed 5) + far (seed 9), tails analysis.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; ROOT=runs/dream_c; MODEL=~/models/mlx/Qwen3-8B-Base-8bit
echo "N START $(date)"
# qd: SFT on the elites (same recipe as attract)
cp $ROOT/sft_qd_c5/train.jsonl $ROOT/sft_qd_c5/valid.jsonl
N=$(wc -l < $ROOT/sft_qd_c5/train.jsonl); IT=$(( (4 * N + 1) / 2 )); [ $IT -lt 40 ] && IT=40
caffeinate -is $PY -m mlx_lm lora --model $MODEL --train --data $ROOT/sft_qd_c5 --mask-prompt --iters $IT --batch-size 2 \
   --learning-rate 1e-5 --num-layers 16 --max-seq-length 1024 --steps-per-report 20 --steps-per-eval 1000 --val-batches 1 \
   --adapter-path $ROOT/adapter_qd_c5 2>&1 | grep -E "Iter [0-9]+: Train|Saved|rror" | tail -2
for spec in heldout:5:qd_c5 far:9:far_qd; do
  w=${spec%%:*}; rest=${spec#*:}; sd=${rest%%:*}; od=${rest#*:}
  caffeinate -is $PY scripts/consolidate.py gen --arm qd --cycle 5 --adapter $ROOT/adapter_qd_c5 --variants $w --n 3 --tokens 1200 --seed $sd --out $ROOT/$od 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $ROOT/$od 2>&1 | grep -v Warning | tail -1
done
# repel_mode: anchored DPO against the best-fit clones
$PY scripts/consolidate.py select --out $ROOT/pool_attract_c5 --mode pairs_mode --k 40 --sft $ROOT/pairs_mode_c5/pairs.jsonl 2>&1 | grep -v Warning | tail -1
caffeinate -is $PY scripts/dpo_lora.py --pairs $ROOT/pairs_mode_c5/pairs.jsonl --adapter-path $ROOT/adapter_repel_mode_c5 --iters 80 --pairs-per-step 2 --beta 0.1 --lr 1e-5 --alpha 1.0 2>&1 | grep -v Warning | grep -E "Iter (40|80)|saved|rror"
for spec in heldout:5:repel_mode_c5 far:9:far_repel_mode; do
  w=${spec%%:*}; rest=${spec#*:}; sd=${rest%%:*}; od=${rest#*:}
  caffeinate -is $PY scripts/consolidate.py gen --arm repel_mode --cycle 5 --adapter $ROOT/adapter_repel_mode_c5 --variants $w --n 3 --tokens 1200 --seed $sd --out $ROOT/$od 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $ROOT/$od 2>&1 | grep -v Warning | tail -1
done
$PY scripts/consolidate_tails_analysis.py > $ROOT/analysis_n.log 2>&1
echo "N DONE $(date)"
