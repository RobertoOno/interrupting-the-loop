#!/bin/sh
# Battery B-CONF chain (pre-registered PLANO 2026-08-30 ~17h30): 3 arms x
# (train + far) x 6 notebooks, then verifier scoring. Zero API. Resumable.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/state_bconf

gen() { out=$1; shift
  for vs in train far; do
    caffeinate -is $PY scripts/state_code.py --out $R/$out --variants $vs --n 6 \
        --tokens 1500 --rng-seed 1 "$@" || echo "FAIL gen $out $vs"
  done
}

echo "B-CONF START $(date)"
gen none       --op none
gen pulse_kick --op pulse --pulse-source kicks  --layer 18 --alpha 2.0 --anchor --keep-norm
gen pulse_ang  --op pulse --pulse-source angles --layer 18 --alpha 2.0 --anchor --keep-norm
for arm in none pulse_kick pulse_ang; do
  $PY scripts/consolidate.py verify --out $R/$arm
done
echo "B-CONF DONE $(date)"
