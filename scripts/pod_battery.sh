#!/bin/sh
# Run a battery on a RunPod GPU pod, end to end, with the anti-forget rule
# baked in: pod up = chain running; results rsynced back; pod ALWAYS removed
# on exit (trap) and --terminate-after set at creation as the last-resort guard.
#
#   sh scripts/pod_battery.sh smoke                 # ~US$0.10 pipeline check
#   sh scripts/pod_battery.sh 'cd /workspace/creative-machine && sh scripts/<battery>.sh'
#
# Env overrides: CM_GPU (default RTX 4090), CM_DC (EU-RO-1), CM_TTL_H (12),
# CM_WAIT_MIN (600). The remote command MUST print CM-DONE when finished.
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl
GPU="${CM_GPU:-NVIDIA GeForce RTX 4090}"
DC="${CM_DC:-EU-RO-1}"
TTL_H="${CM_TTL_H:-12}"
WAIT_MIN="${CM_WAIT_MIN:-600}"

CMD="${1:-}"
[ -z "$CMD" ] && { echo "usage: pod_battery.sh smoke|'<remote command>'"; exit 2; }
if [ "$CMD" = "smoke" ]; then
  CMD='cd /workspace/creative-machine && .pod-venv/bin/python scripts/torch_state.py --out runs/pod_smoke/none --op none --model Qwen/Qwen3-0.6B-Base --max-tokens 96 --habit && echo CM-DONE'
  CMD_SETUP_ONLY_SMALL=1
fi

$RP user >/dev/null 2>&1 || { echo "RUNPOD_API_KEY não resolvível (runpodctl user falhou)"; exit 3; }
$RP ssh list-keys 2>/dev/null | grep -q . || { echo "registrando chave SSH"; $RP ssh add-key || exit 3; }

VOL=$($RP network-volume list 2>/dev/null | awk '/cm-vol/ {print $1; exit}')
if [ -z "$VOL" ]; then
  echo "criando volume cm-vol (50GB, $DC)"
  $RP network-volume create --name cm-vol --size 50 --data-center-id "$DC" || exit 3
  VOL=$($RP network-volume list | awk '/cm-vol/ {print $1; exit}')
fi
echo "volume: $VOL"

TERM_AT=$(date -u -v+"${TTL_H}"H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "+${TTL_H} hours" +%Y-%m-%dT%H:%M:%SZ)
echo "criando pod ($GPU, $DC, terminate-after $TERM_AT)"
OUT=$($RP pod create --name cm-pod --template-id runpod-torch-v280 \
      --gpu-id "$GPU" --data-center-ids "$DC" \
      --network-volume-id "$VOL" --volume-mount-path /workspace \
      --ssh --terminate-after "$TERM_AT" 2>&1)
echo "$OUT"
POD=$(echo "$OUT" | grep -oE '[a-z0-9]{13,}' | head -1)
[ -z "$POD" ] && { echo "falha ao criar pod"; exit 4; }

cleanup() {
  echo "removendo pod $POD (anti-esquecimento)"
  $RP pod remove "$POD" 2>/dev/null
  $RP pod list 2>/dev/null | head -3
}
trap cleanup EXIT INT TERM

echo "aguardando runtime do pod $POD"
i=0
while :; do
  i=$((i+1))
  INFO=$($RP ssh info "$POD" 2>/dev/null)
  echo "$INFO" | grep -q '"ip"' && break
  [ $i -ge 40 ] && { echo "runtime nunca subiu (máquina ruim) — abortando"; exit 5; }
  sleep 15
done
IP=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["ip"])')
PORT=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["port"])')
KEY=$(echo "$INFO" | .venv/bin/python -c 'import sys,json;print(json.load(sys.stdin)["ssh_key"]["path"])')
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -p $PORT root@$IP"
echo "pod pronto: $IP:$PORT"

echo "sincronizando repo -> pod"
rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=no -p $PORT" \
  --exclude .venv --exclude runs --exclude '.git' --exclude paper --exclude paper2 --exclude paper3 \
  ./ root@"$IP":/workspace/creative-machine/ || exit 6

echo "preparando ambiente remoto"
$SSH 'cd /workspace/creative-machine && export HF_HOME=/workspace/hf-cache && \
      python3 -m venv --system-site-packages .pod-venv 2>/dev/null; \
      .pod-venv/bin/pip install -q --upgrade pip >/dev/null 2>&1; \
      .pod-venv/bin/pip install -q transformers accelerate numpy >/dev/null 2>&1; \
      .pod-venv/bin/pip install -q -e . >/dev/null 2>&1; echo SETUP-OK' || exit 6

echo "lançando cadeia (destacada)"
$SSH "cd /workspace/creative-machine && export HF_HOME=/workspace/hf-cache && \
      mkdir -p runs && setsid bash -c '$CMD' > runs/pod_chain.log 2>&1 </dev/null & echo LANÇADA"

echo "monitorando (timeout ${WAIT_MIN} min)"
t=0
while :; do
  sleep 60; t=$((t+1))
  TAIL=$($SSH 'tail -3 /workspace/creative-machine/runs/pod_chain.log 2>/dev/null')
  echo "[$t min] $(echo "$TAIL" | tail -1)"
  echo "$TAIL" | grep -q "CM-DONE" && { echo "cadeia concluída"; break; }
  [ $t -ge "$WAIT_MIN" ] && { echo "TIMEOUT — puxando o que houver"; break; }
done

echo "puxando resultados"
mkdir -p runs/pod
rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=no -p $PORT" \
  root@"$IP":/workspace/creative-machine/runs/ runs/pod/ || echo "rsync de volta falhou"
echo "POD-BATTERY DONE ($(date))"
