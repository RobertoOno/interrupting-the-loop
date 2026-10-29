#!/bin/sh
# A2 sem curador (docs/A2_SEM_CURADOR_V1.md) — PRODUCTION phase: the base (thinking on, 131 072 tokens) on L1, L2, L3 of the 48
# training instances, one attempt each, no selection: every proof the verifier accepts is a training example. Resume loop for proxy
# transport cuts (E6 rule of the replication: a cell whose result is an infrastructure failure is re-run, at most 3 times). At the end:
# yield summary, "production done" for the guard, stop file for the pod script (which removes the pod).
#   screen -dmS a2c3prod caffeinate -i -s sh scripts/a2c3_prod.sh          (log runs/a2c3/prod.log)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a2c3; LOG=$RUNS/prod.log; PLAN=docs/a2c3_prod_plan_v1.json; R=$RUNS/a2c3_prod_v1; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for $RUNS/vllm_endpoint"; n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 240 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm_endpoint ] || { say "endpoint never appeared"; exit 3; }
EP=$(cat $RUNS/vllm_endpoint); say "endpoint $EP"
# readiness of the reasoning path: one short completion with thinking on (not read)
REPLY=$(curl -s -m 180 "$EP/chat/completions" -H 'Content-Type: application/json' -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"What is 2+3? Answer with the number only."}],"max_tokens":512,"chat_template_kwargs":{"enable_thinking":true}}')
echo "readiness: $(echo "$REPLY" | head -c 500)" >> "$LOG"
echo "$REPLY" | grep -q '"reasoning' && say "readiness: reasoning field present" || say "WARNING: no reasoning field in the readiness reply"
rounds=0
while :; do
  rounds=$((rounds+1)); say "running production (round $rounds)"
  CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan $PLAN --run-root $RUNS >> "$LOG" 2>&1
  REDO=$($PY - "$R" <<'PYEOF'
import json, sys, shutil, glob
from pathlib import Path
R = Path(sys.argv[1]); rc = R / "retries.json"; retries = json.loads(rc.read_text()) if rc.exists() else {}
redo = 0
for f in glob.glob(str(R / "*/result.json")):
    if ".failed" in Path(f).parent.name:
        continue
    r = json.load(open(f))
    if r["result"]["status"] == "infrastructure_failure":
        cell = Path(f).parent.name; n = retries.get(cell, 0)
        if n < 3:
            retries[cell] = n + 1; shutil.move(str(Path(f).parent), str(R / f"{cell}.failed{n + 1}")); redo += 1
rc.write_text(json.dumps(retries, indent=1)); print(redo)
PYEOF
)
  PENDING=$($PY -c "import json,glob; plan=json.load(open('$PLAN')); done=set(p.split('/')[-2] for p in glob.glob('$R/*/result.json')); print(sum(1 for c in plan['cells'] if c['cell_id'] not in done))")
  say "production round $rounds: redo=$REDO pending=$PENDING"
  [ "$PENDING" = "0" ] && break
  [ $rounds -ge 12 ] && { say "giving up after 12 rounds"; break; }
  [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering"; break; }
  sleep 30
done
$PY - "$R" <<'PYEOF' | tee -a "$LOG"
import json, glob, sys, collections
R = sys.argv[1]; c = collections.Counter(); k = collections.Counter()
for f in glob.glob(f"{R}/*/result.json"):
    if ".failed" in f.split("/")[-2]:
        continue
    r = json.load(open(f))["result"]; s = f.split("/")[-2].split("_")[1]; c[s] += 1; k[s] += int(bool(r.get("target_solved")))
print("production yield:", {s: f"{k[s]}/{c[s]}" for s in sorted(c)}, "total", sum(k.values()), "of", sum(c.values()))
PYEOF
say "production done"; touch $RUNS/vllm_stop
