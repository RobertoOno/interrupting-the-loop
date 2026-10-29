#!/usr/bin/env python3
"""Paper 6 tables, generated from the single-read JSON files of each node so that no number is typed by hand.
  python3 scripts/paper6_tables.py            -> paper6/tables/*.tex
Sources: docs/a2c_results/consolidation.json, docs/a2c2_results/{consolidation,e8_same_config}.json, docs/a2c3_results/own.json,
docs/a2c4_results/own2.json, docs/a7_results/{screen,confirm}.json, docs/a8_results/{narrow,narrow_c}.json, docs/a9_results/read.json,
docs/a9_results/w5_routes.json, docs/a6_results/report.json."""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; OUT = ROOT / "paper6/tables"; OUT.mkdir(parents=True, exist_ok=True)
STEPS = ["L1", "L2", "L3", "L4", "L5", "E"]; WALLS = ["W1", "W2", "W3", "W4"]
load = lambda p: json.load(open(ROOT / p))
UP, DOWN = r"$\uparrow$", r"$\downarrow$"


def kn(t): return f"{t['k']}/{t['n']}"
def pf(x): return f"{x:.3f}"
def diff(c, pkey="p"):
    d = c["mean_rate_diff"]; return f"{d:+.2f} ($p={pf(c[pkey])}$)"
def write(name, body):
    (OUT / name).write_text(body); print("wrote", name)


def curated():
    r1, r2 = load("docs/a2c_results/consolidation.json"), load("docs/a2c2_results/consolidation.json")
    L = [r"\begin{tabular}{l" + "c" * 6 + "}", r"\toprule", "arm & " + " & ".join(STEPS) + r" \\", r"\midrule"]
    for label, r in (("round 1 (13--14 September)", r1), ("replication, new instances and adapters (14 September)", r2)):
        L.append(r"\multicolumn{7}{l}{\emph{" + label + r"}} \\")
        for arm, name in (("base", "base, no thinking"), ("p1", "p1: form of E/L5 (96 examples)"), ("p2", "p2: six forms (288)"), ("p3", "p3: syntax control (288)")):
            cells = [kn(r["rates"][arm][s]) + (UP if arm != "base" and r["rises"][arm][s] else "") for s in STEPS]
            L.append(f"{name} & " + " & ".join(cells) + r" \\")
        L.append(r"\midrule")
    L[-1] = r"\bottomrule"; L.append(r"\end{tabular}")
    write("curated.tex", "\n".join(L) + "\n")


