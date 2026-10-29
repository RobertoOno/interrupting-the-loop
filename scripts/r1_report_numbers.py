#!/usr/bin/env python3
"""Every number in the R1/R2 report (paper7/) as a LaTeX macro, computed from the archived evidence; nothing in the text is typed.

    python scripts/r1_report_numbers.py --out paper7/numbers.tex

Reads only docs/r1/reference_set_v1.jsonl, docs/r1/evidence_v1/, docs/r2/pilot_evidence_v1/ and docs/r1/report_review_v2/ (the
archived copies, so the report can be rebuilt from the repository alone). The last holds the post hoc material added during the
review of the report: the notebook's size at each freeze (scripts/r1_notebook_size.py) and the coding of each erratum's status at
the freeze (freeze_status/consensus.json, when present).
"""

from __future__ import annotations

import argparse
import collections
import hashlib
from fractions import Fraction
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from r1_analysis import chao1, wilson  # noqa: E402
from r1_judging import CHECKER_SEVERITY_KEPT, severity_of  # noqa: E402

EV = ROOT / "docs/r1/evidence_v1"
REV = ROOT / "docs/r1/report_review_v2"
PILOT = ROOT / "docs/r2/pilot_evidence_v1"
FAMS = ["opus", "gpt", "kimi", "deepseek", "mistral", "qwen"]
FAMNAME = {"opus": "Opus", "gpt": "Gpt", "kimi": "Kimi", "deepseek": "Deepseek", "mistral": "Mistral", "qwen": "Qwen"}
CLASSES = ["NUM", "MIX", "SCOPE", "STATUS", "META", "METHOD", "PROP", "INTERNAL", "CITE", "TYPO"]
RUN = {1: "A", 2: "B"}


def pct(k, n):
    """A percentage rounded half up, computed on exact fractions."""
    x = Fraction(100) * Fraction(k) / Fraction(n)
    return f"{int(x + Fraction(1, 2))}"


def floor2(x):
    """A lower bound, rounded down to two decimals."""
    return f"{math.floor(x * 100) / 100:.2f}"


def floor3(x):
    """A lower bound, rounded down to three decimals."""
    return f"{math.floor(x * 1000) / 1000:.3f}"


