#!/bin/sh
# Battery H1-minimal chain: new cells -> judge resumes in runs/state_pulse.
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python scripts/run_h1.py || exit 1
echo "H1 JUDGE START $(date)"
AWS_PROFILE=main-account caffeinate -is .venv/bin/python scripts/dream_rejudge_surprise.py \
    runs/state_pulse --protocol gen --k 5 || exit 1
echo "H1 DONE $(date)"
