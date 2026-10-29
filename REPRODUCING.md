# Reproducing the published papers

This repository holds the delivered manuscripts, analysis and generation code, and synthetic tests. Immutable evidence deposits hold the run data, model responses and verifier reports. The published PDFs remain the versioned record; [publication notes](docs/PUBLICATION_NOTES.md) record later qualifications without changing those PDFs.

## Install and run offline tests

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,analysis]'
.venv/bin/python -m pytest -q
.venv/bin/python scripts/test_p3_snapshot.py
```

The first test command covers the shared runtime and papers 1–4, 6 and 7. The second covers every published P3 test in a temporary Git checkout, with the four upstream modules pinned by its frozen source-matching plan. Those exact versions are retained under `reproduction/p3_snapshot/`; the script checks their SHA-256 before use. This keeps P3’s original source-matching hash checks while preserving the later shared modules needed by paper 6. Both suites run in CI; the P3 core, rehearsal and batch audit are separate CI jobs to keep each within its time limit.

The private financial-authorisation note at `docs/p3/AWS_LIMITE_DIARIO.md` is represented by an explicitly labelled public test fixture. Generated-plan unit tests hash that inert file; its hash differs from the sealed historical note. These synthetic plans do not constitute an admission to rerun a closed experiment. Historical financial admission cannot be reconstructed from this public fixture.

The core works on CPU. Tests that need MLX, model weights, Lean, a sandbox or a GPU check their prerequisites. Running tests does not require paid model calls. Generation and training scripts are separate, require model/provider setup and can incur costs.

## Manuscripts

Run `tectonic main.tex` inside `paper/`, `paper2/`, ..., `paper7/`. The short evaluation paper is in `paper/short/`. The committed PDFs are the delivered versions; rebuilding can change PDF metadata even when the content is the same.

## Restore published data

From the repository root:

```sh
python scripts/restore_published_data.py --deposit programs
python scripts/restore_published_data.py --deposit papers
python scripts/restore_published_data.py --deposit report
```

The restorer downloads the versioned Zenodo files, verifies their MD5 checksums against the record API, and restores data to the paths the analysis scripts expect. It restores data only: it does not replace code or manuscripts. Existing identical files are kept; conflicting files stop the operation. Downloads are cached under `.reproduction-data/`.

- `programs`: [10.5281/zenodo.22713807](https://doi.org/10.5281/zenodo.22713807), the three programs underlying paper 5. It includes the two Lean worlds, their frozen session traces and the form × slot × persistence factorial.
- `papers`: [10.5281/zenodo.23163299](https://doi.org/10.5281/zenodo.23163299), the October correction evidence for papers 1–4 and 6. It adds the missing runs, LLM judgments and evidence archives. Some earlier data are intentionally deduplicated against the deposits below.
- `report`: [10.5281/zenodo.23562924](https://doi.org/10.5281/zenodo.23562924), paper 7 and its anonymised evidence. Deposited `evidence/r1_replay/`, `evidence/r2_pilots/` and review data are mapped back to the `docs/r1/` and `docs/r2/` paths used by its analysis scripts.

For papers 1–4, also obtain the original `run-data-v1` and `run-data-v2` archives from the [GitHub releases](https://github.com/RobertoOno/interrupting-the-loop/releases), archived at [10.5281/zenodo.22714138](https://doi.org/10.5281/zenodo.22714138). They unpack into `runs/`. Read the deposit READMEs for overlaps and prerequisites. Paper 1's primary analysis merges the paper 1 and paper 2 correction archives and uses the deposited self-copy flags; the restorer restores the recorded backup, and you can copy it to `runs/selfcopy_flags.json` when following that deposit's instructions.

## Regenerate paper outputs

```sh
# Paper 5: the factorial tables and figure (programs deposit).
python scripts/paper5_tables.py

# Paper 6: tables and figures from the deposited single-read results.
python scripts/paper6_tables.py
python scripts/paper6_figures.py

# Paper 7: all reported numbers, using the redacted report deposit.
python scripts/r1_report_numbers.py --out paper7/numbers.tex
```

Plot generation needs Matplotlib, included in the `analysis` extra. Paper 6's figure bytes can differ across Matplotlib/font versions; the table and numerical inputs are fixed.

For paper 1 the primary reader is `scripts/analysis_gen.py`; for paper 2 the consolidation and tail readers are `scripts/analysis_c*.py`, `scripts/analysis_n.py` and related readers; for paper 3 see `scripts/analysis_f*.py`; for paper 4 use `scripts/analysis_r4.py`, `scripts/analysis_pulse*.py` and `scripts/spectral_summary.py`. Each script documents its inputs. The archived index for each paper maps batteries to files.

## Limits of the public reproduction

The deposits' manifests and redaction logs are authoritative. A sealed manifest can list original hashes for files whose public copies were redacted; use the outer deposit manifest and `REDACTIONS.json` for the public copies.

Individual human ratings and identity keys remain withheld. Large model adapters and hidden-state tensors are not deposited; their recorded hashes and sizes are listed in the evidence deposits. Re-verifying Lean proofs requires the pinned Lean/Mathlib versions recorded in the corresponding plans. Re-running model generation also needs the recorded weights, backend and provider access.

Paper 7's records-level replay cannot be rerun from public files: its historical snapshots contain the private research notebook. Its snapshot manifest and the resulting audit traces are deposited. `r1_freeze.py`, `r1_notebook_size.py` and the deposit-building script are preserved as provenance code and require private history or scrubbing inputs; use the deposited frozen texts for the public analyses. Reconstructed requests from the redacted paper 1 differ from the historical requests, as the report explains.
