#!/bin/sh
# Round-5 N2b: judge the text arm at +0 (window beginning at the end of each injected sentence), 30 premises,
# 4 windows per cell; three judge workers, merge, single read.  AWS_PROFILE=main-account sh scripts/r4_text0_judge.sh
set -u
cd "$(dirname "$0")/.." || exit 1
export AWS_PROFILE="${AWS_PROFILE:-main-account}"
PY=.venv/bin/python
run() { $PY scripts/dream_rejudge_surprise.py runs/r4 --protocol gen --k 5 --offsets 0 --margin 0 --max-windows-per-cell 8 --cells-regex '^[nog][0-9]_inter$' "$@"; }
run --out-name rejudge_text0_a.json --skip-from rejudge_text0_b.json rejudge_text0_c.json > runs/r4_text0_a.log 2>&1 &
run --order reverse --out-name rejudge_text0_b.json --skip-from rejudge_text0_a.json rejudge_text0_c.json > runs/r4_text0_b.log 2>&1 &
run --order random --out-name rejudge_text0_c.json --skip-from rejudge_text0_a.json rejudge_text0_b.json > runs/r4_text0_c.log 2>&1 &
wait
$PY - <<'PYEOF'
import json
from pathlib import Path
R = Path("runs/r4"); seen = set(); out = []
for n in ("rejudge_text0_a.json", "rejudge_text0_b.json", "rejudge_text0_c.json"):
    f = R / n
    if f.exists():
        for r in json.loads(f.read_text()):
            k = (r["cell"], r["step"])
            if k not in seen:
                seen.add(k); out.append(r)
(R / "rejudge_text0.json").write_text(json.dumps(out, indent=2))
print("merged +0 text windows:", len(out), "cells:", len({r['cell'] for r in out}), "mean k:", round(sum(r['k'] for r in out)/max(1,len(out)), 2))
PYEOF
echo "TEXT0-JUDGE DONE $(date)"
