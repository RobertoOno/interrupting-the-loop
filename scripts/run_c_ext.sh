#!/bin/sh
# Battery C-ext: cycles 4-5 (resumes run_c.sh), then far transfer with the final adapters.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; ROOT=runs/dream_c
sh scripts/run_c.sh 5
echo "CEXT CYCLES DONE $(date)"
for spec in base:none attract:$ROOT/adapter_attract_c5 random:$ROOT/adapter_random_c5; do
  arm=${spec%%:*}; ad=${spec#*:}
  caffeinate -is $PY scripts/consolidate.py gen --arm far_$arm --cycle 5 --adapter $ad --variants far --n 3 --tokens 1200 --seed 9 --out $ROOT/far_$arm 2>&1 | grep --line-buffered -v Warning
  $PY scripts/consolidate.py verify --out $ROOT/far_$arm 2>&1 | grep -v Warning | tail -1
done
$PY scripts/consolidate_far_analysis.py > $ROOT/analysis_far.log 2>&1
echo "CEXT DONE $(date)"
