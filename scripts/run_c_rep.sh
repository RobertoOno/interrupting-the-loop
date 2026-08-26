#!/bin/sh
# Battery C-rep (pre-registered PLANO 2026-08-26): THREE independent consolidation
# lineages, five cycles fixed in advance, fresh generation/selection seeds per
# lineage, and a SECOND held-out set (heldout2) generated and scored ONCE, only
# after cycle 5 (never consulted during the run; no interim analysis).
# Then a shared-pool one-shot control: top-40 vs random-40 from the SAME pool.
# Hyperparameters copied verbatim from run_c.sh (the original lineage).
# Resumable: existing notebooks/adapters are skipped. Marker: C-REP DONE.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; MODEL=~/models/mlx/Qwen3-8B-Base-8bit
NB=3; TOK=1200; K=40

gen() { # root arm cycle adapter variants seed
  caffeinate -is $PY scripts/consolidate.py gen --arm $2 --cycle $3 --adapter $4 --variants $5 --n $NB --tokens $TOK --seed $6 --out $1/$2_c$3 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $1/$2_c$3 2>&1 | grep -v Warning | tail -1
}
pool() { # root arm cycle
  $PY - "$1" "$2" "$3" <<'PYEOF'
import json, sys, pathlib
root, arm, k = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
merged = {}
for d in [root / "base_c0"] + [root / f"{arm}_c{j}" for j in range(1, k)]:
    f = d / "candidates.json"
    if f.exists():
        merged.update(json.loads(f.read_text()))
out = root / f"pool_{arm}_c{k}"; out.mkdir(exist_ok=True)
(out / "candidates.json").write_text(json.dumps(merged))
print(f"pool {arm} c{k}: {len(merged)} candidates")
PYEOF
}
train() { # root arm cycle mode seed
  if [ -f $1/adapter_$2_c$3/adapters.safetensors ]; then echo "adapter $2 c$3 exists, skipping"; return; fi
  pool $1 $2 $3
  $PY scripts/consolidate.py select --out $1/pool_$2_c$3 --mode $4 --k $K --sft $1/sft_$2_c$3/train.jsonl --seed $5 2>&1 | tail -1
  cp $1/sft_$2_c$3/train.jsonl $1/sft_$2_c$3/valid.jsonl
  N=$(wc -l < $1/sft_$2_c$3/train.jsonl); IT=$(( (4 * N + 1) / 2 )); [ $IT -lt 40 ] && IT=40
  caffeinate -is $PY -m mlx_lm lora --model $MODEL --train --data $1/sft_$2_c$3 --mask-prompt --iters $IT --batch-size 2 \
     --learning-rate 1e-5 --num-layers 16 --max-seq-length 1024 --steps-per-report 20 --steps-per-eval 1000 --val-batches 1 \
     --adapter-path $1/adapter_$2_c$3 2>&1 | grep -E "Iter [0-9]+: Train|Saved|rror" | tail -3
}

echo "C-REP START $(date)"
for L in 1 2 3; do
  ROOT=runs/dream_c_rep/L$L; mkdir -p $ROOT
  GS=$((100 * L))                     # generation seed base for this lineage
  echo "== lineage $L (gen seeds $GS+cycle, select seeds $((10 * L))+cycle) $(date)"
  gen $ROOT base 0 none train $GS
  c=1
  while [ $c -le 5 ]; do
    echo "== L$L cycle $c $(date)"
    train $ROOT attract $c finds  $((10 * L + c))
    train $ROOT random  $c random $((10 * L + c))
    gen $ROOT attract $c $ROOT/adapter_attract_c$c train $((GS + c))
    gen $ROOT random  $c $ROOT/adapter_random_c$c  train $((GS + c))
    gen $ROOT base    $c none                      train $((GS + c))
    c=$((c + 1))
  done
  echo "== L$L FINAL heldout2 (single read) $(date)"
  gen $ROOT base    5f none                      heldout2 $((GS + 9))
  gen $ROOT attract 5f $ROOT/adapter_attract_c5  heldout2 $((GS + 9))
  gen $ROOT random  5f $ROOT/adapter_random_c5   heldout2 $((GS + 9))
  echo "LINEAGE $L DONE $(date)"
done

echo "== shared-pool one-shot control $(date)"
ROOT=runs/dream_c_rep/pool1; mkdir -p $ROOT
gen $ROOT base 0 none train 400
pool $ROOT base 1
$PY scripts/consolidate.py select --out $ROOT/pool_base_c1 --mode finds  --k $K --sft $ROOT/sft_top_c1/train.jsonl  --seed 41 2>&1 | tail -1
$PY scripts/consolidate.py select --out $ROOT/pool_base_c1 --mode random --k $K --sft $ROOT/sft_rand_c1/train.jsonl --seed 42 2>&1 | tail -1
for a in top rand; do
  cp $ROOT/sft_${a}_c1/train.jsonl $ROOT/sft_${a}_c1/valid.jsonl
  N=$(wc -l < $ROOT/sft_${a}_c1/train.jsonl); IT=$(( (4 * N + 1) / 2 )); [ $IT -lt 40 ] && IT=40
  [ -f $ROOT/adapter_${a}/adapters.safetensors ] || caffeinate -is $PY -m mlx_lm lora --model $MODEL --train --data $ROOT/sft_${a}_c1 --mask-prompt --iters $IT --batch-size 2 \
     --learning-rate 1e-5 --num-layers 16 --max-seq-length 1024 --steps-per-report 20 --steps-per-eval 1000 --val-batches 1 \
     --adapter-path $ROOT/adapter_${a} 2>&1 | grep -E "Iter [0-9]+: Train|Saved|rror" | tail -3
done
gen $ROOT top  1f $ROOT/adapter_top  heldout2 409
gen $ROOT rand 1f $ROOT/adapter_rand heldout2 409
gen $ROOT base 1f none               heldout2 409
echo "C-REP DONE $(date)"
