#!/usr/bin/env python3
"""A7 — wall screen: worlds, Lean verification, reference sources, plans (docs/A7_PAREDE_V1.md). No model calls.

  build   --root worlds/walls --prefix a7-screen --per-step 2 --index docs/a7_screen_worlds.json
          one instance per (candidate, index): seeds "<prefix>-<step>-<i>"; certificate stored in metadata and index
  verify  --index docs/a7_screen_worlds.json --out docs/a7_screen_verification.json   (modules, reference proof, mutation)
  sources --index docs/a7_screen_worlds.json --out docs/a7_sources
          reference arm: the SIBLING instance's complete verified proof of the same candidate (never the instance's own)
  plan    --index docs/a7_screen_worlds.json --sources docs/a7_sources/index.json --out-dir docs
          a7s_base_v1: base qwen3.8-27b, arms none + reference; a7s_own2_v1: adapter a2c4-own2, arm none.
          Agent = the thinking configuration of docs/a2c2_baset131_plan_v1.json (131 072 tokens, T 1.0/top-p 0.95, 3600 s).
"""
from __future__ import annotations
import argparse, json, random, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402
from creative_machine.formal_routes import ladder_runner_v1 as R  # noqa: E402
from creative_machine.formal_routes import ladder_walls_v1 as W  # noqa: E402


def rel(p: Path) -> str:
    return str(Path(p).resolve().relative_to(ROOT))


def cmd_build(a):
    index = []
    for step in (a.steps or W.WALLS):
        for i in range(1, a.per_step + 1):
            seed = f"{a.prefix}-{step}-{i}"
            d = W.build_wall(seed, step, a.root, phase=a.phase)
            meta = json.loads((d / "metadata.json").read_text())
            index.append({"seed": seed, "step": step, "instance": meta["instance"], "path": rel(d.parent), "world": rel(d),
                          "certificate_clean": meta["certificate"]["clean"], "parameters": meta["parameters"]})
            if not meta["certificate"]["clean"]:
                sys.exit(f"certificate not clean for {seed}: {meta['certificate']['unintended_shortcuts'][:3]}")
    a.index.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps([{k: e[k] for k in ("seed", "instance", "certificate_clean")} for e in index], indent=1))


def cmd_verify(a):
    index = json.loads(a.index.read_text())
    def one(e):
        d = ROOT / e["world"]
        v = L.verify_step(d, timeout=900); m = W.mutation_check_wall(d)
        ok = v["modules_ok"] and v["reference_ok"] and m["reference_rejected"] and m["witness_ok"]
        return {"world": e["world"], "ok": ok, "modules_ok": v["modules_ok"], "reference_ok": v["reference_ok"],
                "reference_rejected_on_mutation": m["reference_rejected"], "witness_ok": m["witness_ok"], "errors": (v["errors"] + m["errors"])[:2]}
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        res = list(pool.map(one, index))
    out = {"summary": {"checked": len(res), "ok": sum(r["ok"] for r in res)}, "results": res}
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out["summary"]))
    sys.exit(0 if out["summary"]["ok"] == out["summary"]["checked"] else 1)


def cmd_sources(a):
    index = json.loads(a.index.read_text()); a.out.mkdir(parents=True, exist_ok=True); src_index = {}
    by_step = {}
    for e in index:
        by_step.setdefault(e["step"], []).append(e)
    for step, es in by_step.items():
        for j, e in enumerate(es):
            sib = es[(j + 1) % len(es)]
            assert sib["instance"] != e["instance"]
            sd = ROOT / sib["world"]
            md = R.render_example_md(sd, (sd / "Hidden/Reference.lean").read_text(encoding="utf-8"))
            p = a.out / f"{e['instance']}_reference.md"; p.write_text(md, encoding="utf-8")
            src_index[e["instance"]] = {"reference": rel(p), "sibling": sib["instance"], "step": step}
    (a.out / "index.json").write_text(json.dumps(src_index, indent=1) + "\n")
    print(json.dumps(src_index, indent=1))


def _merged_plan(plan_id, phase, index, arms, model, agent, attempts, order_seed, max_parallel, cell_sources=None, budgets=None, label="b128k"):
    parts = []
    for e in index:
        parts.append(R.make_plan(ROOT, plan_id=plan_id, phase=phase, instances=[ROOT / e["path"]], steps=[e["step"]], arms=arms, attempts=attempts,
                                 budgets=budgets or {"b128k": 131072}, agent={**agent, "model": model}, order_seed=order_seed, daily_reserve_usd=0.0,
                                 max_parallel=max_parallel, main_budget_label=label, cell_sources=cell_sources))
    plan = parts[0]
    plan["instances"] = [i for p in parts for i in p["instances"]]
    plan["steps"] = sorted({e["step"] for e in index})
    plan["cells"] = [c for p in parts for c in p["cells"]]
    plan["missing_source_cells"] = [m for p in parts for m in p["missing_source_cells"]]
    random.Random(order_seed).shuffle(plan["cells"])
    for i, c in enumerate(plan["cells"]):
        c["ordinal"] = i
    return plan


