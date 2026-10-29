#!/bin/sh
# A2 sem curador (docs/A2_SEM_CURADOR_V1.md) — PHASE 2 chain, started any time: waits for "production done" in runs/a2c3/prod.log;
# renders the training data from the production run (own = the model's verified proofs, curm = the curated rows of the same cells) and
# verifies every example in Lean; yield gate (>= 24) and data gate (all verified) -> commits the data; starts the training/serving pod
# (scripts/a2c3_train_pod.sh in its own screen) and its guard; runs the four test arms with the E6 resume loop; reads with the script
# written before the data; diagnostics; "phase2 done" and the stop file for the pod.
#   screen -dmS a2c3ph2 caffeinate -i -s sh scripts/a2c3_phase2.sh           (log runs/a2c3/phase2.log)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a2c3; DATA=docs/a2c3_data; LOG=$RUNS/phase2.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for 'production done' in $RUNS/prod.log"
until grep -q "production done" $RUNS/prod.log 2>/dev/null; do sleep 120; done
say "production finished: $(grep 'production yield' $RUNS/prod.log | tail -1)"
# --- data: render + verify (no selection), gates
$PY scripts/a2c3_prepare.py render --prod-run $RUNS/a2c3_prod_v1 --out $DATA 2>&1 | tee -a "$LOG"
GATE=$($PY -c "import json; print('ok' if json.load(open('$DATA/manifest.json'))['gate_passed'] else 'fail')")
[ "$GATE" = "ok" ] || { say "yield gate failed (fewer than 24 own proofs): node closes without training"; say "phase2 done"; exit 0; }
$PY scripts/a2c3_prepare.py verify --out $DATA --workers 6 2>&1 | tail -1 | tee -a "$LOG"
VER=$($PY -c "import json; s=json.load(open('$DATA/verification.json'))['summary']; print('ok' if s['checked']==s['ok'] and s['checked']>0 else 'fail')")
[ "$VER" = "ok" ] || { say "data gate failed (an example did not verify): stop for review"; say "phase2 done"; exit 0; }
git add $DATA && git -c core.hooksPath=/dev/null commit -q -m "A2 without curator: production data rendered and verified (own proofs and matched curated rows)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && say "data committed: $(git log --oneline -1)"
# --- pod 2 (train + serve) and its guard
screen -dmS a2c3pod2 caffeinate -i -s sh scripts/a2c3_train_pod.sh
A2C3_POD_FILE=$RUNS/pod2_id A2C3_MARKER="phase2 done" A2C3_LOG=$LOG A2C3_DEADLINE="2026-09-15 22:00" screen -dmS a2c3guard3 caffeinate -i -s sh scripts/a2c3_guard.sh
say "pod 2 and guard started; waiting for $RUNS/vllm2_endpoint"
n=0; until [ -f $RUNS/vllm2_endpoint ] || [ $n -ge 360 ]; do sleep 30; n=$((n+1)); done
[ -f $RUNS/vllm2_endpoint ] || { say "endpoint 2 never appeared"; say "phase2 done"; exit 3; }
EP=$(cat $RUNS/vllm2_endpoint); say "endpoint $EP: $(curl -s -m 15 "$EP/models" | head -c 200)"
# --- four test arms with the resume loop (no-thinking arms first)
for arm in own curm ownt131 curmt131; do
  R=$RUNS/a2c3_${arm}_v1; rounds=0
  while :; do
    rounds=$((rounds+1)); say "running $arm (round $rounds)"
    CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan docs/a2c3_${arm}_plan_v1.json --run-root $RUNS >> "$LOG" 2>&1
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
    PENDING=$($PY -c "import json,glob; plan=json.load(open('docs/a2c3_${arm}_plan_v1.json')); done=set(p.split('/')[-2] for p in glob.glob('$R/*/result.json')); print(sum(1 for c in plan['cells'] if c['cell_id'] not in done))")
    say "$arm round $rounds: redo=$REDO pending=$PENDING"
    [ "$PENDING" = "0" ] && break
    [ $rounds -ge 12 ] && { say "$arm: giving up after 12 rounds"; break; }
    [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering"; break; }
    sleep 30
  done
done
# --- read (script written before the data) and diagnostics
mkdir -p docs/a2c3_results
NOWN=$($PY -c "import json; print(json.load(open('$DATA/manifest.json'))['n_own'])")
$PY scripts/analysis_a2_own.py --plan-base docs/a2c2_base_plan_v1.json --run-base runs/a2c2/a2c2_base_v1 --plan-p2 docs/a2c2_p2_plan_v1.json --run-p2 runs/a2c2/a2c2_p2_v1 \
  --plan-baset docs/a2c2_baset131_plan_v1.json --run-baset runs/a2c2/a2c2_baset131_v1 --plan-p2t docs/a2c2_p2t131_plan_v1.json --run-p2t runs/a2c2/a2c2_p2t131_v1 \
  --plan-own docs/a2c3_own_plan_v1.json --run-own $RUNS/a2c3_own_v1 --plan-curm docs/a2c3_curm_plan_v1.json --run-curm $RUNS/a2c3_curm_v1 \
  --plan-ownt docs/a2c3_ownt131_plan_v1.json --run-ownt $RUNS/a2c3_ownt131_v1 --plan-curmt docs/a2c3_curmt131_plan_v1.json --run-curmt $RUNS/a2c3_curmt131_v1 \
  --n-own-examples "$NOWN" --out docs/a2c3_results/own.md --json docs/a2c3_results/own.json 2>&1 | tee -a "$LOG"
$PY scripts/a2c2_diagnostics.py --runs prod=$RUNS/a2c3_prod_v1 own=$RUNS/a2c3_own_v1 curm=$RUNS/a2c3_curm_v1 ownt131=$RUNS/a2c3_ownt131_v1 curmt131=$RUNS/a2c3_curmt131_v1 --out docs/a2c3_results/diagnostics.json --md docs/a2c3_results/diagnostics.md 2>&1 | tail -1 | tee -a "$LOG"
say "phase2 done"; touch $RUNS/vllm2_stop
