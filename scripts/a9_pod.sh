#!/bin/sh
# A8-c + A9 (docs/A8_CURADORIA_ESTREITA_V1.md E4; docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md) — ONE H200 pod for the whole window.
# Phase 1: same install command and serve flags as A8; serves the BF16 base + a2c4-own2 + a2c4-curm2 -> runs/a9/vllm_endpoint.
# Phase 2, when runs/a9/train_request appears: stop vLLM, train a9-own3 on docs/a9_data/own3.jsonl with the frozen consolidation recipe
#   (scripts/a2c_train.py, 108 steps, one seed; detached on the pod and polled, so a dropped link does not kill it), download the adapter
#   in 25 MB chunks with checksum, serve base + own2 + curm2 + a9-own3 -> runs/a9/vllm_endpoint2.
# Holds until runs/a9/vllm_stop or the cap; the trap removes the pod. A failed training writes runs/a9/train_failed and ends (pod removed).
#   screen -dmS a9pod caffeinate -i -s sh scripts/a9_pod.sh      (log runs/a9/pod.log; pod id runs/a9/pod_id)
set -u
cd "$(dirname "$0")/.." || exit 1
RUNS=runs/a9; RP=runpodctl; mkdir -p "$RUNS"; LOG=$RUNS/pod.log; EP=$RUNS/vllm_endpoint; EP2=$RUNS/vllm_endpoint2; STOP=$RUNS/vllm_stop; TREQ=$RUNS/train_request; TFAIL=$RUNS/train_failed
rm -f "$EP" "$EP2" "$STOP" "$TREQ" "$TFAIL"
AD1=runs/a2c4/adapters/a2c4-own2; AD2=runs/a2c4/adapters/a2c4-curm2; DATA=docs/a9_data; NEW=a9-own3
MODEL="${CM_A2C_MODEL:-Qwen/Qwen3.8-27B}"; GPU="${CM_GPU:-NVIDIA H200}"; DISK="${CM_DISK:-250}"; CAP_H="${CM_A9_CAP_H:-21}"
IMAGE="${CM_A2C_IMAGE:-runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404}"; MAXLEN="${CM_VLLM_MAXLEN:-163840}"; SEQS="${CM_VLLM_SEQS:-16}"; REMOTE=/workspace/a9
STEPS="${CM_A2C_STEPS:-108}"; SEED="${A9_SEED:-2026091901}"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
[ -n "${RUNPOD_API_KEY:-}" ] || { say "RUNPOD_API_KEY não definido"; exit 3; }
for a in "$AD1" "$AD2"; do [ -f "$a/adapter_model.safetensors" ] || { say "adaptador $a ausente"; exit 2; }; done
say "criando pod $IMAGE em $GPU (disco ${DISK} GB, cap ${CAP_H}h)"
OUT=$($RP pod create --name "cm-a9" --image "$IMAGE" --gpu-id "$GPU" --container-disk-in-gb "$DISK" --ports "22/tcp,8000/http" --cloud-type SECURE --min-cuda-version "${CM_MIN_CUDA:-13.0}" --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { say "falha ao criar pod:"; echo "$OUT" | tail -5 | tee -a "$LOG"; exit 4; }
say "pod: $POD"; echo "$POD" > "$RUNS/pod_id"; T0=$(date +%s)
cleanup() { say "removendo pod $POD"; $RP pod remove "$POD" >>"$LOG" 2>&1; $RP pod list 2>>"$LOG" | head -3 >>"$LOG"; rm -f "$EP" "$EP2"; }
trap cleanup EXIT INT TERM
INFO=$($RP ssh info "$POD" 2>>"$LOG"); KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; d=json.load(sys.stdin); print(d["ssh_key"]["path"])')
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["port"])')
SSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT root@$IP"
SCP="scp -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -P $PORT"
echo "$SSH" > "$RUNS/ssh_cmd"
remote() { $SSH "$@" >>"$LOG" 2>&1; }
remote_retry() { _n=0; until $SSH "$@" >>"$LOG" 2>&1; do _n=$((_n+1)); [ $_n -ge 6 ] && return 1; say "ssh falhou (tentativa $_n); repetindo em 20 s"; sleep 20; done; }
scp_retry() { _n=0; until $SCP "$@" >>"$LOG" 2>&1; do _n=$((_n+1)); [ $_n -ge 8 ] && return 1; say "scp falhou (tentativa $_n); repetindo em 15 s"; sleep 15; done; }
n=0; until $SSH "nvidia-smi -L" >>"$LOG" 2>&1 || [ $n -ge 30 ]; do sleep 20; n=$((n+1)); done
$SSH "nvidia-smi -L; nvidia-smi --query-gpu=driver_version --format=csv,noheader" >>"$LOG" 2>&1 || { say "ssh não respondeu"; exit 5; }
say "instalando vllm (mesmo comando do A8), depois peft/accelerate sem atualizar o resto"
remote "mkdir -p $REMOTE/adapters $REMOTE/data && cd $REMOTE && export PIP_BREAK_SYSTEM_PACKAGES=1 && python -m pip install -q -U pip && python -m pip install -q -U vllm hf_transfer && python -m pip install -q peft accelerate && python -c 'import vllm,transformers,peft,torch; print(\"versions\", vllm.__version__, transformers.__version__, peft.__version__, torch.__version__)'" || { say "pip falhou"; exit 6; }
say "stack: $(grep versions "$LOG" | tail -1)"
copy_adapter() {   # 25 MB chunks, per-chunk retries, SHA-256 of the whole tarball checked on the pod before unpacking
  NAME=$(basename "$1"); TMP=$(mktemp -d)
  tar cf "$TMP/$NAME.tar" -C "$(dirname "$1")" "$NAME" || { say "tar de $NAME falhou"; rm -rf "$TMP"; return 1; }
  SUM=$(shasum -a 256 "$TMP/$NAME.tar" | cut -d' ' -f1); split -b 25m "$TMP/$NAME.tar" "$TMP/$NAME.part."
  say "enviando $NAME em $(ls "$TMP/$NAME.part."* | wc -l | tr -d ' ') pedaços"
  remote_retry "mkdir -p $REMOTE/parts && rm -f $REMOTE/parts/$NAME.part.*" || { rm -rf "$TMP"; return 1; }
  for f in "$TMP/$NAME.part."*; do scp_retry "$f" root@$IP:$REMOTE/parts/ || { say "pedaço $(basename "$f") falhou em 8 tentativas"; rm -rf "$TMP"; return 1; }; done
  remote_retry "cd $REMOTE && cat parts/$NAME.part.* > $NAME.tar && echo '$SUM  $NAME.tar' | sha256sum -c - && tar xf $NAME.tar -C adapters/ && rm -rf parts $NAME.tar" \
    || { say "remontagem ou checksum de $NAME falhou"; rm -rf "$TMP"; return 1; }
  rm -rf "$TMP"; say "adaptador $NAME enviado em pedaços e conferido"
}
fetch_adapter() {  # pod -> local, the same way
  NAME=$1; DST=$RUNS/adapters; mkdir -p "$DST"; TMP=$(mktemp -d)
  remote_retry "cd $REMOTE && rm -rf dl && mkdir dl && tar cf $NAME.tar -C adapters $NAME && split -b 25m $NAME.tar dl/$NAME.part. && sha256sum $NAME.tar | cut -d' ' -f1 > $NAME.sha" || { rm -rf "$TMP"; return 1; }
  SUM=$($SSH "cat $REMOTE/$NAME.sha" 2>>"$LOG"); PARTS=$($SSH "ls $REMOTE/dl" 2>>"$LOG")
  [ -n "$SUM" ] && [ -n "$PARTS" ] || { rm -rf "$TMP"; return 1; }
  for p in $PARTS; do scp_retry root@$IP:$REMOTE/dl/$p "$TMP/" || { rm -rf "$TMP"; return 1; }; done
  cat "$TMP"/$NAME.part.* > "$TMP/$NAME.tar"
  [ "$(shasum -a 256 "$TMP/$NAME.tar" | cut -d' ' -f1)" = "$SUM" ] || { say "checksum do download de $NAME não confere"; rm -rf "$TMP"; return 1; }
  rm -rf "$DST/$NAME"; tar xf "$TMP/$NAME.tar" -C "$DST" && rm -rf "$TMP" && say "adaptador $NAME baixado e conferido ($(du -sh "$DST/$NAME" | cut -f1))"
}
URL="https://$POD-8000.proxy.runpod.net"
serve() {   # $1 = extra --lora-modules entries, $2 = log suffix
  # 19/09 fix: the first version guarded the start with `pgrep -f '[v]llm serve'`, which matched the remote shell's OWN command line (it
  # contained the literal "vllm serve ..." text) and therefore never started the server. The start now lives in a script on the pod and is
  # guarded by a flag file per phase, so nothing in this command line can match itself and a retried ssh cannot start it twice.
  remote_retry "cd $REMOTE && (test -f started_$2 || (touch started_$2; nohup sh start_vllm.sh $2 $1 > /dev/null 2>&1 &)); sleep 5; echo started"
  n=0; until [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models" 2>/dev/null)" = "200" ] || [ $n -ge 180 ] || [ -f "$STOP" ]; do sleep 20; n=$((n+1)); done
  [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models")" = "200" ] || { say "servidor não subiu:"; $SSH "tail -30 $REMOTE/vllm_serve_$2.log" | tee -a "$LOG" | tail -10; return 1; }
  say "servindo ($2) aos $(( ($(date +%s) - T0) / 60 )) min: $(curl -s -m 15 "$URL/v1/models" | .venv/bin/python -c 'import sys,json; print([m["id"] for m in json.load(sys.stdin)["data"]])')"
}
TS0=$(mktemp -d); printf '#!/bin/sh\n# $1 = log suffix, the rest = extra --lora-modules entries; same flags as A8\nSUF=$1; shift\ncd %s\nHF_HUB_ENABLE_HF_TRANSFER=1 exec vllm serve %s --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules a2c4-own2=%s/adapters/a2c4-own2 a2c4-curm2=%s/adapters/a2c4-curm2 "$@" --max-model-len %s --max-num-seqs %s --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > %s/vllm_serve_$SUF.log 2>&1\n' "$REMOTE" "$MODEL" "$REMOTE" "$REMOTE" "$MAXLEN" "$SEQS" "$REMOTE" > "$TS0/start_vllm.sh"
scp_retry "$TS0/start_vllm.sh" root@$IP:$REMOTE/ || { say "envio do script de partida falhou"; exit 7; }; rm -rf "$TS0"
copy_adapter "$AD1" || { say "envio do adaptador 1 falhou"; exit 7; }
copy_adapter "$AD2" || { say "envio do adaptador 2 falhou"; exit 7; }
say "fase 1: servindo a base + a2c4-own2 + a2c4-curm2 ($MODEL, contexto $MAXLEN, $SEQS sequências)"
serve "" phase1 || exit 12
echo "$URL/v1" > "$EP"; say "endpoint escrito em $EP; segurando até $TREQ, $STOP ou ${CAP_H}h"
TRAINED=0; FETCHED=0
while :; do
  [ -f "$STOP" ] && { say "stop file: encerrando"; break; }
  [ $(( ($(date +%s) - T0) / 3600 )) -ge "$CAP_H" ] && { say "cap de ${CAP_H}h: encerrando"; break; }
  if [ -f "$TREQ" ] && [ $TRAINED -eq 0 ]; then
    TRAINED=1; rm -f "$EP"; say "fase 2: pedido de treino visto; parando o vLLM"
    [ -f "$DATA/own3.jsonl" ] && [ -f "$DATA/manifest.json" ] || { say "dados de treino ausentes"; touch "$TFAIL"; exit 9; }
    remote_retry "pkill -f '[v]llm serve'; sleep 8; for p in \$(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do kill -9 \$p 2>/dev/null; done; sleep 6; nvidia-smi --query-gpu=memory.used --format=csv,noheader"
    n=0; until [ "$($SSH "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits" 2>/dev/null | head -1 | tr -d ' ')" -lt 4000 ] 2>/dev/null || [ $n -ge 30 ]; do sleep 10; n=$((n+1)); done
    TS=$(mktemp -d); printf '#!/bin/sh\ncd %s\nHF_HUB_ENABLE_HF_TRANSFER=1 python a2c_train.py --model %s --data data/own3.jsonl --out adapters/%s --steps %s --seed %s > train_own3.log 2>&1\necho $? > train_own3.rc\n' "$REMOTE" "$MODEL" "$NEW" "$STEPS" "$SEED" > "$TS/train_own3.sh"
    scp_retry "$DATA/own3.jsonl" "$DATA/manifest.json" root@$IP:$REMOTE/data/ && scp_retry scripts/a2c_train.py "$TS/train_own3.sh" root@$IP:$REMOTE/ || { say "cópia dos dados falhou"; touch "$TFAIL"; exit 7; }
    rm -rf "$TS"; say "treinando $NEW ($STEPS passos, semente $SEED; $(wc -l < "$DATA/own3.jsonl" | tr -d ' ') exemplos), destacado no pod"
    remote_retry "cd $REMOTE && (test -f train_own3.started || (touch train_own3.started; nohup sh train_own3.sh > /dev/null 2>&1 &)); sleep 2; echo started"
    n=0; RC=""
    until RC=$($SSH "cat $REMOTE/train_own3.rc" 2>/dev/null) && [ -n "$RC" ]; do
      n=$((n+1)); [ $n -ge 150 ] && break
      [ $((n % 5)) -eq 0 ] && say "treino: $($SSH "tail -c 200 $REMOTE/train_own3.log" 2>/dev/null | tr '\n\r' '  ' | cut -c1-160)"
      sleep 60
    done
    [ "$RC" = "0" ] && $SSH "test -f $REMOTE/adapters/$NEW/manifest.json" 2>>"$LOG" || { say "treino falhou (rc='$RC'): $($SSH "tail -5 $REMOTE/train_own3.log" 2>/dev/null | tr '\n' ' ' | cut -c1-300)"; touch "$TFAIL"; exit 8; }
    say "$NEW treinado: $($SSH "tail -2 $REMOTE/train_own3.log" 2>/dev/null | tr '\n' ' ' | cut -c1-200)"
    fetch_adapter "$NEW" && FETCHED=1 || say "WARNING: download do adaptador falhou agora; nova tentativa antes de remover o pod"
    say "fase 3: servindo a base + own2 + curm2 + $NEW"
    serve "$NEW=$REMOTE/adapters/$NEW" phase3 || { touch "$TFAIL"; exit 12; }
    echo "$URL/v1" > "$EP2"; say "endpoint 2 escrito em $EP2"
  fi
  sleep 30
done
[ $TRAINED -eq 1 ] && [ $FETCHED -eq 0 ] && { fetch_adapter "$NEW" || say "WARNING: adaptador $NEW NÃO foi baixado"; }
say "horas de GPU: $(( ($(date +%s) - T0) / 60 )) min"
