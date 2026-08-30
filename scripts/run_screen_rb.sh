#!/bin/sh
# Screen RB (route blocking, operator 7; PLANO 2026-08-30 night). For each
# train variant, the route of the B-CONF control arm's best notebook is
# projected out (top-k trajectory PCs, premise coordinate anchored) during
# fresh generation. Verifier-read only. Calibration: k=1 surgical, k>=4 lobotomy.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/state_rb

gen() { out=$1; shift
  caffeinate -is $PY scripts/state_code.py --out $R/$out --op none --variants train \
      --n 3 --tokens 1500 --rng-seed 2 "$@" || echo "FAIL gen $out"
}

echo "SCREEN-RB START $(date)"
gen ctrl
gen rb1 --block-route-dir runs/routes/none_best --block-k 1 --anchor
gen rb2 --block-route-dir runs/routes/none_best --block-k 2 --anchor
for arm in ctrl rb1 rb2; do
  $PY scripts/consolidate.py verify --out $R/$arm
done
echo "SCREEN-RB DONE $(date)"
