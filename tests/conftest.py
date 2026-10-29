"""Optional historical sandbox prerequisite; never replace a scientific checker."""
import shutil

import pytest


def pytest_collection_modifyitems(items):
    from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
    if shutil.which(str(CODEX_BINARY)):
        return
    # These older integration tests check for Lean but also need the recorded
    # Codex sandbox binary. Synthetic tests and verification rules are unchanged.
    integrations = {
        ("test_a2_openai_session.py", "test_run_plan_dispatches_open_model_without_daily_budget"),
        ("test_bedrock_routes.py", "test_hard_world_and_oracle_work_through_sandbox"),
    }
    for item in items:
        if (item.path.name, item.originalname) in integrations:
            item.add_marker(pytest.mark.skip(reason="historical Codex sandbox binary unavailable"))
