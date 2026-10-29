#!/bin/sh
# Programa 4 — Encaixe: the battery driver that runs ON the pod, self-contained (pre-registered PLANO 2026-09-09;
# operational amendment: the cockpit may be switched off, so server, searches, verifier and results all live on the
# pod, results on the attached NETWORK VOLUME, and the pod deletes itself at the end, on failure, or at the hour cap).
#   started detached by scripts/run_slot_pod.sh:  sh scripts/slot_pod_driver.sh [smoke|full]
# Layout on the volume (survives the pod): /workspace/cm-slot/{repo,runs/slot,driver.log,launch.json,CM-DONE|CM-FAILED}
# Design (identical to the pre-registration): beatavg L = 5000, BD flags, 120 samples/run (10 gens x 6 x 2 islands),
# 12 arms x 4 RNG seeds = 48 runs, PAR searches in parallel, resumable; proposer Qwen3-Coder-30B-A3B-Instruct in vLLM.
set -u
[ -f /etc/rp_environment ] && . /etc/rp_environment   # RUNPOD_POD_ID and the pod-scoped RUNPOD_API_KEY (not inherited by ssh commands)
MODE="${1:-full}"
BASE="${CM_BASE:-/workspace/cm-slot}"; REPO="$BASE/repo"; R="$BASE/runs/slot"; LOG="$BASE/driver.log"
MODEL_ID="${CM_MODEL:-Qwen/Qwen3-Coder-30B-A3B-Instruct}"
MAX_HOURS="${CM_MAX_HOURS:-7}"; PAR="${CM_PAR:-4}"
SEEDS="${CM_SEEDS:-11 12 13 14}"
ARMS="${CM_ARMS:-nohint words words_g0 wordseed wordseed_pin famseed famseed_pin codehint codehint_g0 famseed_words selfseed oracle}"
STR="One known family of strong constructions places an atom at zero holding a substantial fraction of the mass and spreads the rest over atoms accumulating geometrically toward the maximum, at positions like (1 - r**i) * (L - 1); single-scale sets of a few atoms are believed suboptimal."
VENV="${CM_VENV:-/root/.sv}"; PY=$VENV/bin/python
# vLLM pinned to the last PyPI wheel built for CUDA 12.8 (0.18.x: torch 2.10, transformers < 5); from 0.22 on the PyPI wheels
# are CUDA 13 builds, which the hosts with driver 570.x (CUDA 12.8) refuse ("NVIDIA driver too old"; libcudart.so.13),
# and 0.10.2 breaks on the template's transformers 5 (2026-09-09/10, EU-FR-1). torch comes from the cu128 index.
VLLM_SPEC="${CM_VLLM:-vllm==0.18.1}"; PIP_EXTRA="${CM_PIP_EXTRA:---extra-index-url https://download.pytorch.org/whl/cu128}"
# the template's /etc/rp_environment turns on hf_transfer (not installed in the venv: downloads abort) and xet; use plain http
export HF_HOME=/root/hf-cache HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=0; unset HF_XET_HIGH_PERFORMANCE
T0=$(date +%s)
mkdir -p "$R"; cd "$REPO" || exit 1
log() { echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $*" >> "$LOG"; }

terminate() {  # delete THIS pod: REST with the account key (container disk), then runpodctl, then GraphQL
  sync; log "TERMINATE pod ${RUNPOD_POD_ID:-?}"
  [ -n "${RUNPOD_POD_ID:-}" ] || { log "no RUNPOD_POD_ID: cannot self-terminate"; return; }
  # the ACCOUNT key (container-disk config, verified with `runpodctl user` at hand-over) first; the pod-scoped
  # injected key (REST GET answered 403 on 2026-09-09) only as a fallback for the GraphQL mutation
  ACC=$(sed -n 's/^apikey *= *"\(.*\)"/\1/p' /root/.runpod/config.toml 2>/dev/null | head -1)
  POD_KEY="${RUNPOD_API_KEY:-}"
  export PATH=/usr/local/bin:/root/.local/bin:$PATH
  for attempt in 1 2 3; do
    [ -n "$ACC" ] && curl -s -m 30 -X DELETE "https://rest.runpod.io/v1/pods/$RUNPOD_POD_ID" -H "Authorization: Bearer $ACC" >> "$LOG" 2>&1
    env -u RUNPOD_API_KEY runpodctl pod delete "$RUNPOD_POD_ID" >> "$LOG" 2>&1
    for K in "$ACC" "$POD_KEY"; do
      [ -n "$K" ] && curl -s -m 30 -X POST "https://api.runpod.io/graphql?api_key=$K" -H 'Content-Type: application/json' \
        -d "{\"query\":\"mutation { podTerminate(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) }\"}" >> "$LOG" 2>&1
    done
    sleep 20
  done
}
DONE_FLAG=""
finish() {
  [ -n "$DONE_FLAG" ] || { log "driver exiting without a DONE marker -> CM-FAILED"; touch "$BASE/CM-FAILED"; }
  tail -50 "$BASE/vllm.log" > "$BASE/vllm_tail.log" 2>/dev/null
  terminate
}
trap finish EXIT INT TERM

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
log "DRIVER START mode=$MODE pod=${RUNPOD_POD_ID:-?} gpu=$GPU_NAME"
# independent watchdog: whatever happens to this shell, the pod goes away after MAX_HOURS + 15 min
( sleep $((MAX_HOURS * 3600 + 900)); echo "$(date -u) WATCHDOG fired" >> "$LOG"; touch "$BASE/CM-FAILED"; terminate ) > /dev/null 2>&1 &
WD=$!

log "installing vLLM"
python3 -m venv --system-site-packages "$VENV" 2>/dev/null
"$VENV/bin/pip" install -q --upgrade pip >> "$LOG" 2>&1
"$VENV/bin/pip" install -q "$VLLM_SPEC" scipy $PIP_EXTRA >> "$LOG" 2>&1 || { log "pip failed"; exit 6; }
log "vLLM installed: $("$PY" -c "import vllm, torch, transformers; print(vllm.__version__, torch.__version__, torch.version.cuda, transformers.__version__)" 2>&1 | tail -1)"
"$PY" -c "import vllm" > /dev/null 2>&1 || { log "vLLM import failed (wheel/CUDA mismatch?)"; exit 6; }

if pgrep -f "vllm.entrypoints.openai.api_server" > /dev/null; then
  log "server already running (reusing it)"
else
  log "starting server ($MODEL_ID)"
  setsid "$PY" -m vllm.entrypoints.openai.api_server --model "$MODEL_ID" --port 8000 --max-model-len 8192 \
    --gpu-memory-utilization 0.92 --max-num-seqs 64 > "$BASE/vllm.log" 2>&1 < /dev/null &
fi
i=0
while :; do
  i=$((i+1))
  curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null | grep -q "Qwen3-Coder-30B" && { log "SERVER READY"; break; }
  [ $((i % 20)) -eq 0 ] && log "waiting server: $(tail -1 "$BASE/vllm.log" 2>/dev/null | cut -c1-160)"
  [ $i -ge 160 ] && { log "server never answered"; exit 7; }
  sleep 15
done

arm_flags() {  # $1 = arm -> extra flags (printed; $STR expanded by eval in search())
  case "$1" in
    nohint)        echo "" ;;
    words)         echo "--hint \"\$STR\"" ;;
    words_g0)      echo "--hint \"\$STR\" --hint-gens 1" ;;
    wordseed)      echo "--seed-file docs/hint/seed_words.py" ;;
    wordseed_pin)  echo "--seed-file docs/hint/seed_words.py --pin-seed" ;;
    famseed)       echo "--seed-file docs/hint/seed_family_poor.py" ;;
    famseed_pin)   echo "--seed-file docs/hint/seed_family_poor.py --pin-seed" ;;
    codehint)      echo "--hint-file docs/hint/hint_code_poor.txt" ;;
    codehint_g0)   echo "--hint-file docs/hint/hint_code_poor.txt --hint-gens 1" ;;
    famseed_words) echo "--seed-file docs/hint/seed_family_poor.py --hint \"\$STR\"" ;;
    selfseed)      echo "--seed-file docs/hint/seed_self_s11.py" ;;
    oracle)        echo "--seed-file docs/hint/seed_family_oracle.py" ;;
    *) log "unknown arm: $1"; exit 9 ;;
  esac
}
search() {  # $1 = arm ; $2 = rng seed ; $3 = gens ; $4 = samples ; $5 = out name
  OUTD="$R/$5"
  if [ -f "$OUTD.log" ] && grep -q "DONE best" "$OUTD.log"; then log "skip $5"; return; fi
  EXTRA=$(arm_flags "$1")
  eval CM_ALLOW_MULTI=1 "$PY" scripts/frontier_search.py --problem beatavg --oai-base "http://localhost:8000/v1" \
    --oai-model "$MODEL_ID" --max-tokens 1400 --temp 0.8 --gens "$3" --samples "$4" --islands 2 \
    --memory schema --novelty behavior --repel-prompt --seed "$2" $EXTRA --out "$OUTD" > "$OUTD.log" 2>&1
  log "$5: $(grep -E 'DONE best' "$OUTD.log" | tail -1)"
}

