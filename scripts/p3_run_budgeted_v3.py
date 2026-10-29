#!/usr/bin/env python3
"""Execute the already-frozen v3 once, under the additional USD150/day guard."""

import json
from pathlib import Path

from creative_machine.aws_daily_budget import DailyBudget
from creative_machine.formal_routes.calibration_protocol_v3 import (
    assert_committed_v3, load_plan_v3, run_v3,
)

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs/p3/calibration_conceptual_plan_v3.json"


def main():
    plan = load_plan_v3(ROOT, PLAN)
    assert_committed_v3(ROOT, PLAN, plan)
    if ((ROOT / plan["run_directory"]).exists()
            or (ROOT / "docs/p3/calibration_conceptual_evidence_v3/summary.json").exists()):
        raise FileExistsError("calibration already started; never rerun automatically")
    budget = DailyBudget(ROOT / "runs/aws-budget/claude_daily.jsonl")
    reservation = budget.reserve(plan["plan_id"], plan["max_total_cost_usd"])
    print(json.dumps({"event": "daily_budget_reserved", **reservation}), flush=True)
    # Keep the full reservation after crashes, uncertain requests, or accounting
    # errors. The frozen runner itself remains byte-identical to its original commit.
    result = run_v3(ROOT, PLAN, ROOT / "runs/p3/calibration")
    if result["uncertain_requests"] == 0 and all(c["status"] != "budget_accounting_error" for c in result["cells"]):
        print(json.dumps(budget.settle(plan["plan_id"], result["cost_usd_at_published_rates"])), flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
