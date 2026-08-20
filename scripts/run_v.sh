#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
for arm in fb300 fbagenda; do
  for r in 0 1; do
    caffeinate -is .venv/bin/python scripts/problem_loop.py --arm $arm --rng-seed $r --out runs/dream_v/${arm}_r${r}
  done
done
echo "V GENERATED $(date)"
.venv/bin/python scripts/problem_loop_analysis.py > runs/dream_v/analysis.log 2>&1
echo "V DONE $(date)"