log "smoke"; search nohint 0 1 2 smoke_nohint
grep -qE "valid [1-9]" "$R/smoke_nohint.log" || {
  log "smoke without a valid program; ABORT. first response: $("$PY" -c "import json; r=[json.loads(l) for l in open('$R/smoke_nohint/history.jsonl')]; print(r[0].get('error'), '|', repr(r[0].get('raw', r[0].get('code','')))[:600])" 2>&1)"
  exit 8; }
[ "$MODE" = "smoke" ] && { log "CM-DONE smoke"; DONE_FLAG=1; touch "$BASE/CM-DONE"; exit 0; }

# full: seeds outer, arms inner (a partial battery stays balanced across arms); PAR searches in parallel.
# wait ONLY for the search jobs: a bare `wait` also waits for the watchdog subshell and stalled the battery after the
# first batch (2026-09-10, 4.5 h of idle GPU).
n=0; PIDS=""
for s in $SEEDS; do
  for arm in $ARMS; do
    EL=$(( ($(date +%s) - T0) / 3600 ))
    [ "$EL" -ge "$MAX_HOURS" ] && { log "hour cap ($MAX_HOURS h) reached; no more admissions"; [ -n "$PIDS" ] && wait $PIDS; log "CM-STOPPED"; DONE_FLAG=1; touch "$BASE/CM-STOPPED"; exit 0; }
    search "$arm" "$s" 10 6 "${arm}_s$s" & PIDS="$PIDS $!"; n=$((n+1)); [ $n -ge "$PAR" ] && { wait $PIDS; PIDS=""; n=0; }
  done
done
[ -n "$PIDS" ] && wait $PIDS
log "CM-DONE full ($(ls "$R" | grep -c '\.log$') logs; $(( ($(date +%s) - T0) / 60 )) min)"
DONE_FLAG=1; touch "$BASE/CM-DONE"
kill $WD 2>/dev/null
exit 0
