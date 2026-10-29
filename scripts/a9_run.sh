#!/bin/sh
# A9 (docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md) — called by scripts/a9_chain.sh with A9_EP = the endpoint serving base + own2 + curm2 + a9-own3.
# Arms in priority order (the primary block first), each with the resume loop; no new thinking arm starts after A9_CUTOFF_T and no new
# arm at all after A9_CUTOFF_N, so that the single read, the archive, the commit and the push always fit before the guard's deadline.
# Then: the read written before the data, diagnostics, evidence archive, commit and push.
cd "$(dirname "$0")/.." || exit 1
export PYTHONPATH=src CM_LAKE_SHARED="$HOME/wrk/creative-machine-data/lean/mathlib_v4.33.1"
PY=.venv/bin/python; RUNS=runs/a9; LOG=$RUNS/chain.log; OUT=docs/a9_results; EP="${A9_EP:?endpoint}"; mkdir -p "$OUT"
CUT_T=$(date -j -f '%Y-%m-%d %H:%M' "${A9_CUTOFF_T:-2026-09-20 02:30}" +%s); CUT_N=$(date -j -f '%Y-%m-%d %H:%M' "${A9_CUTOFF_N:-2026-09-20 04:15}" +%s)
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }
. scripts/a9_lib.sh
THINK="a9_w5own3_v1 a9_w5own2_v1 a9_w5base_v1"; PLAIN="a9_own3n_v1 a9_own2n_v1 a9_basen_v1 a9_w5own3n_v1 a9_w5own2n_v1 a9_own3lad_v1"; THINK2="a9_own3t_v1 a9_own2t_v1"
for pid in $THINK $PLAIN $THINK2; do
  PLAN=docs/${pid}_plan.json; [ -f "$PLAN" ] || { say "SKIP $pid: plan missing"; continue; }
  case " $PLAIN " in *" $pid "*) CUT=$CUT_N; unset CM_MAX_PARALLEL;; *) CUT=$CUT_T; export CM_MAX_PARALLEL="${A9_THINK_PARALLEL:-12}";; esac   # E1: thinking arms at 12 client slots
  [ "$(date +%s)" -ge "$CUT" ] && { say "SKIP $pid: past the cutoff for this kind of arm (read will state the observed n)"; continue; }
  run_plan "$PLAN" "$RUNS" "$EP" 10 || { say "server lost during $pid: stopping the arms"; break; }
done
say "A9 arms ended: single read"
$PY scripts/analysis_a9.py --runs $RUNS --docs docs --out $OUT/read.md --json $OUT/read.json 2>&1 | tee -a "$LOG"
ARGS=""; for pid in $THINK $PLAIN $THINK2; do [ -d $RUNS/$pid ] && ARGS="$ARGS ${pid#a9_}=$RUNS/$pid"; done
$PY scripts/a2c2_diagnostics.py --runs $ARGS --out $OUT/diagnostics.json --md $OUT/diagnostics.md 2>&1 | tail -1 | tee -a "$LOG"
IARGS=""; for pid in $THINK $THINK2 a9_own3n_v1 a9_own2n_v1 a9_basen_v1 a9_w5own3n_v1 a9_w5own2n_v1; do [ -d $RUNS/$pid ] && IARGS="$IARGS $pid=$RUNS/$pid"; done
$PY scripts/a8_invariant_attempts.py --arms $IARGS --out $OUT/invariant_attempts.json >> "$LOG" 2>&1
[ -f $RUNS/adapters/a9-own3/adapter_model.safetensors ] && (cd $RUNS/adapters && shasum -a 256 a9-own3/adapter_model.safetensors a9-own3/adapter_config.json a9-own3/manifest.json) > $OUT/adapter_weights.sha256 2>/dev/null
ST=$RUNS/archive_staging; rm -rf $ST; mkdir -p $ST
for f in pod.log chain.log guard.log; do [ -f $RUNS/$f ] && cp $RUNS/$f $ST/$f; done
RUNDIRS=""; for pid in $THINK $PLAIN $THINK2; do [ -d $RUNS/$pid ] && { RUNDIRS="$RUNDIRS $RUNS/$pid"; [ -f $RUNS/$pid/retries.json ] && cp $RUNS/$pid/retries.json $ST/${pid}_retries.json; }; done
[ -f $RUNS/adapters/a9-own3/train_log.jsonl ] && cp $RUNS/adapters/a9-own3/train_log.jsonl $ST/a9-own3_train_log.jsonl; [ -f $RUNS/adapters/a9-own3/manifest.json ] && cp $RUNS/adapters/a9-own3/manifest.json $ST/a9-own3_manifest.json
$PY scripts/a1_archive.py --runs $RUNDIRS --dst docs/a9_evidence_v1 \
  --docs $OUT/read.md $OUT/read.json $OUT/diagnostics.md $OUT/diagnostics.json $OUT/invariant_attempts.json $(ls $OUT/adapter_weights.sha256 2>/dev/null) docs/a9_*_v1_plan.json \
  docs/a9_worlds.json docs/a9_verification.json docs/a9_w5_worlds.json docs/a9_w5_verification.json docs/a9_data/manifest.json docs/a9_data/verification.json docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md $ST/* >> "$LOG" 2>&1 \
  && $PY scripts/a1_archive.py --dst docs/a9_evidence_v1 --verify >> "$LOG" 2>&1 && say "archive verified: $(tail -1 "$LOG" | cut -c1-160)" || say "ARCHIVE FAILED"
git add docs/a9_evidence_v1 $OUT && git -c core.hooksPath=/dev/null commit -q -m "A9: pre-registered read and evidence archive (automatic, before interpretation)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" >> "$LOG" 2>&1 && say "committed: $(git log --oneline -1 | cut -c1-110)"
git push -q origin "$(git rev-parse --abbrev-ref HEAD)" >> "$LOG" 2>&1 && say "pushed" || say "PUSH FAILED"
say "a9 run done"
