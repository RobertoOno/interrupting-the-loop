#!/bin/sh
# Battery L — the closed loop (pre-registered PLANO 2026-08-26; queued after the C lineages).
# Session 1: bare search builds a candidate pool. Consolidation: LoRA on the pool's best
# (cons) and on a random subset (rand). Session 2: 2x2 consolidation x repulsion + the
# random-adapter control, fresh seed. Primary: does repulsion recover the tail that
# consolidation costs? Resumable: finished runs, adapters and pools are skipped.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/frontier/L; mkdir -p $R
PROBS="circlepack26 ringload15 beatavg autocorr1 sumdiff3 maxmin16"
K=40

# --- technical gate: can mlx_lm train a LoRA on the 30B MoE within memory? ---
MOE=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit
SMALL=~/models/mlx/Qwen3-8B-8bit
if [ -f $R/model.chosen ]; then
  read MODEL SAMPLES GENS < $R/model.chosen
else
  mkdir -p $R/probe
  printf '{"prompt": "hello", "completion": "world"}\n%.0s' 1 2 3 4 > $R/probe/train.jsonl
  cp $R/probe/train.jsonl $R/probe/valid.jsonl
  echo "PROBE lora-on-MoE $(date)"
  if $PY -m mlx_lm lora --model $MOE --train --data $R/probe --mask-prompt --iters 2 \
       --batch-size 1 --num-layers 4 --adapter-path $R/probe/adapter > $R/probe.log 2>&1; then
    echo "$MOE 120 10" > $R/model.chosen; echo "PROBE PASS: 30B MoE proposer, 120 samples"
  else
    echo "$SMALL 60 10" > $R/model.chosen; echo "PROBE FAIL: falling back to 8B, 60 samples (see $R/probe.log)"
  fi
  read MODEL SAMPLES GENS < $R/model.chosen
fi
SPL=$(( SAMPLES / (GENS * 2) ))
COMMON="--model $MODEL --chat --max-tokens 1400 --temp 0.8 --gens $GENS --samples $SPL --islands 2"
echo "BATTERY-L START $(date) model=$MODEL samples=$SAMPLES"

run() { # out-dir extra-flags...
  out=$1; shift
  if [ -f "$out.log" ] && grep -q "DONE best" "$out.log"; then echo "skip $(basename $out)"; return; fi
  echo "run $(basename $out) $(date)"
  caffeinate -is $PY scripts/frontier_search.py $COMMON "$@" --out $out > $out.log 2>&1
}

train() { # problem mode sft-dir adapter-dir pool-dir
  [ -f "$4/adapters.safetensors" ] && { echo "skip adapter $(basename $4)"; return; }
  $PY scripts/closed_loop.py select --run $5 --problem $1 --mode $2 --k $K --sft $3 \
      --chat-model $MODEL --seed 7 || return 1
  cp $3/train.jsonl $3/valid.jsonl
  N=$(wc -l < $3/train.jsonl); IT=$(( (4 * N + 1) / 2 )); [ $IT -lt 40 ] && IT=40
  echo "train $(basename $4) ($N programs, $IT iters) $(date)"
  caffeinate -is $PY -m mlx_lm lora --model $MODEL --train --data $3 --mask-prompt --iters $IT \
      --batch-size 2 --adapter-path $4 >> $4.log 2>&1
}

for p in $PROBS; do
  run $R/${p}_pool --problem $p --seed 0                                    # session 1: bare
  train $p finds  $R/sft_cons_$p $R/adapter_cons_$p $R/${p}_pool
  train $p random $R/sft_rand_$p $R/adapter_rand_$p $R/${p}_pool
done
echo "L POOLS+ADAPTERS DONE $(date)"

for p in $PROBS; do                                                        # session 2: fresh seed
  run $R/${p}_base   --problem $p --seed 3
  run $R/${p}_baseD  --problem $p --seed 3 --novelty behavior --repel-prompt
  run $R/${p}_cons   --problem $p --seed 3 --adapter $R/adapter_cons_$p
  run $R/${p}_consD  --problem $p --seed 3 --adapter $R/adapter_cons_$p --novelty behavior --repel-prompt
  run $R/${p}_rand   --problem $p --seed 3 --adapter $R/adapter_rand_$p
done
echo "BATTERY-L DONE $(date)"
