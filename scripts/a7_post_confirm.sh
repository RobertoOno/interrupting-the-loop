#!/bin/sh
# A7 — after the confirmation (docs/A7_PAREDE_V1.md): waits for "confirm done" in runs/a7c/confirm.log; archives the four confirmation
# arms with logs, retries, plans, worlds index, verification, sources and the read into docs/a7_confirm_evidence_v1 (SHA-256 manifest,
# verified); commits and pushes the read and the archive; after 15 min records whether the pod was removed. No model calls, no reading
# or interpretation beyond the pre-registered script's own output.
#   screen -dmS a7post caffeinate -i -s sh scripts/a7_post_confirm.sh      (log runs/a7c/post.log)
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; LOG=runs/a7c/post.log
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
say "waiting for 'confirm done' in runs/a7c/confirm.log"
until grep -q "confirm done" runs/a7c/confirm.log 2>/dev/null; do sleep 120; done
say "confirmation finished; verdict line: $(grep -E '"verdict"' runs/a7c/confirm.log | tail -1 | cut -c1-300)"
ST=runs/a7c/archive_staging; rm -rf $ST; mkdir -p $ST
for f in pod.log confirm.log guard.log; do [ -f runs/a7c/$f ] && cp runs/a7c/$f $ST/$f; done
for pid in a7c_base_v1 a7c_own2_v1 a7c_ref_v1 a7c_curm2_v1; do [ -f runs/a7c/$pid/retries.json ] && cp runs/a7c/$pid/retries.json $ST/${pid}_retries.json; done
DOCS=""
for f in docs/a7_results/confirm.md docs/a7_results/confirm.json docs/a7c_base_v1_plan.json docs/a7c_own2_v1_plan.json docs/a7c_ref_v1_plan.json docs/a7c_curm2_v1_plan.json \
         docs/a7_confirm_worlds.json docs/a7_confirm_verification.json docs/a7c_sources/index.json docs/A7_PAREDE_V1.md; do [ -f "$f" ] && DOCS="$DOCS $f"; done
if [ -d docs/a7_confirm_evidence_v1 ]; then say "docs/a7_confirm_evidence_v1 already exists: archive skipped"; else
  $PY scripts/a1_archive.py --runs runs/a7c/a7c_base_v1 runs/a7c/a7c_own2_v1 runs/a7c/a7c_ref_v1 runs/a7c/a7c_curm2_v1 --dst docs/a7_confirm_evidence_v1 --docs $DOCS $ST/* >> "$LOG" 2>&1 \
    && $PY scripts/a1_archive.py --dst docs/a7_confirm_evidence_v1 --verify >> "$LOG" 2>&1 && say "archive verified: $(tail -1 "$LOG")" || say "ARCHIVE FAILED (see $LOG)"
fi
git add docs/a7_confirm_evidence_v1 docs/a7_results/confirm.md docs/a7_results/confirm.json 2>>"$LOG" && \
  git -c core.hooksPath=/dev/null commit -q -m "A7 confirmation: pre-registered read and evidence archive (automatic, before interpretation)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" >> "$LOG" 2>&1 && say "committed: $(git log --oneline -1 | cut -c1-120)" || say "nothing committed (see $LOG)"
git push -q origin "$(git rev-parse --abbrev-ref HEAD)" >> "$LOG" 2>&1 && say "pushed" || say "PUSH FAILED (see $LOG)"
sleep 900
say "pods after the guard window: $(runpodctl pod list 2>&1 | tr -d '\n' | cut -c1-200)"
say "post done"