def e8():
    e = load("docs/a2c2_results/e8_same_config.json"); rates, con = e["rates"], e["contrasts"]
    rows = (("base", "base", "off", "0.7 / 0.8", "16k"), ("basen", "base", "off", "1.0 / 0.95", "131k"), ("baset", "base", "on", "1.0 / 0.95", "131k"),
            ("p2", "p2", "off", "0.7 / 0.8", "16k"), ("p2n", "p2", "off", "1.0 / 0.95", "131k"), ("p2t", "p2", "on", "1.0 / 0.95", "131k"))
    L = [r"\begin{tabular}{llcccc}", r"\toprule", r"arm & weights & thinking & $T$ / top-$p$ & budget & L2 \quad L3 \\", r"\midrule"]
    for key, w, th, samp, bud in rows:
        L.append(f"{key} & {w} & {th} & {samp} & {bud} & {kn(rates[key]['L2'])} \\quad {kn(rates[key]['L3'])} " + r"\\")
    L += [r"\midrule", r"\multicolumn{6}{l}{\emph{paired contrasts (rate difference, sign-flip $p$)}} \\"]
    for name, lab in (("p2t_vs_p2n", "p2t $-$ p2n (thinking, same configuration)"), ("p2n_vs_p2", "p2n $-$ p2 (configuration alone)"),
                      ("baset_vs_basen", "baset $-$ basen (thinking, no form)"), ("p2t_vs_baset", "p2t $-$ baset (form, both thinking)")):
        L.append(r"\multicolumn{5}{l}{" + lab + "} & " + diff(con["L2"][name]) + r" \quad " + diff(con["L3"][name]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("e8.tex", "\n".join(L) + "\n")


def loop():
    o1, o2 = load("docs/a2c3_results/own.json"), load("docs/a2c4_results/own2.json")
    L = [r"\begin{tabular}{l" + "c" * 6 + "}", r"\toprule", "arm & " + " & ".join(STEPS) + r" \\", r"\midrule", r"\multicolumn{7}{l}{\emph{no thinking (16{,}384 tokens, $T$ 0.7)}} \\"]
    plain = (("base", o2, "base"), ("own", o1, "own: 60 own proofs of L1--L3 (iteration 1)"), ("curm", o1, "curm: the reference proofs of the same 60 cells"),
             ("own2", o2, "own2: 135 own proofs, cumulative (iteration 2)"), ("curm2", o2, "curm2: the reference proofs of the same 135 cells"), ("p2", o2, "p2: reference proofs of all six steps (288)"))
    for key, src, name in plain:
        L.append(f"{name} & " + " & ".join(kn(src["rates"][key][s]) if s in src["rates"][key] else "--" for s in STEPS) + r" \\")
    L += [r"\midrule", r"\multicolumn{7}{l}{\emph{thinking (131{,}072 tokens, $T$ 1.0)}} \\"]
    think = (("baset", o2, "base"), ("ownt", o1, "own (iteration 1)"), ("curmt", o1, "curm"), ("own2t", o2, "own2 (iteration 2)"), ("curm2t", o2, "curm2"), ("p2t", o2, "p2"))
    for key, src, name in think:
        L.append(f"{name} & " + " & ".join(kn(src["rates"][key][s]) if s in src["rates"][key] else "--" for s in STEPS) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("loop.tex", "\n".join(L) + "\n")
    # the contrasts that carry the verdicts
    c1, c2 = o1["contrasts"], o2["contrasts"]
    g = lambda c, s, n: f"{c[s][n]['mean_rate_diff']:+.2f} ($p={pf(c[s][n]['p_greater'])}$)"
    L = [r"\begin{tabular}{lll}", r"\toprule", r"contrast & step & rate difference \\", r"\midrule",
         f"own $-$ base (no thinking) & L1 & {g(c1, 'L1', 'own_vs_base')}" + r" \\",
         f"ownt $-$ baset & L2 & {g(c1, 'L2', 'ownt_vs_baset')}" + r" \\", f"ownt $-$ baset & L3 & {g(c1, 'L3', 'ownt_vs_baset')}" + r" \\",
         f"ownt $-$ p2t & L2 & {g(c1, 'L2', 'ownt_vs_p2t')}" + r" \\", f"ownt $-$ p2t & L3 & {g(c1, 'L3', 'ownt_vs_p2t')}" + r" \\",
         f"curm $-$ own (no thinking) & L3 & {g(c1, 'L3', 'curm_vs_own')}" + r" \\", r"\midrule",
         f"own2 $-$ base (no thinking) & L5 & {g(c2, 'L5', 'own2_vs_base')}" + r" \\", f"own2 $-$ base (no thinking) & E & {g(c2, 'E', 'own2_vs_base')}" + r" \\",
         f"own2t $-$ baset & L4 & {g(c2, 'L4', 'own2t_vs_baset')}" + r" \\", f"own2t $-$ baset & L5 & {g(c2, 'L5', 'own2t_vs_baset')}" + r" \\", f"own2t $-$ baset & E & {g(c2, 'E', 'own2t_vs_baset')}" + r" \\",
         f"curm2 $-$ own2 (no thinking) & L3 & {g(c2, 'L3', 'curm2_vs_own2')}" + r" \\", f"curm2 $-$ own2 (no thinking) & L4 & {g(c2, 'L4', 'curm2_vs_own2')}" + r" \\",
         r"\bottomrule", r"\end{tabular}"]
    write("loop_contrasts.tex", "\n".join(L) + "\n")


def walls():
    s, c = load("docs/a7_results/screen.json"), load("docs/a7_results/confirm.json")
    names = {"W1": "W1 Pell form modulo a prime", "W2": "W2 plane lattice (trap)", "W3": "W3 hyperbolic form, four fields", "W4": "W4 large prime"}
    L = [r"\begin{tabular}{lcccl}", r"\toprule", r"candidate & base & base + sibling proof & own2 & class \\", r"\midrule"]
    for w in WALLS:
        d = s["candidates"][w]
        L.append(f"{names[w]} & {kn(d['base_none'])} & {kn(d['base_ref'])} & {kn(d['own2_none'])} & " + d["class"].replace("_", r"\_") + r" \\")
    w1 = c["walls"]["W1"]
    L += [r"\midrule", r"\multicolumn{5}{l}{\emph{confirmation of W1, six new instances}} \\",
          f"W1 & {kn(w1['base_none'])} & {kn(w1['base_ref'])} & {kn(w1['own2_none'])} & " + w1["verdict"].replace("_", r"\_") + r" \\",
          r"\multicolumn{5}{l}{curm2, the template adapter (descriptive, cut by the guard): " + kn(w1["curm2_none"]) + "; own2 $-$ base " + f"{w1['own2_vs_base']['mean_rate_diff']:+.2f} ($p={pf(w1['own2_vs_base']['p'])}$)" + r"} \\",
          r"\bottomrule", r"\end{tabular}"]
    write("walls.tex", "\n".join(L) + "\n")


def a8():
    n0, n = load("docs/a8_results/narrow.json"), load("docs/a8_results/narrow_c.json")
    L = [r"\begin{tabular}{lcccccc}", r"\toprule", r"family & base & own2 & curm2 (template) & own2 $-$ base & curm2 $-$ base & own2 $-$ curm2 \\", r"\midrule"]
    for w in WALLS:
        f = n["families"][w]; f0 = n0["families"][w]
        def c(x):
            d = x["mean_rate_diff"]; m = UP if x["rise"] else (DOWN if x["fall"] else ""); pv = x["p_fall"] if x["fall"] or d < 0 else x["p_rise"]
            return f"{d:+.2f} ($p={pf(pv)}$){m}"
        L.append(f"{w} & {kn(f['base'])} & {kn(f['own2'])} & {kn(f['curm2'])} (node read {kn(f0['curm2'])}) & {c(f['own2_vs_base'])} & {c(f['curm2_vs_base'])} & {c(f['own2_vs_curm2'])}" + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("a8.tex", "\n".join(L) + "\n")


def a9():
    r = load("docs/a9_results/read.json"); routes = load("docs/a9_results/w5_routes.json")
    def c(b):
        x = b["contrast"]
        if not x.get("n_instances"): return "--"
        d = x["mean_rate_diff"]; m = UP if x["rise"] else (DOWN if x["fall"] else ""); pv = x["p_fall"] if x["fall"] or d < 0 else x["p_rise"]
        return f"{d:+.2f} ($p={pf(pv)}$){m}"
    L = [r"\begin{tabular}{lccccl}", r"\toprule", r"block & own3 & own2 & base & own3 $-$ own2 & note \\", r"\midrule"]
    t = r["W5_thinking"]; L.append(f"W5, thinking (primary) & {kn(t['own3_vs_own2']['x'])} & {kn(t['own3_vs_own2']['y'])} & {kn(t['own3_vs_base']['y'])} & {c(t['own3_vs_own2'])} & own3 $-$ base {c(t['own3_vs_base'])}" + r" \\")
    u = r["W5_no_thinking"]["own3_vs_own2"]; L.append(f"W5, no thinking & {kn(u['x'])} & {kn(u['y'])} & -- & {c(u)} & " + r"\\")
    for w in WALLS:
        b = r["walls_no_thinking"][w]; L.append(f"{w} new instances, no thinking & {kn(b['own3_vs_own2']['x'])} & {kn(b['own3_vs_own2']['y'])} & {kn(b['own3_vs_base']['y'])} & {c(b['own3_vs_own2'])} & " + r"\\")
    for w in WALLS:
        b = r["walls_thinking"][w]["own3_vs_own2"]; L.append(f"{w} new instances, thinking & {kn(b['x'])} & {kn(b['y'])} & -- & {c(b)} & " + r"\\")
    for s in STEPS:
        b = r["ladder_no_thinking"][s]["own3_vs_own2"]; L.append(f"ladder {s}, retention, no thinking & {kn(b['x'])} & {kn(b['y'])} (16 Sept.) & -- & {c(b)} & " + r"\\")
    a = routes["arms"]
    L += [r"\midrule", r"\multicolumn{6}{l}{W5 solved by the intended route (quadratic form modulo $p$), post hoc: base " + f"{a['a9_w5base_v1']['solved_intended']}/18, own2 {a['a9_w5own2_v1']['solved_intended']}/18, own3 {a['a9_w5own3_v1']['solved_intended']}/18" + r"} \\",
          r"\bottomrule", r"\end{tabular}"]
    write("a9.tex", "\n".join(L) + "\n")


def a6():
    rep = load("docs/a6_results/report.json"); per = rep["per_condition_step"]
    def q3(x):
        if x is None: return "--"
        if x[0] == x[2] and x[1] >= 0.97: return r"$\geq$0.98 (sat.)"   # every session of every instance has the type: the smoothing floor, not an estimate
        if x[0] == x[2] and x[1] <= 0.03: return r"$\leq$0.02 (sat.)"
        return f"{x[1]:.2f} [{x[0]:.2f}, {x[2]:.2f}]"
    rows = [("A2 replication, no thinking", [("a2c2_base_v1", "base", s) for s in STEPS] + [("a2c2_p2_v1", "p2", s) for s in STEPS]),
            ("thinking (E8)", [("a2c2_basen131_v1", "basen", s) for s in ("L2", "L3")] + [("a2c2_baset131_v1", "baset", s) for s in ("L2", "L3")] + [("a2c2_p2n131_v1", "p2n", s) for s in ("L2", "L3")] + [("a2c2_p2t131_v1", "p2t", s) for s in ("L2", "L3")]),
            ("iteration 2, L4", [("a2c4_own2_v1", "own2 (no thinking)", "L4"), ("a2c4_curm2_v1", "curm2, template (no thinking)", "L4"), ("a2c4_own2t131_v1", "own2, thinking", "L4"), ("a2c4_baset131_v1", "base, thinking", "L4")]),
            ("walls (A8, thinking; template arm complete)", [("a8_base_v1", "base", w) for w in WALLS] + [("a8_own2_v1", "own2", w) for w in WALLS] + [("a8c_curm2_v1", "curm2", w) for w in WALLS]),
            ("W5 (A9, thinking)", [("a9_w5base_v1", "base", "W5"), ("a9_w5own2_v1", "own2", "W5"), ("a9_w5own3_v1", "own3", "W5")]),
            ("new wall instances (A9, thinking)", [("a9_own2t_v1", "own2", w) for w in WALLS] + [("a9_own3t_v1", "own3", w) for w in WALLS])]
    L = [r"\begin{tabular}{llccccc}", r"\toprule", r"condition & step & $n$ & solved & $\pi$ & $\theta_{\text{right}}$ & $\theta_{\text{wrong}}$ \\", r"\midrule"]
    for title, items in rows:
        L.append(r"\multicolumn{7}{l}{\emph{" + title + r"}} \\")
        for arm, name, s in items:
            v = per.get(f"{arm}|{s}")
            if v is None: continue
            L.append(f"{name} & {s} & {v['n']} & {v['solved']} & {q3(v['pi'])} & {q3(v['theta_right'])} & {q3(v['theta_wrong'])}" + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("a6.tex", "\n".join(L) + "\n")
    Q = rep["questions"]
    def fq(x):
        if x is None: return "--"
        if x[0] == x[2]:   # both cells saturated: the clamp of the smoothing, not a measured difference
            return ("$>$+7" if x[1] > 7 else "$<-$7" if x[1] < -7 else "0") + " (sat.)"
        return f"{x[1]:+.2f} [{x[0]:+.2f}, {x[2]:+.2f}]"
    L = [r"\begin{tabular}{llccc}", r"\toprule", r"contrast & step & $\Delta\,\mathrm{logit}\,\pi$ & $\Delta\,\mathrm{logit}\,\theta_{\text{right}}$ & $\Delta\,\mathrm{logit}$ rate \\", r"\midrule"]
    labels = {"Q1 replication p2 vs base, no thinking (A2 replica)": "p2 $-$ base, no thinking (replication)", "Q2 A8 own2 vs base, thinking": "own2 $-$ base, walls, thinking",
              "Q2 A8 curm2 vs base, thinking": "curm2 $-$ base, walls, thinking", "Q2 A8 own2 vs curm2, thinking": "own2 $-$ curm2, walls, thinking",
              "Q3 L4: own2 vs curm2, no thinking (iteration 2)": "own2 $-$ curm2, L4, no thinking", "Q3 L4: own2t131 vs baset131 (iteration 2)": "own2 $-$ base, L4, thinking",
              "Q4 thinking given the form: p2t131 vs p2n131 (same config but thinking)": "p2t $-$ p2n (thinking given the form)", "Q4 thinking without the form: baset131 vs basen131": "baset $-$ basen (thinking without the form)"}
    for qk, lab in labels.items():
        for s, cq in Q[qk].items():
            L.append(f"{lab} & {s} & {fq(cq['dlogit_pi'])} & {fq(cq['dlogit_theta_right'])} & {fq(cq['dlogit_rate'])}" + r" \\")
        L.append(r"\midrule")
    L[-1] = r"\bottomrule"; L.append(r"\end{tabular}")
    write("a6_contrasts.tex", "\n".join(L) + "\n")


def coverage():
    """Instances with at least one solve at the attempts available (support at small k), from the per-session table of A6."""
    import collections
    rows = [json.loads(l) for l in (ROOT / "docs/a6_results/sessions.jsonl").read_text().splitlines() if l.strip()]
    def cov(node, arm, step):
        by = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            if r["node"] == node and r["arm"] == arm and r["step"] == step:
                by[r["instance"]][0] += 1; by[r["instance"]][1] += r["solved"]
        ks = sorted({v[0] for v in by.values()}) if by else [0]
        return f"{sum(1 for v in by.values() if v[1] > 0)}/{len(by)}", (str(ks[0]) if len(ks) == 1 else f"{ks[0]}--{ks[-1]}")
    blocks = [("W1 (A7 confirmation)", [("base", "a7_confirm", "a7c_base_v1"), ("own2", "a7_confirm", "a7c_own2_v1"), ("base + sibling proof", "a7_confirm", "a7c_ref_v1"), ("curm2, template (cut short)", "a7_confirm", "a7c_curm2_v1")], ["W1"]),
              ("W1--W4 (A8)", [("base", "a8", "a8_base_v1"), ("own2", "a8", "a8_own2_v1"), ("curm2", "a8c", "a8_curm2_v1")], WALLS),
              ("W1--W4, fresh instances (A9)", [("own2", "a9", "a9_own2t_v1"), ("own3", "a9", "a9_own3t_v1")], WALLS),
              ("W5 (A9)", [("base", "a9", "a9_w5base_v1"), ("own2", "a9", "a9_w5own2_v1"), ("own3", "a9", "a9_w5own3_v1")], ["W5"]),
              ("ladder, thinking (iteration 2)", [("base", "a2c4", "a2c4_baset131_v1"), ("own2", "a2c4", "a2c4_own2t131_v1"), ("curm2", "a2c4", "a2c4_curm2t131_v1")], ["L4", "L5", "E"])]
    L = [r"\begin{tabular}{llll}", r"\toprule", r"block & arm & attempts per instance & instances with at least one solve \\", r"\midrule"]
    for title, arms, steps in blocks:
        for lab, node, arm in arms:
            cells = []; ks = set()
            for s in steps:
                c, k = cov(node, arm, s); cells.append(f"{s} {c}"); ks.add(k)
            L.append(f"{title} & {lab} & {'/'.join(sorted(ks))} & " + ", ".join(cells) + r" \\")
        L.append(r"\midrule")
    L[-1] = r"\bottomrule"; L.append(r"\end{tabular}")
    write("coverage.tex", "\n".join(L) + "\n")


if __name__ == "__main__":
    curated(); e8(); loop(); walls(); a8(); a9(); a6(); coverage()
