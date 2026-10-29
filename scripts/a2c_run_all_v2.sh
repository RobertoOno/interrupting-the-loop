#!/bin/sh
# A2 consolidation — test phase, per docs/A2_CONSOLIDACAO_V1.md: wait for the served endpoint (base + three LoRA modules), one smoke
# request per served name (not read), preflight --no-lean of the four plans, run base -> p1 -> p2 -> p3 (144 sessions each, same
# server, same order), single read with scripts/analysis_a2_consolidation.py, then request the pod stop.
# v2 (replication): A2C_TAG selects plans docs/${TAG}_<arm>_plan_v1.json, runs runs/${TAG}, results docs/${TAG}_results; arms
# base p1 p2 p3 baset p2t (the last two: thinking on, L2/L3); read by analysis_a2_consolidation_v2.py.
#   A2C_TAG=a2c2 screen -dmS a2c2run caffeinate -i -s sh scripts/a2c_run_all_v2.sh
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
for arm in base p1 p2 p3 baset p2t; do
  PRE=$($PY scripts/a1_ladder.py preflight --plan docs/${TAG}_${arm}_plan_v1.json --no-lean | $PY -c "import sys,json; d=json.load(sys.stdin); print('ok' if d['ok'] else 'FAIL '+json.dumps({k:d[k] for k in ('drift','sandbox')}))")
  say "preflight $arm: $PRE"; [ "$PRE" = "ok" ] || { say "preflight failed; stopping"; touch "$STOP"; exit 3; }
done
for arm in base p1 p2 p3 baset p2t; do
  say "running $arm"
  CM_OPENAI_BASE_URL="$EP" $PY scripts/a1_ladder.py run --plan docs/${TAG}_${arm}_plan_v1.json --run-root $RUNS >> "$LOG" 2>&1
  say "$arm done: $(tail -1 $RUNS/${TAG}_${arm}_v1/run.log | cut -c1-200)"
done
mkdir -p $RES
$PY scripts/analysis_a2_consolidation_v2.py --plan-base docs/${TAG}_base_plan_v1.json --run-base $RUNS/${TAG}_base_v1 --plan-p1 docs/${TAG}_p1_plan_v1.json --run-p1 $RUNS/${TAG}_p1_v1 \
  --plan-p2 docs/${TAG}_p2_plan_v1.json --run-p2 $RUNS/${TAG}_p2_v1 --plan-p3 docs/${TAG}_p3_plan_v1.json --run-p3 $RUNS/${TAG}_p3_v1 \
  --plan-baset docs/${TAG}_baset_plan_v1.json --run-baset $RUNS/${TAG}_baset_v1 --plan-p2t docs/${TAG}_p2t_plan_v1.json --run-p2t $RUNS/${TAG}_p2t_v1 \
  --out $RES/consolidation.md --json $RES/consolidation.json | tee -a "$LOG"
touch "$STOP"; say "analysis done; stop file written"
