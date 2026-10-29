#!/usr/bin/env python3
"""R2: generate the synthetic study records with known ground truth (docs/R2_REGRAS_DE_ESCRITA_PRE_REGISTRO_V0.md §3).

    python scripts/r2_records.py --out runs/r2/records --truth runs/r2/truth

Twelve records (four domains x three instances), seed fixed. Each record folder holds what a writer sees: notebook.md, results/
(final.json and the superseded provisional runs), manifest.json, companion.md, draft.md (typed) and draft_keyed.md (placeholders).
The ground truth of the twelve required claims goes to a separate folder that writers never see. The main effect was revised once
(k = 1) in six records and three times (k = 3) in the other six; the manifest is stale on the release item in six records, balanced
with k.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

SEED = 20261006
DOMAINS = {
    "interrupt": dict(
        title="Periodic topic interruption raises judged surprise in base-model generation",
        intervention="periodic topic interruption", baseline="habituation alone", metric="judged surprise (0-10)",
        unit="premise", units="premises", task="genre", tasks="genres", family="premise family", families="premise families",
        judge="the Merlin-70B judge", sweep="the interruption-period sweep", side="window length", mscale=1.0),
    "verifier": dict(
        title="Verifier feedback inside the search notebook and the gain over the classic heuristic",
        intervention="in-notebook verifier feedback", baseline="the plain notebook", metric="gain over best fit (x100)",
        unit="notebook", units="notebooks", task="problem variant", tasks="problem variants", family="variant family",
        families="variant families", judge="the exact verifier", sweep="the feedback-frequency sweep", side="chunk size",
        mscale=0.6),
    "consolidate": dict(
        title="LoRA consolidation of a code proposer moves the mean candidate",
        intervention="LoRA consolidation on verified candidates", baseline="the untrained proposer",
        metric="held-out improvement (x100)", unit="lineage", units="lineages", task="problem family", tasks="problem families",
        family="family cluster", families="family clusters", judge="the exact scorer", sweep="the learning-rate sweep",
        side="adapter rank", mscale=0.8),
    "prover": dict(
        title="Fine-tuning a prover on its own verified proofs",
        intervention="fine-tuning on own verified proofs", baseline="the base prover", metric="solve rate gain (points)",
        unit="world", units="worlds", task="world class", tasks="world classes", family="world family", families="world families",
        judge="the Lean checker", sweep="the data-mixture sweep", side="sampling temperature", mscale=4.0),
}
MODEL_STEMS = ["Kestrel", "Harrier", "Merganser", "Pipit", "Avocet", "Shrike"]
DISTRACTORS = [
    "Refactored the {side} handling in the runner. The old code read the setting from two places (the config file and an "
    "environment variable) and silently preferred the environment; now there is one source, the config, and the runner refuses "
    "to start if they disagree. No behavioural change on the current configs: I diffed the outputs of a 3-{unit} smoke run "
    "before and after and they are byte-identical. Tests: {t} pass.",
    "Side check on {side}, outside the registered design: setting it to {a} instead of {b} moved the metric from {x} to {y} on "
    "a 4-{unit} slice (one seed). This is within the seed noise we saw in the pilot (about +/-{noise}), so I am not pursuing it. "
    "Logged here so nobody re-runs it thinking it is new.\n\n| {side} | metric | seed |\n|---|---|---|\n| {a} | {x} | 0 |\n"
    "| {b} | {y} | 0 |",
    "Reading notes on {topic}. Two papers are relevant: one argues that the effect we look at is mostly a length artefact, the "
    "other measures something close to {intervention} but with a different unit of inference (windows rather than {units}), "
    "which inflates n. Neither tests our contrast directly. Added both to the related-work list with a sentence each; the "
    "length argument is worth one line in Limitations.",
    "Infra: one batch stalled for {m} minutes on a provider timeout around 03:00. The runner's checkpointing worked: it resumed "
    "from the last completed {unit} and nothing was lost or duplicated (checked the cell counts: all complete, no repeats). "
    "Opened an issue to add a watchdog so a stalled batch pages me instead of waiting.",
    "Budget check: {usd} spent so far this month on this study, most of it on the judge. Projected total stays under the cap "
    "even with the full n. If the cap tightens, the first thing to cut is the secondary view, not the registered estimand.",
    "Call with a collaborator about {topic}. They suggested a different seed policy (one seed per {unit} instead of a shared "
    "seed). Reasonable, but changing it now would break the comparison with the pilot; noted for a future study, not adopted. "
    "They also asked whether the judge sees the intervention text; it does not, the windows are generated text only.",
    "Cleaned the results folder: moved scratch outputs and the debugging dumps to archive/ (not part of the record), kept "
    "run files and final.json at the top level. The manifest is the list of what is released; the results files are the "
    "numbers of record. Wrote a short README in results/ saying which file is final.",
    "Ideas for later, not registered: {topic} could explain part of the variance across {tasks}; testing it properly would need "
    "a new pre-registration and probably twice the n. Parking it.",
    "Timing: one full pass over the {units} takes about {m} minutes on the current setup, of which roughly two thirds is the "
    "judge. Parallelising the judge calls would cut it, but the provider's rate limit is the bottleneck, not our code.",
    "Fixed a typo in the plotting script (an axis label said 'surprize'). Figures regenerated; the numbers behind them are "
    "unchanged (same hashes for the data files).",
    "Spot-read {t2} outputs by hand across arms. Nothing unusual. One output was truncated at the token limit; the registered "
    "rule excludes truncated outputs, so it is out, and the exclusion is logged in the cell file. Two outputs repeat a sentence "
    "verbatim, which is within what we saw in the pilot.",
    "Logged the package versions and updated the lockfile; pinned the tokenizer revision after noticing that a minor release "
    "changed the treatment of a whitespace token. Re-ran one {unit} with the pinned revision: identical outputs.",
    "Intermediate sanity check on a secondary metric (not registered): the variance across {units} is {x} in the treatment arm "
    "and {y} in the baseline arm. Expected to be similar; it is. Nothing to act on.",
    "Wrote the analysis script for the registered contrasts before the full data, as the protocol requires: paired permutation "
    "over {units}, one-sided for H1 and H2, Holm across the two. Tested it on synthetic data with a planted effect of {x}; it "
    "recovers it.",
    "Per-{unit} latency of the judge calls this week (not a study metric):\n\n{table}",
    "Length statistics of the generated outputs (tokens), for the record; not registered and not used in any test:\n\n{table}",
    "Re-ran the secondary-metric script after the lockfile update; per-{unit} values (secondary metric, not the estimand):"
    "\n\n{table}\n\nSame as before to the third decimal.",
]
TOPICS = ["judge calibration", "length effects", "seed variance", "prompt formats", "evaluation windows", "data leakage",
          "proposer diversity", "verifier latency", "tokenizer drift", "budget allocation"]


def r2(x: float) -> str:
    return f"{x:+.2f}"


def make_record(rid: str, domain: str, k: int, stale_manifest: bool, rng: random.Random, n_distractors: int | None = None,
                silent: bool = False) -> tuple[dict, dict]:
    """silent=True: the facts are not narrated; they live only in artifacts (release listing, run config, review headers,
    companion note) or in an absence (the announced sweep never reappears)."""
    d = DOMAINS[domain]
    s = d["mscale"]
    model = rng.choice(MODEL_STEMS)
    size = rng.choice([7, 14, 32])
    model_planned, model_run = f"{model}-{size}B", f"{model}-{size}B-Base"
    final = round(rng.uniform(0.9, 1.6) * s, 2)
    provisional = [round(final + rng.choice([-1, 1]) * rng.uniform(0.15, 0.45) * s, 2) for _ in range(k)]
    while any(abs(p - final) < 0.1 * s for p in provisional) or len(set(provisional)) < k:
        provisional = [round(final + rng.choice([-1, 1]) * rng.uniform(0.15, 0.45) * s, 2) for _ in range(k)]
    half = round(rng.uniform(0.35, 0.6) * s, 2)
    ci = (round(final - half, 2), round(final + half, 2))
    ci_prov = (round(provisional[0] - half * 1.2, 2), round(provisional[0] + half * 1.2, 2))
    n_pilot, n_final = rng.choice([(8, 10), (8, 12), (10, 16)])
    h2_prov, h2_prov_p = round(rng.uniform(0.5, 0.8) * s, 2), round(rng.uniform(0.02, 0.04), 3)
    h2_final, h2_final_p = round(rng.uniform(0.2, 0.4) * s, 2), round(rng.uniform(0.09, 0.2), 3)
    neg_task = rng.randint(1, 9)
    neg_val = round(-rng.uniform(0.02, 0.08) * s, 2)
    mean_family, mean_pooled = round(rng.uniform(0.6, 0.9) * s, 3), round(rng.uniform(1.1, 1.5) * s, 3)
    comp_v1 = round(rng.uniform(0.75, 0.95), 2)
    comp_v2 = round(comp_v1 - rng.uniform(0.06, 0.15), 2)
    c1, c2 = f"+{comp_v1:.2f}", f"+{comp_v2:.2f}"
    link = f"https://example.org/{rid.lower()}-release"
    dates = {"kickoff": "2026-03-02", "pilot": "2026-03-04", "read1": "2026-03-09", "draft": "2026-03-10", "h3": "2026-03-11",
             "model": "2026-03-16", "sweep_plan": "2026-03-20", "expand": "2026-03-24", "final": "2026-03-30",
             "companion": "2026-04-02", "cancel": "2026-04-05", "rev1": "2026-04-08", "rev2": "2026-04-12",
             "release": "2026-04-14", "pull": "2026-04-18"}
    rerun_dates = ["2026-03-16", "2026-03-27"]

    entries = []

    def add(date, text):
        entries.append((date, text))

    add(dates["kickoff"], f"Kickoff. Study: does {d['intervention']} beat {d['baseline']} on {d['metric']}? Model planned: "
        f"{model_planned}. Registered before any data: H1 ({d['intervention']} > {d['baseline']} on the per-{d['family']} mean), "
        f"H2 (the gain persists on the held-out half). Estimand: the mean over {d['families']} (pooled means only as a "
        f"secondary view). Release plan: code, per-run data and the individual judgments of {d['judge']}.")
    add(dates["pilot"], f"Pilot with n={n_pilot} {d['units']}. Pipeline works end to end.")
    add(dates["read1"], f"First read (run 1, results/run1.json): main effect {r2(provisional[0])} "
        f"[{ci_prov[0]:+.2f}, {ci_prov[1]:+.2f}] on n={n_pilot}; H2 {r2(h2_prov)}, p={h2_prov_p} (supported at this point); "
        f"positive in all 9 {d['tasks']}; pooled mean {mean_pooled}. The companion paper (v1) reports an effect of {c1} for the "
        f"same {d['intervention']}.")
    add(dates["draft"], "Wrote the paper draft (draft.md) from the first read so the structure is ready; numbers to be updated.")
    add(dates["h3"], f"Added H3 after looking at the first read: the gain is larger in the first {d['family']}." + (
        "" if silent else " Registered today, so H3 is exploratory (registered after data)."))
    if not silent:
        add(dates["model"], f"Checked the run logs: every run so far used {model_run}, not the {model_planned} named in the plan "
            f"(the instruct checkpoint was never available). Keeping {model_run}.")
    for i in range(1, k):
        add(rerun_dates[i - 1], f"Found a bug in the {d['side']} handling; rerun {i + 1} (results/run{i + 1}.json): main effect "
            f"{r2(provisional[i])}. Superseded by later runs.")
    add(dates["sweep_plan"], f"{d['sweep'][0].upper() + d['sweep'][1:]} will run next week and will be reported in the paper.")
    add(dates["expand"], f"Expanded to the full n={n_final} {d['units']} as registered.")
    if silent:
        add(dates["final"], "Final read done; the numbers of record are in results/final.json.")
        add(dates["rev1"], "Review round 1: comments from reviewers A and B applied (reviews/round1_A.md, reviews/round1_B.md).")
        add(dates["rev2"], "Review round 2: comments from reviewers A and B applied (reviews/round2_A.md, reviews/round2_B.md).")
        add(dates["release"], f"Prepared the release at {link}; its contents are listed in release/FILES.txt.")
    else:
        add(dates["final"], f"Final read (results/final.json): main effect {r2(final)} [{ci[0]:+.2f}, {ci[1]:+.2f}] on "
            f"n={n_final}; H2 {r2(h2_final)}, p={h2_final_p}: not supported. Positive in 8 of 9 {d['tasks']} ({d['task']} {neg_task} at "
            f"{neg_val:+.2f}). Registered estimand, the per-{d['family']} mean: {mean_family}; pooled mean (secondary): {mean_pooled}. "
            f"These are the numbers of record.")
        add(dates["companion"], f"The companion paper posted v2 with a correction: its effect is {c2}, not {c1}.")
        add(dates["cancel"], f"Cancelled {d['sweep']} (budget). It will not be run for this paper.")
        add(dates["rev1"], "Review round 1 by two AI reviewer agents (model-based reviewers, not human, not peer review). "
            "Applied their comments.")
        add(dates["rev2"], "Review round 2 by the same two AI reviewer agents. Applied their comments.")
        if stale_manifest:
            add(dates["release"], f"Released code, aggregate data and the individual judgments at {link}. Manifest updated.")
            add(dates["pull"], "Pulled the individual judgments from the release: two raters withdrew consent to share them. The "
                "release now holds code and aggregate data only. The manifest still has to be updated.")
        else:
            add(dates["release"], f"Released code and aggregate data at {link}. The individual judgments are withheld (rater "
                "privacy). Manifest updated.")
    # distractors between the substantive entries, dated inside the study window
    pool = []
    n_d = rng.randint(110, 130)
    for j in range(n_d if n_distractors is None else n_distractors):
        if not pool:
            pool = DISTRACTORS[:]
            rng.shuffle(pool)
        tpl = pool.pop()
        day = rng.randint(3, 47)
        date = f"2026-{3 + (day - 1) // 31:02d}-{(day - 1) % 31 + 1:02d}"
        rows = rng.randint(8, 12)
        table = "| " + d["unit"] + " | value |\n|---|---|\n" + "\n".join(
            f"| {r + 1} | {rng.uniform(0.5, 9.5):.3f} |" for r in range(rows))
        add(date, tpl.format(side=d["side"], t=rng.randint(40, 200), t2=rng.randint(12, 60), a=rng.choice([64, 128, 256]),
                             b=rng.choice([32, 512]), x=round(rng.uniform(1, 9), 2), y=round(rng.uniform(1, 9), 2),
                             noise=round(rng.uniform(0.1, 0.4), 2), topic=rng.choice(TOPICS), intervention=d["intervention"],
                             m=rng.randint(4, 90), usd=f"US${rng.randint(10, 400)}", units=d["units"], unit=d["unit"],
                             tasks=d["tasks"], table=table))
    entries.sort(key=lambda e: e[0])
    notebook = f"# Lab notebook: {d['title']}\n\n" + "\n\n".join(f"## {date}\n\n{text}" for date, text in entries) + "\n"

    results = {"final.json": {"main_effect": final, "ci_lo": ci[0], "ci_hi": ci[1], "n": n_final, "h2_estimate": h2_final,
                              "h2_p": h2_final_p, "scope_positive": 8, "scope_total": 9, "negative_task": neg_task,
                              "negative_value": neg_val, "mean_per_family": mean_family, "mean_pooled": mean_pooled,
                              "status": "final"}}
    results["run1.json"] = {"main_effect": provisional[0], "ci_lo": ci_prov[0], "ci_hi": ci_prov[1], "n": n_pilot,
                            "h2_estimate": h2_prov, "h2_p": h2_prov_p, "scope_positive": 9, "scope_total": 9,
                            "mean_pooled": mean_pooled, "status": "superseded"}
    for i in range(1, k):
        results[f"run{i + 1}.json"] = {"main_effect": provisional[i], "status": "superseded"}
    released = ["code", "aggregate data"] + (["individual judgments"] if stale_manifest and not silent else [])
    manifest = {
        "released": released, "withheld": [] if stale_manifest else ["individual judgments"], "release_link": link,
        "review": "two rounds by two AI reviewer agents; not peer reviewed",
        "analyses": {d["sweep"]: "cancelled, not run"},
        "registration": {"H1": dates["kickoff"], "H2": dates["kickoff"], "H3": f"{dates['h3']} (after the first read; exploratory)"},
        "model": model_run, "companion_effect": comp_v2, "updated": dates["release"],
    }
    claims = {
        "release": ("Code, aggregate data and the individual judgments are released at " if stale_manifest else
                    "Code and aggregate data are released at ") + f"{link}" + ("." if stale_manifest else
                                                                                 "; the individual judgments are withheld."),
        "review": "The paper had two rounds of review by AI reviewer agents; it has not been peer reviewed.",
        "status_sweep": f"{d['sweep'][0].upper() + d['sweep'][1:]} was cancelled and not run.",
        "registration": f"H1 and H2 were registered before any data; H3 was registered after the first read and is exploratory.",
        "companion": c2,
        "model": model_run,
    }
    draft_typed = draft(d, typed=True, model=model_planned, main=provisional[0], ci=ci_prov, n=n_pilot, h2=(h2_prov, h2_prov_p),
                        mean=mean_pooled, comp=c1)
    draft_keyed = draft(d, typed=False, model=None, main=None, ci=None, n=None, h2=None, mean=None, comp=None)
    companion = (f"# Companion paper\n\n- v1 ({dates['read1']}): reports an effect of {c1} for {d['intervention']}.\n"
                 f"- v2 ({dates['companion']}): corrected to {c2} (an error in their aggregation).\n")
    files = {"notebook.md": notebook, "companion.md": companion, "draft.md": draft_typed, "draft_keyed.md": draft_keyed}
    if silent:
        # no manifest (the real project had none); the facts sit in artifacts
        files["results/run_config.json"] = json.dumps({"model": model_run, "seed_policy": "shared", d["side"]: 128}, indent=1)
        files["release/FILES.txt"] = (f"Release {link}\n\ncode/runner.py\ncode/analysis.py\ncode/README.md\n"
                                      f"data/aggregate_results.csv\ndata/README.md\n")
        for rnd in (1, 2):
            for who in ("A", "B"):
                files[f"reviews/round{rnd}_{who}.md"] = (
                    f"# Review, round {rnd}, reviewer {who}\n\nReviewer: AI reviewer agent (Claude Opus 5), not a human reviewer.\n\n"
                    f"- The abstract should state the unit of inference.\n- Report the registered estimand before the secondary view.\n"
                    f"- Clarify the exclusion rule for truncated outputs.\n")
    else:
        files["manifest.json"] = json.dumps(manifest, indent=1)
    for name, obj in results.items():
        files[f"results/{name}"] = json.dumps(obj, indent=1)
    truth = {
        "record": rid, "domain": domain, "k": k, "stale_manifest": stale_manifest and not silent, "silent": silent,
        "values": results["final.json"],
        "provisional_main": provisional, "keyed_values": {"main": final, "ci_lo": ci[0], "ci_hi": ci[1], "n": n_final,
                                                          "h2_est": h2_final, "h2_p": h2_final_p, "scope_pos": 8, "scope_total": 9,
                                                          "mean_per_family": mean_family, "mean_pooled": mean_pooled},
        "claims_rendered": claims,
        "required": [
            {"id": 1, "fact": "main effect", "correct": r2(final), "stale": [r2(p) for p in provisional]},
            {"id": 2, "fact": "confidence interval of the main effect", "correct": f"[{ci[0]:+.2f}, {ci[1]:+.2f}]",
             "stale": [f"[{ci_prov[0]:+.2f}, {ci_prov[1]:+.2f}]"]},
            {"id": 3, "fact": f"number of {d['units']}", "correct": f"n = {n_final}", "stale": [f"n = {n_pilot}"]},
            {"id": 4, "fact": "outcome of H2", "correct": f"H2 not supported ({r2(h2_final)}, p = {h2_final_p})",
             "stale": [f"H2 supported ({r2(h2_prov)}, p = {h2_prov_p})"]},
            {"id": 5, "fact": f"in how many {d['tasks']} the effect is positive", "correct": f"8 of 9 ({d['task']} {neg_task} negative)",
             "stale": ["all 9"]},
            {"id": 6, "fact": "the mean reported as the registered estimand",
             "correct": f"per-{d['family']} mean {mean_family} (pooled {mean_pooled} only as secondary)",
             "stale": [f"pooled mean {mean_pooled} presented as the main mean"]},
            {"id": 7, "fact": f"status of {d['sweep']}", "correct": "cancelled, not run",
             "stale": ["in progress", "will be reported", "reported"]},
            {"id": 8, "fact": "what is released", "correct": "code and aggregate data; individual judgments not released",
             "stale": ["individual judgments released", "per-run data and judgments released"]},
            {"id": 9, "fact": "review", "correct": "two rounds by AI reviewer agents; not peer reviewed",
             "stale": ["independent review", "external review", "peer review", "will undergo independent review"]},
            {"id": 10, "fact": "registration of H3", "correct": "H3 registered after the first read; exploratory",
             "stale": ["three pre-registered hypotheses", "H3 pre-registered"]},
            {"id": 11, "fact": "effect reported by the companion paper", "correct": f"{c2} (its v2)",
             "stale": [c1]},
            {"id": 12, "fact": "model used", "correct": model_run, "stale": [model_planned]},
        ],
    }
    return files, truth


def draft(d, typed: bool, model, main, ci, n, h2, mean, comp) -> str:
    """The draft written on the first-read date: typed values (W0, W1, W3) or placeholders (W2) around the same prose."""
    V = (lambda key, val: val) if typed else (lambda key, val: "{{val:" + key + "}}")
    C = (lambda key, val: val) if typed else (lambda key, val: "{{claim:" + key + "}}")
    main_s = V("main", r2(main) if typed else "")
    ci_s = f"[{V('ci_lo', f'{ci[0]:+.2f}' if typed else '')}, {V('ci_hi', f'{ci[1]:+.2f}' if typed else '')}]"
    n_s = V("n", str(n) if typed else "")
    h2e = V("h2_est", r2(h2[0]) if typed else "")
    h2p = V("h2_p", str(h2[1]) if typed else "")
    total = V("scope_total", "9")
    mean_s = V("mean_pooled", str(mean) if typed else "")
    comp_s = C("companion", comp if typed else "")
    model_s = C("model", model if typed else "")
    release = C("release", f"Code, per-run data and the individual judgments of {d['judge']} are released with the paper."
                if typed else "")
    review = C("review", "The paper will undergo independent review before submission." if typed else "")
    registration = C("registration", "We pre-registered three hypotheses (H1-H3) before collecting data." if typed else "")
    status = C("status_sweep", f"{d['sweep'][0].upper() + d['sweep'][1:]} is in progress and will be reported in the final "
               "version." if typed else "")
    return f"""# {d['title']}

