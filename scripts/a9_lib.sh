# A8-c / A9 — shared shell functions, SOURCED by scripts/a9_chain.sh and scripts/a9_run.sh (needs PY, LOG and say()). Frozen at launch.
# run_plan <plan.json> <run-root> <endpoint> [max rounds]: runs the plan with the resume loop of the program: a session that ended in
# infrastructure_failure is not an observation; it is moved to <cell>.failed<n> and re-run, at most 3 times per cell (retries.json).
run_plan() {
  _PLAN=$1; _RR=$2; _EP=$3; _MAXR=${4:-10}; _PID=$(basename "$_PLAN" _plan.json); _R=$_RR/$_PID; _rounds=0
  while :; do
    _rounds=$((_rounds+1)); say "running $_PID (round $_rounds)"
    CM_OPENAI_BASE_URL="$_EP" $PY scripts/a1_ladder.py run --plan "$_PLAN" --run-root "$_RR" >> "$LOG" 2>&1
    _REDO=$($PY - "$_R" <<'PYEOF'
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
R.mkdir(parents=True, exist_ok=True); rc.write_text(json.dumps(retries, indent=1)); print(redo)
PYEOF
)
    _PENDING=$($PY -c "import json,glob; plan=json.load(open('$_PLAN')); done=set(p.split('/')[-2] for p in glob.glob('$_R/*/result.json')); print(sum(1 for c in plan['cells'] if c['cell_id'] not in done))")
    say "$_PID round $_rounds: redo=$_REDO pending=$_PENDING"
    [ "$_PENDING" = "0" ] && break
    [ $_rounds -ge $_MAXR ] && { say "$_PID: giving up after $_MAXR rounds"; break; }
    [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$_EP/models")" = "200" ] || { say "server not answering"; return 1; }
    sleep 30
  done
  return 0
}
# readiness <endpoint> <model> <thinking true|false>
readiness() {
  _REPLY=$(curl -s -m 240 "$1/chat/completions" -H 'Content-Type: application/json' -d "{\"model\":\"$2\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+3? Answer with the number only.\"}],\"max_tokens\":512,\"chat_template_kwargs\":{\"enable_thinking\":$3}}")
  echo "readiness ($2, thinking $3): $(echo "$_REPLY" | head -c 300)" >> "$LOG"
  echo "$_REPLY" | grep -q '"content"' && say "readiness: $2 answers (thinking $3)" || say "WARNING: $2 gave no answer (thinking $3)"
}
