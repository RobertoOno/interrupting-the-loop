#!/bin/sh
# Battery F extension 2 (pre-registered 2026-08-24): three NEW problems (maxmin16, heiltri11, factn180)
# x 5 arms x 2 replicates, same budget as battery F (10 gens x 2 islands x 6 = 120 samples per run).
# Resumable: finished runs are skipped. Ends with the pooled n=9 analysis.
# Waits for F-ext2, then runs the three missing 2^3 arms over all nine problems x 2 replicates.
while ! grep -q "F-EXT2 DONE" runs/frontier/F_ext2_chain.log 2>/dev/null; do sleep 300; done
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit; R=runs/frontier/F; mkdir -p $R
COMMON="--model $M --chat --max-tokens 1400 --temp 0.8 --gens 10 --samples 6 --islands 2"
arm_flags() { case $1 in
  BC) echo "--memory schema --agenda";;
  BD) echo "--memory schema --novelty behavior --repel-prompt";;
  CD) echo "--agenda --novelty behavior --repel-prompt";;
esac; }
echo "F-23 START $(date)"
for rep in "" "_s1"; do
  seed=0; [ "$rep" = "_s1" ] && seed=1
  for prob in circlepack26 ringload15 beatavg autocorr1 isofree64 sumdiff3 maxmin16 heiltri11 factn180; do
    for arm in BC BD CD; do
      out=$R/${prob}_${arm}${rep}
      if grep -q "DONE best" $out.log 2>/dev/null; then echo "skip $prob $arm$rep"; continue; fi
      echo "run $prob $arm$rep $(date)"
      $PY scripts/frontier_search.py --problem $prob $COMMON $(arm_flags $arm) --seed $seed --out $out > $out.log 2>&1
    done
  done
done
$PY scripts/frontier_analysis.py > $R/analysis_23.log 2>&1
echo "F-23 DONE $(date)"
