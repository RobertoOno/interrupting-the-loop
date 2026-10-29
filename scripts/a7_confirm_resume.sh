#!/bin/sh
# A7 confirmation — RESUME after the Mac reboot of 17/09 (docs/A7_PAREDE_V1.md, E2): the pod and its vLLM server survived, the local chain
# did not. Runs only the unfinished descriptive arm a7c_curm2_v1 with the same resume loop, then the pre-registered read (walls: W1),
# "confirm done", and removes the pod directly (the original pod script, which held the stop file and the cap, died in the reboot).
#   screen -dmS a7resume caffeinate -i -s sh scripts/a7_confirm_resume.sh    (log runs/a7c/confirm.log, appended)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a7c; LOG=$RUNS/confirm.log; EP=$(cat $RUNS/vllm_endpoint); POD=$(cat $RUNS/pod_id)
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "RESUME after reboot (E2): endpoint $EP, pod $POD"
[ "$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering at resume"; }
PLAN=docs/a7c_curm2_v1_plan.json; R=$RUNS/a7c_curm2_v1; rounds=0
while :; do
  rounds=$((rounds+1)); say "running a7c_curm2_v1 (resume round $rounds)"
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
  say "a7c_curm2_v1 resume round $rounds: redo=$REDO pending=$PENDING"
  [ "$PENDING" = "0" ] && break
  [ $rounds -ge 8 ] && { say "a7c_curm2_v1: giving up after 8 resume rounds"; break; }
  [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "server not answering"; break; }
  sleep 30
done
mkdir -p docs/a7_results
$PY scripts/analysis_a7_confirm.py --walls W1 --plan-base docs/a7c_base_v1_plan.json --run-base $RUNS/a7c_base_v1 --plan-own2 docs/a7c_own2_v1_plan.json --run-own2 $RUNS/a7c_own2_v1 \
  --plan-ref docs/a7c_ref_v1_plan.json --run-ref $RUNS/a7c_ref_v1 --plan-curm2 docs/a7c_curm2_v1_plan.json --run-curm2 $RUNS/a7c_curm2_v1 \
  --out docs/a7_results/confirm.md --json docs/a7_results/confirm.json 2>&1 | tee -a "$LOG"
say "confirm done"
runpodctl pod remove "$POD" >> "$LOG" 2>&1 && say "pod $POD removed by the resume chain" || say "pod removal FAILED (the guard will retry)"
say "pods now: $(runpodctl pod list 2>&1 | tr -d '\n' | cut -c1-160)"
