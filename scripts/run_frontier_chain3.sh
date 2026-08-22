#!/bin/sh
# Sequential: Coder (chat mode) baseline on circle packing, then the cognitive-arms smoke in chat mode.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; M=~/models/mlx/Qwen3-Coder-30B-A3B-Instruct-8bit
echo "CHAIN3 START $(date)"
$PY scripts/frontier_search.py --problem circlepack26 --model $M --chat --max-tokens 1400 --temp 0.8 --gens 20 --samples 8 --islands 2 --out runs/frontier/cp26_coderchat_s0 > runs/frontier/cp26_coderchat_s0.log 2>&1
echo "CODERCHAT BASELINE DONE $(date)"
$PY scripts/frontier_search.py --problem circlepack26 --model $M --chat --max-tokens 1400 --temp 0.8 --gens 3 --samples 4 --islands 1 --memory schema --agenda --novelty behavior --repel-prompt --out runs/frontier/smoke_cog_coderchat > runs/frontier/smoke_cog_coderchat.log 2>&1
echo "CHAIN3 DONE $(date)"