def cmd_plan(a):
    index = json.loads(a.index.read_text()); srcs = json.loads(a.sources.read_text())
    agent = json.loads((ROOT / "docs/a2c2_baset131_plan_v1.json").read_text())["agent"]
    agent = {k: v for k, v in agent.items() if k != "model"}
    cell_sources = {(inst, "reference"): v["reference"] for inst, v in srcs.items()}
    plans = {"a7s_base_v1": _merged_plan("a7s_base_v1", "a7_screen", index, ["none", "reference"], "qwen3.8-27b", agent, a.attempts, a.order_seed, a.max_parallel, cell_sources),
             "a7s_own2_v1": _merged_plan("a7s_own2_v1", "a7_screen", index, ["none"], "a2c4-own2", agent, a.attempts, a.order_seed, a.max_parallel)}
    for pid, plan in plans.items():
        if plan["missing_source_cells"]:
            sys.exit(f"{pid}: missing sources {plan['missing_source_cells'][:3]}")
        (a.out_dir / f"{pid}_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps({"plan_id": pid, "cells": len(plan["cells"]), "arms": plan["arms"], "model": plan["agent"]["model"], "steps": plan["steps"]}))


def cmd_plan_confirm(a):
    """Phase 2 (E1): a7c_base_v1 base none x8; a7c_own2_v1 a2c4-own2 none x8; a7c_ref_v1 base reference x4; a7c_curm2_v1 a2c4-curm2 none x4."""
    index = json.loads(a.index.read_text()); srcs = json.loads(a.sources.read_text())
    agent = json.loads((ROOT / "docs/a2c2_baset131_plan_v1.json").read_text())["agent"]
    agent = {k: v for k, v in agent.items() if k != "model"}
    cell_sources = {(inst, "reference"): v["reference"] for inst, v in srcs.items()}
    spec = {"a7c_base_v1": (["none"], "qwen3.8-27b", 8, None), "a7c_own2_v1": (["none"], "a2c4-own2", 8, None),
            "a7c_ref_v1": (["reference"], "qwen3.8-27b", 4, cell_sources), "a7c_curm2_v1": (["none"], "a2c4-curm2", 4, None)}
    for pid, (arms, model, attempts, cs) in spec.items():
        plan = _merged_plan(pid, "a7_confirm", index, arms, model, agent, attempts, a.order_seed, a.max_parallel, cs)
        if plan["missing_source_cells"]:
            sys.exit(f"{pid}: missing sources {plan['missing_source_cells'][:3]}")
        (a.out_dir / f"{pid}_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps({"plan_id": pid, "cells": len(plan["cells"]), "arms": plan["arms"], "model": plan["agent"]["model"], "steps": plan["steps"]}))


def cmd_plan_narrow(a):
    """A8: three arms on the same fresh cells of all four families, no example: base, a2c4-own2, a2c4-curm2."""
    index = json.loads(a.index.read_text())
    agent = json.loads((ROOT / "docs/a2c2_baset131_plan_v1.json").read_text())["agent"]
    agent = {k: v for k, v in agent.items() if k != "model"}
    for pid, model in (("a8_base_v1", "qwen3.8-27b"), ("a8_own2_v1", "a2c4-own2"), ("a8_curm2_v1", "a2c4-curm2")):
        plan = _merged_plan(pid, "a8_narrow", index, ["none"], model, agent, a.attempts, a.order_seed, a.max_parallel)
        (a.out_dir / f"{pid}_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps({"plan_id": pid, "cells": len(plan["cells"]), "model": plan["agent"]["model"], "steps": plan["steps"],
                          "instances": len(plan["instances"]), "attempts": a.attempts}))


