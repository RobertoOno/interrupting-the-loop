#!/bin/sh
# A2 sem curador, iteration 2 (docs/A2_SEM_CURADOR_ITER2_V1.md) — PRODUCTION phase on the served base + a2c3-own:
#   1. production: a2c3-own with thinking (131 072 tokens) on L4, L5, E of the 48 training instances, one attempt each, no selection;
#   2. comparator: the base with the same thinking on L4, L5, E of the six held-out instances, four attempts (the baset arm for the read).
# Resume loop for proxy transport cuts (a cell whose result is an infrastructure failure is re-run, at most 3 times). At the end: yield
# summary, "production done" for the guard and the phase-2 chain, stop file for the pod script (which removes the pod).
#   screen -dmS a2c4prod caffeinate -i -s sh scripts/a2c4_prod.sh          (log runs/a2c4/prod.log)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a2c4; LOG=$RUNS/prod.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for $RUNS/vllm_endpoint"; n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 240 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm_endpoint ] || { say "endpoint never appeared"; exit 3; }
EP=$(cat $RUNS/vllm_endpoint); say "endpoint $EP"
REPLY=$(curl -s -m 180 "$EP/chat/completions" -H 'Content-Type: application/json' -d '{"model":"a2c3-own","messages":[{"role":"user","content":"What is 2+3? Answer with the number only."}],"max_tokens":512,"chat_template_kwargs":{"enable_thinking":true}}')
echo "readiness (a2c3-own): $(echo "$REPLY" | head -c 400)" >> "$LOG"
echo "$REPLY" | grep -q '"reasoning' && say "readiness: adapter answers with a reasoning field" || say "WARNING: no reasoning field in the readiness reply"
for arm in prod baset131; do
  PLAN=docs/a2c4_${arm}_plan_v1.json; R=$RUNS/a2c4_${arm}_v1; rounds=0
  while :; do
    rounds=$((rounds+1)); say "running $arm (round $rounds)"
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
    say "$arm round $rounds: redo=$REDO pending=$PENDING"
    [ "$PENDING" = "0" ] && break
    [ $rounds -ge 12 ] && { say "$arm: giving up after 12 rounds"; break; }
    [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering"; break; }
    sleep 30
  done
done
$PY - "$RUNS/a2c4_prod_v1" <<'PYEOF' | tee -a "$LOG"
import json, glob, sys, collections
R = sys.argv[1]; c = collections.Counter(); k = collections.Counter()
for f in glob.glob(f"{R}/*/result.json"):
    if ".failed" in f.split("/")[-2]:
        continue
    r = json.load(open(f))["result"]; s = f.split("/")[-2].split("_")[1]; c[s] += 1; k[s] += int(bool(r.get("target_solved")))
print("production yield:", {s: f"{k[s]}/{c[s]}" for s in sorted(c)}, "total", sum(k.values()), "of", sum(c.values()))
PYEOF
say "production done"; touch $RUNS/vllm_stop
