#!/bin/sh
# Programa 2, stage 2 (pre-registered PLANO 2026-09-03): verified search from the
# stage-1 transplants as seed programs. Proposer = Qwen3-30B-A3B-Base served by vLLM on a
# roaming H100 (raw /completions, no chat template); the search + exact verifier run
# on the cockpit (light: seconds of CPU per candidate, generation over an SSH tunnel).
#   sh scripts/run_p2_stage2.sh smoke   # 1 run x 4 samples, pod removed after
#   sh scripts/run_p2_stage2.sh full    # smoke gate, then all seeds x 3 rng, 100 samples each, 3 runs in parallel
# Seeds: runs/p2/stage1_seeds/<arm>/<k>.py (scripts/p2_pick_seeds.py, after the single read of stage 1).
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl
MODE="${1:-smoke}"
MODEL_ID="Qwen/Qwen3-30B-A3B-Base"
LPORT=18000
SEEDS_DIR="${CM_SEEDS:-runs/p2/stage1_seeds}"
R=runs/p2/stage2; mkdir -p $R

$RP user >/dev/null 2>&1 || { echo "RUNPOD_API_KEY não resolvível"; exit 3; }
echo "criando pod servidor (H100, roaming) $(date)"
OUT=$($RP pod create --name cm-serve-p2 --template-id runpod-torch-v280 \
      --gpu-id "NVIDIA H100 80GB HBM3" --container-disk-in-gb 150 \
      --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { echo "falha ao criar pod:"; echo "$OUT" | tail -3; exit 4; }
echo "pod: $POD"
TUN_PID=""
cleanup() {
  echo "encerrando: túnel + pod $POD $(date)"
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
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -p $PORT root@$IP"
echo "pod pronto: $IP:$PORT"

echo "instalando vLLM (destacado no pod)"
$SSH 'python3 -m venv --system-site-packages /workspace/.sv 2>/dev/null; \
      nohup sh -c "/workspace/.sv/bin/pip install -q --upgrade pip; /workspace/.sv/bin/pip install -q vllm ninja flashinfer-python; echo VLLM-OK" \
        > /workspace/install.log 2>&1 </dev/null &' || exit 6
i=0
while :; do
  i=$((i+1))
  $SSH 'tail -1 /workspace/install.log' 2>/dev/null | grep -q VLLM-OK && { echo "vLLM instalado"; break; }
  [ $i -ge 60 ] && { echo "instalação nunca terminou"; $SSH 'tail -5 /workspace/install.log'; exit 6; }
  sleep 20
done

echo "subindo servidor ($MODEL_ID, bf16 ~61 GB; download + carga)"
ssh -f -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" root@"$IP" \
  "export PATH=/workspace/.sv/bin:\$PATH HF_HOME=/workspace/hf-cache HF_HUB_DISABLE_XET=1 VLLM_ATTENTION_BACKEND=FLASHINFER && \
   setsid /workspace/.sv/bin/python -m vllm.entrypoints.openai.api_server \
     --model $MODEL_ID --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.92 --max-num-seqs 64 \
     > /workspace/vllm.log 2>&1 </dev/null" </dev/null
ssh -f -N -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" -L $LPORT:localhost:8000 root@"$IP" </dev/null
TUN_PID=$(pgrep -f "\-L $LPORT:localhost:8000" | head -1)
echo "túnel local :$LPORT (pid $TUN_PID)"
echo "aguardando servidor (até 30 min)"
i=0
while :; do
  i=$((i+1))
  curl -s --max-time 5 "http://localhost:$LPORT/v1/models" 2>/dev/null | grep -q "Qwen3-30B" && { echo "SERVIDOR PRONTO $(date)"; break; }
  [ $((i % 20)) -eq 0 ] && $SSH 'tail -1 /workspace/vllm.log' 2>/dev/null
  [ $i -ge 120 ] && { echo "servidor nunca respondeu"; scp -i "$KEY" -o StrictHostKeyChecking=no -P "$PORT" root@"$IP":/workspace/vllm.log runs/p2/vllm_fail.log 2>/dev/null; exit 7; }
  sleep 15
done

search() {  # $1 = out name ; $2 = rng seed ; $3 = seed file or none ; $4 = gens ; $5 = samples
  OUTD=$R/$1; [ -f "$OUTD/state.json" ] && { echo "skip $1"; return; }
  .venv/bin/python scripts/frontier_search.py --problem sumdiff3 --oai-base "http://localhost:$LPORT/v1" --oai-completions \
    --oai-model "$MODEL_ID" --gens "$4" --samples "$5" --islands 2 --max-tokens 700 --temp 1.0 --min-p 0.05 \
    --seed "$2" --seed-file "$3" --out "$OUTD" > "$OUTD.log" 2>&1
  echo "$1: $(grep -E 'DONE best' "$OUTD.log" | tail -1) $(date)"
}
echo "fumaça $(date)"; search smoke_A 0 none 2 2
grep -qE "valid [1-9]" $R/smoke_A.log || { echo "fumaça sem programa válido; ABORTADO. Primeira resposta:"; \
  .venv/bin/python -c "import json; r=[json.loads(l) for l in open('$R/smoke_A/history.jsonl')]; print(r[0].get('error'), '|', repr(r[0].get('raw', r[0].get('code','')))[:1200])"; exit 8; }
[ "$MODE" = "smoke" ] && { echo "CM-DONE smoke"; exit 0; }

# full: arm A (no seed) x 3 rng, then every picked seed x 3 rng; 3 searches in parallel
n=0
for s in 0 1 2; do search "A_s$s" $s none 25 4 & n=$((n+1)); [ $n -ge 3 ] && { wait; n=0; }; done
for d in "$SEEDS_DIR"/*/; do
  arm=$(basename "$d")
  for f in "$d"*.py; do
    k=$(basename "$f" .py)
    for s in 0 1 2; do
      search "${arm}_k${k}_s$s" $s "$f" 25 4 & n=$((n+1)); [ $n -ge 3 ] && { wait; n=0; }
    done
  done
done
wait
echo "CM-DONE full $(date)"
