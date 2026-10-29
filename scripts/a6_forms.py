#!/usr/bin/env python3
"""A6 — the prior over forms (docs/A6_PRIOR_SOBRE_FORMAS_V1.md). No model calls, no GPU: reads the evidence archives.

  table   --out docs/a6_results/sessions.jsonl         one row per OBSERVED prover session of Qwen3.8-27B (base and adapters): node, arm,
          model, thinking, example arm, step, instance, attempt, solved, submissions, the invariant TYPE declared by the first submission
          (linear | linear_mod | quad_diag | quad_mixed | quad_mod | none), the types over all submissions, right type (per step), tokens.
  sample  --table ... --n 60 --out docs/a6_results/validation_sample.jsonl     stratified sample (seed 20260919) printed WITHOUT the
          classifier's label, to be labelled by reading.
  score   --sample ... --labels docs/a6_results/validation_labels.json          agreement between hand labels and the classifier.
The classifier is heuristic: state-field accessors (s.x ...) or destructured field names, products of two factors that both contain a
field (different fields = mixed, the same = diagonal), a field factor raised to a power (diagonal), modular/divisibility markers.
"""
from __future__ import annotations
import argparse, collections, json, random, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from analysis_a1 import NOT_OBSERVED  # noqa: E402
from a8_invariant_attempts import _factor_left, _factor_right  # noqa: E402

ARCHIVES = ["a2c_evidence_v1", "a2c2_evidence_v1", "a2c2_e8_evidence_v1", "a2c3_evidence_v1", "a2c4_evidence_v1", "a2m_evidence_v1", "a7_screen_evidence_v1",
            "a7_confirm_evidence_v1", "a8_evidence_v1", "a8c_evidence_v1", "a9_evidence_v1"]
NEEDED = {"L1": "linear", "L2": "linear", "L3": "linear_mod", "L4": "quad_mixed", "L5": "quad_mixed", "E": "quad_diag",
          "W1": "quad_mod", "W2": "linear_mod", "W3": "quad_mixed", "W4": "linear_mod", "W5": "quad_mod"}
CLASSES = ["linear", "linear_mod", "quad_diag", "quad_mixed", "quad_mod", "none"]
MOD = re.compile(r"ZMod|ZMOD|ModEq|≡|emod|\bmod\b|%|∣|Dvd|dvd")   # ZMOD/≡ added after validation round 1 (item 1)
ACC = re.compile(r"\b[a-z]\w*\.([xyzw])\b")
BARE = re.compile(r"(?<![\w.])([xyzw])(?![\w.(])")
DESTRUCT = re.compile(r"⟨\s*x\s*,\s*y|\bmk\s+x\s+y\b")


def strip_comments(src: str) -> str:
    return re.sub(r"--.*$", "", re.sub(r"/-.*?-/", "", src, flags=re.S), flags=re.M)


def fields_in(text: str, bare: bool) -> set[str]:
    f = {m.group(1) for m in ACC.finditer(text)}
    if bare:
        f |= {m.group(1) for m in BARE.finditer(text)}
    return f


def classify(src: str | None) -> str:
    """Type of the invariant the submission declares. The invariant text is, in this order: the right-hand sides of the functions of the
    state it defines (any name); if there is none, the statements of its declarations that speak of invariance (move, Step, Reaches); if
    there is none either, the whole body. Products and modular markers are read from that text only, so that the algebra of an invariance
    PROOF (squares of moved coordinates) and the modular case analysis of the final contradiction do not change the class."""
    if not src:
        return "none"
    s = strip_comments(src); bare = bool(DESTRUCT.search(s))
    body = "\n".join(l for l in s.splitlines() if not re.match(r"\s*(def move\d|structure |inductive |\|\s*(first|second|third|fourth)\b|deriving|import |open |set_option|namespace |end )", l)
                     and not re.match(r"\s*(x|y|z|w)\s*:\s*Int", l))
    if not fields_in(body, bare):
        return "none"
    defs, stmts = invariant_texts(body)
    text = "\n".join(defs) if defs else ("\n".join(stmts) if stmts else body)
    modtext = "\n".join(defs + stmts) if (defs or stmts) else body
    mixed = diag = False
    for line in text.splitlines():
        for k, ch in enumerate(line):
            if ch == "*":
                a, b = fields_in(_factor_left(line, k), bare), fields_in(_factor_right(line, k), bare)
                if a and b:
                    if a != b:
                        mixed = True
                    else:
                        diag = True
            elif ch == "^" and fields_in(_factor_left(line, k), bare):
                diag = True
    mod = bool(MOD.search(modtext))
    if mixed or diag:
        return "quad_mod" if mod else ("quad_mixed" if mixed else "quad_diag")
    return "linear_mod" if mod else "linear"


