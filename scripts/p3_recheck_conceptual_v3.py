#!/usr/bin/env python3
"""Audit the complete v3 archive and recheck final candidates offline, without AWS.

Raw archives remain verbatim; this audit is separate from the frozen online scorer.
"""

import hashlib
import json
import math
import tempfile
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from creative_machine.formal_routes.bedrock_calibration import summarize
from creative_machine.formal_routes.calibration_protocol_v3 import load_plan_v3
from creative_machine.formal_routes.calibration_review_v3 import materialize_v3
from creative_machine.formal_routes.calibration_worlds_v3 import load_v3
from creative_machine.formal_routes.lean_sandbox import sandbox_process
from creative_machine.formal_routes.submission import verify_evaluator_solution

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs/p3"
ARCHIVE = DOCS / "calibration_conceptual_evidence_v3"


def audit():
    plan = load_plan_v3(ROOT, DOCS / "calibration_conceptual_plan_v3.json")
    entries = {}
    for line in (DOCS / "calibration_conceptual_raw_manifest_v3.sha256").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        path = Path(relative)
        if relative in entries or path.is_absolute() or ".." in path.parts:
            raise ValueError("invalid or duplicated manifest entry")
        entries[relative] = digest
    actual = {str(p.relative_to(ARCHIVE)) for p in ARCHIVE.rglob("*") if p.is_file()}
    if actual != set(entries) or any(p.is_symlink() for p in ARCHIVE.rglob("*")):
        raise ValueError("archive inventory differs from original raw manifest")
    for relative, expected in entries.items():
        if hashlib.sha256((ARCHIVE / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"archive hash mismatch: {relative}")
    if json.loads((ARCHIVE / "plan.json").read_text()) != plan:
        raise ValueError("archived plan differs from the prospective freeze")
    stored = json.loads((ARCHIVE / "summary.json").read_text())
    rows, checks = [], []
    exact_cost = Decimal("0")
    for cell in plan["cells"]:
        cell_root = ARCHIVE / cell["cell_id"]
        row = json.loads((cell_root / "result.json").read_text())
        session = json.loads((cell_root / "artifacts/session.json").read_text())
        if row["cell"] != cell or row["result"] != session:
            raise ValueError("cell or session identity mismatch")
        events = [json.loads(s) for s in (cell_root / "artifacts/events.jsonl").read_text().splitlines()]
        responses = [e["body"] for e in events if e["event"] == "response"]
        for name, expected in session["tokens"].items():
            if sum(r["usage"].get(name, 0) or 0 for r in responses) != expected:
                raise ValueError("reported token totals differ from responses")
        usage, agent = session["tokens"], plan["agent"]
        cell_cost = (Decimal(str(agent["input_usd_per_million"])) * (
            usage["input_tokens"] + 2 * usage["cache_creation_input_tokens"]
            + Decimal("0.1") * usage["cache_read_input_tokens"])
            + Decimal(str(agent["output_usd_per_million"])) * usage["output_tokens"]) / Decimal("1000000")
        if not math.isclose(float(cell_cost), session["cost_usd_at_published_rates"], rel_tol=0, abs_tol=1e-12):
            raise ValueError("cost differs from raw usage and frozen rates")
        exact_cost += cell_cost
        if sum(e["event"] == "request" for e in events) != session["requests"]:
            raise ValueError("request count mismatch")
        if [e["report"] for e in events if e["event"] == "verification"] != session["verification"]:
            raise ValueError("online verification records differ from events")
        rows.append(row)
        source = cell_root / "workspace/Solution.lean"
        if not source.exists():
            checks.append({"cell_id": cell["cell_id"], "submitted_candidate": False,
                           "original_solved": session["target_solved"], "matches_original": not session["target_solved"]})
            continue
        world = ROOT / cell["world"]
        metadata = load_v3(world, phase="calibration")
        with tempfile.TemporaryDirectory(prefix="p3-recheck-v3-") as temporary:
            record = materialize_v3(world, f"holdout{cell['holdout']}",
                "oracle" if cell["condition"] == "oracle_bridge" else None,
                Path(temporary).resolve() / "workspace")
            (record.path / "Solution.lean").write_bytes(source.read_bytes())
            report = verify_evaluator_solution(record.path,
                namespace=metadata["roles"]["namespace"],
                statement=metadata["roles"]["holdout_statements"][cell["holdout"] - 1],
                bridge_supplied=cell["condition"] == "oracle_bridge",
                process_runner=sandbox_process, allowed_axioms=tuple(plan["allowed_axioms"]))
        checks.append({"cell_id": cell["cell_id"], "submitted_candidate": True,
                       "original_solved": session["target_solved"],
                       "matches_original": report.ok == session["target_solved"],
                       "recheck": asdict(report)})
    recomputed = summarize(plan, rows)
    if (any(stored[key] != value for key, value in recomputed.items() if key != "cost_usd_at_published_rates")
            or not math.isclose(stored["cost_usd_at_published_rates"], float(exact_cost), rel_tol=0, abs_tol=1e-12)):
        raise ValueError("aggregate differs from the frozen scorer applied to archived sessions")
    return {"ok": len(checks) == 8 and all(c["matches_original"] for c in checks),
            "model_calls": 0, "raw_files_verified": len(entries),
            "aggregate_matches": True, "usage_matches_raw_responses": True,
            "estimated_cost_recomputed_from_response_tokens_usd": str(exact_cost), "checks": checks}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
