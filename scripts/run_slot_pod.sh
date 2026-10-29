#!/bin/sh
# Programa 4 — Encaixe: the same idea in two slots (pre-registered PLANO 2026-09-09, before any generation).
# LAUNCHER (cockpit side). Provisions an H100 pod in the data center of a network volume, copies the tree, hands
# the account key to the pod's container disk (never the volume), starts scripts/slot_pod_driver.sh DETACHED and
# exits: from then on the pod runs the whole battery (server + searches + exact verifier), writes results on the
# volume and deletes itself at the end, on failure, or at the hour cap. The cockpit may be switched off.
#   sh scripts/run_slot_pod.sh launch [smoke|full]   # provision + hand over (default full)
#   sh scripts/run_slot_pod.sh attach <pod-id>       # tail the driver log while the cockpit is on
#   sh scripts/slot_fetch.sh                         # afterwards: copy the results from the volume to runs/slot
# Design, arms and flags: scripts/slot_pod_driver.sh (single source of the arm table).
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl
CMD="${1:-launch}"; MODE="${2:-full}"
VOL="${CM_VOLUME:-hgjkrmsmhl}"           # cm-qwen38-eu-fr-1-v1, 200 GB, EU-FR-1 (runpodctl network-volume list)
DC="${CM_DC:-EU-FR-1}"
GPU="${CM_GPU:-NVIDIA H100 80GB HBM3}"
BASE=/workspace/cm-slot
PYL="${CM_PY:-python3}"

if [ "$CMD" = "attach" ]; then
  POD="${2:?pod id}"; INFO=$($RP ssh info "$POD") || exit 2
  IP=$(echo "$INFO" | $PYL -c 'import sys,json;print(json.load(sys.stdin)["ip"])'); PORT=$(echo "$INFO" | $PYL -c 'import sys,json;print(json.load(sys.stdin)["port"])')
  KEY=$(echo "$INFO" | $PYL -c 'import sys,json;print(json.load(sys.stdin)["ssh_key"]["path"])')
  exec ssh -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" root@"$IP" "tail -n 40 -f $BASE/driver.log"
fi

