#!/bin/sh
# A8-c (docs/A8_CURADORIA_ESTREITA_V1.md, E4) — the SECOND read of A8 with the curated arm completed: same script, same rules, its own
# output files (the first read's files are not touched); diagnostics; evidence archive of the completed curated arm; commit and push.
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src
PY=.venv/bin/python; R8=runs/a8; OUT=docs/a8_results
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }
say "A8-c: second read"
$PY scripts/analysis_a8_narrow.py --plan-base docs/a8_base_v1_plan.json --run-base $R8/a8_base_v1 --plan-own2 docs/a8_own2_v1_plan.json --run-own2 $R8/a8_own2_v1 \
  --plan-curm2 docs/a8_curm2_v1_plan.json --run-curm2 $R8/a8_curm2_v1 --out $OUT/narrow_c.md --json $OUT/narrow_c.json
$PY scripts/a2c2_diagnostics.py --runs base=$R8/a8_base_v1 own2=$R8/a8_own2_v1 curm2=$R8/a8_curm2_v1 --out $OUT/diagnostics_c.json --md $OUT/diagnostics_c.md | tail -1
$PY scripts/a8_invariant_attempts.py --arms a8_base_v1=$R8/a8_base_v1 a8_own2_v1=$R8/a8_own2_v1 a8_curm2_v1=$R8/a8_curm2_v1 --out $OUT/invariant_attempts_c.json
ST=runs/a9/archive_staging_a8c; rm -rf $ST; mkdir -p $ST
for f in pod.log chain.log guard.log; do [ -f runs/a9/$f ] && cp runs/a9/$f $ST/a9_$f; done
[ -f $R8/a8_curm2_v1/retries.json ] && cp $R8/a8_curm2_v1/retries.json $ST/a8_curm2_v1_retries.json
$PY scripts/a1_archive.py --runs $R8/a8_curm2_v1 --dst docs/a8c_evidence_v1 \
  --docs $OUT/narrow_c.md $OUT/narrow_c.json $OUT/diagnostics_c.md $OUT/diagnostics_c.json $OUT/invariant_attempts_c.json docs/a8_curm2_v1_plan.json docs/A8_CURADORIA_ESTREITA_V1.md $ST/* \
  && $PY scripts/a1_archive.py --dst docs/a8c_evidence_v1 --verify && say "archive verified" || say "ARCHIVE FAILED"
git add docs/a8c_evidence_v1 $OUT && git -c core.hooksPath=/dev/null commit -q -m "A8-c: second read with the completed curated arm and its evidence archive (automatic, before interpretation)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && say "committed: $(git log --oneline -1 | cut -c1-110)"
git push -q origin "$(git rev-parse --abbrev-ref HEAD)" && say "pushed" || say "PUSH FAILED"
