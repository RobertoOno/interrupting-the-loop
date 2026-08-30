#!/bin/sh
# Battery PULSE-2 chain: new guarded-pulse cells -> judge resumes in runs/state_pulse
# (only the new cells' windows are judged; PULSO-1 verdicts already on disk).
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python scripts/run_pulse2.py || exit 1
echo "PULSE2 JUDGE START $(date)"
AWS_PROFILE=main-account caffeinate -is .venv/bin/python scripts/dream_rejudge_surprise.py \
    runs/state_pulse --protocol gen --k 5 || exit 1
echo "PULSE2 DONE $(date)"
