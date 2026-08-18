#!/bin/sh
# Overnight follow-ups (external review P1/P2), chained after the confirmatory battery:
# (1) convert Qwen3-8B-Base to bf16 (no quantization) and Qwen3-8B (post-trained) to 8-bit;
# (2) run the core ladder on each; (3) judge both under the generated-only protocol.
cd "$(dirname "$0")/.." || exit 1
while ! grep -q "CONFIRM DONE" runs/dream_confirm/chain_nohup.log 2>/dev/null; do sleep 120; done
while ! grep -q "DOWNLOADED" runs/hf_download_qwen3_8b_base.log 2>/dev/null; do sleep 120; done
BASE=$(grep DOWNLOADED runs/hf_download_qwen3_8b_base.log | tail -1 | awk '{print $2}')
if [ ! -d ~/models/mlx/Qwen3-8B-Base-bf16 ]; then
  .venv/bin/python -m mlx_lm convert --hf-path "$BASE" --mlx-path ~/models/mlx/Qwen3-8B-Base-bf16 --dtype bfloat16 || .venv/bin/python -m mlx_lm.convert --hf-path "$BASE" --mlx-path ~/models/mlx/Qwen3-8B-Base-bf16 --dtype bfloat16
fi
echo "BF16 CONVERTED $(date)"
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery ladder3 --model ~/models/mlx/Qwen3-8B-Base-bf16 --out runs/dream_fam8b_bf16
echo "BF16 LADDER DONE $(date)"
AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_fam8b_bf16 --k 5 --protocol gen > runs/dream_fam8b_bf16/rejudge_gen.log 2>&1 &
# post-trained Qwen3-8B (instruct) at 8 bits, if the download finished
if grep -q "DOWNLOADED" runs/hf_download_qwen3_8b_instruct.log 2>/dev/null; then
  INST=$(grep DOWNLOADED runs/hf_download_qwen3_8b_instruct.log | tail -1 | awk '{print $2}')
  if [ ! -d ~/models/mlx/Qwen3-8B-8bit ]; then
    .venv/bin/python -m mlx_lm convert --hf-path "$INST" --mlx-path ~/models/mlx/Qwen3-8B-8bit -q --q-bits 8 || .venv/bin/python -m mlx_lm.convert --hf-path "$INST" --mlx-path ~/models/mlx/Qwen3-8B-8bit -q --q-bits 8
  fi
  echo "INSTRUCT CONVERTED $(date)"
  caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery ladder3 --model ~/models/mlx/Qwen3-8B-8bit --out runs/dream_instruct8b
  echo "INSTRUCT LADDER DONE $(date)"
  AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_instruct8b --k 5 --protocol gen > runs/dream_instruct8b/rejudge_gen.log 2>&1 &
fi
wait
echo "AFTER-CONFIRM CHAIN DONE $(date)"
