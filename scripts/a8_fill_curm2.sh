#!/bin/sh
# A8 FILL (docs/A8_CURADORIA_ESTREITA_V1.md, E1/E2) — collects pending cells of the curated arm ONLY. It never runs the read: with the
# machine about to be shut down, an interrupted chain must not consume the single read with a partial arm. Resume loop
# for proxy transport cuts; the read written before the data; evidence archive, commit and push; then the pod is removed directly.
#   screen -dmS a8fill caffeinate -i -s sh scripts/a8_fill_curm2.sh        (log runs/a8/chain.log, appended)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a8; LOG=$RUNS/chain.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "RESUME (E1): only the curated arm; base and own2 already complete"
say "waiting for $RUNS/vllm_endpoint"; n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 720 ]; do sleep 30; n=$((n+1)); done   # 6 h: on 18/09 the pod took 3 h to serve and the 2 h wait expired first
[ -f $RUNS/vllm_endpoint ] || { say "endpoint never appeared"; exit 3; }
EP=$(cat $RUNS/vllm_endpoint); POD=$(cat $RUNS/pod_id); say "endpoint $EP, pod $POD"
for m in qwen3.8-27b a2c4-own2 a2c4-curm2; do
  REPLY=$(curl -s -m 180 "$EP/chat/completions" -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+3? Answer with the number only.\"}],\"max_tokens\":512,\"chat_template_kwargs\":{\"enable_thinking\":true}}")
  echo "readiness ($m): $(echo "$REPLY" | head -c 300)" >> "$LOG"
  echo "$REPLY" | grep -q '"reasoning' && say "readiness: $m answers with a reasoning field" || say "WARNING: $m gave no reasoning field"
done
for pid in a8_curm2_v1; do
  PLAN=docs/${pid}_plan.json; R=$RUNS/$pid; rounds=0
  while :; do
    rounds=$((rounds+1)); say "running $pid (round $rounds)"
    CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan $PLAN --run-root $RUNS >> "$LOG" 2>&1
    REDO=$($PY - "$R" <<'PYEOF'
import json, sys, shutil, glob
from pathlib import Path
R = Path(sys.argv[1]); rc = R / "retries.json"; retries = json.loads(rc.read_text()) if rc.exists() else {}
redo = 0
for f in glob.glob(str(R / "*/result.json")):
    name = Path(f).parent.name
    if ".failed" in name or ".interrupted" in name:
        continue
    r = json.load(open(f))
    if r["result"]["status"] == "infrastructure_failure":
        n = retries.get(name, 0)
        if n < 3:
            retries[name] = n + 1; shutil.move(str(Path(f).parent), str(R / f"{name}.failed{n + 1}")); redo += 1
rc.write_text(json.dumps(retries, indent=1)); print(redo)
PYEOF
)
    PENDING=$($PY -c "import json,glob; plan=json.load(open('$PLAN')); done=set(p.split('/')[-2] for p in glob.glob('$R/*/result.json')); print(sum(1 for c in plan['cells'] if c['cell_id'] not in done))")
    say "$pid round $rounds: redo=$REDO pending=$PENDING"
    [ "$PENDING" = "0" ] && break
    [ $rounds -ge 10 ] && { say "$pid: giving up after 10 rounds"; break; }
    [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering"; break; }
    sleep 30
  done
done
say "fill done (no read: the curated arm is still partial; the single read happens only when it is complete)"
touch $RUNS/vllm_stop
say "stop file written; the pod script removes the pod"
