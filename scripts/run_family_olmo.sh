#!/bin/sh
# Third generator family: OLMo-2-13B on the ladder (bare / bare_habit / bare_reseed / scaffold0),
# then offline judging (two workers), residual-stream capture and analysis.
cd "$(dirname "$0")/.." || exit 1
export AWS_PROFILE=main-account
OUT=runs/dream_famolmo; MODEL=~/models/mlx/OLMo-2-13B-8bit
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery fam8b --out $OUT --model $MODEL >> $OUT/battery_nohup.log 2>&1
echo "OLMO BATTERY DONE $(date)" >> $OUT/battery_nohup.log
.venv/bin/python scripts/dream_rejudge_surprise.py $OUT --k 5 --tokenizer-model $MODEL --skip-from rejudge_surprise_w2.json >> $OUT/rejudge_nohup.log 2>&1 &
.venv/bin/python scripts/dream_rejudge_surprise.py $OUT --k 5 --tokenizer-model $MODEL --reverse --out-name rejudge_surprise_w2.json --skip-from rejudge_surprise.json >> $OUT/rejudge_w2.log 2>&1 &
caffeinate -is .venv/bin/python scripts/hidden_states.py $OUT --model $MODEL --layers 0,3,6,9,12,15,18,21,24,27,30,33,36,39 >> runs/hidden_nohup.log 2>&1
wait
.venv/bin/python scripts/rejudge_merge.py $OUT --merge --tokenizer-model $MODEL >> $OUT/rejudge_nohup.log 2>&1
.venv/bin/python scripts/hidden_analysis.py $OUT --tag famolmo >> runs/hidden_nohup.log 2>&1
echo "OLMO ALL DONE $(date)" >> $OUT/battery_nohup.log
