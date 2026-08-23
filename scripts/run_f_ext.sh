#!/bin/sh
# Battery F: 6 problems x 5 arms, interleaved by problem, strictly sequential, resumable (skips finished runs).
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit; R=runs/frontier/F; mkdir -p $R
COMMON="--model $M --chat --max-tokens 1400 --temp 0.8 --gens 10 --samples 6 --islands 2"
arm_flags() { case $1 in
  A) echo "";;
  B) echo "--memory schema";;
  C) echo "--agenda";;
  D) echo "--novelty behavior --repel-prompt";;
  E) echo "--memory schema --agenda --novelty behavior --repel-prompt";;
esac; }
echo "F-EXT START $(date)"
for prob in circlepack26 ringload15 beatavg autocorr1 isofree64 sumdiff3; do
  for arm in A B C D E; do
    out=$R/${prob}_${arm}_s1
    if grep -q "DONE best" $out.log 2>/dev/null; then echo "skip $prob $arm"; continue; fi
    echo "run $prob $arm $(date)"
    $PY scripts/frontier_search.py --problem $prob $COMMON $(arm_flags $arm) --out $out > $out.log 2>&1
    $PY scripts/frontier_analysis.py > $R/analysis.log 2>&1
  done
done
echo "F-EXT DONE $(date)"