DECL = re.compile(r"^\s*(private\s+|noncomputable\s+)?(def|lemma|theorem|have|let|abbrev)\b")
STATEDEF = re.compile(r"\b(def|let|have|abbrev)\s+(\w+)\s*(\(\s*\w+\s*:\s*State\s*\)|:\s*State\s*→)")


def invariant_texts(body: str) -> tuple[list[str], list[str]]:
    """(right-hand sides of state-function definitions, statements of declarations that speak of invariance)."""
    lines = body.splitlines(); i = 0; defs, stmts = [], []
    while i < len(lines):
        if DECL.match(lines[i]):
            stmt = lines[i]; j = i
            while ":=" not in stmt and j + 1 < len(lines) and not DECL.match(lines[j + 1]) and j - i < 12:
                j += 1; stmt += "\n" + lines[j]
            if STATEDEF.search(stmt) and ":=" in stmt:
                rhs = stmt.split(":=", 1)[1]; k = j
                while k + 1 < len(lines) and not DECL.match(lines[k + 1]) and lines[k + 1].strip() and k - j < 6:
                    k += 1; rhs += "\n" + lines[k]
                if not re.match(r"\s*by\b", rhs):
                    defs.append(rhs)
                j = k
            else:
                head = stmt.split(":=")[0]
                two_states = len({m.group(0).split(".")[0] for m in ACC.finditer(head)}) >= 2   # s.x ... t.x: a relation between two states (validation round 1, item 34)
                if (re.search(r"\bmove\d|\bStep\b|\bReaches\b", head) or two_states) and "evaluation_solution" not in head:
                    stmts.append(head)
            i = j + 1
        else:
            i += 1
    return defs, stmts


def sessions():
    for arch in ARCHIVES:
        root = ROOT / "docs" / arch
        if not root.exists():
            continue
        for arm in sorted(d for d in root.iterdir() if d.is_dir() and d.name != "analysis" and "aborted" not in d.name):
            for d in sorted(x for x in arm.iterdir() if x.is_dir() and ".failed" not in x.name and ".interrupted" not in x.name and (x / "result.json").exists()):
                R = json.loads((d / "result.json").read_text()); r, cell = R["result"], R["cell"]
                if r.get("status") in NOT_OBSERVED or r.get("mode") != "prover":
                    continue
                cfg = json.loads((d / "input.json").read_text()).get("config", {}) if (d / "input.json").exists() else {}
                model = cfg.get("model", "?")
                if not (model.startswith("qwen3.8") or model.startswith("a2c") or model.startswith("a9")):
                    continue
                think = bool(((cfg.get("extra_body") or {}).get("chat_template_kwargs") or {}).get("enable_thinking", False))
                ev = d / "events.jsonl"
                srcs = [e.get("source") or "" for e in (json.loads(l) for l in ev.open() if l.strip()) if e.get("event") == "verification"] if ev.exists() else []
                forms = [classify(x) for x in srcs]; first = forms[0] if forms else "none"; need = NEEDED.get(cell["step"])
                yield {"node": arch.replace("_evidence_v1", ""), "arm": arm.name, "model": model, "thinking": think, "example": cell.get("arm"), "step": cell["step"],
                       "instance": cell["instance"], "attempt": cell.get("attempt"), "cell": d.name, "solved": bool(r.get("target_solved")), "status": r.get("status"),
                       "submissions": len(srcs), "form_first": first, "forms_any": sorted(set(forms)), "right_first": first == need, "right_any": need in forms,
                       "tokens_out": int((r.get("tokens") or {}).get("output_tokens", 0))}


