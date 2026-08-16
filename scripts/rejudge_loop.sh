#!/bin/sh
# Judge finished cells while a battery is still running; final pass at the end.
#   sh scripts/rejudge_loop.sh runs/dream_b2 "battery b2: finished" [tokenizer_model]
RUN=$1; DONE_MARK=$2; TOK=${3:-~/models/mlx/Qwen3-30B-A3B-Base-8bit}
export AWS_PROFILE=main-account
while ! grep -q "$DONE_MARK" "$RUN/progress.log" 2>/dev/null; do
  .venv/bin/python scripts/dream_rejudge_surprise.py "$RUN" --k 5 --tokenizer-model "$TOK" >> "$RUN/rejudge_nohup.log" 2>&1
  sleep 900
done
.venv/bin/python scripts/dream_rejudge_surprise.py "$RUN" --k 5 --tokenizer-model "$TOK" >> "$RUN/rejudge_nohup.log" 2>&1
echo "REJUDGE DONE $RUN $(date)" >> "$RUN/rejudge_nohup.log"