def cmd_plan_a9(a):
    """A9 (docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md): same cells for every arm of a block, no example.
    Thinking agent = docs/a2c2_baset131_plan_v1.json; no-thinking agent = docs/a2c2_base_plan_v1.json (only the model changes).
      W1..W4 fresh : a9_own2t / a9_own3t (thinking), a9_basen / a9_own2n / a9_own3n (no thinking)
      W5 fresh     : a9_w5base / a9_w5own2 / a9_w5own3 (thinking), a9_w5own2n / a9_w5own3n (no thinking)
      ladder       : a9_own3lad = the cells of docs/a2c4_own2_plan_v1.json with the model a9-own3 (retention against own2's 16/09 run)"""
    idx = json.loads(a.index.read_text()); idx5 = json.loads(a.index_w5.read_text())
    think = {k: v for k, v in json.loads((ROOT / "docs/a2c2_baset131_plan_v1.json").read_text())["agent"].items() if k != "model"}
    plain = {k: v for k, v in json.loads((ROOT / "docs/a2c2_base_plan_v1.json").read_text())["agent"].items() if k != "model"}
    B, O2, O3 = "qwen3.8-27b", "a2c4-own2", "a9-own3"
    spec = [("a9_own2t_v1", idx, O2, think, None, "b128k"), ("a9_own3t_v1", idx, O3, think, None, "b128k"),
            ("a9_basen_v1", idx, B, plain, {"b16k": 16384}, "b16k"), ("a9_own2n_v1", idx, O2, plain, {"b16k": 16384}, "b16k"), ("a9_own3n_v1", idx, O3, plain, {"b16k": 16384}, "b16k"),
            ("a9_w5base_v1", idx5, B, think, None, "b128k"), ("a9_w5own2_v1", idx5, O2, think, None, "b128k"), ("a9_w5own3_v1", idx5, O3, think, None, "b128k"),
            ("a9_w5own2n_v1", idx5, O2, plain, {"b16k": 16384}, "b16k"), ("a9_w5own3n_v1", idx5, O3, plain, {"b16k": 16384}, "b16k")]
    for pid, index, model, agent, budgets, label in spec:
        plan = _merged_plan(pid, "a9", index, ["none"], model, agent, a.attempts, a.order_seed, a.max_parallel, budgets=budgets, label=label)
        (a.out_dir / f"{pid}_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps({"plan_id": pid, "cells": len(plan["cells"]), "model": plan["agent"]["model"], "steps": plan["steps"], "thinking": plan["agent"]["extra_body"]["chat_template_kwargs"]["enable_thinking"], "budget": plan["budgets"]}))
    lad = json.loads((ROOT / "docs/a2c4_own2_plan_v1.json").read_text()); lad["plan_id"] = "a9_own3lad_v1"; lad["phase"] = "a9_retention"; lad["agent"]["model"] = O3
    lad["max_parallel"] = a.max_parallel; lad["notes"] = ["cells, agent and order identical to a2c4_own2_v1; only the model (a9-own3) and max_parallel differ"]
    (a.out_dir / "a9_own3lad_v1_plan.json").write_text(json.dumps(lad, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"plan_id": "a9_own3lad_v1", "cells": len(lad["cells"]), "model": lad["agent"]["model"], "steps": lad["steps"]}))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--root", type=Path, default=ROOT / "worlds/walls"); b.add_argument("--prefix", default="a7-screen")
    b.add_argument("--per-step", type=int, default=2); b.add_argument("--phase", default="a7_screen"); b.add_argument("--index", type=Path, required=True)
    b.add_argument("--steps", nargs="*", default=None, help="subset of W1..W4 (confirmation)")
    v = sub.add_parser("verify"); v.add_argument("--index", type=Path, required=True); v.add_argument("--out", type=Path, required=True); v.add_argument("--workers", type=int, default=4)
    s = sub.add_parser("sources"); s.add_argument("--index", type=Path, required=True); s.add_argument("--out", type=Path, required=True)
    pl = sub.add_parser("plan"); pl.add_argument("--index", type=Path, required=True); pl.add_argument("--sources", type=Path, required=True)
    pl.add_argument("--out-dir", type=Path, default=ROOT / "docs"); pl.add_argument("--attempts", type=int, default=4); pl.add_argument("--order-seed", type=int, default=2026091601)
    pl.add_argument("--max-parallel", type=int, default=16)
    pc = sub.add_parser("plan-confirm"); pc.add_argument("--index", type=Path, required=True); pc.add_argument("--sources", type=Path, required=True)
    pc.add_argument("--out-dir", type=Path, default=ROOT / "docs"); pc.add_argument("--order-seed", type=int, default=2026091701); pc.add_argument("--max-parallel", type=int, default=16)
    pn = sub.add_parser("plan-narrow"); pn.add_argument("--index", type=Path, required=True); pn.add_argument("--out-dir", type=Path, default=ROOT / "docs")
    pn.add_argument("--attempts", type=int, default=3); pn.add_argument("--order-seed", type=int, default=2026091702); pn.add_argument("--max-parallel", type=int, default=16)
    p9 = sub.add_parser("plan-a9"); p9.add_argument("--index", type=Path, required=True); p9.add_argument("--index-w5", type=Path, required=True); p9.add_argument("--out-dir", type=Path, default=ROOT / "docs")
    p9.add_argument("--attempts", type=int, default=3); p9.add_argument("--order-seed", type=int, default=2026091901); p9.add_argument("--max-parallel", type=int, default=16)
    a = p.parse_args()
    {"build": cmd_build, "verify": cmd_verify, "sources": cmd_sources, "plan": cmd_plan, "plan-confirm": cmd_plan_confirm, "plan-narrow": cmd_plan_narrow, "plan-a9": cmd_plan_a9}[a.cmd](a)


if __name__ == "__main__":
    main()