## Abstract

We test whether {d['intervention']} improves {d['metric']} over {d['baseline']}. On n = {n_s} {d['units']}, the gain is {main_s} \
{ci_s}, and it is positive in all {total} {d['tasks']}. {release}

## 1. Introduction

A companion study reported an effect of {comp_s} for the same intervention. We ask whether it holds under a stricter protocol, \
with the {d['unit']} as the unit of inference.

## 2. Methods

All runs use {model_s}. {registration} The estimand is the mean over {d['families']}. Outcomes are scored by {d['judge']}.

## 3. Results

The main effect is {main_s} {ci_s} (n = {n_s}). H2 is supported ({h2e}, p = {h2p}). The effect is positive in all {total} \
{d['tasks']}. The mean is {mean_s}.

## 4. Limitations and future work

{status} The study uses one model family.

## 5. Availability and review

{release} {review}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--pilot", action="store_true", help="one pilot record (P01) from another seed, outside the main twelve")
    ap.add_argument("--pilot-sizes", action="store_true", help="P01 regenerated with more distractors (P02, P03)")
    ap.add_argument("--pilot-silent", action="store_true", help="P01 with the facts only in artifacts or absences (P04)")
    a = ap.parse_args()
    for p in (a.out, a.truth):
        if p.exists() and any(p.iterdir()) and not (a.pilot or a.pilot_sizes or a.pilot_silent):
            sys.exit(f"{p} is not empty; R2 records are generated once, into fresh directories")
    if a.pilot_silent:
        files, truth = make_record("P04", "verifier", 3, True, random.Random(SEED + 999), silent=True)
        for name, text in files.items():
            path = a.out / "P04" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        a.truth.mkdir(parents=True, exist_ok=True)
        (a.truth / "P04.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
        print("P04 silent pilot written")
        return
    if a.pilot_sizes:
        for rid, nd in (("P02", 650), ("P03", 1950)):          # the P01 record (same seed, same facts) with more distractors
            files, truth = make_record(rid, "verifier", 3, True, random.Random(SEED + 999), n_distractors=nd)
            for name, text in files.items():
                path = a.out / rid / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            a.truth.mkdir(parents=True, exist_ok=True)
            (a.truth / f"{rid}.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
            print(rid, "distractors", nd, "notebook chars", len(files["notebook.md"]))
        return
    if a.pilot:
        files, truth = make_record("P01", "verifier", 3, True, random.Random(SEED + 999))
        for name, text in files.items():
            path = a.out / "P01" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        a.truth.mkdir(parents=True, exist_ok=True)
        (a.truth / "P01.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
        print("P01 pilot record written")
        return
    rng = random.Random(SEED)
    plan = []
    for i, dom in enumerate(DOMAINS):
        for j in range(3):
            plan.append(dom)
    combos = [(1, False), (3, True), (1, True), (3, False)]      # each combination 3 times; each domain gets 3 distinct ones
    ks = [combos[i % 4][0] for i in range(12)]
    stale = [combos[i % 4][1] for i in range(12)]
    for i, dom in enumerate(plan):
        rid = f"R{i + 1:02d}"
        files, truth = make_record(rid, dom, ks[i], stale[i], rng)
        for name, text in files.items():
            path = a.out / rid / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        a.truth.mkdir(parents=True, exist_ok=True)
        (a.truth / f"{rid}.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
        print(rid, dom, "k", ks[i], "stale_manifest", stale[i], "notebook chars", len(files["notebook.md"]))


if __name__ == "__main__":
    main()
