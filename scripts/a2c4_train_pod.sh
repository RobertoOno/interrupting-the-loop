#!/bin/sh
# A2 sem curador, iteration 2 (docs/A2_SEM_CURADOR_ITER2_V1.md) — phase 2 pod: one H200 with SSH; the replication's stack; the verified
# cumulative data (docs/a2c4_data: own.jsonl, curm.jsonl); data gate; two LoRA adapters with the consolidation recipe (108 steps, one
# seed); download; serve the BF16 base + the two adapters at the thinking context; runs/a2c4/vllm2_endpoint; hold until
# runs/a2c4/vllm2_stop or the cap; the trap removes the pod.
#   screen -dmS a2c4pod2 caffeinate -i -s sh scripts/a2c4_train_pod.sh        (log runs/a2c4/pod2.log; pod id runs/a2c4/pod2_id)
set -u
cd "$(dirname "$0")/.." || exit 1
RUNS=runs/a2c4; DATA=docs/a2c4_data; RP=runpodctl; mkdir -p "$RUNS"; LOG=$RUNS/pod2.log; EP=$RUNS/vllm2_endpoint; STOP=$RUNS/vllm2_stop; rm -f "$EP" "$STOP"
MODEL="${CM_A2C_MODEL:-Qwen/Qwen3.8-27B}"; GPU="${CM_GPU:-NVIDIA H200}"; DISK="${CM_DISK:-250}"; CAP_H="${CM_A2C_CAP_H:-14}"
IMAGE="${CM_A2C_IMAGE:-runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404}"; STEPS="${CM_A2C_STEPS:-108}"; SEED="${A2C4_SEED:-2026091502}"; REMOTE=/workspace/a2c4
MAXLEN="${CM_VLLM_MAXLEN:-163840}"; SEQS="${CM_VLLM_SEQS:-16}"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
[ -n "${RUNPOD_API_KEY:-}" ] || { say "RUNPOD_API_KEY não definido"; exit 3; }
GATE=$(.venv/bin/python -c "import json; s=json.load(open('$DATA/verification.json'))['summary']; m=json.load(open('$DATA/manifest.json')); print('ok' if s['checked']==s['ok'] and s['checked']>0 and m['gate_passed'] else 'FAIL %s/%s gate=%s' % (s['ok'], s['checked'], m['gate_passed']))" 2>/dev/null || echo "missing")
say "portão de dados: $GATE ($(.venv/bin/python -c "import json; m=json.load(open('$DATA/manifest.json')); print(m['counts'], 'novos', m['n_new'], m['yield_new'])" 2>/dev/null))"
[ "$GATE" = "ok" ] || { say "portão de dados não passou; nada alocado"; exit 10; }
say "criando pod $IMAGE em $GPU (disco ${DISK} GB, cap ${CAP_H}h)"
OUT=$($RP pod create --name "cm-a2c4-train" --image "$IMAGE" --gpu-id "$GPU" --container-disk-in-gb "$DISK" --ports "22/tcp,8000/http" --cloud-type SECURE --min-cuda-version "${CM_MIN_CUDA:-13.0}" --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { say "falha ao criar pod:"; echo "$OUT" | tail -5 | tee -a "$LOG"; exit 4; }
say "pod: $POD"; echo "$POD" > "$RUNS/pod2_id"; T0=$(date +%s)
cleanup() { say "removendo pod $POD"; $RP pod remove "$POD" >>"$LOG" 2>&1; $RP pod list 2>>"$LOG" | head -3 >>"$LOG"; rm -f "$EP"; }
trap cleanup EXIT INT TERM
INFO=$($RP ssh info "$POD" 2>>"$LOG"); KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; d=json.load(sys.stdin); print(d["ssh_key"]["path"])')
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["port"])')
SSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT root@$IP"
SCP="scp -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -P $PORT"
echo "$SSH" > "$RUNS/ssh2_cmd"
remote() { $SSH "$@" >>"$LOG" 2>&1; }
n=0; until $SSH "nvidia-smi -L" >>"$LOG" 2>&1 || [ $n -ge 30 ]; do sleep 20; n=$((n+1)); done
$SSH "nvidia-smi -L; nvidia-smi --query-gpu=driver_version --format=csv,noheader" >>"$LOG" 2>&1 || { say "ssh não respondeu"; exit 5; }
say "instalando vllm/transformers/peft"
remote "cd /workspace && export PIP_BREAK_SYSTEM_PACKAGES=1 && python -m pip install -q -U pip && python -m pip install -q -U vllm transformers peft accelerate huggingface_hub hf_transfer && python -c 'import vllm,transformers,peft,torch; print(vllm.__version__, transformers.__version__, peft.__version__, torch.__version__)'" || { say "pip falhou"; exit 6; }
say "versões: $(tail -1 "$LOG")"
remote "mkdir -p $REMOTE/data $REMOTE/adapters"
$SCP $DATA/own.jsonl $DATA/curm.jsonl $DATA/manifest.json root@$IP:$REMOTE/data/ >>"$LOG" 2>&1 && $SCP scripts/a2c_train.py root@$IP:$REMOTE/ >>"$LOG" 2>&1 || { say "cópia falhou"; exit 7; }
say "dados e script copiados"
for arm in own curm; do
  NAME=a2c4-${arm}2
  say "treinando $NAME ($STEPS passos, semente $SEED)"
  remote "cd $REMOTE && HF_HUB_ENABLE_HF_TRANSFER=1 python a2c_train.py --model $MODEL --data data/$arm.jsonl --out adapters/$NAME --steps $STEPS --seed $SEED 2>&1 | tail -6; test -f adapters/$NAME/manifest.json" || { say "treino $NAME falhou (ver $LOG)"; exit 8; }
  say "$NAME: $(tail -1 "$LOG" | cut -c1-160)"
  mkdir -p $RUNS/adapters && $SCP -r root@$IP:$REMOTE/adapters/$NAME $RUNS/adapters/ >>"$LOG" 2>&1 && say "adaptador $NAME baixado ($(du -sh $RUNS/adapters/$NAME | cut -f1))"
