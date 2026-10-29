#!/usr/bin/env python3
"""A8 — POST-HOC descriptive check, written after the single read and attached to no rule (docs/A8_CURADORIA_ESTREITA_RESULTADOS_V1.md).

Per arm and family: how many OBSERVED sessions submitted at least one Lean source containing a modular/divisibility statement
(ZMod, ModEq, emod, mod, %, ∣, Dvd) and how many one containing a quadratic or bilinear expression of the state (a product of two
factors that both contain a state field, or such a factor raised to a power; see has_field_product and its 19/09 erratum). "Submitted" = the `source` field of
`verification` events, i.e. what the checker received; reasoning text is not searched. Not observed = result status in NOT_OBSERVED or a
directory suffixed .failed*/.interrupted*. The invariant each family needs: W1 pell_mod modular (of a quadratic form), W2 plane_lattice
modular (lattice index), W3 hyperbolic4 quadratic form, W4 lattice_mod_p modular (the L3 form).

  python3 scripts/a8_invariant_attempts.py --evidence docs/a8_evidence_v1 --out docs/a8_results/invariant_attempts.json
"""
from __future__ import annotations
import argparse, collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_a1 import NOT_OBSERVED  # noqa: E402

MOD = re.compile(r"ZMod|ModEq|emod|\bmod\b|%|∣|Dvd|dvd")
FIELD = re.compile(r"\b[a-z]\w*\.[a-z]\w*\b")   # a state-field accessor such as s.x


def _factor_left(line: str, i: int) -> str:
    """The factor ending right before position i (the `*` or `^`): a balanced parenthesised group or a bare token."""
    j = i - 1
    while j >= 0 and line[j] == " ":
        j -= 1
    if j < 0:
        return ""
    if line[j] == ")":
        depth, k = 0, j
        while k >= 0:
            depth += line[k] == ")"; depth -= line[k] == "("
            if depth == 0:
                return line[k: j + 1]
            k -= 1
        return ""
    k = j
    while k >= 0 and (line[k].isalnum() or line[k] in "._'"):
        k -= 1
    return line[k + 1: j + 1]


def _factor_right(line: str, i: int) -> str:
    j = i + 1
    while j < len(line) and line[j] == " ":
        j += 1
    if j >= len(line):
        return ""
    if line[j] == "(":
        depth, k = 0, j
        while k < len(line):
            depth += line[k] == "("; depth -= line[k] == ")"
            if depth == 0:
                return line[j: k + 1]
            k += 1
        return ""
    k = j
    while k < len(line) and (line[k].isalnum() or line[k] in "._'"):
        k += 1
    return line[j:k]


def has_field_product(src: str) -> bool:
    """Heuristic for a quadratic/bilinear expression OF THE STATE: a product whose two factors both contain a state-field accessor
    ((s.x - 2) * (s.z - 3), s.x * s.x), or a factor containing one raised to a power. 19/09 erratum: the first version looked for
    `^2`/`sq` and missed bilinear forms written as products, which is how the hyperbolic form of W3 is written."""
    for line in src.splitlines():
        for i, ch in enumerate(line):
            if ch == "*" and FIELD.search(_factor_left(line, i)) and FIELD.search(_factor_right(line, i)):
                return True
            if ch == "^" and FIELD.search(_factor_left(line, i)):
                return True
    return False
NEEDED = {"W1": "modular_submission", "W2": "modular_submission", "W3": "quadratic_submission", "W4": "modular_submission", "W5": "quad_and_mod_submission"}


def scan(arms: dict) -> dict:
    out = {}
    for arm, root in arms.items():
        st = collections.defaultdict(collections.Counter)
        for d in sorted(Path(root).iterdir()):
            if not d.is_dir() or ".failed" in d.name or ".interrupted" in d.name:
                continue
            if not (d / "result.json").exists():
                continue
            r = json.loads((d / "result.json").read_text())["result"]
            if r.get("status") in NOT_OBSERVED:
                continue
            fam = d.name.split("_")[1]
            ev = d / "events.jsonl" if (d / "events.jsonl").exists() else d / "artifacts" / "events.jsonl"   # archive layout or run layout
            srcs = [e.get("source") or "" for e in (json.loads(l) for l in ev.open() if l.strip()) if e.get("event") == "verification"] if ev.exists() else []
            c = st[fam]; c["observed"] += 1; c["solved"] += int(r.get("status") == "solved"); c["any_submission"] += int(bool(srcs))
            c["modular_submission"] += int(any(MOD.search(s) for s in srcs)); c["quadratic_submission"] += int(any(has_field_product(s) for s in srcs))
            c["quad_and_mod_submission"] += int(any(has_field_product(s) and MOD.search(s) for s in srcs))   # the composition (W1, W5)
        out[arm] = {}
        for f, c in sorted(st.items()):
            out[arm][f] = dict(c); out[arm][f]["needed_kind"] = NEEDED[f]; out[arm][f]["needed_attempted"] = c[NEEDED[f]]
        fs = [f for f in ("W1", "W2", "W3") if f in out[arm]]
        out[arm]["outside_L3_form_W1_W2_W3"] = {"observed": sum(out[arm][f]["observed"] for f in fs), "needed_attempted": sum(out[arm][f]["needed_attempted"] for f in fs)}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidence", type=Path, default=None, help="archive root holding a8_base_v1, a8_own2_v1, a8_curm2_v1")
    p.add_argument("--arms", nargs="*", default=None, help="name=dir pairs (run or archive layout), instead of --evidence")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    arms = dict(x.split("=", 1) for x in a.arms) if a.arms else {n: a.evidence / n for n in ("a8_base_v1", "a8_own2_v1", "a8_curm2_v1")}
    out = scan(arms)
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for arm, fams in out.items():
        print(arm, " | ".join(f"{f}: {v['needed_attempted']}/{v['observed']} ({v['needed_kind'].split('_')[0]}), solved {v['solved']}" for f, v in fams.items() if f.startswith("W")),
              "| W1–W3:", f"{fams['outside_L3_form_W1_W2_W3']['needed_attempted']}/{fams['outside_L3_form_W1_W2_W3']['observed']}")


if __name__ == "__main__":
    main()
