#!/bin/sh
# Battery M (schematic memory; return-to-conflict): generate, self-copy, judge (gen protocol,
# 2 workers), document judge, analysis. Started by launchd at 22:00 or by hand.
cd "$(dirname "$0")/.." || exit 1
mkdir -p runs/dream_m
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery m --out runs/dream_m
echo "M GENERATED $(date)"
.venv/bin/python scripts/selfcopy.py runs/dream_m
AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_m --k 5 --protocol gen > runs/dream_m/rejudge_gen.log 2>&1 &
sleep 30
AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_m --k 5 --protocol gen --order reverse --out-name rejudge_gen_w2.json --skip-from rejudge_gen.json > runs/dream_m/rejudge_gen_w2.log 2>&1 &
AWS_PROFILE=main-account .venv/bin/python scripts/judge_document.py runs/dream_m --k 3 --out runs/document_judgments_m.json > runs/judge_document_m.log 2>&1
wait
.venv/bin/python scripts/selfcopy.py runs/dream_m
.venv/bin/python scripts/analysis_gen.py > runs/dream_m/analysis.log 2>&1
echo "M DONE $(date)"
