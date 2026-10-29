#!/bin/sh
# ONE-OFF helper of the 19/09 run; scripts/a9_pod.sh was fixed on 20/09 and no longer needs it.
# Operational fix for scripts/a9_pod.sh (found 19/09 08:14, 12 min after "fase 1: servindo"): its serve() guard `pgrep -f '[v]llm serve'`
# matches the remote shell's OWN command line, which contains the literal "vllm serve ..." text of the command it is about to run, so the
# server was never started. The pod script was already running and a running shell script must not be edited; phase 1 was started by hand
# with /workspace/a9/start_vllm.sh (same flags as A8), and this helper does the same for phase 3: it waits for the pod script's
# "fase 3: servindo" line and starts the server with the a9-own3 adapter added. It touches nothing else.
#   screen -dmS a9fix caffeinate -i -s sh scripts/a9_serve_fix.sh        (log runs/a9/serve_fix.log)
cd "$(dirname "$0")/.." || exit 1
RUNS=runs/a9; LOG=$RUNS/serve_fix.log
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
say "waiting for phase 3"
until grep -q "fase 3: servindo" $RUNS/pod.log 2>/dev/null || [ -f $RUNS/vllm_stop ] || [ -f $RUNS/train_failed ] || grep -q "a9 chain done" $RUNS/chain.log 2>/dev/null; do sleep 15; done
grep -q "fase 3: servindo" $RUNS/pod.log 2>/dev/null || { say "no phase 3 (stop, failure or end): nothing to do"; exit 0; }
SSHC=$(cat $RUNS/ssh_cmd); n=0
until sh -c "$SSHC \"cd /workspace/a9 && (test -f phase3.started || (touch phase3.started; nohup sh start_vllm.sh phase3 a9-own3=/workspace/a9/adapters/a9-own3 > /dev/null 2>&1 &)); sleep 20; test -s /workspace/a9/vllm_serve_phase3.log\"" >> "$LOG" 2>&1; do
  n=$((n+1)); [ $n -ge 12 ] && { say "could not start the phase 3 server"; exit 1; }; say "start attempt $n failed; retrying"; sleep 20
done
say "phase 3 server started on the pod"
