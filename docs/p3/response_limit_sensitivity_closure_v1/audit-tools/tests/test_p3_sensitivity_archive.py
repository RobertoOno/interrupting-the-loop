"""Synthetic-only safeguards for one-shot S16 closure."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("s16_archive_test", ROOT / "scripts/p3_archive_sensitivity_v1.py")
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


@pytest.mark.parametrize("kind", ["raw", "closure", "manifest", "broken_symlink"])
def test_never_overwrites_existing_or_ambiguous_archive(tmp_path, monkeypatch, kind):
    path = tmp_path / (archive.protocol.ARCHIVE_PATH if kind in ("raw", "broken_symlink") else archive.CLOSURE)
    path.parent.mkdir(parents=True)
    if kind == "manifest": Path(str(path) + ".sha256").write_text("existing")
    elif kind == "broken_symlink": path.symlink_to(tmp_path / "missing")
    else: path.mkdir()
    monkeypatch.setattr(archive.auditor, "audit", lambda *args: pytest.fail("must refuse before auditing/copying"))
    with pytest.raises(FileExistsError): archive.archive(tmp_path)


def test_budget_subset_excludes_other_runs_and_retains_bytes():
    reservation = {"run_id": archive.protocol.PLAN_ID, "event": "reserve", "usd": "30"}
    settlement = {"run_id": archive.protocol.PLAN_ID, "event": "settle", "usd": "3"}
    selected = json.dumps(reservation) + "\n" + json.dumps(settlement) + "\n"
    journal = '{"run_id":"other","event":"reserve"}\n' + selected
    assert archive.budget_subset(journal, reservation, settlement) == selected
    with pytest.raises(ValueError): archive.budget_subset(journal + json.dumps(settlement), reservation, settlement)


def synthetic_log():
    receipt = {"pid": 12345, "commit": archive.auditor.FROZEN_COMMIT}
    intent = {"plan_id": archive.protocol.PLAN_ID, "commit": archive.auditor.FROZEN_COMMIT}
    rows = [{"cell": {"cell_id": "synthetic"}, "result": {"status": "output_limit"}}]
    log = [json.dumps({"event": "batch_started", "plan_id": archive.protocol.PLAN_ID, **receipt}),
        json.dumps({"event": "cell_completed", "cell_id": "synthetic", "completed": 1,
            "total": 16, "status": "output_limit"})]
    return "\n".join(log), rows, receipt, intent


def test_log_reconciles_completed_cells():
    archive.check_log(*synthetic_log())


@pytest.mark.parametrize("change", ["duplicate", "status", "commit", "missing"])
def test_log_drift_rejected(change):
    log, rows, receipt, intent = synthetic_log()
    if change == "duplicate": log += "\n" + log.splitlines()[-1]
    elif change == "status": rows[0]["result"]["status"] = "solved"
    elif change == "commit": receipt["commit"] = "wrong"
    else: log = log.splitlines()[0]
    with pytest.raises(ValueError): archive.check_log(log, rows, receipt, intent)


def test_new_write_refuses_to_replace_data(tmp_path):
    path = tmp_path / "new" / "data"
    archive.write_new(path, b"first")
    with pytest.raises(FileExistsError): archive.write_new(path, b"second")
    assert path.read_bytes() == b"first"
