#!/bin/sh
# A2 consolidation — test phase, per docs/A2_CONSOLIDACAO_V1.md: wait for the served endpoint (base + three LoRA modules), one smoke
# request per served name (not read), preflight --no-lean of the four plans, run base -> p1 -> p2 -> p3 (144 sessions each, same
# server, same order), single read with scripts/analysis_a2_consolidation.py, then request the pod stop.
# v2 (replication): A2C_TAG selects plans docs/${TAG}_<arm>_plan_v1.json, runs runs/${TAG}, results docs/${TAG}_results; arms
# base p1 p2 p3 baset p2t (the last two: thinking on, L2/L3); read by analysis_a2_consolidation_v2.py.
# v3 (replication, E2): the four no-thinking arms run on the 32k server; then the server is relaunched over SSH with a 160k
# context and the thinking arms run with 131k budgets (plans *131); read by analysis v2 with those plans.
#   A2C_TAG=a2c2 screen -dmS a2c2run caffeinate -i -s sh scripts/a2c_run_all_v3.sh
set -u
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="${CM_LAKE_SHARED:-$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1}"
TAG="${A2C_TAG:-a2c}"; RUNS="runs/$TAG"; RES="docs/${TAG}_results"
PY=.venv/bin/python; LOG=$RUNS/run_all.log; EPF=$RUNS/vllm_endpoint; STOP=$RUNS/vllm_stop
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for $EPF"
n=0; while [ ! -f "$EPF" ] && [ $n -lt 1440 ]; do sleep 30; n=$((n+1)); screen -ls | grep -q "${TAG}pod" || { say "pod launcher gone before the endpoint; giving up"; exit 2; }; done
[ -f "$EPF" ] || { say "endpoint never appeared"; exit 2; }
EP=$(cat "$EPF"); say "endpoint $EP"
say "served models: $(curl -s -m 20 "$EP/models" | $PY -c 'import sys,json; print([m["id"] for m in json.load(sys.stdin)["data"]])')"
for name in qwen3.8-27b $TAG-p1 $TAG-p2 $TAG-p3; do
  R=$(curl -s -m 300 "$EP/chat/completions" -H 'Content-Type: application/json' -d "{\"model\":\"$name\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word OK.\"}],\"max_tokens\":16,\"chat_template_kwargs\":{\"enable_thinking\":false}}" | $PY -c 'import sys,json; d=json.load(sys.stdin); c=d["choices"][0]; print(repr((c["message"].get("content") or "")[:40]), c["finish_reason"], d.get("usage",{}).get("completion_tokens"))' 2>&1)
  say "smoke $name: $R"
done
for arm in base p1 p2 p3 baset131 p2t131; do
  PRE=$($PY scripts/a1_ladder.py preflight --plan docs/${TAG}_${arm}_plan_v1.json --no-lean | $PY -c "import sys,json; d=json.load(sys.stdin); print('ok' if d['ok'] else 'FAIL '+json.dumps({k:d[k] for k in ('drift','sandbox')}))")
  say "preflight $arm: $PRE"; [ "$PRE" = "ok" ] || { say "preflight failed; stopping"; touch "$STOP"; exit 3; }
done
for arm in base p1 p2 p3; do
  say "running $arm"
  CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan docs/${TAG}_${arm}_plan_v1.json --run-root $RUNS >> "$LOG" 2>&1
  say "$arm done: $(tail -1 $RUNS/${TAG}_${arm}_v1/run.log | cut -c1-200)"
done
# --- E2: relaunch the server with a 160k context for the thinking arms (131k budgets)
POD=$(grep -o "pod: [a-z0-9]*" $RUNS/pod.log | head -1 | cut -d" " -f2); INFO=$(runpodctl ssh info "$POD" 2>>"$LOG")
KEY=$(echo "$INFO" | $PY -c 'import sys,json; print(json.load(sys.stdin)["ssh_key"]["path"])'); IP=$(echo "$INFO" | $PY -c 'import sys,json; print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | $PY -c 'import sys,json; print(json.load(sys.stdin)["port"])')
SSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -p $PORT root@$IP"
say "relaunching vllm with a 160k context on $POD"
$SSH "pkill -f 'vllm[ ]serve'; sleep 10; cd /workspace/$TAG && (nohup vllm serve Qwen/Qwen3.8-27B --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules $TAG-p1=/workspace/$TAG/adapters/$TAG-p1 $TAG-p2=/workspace/$TAG/adapters/$TAG-p2 $TAG-p3=/workspace/$TAG/adapters/$TAG-p3 --max-model-len 163840 --max-num-seqs 16 --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > vllm_serve_160k.log 2>&1 &); sleep 3; echo relaunched" >>"$LOG" 2>&1
n=0; until [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models" 2>/dev/null)" = "200" ] || [ $n -ge 60 ]; do sleep 20; n=$((n+1)); done
[ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$EP/models")" = "200" ] || { say "160k server did not come up"; $SSH "tail -20 /workspace/$TAG/vllm_serve_160k.log" >>"$LOG" 2>&1; touch "$STOP"; exit 4; }
say "160k server up: $(curl -s -m 15 "$EP/models" | $PY -c 'import sys,json; d=json.load(sys.stdin)["data"]; print([m["id"] for m in d], d[0].get("max_model_len"))')"
for arm in baset131 p2t131; do
  say "running $arm"
  CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan docs/${TAG}_${arm}_plan_v1.json --run-root $RUNS >> "$LOG" 2>&1
  say "$arm done: $(tail -1 $RUNS/${TAG}_${arm}_v1/run.log | cut -c1-200)"
done
mkdir -p $RES
$PY scripts/analysis_a2_consolidation_v2.py --plan-base docs/${TAG}_base_plan_v1.json --run-base $RUNS/${TAG}_base_v1 --plan-p1 docs/${TAG}_p1_plan_v1.json --run-p1 $RUNS/${TAG}_p1_v1 \
  --plan-p2 docs/${TAG}_p2_plan_v1.json --run-p2 $RUNS/${TAG}_p2_v1 --plan-p3 docs/${TAG}_p3_plan_v1.json --run-p3 $RUNS/${TAG}_p3_v1 \
  --plan-baset docs/${TAG}_baset131_plan_v1.json --run-baset $RUNS/${TAG}_baset131_v1 --plan-p2t docs/${TAG}_p2t131_plan_v1.json --run-p2t $RUNS/${TAG}_p2t131_v1 \
  --out $RES/consolidation.md --json $RES/consolidation.json | tee -a "$LOG"
touch "$STOP"; say "analysis done; stop file written"
