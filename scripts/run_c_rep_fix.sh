#!/bin/sh
# C-rep fix (dated amendment, PLANO 2026-08-27): the final heldout2 generations of
# run_c_rep.sh failed on a type bug (--cycle "5f" is not an int) BEFORE generating
# anything, so heldout2 remains never-consulted. This script re-runs exactly the
# pre-registered final reads with integer cycle labels (lineages: cycle 6;
# shared pool: cycle 2), same seeds as registered. Waits for C-REP DONE first.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; NB=3; TOK=1200
until grep -q "C-REP DONE" runs/dream_c_rep/chain.log; do sleep 300; done
echo "C-REP-FIX START $(date)"
gen() { # root arm cycle adapter seed
  caffeinate -is $PY scripts/consolidate.py gen --arm $2 --cycle $3 --adapter $4 --variants heldout2 --n $NB --tokens $TOK --seed $5 --out $1/$2_c$3 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $1/$2_c$3 2>&1 | grep -v Warning | tail -1
}
for L in 1 2 3; do
  ROOT=runs/dream_c_rep/L$L; S=$((100 * L + 9))
  echo "== fix L$L final heldout2 $(date)"
  gen $ROOT base    6 none                          $S
  gen $ROOT attract 6 $ROOT/adapter_attract_c5      $S
  gen $ROOT random  6 $ROOT/adapter_random_c5       $S
done
ROOT=runs/dream_c_rep/pool1
echo "== fix pool1 final heldout2 $(date)"
gen $ROOT base 2 none               409
gen $ROOT top  2 $ROOT/adapter_top  409
gen $ROOT rand 2 $ROOT/adapter_rand 409
echo "C-REP-FIX DONE $(date)"
