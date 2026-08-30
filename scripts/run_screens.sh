#!/bin/sh
# Exploratory screens (PLANO 2026-08-30 afternoon): rotor angle sweep and
# H4 stress regime (continuous repulsion). Cheap-metric read only, no judges.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; R=runs/state_screen; mkdir -p $R

run() { out=$R/$1; shift
  [ -f "$out/run.json" ] && { echo "skip $(basename $out)"; return; }
  caffeinate -is $PY scripts/state_inject.py --out $out \
      --max-tokens 1500 --temp 1.0 --top-p 0.95 --rng-seed 0 --habit "$@" \
      || echo "FAIL $(basename $out)"
}

echo "SCREENS START $(date)"
for p in 0 1 2; do
  for th in 1.2 1.6 2.4; do                                  # rotor angle sweep (pulsed, norm shell)
    run rot_p${p}_t${th} --seed-index $p --op pulse --pulse-op rotate --layer 18 \
        --alpha $th --keep-norm --inject-every 300 --pulse-len 32
  done
  for al in 1.5 3.0; do                                       # H4 stress: CONTINUOUS repulsion
    run repN_p${p}_a${al} --seed-index $p --op repel --layer 18 --alpha $al
    run repA_p${p}_a${al} --seed-index $p --op repel --layer 18 --alpha $al --anchor
  done
done
echo "SCREENS DONE $(date)"
