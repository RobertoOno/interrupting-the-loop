#!/bin/sh
# A2 consolidation — one H200 pod with SSH for the whole GPU phase (docs/A2_CONSOLIDACAO_V1.md):
#   1 create pod (runpod/pytorch image, ports 22/tcp + 8000/http), wait for SSH; 2 install vllm/transformers/peft; 3 sync data +
#   train script; 4 SMOKE: 2-step LoRA on p1, then vllm with that adapter, one completion (not read); 5 wait for the local
#   verification of the training examples to be complete and all ok; 6 train the three adapters (108 steps each), download them;
#   7 serve BF16 + the three LoRA modules, write runs/a2c/vllm_endpoint, hold until runs/a2c/vllm_stop or the cap; trap removes the pod.
# Run inside screen with caffeinate: screen -dmS a2cpod caffeinate -i -s sh scripts/a2c_pod.sh   (log runs/a2c/pod.log)
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl; mkdir -p runs/a2c; LOG=runs/a2c/pod.log; EP=runs/a2c/vllm_endpoint; STOP=runs/a2c/vllm_stop; rm -f "$EP" "$STOP"
MODEL="${CM_A2C_MODEL:-Qwen/Qwen3.8-27B}"; GPU="${CM_GPU:-NVIDIA H200}"; DISK="${CM_DISK:-250}"; CAP_H="${CM_A2C_CAP_H:-10}"
IMAGE="${CM_A2C_IMAGE:-runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404}"; STEPS="${CM_A2C_STEPS:-108}"; REMOTE=/workspace/a2c
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
[ -n "${RUNPOD_API_KEY:-}" ] || { say "RUNPOD_API_KEY não definido"; exit 3; }
say "criando pod $IMAGE em $GPU (disco ${DISK} GB, cap ${CAP_H}h)"
OUT=$($RP pod create --name "cm-a2c" --image "$IMAGE" --gpu-id "$GPU" --container-disk-in-gb "$DISK" --ports "22/tcp,8000/http" --cloud-type SECURE --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { say "falha ao criar pod:"; echo "$OUT" | tail -5 | tee -a "$LOG"; exit 4; }
say "pod: $POD"; T0=$(date +%s)
cleanup() { say "removendo pod $POD"; $RP pod remove "$POD" >>"$LOG" 2>&1; $RP pod list 2>>"$LOG" | head -3 >>"$LOG"; rm -f "$EP"; }
trap cleanup EXIT INT TERM
INFO=$($RP ssh info "$POD" 2>>"$LOG"); KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; d=json.load(sys.stdin); print(d["ssh_key"]["path"])')
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["port"])')
SSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT root@$IP"
SCP="scp -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -P $PORT"
remote() { $SSH "$@" >>"$LOG" 2>&1; }
n=0; until $SSH "nvidia-smi -L" >>"$LOG" 2>&1 || [ $n -ge 30 ]; do sleep 20; n=$((n+1)); done
$SSH "nvidia-smi -L" >>"$LOG" 2>&1 || { say "ssh não respondeu"; exit 5; }
say "ssh ok: $(tail -1 "$LOG" | cut -c1-80)"
say "instalando vllm/transformers/peft (pode levar minutos)"
remote "cd /workspace && export PIP_BREAK_SYSTEM_PACKAGES=1 && python -m pip install -q -U pip && python -m pip install -q -U vllm transformers peft accelerate huggingface_hub hf_transfer && python -c 'import vllm,transformers,peft,torch; print(vllm.__version__, transformers.__version__, peft.__version__, torch.__version__)'" || { say "instalação falhou (ver $LOG)"; exit 6; }
say "versões: $(tail -1 "$LOG")"
remote "mkdir -p $REMOTE/data $REMOTE/adapters"
$SCP docs/a2c_data/p1.jsonl docs/a2c_data/p2.jsonl docs/a2c_data/p3.jsonl docs/a2c_data/manifest.json root@$IP:$REMOTE/data/ >>"$LOG" 2>&1 && $SCP scripts/a2c_train.py root@$IP:$REMOTE/ >>"$LOG" 2>&1 || { say "cópia falhou"; exit 7; }
say "dados e script copiados"
# --- smoke: 2-step LoRA on p1 (downloads the model), then vllm with the adapter, one completion
say "fumaça: treino de 2 passos"
remote "cd $REMOTE && HF_HUB_ENABLE_HF_TRANSFER=1 python a2c_train.py --model $MODEL --data data/p1.jsonl --out adapters/smoke --steps 2 2>&1 | tail -20" || { say "fumaça de treino falhou (ver $LOG)"; exit 8; }
say "fumaça: servindo com o adaptador"
remote "cd $REMOTE && (nohup vllm serve $MODEL --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules smoke=$REMOTE/adapters/smoke --max-model-len 32768 --max-num-seqs 64 --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > vllm_smoke.log 2>&1 &) ; sleep 5; echo started"
n=0; until $SSH "curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/v1/models" 2>/dev/null | grep -q 200 || [ $n -ge 60 ]; do sleep 20; n=$((n+1)); done
$SSH "curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/v1/models" 2>/dev/null | grep -q 200 || { say "vllm da fumaça não subiu:"; $SSH "tail -40 $REMOTE/vllm_smoke.log" | tee -a "$LOG" | tail -12; exit 9; }
$SSH "curl -s -m 300 http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\":\"smoke\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word OK.\"}],\"max_tokens\":32,\"chat_template_kwargs\":{\"enable_thinking\":false}}'" >>"$LOG" 2>&1
say "fumaça LoRA no vllm: $(tail -1 "$LOG" | cut -c1-200)"
remote "pkill -f 'vllm serve' ; sleep 8; nvidia-smi --query-gpu=memory.used --format=csv,noheader"
say "vllm da fumaça parado ($(tail -1 "$LOG"))"
# --- gate: every training example verified locally before training
say "aguardando a verificação local dos exemplos (docs/a2c_data/verification.json)"
n=0; until [ -f docs/a2c_data/verification.json ] || [ $n -ge 240 ]; do sleep 30; n=$((n+1)); done
GATE=$(.venv/bin/python -c "import json; s=json.load(open('docs/a2c_data/verification.json'))['summary']; print('ok' if s['checked']==s['ok'] and s['checked']>0 else 'FAIL %s/%s' % (s['ok'], s['checked']))" 2>/dev/null || echo "missing")
say "verificação dos exemplos: $GATE"
[ "$GATE" = "ok" ] || { say "portão de dados não passou; sem treino"; exit 10; }
# --- train the three adapters with identical steps
for arm in p1 p2 p3; do
  say "treinando a2c-$arm ($STEPS passos)"
  remote "cd $REMOTE && python a2c_train.py --model $MODEL --data data/$arm.jsonl --out adapters/a2c-$arm --steps $STEPS 2>&1 | tail -6" || { say "treino $arm falhou (ver $LOG)"; exit 11; }
  say "a2c-$arm: $(tail -1 "$LOG" | cut -c1-160)"
  mkdir -p runs/a2c/adapters && $SCP -r root@$IP:$REMOTE/adapters/a2c-$arm runs/a2c/adapters/ >>"$LOG" 2>&1 && say "adaptador a2c-$arm baixado ($(du -sh runs/a2c/adapters/a2c-$arm | cut -f1))"
