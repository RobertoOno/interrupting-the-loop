#!/bin/sh
# Degrau 2 — open-model contrast: H100 pod serving Qwen3.8-27B with vLLM (32k context), generation over an SSH tunnel,
# Lean verification on this machine. Smoke gate (one oracle recipient must yield a parseable submission), then the sweep.
#   sh scripts/run_p3_open_pod.sh smoke|full|resume   (resume: no smoke, context 64k, retries infrastructure failures)
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl; MODE="${1:-smoke}"; MODEL_ID="Qwen/Qwen3.8-27B"; LPORT=18000
PY=/Users/robertoonofilho/wrk/creative-machine/.venv/bin/python; export PYTHONPATH=src
$RP user >/dev/null 2>&1 || { echo "RUNPOD_API_KEY não resolvível"; exit 3; }
echo "criando pod servidor (H100) $(date)"
OUT=$($RP pod create --name cm-open-p3 --template-id runpod-torch-v280 --gpu-id "NVIDIA H100 80GB HBM3" --container-disk-in-gb 150 --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { echo "falha ao criar pod:"; echo "$OUT" | tail -3; exit 4; }
echo "pod: $POD"; TUN_PID=""
cleanup() { echo "encerrando: túnel + pod $POD $(date)"; [ -n "$TUN_PID" ] && kill "$TUN_PID" 2>/dev/null; $RP pod remove "$POD" 2>/dev/null; $RP pod list 2>/dev/null | head -3; }
trap cleanup EXIT INT TERM
i=0; while :; do i=$((i+1)); INFO=$($RP ssh info "$POD" 2>/dev/null); echo "$INFO" | grep -q '"ip"' && break; [ $i -ge 40 ] && { echo "runtime nunca subiu"; exit 5; }; sleep 15; done
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["port"])'); KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["ssh_key"]["path"])')
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -p $PORT root@$IP"
echo "pod pronto: $IP:$PORT"
$SSH 'python3 -m venv --system-site-packages /workspace/.sv 2>/dev/null; nohup sh -c "/workspace/.sv/bin/pip install -q --upgrade pip; /workspace/.sv/bin/pip install -q vllm ninja flashinfer-python; echo VLLM-OK" > /workspace/install.log 2>&1 </dev/null &' || exit 6
i=0; while :; do i=$((i+1)); $SSH 'tail -1 /workspace/install.log' 2>/dev/null | grep -q VLLM-OK && { echo "vLLM instalado"; break; }; [ $i -ge 60 ] && { echo "instalação nunca terminou"; exit 6; }; sleep 20; done
ssh -f -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" root@"$IP" "export PATH=/workspace/.sv/bin:\$PATH HF_HOME=/workspace/hf-cache HF_HUB_DISABLE_XET=1 VLLM_ATTENTION_BACKEND=FLASHINFER && setsid /workspace/.sv/bin/python -m vllm.entrypoints.openai.api_server --model $MODEL_ID --port 8000 --max-model-len 65536 --gpu-memory-utilization 0.92 --max-num-seqs 8 > /workspace/vllm.log 2>&1 </dev/null" </dev/null
ssh -f -N -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" -L $LPORT:localhost:8000 root@"$IP" </dev/null
TUN_PID=$(pgrep -f "\-L $LPORT:localhost:8000" | head -1); echo "túnel local :$LPORT (pid $TUN_PID)"
i=0; while :; do i=$((i+1)); curl -s --max-time 5 "http://localhost:$LPORT/v1/models" 2>/dev/null | grep -q "Qwen3.8" && { echo "SERVIDOR PRONTO $(date)"; break; }; [ $((i % 20)) -eq 0 ] && $SSH 'tail -1 /workspace/vllm.log' 2>/dev/null; [ $i -ge 120 ] && { echo "servidor nunca respondeu"; exit 7; }; sleep 15; done
R=runs/p3/open_contrast_v1; mkdir -p $R
if [ "$MODE" = "resume" ]; then
  echo "retomada (sem fumaça; readmitindo falhas de infraestrutura) $(date)"
  $PY scripts/p3_open_contrast.py --workers 3 --context 65536 --retry-infrastructure > $R/sweep_resume.log 2>&1; tail -3 $R/sweep_resume.log
  echo "CM-DONE resume $(date)"; exit 0
fi
SMOKE=$($PY -c "
import json,sys; sys.path.insert(0,'scripts'); import p3_open_contrast as m
c=[c for c in m.plan() if c['role']=='recipient' and c['condition']=='oracle_bridge' and c['budget']==4096 and not c['thinking']][0]; print(c['cell_id'])")
echo "fumaça: célula $SMOKE $(date)"; $PY scripts/p3_open_contrast.py --only "$SMOKE" --workers 1 > $R/smoke.log 2>&1; tail -2 $R/smoke.log
grep -q '"turns": [1-9]' $R/smoke.log || { echo "fumaça sem submissão parseável; ABORTADO"; exit 8; }
[ "$MODE" = "smoke" ] && { echo "CM-DONE smoke"; exit 0; }
echo "varredura completa $(date)"; $PY scripts/p3_open_contrast.py --workers 4 > $R/sweep.log 2>&1; tail -3 $R/sweep.log
echo "CM-DONE full $(date)"
