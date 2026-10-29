#!/bin/sh
# A8 curation-narrowing (docs/A8_CURADORIA_ESTREITA_V1.md) — serve the BF16 base + the adapters a2c4-own2 and a2c4-curm2 with vLLM on
# one H200 (SSH pod, the same pip stack and serve flags as before: context 163840, 16 sequences, reasoning parser qwen3, LoRA enabled).
# Writes runs/a8/vllm_endpoint when /v1/models answers through the proxy; holds until runs/a8/vllm_stop or the cap; trap removes the pod.
#   screen -dmS a8pod caffeinate -i -s sh scripts/a8_pod.sh      (log runs/a8/pod.log; pod id runs/a8/pod_id)
set -u
cd "$(dirname "$0")/.." || exit 1
RUNS=runs/a8; RP=runpodctl; mkdir -p "$RUNS"; LOG=$RUNS/pod.log; EP=$RUNS/vllm_endpoint; STOP=$RUNS/vllm_stop; rm -f "$EP" "$STOP"
ADAPTER="${A7_ADAPTER:-runs/a2c4/adapters/a2c4-own2}"; ADNAME="${A7_ADAPTER_NAME:-a2c4-own2}"; ADAPTER2="${A7_ADAPTER2:-runs/a2c4/adapters/a2c4-curm2}"; ADNAME2="${A7_ADAPTER2_NAME:-a2c4-curm2}"
MODEL="${CM_A2C_MODEL:-Qwen/Qwen3.8-27B}"; GPU="${CM_GPU:-NVIDIA H200}"; DISK="${CM_DISK:-200}"; CAP_H="${CM_A2C_CAP_H:-16}"
IMAGE="${CM_A2C_IMAGE:-runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404}"; MAXLEN="${CM_VLLM_MAXLEN:-163840}"; SEQS="${CM_VLLM_SEQS:-16}"; REMOTE=/workspace/a8
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
[ -n "${RUNPOD_API_KEY:-}" ] || { say "RUNPOD_API_KEY não definido"; exit 3; }
[ -f "$ADAPTER/adapter_model.safetensors" ] || { say "adaptador $ADAPTER ausente"; exit 2; }
[ -f "$ADAPTER2/adapter_model.safetensors" ] || { say "adaptador $ADAPTER2 ausente"; exit 2; }
say "criando pod $IMAGE em $GPU (disco ${DISK} GB, cap ${CAP_H}h)"
OUT=$($RP pod create --name "cm-a8" --image "$IMAGE" --gpu-id "$GPU" --container-disk-in-gb "$DISK" --ports "22/tcp,8000/http" --cloud-type SECURE --min-cuda-version "${CM_MIN_CUDA:-13.0}" --wait --wait-timeout 10m 2>&1)
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
# the adapters are ~300 MB each and the local link can drop mid-copy (18/09, twice): send them in 25 MB chunks, retrying each chunk,
# then reassemble on the pod and check the SHA-256 of the whole tarball before unpacking.
copy_adapter() {
  NAME=$(basename "$1"); TMP=$(mktemp -d)
  tar cf "$TMP/$NAME.tar" -C "$(dirname "$1")" "$NAME" || { say "tar de $NAME falhou"; rm -rf "$TMP"; return 1; }
  SUM=$(shasum -a 256 "$TMP/$NAME.tar" | cut -d' ' -f1)
  split -b 25m "$TMP/$NAME.tar" "$TMP/$NAME.part."
  NP=$(ls "$TMP/$NAME.part."* | wc -l | tr -d ' ')
  say "enviando $NAME em $NP pedaços (sha256 ${SUM%????????????????????????????????????????????????????????}...)"
  remote "mkdir -p $REMOTE/parts && rm -f $REMOTE/parts/$NAME.part.*"
  for f in "$TMP/$NAME.part."*; do
    n=0
    until $SCP "$f" root@$IP:$REMOTE/parts/ >>"$LOG" 2>&1; do
      n=$((n+1)); [ $n -ge 8 ] && { say "pedaço $(basename "$f") falhou em 8 tentativas"; rm -rf "$TMP"; return 1; }
      say "pedaço $(basename "$f") falhou (tentativa $n); repetindo em 15 s"; sleep 15
    done
  done
  remote "cd $REMOTE && cat parts/$NAME.part.* > $NAME.tar && echo '$SUM  $NAME.tar' | sha256sum -c - && tar xf $NAME.tar -C adapters/ && rm -rf parts $NAME.tar" \
    || { say "remontagem ou checksum de $NAME falhou"; rm -rf "$TMP"; return 1; }
  rm -rf "$TMP"; say "adaptador $NAME enviado em pedaços e conferido"
}
copy_adapter "$ADAPTER" || { say "envio do adaptador falhou"; exit 7; }
copy_adapter "$ADAPTER2" || { say "envio do adaptador 2 falhou"; exit 7; }
say "adaptador $ADNAME copiado ($(du -sh "$ADAPTER" | cut -f1))"
say "servindo a base + $ADNAME + $ADNAME2 ($MODEL, contexto $MAXLEN, $SEQS sequências)"
remote "cd $REMOTE && (HF_HUB_ENABLE_HF_TRANSFER=1 nohup vllm serve $MODEL --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules $ADNAME=$REMOTE/adapters/$(basename "$ADAPTER") $ADNAME2=$REMOTE/adapters/$(basename "$ADAPTER2") --max-model-len $MAXLEN --max-num-seqs $SEQS --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > $REMOTE/vllm_serve.log 2>&1 &) ; sleep 5; echo started"
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
