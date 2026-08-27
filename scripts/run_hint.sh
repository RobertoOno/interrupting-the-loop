#!/bin/sh
# Family-hint battery (pre-registered PLANO 2026-08-27; the paper-3 decisive test).
# beatavg, local 30B coder chat, BD flags (parsimonious recipe), 120 samples,
# 5 conditions x 3 seeds. Waits for SFT-ONLY DONE. Marker: HINT DONE.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit; R=runs/frontier/hint; mkdir -p $R
until grep -q "SFT-ONLY DONE" runs/dream_c/sft_only_chain.log; do sleep 300; done
COMMON="--model $M --chat --max-tokens 1400 --temp 0.8 --gens 10 --samples 6 --islands 2 --memory schema --novelty behavior --repel-prompt"
GEN="Consider trying a fundamentally different representation or family of constructions from those tried so far, rather than refining the current one."
STR="One known family of strong constructions places an atom at zero holding a substantial fraction of the mass and spreads the rest over atoms accumulating geometrically toward the maximum, at positions like (1 - r**i) * (L - 1); single-scale sets of a few atoms are believed suboptimal."
echo "HINT START $(date)"
for s in 11 12 13; do
  for cond in nohint generic structural famseed oracle; do
    out=$R/${cond}_s$s
    if [ -f "$out.log" ] && grep -q "DONE best" "$out.log"; then echo "skip $cond s$s"; continue; fi
    echo "run $cond s$s $(date)"
    case $cond in
      nohint)     EXTRA="" ;;
      generic)    EXTRA="--hint \"$GEN\"" ;;
      structural) EXTRA="--hint \"$STR\"" ;;
      famseed)    EXTRA="--seed-file docs/hint/seed_family_poor.py" ;;
      oracle)     EXTRA="--seed-file docs/hint/seed_family_oracle.py" ;;
    esac
    eval caffeinate -is $PY scripts/frontier_search.py --problem beatavg $COMMON --seed $s $EXTRA --out $out > $out.log 2>&1
  done
done
echo "HINT DONE $(date)"
