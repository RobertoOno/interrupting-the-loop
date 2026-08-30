#!/bin/sh
# Screen B-1 (PLANO 2026-08-30 afternoon): state operators inside verified
# code generation. Verifier-read only, no judges. Resumable per notebook.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/state_code

gen() { out=$1; shift
  caffeinate -is $PY scripts/state_code.py --out $R/$out --variants train --n 3 \
      --tokens 1500 --rng-seed 0 "$@" || echo "FAIL gen $out"
}

echo "SCREEN-B1 START $(date)"
gen none       --op none
gen pulse_ang  --op pulse --pulse-source angles --layer 18 --alpha 2.0 --anchor --keep-norm
gen pulse_kick --op pulse --pulse-source kicks  --layer 18 --alpha 2.0 --anchor --keep-norm
gen repel      --op repel --layer 18 --alpha 1.5
for arm in none pulse_ang pulse_kick repel; do
  $PY scripts/consolidate.py verify --out $R/$arm
done
echo "SCREEN-B1 DONE $(date)"
