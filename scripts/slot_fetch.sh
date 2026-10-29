#!/bin/sh
# Programa 4 — Encaixe: fetch the battery results from the network volume after the pod has deleted itself.
# Creates the cheapest pod that can mount the volume in its data center, rsyncs /workspace/cm-slot to runs/slot_volume,
# and deletes the pod (trap). Then: python scripts/analysis_slot.py --runs runs/slot_volume/runs/slot
#   sh scripts/slot_fetch.sh            # GPU pod (CM_GPU, default RTX A4000-class) — CPU pods may not mount volumes in every DC
set -u
cd "$(dirname "$0")/.." || exit 1
RP=runpodctl
VOL="${CM_VOLUME:-hgjkrmsmhl}"; DC="${CM_DC:-EU-FR-1}"; GPU="${CM_GPU:-NVIDIA H100 80GB HBM3}"
DEST="${CM_DEST:-runs/slot_volume}"; PYL="${CM_PY:-python3}"
mkdir -p "$DEST"
$RP pod list 2>/dev/null | grep -q '"cm-slot"' && { echo "AVISO: um pod cm-slot ainda existe (a bateria pode estar rodando); veja runpodctl pod list"; }
POD=""
for KIND in cpu gpu; do
  if [ "$KIND" = "cpu" ]; then
    echo "criando pod de recolha (CPU em $DC) $(date)"
    OUT=$($RP pod create --name cm-slot-fetch --compute-type cpu --template-id runpod-torch-v280 --container-disk-in-gb 20 \
          --network-volume-id "$VOL" --data-center-ids "$DC" --wait --wait-timeout 5m 2>&1)
  else
    echo "criando pod de recolha ($GPU em $DC) $(date)"
    OUT=$($RP pod create --name cm-slot-fetch --template-id runpod-torch-v280 --gpu-id "$GPU" --container-disk-in-gb 20 \
          --network-volume-id "$VOL" --data-center-ids "$DC" --wait --wait-timeout 5m 2>&1)
  fi
  POD=$(echo "$OUT" | $PYL -c 'import sys,re; m=re.search(r"\"id\":\s*\"([a-z0-9]+)\"", sys.stdin.read()); print(m.group(1) if m else "")')
  [ -n "$POD" ] && break
  echo "  falhou ($KIND): $(echo "$OUT" | tail -1 | cut -c1-200)"
done
[ -z "$POD" ] && { echo "falha ao criar pod de recolha"; exit 4; }
cleanup() { echo "removendo pod de recolha $POD"; $RP pod delete "$POD" 2>/dev/null; $RP pod list 2>/dev/null | head -3; }
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
ssh -i "$KEY" -o StrictHostKeyChecking=no -p "$PORT" root@"$IP" "ls -la /workspace/cm-slot; cat /workspace/cm-slot/driver.log | tail -5" || exit 6
rsync -rltz --exclude repo -e "ssh -i $KEY -o StrictHostKeyChecking=no -p $PORT" root@"$IP":/workspace/cm-slot/ "$DEST/" || exit 6
echo "recolhido em $DEST: $(ls "$DEST/runs/slot" 2>/dev/null | grep -c '\.log$') logs; marcadores: $(ls "$DEST" | grep -E '^CM-' | tr '\n' ' ')"
