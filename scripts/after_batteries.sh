#!/bin/sh
# After the generation batteries: matched-frequency controls (b2x, into runs/dream_b2),
# residual-stream capture for the three run sets, the b2x rejudge (only after the
# battery-2 rejudge loop has released the results file), then the analysis.
cd "$(dirname "$0")/.." || exit 1
LOG=runs/hidden_nohup.log
until grep -q "BATTERIES DONE" runs/dream_b2/battery_nohup.log 2>/dev/null; do sleep 120; done
echo "start $(date)" >> $LOG
caffeinate -is .venv/bin/python scripts/dream_battery2.py --battery b2x --out runs/dream_b2 >> runs/dream_b2/battery_nohup.log 2>&1
(
  until grep -q "REJUDGE DONE runs/dream_b2" runs/dream_b2/rejudge_nohup.log 2>/dev/null; do sleep 120; done
  AWS_PROFILE=main-account .venv/bin/python scripts/dream_rejudge_surprise.py runs/dream_b2 --k 5 >> runs/dream_b2/rejudge_nohup.log 2>&1
  echo "REJUDGE DONE b2x $(date)" >> runs/dream_b2/rejudge_nohup.log
) &
caffeinate -is .venv/bin/python scripts/hidden_states.py runs/dream_scaffold --conds bare bare_reseed scaffold0 abl_salience >> $LOG 2>&1
caffeinate -is .venv/bin/python scripts/hidden_states.py runs/dream_b2 >> $LOG 2>&1
caffeinate -is .venv/bin/python scripts/hidden_states.py runs/dream_fam8b --model ~/models/mlx/Qwen3-8B-Base-8bit --layers 0,3,6,9,12,15,18,21,24,27,30,33,35 >> $LOG 2>&1
echo "CAPTURE DONE $(date)" >> $LOG
wait
.venv/bin/python scripts/hidden_analysis.py runs/dream_scaffold --tag scaffold >> $LOG 2>&1
.venv/bin/python scripts/hidden_analysis.py runs/dream_b2 --tag b2 >> $LOG 2>&1
.venv/bin/python scripts/hidden_analysis.py runs/dream_fam8b --tag fam8b >> $LOG 2>&1
echo "HIDDEN DONE $(date)" >> $LOG
