#!/bin/sh
# R4 post-processing (pre-registered PLANO 2026-09-01): pull the pod cells,
# judge them with the P1 protocol (three workers), flag self-copies, run the
# manipulation check, and do the single read (analysis_r4.py).
#   AWS_PROFILE=main-account sh scripts/r4_judge.sh
set -u
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
export AWS_PROFILE="${AWS_PROFILE:-main-account}"
[ -d runs/pod/r4 ] || { echo "runs/pod/r4 missing (pod_battery rsync back first)"; exit 2; }
mkdir -p runs/r4 && rsync -a runs/pod/r4/ runs/r4/
echo "R4 cells: $(ls runs/r4 | grep -c '_')  $(date)"

J="$PY scripts/dream_rejudge_surprise.py runs/r4 --protocol gen --k 5"
$J --out-name rejudge_gen_a.json --skip-from rejudge_gen_b.json rejudge_gen_c.json > runs/r4_judge_a.log 2>&1 &
$J --order reverse --out-name rejudge_gen_b.json --skip-from rejudge_gen_a.json rejudge_gen_c.json > runs/r4_judge_b.log 2>&1 &
$J --order random --out-name rejudge_gen_c.json --skip-from rejudge_gen_a.json rejudge_gen_b.json > runs/r4_judge_c.log 2>&1 &
wait
$PY - <<'EOF'
import json
from pathlib import Path
R = Path("runs/r4"); seen = set(); out = []
for n in ("rejudge_gen_a.json", "rejudge_gen_b.json", "rejudge_gen_c.json"):
    f = R / n
    if f.exists():
        for r in json.loads(f.read_text()):
            k = (r["cell"], r["step"])
            if k not in seen:
                seen.add(k); out.append(r)
(R / "rejudge_gen.json").write_text(json.dumps(out, indent=2))
print("merged windows:", len(out), "cells:", len({r['cell'] for r in out}))
EOF
$PY scripts/selfcopy.py runs/r4 > runs/r4_selfcopy.log 2>&1
$PY scripts/manip_check.py runs/r4 > runs/manip_r4.log 2>&1
$PY scripts/analysis_r4.py > runs/r4_analysis.log 2>&1
tail -3 runs/r4_analysis.log
echo "R4-JUDGE DONE $(date)"