done
say "servindo base + 2 adaptadores (contexto $MAXLEN, $SEQS sequências)"
remote "cd $REMOTE && (nohup vllm serve $MODEL --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules a2c4-own2=$REMOTE/adapters/a2c4-own2 a2c4-curm2=$REMOTE/adapters/a2c4-curm2 --max-model-len $MAXLEN --max-num-seqs $SEQS --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > $REMOTE/vllm_serve.log 2>&1 &) ; sleep 5; echo started"
URL="https://$POD-8000.proxy.runpod.net"; n=0
until [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models" 2>/dev/null)" = "200" ] || [ $n -ge 90 ] || [ -f "$STOP" ]; do sleep 20; n=$((n+1)); done
[ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models")" = "200" ] || { say "servidor não subiu:"; $SSH "tail -30 $REMOTE/vllm_serve.log" | tee -a "$LOG" | tail -10; exit 12; }
say "pronto em $(( ($(date +%s) - T0) / 60 )) min: $(curl -s -m 15 "$URL/v1/models" | .venv/bin/python -c 'import sys,json; print([m["id"] for m in json.load(sys.stdin)["data"]])')"
echo "$URL/v1" > "$EP"; say "endpoint escrito em $EP; segurando até $STOP ou ${CAP_H}h"
while :; do
  [ -f "$STOP" ] && { say "stop file: encerrando"; break; }
  [ $(( ($(date +%s) - T0) / 3600 )) -ge "$CAP_H" ] && { say "cap de ${CAP_H}h: encerrando"; break; }
  sleep 60
done
say "horas de GPU: $(( ($(date +%s) - T0) / 60 )) min"
