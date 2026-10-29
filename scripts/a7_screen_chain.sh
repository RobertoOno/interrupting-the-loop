#!/bin/sh
# A7 wall screen (docs/A7_PAREDE_V1.md) — chain on the served base + a2c4-own2: readiness of both models; a7s_base_v1 (none + sibling
# reference, 64 cells) then a7s_own2_v1 (32 cells), each with the resume loop for proxy transport cuts (a cell whose result is an
# infrastructure failure is re-run, at most 3 times); the screen read with the script written before the data; "screen done" for the
# guard and the stop file for the pod script (which removes the pod).
#   screen -dmS a7chain caffeinate -i -s sh scripts/a7_screen_chain.sh      (log runs/a7/screen.log)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a7; LOG=$RUNS/screen.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for $RUNS/vllm_endpoint"; n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 240 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm_endpoint ] || { say "endpoint never appeared"; exit 3; }
EP=$(cat $RUNS/vllm_endpoint); say "endpoint $EP"
for m in qwen3.8-27b a2c4-own2; do
  REPLY=$(curl -s -m 180 "$EP/chat/completions" -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+3? Answer with the number only.\"}],\"max_tokens\":512,\"chat_template_kwargs\":{\"enable_thinking\":true}}")
  echo "readiness ($m): $(echo "$REPLY" | head -c 300)" >> "$LOG"
  echo "$REPLY" | grep -q '"reasoning' && say "readiness: $m answers with a reasoning field" || say "WARNING: $m gave no reasoning field"
done
for pid in a7s_base_v1 a7s_own2_v1; do
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
    say "$pid round $rounds: redo=$REDO pending=$PENDING"
    [ "$PENDING" = "0" ] && break
    [ $rounds -ge 12 ] && { say "$pid: giving up after 12 rounds"; break; }
    [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering"; break; }
    sleep 30
  done
done
mkdir -p docs/a7_results
$PY scripts/analysis_a7_screen.py --plan-base docs/a7s_base_v1_plan.json --run-base $RUNS/a7s_base_v1 --plan-own2 docs/a7s_own2_v1_plan.json --run-own2 $RUNS/a7s_own2_v1 \
  --out docs/a7_results/screen.md --json docs/a7_results/screen.json 2>&1 | tee -a "$LOG"
say "screen done"; touch $RUNS/vllm_stop
