#!/bin/sh
# Detached driver for the P3 production/transfer diagnostic: survives the Claude session closing.
# Waits for the first (already running) proposer cell to finish, then runs every remaining cell in order
# (proposers, then recipients), single read at the end. Keeps the Mac awake on AC power (caffeinate -s -i).
#   nohup caffeinate -s -i sh scripts/p3_transfer_detached.sh > runs/p3/transfer_v1_detached.log 2>&1 &
set -u
cd "$(dirname "$0")/.." || exit 1
PY=/Users/robertoonofilho/wrk/creative-machine/.venv/bin/python
export PYTHONPATH=src
FIRST=runs/p3/transfer_v1/T26_40A8FE16CB8C/result.json
i=0
while [ ! -f "$FIRST" ]; do i=$((i+1)); [ $i -ge 90 ] && { echo "first cell never finished (15 min); proceeding anyway $(date)"; break; }; sleep 10; done
echo "first cell status: $(test -f "$FIRST" && $PY -c "import json; r=json.load(open('$FIRST')); res=r.get('result') or {}; print(res.get('status'), res.get('production_outcome'), 'bridge' if res.get('selected_bridge') else 'no-bridge', 'visible', res.get('visible_solved'), 'cost', res.get('cost_usd_at_configured_rates'), r.get('launcher_error'))") $(date)"
$PY scripts/p3_transfer_run.py --phase proposers --workers 2 ${RETRY:-}
$PY scripts/p3_transfer_run.py --phase recipients --workers 2 ${RETRY:-}
echo "SINGLE READ $(date)"
$PY scripts/analysis_p3_transfer.py
echo "CM-DONE p3 transfer $(date)"
