#!/bin/sh
# Battery H2 chain: cells -> judge (P1 gen protocol, k=5, Opus 5 via Bedrock).
# Analysis (scripts/analysis_h2.py) is run ONCE by hand after H2 DONE.
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python scripts/run_h2.py || exit 1
echo "H2 JUDGE START $(date)"
AWS_PROFILE=main-account caffeinate -is .venv/bin/python scripts/dream_rejudge_surprise.py \
    runs/state_h2 --protocol gen --k 5 || exit 1
echo "H2 DONE $(date)"
