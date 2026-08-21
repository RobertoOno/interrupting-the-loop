#!/bin/sh
# Battery C: consolidation by LoRA, 3 cycles. Cycle 0 = shared base generation.
# Arms from cycle 1: attract (LoRA on finds ∪ top-40 by train excess, from the arm's own lineage),
# random (LoRA on a same-size random sample of valid candidates), base (no adapter, held-out only).
# Usage: sh scripts/run_c.sh [cycles]   (resumable: gen skips existing notebooks)
cd "$(dirname "$0")/.." || exit 1
CY=${1:-3}; ROOT=runs/dream_c; PY=.venv/bin/python; MODEL=~/models/mlx/Qwen3-8B-Base-8bit
NB=3; TOK=1200; K=40
mkdir -p $ROOT
gen() { # arm cycle adapter variants seed
  caffeinate -is $PY scripts/consolidate.py gen --arm $1 --cycle $2 --adapter $3 --variants $4 --n $NB --tokens $TOK --seed $5 --out $ROOT/$1_c$2 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $ROOT/$1_c$2 2>&1 | grep -v Warning | tail -1
}
pool() { # arm cycle -> merged candidates of the lineage into $ROOT/pool_<arm>_c<cycle>/candidates.json
  $PY - "$ROOT" "$1" "$2" <<'PYEOF'
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
train() { # arm cycle mode
  if [ -f $ROOT/adapter_$1_c$2/adapters.safetensors ]; then echo "adapter $1 c$2 exists, skipping training"; return; fi
  pool $1 $2
  $PY scripts/consolidate.py select --out $ROOT/pool_$1_c$2 --mode $3 --k $K --sft $ROOT/sft_$1_c$2/train.jsonl --seed $2 2>&1 | tail -1
  cp $ROOT/sft_$1_c$2/train.jsonl $ROOT/sft_$1_c$2/valid.jsonl
  N=$(wc -l < $ROOT/sft_$1_c$2/train.jsonl); IT=$(( (4 * N + 1) / 2 )); [ $IT -lt 40 ] && IT=40
  caffeinate -is $PY -m mlx_lm lora --model $MODEL --train --data $ROOT/sft_$1_c$2 --mask-prompt --iters $IT --batch-size 2 \
     --learning-rate 1e-5 --num-layers 16 --max-seq-length 1024 --steps-per-report 20 --steps-per-eval 1000 --val-batches 1 \
     --adapter-path $ROOT/adapter_$1_c$2 2>&1 | grep -E "Iter [0-9]+: Train|Saved|rror" | tail -3
}
echo "C START $(date)"
gen base 0 none train 0; gen base 0 none heldout 0   # resumable: existing notebooks are skipped
c=1
while [ $c -le $CY ]; do
  echo "== cycle $c $(date)"
  train attract $c finds
  train random $c random
  gen attract $c $ROOT/adapter_attract_c$c train $c
  gen attract $c $ROOT/adapter_attract_c$c heldout $c
  gen random $c $ROOT/adapter_random_c$c train $c
  gen random $c $ROOT/adapter_random_c$c heldout $c
  gen base $c none heldout $c
  $PY scripts/consolidate_analysis.py > $ROOT/analysis_c$c.log 2>&1
  c=$((c + 1))
done
echo "C DONE $(date)"
