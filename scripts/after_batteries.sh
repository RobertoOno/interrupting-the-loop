#!/bin/sh
# Runs when the generation batteries are done: residual-stream capture for the
# three run sets, then the analysis. Resumable (hidden_states skips done cells).
cd "$(dirname "$0")/.." || exit 1
LOG=runs/hidden_nohup.log
until grep -q "BATTERIES DONE" runs/dream_b2/battery_nohup.log 2>/dev/null; do sleep 120; done
echo "start $(date)" >> $LOG
caffeinate -is .venv/bin/python scripts/hidden_states.py runs/dream_scaffold --conds bare bare_reseed scaffold0 abl_salience >> $LOG 2>&1
caffeinate -is .venv/bin/python scripts/hidden_states.py runs/dream_b2 >> $LOG 2>&1
caffeinate -is .venv/bin/python scripts/hidden_states.py runs/dream_fam8b --model ~/models/mlx/Qwen3-8B-Base-8bit --layers 0,3,6,9,12,15,18,21,24,27,30,33,35 >> $LOG 2>&1
.venv/bin/python scripts/hidden_analysis.py runs/dream_scaffold --tag scaffold >> $LOG 2>&1
.venv/bin/python scripts/hidden_analysis.py runs/dream_b2 --tag b2 >> $LOG 2>&1
.venv/bin/python scripts/hidden_analysis.py runs/dream_fam8b --tag fam8b >> $LOG 2>&1
echo "HIDDEN DONE $(date)" >> $LOG
