#!/bin/sh
# After overnight2: the judge-gated interruption battery on the main generator, then judging (gen protocol).
cd "$(dirname "$0")/.." || exit 1
while ! grep -q "OVERNIGHT2 DONE" runs/overnight2_nohup.log 2>/dev/null; do sleep 120; done
mkdir -p runs/dream_gate
AWS_PROFILE=main-account caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery gate --out runs/dream_gate
echo "GATE DONE $(date)"
AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_gate --k 5 --protocol gen > runs/dream_gate/rejudge_gen.log 2>&1 &
AWS_PROFILE=main-account .venv/bin/python scripts/judge_document.py runs/dream_gate --k 3 --out runs/document_judgments_gate.json > runs/judge_document_gate.log 2>&1 &
wait
echo "OVERNIGHT3 DONE $(date)"