def cmd_table(a):
    rows = list(sessions()); a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    c = collections.Counter((r["node"], r["arm"]) for r in rows)
    print(json.dumps({"sessions": len(rows), "arms": len(c), "by_form_first": dict(collections.Counter(r["form_first"] for r in rows))}))
    for (node, arm), n in sorted(c.items()):
        sub = [r for r in rows if r["node"] == node and r["arm"] == arm]
        print(f"{node:12s} {arm:28s} n={n:4d} model={sub[0]['model']:12s} think={int(sub[0]['thinking'])} solved={sum(r['solved'] for r in sub):4d} right_first={sum(r['right_first'] for r in sub):4d}")


def first_source(row) -> str:
    root = ROOT / "docs" / (row["node"] + "_evidence_v1") / row["arm"] / row["cell"] / "events.jsonl"
    for l in root.open():
        if l.strip():
            e = json.loads(l)
            if e.get("event") == "verification":
                return e.get("source") or ""
    return ""


def cmd_sample(a):
    rows = [json.loads(l) for l in a.table.read_text().splitlines() if l.strip()]; rng = random.Random(a.seed)
    seen = {json.loads(l)["cell"] for f in a.exclude for l in f.read_text().splitlines() if l.strip()}; rows = [r for r in rows if r["cell"] not in seen]
    strata = collections.defaultdict(list)
    for r in rows:
        if r["submissions"]:
            strata[(r["node"], r["arm"], r["step"])].append(r)
    keys = sorted(strata); rng.shuffle(keys); picked = [rng.choice(strata[k]) for k in keys[: a.n]]
    a.out.write_text("".join(json.dumps({"id": i, **{k: r[k] for k in ("node", "arm", "cell", "step")}}) + "\n" for i, r in enumerate(picked)))
    for i, r in enumerate(picked):
        src = strip_comments(first_source(r)); keep = [l.rstrip() for l in src.splitlines() if re.search(r"\b(def|let|have|lemma|theorem|abbrev)\b", l) or ACC.search(l)]
        print(f"#{i} [{r['step']}]"); print("\n".join("   " + l[:150] for l in keep[: a.lines]))


def cmd_score(a):
    sample = [json.loads(l) for l in a.sample.read_text().splitlines() if l.strip()]; labels = json.loads(a.labels.read_text())
    table = {(r["node"], r["arm"], r["cell"]): r for r in (json.loads(l) for l in a.table.read_text().splitlines() if l.strip())}
    agree = dis = 0; out = []
    for s in sample:
        hand = labels.get(str(s["id"]));
        if hand is None:
            continue
        auto = table[(s["node"], s["arm"], s["cell"])]["form_first"]; ok = hand == auto; agree += ok; dis += not ok
        if not ok:
            out.append({"id": s["id"], "step": s["step"], "cell": s["cell"], "arm": s["arm"], "hand": hand, "auto": auto})
    res = {"labelled": agree + dis, "agree": agree, "agreement": agree / max(1, agree + dis), "disagreements": out}
    a.out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n"); print(json.dumps({k: res[k] for k in ("labelled", "agree", "agreement")})); [print(d) for d in out]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table"); t.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sample"); s.add_argument("--table", type=Path, required=True); s.add_argument("--n", type=int, default=60); s.add_argument("--lines", type=int, default=9); s.add_argument("--out", type=Path, required=True)
    s.add_argument("--seed", type=int, default=20260919); s.add_argument("--exclude", type=Path, nargs="*", default=[])
    c = sub.add_parser("score"); c.add_argument("--table", type=Path, required=True); c.add_argument("--sample", type=Path, required=True); c.add_argument("--labels", type=Path, required=True); c.add_argument("--out", type=Path, required=True)
    a = p.parse_args(); {"table": cmd_table, "sample": cmd_sample, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
