#!/bin/sh
# Waits for (a) the 8B post-trained test to finish and (b) the coder model download, then runs, strictly in sequence:
# circle-packing baseline with the coder proposer (30 gens), then the cognitive-arms smoke on ring loading.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit
while ! grep -q "DOWNLOAD DONE" runs/download_coder30b.log 2>/dev/null; do sleep 60; done
echo "CHAIN2 START $(date)"
$PY scripts/frontier_search.py --problem circlepack26 --model $M --gens 30 --samples 8 --islands 2 --out runs/frontier/cp26_coder_s0 > runs/frontier/cp26_coder_s0.log 2>&1
echo "CODER BASELINE DONE $(date)"
$PY scripts/frontier_search.py --problem ringload15 --model $M --gens 3 --samples 4 --islands 1 --memory schema --agenda --novelty behavior --repel-prompt --out runs/frontier/smoke_schema_coder > runs/frontier/smoke_schema_coder.log 2>&1
echo "CHAIN2 DONE $(date)"
