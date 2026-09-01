#!/bin/sh
# RECORD-27B (pre-registered PLANO 2026-09-01): does the construction-family
# wall survive a current-generation proposer? E-arm beat-the-average, 600
# samples, proposer = Qwen3.8-27B served by vLLM on a roaming H100; the
# search + verifier run locally (light), generation goes over an SSH tunnel.
#   sh scripts/run_record27.sh smoke   # 8-sample pipeline check
#   sh scripts/run_record27.sh full    # the pre-registered E600
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl
MODE="${1:-smoke}"
MODEL_ID="Qwen/Qwen3.8-27B"
LPORT=18000

$RP user >/dev/null 2>&1 || { echo "RUNPOD_API_KEY não resolvível"; exit 3; }

echo "criando pod servidor (H100, roaming) $(date)"
OUT=$($RP pod create --name cm-serve --template-id runpod-torch-v280 \
      --gpu-id "NVIDIA H100 80GB HBM3" --container-disk-in-gb 150 \
      --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { echo "falha ao criar pod:"; echo "$OUT" | tail -3; exit 4; }
echo "pod: $POD"

TUN_PID=""
cleanup() {
  echo "encerrando: túnel + pod $POD"
  [ -n "$TUN_PID" ] && kill "$TUN_PID" 2>/dev/null
  $RP pod remove "$POD" 2>/dev/null
  $RP pod list 2>/dev/null | head -3
}
trap cleanup EXIT INT TERM

i=0
while :; do
  i=$((i+1)); INFO=$($RP ssh info "$POD" 2>/dev/null)
  echo "$INFO" | grep -q '"ip"' && break
  [ $i -ge 40 ] && { echo "runtime nunca subiu"; exit 5; }
  sleep 15
done
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["ip"])')
PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["port"])')
KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["ssh_key"]["path"])')
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -p $PORT root@$IP"
echo "pod pronto: $IP:$PORT"

echo "instalando vLLM (pode levar ~4 min)"
$SSH 'export HF_HOME=/workspace/hf-cache HF_HUB_DISABLE_XET=1 && \
      python3 -m venv --system-site-packages /workspace/.sv 2>/dev/null; \
      /workspace/.sv/bin/pip install -q --upgrade pip >/dev/null 2>&1; \
      /workspace/.sv/bin/pip install -q vllm ninja >/dev/null 2>&1; echo VLLM-OK' || exit 6

echo "subindo servidor (download ~55GB + carga; paciência)"
ssh -f -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" root@"$IP" \
  "export PATH=/workspace/.sv/bin:\$PATH HF_HOME=/workspace/hf-cache HF_HUB_DISABLE_XET=1 && \
   setsid /workspace/.sv/bin/python -m vllm.entrypoints.openai.api_server \
     --model $MODEL_ID --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.92 \
     > /workspace/vllm.log 2>&1 </dev/null" </dev/null

ssh -f -N -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" -L $LPORT:localhost:8000 root@"$IP" </dev/null
TUN_PID=$(pgrep -f "\-L $LPORT:localhost:8000" | head -1)
echo "túnel local :$LPORT (pid $TUN_PID)"

echo "aguardando servidor (até 30 min)"
i=0
while :; do
  i=$((i+1))
  curl -s --max-time 5 "http://localhost:$LPORT/v1/models" 2>/dev/null | grep -q "Qwen3.8" && { echo "SERVIDOR PRONTO"; break; }
  [ $((i % 20)) -eq 0 ] && $SSH 'tail -1 /workspace/vllm.log' 2>/dev/null
  [ $i -ge 120 ] && { echo "servidor nunca respondeu; vllm.log:"; $SSH 'tail -15 /workspace/vllm.log'; exit 7; }
  sleep 15
done

R=runs/frontier/record27; mkdir -p $R
if [ "$MODE" = "smoke" ]; then GENS=2; SPL=2; OUTD=$R/beatavg_E_smoke; else GENS=50; SPL=6; OUTD=$R/beatavg_E600; fi
echo "RECORD27 busca ($MODE: gens=$GENS spl=$SPL) $(date)"
.venv/bin/python scripts/frontier_search.py --problem beatavg --chat --max-tokens 1400 \
  --temp 0.8 --gens $GENS --samples $SPL --islands 2 \
  --memory schema --agenda --novelty behavior --repel-prompt \
  --oai-base "http://localhost:$LPORT/v1" --oai-model "$MODEL_ID" \
  --out $OUTD > $OUTD.log 2>&1
echo "busca terminou: $(grep -E 'DONE best' $OUTD.log | tail -1)"
echo "RECORD27 DONE ($MODE) $(date)"
