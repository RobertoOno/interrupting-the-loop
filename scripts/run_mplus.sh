#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
mkdir -p runs/dream_mplus
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery mplus --out runs/dream_mplus
echo "MPLUS GENERATED $(date)"
.venv/bin/python scripts/selfcopy.py runs/dream_mplus
AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_mplus --k 5 --protocol gen > runs/dream_mplus/rejudge_gen.log 2>&1 &
sleep 20
AWS_PROFILE=main-account .venv/bin/python scripts/judge_document.py runs/dream_mplus --k 3 --out runs/document_judgments_mplus.json > runs/judge_document_mplus.log 2>&1
wait
.venv/bin/python scripts/selfcopy.py runs/dream_mplus
.venv/bin/python scripts/analysis_gen.py > runs/dream_mplus/analysis.log 2>&1
echo "MPLUS DONE $(date)"
