#!/bin/sh
# A8-c / A9 — READ-ONLY watcher. Exits (which wakes the assistant) on the first milestone, on the first anomaly, or after MAX minutes
# (heartbeat), printing a status block. It never touches the pod, the chain or the data.
#   sh scripts/a9_watch.sh [max minutes, default 30]
cd "$(dirname "$0")/.." || exit 1
RUNS=runs/a9; MAX=${1:-30}; ST=$RUNS/watch_state; T0=$(date +%s); BAD='WARNING|FAILED|falhou|never appeared|giving up|not answering|Traceback|ausente|não subiu|não respondeu'
flags() { f=""; for x in vllm_endpoint data_ready train_request train_failed vllm_endpoint2 vllm_stop; do [ -f $RUNS/$x ] && f="$f $x"; done
  grep -q "A8-c read script ended" $RUNS/chain.log 2>/dev/null && f="$f a8c_read"; grep -q "a9 chain done" $RUNS/chain.log 2>/dev/null && f="$f chain_done"; echo "$f"; }
count() { find runs/a8/a8_curm2_v1 runs/a9 -name result.json -not -path '*failed*' -not -path '*interrupted*' 2>/dev/null | wc -l | tr -d ' '; }
lines() { cat $RUNS/chain.log $RUNS/pod.log 2>/dev/null | grep -cE "$BAD"; }
infra() { grep -c ": infrastructure_failure " $RUNS/chain.log 2>/dev/null; }
srvrun() { curl -s -m 15 "${1%/v1}/metrics" 2>/dev/null | awk '/^vllm:num_requests_(running|waiting)/ {s+=$NF; k=1} END {if (k) print s+0; else print -1}'; }
status() { echo "== $(date '+%Y-%m-%d %H:%M:%S') $1"; echo "flags:$(flags) | results: $(count) | bad lines: $(lines) | transport failures so far: $(infra)"
  echo "-- chain.log"; tail -4 $RUNS/chain.log 2>/dev/null | cut -c1-220; echo "-- pod.log"; tail -3 $RUNS/pod.log 2>/dev/null | cut -c1-220
  echo "-- guard"; tail -1 $RUNS/guard.log 2>/dev/null; echo "-- runpod: $(runpodctl user 2>/dev/null | grep -E 'clientBalance|currentSpendPerHr' | tr -d ' \n')"; }
[ -f $ST ] || { echo "$(flags)|$(lines)" > $ST; }
F0=$(cut -d'|' -f1 $ST); B0=$(cut -d'|' -f2 $ST); EPFAIL=0; LASTN=$(count); LASTT=$(date +%s); I0=$(infra); IDLE=0
while :; do
  F=$(flags); B=$(lines); N=$(count); NOW=$(date +%s)
  [ "$N" != "$LASTN" ] && { LASTN=$N; LASTT=$NOW; }
  DONE=0; echo "$F" | grep -q chain_done && DONE=1
  if [ "$F" != "$F0" ]; then echo "$F|$B" > $ST; status "MILESTONE: flags changed from [$F0] to [$F]"; exit 0; fi
  if [ "$B" != "$B0" ]; then echo "$F|$B" > $ST; status "ANOMALY: new warning/failure lines"; cat $RUNS/chain.log $RUNS/pod.log | grep -E "$BAD" | tail -5 | cut -c1-240; exit 0; fi
  [ $(( $(infra) - I0 )) -ge 6 ] && { status "ANOMALY: 6 or more transport failures in this watch window"; exit 0; }
  if [ $DONE -eq 0 ]; then
    pgrep -f "scripts/a9_chain.sh" >/dev/null || { status "ANOMALY: chain process not running"; exit 0; }
    pgrep -f "scripts/a9_pod.sh" >/dev/null || { status "ANOMALY: pod script not running"; exit 0; }
    pgrep -f "scripts/a2c3_guard.sh" >/dev/null || { status "ANOMALY: guard not running"; exit 0; }
    EPF=""; [ -f $RUNS/vllm_endpoint2 ] && EPF=$RUNS/vllm_endpoint2; [ -z "$EPF" ] && [ -f $RUNS/vllm_endpoint ] && EPF=$RUNS/vllm_endpoint
    if [ -n "$EPF" ]; then
      [ "$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$(cat $EPF)/models")" = "200" ] && EPFAIL=0 || EPFAIL=$((EPFAIL+1))
      [ $EPFAIL -ge 3 ] && { status "ANOMALY: endpoint not answering 3 checks in a row"; exit 0; }
      if pgrep -f "a1_ladder.py run" >/dev/null; then
        [ "$(srvrun "$(cat $EPF)")" = "0" ] && IDLE=$((IDLE+1)) || IDLE=0
        [ $IDLE -ge 5 ] && { status "ANOMALY: a plan is running and the server has had no request for 5 checks (deaf clients?)"; exit 0; }
      fi
      grep -qE "running .* \(round" $RUNS/chain.log 2>/dev/null && [ $((NOW - LASTT)) -ge 4500 ] && { status "ANOMALY: no new result for 75 min while a plan is running"; exit 0; }
    fi
  fi
  [ $((NOW - T0)) -ge $((MAX * 60)) ] && { status "heartbeat after $MAX min"; exit 0; }
  sleep 60
done
