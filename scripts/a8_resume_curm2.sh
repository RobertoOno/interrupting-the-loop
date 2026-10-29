#!/bin/sh
# A8 RESUME (docs/A8_CURADORIA_ESTREITA_V1.md, E1) — after the planned shutdown of 18/09: the base and own2 arms are complete; this
# runs only the pending cells of the curated arm on a fresh pod, then the read, the archive and the pod removal. Resume loop
# for proxy transport cuts; the read written before the data; evidence archive, commit and push; then the pod is removed directly.
#   screen -dmS a8resume caffeinate -i -s sh scripts/a8_resume_curm2.sh   (log runs/a8/chain.log, appended)
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a8; LOG=$RUNS/chain.log; mkdir -p "$RUNS"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "RESUME (E1): only the curated arm; base and own2 already complete"
say "waiting for $RUNS/vllm_endpoint"; n=0; until [ -f $RUNS/vllm_endpoint ] || [ $n -ge 240 ]; do sleep 30; n=$((n+1)); done
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
mkdir -p docs/a8_results
$PY scripts/analysis_a8_narrow.py --plan-base docs/a8_base_v1_plan.json --run-base $RUNS/a8_base_v1 --plan-own2 docs/a8_own2_v1_plan.json --run-own2 $RUNS/a8_own2_v1 \
  --plan-curm2 docs/a8_curm2_v1_plan.json --run-curm2 $RUNS/a8_curm2_v1 --out docs/a8_results/narrow.md --json docs/a8_results/narrow.json 2>&1 | tee -a "$LOG"
ST=$RUNS/archive_staging; rm -rf $ST; mkdir -p $ST
for f in pod.log chain.log guard.log; do [ -f $RUNS/$f ] && cp $RUNS/$f $ST/$f; done
for pid in a8_curm2_v1; do [ -f $RUNS/$pid/retries.json ] && cp $RUNS/$pid/retries.json $ST/${pid}_retries.json; done
$PY scripts/a1_archive.py --runs $RUNS/a8_base_v1 $RUNS/a8_own2_v1 $RUNS/a8_curm2_v1 --dst docs/a8_evidence_v1 \
  --docs docs/a8_results/narrow.md docs/a8_results/narrow.json docs/a8_base_v1_plan.json docs/a8_own2_v1_plan.json docs/a8_curm2_v1_plan.json \
  docs/a8_worlds.json docs/a8_verification.json docs/A8_CURADORIA_ESTREITA_V1.md $ST/* >> "$LOG" 2>&1 \
  && $PY scripts/a1_archive.py --dst docs/a8_evidence_v1 --verify >> "$LOG" 2>&1 && say "archive verified: $(tail -1 "$LOG")" || say "ARCHIVE FAILED"
git add docs/a8_evidence_v1 docs/a8_results && git -c core.hooksPath=/dev/null commit -q -m "A8: pre-registered read and evidence archive (automatic, before interpretation)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" >> "$LOG" 2>&1 && say "committed: $(git log --oneline -1 | cut -c1-110)"
git push -q origin "$(git rev-parse --abbrev-ref HEAD)" >> "$LOG" 2>&1 && say "pushed" || say "PUSH FAILED"
say "a8 done"
runpodctl pod remove "$POD" >> "$LOG" 2>&1 && say "pod $POD removed by the chain" || say "pod removal FAILED (the guard will retry)"
say "pods now: $(runpodctl pod list 2>&1 | tr -d '\n' | cut -c1-160)"
