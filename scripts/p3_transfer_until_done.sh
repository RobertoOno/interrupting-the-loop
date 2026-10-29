#!/bin/sh
# Re-admits infrastructure failures (provider 529 overload, network drops) until every one of the 26 cells has a
# genuine outcome or a documented skip. Each attempt runs the detached driver in retry mode; a 529 before any
# token costs nothing. Spacing 10 min, at most 12 attempts (2 h). Appends to the same log the monitor tails.
set -u
cd "$(dirname "$0")/.." || exit 1
PY=/Users/robertoonofilho/wrk/creative-machine/.venv/bin/python
pending() {  # cells still lacking a genuine outcome: infrastructure failure, launcher error, or missing result
  $PY - <<'PYEOF'
import json, pathlib
bp = json.load(open("docs/p3/transfer_design_draft_v1.json")); n = 0
for c in bp["cells"]:
    p = pathlib.Path("runs/p3/transfer_v1") / c["cell_id"] / "result.json"
    if not p.exists(): n += 1; continue
    r = json.loads(p.read_text()); res = r.get("result") or {}
    if res.get("infrastructure_failure") or r.get("launcher_error"): n += 1
print(n)
PYEOF
}
i=0
while :; do
  i=$((i+1)); left=$(pending)
  echo "until-done attempt $i: $left cell(s) pending $(date)"
  [ "$left" -eq 0 ] && { echo "ALL CELLS SETTLED $(date)"; break; }
  [ $i -gt 12 ] && { echo "GIVING UP after 12 attempts; $left pending $(date)"; break; }
  RETRY=--retry-infrastructure sh scripts/p3_transfer_detached.sh
  sleep 600
done
echo "UNTIL-DONE FINISHED $(date)"
