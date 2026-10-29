#!/bin/sh
# A2 Mathlib pilot: automatic follow-up of one model's plan A, per the pre-registered rules (docs/A2_PILOTO_MATHLIB_V1.md).
# Waits for plan A's summary, reads it ONCE with scripts/analysis_a2_pilot.py, then: competence AND headroom -> preflight and
# run plan B on the same endpoint, re-read A+B, stop the pod; otherwise stop the pod at once. No decision is taken here that
# the pre-registration did not fix. Usage (inside screen + caffeinate):
#   sh scripts/a2m_after_a.sh <tag> <plan_a.json> <plan_b.json> <endpoint_file> <stop_file> <results_name>
set -u
cd "$(dirname "$0")/.." || exit 1
TAG=$1; PA=$2; PB=$3; EPF=$4; STOP=$5; NAME=$6
export PYTHONPATH=src CM_LAKE_SHARED="${CM_LAKE_SHARED:-$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1}"
PY=.venv/bin/python; LOG=runs/a2/after_a_${TAG}.log
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
IDA=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['plan_id'])" "$PA"); RA=runs/a2/$IDA
IDB=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['plan_id'])" "$PB"); RB=runs/a2/$IDB
say "waiting for $RA/summary_*.json"
while ! ls "$RA"/summary_*.json >/dev/null 2>&1; do sleep 60; done
mkdir -p docs/a2m_results
$PY scripts/analysis_a2_pilot.py --plan-a "$PA" --run-a "$RA" --out "docs/a2m_results/$NAME.md" --json "docs/a2m_results/$NAME.json" | tee -a "$LOG"
GATE=$($PY -c "import json; r=json.load(open('docs/a2m_results/$NAME.json'))['rules']; print('yes' if r['competence'] and r['headroom'] else 'no')")
say "plan A read: competence and headroom -> $GATE"
if [ "$GATE" = "yes" ]; then
  PRE=$($PY scripts/a1_ladder.py preflight --plan "$PB" --no-lean | $PY -c "import sys,json; print('ok' if json.load(sys.stdin)['ok'] else 'FAIL')")
  say "plan B preflight: $PRE"
  if [ "$PRE" = "ok" ]; then
    EP=$(cat "$EPF"); say "running plan B on $EP"
    CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan "$PB" --run-root runs/a2 >> "$LOG" 2>&1
    $PY scripts/analysis_a2_pilot.py --plan-a "$PA" --run-a "$RA" --plan-b "$PB" --run-b "$RB" --out "docs/a2m_results/$NAME.md" --json "docs/a2m_results/$NAME.json" | tee -a "$LOG"
  fi
fi
touch "$STOP"; say "stop file written: $STOP (pod removal requested)"
