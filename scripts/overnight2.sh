#!/bin/sh
# Overnight, after after_confirm.sh: reset/preserved/sham at period 300 on Qwen3-8B and OLMo-2 (pairs with
# their bare_habit cells), then the second genre on the main generator; each judged (gen protocol) as it finishes.
cd "$(dirname "$0")/.." || exit 1
while ! grep -q "AFTER-CONFIRM CHAIN DONE" runs/after_confirm_nohup.log 2>/dev/null; do sleep 120; done
mkdir -p runs/dream_fam8b_reset runs/dream_famolmo_reset runs/dream_genre
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery reset_ladder --model ~/models/mlx/Qwen3-8B-Base-8bit --out runs/dream_fam8b_reset
echo "8B RESET LADDER DONE $(date)"
(AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_fam8b_reset --k 5 --protocol gen > runs/dream_fam8b_reset/rejudge_gen.log 2>&1;
 AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_fam8b_reset --k 5 --protocol gen --order reverse --out-name rejudge_gen_w2.json --skip-from rejudge_gen.json > runs/dream_fam8b_reset/rejudge_gen_w2.log 2>&1) &
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery reset_ladder --model ~/models/mlx/OLMo-2-13B-8bit --out runs/dream_famolmo_reset
echo "OLMO RESET LADDER DONE $(date)"
(AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_famolmo_reset --k 5 --protocol gen --tokenizer-model ~/models/mlx/OLMo-2-13B-8bit > runs/dream_famolmo_reset/rejudge_gen.log 2>&1;
 AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_famolmo_reset --k 5 --protocol gen --tokenizer-model ~/models/mlx/OLMo-2-13B-8bit --order reverse --out-name rejudge_gen_w2.json --skip-from rejudge_gen.json > runs/dream_famolmo_reset/rejudge_gen_w2.log 2>&1) &
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery genre --premises genre --out runs/dream_genre
echo "GENRE DONE $(date)"
(AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_genre --k 5 --protocol gen > runs/dream_genre/rejudge_gen.log 2>&1;
 AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_genre --k 5 --protocol gen --order reverse --out-name rejudge_gen_w2.json --skip-from rejudge_gen.json > runs/dream_genre/rejudge_gen_w2.log 2>&1) &
wait
echo "OVERNIGHT2 DONE $(date)"
