#!/bin/sh
# Round-3 N2: matched-layout re-judging of pulseG20 and habit (30 premises) at
# +32/+160 after each burst end (pseudo-injections every 300, length 32); three
# judge workers, merge, single read. AWS_PROFILE=main-account sh scripts/r4_matched_judge.sh
set -u
cd "$(dirname "$0")/.." || exit 1
export AWS_PROFILE="${AWS_PROFILE:-main-account}"
PY=.venv/bin/python
run() { $PY scripts/dream_rejudge_surprise.py runs/r4 --protocol gen --k 5 --pseudo-every 300 --pseudo-len 32 --cells-regex '_(pulseG20|habit)$' "$@"; }
run --out-name rejudge_matched_a.json --skip-from rejudge_matched_b.json rejudge_matched_c.json > runs/r4_matched_a.log 2>&1 &
run --order reverse --out-name rejudge_matched_b.json --skip-from rejudge_matched_a.json rejudge_matched_c.json > runs/r4_matched_b.log 2>&1 &
run --order random --out-name rejudge_matched_c.json --skip-from rejudge_matched_a.json rejudge_matched_b.json > runs/r4_matched_c.log 2>&1 &
wait
$PY - <<'PYEOF'
import json
from pathlib import Path
R = Path("runs/r4"); seen = set(); out = []
for n in ("rejudge_matched_a.json", "rejudge_matched_b.json", "rejudge_matched_c.json"):
    f = R / n
    if f.exists():
        for r in json.loads(f.read_text()):
            k = (r["cell"], r["step"])
            if k not in seen:
                seen.add(k); out.append(r)
(R / "rejudge_matched.json").write_text(json.dumps(out, indent=2))
print("merged matched windows:", len(out), "cells:", len({r['cell'] for r in out}))
PYEOF
$PY scripts/analysis_r4.py > runs/r4_analysis.log 2>&1
grep -i "Traceback\|Error" runs/r4_analysis.log | head -2
sed -n '/## Matched-layout/,/## Effective/p' docs/APPENDIX_R4.md
echo "MATCHED-JUDGE DONE $(date)"
