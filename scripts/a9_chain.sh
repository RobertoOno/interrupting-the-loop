#!/bin/sh
# A8-c + A9 chain on ONE pod (scripts/a9_pod.sh). The Mac is the controller: Lean verification runs locally.
#  1. waits for runs/a9/vllm_endpoint (6 h), readiness of the three served models;
#  2. A8-c: completes the pending cells of a8_curm2_v1 (docs/A8_CURADORIA_ESTREITA_V1.md, E4) with the resume loop, then the SECOND
#     read, its diagnostics, its own evidence archive, commit and push (scripts/a8c_read.sh);
#  3. waits for runs/a9/data_ready (written only after the A9 pre-registration, data, worlds and plans are committed), asks the pod to
#     train a9-own3 (runs/a9/train_request), waits for runs/a9/vllm_endpoint2;
#  4. A9: scripts/a9_run.sh (arms with the resume loop, single read written before the data, archive, commit, push);
#  5. "a9 chain done", stop file, and the pod is removed directly (the guard and the pod script's trap are the backups).
#   screen -dmS a9chain caffeinate -i -s sh scripts/a9_chain.sh        (log runs/a9/chain.log)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a9; LOG=$RUNS/chain.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
. scripts/a9_lib.sh
finish() { say "a9 chain done"; touch $RUNS/vllm_stop; POD=$(cat $RUNS/pod_id 2>/dev/null); [ -n "$POD" ] && { runpodctl pod remove "$POD" >> "$LOG" 2>&1 && say "pod $POD removed by the chain" || say "pod removal FAILED (guard and trap will retry)"; }; say "pods now: $(runpodctl pod list 2>&1 | tr -d '\n' | cut -c1-160)"; exit "${1:-0}"; }
say "waiting for $RUNS/vllm_endpoint (up to 6 h)"; n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 720 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm_endpoint ] || { say "endpoint never appeared"; finish 3; }
EP=$(cat $RUNS/vllm_endpoint); say "endpoint $EP, pod $(cat $RUNS/pod_id)"
for m in qwen3.8-27b a2c4-own2 a2c4-curm2; do readiness "$EP" "$m" true; done
say "A8-c: completing the curated arm (E4)"
run_plan docs/a8_curm2_v1_plan.json runs/a8 "$EP" 10
sh scripts/a8c_read.sh >> "$LOG" 2>&1; say "A8-c read script ended (rc $?)"
say "waiting for $RUNS/data_ready (up to 4 h)"; n=0; until [ -f $RUNS/data_ready ] || [ $n -ge 480 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/data_ready ] || { say "A9 data never became ready: stopping without A9"; finish 0; }
say "data ready: $(cat $RUNS/data_ready | head -c 200); requesting training"; touch $RUNS/train_request
n=0; until [ -f $RUNS/vllm_endpoint2 ] || [ -f $RUNS/train_failed ] || [ $n -ge 360 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm_endpoint2 ] || { say "endpoint 2 never appeared (train_failed: $([ -f $RUNS/train_failed ] && echo yes || echo no))"; finish 4; }
EP2=$(cat $RUNS/vllm_endpoint2); say "endpoint 2 $EP2: $(curl -s -m 15 "$EP2/models" | head -c 300)"
for m in qwen3.8-27b a2c4-own2 a9-own3; do readiness "$EP2" "$m" true; done
readiness "$EP2" a9-own3 false
[ -f scripts/a9_run.sh ] || { say "scripts/a9_run.sh missing: stopping"; finish 5; }
A9_EP="$EP2" sh scripts/a9_run.sh; say "A9 run script ended (rc $?)"
finish 0
