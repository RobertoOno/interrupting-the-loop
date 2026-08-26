#!/bin/sh
# Frontier-operator scoping (pre-registered PLANO 2026-08-26 ~05:20):
# Claude Opus 5 proposer, arms A (bare) / B (schematic memory) / D (behavioural
# repulsion) on beatavg, maxmin16, heiltri11; 300 samples each, sequential.
# maxmin16_B reuses runs/frontier/record/maxmin16_claude_B (same config, seed 2).
# API-only: exempt from the one-model guard; safe alongside local runs.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/frontier/FP; mkdir -p $R
export AWS_PROFILE=main-account
COMMON="--api-model anthropic.claude-opus-5 --gens 25 --samples 6 --islands 2 --seed 2 --max-tokens 1400"
ARM_A=""
ARM_B="--memory schema"
ARM_D="--novelty behavior --repel-prompt"
echo "FRONTIER-OPS START $(date)"
for prob in beatavg maxmin16 heiltri11; do
  for arm in A B D; do
    [ "$prob" = "maxmin16" ] && [ "$arm" = "B" ] && continue  # reuse record arm
    out=$R/${prob}_${arm}
    if [ -f "$out.log" ] && grep -q "DONE best" "$out.log"; then
      echo "skip $prob $arm (done)"; continue
    fi
    eval flags=\$ARM_$arm
    echo "run $prob $arm $(date)"
    $PY scripts/frontier_search.py --problem $prob $COMMON $flags --out $out > $out.log 2>&1
  done
done
echo "FRONTIER-OPS DONE $(date)"
