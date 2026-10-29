#!/bin/sh
# MANUAL remedy, never called by the chain: when the clients of a running plan are deaf (the server idles while `a1_ladder.py run` waits on
# dead connections), kill that runner and set aside the in-flight session directories (no result.json) of the given run directory, so that the
# chain's resume loop starts the next round at once. A session set aside here was never observed and consumes no retry.
#   sh scripts/a9_unstick.sh runs/a9/a9_w5base_v1
cd "$(dirname "$0")/.." || exit 1
R=${1:?run directory}; TAG=$(date '+%H%M')
pkill -f "a1_ladder.py run" && echo "runner killed" || echo "no runner found"
sleep 3
for d in "$R"/W*_a[0-9] "$R"/S*_a[0-9]; do
  [ -d "$d" ] && [ ! -f "$d/result.json" ] && mv "$d" "$d.interrupted_$TAG" && echo "set aside $(basename "$d")"
done
