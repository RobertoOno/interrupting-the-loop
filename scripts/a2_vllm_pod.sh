#!/bin/sh
# A2: serve an open model with vLLM on a RunPod GPU (OpenAI-compatible API through the HTTP proxy, no SSH), hold the
# pod while a run uses it, and REMOVE it on exit, error, stop file or hard cap. Run inside screen with caffeinate:
#   screen -dmS a2vllm caffeinate -i -s sh scripts/a2_vllm_pod.sh          (log runs/a2/vllm_pod.log)
#   endpoint file: runs/a2/vllm_endpoint (written when /v1/models answers); stop: touch runs/a2/vllm_stop
# Env: CM_VLLM_MODEL (HF id), CM_VLLM_SERVED (served name), CM_VLLM_PARSER (tool-call parser), CM_GPU, CM_DISK, CM_VLLM_IMAGE,
#      CM_VLLM_CAP_H (hard cap hours, default 3), CM_VLLM_READY_MIN (readiness timeout, default 30), CM_COST_MAX ($/h)
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl; mkdir -p runs/a2; TAG="${CM_VLLM_TAG:-}"; LOG=runs/a2/vllm${TAG}_pod.log; EP=runs/a2/vllm${TAG}_endpoint; STOP=runs/a2/vllm${TAG}_stop; rm -f "$EP" "$STOP"
MODEL="${CM_VLLM_MODEL:-Qwen/Qwen3-Coder-30B-A3B-Instruct}"; SERVED="${CM_VLLM_SERVED:-qwen3-coder-30b}"; PARSER="${CM_VLLM_PARSER-qwen3_coder}"
GPU="${CM_GPU:-NVIDIA H100 80GB HBM3}"; DISK="${CM_DISK:-120}"; CAP_H="${CM_VLLM_CAP_H:-3}"; READY_MIN="${CM_VLLM_READY_MIN:-30}"; IMAGE="${CM_VLLM_IMAGE:-vllm/vllm-openai:latest}"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
[ -n "${RUNPOD_API_KEY:-}" ] || { say "RUNPOD_API_KEY não definido"; exit 3; }
TOOLS=""; [ -n "$PARSER" ] && TOOLS="--enable-auto-tool-choice --tool-call-parser $PARSER"   # CM_VLLM_PARSER="" for a prover served without tools
ARGS="--model $MODEL --served-model-name $SERVED $TOOLS --max-model-len ${CM_VLLM_MAXLEN:-32768} --gpu-memory-utilization 0.92 --port 8000 --host 0.0.0.0 ${CM_VLLM_EXTRA:-}"
say "criando pod vLLM: $MODEL em $GPU (cap ${CAP_H}h; imagem $IMAGE)"
OUT=$($RP pod create --name "cm-vllm${TAG}" --image "$IMAGE" --gpu-id "$GPU" --container-disk-in-gb "$DISK" --ports "8000/http" \
      --docker-args "$ARGS" --cloud-type SECURE 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { say "falha ao criar pod:"; echo "$OUT" | tail -5 | tee -a "$LOG"; exit 4; }
say "pod: $POD"
cleanup() { say "removendo pod $POD"; $RP pod remove "$POD" >>"$LOG" 2>&1; $RP pod list 2>>"$LOG" | head -3 >>"$LOG"; rm -f "$EP"; }
trap cleanup EXIT INT TERM
URL="https://$POD-8000.proxy.runpod.net"; T0=$(date +%s)
say "aguardando /v1/models em $URL (até ${READY_MIN} min)"
while :; do
  code=$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models" 2>/dev/null || echo 000)
  [ "$code" = "200" ] && break
  [ -f "$STOP" ] && { say "stop file durante a espera: encerrando"; exit 6; }
  [ $(( ($(date +%s) - T0) / 60 )) -ge "$READY_MIN" ] && { say "servidor não subiu em ${READY_MIN} min (último código $code)"; exit 5; }
  sleep 20
done
say "pronto em $(( ($(date +%s) - T0) / 60 )) min: $(curl -s -m 15 "$URL/v1/models" | head -c 300)"
echo "$URL/v1" > "$EP"
say "endpoint escrito em $EP; segurando o pod até $STOP ou ${CAP_H}h"
while :; do
  [ -f "$STOP" ] && { say "stop file: encerrando"; break; }
  [ $(( ($(date +%s) - T0) / 3600 )) -ge "$CAP_H" ] && { say "cap de ${CAP_H}h: encerrando"; break; }
  sleep 60
done
say "horas de GPU: $(( ($(date +%s) - T0) / 60 )) min"