done
# --- serve the base and the three adapters
say "servindo base + 3 adaptadores"
remote "cd $REMOTE && (nohup vllm serve $MODEL --served-model-name qwen3.8-27b --enable-lora --max-lora-rank 16 --max-loras 4 --lora-modules a2c-p1=$REMOTE/adapters/a2c-p1 a2c-p2=$REMOTE/adapters/a2c-p2 a2c-p3=$REMOTE/adapters/a2c-p3 --max-model-len 32768 --max-num-seqs 64 --reasoning-parser qwen3 --port 8000 --host 0.0.0.0 > vllm_serve.log 2>&1 &) ; sleep 5; echo started"
URL="https://$POD-8000.proxy.runpod.net"; n=0
until [ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models" 2>/dev/null)" = "200" ] || [ $n -ge 60 ]; do sleep 20; n=$((n+1)); done
[ "$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$URL/v1/models")" = "200" ] || { say "servidor final não subiu:"; $SSH "tail -30 $REMOTE/vllm_serve.log" | tee -a "$LOG" | tail -10; exit 12; }
say "pronto: $(curl -s -m 15 "$URL/v1/models" | head -c 300)"
echo "$URL/v1" > "$EP"; say "endpoint escrito em $EP; segurando até $STOP ou ${CAP_H}h"
while :; do
  [ -f "$STOP" ] && { say "stop file: encerrando"; break; }
  [ $(( ($(date +%s) - T0) / 3600 )) -ge "$CAP_H" ] && { say "cap de ${CAP_H}h: encerrando"; break; }
  sleep 60
done
$SCP root@$IP:$REMOTE/vllm_serve.log runs/a2c/vllm_serve.log >>"$LOG" 2>&1
say "horas de GPU: $(( ($(date +%s) - T0) / 60 )) min"
