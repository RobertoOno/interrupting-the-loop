#!/bin/sh
# A2 sem curador, iteration 2 (docs/A2_SEM_CURADOR_ITER2_V1.md) — serve the BF16 base + the iteration-1 adapter a2c3-own with vLLM on
# one H200 (SSH pod, the same pip stack and serve flags as before: context 163840, 16 sequences, reasoning parser qwen3, LoRA enabled).
# Writes runs/a2c4/vllm_endpoint when /v1/models answers through the proxy; holds until runs/a2c4/vllm_stop or the cap; trap removes the pod.
#   screen -dmS a2c4pod caffeinate -i -s sh scripts/a2c4_serve_pod.sh        (log runs/a2c4/pod.log; pod id runs/a2c4/pod_id)
set -u
cd "$(dirname "$0")/.." || exit 1
RUNS=runs/a2c4; RP=runpodctl; mkdir -p "$RUNS"; LOG=$RUNS/pod.log; EP=$RUNS/vllm_endpoint; STOP=$RUNS/vllm_stop; rm -f "$EP" "$STOP"
ADAPTER="${A2C4_ADAPTER:-runs/a2c3/adapters/a2c3-own}"; ADNAME="${A2C4_ADAPTER_NAME:-a2c3-own}"
MODEL="${CM_A2C_MODEL:-Qwen/Qwen3.8-27B}"; GPU="${CM_GPU:-NVIDIA H200}"; DISK="${CM_DISK:-200}"; CAP_H="${CM_A2C_CAP_H:-14}"
IMAGE="${CM_A2C_IMAGE:-runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404}"; MAXLEN="${CM_VLLM_MAXLEN:-163840}"; SEQS="${CM_VLLM_SEQS:-16}"; REMOTE=/workspace/a2c4
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
[ -n "${RUNPOD_API_KEY:-}" ] || { say "RUNPOD_API_KEY não definido"; exit 3; }
[ -f "$ADAPTER/adapter_model.safetensors" ] || { say "adaptador $ADAPTER ausente"; exit 2; }
say "criando pod $IMAGE em $GPU (disco ${DISK} GB, cap ${CAP_H}h)"
OUT=$($RP pod create --name "cm-a2c4" --image "$IMAGE" --gpu-id "$GPU" --container-disk-in-gb "$DISK" --ports "22/tcp,8000/http" --cloud-type SECURE --min-cuda-version "${CM_MIN_CUDA:-13.0}" --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { say "falha ao criar pod:"; echo "$OUT" | tail -5 | tee -a "$LOG"; exit 4; }
say "pod: $POD"; echo "$POD" > "$RUNS/pod_id"; T0=$(date +%s)
cleanup() { say "removendo pod $POD"; $RP pod remove "$POD" >>"$LOG" 2>&1; $RP pod list 2>>"$LOG" | head -3 >>"$LOG"; rm -f "$EP"; }
trap cleanup EXIT INT TERM
INFO=$($RP ssh info "$POD" 2>>"$LOG"); KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; d=json.load(sys.stdin); print(d["ssh_key"]["path"])')
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["port"])')
SSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT root@$IP"
SCP="scp -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -P $PORT"
echo "$SSH" > "$RUNS/ssh_cmd"
remote() { $SSH "$@" >>"$LOG" 2>&1; }
n=0; until $SSH "nvidia-smi -L" >>"$LOG" 2>&1 || [ $n -ge 30 ]; do sleep 20; n=$((n+1)); done
$SSH "nvidia-smi -L; nvidia-smi --query-gpu=driver_version --format=csv,noheader" >>"$LOG" 2>&1 || { say "ssh não respondeu"; exit 5; }
say "instalando vllm"
remote "mkdir -p $REMOTE/adapters && cd $REMOTE && export PIP_BREAK_SYSTEM_PACKAGES=1 && python -m pip install -q -U pip && python -m pip install -q -U vllm hf_transfer && python -m pip show vllm transformers | grep -E '^(Name|Version)'" || { say "pip falhou"; exit 6; }
say "stack: $(tail -4 "$LOG" | tr '\n' ' ')"
$SCP -r "$ADAPTER" root@$IP:$REMOTE/adapters/ >>"$LOG" 2>&1 || { say "cópia do adaptador falhou"; exit 7; }
say "adaptador $ADNAME copiado ($(du -sh "$ADAPTER" | cut -f1))"
say "servindo a base + $ADNAME ($MODEL, contexto $MAXLEN, $SEQS sequências)"
remote "cd $REMOTE && (HF_HUB_ENABLE_HF_TRANSFER=1 nohup vllm serve $MODEL --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules $ADNAME=$REMOTE/adapters/$(basename "$ADAPTER") --max-model-len $MAXLEN --max-num-seqs $SEQS --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > $REMOTE/vllm_serve.log 2>&1 &) ; sleep 5; echo started"
URL="https://$POD-8000.proxy.runpod.net"; n=0
until [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models" 2>/dev/null)" = "200" ] || [ $n -ge 180 ] || [ -f "$STOP" ]; do sleep 20; n=$((n+1)); done
[ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models")" = "200" ] || { say "servidor não subiu:"; $SSH "tail -30 $REMOTE/vllm_serve.log" | tee -a "$LOG" | tail -10; exit 12; }
say "pronto em $(( ($(date +%s) - T0) / 60 )) min: $(curl -s -m 15 "$URL/v1/models" | .venv/bin/python -c 'import sys,json; print([m["id"] for m in json.load(sys.stdin)["data"]])')"
echo "$URL/v1" > "$EP"; say "endpoint escrito em $EP; segurando até $STOP ou ${CAP_H}h"
while :; do
  [ -f "$STOP" ] && { say "stop file: encerrando"; break; }
  [ $(( ($(date +%s) - T0) / 3600 )) -ge "$CAP_H" ] && { say "cap de ${CAP_H}h: encerrando"; break; }
  sleep 60
done
say "horas de GPU: $(( ($(date +%s) - T0) / 60 )) min"
