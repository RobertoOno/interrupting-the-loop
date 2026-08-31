#!/bin/sh
# Battery GEN cells — runs INSIDE a pod (launched via pod_battery.sh).
#   sh scripts/run_gen_pod.sh <tag> <hf-model-id> <layer> [smoke]
# 3 arms (habit / pulseG alpha 2.0 guarded / inter) x the 10 confirmatory
# premises, 1500 tokens, RNG 0 — the H1 parity trio on a new model.
# smoke mode: 1 premise x 2 arms x 120 tokens. Prints CM-DONE at the end.
set -u
cd "$(dirname "$0")/.." || exit 1
TAG="$1"; MODEL="$2"; LAYER="$3"; MODE="${4:-full}"
PY=.pod-venv/bin/python
R=runs/gen_$TAG
NPREM=10; NTOK=1500; ARMS="habit pulse inter"; NFAIL=0; CONSEC=0
[ "$MODE" = "smoke" ] && { NPREM=1; NTOK=120; ARMS="habit pulse"; }

for i in $(seq 0 $((NPREM - 1))); do
  for arm in $ARMS; do
    out=$R/p${i}_${arm}
    [ -f "$out/run.json" ] && { echo "skip p${i}_${arm}"; continue; }
    case $arm in
      habit) FLAGS="--op none --habit" ;;
      pulse) FLAGS="--op pulse --alpha 2.0 --anchor --keep-norm --habit --inject-every 300 --pulse-len 32" ;;
      inter) FLAGS="--op prompt --inject-rotate --habit --inject-every 300" ;;
    esac
    # the 10 confirmatory premises live in dream_battery2.NEW_SEEDS; index via env
    PREM=$($PY -c "import sys; sys.path.insert(0,'scripts'); from dream_battery2 import NEW_SEEDS; print(NEW_SEEDS[$i])")
    $PY scripts/torch_state.py --out "$out" --model "$MODEL" --layer "$LAYER" \
        --seed-text "$PREM" --max-tokens "$NTOK" --rng-seed 0 $FLAGS && CONSEC=0 || { echo "FAIL p${i}_${arm}"; NFAIL=$((NFAIL+1)); CONSEC=$((CONSEC+1)); }
    [ "$CONSEC" -ge 3 ] && { echo "CM-FAILED (abortado: $CONSEC consecutivas)"; exit 1; }
  done
done
if [ "$NFAIL" -gt 0 ]; then echo "CM-FAILED ($NFAIL)"; else echo "CM-DONE"; fi
