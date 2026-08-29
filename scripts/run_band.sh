#!/bin/sh
# Phase 5, day one — exploratory band sweep (declared in PLANO 2026-08-29).
# Translation operator on the 8B Base: v = mean-state(SEEDS[1]) - mean-state(premise),
# premise = SEEDS[0], continuous schedule, dose x layer x rng-seed grid + bare controls.
# Resumable: cells with run.json are skipped.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/state_band; mkdir -p $R
CONCEPT="She kept a notebook of things that had almost happened."

run() { # cell-name args...
  out=$R/$1; shift
  [ -f "$out/run.json" ] && { echo "skip $(basename $out)"; return; }
  caffeinate -is $PY scripts/state_inject.py --out $out --seed-index 0 \
      --max-tokens 1500 --temp 1.0 --top-p 0.95 "$@" || echo "FAIL $(basename $out)"
}

echo "BAND START $(date)"
for s in 0 1 2; do run bare_s$s --op none --rng-seed $s; done
for L in 6 18 30; do
  for a in 0.25 0.5 1 2 4 8; do
    for s in 0 1 2; do
      run tr_L${L}_a${a}_s$s --op translate --layer $L --alpha $a \
          --concept-a "$CONCEPT" --rng-seed $s
    done
  done
done
echo "BAND DONE $(date)"
