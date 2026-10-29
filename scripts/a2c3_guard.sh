#!/bin/sh
# A2 sem curador — independent guard for the pod in runs/a2c3/pod_id: removes it when the marker appears in the chain log or at the
# hard deadline (local time), whichever comes first. Belt and braces over the pod script's own trap and cap.
#   A2C3_MARKER="production done" A2C3_LOG=runs/a2c3/prod.log A2C3_DEADLINE="2026-09-15 10:30" screen -dmS a2c3guard caffeinate -i -s sh scripts/a2c3_guard.sh
cd "$(dirname "$0")/.." || exit 1
RUNS="${A2C3_RUNS:-runs/a2c3}"; PODF="${A2C3_POD_FILE:-$RUNS/pod_id}"; MARKER="${A2C3_MARKER:-production done}"; CLOG="${A2C3_LOG:-$RUNS/prod.log}"; DEADLINE=$(date -j -f '%Y-%m-%d %H:%M' "${A2C3_DEADLINE:-2026-09-15 10:30}" +%s)
n=0; until [ -f "$PODF" ] || [ $n -ge 60 ]; do sleep 30; n=$((n+1)); done
POD=$(cat "$PODF" 2>/dev/null); [ -n "$POD" ] || { echo "$(date '+%H:%M:%S') no pod id; guard exits" >> "$RUNS/guard.log"; exit 0; }
echo "$(date '+%H:%M:%S') guard armed for $POD: marker '$MARKER' in $CLOG or deadline ${A2C3_DEADLINE:-2026-09-15 10:30}" >> "$RUNS/guard.log"
CHAIN="${A2C3_CHAIN_PATTERN:-}"   # 19/09: if set, the pod is removed as soon as no process matches this pattern (pod alive, controller dead, cost money twice)
while :; do
  if [ -n "$CHAIN" ] && ! pgrep -f "$CHAIN" >/dev/null 2>&1; then echo "$(date '+%H:%M:%S') chain '$CHAIN' not running: removing $POD" >> "$RUNS/guard.log"; break; fi
  if grep -q "$MARKER" "$CLOG" 2>/dev/null; then echo "$(date '+%H:%M:%S') marker seen: giving the pod script 10 min, then removing $POD" >> "$RUNS/guard.log"; sleep 600; break; fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then echo "$(date '+%H:%M:%S') hard deadline: removing $POD" >> "$RUNS/guard.log"; break; fi
  sleep 60
done
runpodctl pod remove "$POD" >> "$RUNS/guard.log" 2>&1; runpodctl pod list >> "$RUNS/guard.log" 2>&1; echo "$(date '+%H:%M:%S') done" >> "$RUNS/guard.log"
