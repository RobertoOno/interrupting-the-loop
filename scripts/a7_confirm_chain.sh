#!/bin/sh
# A7 wall CONFIRMATION chain (docs/A7_PAREDE_V1.md, phase 2 + E1), started any time: waits for "screen done"; takes the screen's
# wall_candidates that are COMPLETE (8 observed cells in every arm), in the fixed order W1, W2, W3, W4, at most three; builds six new
# held-out instances per wall (seeds a7-confirm-<W>-1..6, certificate clean), verifies them in Lean, writes sibling reference sources and
# the four plans, commits them; starts the pod (base + a2c4-own2 + a2c4-curm2) and its guard; runs base x8, own2 x8, base+reference x4,
# curm2 x4 with the resume loop; reads with the script written before the data; "confirm done" and the stop file.
#   screen -dmS a7conf caffeinate -i -s sh scripts/a7_confirm_chain.sh       (log runs/a7c/confirm.log)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a7c; LOG=$RUNS/confirm.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for 'screen done' in runs/a7/screen.log"
until grep -q "screen done" runs/a7/screen.log 2>/dev/null; do sleep 120; done
WALLS=$($PY -c "
import json
s = json.load(open('docs/a7_results/screen.json'))
c = s['candidates']
print(' '.join([w for w in ['W1', 'W2', 'W3', 'W4'] if c[w]['class'] == 'wall_candidate' and c[w]['complete']][:3]))")
say "screen verdict: $($PY -c "import json; s=json.load(open('docs/a7_results/screen.json')); print(s['verdict'], {w: (c['class'], c['complete']) for w, c in s['candidates'].items()})")"
[ -n "$WALLS" ] || { say "no complete wall candidate: confirmation not launched"; say "confirm done"; exit 0; }
NW=$(echo $WALLS | wc -w | tr -d ' ')
say "walls to confirm (fixed order, at most three): $WALLS"
$PY scripts/a7_screen.py build --root worlds/walls --prefix a7-confirm --per-step 6 --steps $WALLS --phase a7_confirm --index docs/a7_confirm_worlds.json >> "$LOG" 2>&1 || { say "build failed (certificate or collision): stop for review"; say "confirm done"; exit 0; }
$PY scripts/a7_screen.py verify --index docs/a7_confirm_worlds.json --out docs/a7_confirm_verification.json --workers 8 >> "$LOG" 2>&1 || { say "Lean verification failed: stop for review"; say "confirm done"; exit 0; }
say "confirmation worlds verified: $($PY -c "import json; print(json.load(open('docs/a7_confirm_verification.json'))['summary'])")"
$PY scripts/a7_screen.py sources --index docs/a7_confirm_worlds.json --out docs/a7c_sources > /dev/null
$PY scripts/a7_screen.py plan-confirm --index docs/a7_confirm_worlds.json --sources docs/a7c_sources/index.json --out-dir docs >> "$LOG" 2>&1 || { say "planning failed"; say "confirm done"; exit 0; }
git add worlds/walls docs/a7_confirm_worlds.json docs/a7_confirm_verification.json docs/a7c_sources docs/a7c_base_v1_plan.json docs/a7c_own2_v1_plan.json docs/a7c_ref_v1_plan.json docs/a7c_curm2_v1_plan.json docs/a7_results/screen.md docs/a7_results/screen.json && \
  git -c core.hooksPath=/dev/null commit -q -m "A7 confirmation: screen read, six held-out instances per wall ($WALLS) verified in Lean, sibling sources and plans

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" && say "committed: $(git log --oneline -1)"
CAP=$((3 + 9 * NW)); DEADLINE=$(date -v+$((CAP + 1))H '+%Y-%m-%d %H:%M')
CM_A2C_CAP_H=$CAP screen -dmS a7cpod caffeinate -i -s sh scripts/a7_confirm_pod.sh
A2C3_RUNS=$RUNS A2C3_POD_FILE=$RUNS/pod_id A2C3_MARKER="confirm done" A2C3_LOG=$LOG A2C3_DEADLINE="$DEADLINE" screen -dmS a7cguard caffeinate -i -s sh scripts/a2c3_guard.sh
say "pod (cap ${CAP}h) and guard (deadline $DEADLINE) started; waiting for $RUNS/vllm_endpoint"
n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 240 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm_endpoint ] || { say "endpoint never appeared"; say "confirm done"; exit 3; }
EP=$(cat $RUNS/vllm_endpoint); say "endpoint $EP"
for m in qwen3.8-27b a2c4-own2 a2c4-curm2; do
  REPLY=$(curl -s -m 180 "$EP/chat/completions" -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+3? Answer with the number only.\"}],\"max_tokens\":512,\"chat_template_kwargs\":{\"enable_thinking\":true}}")
  echo "readiness ($m): $(echo "$REPLY" | head -c 300)" >> "$LOG"
  echo "$REPLY" | grep -q '"reasoning' && say "readiness: $m answers with a reasoning field" || say "WARNING: $m gave no reasoning field"
done
for pid in a7c_base_v1 a7c_own2_v1 a7c_ref_v1 a7c_curm2_v1; do
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
$PY scripts/analysis_a7_confirm.py --walls $WALLS --plan-base docs/a7c_base_v1_plan.json --run-base $RUNS/a7c_base_v1 --plan-own2 docs/a7c_own2_v1_plan.json --run-own2 $RUNS/a7c_own2_v1 \
  --plan-ref docs/a7c_ref_v1_plan.json --run-ref $RUNS/a7c_ref_v1 --plan-curm2 docs/a7c_curm2_v1_plan.json --run-curm2 $RUNS/a7c_curm2_v1 \
  --out docs/a7_results/confirm.md --json docs/a7_results/confirm.json 2>&1 | tee -a "$LOG"
say "confirm done"; touch $RUNS/vllm_stop
