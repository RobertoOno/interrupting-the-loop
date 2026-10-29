#!/bin/sh
# A2 Mathlib pilot, amendment E6: run one model's plan B (descriptive) once the endpoint is up, re-read A+B, stop the pod.
#   sh scripts/a2m_run_b.sh <plan_a.json> <plan_b.json> <endpoint_file> <stop_file> <results_name>
set -u
cd "$(dirname "$0")/.." || exit 1
PA=$1; PB=$2; EPF=$3; STOP=$4; NAME=$5
export PYTHONPATH=src CM_LAKE_SHARED="${CM_LAKE_SHARED:-$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1}"
PY=.venv/bin/python; LOG=runs/a2/run_b_${NAME}.log
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
IDA=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['plan_id'])" "$PA"); RA=runs/a2/$IDA
IDB=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['plan_id'])" "$PB"); RB=runs/a2/$IDB
say "waiting for endpoint file $EPF"
n=0; while [ ! -f "$EPF" ] && [ $n -lt 240 ]; do sleep 15; n=$((n+1)); done
[ -f "$EPF" ] || { say "endpoint never appeared; giving up"; exit 2; }
EP=$(cat "$EPF")
PRE=$($PY scripts/a1_ladder.py preflight --plan "$PB" --no-lean | $PY -c "import sys,json; print('ok' if json.load(sys.stdin)['ok'] else 'FAIL')")
say "plan B preflight: $PRE"
if [ "$PRE" = "ok" ]; then
  say "running plan B on $EP"
  CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan "$PB" --run-root runs/a2 >> "$LOG" 2>&1
  $PY scripts/analysis_a2_pilot.py --plan-a "$PA" --run-a "$RA" --plan-b "$PB" --run-b "$RB" --out "docs/a2m_results/$NAME.md" --json "docs/a2m_results/$NAME.json" | tee -a "$LOG"
fi
touch "$STOP"; say "stop file written: $STOP"
