#!/bin/sh
# Battery PULSE chain: cells -> judge (P1 gen protocol, k=5, Opus 5 via Bedrock).
# Analysis (scripts/analysis_pulse.py) runs ONCE by hand after PULSE DONE.
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python scripts/run_pulse.py || exit 1
echo "PULSE JUDGE START $(date)"
AWS_PROFILE=main-account caffeinate -is .venv/bin/python scripts/dream_rejudge_surprise.py \
    runs/state_pulse --protocol gen --k 5 || exit 1
echo "PULSE DONE $(date)"
