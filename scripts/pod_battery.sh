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
NOVOL="${CM_NOVOL:-}"
DISK="${CM_DISK:-40}"
EXTRA_PIP="${CM_EXTRA_PIP:-}"

CMD="${1:-}"
[ -z "$CMD" ] && { echo "usage: pod_battery.sh smoke|'<remote command>'"; exit 2; }
if [ "$CMD" = "smoke" ]; then
  CMD='cd /workspace/creative-machine && .pod-venv/bin/python scripts/torch_state.py --out runs/pod_smoke/none --op none --model Qwen/Qwen3-0.6B-Base --max-tokens 96 --habit && echo CM-DONE'
  CMD_SETUP_ONLY_SMALL=1
fi

$RP user >/dev/null 2>&1 || { echo "RUNPOD_API_KEY não resolvível (runpodctl user falhou)"; exit 3; }
if $RP ssh list-keys 2>/dev/null | grep -q '"keys": null'; then
  echo "registrando chave SSH"
  echo y | $RP ssh add-key || exit 3
fi

volid() { $RP network-volume list 2>/dev/null | .venv/bin/python -c \
  'import sys,json; vs=[v for v in json.load(sys.stdin) if v.get("name")=="cm-vol"]; print(vs[0]["id"] if vs else "")'; }
VOL=$(volid)
if [ -n "$NOVOL" ]; then VOL=""; echo "sem volume (CM_NOVOL)"; elif [ -z "$VOL" ]; then
  echo "criando volume cm-vol (50GB, $DC)"
  $RP network-volume create --name cm-vol --size 50 --data-center-id "$DC" || exit 3
  VOL=$(volid)
fi
echo "volume: $VOL"

# v2.12: no --terminate-after; the guards are the exit trap + the monitor timeout.
echo "criando pod ($GPU, $DC) e aguardando SSH (--wait)"
VOLFLAGS=""; [ -n "$VOL" ] && VOLFLAGS="--network-volume-id $VOL --volume-mount-path /workspace --data-center-ids $DC"
OUT=$($RP pod create --name cm-pod --template-id runpod-torch-v280 \
      --gpu-id "$GPU" --container-disk-in-gb "$DISK" $VOLFLAGS \
      --wait --wait-timeout 10m 2>&1)
POD=$(echo "$OUT" | .venv/bin/python -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
[ -z "$POD" ] && { echo "falha ao criar pod:"; echo "$OUT" | tail -5; exit 4; }
echo "pod: $POD"

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
rsync -rltz -e "ssh -i $KEY -o StrictHostKeyChecking=no -p $PORT" \
  --exclude .venv --exclude runs --exclude '.git' --exclude __pycache__ --exclude '*.egg-info' --exclude .pytest_cache --exclude paper --exclude paper2 --exclude paper3 \
  ./ root@"$IP":/workspace/creative-machine/ || exit 6

echo "preparando ambiente remoto"
$SSH 'cd /workspace/creative-machine && export HF_HOME=/workspace/hf-cache HF_HUB_DISABLE_XET=1 && \
      python3 -m venv --system-site-packages .pod-venv 2>/dev/null; \
      .pod-venv/bin/pip install -q --upgrade pip >/dev/null 2>&1; \
      .pod-venv/bin/pip install -q transformers accelerate numpy $EXTRA_PIP >/dev/null 2>&1; \
      .pod-venv/bin/pip install -q -e . >/dev/null 2>&1; echo SETUP-OK' || exit 6

echo "lançando cadeia (destacada)"
$SSH "cd /workspace/creative-machine && export HF_HOME=/workspace/hf-cache HF_HUB_DISABLE_XET=1 && \
      mkdir -p runs && setsid bash -c '$CMD' > runs/pod_chain.log 2>&1 </dev/null & echo LANÇADA"

echo "monitorando (timeout ${WAIT_MIN} min)"
t=0
while :; do
  sleep 60; t=$((t+1))
  TAIL=$($SSH 'tail -3 /workspace/creative-machine/runs/pod_chain.log 2>/dev/null')
  echo "[$t min] $(echo "$TAIL" | tail -1)"
  echo "$TAIL" | grep -qE "CM-DONE|CM-FAILED" && { echo "cadeia terminou: $(echo "$TAIL" | grep -oE 'CM-DONE|CM-FAILED.*')"; break; }
  [ $t -ge "$WAIT_MIN" ] && { echo "TIMEOUT — puxando o que houver"; break; }
done

echo "puxando resultados"
mkdir -p runs/pod
rsync -rltz -e "ssh -i $KEY -o StrictHostKeyChecking=no -p $PORT" \
  root@"$IP":/workspace/creative-machine/runs/ runs/pod/ || echo "rsync de volta falhou"
echo "POD-BATTERY DONE ($(date))"
