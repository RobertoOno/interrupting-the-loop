#!/bin/sh
# Sequential (never concurrent) frontier runs: baseline circle packing, then the cognitive-arms smoke.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
$PY scripts/frontier_search.py --problem circlepack26 --gens 30 --samples 8 --islands 2 --out runs/frontier/cp26_base_s0 > runs/frontier/cp26_base_s0.log 2>&1
echo "BASELINE DONE $(date)"
$PY scripts/frontier_search.py --problem ringload15 --gens 2 --samples 3 --islands 1 --memory schema --agenda --novelty behavior --repel-prompt --out runs/frontier/smoke_schema > runs/frontier/smoke_schema.log 2>&1
echo "SMOKE DONE $(date)"
echo "CHAIN DONE $(date)"