$RP user >/dev/null 2>&1 || { echo "RUNPOD_API_KEY não resolvível"; exit 3; }
[ -n "${RUNPOD_API_KEY:-}" ] || [ -f "$HOME/.runpod/config.toml" ] || { echo "sem RUNPOD_API_KEY nem ~/.runpod/config.toml (a chave que o pod usa para se remover)"; exit 3; }
echo "criando pod ($GPU em $DC, volume $VOL) $(date)"
POD=""
for attempt in 1 2 3; do
  OUT=$($RP pod create --name cm-slot --template-id runpod-torch-v280 --gpu-id "$GPU" --container-disk-in-gb 150 \
        --network-volume-id "$VOL" --data-center-ids "$DC" --wait --wait-timeout 10m 2>&1)
  POD=$(echo "$OUT" | $PYL -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
  [ -n "$POD" ] && break
  echo "tentativa $attempt falhou: $(echo "$OUT" | tail -1 | cut -c1-200)"; sleep 60
done
[ -z "$POD" ] && { echo "sem capacidade em $DC; nada criado"; exit 4; }
echo "pod: $POD"
HANDED=""
cleanup() {  # only if the hand-over did not happen: never leave an orphan pod billing
  [ -n "$HANDED" ] && return
  echo "entrega não concluída: removendo o pod $POD"; $RP pod delete "$POD" 2>/dev/null; $RP pod list 2>/dev/null | head -3
}
trap cleanup EXIT INT TERM

i=0
while :; do
  i=$((i+1)); INFO=$($RP ssh info "$POD" 2>/dev/null)
  echo "$INFO" | grep -q '"ip"' && break
  [ $i -ge 40 ] && { echo "runtime nunca subiu"; exit 5; }
  sleep 15
done
IP=$(echo "$INFO" | $PYL -c 'import sys,json;print(json.load(sys.stdin)["ip"])')
PORT=$(echo "$INFO" | $PYL -c 'import sys,json;print(json.load(sys.stdin)["port"])')
KEY=$(echo "$INFO" | $PYL -c 'import sys,json;print(json.load(sys.stdin)["ssh_key"]["path"])')
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -p $PORT root@$IP"
echo "pod pronto: $IP:$PORT"
$SSH "mkdir -p $BASE/repo /root/.runpod && echo pod=\$RUNPOD_POD_ID dc=\$RUNPOD_DC_ID && df -h /workspace | tail -1" || exit 6

echo "copiando a árvore (scripts, src, docs/hint) e a chave (disco do contêiner)"
rsync -rltzR --delete -e "ssh -i $KEY -o StrictHostKeyChecking=no -p $PORT" scripts src docs/hint root@"$IP":$BASE/repo/ || exit 6
# the key the pod uses to delete itself: the one this shell authenticates with (RUNPOD_API_KEY), written over stdin —
# the Mac's ~/.runpod/config.toml carried a key the API rejected (2026-09-09/10)
if [ -n "${RUNPOD_API_KEY:-}" ]; then
  printf 'apikey = "%s"\napiurl = "https://api.runpod.io/graphql"\n' "$RUNPOD_API_KEY" | $SSH "cat > /root/.runpod/config.toml && chmod 600 /root/.runpod/config.toml" || exit 6
else
  scp -q -i "$KEY" -o StrictHostKeyChecking=no -P "$PORT" "$HOME/.runpod/config.toml" root@"$IP":/root/.runpod/config.toml || exit 6
fi
$SSH "curl -sSL https://cli.runpod.net | bash >/dev/null 2>&1; export PATH=/usr/local/bin:/root/.local/bin:\$PATH; runpodctl version 2>&1 | head -1; runpodctl user >/dev/null 2>&1 && echo 'chave ok no pod' || echo 'ERRO: a chave não autentica no pod (a auto-remoção falharia)'; ls $BASE/repo/docs/hint/seed_words.py $BASE/repo/scripts/frontier_search.py >/dev/null && echo 'árvore ok'" | tee /tmp/cm_slot_podcheck.txt
grep -q 'chave ok no pod' /tmp/cm_slot_podcheck.txt || { echo 'sem chave válida no pod: não entrego (o pod não conseguiria se remover)'; exit 6; }
$PYL - "$POD" "$DC" "$VOL" "$GPU" "$MODE" > /tmp/cm_slot_launch.json <<'EOF'
import json, subprocess, sys
from datetime import datetime, timezone
print(json.dumps({"pod": sys.argv[1], "dc": sys.argv[2], "volume": sys.argv[3], "gpu": sys.argv[4], "mode": sys.argv[5],
                  "commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
                  "launched_at": datetime.now(timezone.utc).isoformat()}, indent=1))
EOF
scp -q -i "$KEY" -o StrictHostKeyChecking=no -P "$PORT" /tmp/cm_slot_launch.json root@"$IP":$BASE/launch.json
# the driver is detached inside an inner shell with every fd redirected, so no remote process keeps the ssh channel
# open (a bare `cmd &` after `&&` backgrounds the whole and-list and its subshell holds the channel until the driver ends)
$SSH "cd $BASE/repo && rm -f $BASE/CM-DONE $BASE/CM-FAILED $BASE/CM-STOPPED; sh -c 'CM_MAX_HOURS=${CM_MAX_HOURS:-7} CM_PAR=${CM_PAR:-4} setsid nohup sh scripts/slot_pod_driver.sh $MODE > $BASE/driver.out 2>&1 < /dev/null &'; sleep 3; pgrep -f slot_pod_driver.sh >/dev/null && echo 'driver rodando'" | grep -q "driver rodando" || { echo "driver não iniciou"; exit 7; }
HANDED=1
echo "ENTREGUE ao pod $POD ($DC, $GPU, volume $VOL) $(date)"
echo "acompanhar (com o cockpit ligado): sh scripts/run_slot_pod.sh attach $POD"
echo "recolher depois (pod já removido): sh scripts/slot_fetch.sh"