def chao_interval(s, f1, f2, z=1.96):
    """Approximate 95% interval for Chao's (1987) estimator N = S + f1^2/(2 f2): his variance formula and the log-normal interval
    S + T/C to S + T*C, with T = N - S and C = exp(z sqrt(log(1 + var/T^2))). It treats the occasions as independent."""
    r = f1 / f2
    var = f2 * (r ** 4 / 4 + r ** 3 + r ** 2 / 2)
    t = f1 * f1 / (2 * f2)
    c = math.exp(z * math.sqrt(math.log(1 + var / t ** 2)))
    return s + t / c, s + t * c


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    m = {}
    ref = [json.loads(l) for l in (ROOT / "docs/r1/reference_set_v1.jsonl").read_text().splitlines() if l.strip()]
    prim = [r for r in ref if r["primary"]]
    pid = {r["id"] for r in prim}
    m["NrefAll"], m["NrefPrimary"] = len(ref), len(prim)
    m["NrefLowConf"] = sum(1 for r in ref if not r["primary"] and r["visible"] == "source")   # low-confidence items kept out
    m["NrefPdfOnly"] = sum(1 for r in ref if r["visible"] == "pdf_only")
    m["Nomission"] = sum(1 for r in ref if r.get("omission"))
    m["NomissionPrimary"] = sum(1 for r in prim if r.get("omission"))
    for doc in ["P1", "PS", "P2", "P3", "P4", "P6"]:
        m[f"Nref{doc.replace('P1', 'Pone').replace('PS', 'Pshort').replace('P2', 'Ptwo').replace('P3', 'Pthree').replace('P4', 'Pfour').replace('P6', 'Psix')}"] = sum(1 for r in ref if r["doc"] == doc)
    for c in CLASSES:
        m[f"Nclass{c.title()}"] = sum(1 for r in prim if r["class"] == c)
    for g, w in (("G1", "One"), ("G2", "Two"), ("G3", "Three")):
        m[f"NsevG{w}"] = sum(1 for r in prim if r["severity"] == g)
    kb = json.loads((EV / "coder_b/kappa.json").read_text())
    m["KappaClass"], m["AgreeClass"] = f"{kb['kappa_class']:.2f}", pct(kb["agreement_class"], 1)
    m["KappaSev"], m["AgreeSev"] = f"{kb['kappa_severity']:.2f}", pct(kb["agreement_severity"], 1)
    mv = json.loads((EV / "match_validation/validation_results.json").read_text())["metrics"]
    m["ValRecall"], m["ValPrecision"] = f"{mv['recall']:.2f}", f"{mv['precision']:.2f}"
    m["ValPos"], m["ValNeg"] = mv["n_pos"], mv["n_neg"]
    hc = json.loads((EV / "hand_check.json").read_text())
    m["HandCorrect"], m["HandN"] = hc["correct"], hc["n"]
    is_opus = lambda cell: "_opus_" in cell or cell.startswith("c2_opus")  # noqa: E731
    m["HandOpusN"] = sum(1 for r in hc["rows"] if is_opus(r["cell"]))
    m["HandOpusCorrect"] = sum(1 for r in hc["rows"] if is_opus(r["cell"]) and r["correct"])
    m["HandOtherN"] = sum(1 for r in hc["rows"] if not is_opus(r["cell"]))
    m["HandOtherCorrect"] = sum(1 for r in hc["rows"] if not is_opus(r["cell"]) and r["correct"])
    cap = json.loads((EV / "captures.json").read_text())
    occ = {k: set(v["caught"]) for k, v in cap["occasions"].items()}
    meta = cap["occasions"]
    new = {x["id"] for x in cap["added_items"]}
    m["Nnew"] = len(new)
    m["Nclusters"], m["AdjAgree"] = cap["adjudication"]["n_clusters_judged"], pct(cap["adjudication"]["agreement"], 1)
    an = json.loads((EV / "R1_analysis.json").read_text())
    for f in FAMS:
        for r in (1, 2):
            k = len(occ[f"C1:{f}:r{r}"] & pid)
            m[f"Rec{FAMNAME[f]}{RUN[r]}"] = k
            m[f"Rec{FAMNAME[f]}{RUN[r]}Pct"] = pct(k, len(pid))
            prec = an["precision"].get(f"C1:{f}:r{r}")
            m[f"Prec{FAMNAME[f]}{RUN[r]}"] = f"{prec:.2f}"
        m[f"Rec{FAMNAME[f]}Both"] = len((occ[f"C1:{f}:r1"] | occ[f"C1:{f}:r2"]) & pid)
    for r in (1, 2):
        lo, hi = wilson(len(occ[f"C1:opus:r{r}"] & pid), len(pid))
        m[f"RecOpus{RUN[r]}Lo"], m[f"RecOpus{RUN[r]}Hi"] = f"{lo:.2f}", f"{hi:.2f}"
    # the two Opus runs compared on the same errata: exact McNemar test on the discordant items
    only_a, only_b = len((occ["C1:opus:r1"] - occ["C1:opus:r2"]) & pid), len((occ["C1:opus:r2"] - occ["C1:opus:r1"]) & pid)
    n_disc = only_a + only_b
    m["OpusOnlyA"], m["OpusOnlyB"] = only_a, only_b
    m["McNemarOpusP"] = f"{min(1.0, 2 * sum(math.comb(n_disc, k) for k in range(min(only_a, only_b) + 1)) / 2 ** n_disc):.2f}"
    m["RecCtwo"], m["RecCtwoPct"] = len(occ["C2:opus"] & pid), pct(len(occ["C2:opus"] & pid), len(pid))
    mid = [len(occ[f"C1:{f}:r{r}"] & pid) for f in ("gpt", "kimi") for r in (1, 2)]
    m["MidFamLoPct"], m["MidFamHiPct"] = pct(min(mid), len(pid)), pct(max(mid), len(pid))
    m["PrecCtwo"] = f"{an['precision']['C2:opus']:.2f}"
    m["RecCthree"], m["RecCfour"] = len(occ["C3"] & pid), len(occ["C4"] & pid)
    m["PrecCthree"], m["PrecCfour"] = floor3(an["precision"]["C3"]), floor3(an["precision"]["C4"])
    # precision split: a high/medium finding is real when it matched an audited erratum, or when its cluster was confirmed as a new
    # error by both adjudicators (Opus 5.5 and GPT-6.1 Sol), as in captures() of scripts/r1_judging.py
    both_yes, member_of, verdict_pairs = {}, {}, collections.Counter()
    for p in sorted((EV / "adjudication").glob("adj_*_opus.json")):
        va = {v["cid"]: v.get("verdict") for v in (json.loads(p.read_text())["verdicts"] or []) if isinstance(v, dict) and "cid" in v}
        bp = p.with_name(p.name.replace("_opus", "_gpt"))
        vb = {v["cid"]: v.get("verdict") for v in ((json.loads(bp.read_text())["verdicts"] or []) if bp.exists() else [])
              if isinstance(v, dict) and "cid" in v}
        for cid in set(va) | set(vb):
            both_yes[cid] = va.get(cid) == "yes" and vb.get(cid) == "yes"
            verdict_pairs[(va.get(cid), vb.get(cid))] += 1
    for p in sorted((EV / "clusters").glob("clusters_*.json")):
        for c in json.loads(p.read_text())["clusters"]:
            for mem in c["members"]:
                member_of[mem] = c["cid"]
    split = collections.defaultdict(collections.Counter)
    for p in sorted((EV / "matches_filled").rglob("c[1-4]_*.json")):
        row = json.loads(p.read_text())
        if row.get("mode") != "findings":
            continue
        for f in row["findings"]:
            if not (row["occasion"] in ("C3", "C4") or severity_of(f) in CHECKER_SEVERITY_KEPT):
                continue
            sp = split[row["occasion"]]
            sp["findings"] += 1
            if f.get("matches"):
                sp["matched"] += 1
            elif both_yes.get(member_of.get(f"{row['cell']}#{f['n']}")):
                sp["new"] += 1
    for k, sp in split.items():
        assert abs((sp["matched"] + sp["new"]) / sp["findings"] - an["precision"][k]) < 1e-9, k
    # the two adjudicators' verdicts (Opus 5.5, GPT-6.1 Sol): a new error needs both to say yes
    assert verdict_pairs[("yes", "yes")] == len(new) and sum(verdict_pairs.values()) == m["Nclusters"]
    m["AdjOpusYes"] = sum(n for (a, b), n in verdict_pairs.items() if a == "yes")
    m["AdjGptYes"] = sum(n for (a, b), n in verdict_pairs.items() if b == "yes")
    m["AdjEitherYes"] = sum(n for (a, b), n in verdict_pairs.items() if "yes" in (a, b))
    m["AdjBothNo"] = verdict_pairs[("no", "no")]
    m["AdjBothUnc"] = verdict_pairs[("uncertain", "uncertain")]
    same = verdict_pairs[("yes", "yes")] + m["AdjBothNo"] + m["AdjBothUnc"]
    assert abs(same / m["Nclusters"] - cap["adjudication"]["agreement"]) < 1e-9   # agreement counts all three answers
    for f in FAMS:
        for r in (1, 2):
            sp = split[f"C1:{f}:r{r}"]
            m[f"PrecM{FAMNAME[f]}{RUN[r]}"] = f"{sp['matched'] / sp['findings']:.2f}"
    m["PrecMCtwo"] = f"{split['C2:opus']['matched'] / split['C2:opus']['findings']:.2f}"
    for r in (1, 2):
        sp = split[f"C1:opus:r{r}"]
        lo, hi = wilson(sp["matched"] + sp["new"], sp["findings"])
        m[f"PrecOpus{RUN[r]}Lo"], m[f"PrecOpus{RUN[r]}Hi"] = f"{lo:.2f}", f"{hi:.2f}"
    # recall counts findings of any severity, precision only those the checker rated high or medium: how many errata a check caught
    # only through findings it rated low (never adjudicated), and how often each family rated its findings high or medium
    caught_hm, n_sev, low_matched = collections.defaultdict(set), collections.defaultdict(collections.Counter), collections.Counter()
    for p in sorted((EV / "matches_filled").rglob("c[1-2]_*.json")):
        row = json.loads(p.read_text(encoding="utf-8"))
        if row.get("mode") != "findings":
            continue
        for f in row["findings"]:
            kept = severity_of(f) in CHECKER_SEVERITY_KEPT
            n_sev[row["occasion"]]["hm" if kept else "low"] += 1
            if kept:
                caught_hm[row["occasion"]] |= set(f.get("matches") or []) & pid
            elif f.get("matches"):
                low_matched[row["occasion"]] += 1
    for name, o in (("OpusA", "C1:opus:r1"), ("OpusB", "C1:opus:r2"), ("Ctwo", "C2:opus")):
        m[f"RecHm{name}"] = len(caught_hm[o])
        m[f"RecLowOnly{name}"] = len((occ[o] & pid) - caught_hm[o])
        m[f"Nlow{name}"], m[f"NlowMatched{name}"] = n_sev[o]["low"], low_matched[o]
        allf = n_sev[o]["hm"] + n_sev[o]["low"]
        matched_all = split[o]["matched"] + low_matched[o]
        m[f"PrecAll{name}"] = floor2((matched_all + split[o]["new"]) / allf)   # a lower bound: low unmatched never adjudicated
    shares = {f: (n_sev[f"C1:{f}:r1"]["hm"] + n_sev[f"C1:{f}:r2"]["hm"]) /
              sum(n_sev[f"C1:{f}:r{r}"][k] for r in (1, 2) for k in ("hm", "low")) for f in FAMS}
    m["HmShareOpus"], m["HmShareGpt"] = pct(shares["opus"], 1), pct(shares["gpt"], 1)
    m["HmShareMin"], m["HmShareMax"] = pct(min(shares.values()), 1), pct(max(shares.values()), 1)
    m["PrecCthreeK"], m["PrecCthreeN"] = split["C3"]["matched"], split["C3"]["findings"]
    m["PrecCfourK"], m["PrecCfourN"] = split["C4"]["matched"], split["C4"]["findings"]
    for name, key in (("OpusA", "C1:opus:r1"), ("OpusB", "C1:opus:r2"), ("GptA", "C1:gpt:r1"), ("GptB", "C1:gpt:r2"),
                      ("Ctwo", "C2:opus")):
        sp = split[key]
        m[f"Prec{name}N"], m[f"Prec{name}Matched"], m[f"Prec{name}New"] = sp["findings"], sp["matched"], sp["new"]
    # one records-level finding came from the snapshot's own exclusions (the review reports, left out as other checks, were read as
    # absent); found by reading C2's findings; both adjudicators said uncertain, so it stays in C2's denominator
    excl = sorted(k for k, cid in member_of.items() if cid == "P6-K056")
    assert excl == ["c2_opus_P6#1"], excl
    sp = split["C2:opus"]
    m["PrecCtwoNoExcl"] = f"{(sp['matched'] + sp['new']) / (sp['findings'] - len(excl)):.2f}"
    forced, calls = [], {}
    for p in EV.glob("c2/*/raw.jsonl"):
        for line in p.read_text().splitlines():
            row = json.loads(line)
            if row.get("event") == "final":
                forced.append(row["cell"])
    for p in EV.glob("c2/*/c2_*.json"):
        row = json.loads(p.read_text())
        calls[row["cell"]] = row["tool_calls"]
    m["CtwoForced"] = len(forced)
    nb_touch, nb_dir_search = collections.Counter(), collections.Counter()
    for p in EV.glob("c2/*/raw.jsonl"):
        for line in p.read_text().splitlines():
            row = json.loads(line)
            if row.get("event") == "tool" and "PLANO.md" in json.dumps(row.get("input", {})):
                nb_touch[row["cell"]] += 1
            # searches over the whole snapshot or over docs/ also scan the notebook without naming it
            elif row.get("event") == "tool" and row.get("name") == "grep" and \
                    str(row.get("input", {}).get("path", "")).strip("/") in ("", ".", "docs"):
                nb_dir_search[row["cell"]] += 1
    c2cells = sorted(calls)
    m["CtwoNbMin"] = min(nb_touch.get(c, 0) for c in c2cells)
    m["CtwoNbMax"] = max(nb_touch.get(c, 0) for c in c2cells)
    m["CtwoNbPsix"] = nb_touch.get("c2_opus_P6", 0)
    m["CtwoNbPsixDirSearch"] = nb_dir_search.get("c2_opus_P6", 0)
    c4 = [json.loads(p.read_text()) for p in EV.glob("c4/c4_*.json")]
    m["CfourPartial"] = sum(1 for d in c4 if d.get("status") == "partial")
    m["CfourFindings"] = sum(len(d["findings"]) for d in c4)
    m["CfourNotReturned"] = sum(1 for d in c4 for f in d["findings"] if "not returned" in f.get("problem", "").lower())
    m["CtwoForcedCallsLo"] = min(calls[c] for c in forced)
    m["CtwoForcedCallsHi"] = max(calls[c] for c in forced)
    # the token cap counted cache reads; the distinct tokens an audit read are its uncached input plus what it wrote to the cache
    distinct = {}
    for p in EV.glob("c2/*/c2_*.json"):
        row = json.loads(p.read_text())
        distinct[row["cell"]] = row["usage"].get("in", 0) + row["usage"].get("cache_write", 0)
    m["CtwoDistinctLo"] = round(min(distinct[c] for c in forced) / 1000)
    m["CtwoDistinctHi"] = round(max(distinct[c] for c in forced) / 1000)
    # C1 replies that strict JSON parsing could not read (recovered by the lenient parser of amendment 3)
    c1cells = [json.loads(p.read_text()) for p in EV.glob("c1/*/c1_*.json")]
    m["NreplyCone"] = len(c1cells)
    m["NparseRecovered"] = sum(1 for c in c1cells if c.get("status") == "unparsed")
    m["NparseRecoveredWeak"] = sum(1 for c in c1cells if c.get("status") == "unparsed" and c["model"] in ("deepseek", "mistral", "qwen"))
    m["NreplyWeak"] = sum(1 for c in c1cells if c["model"] in ("deepseek", "mistral", "qwen"))
    m["NfreeText"] = sum(1 for p in (EV / "matches_filled").rglob("c[1-4]_*.json") if json.loads(p.read_text()).get("mode") == "free_text")
    free_cells = {json.loads(p.read_text())["cell"] for p in (EV / "matches_filled").rglob("c[1-4]_*.json")
                  if json.loads(p.read_text()).get("mode") == "free_text"}
    unparsed = {c["cell"] for c in c1cells if c.get("status") == "unparsed"}
    assert free_cells <= unparsed and len(free_cells) == m["NfreeText"]
    m["NparseLenient"] = len(unparsed - free_cells)
    # amendment 6: the findings the matcher left without a decision, and how they were settled
    undecided = decided_before = 0
    for p in (EV / "matches").rglob("c[1-4]_*.json"):
        row = json.loads(p.read_text())
        if row.get("mode") == "findings":
            undecided += sum(1 for f in row["findings"] if f.get("matches") is None)
            decided_before += sum(1 for f in row["findings"] if f.get("matches") is not None)
    dec, dec_strong = collections.Counter(), collections.Counter()
    for p in (EV / "matches_filled").rglob("c[1-4]_*.json"):
        row = json.loads(p.read_text())
        if row.get("mode") == "findings":
            for f in row["findings"]:
                dec[f["decision"]] += 1
                if row["occasion"] in ("C1:opus:r1", "C1:opus:r2", "C2:opus"):
                    dec_strong[f["decision"]] += 1
    m["NmatchUndecided"], m["NmatchOmitted"], m["NmatchFilled"] = undecided, dec["omitted_as_no_match"], dec["filled"]
    m["NmatchRecovered"] = dec["returned"] - decided_before
    assert m["NmatchRecovered"] + m["NmatchOmitted"] + m["NmatchFilled"] == undecided
    assert dec_strong["omitted_as_no_match"] == 0 and dec_strong["filled"] == 0   # the text says none came from Opus or C2
    opus_both = (occ["C1:opus:r1"] | occ["C1:opus:r2"]) & pid
    docname = {"P1": "Pone", "PS": "Pshort", "P2": "Ptwo", "P3": "Pthree", "P4": "Pfour", "P6": "Psix"}
    sizes = {}
    for line in (EV / "c1/opus/raw.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row.get("event") == "request" and row["cell"].endswith("_r1"):
            sizes[row["cell"].split("_")[2]] = row["prompt_chars"]
    for doc, name in docname.items():
        ids = {r["id"] for r in prim if r["doc"] == doc}
        m[f"NprimDoc{name}"] = len(ids)
        m[f"RecOpusEither{name}"] = len(opus_both & ids)
        m[f"SizeKc{name}"] = round(sizes[doc] / 1000)
    m["CtwoOnlyVsOpus"] = len((occ["C2:opus"] & pid) - opus_both)
    m["OpusOnlyVsCtwo"] = len(opus_both - occ["C2:opus"])
    c1 = set().union(*(v for k, v in occ.items() if k.startswith("C1:")))
    rep = c1 | occ["C2:opus"] | occ["C3"] | occ["C4"]
    m["RecConeAll"], m["RecConeAllPct"] = len(c1 & pid), pct(len(c1 & pid), len(pid))
    m["RecAll"], m["RecAllPct"] = len(rep & pid), pct(len(rep & pid), len(pid))
    low3 = {r["id"] for r in prim if r.get("audit_confidence") == "low"}
    assert len(low3) == 3 and all(i.startswith("P3-13") for i in low3)
    p77 = pid - low3
    m["NrefNoLowThree"] = len(p77)
    m["RecOpusANoLowPct"] = pct(len(occ["C1:opus:r1"] & p77), len(p77))
    m["RecOpusBNoLowPct"] = pct(len(occ["C1:opus:r2"] & p77), len(p77))
    m["RecConeNoLowPct"], m["RecAllNoLowPct"] = pct(len(c1 & p77), len(p77)), pct(len(rep & p77), len(p77))
    missed = [r for r in prim if r["id"] not in rep]
    m["Nmissed"] = len(missed)
    mc = collections.Counter(r["class"] for r in missed)
    for c in CLASSES:
        m[f"Missed{c.title()}"] = mc.get(c, 0)
        ids = {r["id"] for r in prim if r["class"] == c}
        m[f"ByClassCone{c.title()}"] = len(ids & c1)
        m[f"ByClassAll{c.title()}"] = len(ids & rep)
    g1 = {r["id"] for r in prim if r["severity"] == "G1"}
    m["GoneOpusA"], m["GoneOpusB"] = len(g1 & occ["C1:opus:r1"]), len(g1 & occ["C1:opus:r2"])
    m["GoneCtwo"], m["GoneCone"], m["GoneAll"] = len(g1 & occ["C2:opus"]), len(g1 & c1), len(g1 & rep)
    # the registered sensitivity analyses with the second coder's (GPT-6.1 Sol) severities and classes (v0 section 4; amendment 1)
    cbc = {x["id"]: x for x in json.loads((EV / "coder_b/coder_b.json").read_text())["coded"]}
    assert pid <= set(cbc)
    g1b = {i for i in pid if cbc[i]["severity"] == "G1"}
    m["NsevGOneB"] = len(g1b)
    m["GoneOpusAB"], m["GoneOpusBB"] = len(g1b & occ["C1:opus:r1"]), len(g1b & occ["C1:opus:r2"])
    m["GoneCtwoB"], m["GoneConeB"], m["GoneAllB"] = len(g1b & occ["C2:opus"]), len(g1b & c1), len(g1b & rep)
    ms_b = {i for i in pid if cbc[i]["class"] in ("META", "STATUS")}
    num_b = {i for i in pid if cbc[i]["class"] == "NUM"}
    m["PredOneB"], m["PredTwoB"] = f"{len(ms_b & c1) / len(ms_b):.2f}", f"{len(ms_b & occ['C2:opus']) / len(ms_b):.2f}"
    m["PredThreeRecB"] = f"{len(num_b & occ['C3']) / len(num_b):.2f}"
    m["NclassNumB"] = len(num_b)
    jud = {r["id"] for r in ref if r["source"].startswith("JUDGe")}
    m["Njudge"] = len(jud)
    for f in ("opus", "gpt", "kimi"):
        for r in (1, 2):
            m[f"Judge{FAMNAME[f]}{RUN[r]}"] = len(jud & occ[f"C1:{f}:r{r}"])
    m["JudgeCtwo"] = len(jud & occ["C2:opus"])
    adds = cap["added_items"]
    for g, w in (("G1", "One"), ("G2", "Two"), ("G3", "Three")):
        m[f"NewSevG{w}"] = sum(1 for x in adds if x["severity"] == g)
    nc = collections.Counter(x["class"] for x in adds)
    m["NewInternal"], m["NewScope"], m["NewNum"] = nc.get("INTERNAL", 0), nc.get("SCOPE", 0), nc.get("NUM", 0)
    m["NewOther"] = len(adds) - m["NewInternal"] - m["NewScope"] - m["NewNum"]
    finder = {f: sum(1 for n in new if any(n in occ[k] for k in occ if k.startswith(f"C1:{f}:"))) for f in FAMS}
    m["NewByGpt"], m["NewByKimi"], m["NewByOpus"] = finder["gpt"], finder["kimi"], finder["opus"]
    m["NewByCtwo"] = sum(1 for n in new if n in occ["C2:opus"])
    m["NewGptOnly"] = sum(1 for n in new if [k for k in occ if n in occ[k]] and all(k.startswith("C1:gpt:") for k in occ if n in occ[k]))
    cr = an["capture_recapture"]
    m["ChaoS"], m["ChaoFone"], m["ChaoFtwo"] = cr["S"], cr["f1"], cr["f2"]
    m["ChaoN"] = int(round(cr["N_hat"]))
    m["ChaoNexact"] = f"{cr['N_hat']:.1f}"
    t_occ = len(occ)
    m["ChaoT"] = t_occ
    m["ChaoNt"] = f"{cr['S'] + (t_occ - 1) / t_occ * cr['f1'] ** 2 / (2 * cr['f2']):.1f}"
    universe = pid | new
    replayed_only = chao1([occ[k] & universe for k in occ if k not in ("H1", "H2")])
    m["ChaoReplayedN"] = int(round(replayed_only["N_hat"]))
    m["ChaoReplayedS"] = replayed_only["S"]
    m["ChaoOnlyHist"] = cr["S"] - replayed_only["S"]    # known errors that only the audit or the workshop reviewer saw
    m["ChaoCover"] = pct(cr["coverage"], 1)
    m["ChaoUnseen"] = m["ChaoN"] - cr["S"]
    # the occasions as the pre-registration's text defines them (v0 section 8): the audit, C1 per family, C2, C3 and C4
    fam_occ = [occ["H2"]] + [occ[f"C1:{f}:r1"] | occ[f"C1:{f}:r2"] for f in FAMS] + [occ["C2:opus"], occ["C3"], occ["C4"]]
    crf = chao1([s & universe for s in fam_occ])
    m["ChaoFamT"], m["ChaoFamS"], m["ChaoFamFone"], m["ChaoFamFtwo"] = len(fam_occ), crf["S"], crf["f1"], crf["f2"]
    m["ChaoFamN"], m["ChaoFamNexact"] = int(round(crf["N_hat"])), f"{crf['N_hat']:.1f}"
    m["ChaoAuditN"] = len(occ["H2"] & pid)            # the audit as an occasion: the primary items it found itself
    m["ChaoFamCover"], m["ChaoFamUnseen"] = pct(crf["coverage"], 1), int(round(crf["N_hat"])) - crf["S"]
    lo, hi = chao_interval(cr["S"], cr["f1"], cr["f2"])
    m["ChaoLo"], m["ChaoHi"] = int(math.floor(lo)), int(math.ceil(hi))
    lo, hi = chao_interval(crf["S"], crf["f1"], crf["f2"])
    m["ChaoFamLo"], m["ChaoFamHi"] = int(math.floor(lo)), int(math.ceil(hi))
    # another passage of the pre-registration (v0 section 6) also lists the workshop reviewer among the occasions
    crh = chao1([s & universe for s in fam_occ + [occ["H1"]]])
    m["ChaoFamHNexact"] = f"{crh['N_hat']:.1f}"
    dup_new, dup_ref = "N-PS-K018", "PS-01"
    assert dup_new in new and dup_ref in pid and dup_ref in jud
    assert [k for k in occ if dup_new in occ[k]] == ["C1:kimi:r1"] and dup_ref not in occ["C1:kimi:r1"]
    occ_d = {k: {dup_ref if x == dup_new else x for x in v} for k, v in occ.items()}
    uni_d = pid | (new - {dup_new})
    m["NnewDedup"] = len(new - {dup_new})
    crd = chao1([occ_d[k] & uni_d for k in occ_d])
    m["ChaoDedupNexact"], m["ChaoDedupN"] = f"{crd['N_hat']:.1f}", int(round(crd["N_hat"]))
    fam_d = [occ_d["H2"]] + [occ_d[f"C1:{f}:r1"] | occ_d[f"C1:{f}:r2"] for f in FAMS] + [occ_d["C2:opus"], occ_d["C3"], occ_d["C4"]]
    crd_f = chao1([s & uni_d for s in fam_d])
    m["ChaoFamDedupNexact"], m["ChaoFamDedupN"] = f"{crd_f['N_hat']:.1f}", int(round(crd_f["N_hat"]))
    m["JudgeKimiADedup"] = len(jud & occ_d["C1:kimi:r1"])
    for x in ("N-P3-K003", "N-P3-K035", "N-P6-K018"):     # restate parts of audit items the reference set kept as one item
        assert x in new
    # second opinion, on the primary set and on the primary set plus the new items
    def pair_stats(pool):
        same = len((occ["C1:opus:r1"] | occ["C1:opus:r2"]) & pool)
        per = {}
        for f in FAMS[1:]:
            v = [len((occ[f"C1:opus:r{i}"] | occ[f"C1:{f}:r{j}"]) & pool) for i in (1, 2) for j in (1, 2)]
            per[f] = sum(v) / 4
        return same, sum(per.values()) / len(per), per
    s, mean, per = pair_stats(pid)
    m["SecSame"], m["SecCross"], m["SecCrossGpt"], m["SecCrossKimi"] = s, f"{mean:.1f}", f"{per['gpt']:.1f}", f"{per['kimi']:.1f}"
    lo = min(per[f] for f in ("deepseek", "mistral", "qwen"))
    hi = max(per[f] for f in ("deepseek", "mistral", "qwen"))
    m["SecCrossWeakLo"], m["SecCrossWeakHi"] = f"{lo:.1f}", f"{hi:.1f}"
    s2, mean2, per2 = pair_stats(pid | new)
    m["SecSameU"], m["SecCrossU"], m["SecCrossGptU"] = s2, f"{mean2:.1f}", f"{per2['gpt']:.1f}"
    preds = {p["id"]: p for p in an["predictions"]}
    m["PredOne"] = f"{preds[1]['value']:.2f}"
    m["PredTwo"] = f"{preds[2]['value']:.2f}"
    m["PredThreeRec"], m["PredThreePrec"] = f"{preds[3]['value'][0]:.2f}", floor3(preds[3]["value"][1])
    m["PredFive"] = f"{preds[5]['value']:.2f}"
    m["PredFourSame"] = preds[4]["value"]["same_family_pair"]
    m["PredFourCross"] = f"{preds[4]['value']['cross_family_pair_mean']:.1f}"
    nf = 0
    for p in (EV / "matches_filled").rglob("c[1-4]_*.json"):
        row = json.loads(p.read_text())
        if row.get("mode") == "findings":
            nf += len(row["findings"])
    m["Nfindings"] = nf
    ncl = sum(len(json.loads(p.read_text())["findings"]) for p in (EV / "clusters").glob("clusters_*.json"))
    m["NunmatchedHM"] = ncl
    spent = 0.0
    for p in list(EV.glob("c1/*/summary.json")) + list(EV.glob("c2/*/summary.json")) + list(EV.glob("matches*/*/summary.json")) + \
            [EV / x / "summary.json" for x in ("coder_b", "match_validation_set", "match_validation", "clusters", "adjudication",
                                               "smoke", "smoke_sonnet", "matches_fill_log")]:
        if p.exists():
            spent += json.loads(p.read_text())["spent_usd_upper_bound"]
    m["CostRone"] = f"{spent:.2f}"
    # the matching script changed after the hash recorded at amendment 3 (amendments 5 and 6): its final hash, as in the repository
    m["JudgingHashFinal"] = hashlib.sha256((ROOT / "scripts/r1_judging.py").read_bytes()).hexdigest()[:16]
    # R2 pilots
    papers = facts = errs = omitted = 0
    harness_papers = harness_facts = 0
    by_task = collections.Counter()
    for p in PILOT.rglob("score_*.json"):
        s = json.loads(p.read_text())
        if s.get("status") == "no_paper" or not s.get("labels"):
            continue
        papers += 1
        labs = [v["label"] for v in s["labels"].values()]
        facts += len(labs)
        if p.name.startswith("score_W2_"):      # the construction task: the harness filled the numbers and keyed claims
            harness_papers += 1
            harness_facts += len(labs)
        task = p.name.split("_")[1]               # W0: make the draft consistent with the record; N0: only update the results
        by_task[task + "papers"] += 1
        by_task[task + "facts"] += len(labs)
        errs += sum(1 for x in labs if x in ("stale", "wrong"))
        omitted += sum(1 for x in labs if x == "omitted")
    m["PilotPapers"], m["PilotFacts"], m["PilotErrors"], m["PilotOmitted"] = papers, facts, errs, omitted
    m["PilotPapersHarness"], m["PilotFactsHarness"] = harness_papers, harness_facts
    m["PilotPapersFull"], m["PilotFactsFull"] = by_task["W0papers"], by_task["W0facts"]
    m["PilotPapersNarrow"], m["PilotFactsNarrow"] = by_task["N0papers"], by_task["N0facts"]
    assert by_task["W0papers"] + by_task["N0papers"] + harness_papers == papers
    def provider_tokens(rel):
        u = json.loads((PILOT / rel).read_text())["usage"]
        return round((u.get("in", 0) + u.get("cache_read", 0) + u.get("cache_write", 0)) / 1000)
    m["PilotTokSmallGpt"] = provider_tokens("write/N0_gpt/N0_gpt_P01.json")
    m["PilotTokSmallOpus"] = provider_tokens("write/N0_opus/N0_opus_P01.json")
    m["PilotTokMidOpus"] = provider_tokens("sizes/N0_opus/N0_opus_P02.json")
    m["PilotTokLargeGpt"] = provider_tokens("sizes/N0_gpt_P03/N0_gpt_P03.json")
    pspent = 0.0
    for p in PILOT.rglob("summary.json"):
        try:
            pspent += json.loads(p.read_text())["spent_usd_upper_bound"]
        except (KeyError, json.JSONDecodeError):
            pass
    m["CostPilot"] = f"{pspent:.2f}"
    nb = json.loads((REV / "notebook_size.json").read_text())["by_freeze"]
    m["NbTokFirst"] = round(nb["P1"]["tokens_cl100k"] / 1000)
    m["NbTokLast"] = round(nb["P6"]["tokens_cl100k"] / 1000)
    m["NbCharsLast"] = round(nb["P6"]["chars"] / 1000)
    nbj = json.loads((REV / "notebook_size.json").read_text())
    largest_cl = max(v["tokens_cl100k"] for v in nbj["pilot_records"].values())
    m["PilotTokLargeCl"] = round(largest_cl / 1000)
    m["NbFreezesUnderPilot"] = sum(1 for v in nb.values() if v["tokens_cl100k"] <= largest_cl)
    opus_done = set()
    for p in PILOT.rglob("score_*_opus_*.json"):
        s = json.loads(p.read_text())
        if s.get("status") == "ok" and s.get("labels"):
            opus_done.add(s["record"])
    largest_opus = max(nbj["pilot_records"][r]["tokens_cl100k"] for r in opus_done)
    m["PilotTokLargeOpusCl"] = round(largest_opus / 1000)
    m["NbFreezesUnderPilotOpus"] = sum(1 for v in nb.values() if v["tokens_cl100k"] <= largest_opus)
    # post hoc (added during the report's review): each primary erratum's status at the freeze, coded by two fresh agents
    cons_path = REV / "freeze_status/consensus.json"
    if cons_path.exists():
        cons = {x["id"]: x["code"] for x in json.loads(cons_path.read_text())}
        assert set(cons) == pid, "the freeze-status coding must cover exactly the primary set"
        ca = {x["id"]: x["code"] for x in json.loads((REV / "freeze_status/coder_a_fable.json").read_text())}
        cb = {x["id"]: x["code"] for x in json.loads((REV / "freeze_status/coder_b_opus.json").read_text())}
        agree = sum(1 for k in pid if ca[k] == cb[k])
        pa, pb = collections.Counter(ca[k] for k in pid), collections.Counter(cb[k] for k in pid)
        pe = sum(pa[c] * pb[c] for c in set(pa) | set(pb)) / len(pid) ** 2
        m["FreezeAgree"], m["FreezeKappa"] = agree, f"{(agree / len(pid) - pe) / (1 - pe):.2f}"
        m["FreezeAdjudicated"] = len(pid) - agree
        doc = {k for k, c in cons.items() if c == "FREEZE_DOC"}
        rec = {k for k, c in cons.items() if c == "FREEZE_RECORDS"}
        later = {k for k, c in cons.items() if c == "LATER"}
        m["NfreezeDoc"], m["NfreezeRec"], m["NfreezeLater"] = len(doc), len(rec), len(later)
        for name, s in (("OpusA", occ["C1:opus:r1"]), ("OpusB", occ["C1:opus:r2"]), ("Cone", c1), ("Ctwo", occ["C2:opus"]), ("All", rep)):
            m[f"Rec{name}Doc"], m[f"Rec{name}DocPct"] = len(s & doc), pct(len(s & doc), len(doc))
            m[f"Rec{name}Rec"], m[f"Rec{name}RecPct"] = len(s & rec), pct(len(s & rec), len(rec))
        work = {r["id"] for r in prim if r["class"] in ("META", "STATUS", "PROP")}
        m["NworkClaims"], m["NworkClaimsRec"], m["NworkClaimsDoc"] = len(work), len(work & rec), len(work & doc)
        m["NworkClaimsLater"] = len(work & later)
        m["WorkRecCaught"], m["WorkDocCaught"] = len(work & rec & rep), len(work & doc & rep)
        missed_ids = {r["id"] for r in missed}
        m["MissedDoc"], m["MissedRec"], m["MissedLater"] = len(missed_ids & doc), len(missed_ids & rec), len(missed_ids & later)
        m["MissedDocGone"] = sum(1 for r in prim if r["id"] in (missed_ids & doc) and r["severity"] == "G1")
        m["MissedDocGoneB"] = len(missed_ids & doc & g1b)
        # the coding read with each coder's own array instead of the adjudicated one
        for tag, codes in (("CoderA", ca), ("CoderB", cb)):
            d_ = {k for k in pid if codes[k] == "FREEZE_DOC"}
            r_ = {k for k in pid if codes[k] == "FREEZE_RECORDS"}
            m[f"RecConeDocPct{tag}"], m[f"RecConeRecPct{tag}"] = pct(len(c1 & d_), len(d_)), pct(len(c1 & r_), len(r_))
            m[f"RecCtwoRecPct{tag}"] = pct(len(occ["C2:opus"] & r_), len(r_))
        m["MissedRecWork"] = len(missed_ids & rec & work)
        rs = json.loads((REV / "freeze_status/records_sources.json").read_text())
        assert {x["id"] for x in rs["items"]} == rec, "records_sources.json must cover exactly the records-only items"
        snap = {x["id"] for x in rs["items"] if x["in_c2_snapshot"]}
        m["NrecSnap"], m["NrecNoSnap"] = len(snap), len(rec - snap)
        m["RecCtwoRecSnap"], m["RecCtwoRecSnapPct"] = len(occ["C2:opus"] & snap), pct(len(occ["C2:opus"] & snap), len(snap))
        m["WorkRecSnap"], m["WorkRecNoSnap"] = len(work & rec & snap), len((work & rec) - snap)
        m["WorkRecSnapCtwo"] = len(work & rec & snap & occ["C2:opus"])
        m["NrecSnapRevised"] = sum(1 for x in rs["items"] if x.get("revised"))
        norm = set(rs["norm_dependent"])
        assert norm <= rec
        m["NnormDep"] = len(norm)
        # the same omissions in the class counts: no check was asked for an AI-use statement
        meta = {r["id"] for r in prim if r["class"] == "META"}
        meta_status = {r["id"] for r in prim if r["class"] in ("META", "STATUS")}
        assert norm <= meta
        m["NclassMetaNoNorm"], m["ByClassAllMetaNoNorm"] = len(meta - norm), len((meta - norm) & rep)
        m["NmissedNoNorm"] = len(missed_ids - norm)
        m["PredOneNoNorm"] = f"{len((meta_status - norm) & c1) / len(meta_status - norm):.2f}"
        m["PredTwoNoNorm"] = f"{len((meta_status - norm) & occ['C2:opus']) / len(meta_status - norm):.2f}"
        m["NfreezeRecNoNorm"] = len(rec - norm)
        m["MissedRecNoNorm"] = len((missed_ids & rec) - norm)
        m["NworkClaimsRecNoNorm"] = len((work & rec) - norm)
        m["NfreezeRecAlt"] = len(rec | later)          # if the one LATER item is read as an intention written as a fact
        m["MissedRecAlt"] = len(missed_ids & (rec | later))
    # post hoc strict re-check of the matcher (docs/r1/report_review_v2/strict_recheck/PROTOCOL.md): a check keeps an erratum only if
    # both judges (GPT-6.1 Sol and a fresh Claude Fable 5.1 agent) say one of its findings identifies that erratum
    sr = REV / "strict_recheck"
    if (sr / "verdicts_fable.json").exists() and (sr / "gpt" / "summary.json").exists():
        key = json.loads((sr / "key.json").read_text(encoding="utf-8"))
        yes = lambda v: isinstance(v, dict) and str(v.get("identifies", "")).strip().lower() == "yes"  # noqa: E731
        fable = {v["pair"]: yes(v) for v in json.loads((sr / "verdicts_fable.json").read_text(encoding="utf-8"))}
        gpt = {}
        for p in sorted((sr / "gpt").glob("strict_gpt_*.json")):
            row = json.loads(p.read_text(encoding="utf-8"))
            for q, v in zip(row["pairs"], row["verdicts"]):
                gpt[q] = yes(v)
        assert set(fable) <= set(key) and set(gpt) <= set(key)
        both = {q for q in key if fable.get(q) and gpt.get(q)}
        m["StrictPairs"] = len(key)
        m["StrictYesGpt"] = sum(1 for q in key if gpt.get(q))
        m["StrictYesFable"] = sum(1 for q in key if fable.get(q))
        m["StrictYesBoth"] = len(both)
        m["StrictJudgeAgree"] = pct(sum(1 for q in key if bool(gpt.get(q)) == bool(fable.get(q))), len(key))

        def credits(pairs_ok):
            out = collections.defaultdict(set)
            for q in pairs_ok:
                out[key[q]["occasion"]].add(key[q]["erratum"])
            return out
        strict = credits(both)
        for o, s in strict.items():
            assert s <= occ[o], o                       # the re-check can only remove credits
        s_c1 = set().union(*(s for o, s in strict.items() if o.startswith("C1:")))
        s_rep = s_c1 | strict["C2:opus"] | strict["C3"] | strict["C4"]
        groups = (("OpusA", strict["C1:opus:r1"], occ["C1:opus:r1"]), ("OpusB", strict["C1:opus:r2"], occ["C1:opus:r2"]),
                  ("Cone", s_c1, c1), ("Ctwo", strict["C2:opus"], occ["C2:opus"]), ("All", s_rep, rep))
        for name, s, _ in groups:
            m[f"StrictRec{name}"], m[f"StrictRec{name}Pct"] = len(s & pid), pct(len(s & pid), len(pid))
        kept = sum(len(s & pid) for o, s in strict.items())
        total = sum(len(occ[o] & pid) for o in occ if not o.startswith("H"))
        m["StrictKeptPct"] = pct(kept, total)
        m["StrictKept"], m["StrictCredits"] = kept, total       # credits: an erratum credited to a replayed check
        if cons_path.exists():
            for name, s, _ in groups:
                m[f"StrictRec{name}Doc"], m[f"StrictRec{name}DocPct"] = len(s & doc), pct(len(s & doc), len(doc))
                m[f"StrictRec{name}Rec"], m[f"StrictRec{name}RecPct"] = len(s & rec), pct(len(s & rec), len(rec))
            # P1-08 (a release claim) survives only through Mistral Large 3's free-text reply, which reports a 404 from the
            # repository's address: a check a checker without web access could not make
            assert {key[q]["occasion"] for q in both if key[q]["erratum"] == "P1-08" and key[q]["occasion"].startswith("C1:")} \
                == {"C1:mistral:r1"}
            pair_text = {json.loads(l)["pair"]: json.loads(l)["finding"]
                         for l in (sr / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
            assert [q for q in both if key[q]["erratum"] == "P1-08" and key[q]["occasion"].startswith("C1:")] == ["p077"]
            assert "404" in pair_text["p077"] and key["p077"]["n"] == "free_text"
            assert "P1-08" in (s_c1 & rec)
            m["StrictRecConeRecNoFab"] = len((s_c1 & rec) - {"P1-08"})
            m["StrictRecConeRecNoFabPct"] = pct(m["StrictRecConeRecNoFab"], len(rec))
            for tag, codes in (("CoderA", ca), ("CoderB", cb)):
                r_ = {k for k in pid if codes[k] == "FREEZE_RECORDS"}
                m[f"StrictRecConeRec{tag}"], m[f"NfreezeRec{tag}"] = len(s_c1 & r_), len(r_)
            for judge, ok in (("Gpt", {q for q in key if gpt.get(q)}), ("Fable", {q for q in key if fable.get(q)})):
                cj = set().union(*(s for o, s in credits(ok).items() if o.startswith("C1:")))
                m[f"StrictRecConeDocPct{judge}"] = pct(len(cj & doc), len(doc))
                m[f"StrictRecConeRecPct{judge}"] = pct(len(cj & rec), len(rec))
        m["StrictByClassConeInternal"] = len(s_c1 & {r["id"] for r in prim if r["class"] == "INTERNAL"})
        ms = {r["id"] for r in prim if r["class"] in ("META", "STATUS")}
        m["StrictPredOne"] = f"{len(s_c1 & ms) / len(ms):.2f}"
        m["StrictPredTwo"] = f"{len(strict['C2:opus'] & ms) / len(ms):.2f}"
        m["StrictGoneOpusA"], m["StrictGoneOpusB"] = len(strict["C1:opus:r1"] & g1), len(strict["C1:opus:r2"] & g1)
        m["StrictGoneCtwo"], m["StrictGoneAll"] = len(strict["C2:opus"] & g1), len(s_rep & g1)
        for f in ("opus", "gpt", "kimi"):
            for r in (1, 2):
                m[f"StrictJudge{FAMNAME[f]}{RUN[r]}"] = len(strict[f"C1:{f}:r{r}"] & jud)
        m["StrictJudgeCtwo"] = len(strict["C2:opus"] & jud)
        assert m["StrictJudgeOpusA"] == m["StrictJudgeOpusB"]       # the abstract states one number for both runs
        m["StrictJudgeAny"] = len(s_rep & jud)
        # strict precision: a high/medium finding is real if one of its matches survived, or (unmatched) its cluster is a new error
        strict_found = collections.defaultdict(set)
        for q in both:
            strict_found[key[q]["cell"]].add(key[q]["n"])
        s_real, s_all = collections.Counter(), collections.Counter()
        for p in sorted((EV / "matches_filled").rglob("c[1-4]_*.json")):
            row = json.loads(p.read_text(encoding="utf-8"))
            if row.get("mode") != "findings":
                continue
            for f in row["findings"]:
                if not (row["occasion"] in ("C3", "C4") or severity_of(f) in CHECKER_SEVERITY_KEPT):
                    continue
                s_all[row["occasion"]] += 1
                if f["n"] in strict_found[row["cell"]] or (not f.get("matches") and
                                                           both_yes.get(member_of.get(f"{row['cell']}#{f['n']}"))):
                    s_real[row["occasion"]] += 1
        for o in s_all:
            assert s_all[o] == split[o]["findings"] and s_real[o] <= split[o]["matched"] + split[o]["new"], o
        for f in FAMS:
            for r in (1, 2):
                o = f"C1:{f}:r{r}"
                m[f"PrecStrict{FAMNAME[f]}{RUN[r]}"] = floor2(s_real[o] / s_all[o])
        m["PrecStrictCtwo"] = floor2(s_real["C2:opus"] / s_all["C2:opus"])
        m["PrecStrictCthreeK"], m["PrecStrictCfourK"] = s_real["C3"], s_real["C4"]
        a_, b_ = m["StrictRecOpusAPct"], m["StrictRecOpusBPct"]
        m["StrictRecOpusRange"] = a_ if a_ == b_ else f"{min(a_, b_, key=int)}--{max(a_, b_, key=int)}"
        # Chao with the strict credits: the historical occasions and the new errors' captures are unchanged
        crs = chao1([(occ[o] if o.startswith("H") else strict[o] | (occ[o] & new)) & universe for o in occ])
        m["StrictChaoNexact"] = f"{crs['N_hat']:.1f}"
    # appendix: registered measures (v0 section 8) not discussed in the text: recall by document for every check, Jaccard overlaps,
    # and Chao's estimate by class (all occasions, as in the main estimate; a new error has the Opus adjudicator's class)
    doc_checks = [(f"{FAMNAME[f]}{RUN[r]}", occ[f"C1:{f}:r{r}"]) for f in FAMS for r in (1, 2)] + \
        [("Cone", c1), ("Ctwo", occ["C2:opus"]), ("Cthree", occ["C3"]), ("Cfour", occ["C4"]), ("All", rep)]
    for name, s in doc_checks:
        for doc, dn in docname.items():
            m[f"DocRec{name}{dn}"] = len(s & {r["id"] for r in prim if r["doc"] == doc})

    def jac(x, y):
        x, y = x & pid, y & pid
        return f"{len(x & y) / len(x | y):.2f}"
    m["JacOpusRuns"] = jac(occ["C1:opus:r1"], occ["C1:opus:r2"])
    m["JacOpusCtwo"] = jac(opus_both, occ["C2:opus"])
    m["JacOpusGpt"] = jac(opus_both, occ["C1:gpt:r1"] | occ["C1:gpt:r2"])
    m["JacConeCtwo"] = jac(c1, occ["C2:opus"])
    m["JacConeCtwoInter"], m["JacConeCtwoUnion"] = len(c1 & occ["C2:opus"] & pid), len((c1 | occ["C2:opus"]) & pid)
    cls_of = {r["id"]: r["class"] for r in prim} | {x["id"]: x["class"] for x in adds}
    for c in CLASSES:
        ids = {i for i in universe if cls_of.get(i) == c}
        crc = chao1([s & ids for s in occ.values()])
        m[f"ChaoClass{c.title()}S"], m[f"ChaoClass{c.title()}N"] = crc["S"], f"{crc['N_hat']:.1f}"
        m[f"ChaoClass{c.title()}Cover"] = pct(crc["coverage"], 1)
    lines = ["% Generated by scripts/r1_report_numbers.py from the archived evidence. Do not edit by hand."]
    for k in sorted(m):
        lines.append(f"\\newcommand{{\\{k}}}{{{m[k]}}}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(m)} macros written to {a.out}")


if __name__ == "__main__":
    main()
