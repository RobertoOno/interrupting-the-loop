#!/bin/sh
# Battery R4 cells (response to the paper-4 review; pre-registered in PLANO
# 2026-09-01) — runs INSIDE a pod (launched via pod_battery.sh).
#   sh scripts/run_r4_pod.sh [smoke]
# One backend for every cell (Qwen3-8B-Base bf16, layer 18, 1500 tokens,
# RNG 0). R4b first: habit / pulseG20 / inter on 30 premises (pools n =
# confirmatory, o = original, g = expository). Then R4a: 8 extra arms on the
# confirmatory pool. Cell dirs runs/r4/<pool><i>_<arm>. Prints CM-DONE.
set -u
cd "$(dirname "$0")/.." || exit 1
MODE="${1:-full}"
PY=.pod-venv/bin/python
MODEL="${CM_MODEL:-Qwen/Qwen3-8B-Base}"
LAYER="${CM_LAYER:-18}"
R=runs/r4; NTOK=1500; NFAIL=0; CONSEC=0
P="--op pulse --habit --inject-every 300 --pulse-len 32"

flags() {
  case $1 in
    habit)      echo "--op none --habit" ;;
    inter)      echo "--op prompt --inject-rotate --habit --inject-every 300" ;;
    reset_inter) echo "--op prompt --inject-rotate --habit --inject-every 300 --reset-on-inject" ;;
    pulseG20)   echo "$P --alpha 2.0 --anchor --keep-norm" ;;
    sham_rand)  echo "$P --alpha 2.0 --anchor --keep-norm --pulse-source random" ;;
    sham_shuf)  echo "$P --alpha 2.0 --anchor --keep-norm --pulse-source shuffle" ;;
    pulse_u10)  echo "$P --alpha 1.0" ;;
    pulse_u15)  echo "$P --alpha 1.5" ;;
    pulse_u20)  echo "$P --alpha 2.0" ;;
    # same rotating directions, duty 100%: burst = period (the honest temporal law)
    cont_a1)    echo "--op pulse --habit --inject-every 300 --pulse-len 300 --alpha 1.0" ;;
    cont_a0107) echo "--op pulse --habit --inject-every 300 --pulse-len 300 --alpha 0.107" ;;
  esac
}

cell() {  # pool index arm
  out=$R/$1$2_$3
  [ -f "$out/run.json" ] && { echo "skip $1$2_$3"; return; }
  PREM=$($PY -c "import sys; sys.path.insert(0,'scripts'); from dream_battery2 import SEEDS, NEW_SEEDS, GENRE_SEEDS; print({'n': NEW_SEEDS, 'o': SEEDS, 'g': GENRE_SEEDS}['$1'][$2])")
  if $PY scripts/torch_state.py --out "$out" --model "$MODEL" --layer "$LAYER" \
       --seed-text "$PREM" --max-tokens "$NTOK" --rng-seed 0 $(flags "$3"); then
    CONSEC=0
  else
    echo "FAIL $1$2_$3"; NFAIL=$((NFAIL+1)); CONSEC=$((CONSEC+1))
  fi
  [ "$CONSEC" -ge 3 ] && { echo "CM-FAILED (abortado: $CONSEC consecutivas)"; exit 1; }
}

if [ "$MODE" = "smoke" ]; then
  NTOK=400; R=runs/r4_smoke
  for arm in sham_rand cont_a0107 reset_inter pulseG20; do cell n 0 $arm; done
elif [ "$MODE" = "r5" ]; then
  # review round 2, R5: the one-carrier temporal contrast on all 30 premises
  for pool in o g; do
    for i in 0 1 2 3 4 5 6 7 8 9; do
      for arm in cont_a1 cont_a0107 pulse_u10; do cell $pool $i $arm; done
    done
  done
else
  for pool in n o g; do
    for i in 0 1 2 3 4 5 6 7 8 9; do
      for arm in habit pulseG20 inter; do cell $pool $i $arm; done
    done
  done
  for i in 0 1 2 3 4 5 6 7 8 9; do
    for arm in sham_rand sham_shuf cont_a1 cont_a0107 reset_inter pulse_u10 pulse_u15 pulse_u20; do
      cell n $i $arm
    done
  done
fi
if [ "$NFAIL" -gt 0 ]; then echo "CM-FAILED ($NFAIL)"; else echo "CM-DONE"; fi
