from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import fcntl
import os

import pytest

from creative_machine import aws_daily_budget as legacy
from creative_machine.formal_routes import transfer_budget_v1 as budget
from creative_machine.formal_routes.transfer_worker_v1 import WorkerClaim, WorkerOwnershipError
from creative_machine.formal_routes.transfer_design_v1 import encoded, sha

NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
PLAN = "a" * 64
ALLOW = ("fixture-reconciler",)


def reconciliation(path, *, at=NOW, usage="0", commitments="0", **changes):
    result = {"version": budget.VERSION, "data_kind": "synthetic", "observed_at": at.isoformat(),
        "day": at.astimezone(legacy.ZONE).date().isoformat(), "timezone": str(legacy.ZONE),
        "ledger_sha256": sha(path.read_bytes() if path.exists() else b""), "reconciler_id": ALLOW[0],
        "covered_scopes": ["synthetic other agents and repository copies"], "evidence_sha256": ["b" * 64],
        "external_accounting_complete": True, "untracked_usage_upper_usd": usage,
        "untracked_open_commitments_usd": commitments}
    result.update(changes)
    return result


def reserve(guard, owner, receipt):
    return guard.reserve(owner, receipt, expected_reconciliation_sha256=sha(encoded(receipt)), permitted_reconcilers=ALLOW)


def check(guard, owner, reservation, receipt, **changes):
    kwargs = {"expected_reservation_sha256": sha(encoded(reservation)), "reconciliation": receipt,
              "expected_reconciliation_sha256": sha(encoded(receipt)), "permitted_reconcilers": ALLOW}
    kwargs.update(changes)
    return guard.check_before_request(owner, reservation, **kwargs)


def test_reserve_legacy_compatible_once_and_hold_until_explicit_settlement(tmp_path):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    receipt = reconciliation(path, usage="30", commitments="20")
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        reserved = reserve(guard, owner, receipt)
        assert reserved["reservation"]["usd"] == "50" and not reserved["inference_admitted"]
        state = check(guard, owner, reserved, receipt)
        assert state["local_committed_usd"] == state["external_upper_usd"] == "50"
        assert state["external_reservation_must_remain_open"] and not state["inference_admitted"]
        with pytest.raises(budget.BudgetAdmissionError): reserve(guard, owner, reconciliation(path))
    rows = budget.events_from(path.read_bytes())
    assert len(rows) == 1 and legacy.balance(rows, "2026-09-09") == Decimal("50")


@pytest.mark.parametrize("usage,commitments,allowed", (("100", "0", True), ("99", "1", True),
    ("100.0001", "0", False), ("80", "21", False), ("100." + "0" * 45 + "1", "0", False)))
def test_external_usage_and_commitments_share_the_same_daily_limit(tmp_path, usage, commitments, allowed):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        receipt = reconciliation(path, usage=usage, commitments=commitments)
        if allowed: reserve(guard, owner, receipt)
        else:
            with pytest.raises(budget.BudgetAdmissionError, match="USD150"): reserve(guard, owner, receipt)
            assert not path.read_bytes()


@pytest.mark.parametrize("field,value", (("external_accounting_complete", False), ("external_accounting_complete", 1),
    ("covered_scopes", []), ("evidence_sha256", []), ("evidence_sha256", ["bad"]),
    ("reconciler_id", "unknown"), ("data_kind", "experimental"), ("timezone", "UTC"),
    ("untracked_usage_upper_usd", "-1"), ("untracked_open_commitments_usd", "NaN")))
def test_unknown_unbound_or_invalid_reconciliation_never_reserves(tmp_path, field, value):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        receipt = reconciliation(path, **{field: value})
        with pytest.raises((ValueError, RuntimeError)): reserve(guard, owner, receipt)
        assert not path.exists()


@pytest.mark.parametrize("age", (-1, 1801))
def test_stale_or_future_receipt_blocks_admission(tmp_path, age):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    receipt = reconciliation(path, at=NOW - timedelta(seconds=age))
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        with pytest.raises(budget.BudgetAdmissionError, match="stale/future"): reserve(guard, owner, receipt)


def test_existing_journal_change_requires_new_external_snapshot(tmp_path):
    path = tmp_path / "daily.jsonl"
    receipt = reconciliation(path)
    legacy.DailyBudget(path).reserve("other", 10, at=NOW)
    before = path.read_bytes()
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
        with pytest.raises(budget.BudgetAdmissionError, match="snapshot changed"): reserve(guard, owner, receipt)
    assert path.read_bytes() == before


def test_old_open_reservations_carry_forward_and_cannot_overspend(tmp_path):
    path = tmp_path / "daily.jsonl"
    legacy.DailyBudget(path).reserve("yesterday", 101, at=NOW - timedelta(days=1))
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        with pytest.raises(budget.BudgetAdmissionError, match="USD150"): reserve(guard, owner, reconciliation(path))


def test_midnight_requires_new_conciliation_but_never_expires_reservation(tmp_path):
    path = tmp_path / "daily.jsonl"
    before = datetime(2026, 9, 9, 2, 59, 59, tzinfo=timezone.utc)
    current = [before]
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: current[0])
    receipt = reconciliation(path, at=before)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        reservation = reserve(guard, owner, receipt)
        current[0] += timedelta(seconds=2)
        with pytest.raises(budget.BudgetAdmissionError, match="civil day"): check(guard, owner, reservation, receipt)
        fresh = reconciliation(path, at=current[0])
        assert check(guard, owner, reservation, fresh)["local_committed_usd"] == "50"
        assert len(budget.events_from(path.read_bytes())) == 1


def test_new_legacy_reservation_requires_reconciliation_and_settlement_stops_worker(tmp_path):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    receipt = reconciliation(path)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        reservation = reserve(guard, owner, receipt)
        legacy.DailyBudget(path).reserve("other", 20, at=NOW)
        with pytest.raises(budget.BudgetAdmissionError, match="changed ledger"): check(guard, owner, reservation, receipt)
        fresh = reconciliation(path)
        assert check(guard, owner, reservation, fresh)["local_committed_usd"] == "70"
        legacy.DailyBudget(path).settle("transfer", 1, at=NOW)
        with pytest.raises(budget.BudgetAdmissionError, match="already settled"):
            check(guard, owner, reservation, reconciliation(path))


def test_increased_external_commitment_blocks_existing_reservation_without_release(tmp_path):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        reservation = reserve(guard, owner, reconciliation(path))
        with pytest.raises(budget.BudgetAdmissionError, match="USD150"):
            check(guard, owner, reservation, reconciliation(path, usage="101"))
        assert len(budget.events_from(path.read_bytes())) == 1


@pytest.mark.parametrize("kind", ("partial", "duplicate", "cap", "clock", "unknown"))
def test_corrupt_financial_history_is_preserved(tmp_path, kind):
    path = tmp_path / "daily.jsonl"
    legacy.DailyBudget(path).reserve("old", 1, at=NOW)
    if kind == "partial": path.write_bytes(path.read_bytes()[:-1])
    elif kind == "duplicate": path.write_bytes(path.read_bytes() * 2)
    else:
        row = json.loads(path.read_text())
        if kind == "cap": row["daily_limit_usd"] = "200"
        elif kind == "clock": row["at"] = NOW.isoformat()
        else: row["unknown"] = True
        path.write_text(json.dumps(row) + "\n")
    original = path.read_bytes()
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
        with pytest.raises((RuntimeError, ValueError)): reserve(guard, owner, reconciliation(path))
    assert path.read_bytes() == original


def test_claim_loss_or_modified_reservation_cannot_pass_pre_request_check(tmp_path):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    receipt = reconciliation(path)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        reservation = reserve(guard, owner, receipt)
        expected = sha(encoded(reservation))
        reservation["reservation"]["usd"] = "1"
        with pytest.raises(budget.BudgetAdmissionError, match="external reservation"):
            check(guard, owner, reservation, receipt, expected_reservation_sha256=expected)
        owner.close()
        with pytest.raises(WorkerOwnershipError): reserve(guard, owner, receipt)


def test_ambiguous_append_keeps_legacy_reservation_and_no_retry(tmp_path, monkeypatch):
    path = tmp_path / "daily.jsonl"
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        original = os.fsync
        def fail(fd): raise OSError("ambiguous durable write")
        monkeypatch.setattr(os, "fsync", fail)
        with pytest.raises(OSError): reserve(guard, owner, reconciliation(path))
        monkeypatch.setattr(os, "fsync", original)
        assert len(budget.events_from(path.read_bytes())) == 1
        with pytest.raises(budget.BudgetAdmissionError, match="already reserved"): reserve(guard, owner, reconciliation(path))


def test_experimental_clock_override_forbidden(tmp_path):
    with pytest.raises(budget.BudgetAdmissionError, match="clock injection"):
        budget.TransferBudget(tmp_path / "daily.jsonl", data_kind="experimental", clock=lambda: NOW)


def test_busy_legacy_lock_blocks_without_writing_or_waiting(tmp_path):
    path = tmp_path / "daily.jsonl"
    path.touch()
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner, path.open("r+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError): reserve(guard, owner, reconciliation(path))
        assert not path.read_bytes()


@pytest.mark.parametrize("kind", ("symlink", "hardlink", "fifo"))
def test_unsafe_ledger_is_not_used(tmp_path, kind):
    path = tmp_path / "daily.jsonl"
    original = tmp_path / "original"
    original.touch()
    if kind == "symlink": path.symlink_to(original)
    elif kind == "hardlink": os.link(original, path)
    else: os.mkfifo(path)
    # Do not read a FIFO in the fixture; the guard itself must refuse it.
    receipt = reconciliation(original)
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: NOW)
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        with pytest.raises((OSError, RuntimeError)): reserve(guard, owner, receipt)
    assert not original.read_bytes()


def test_request_clock_before_a_ledger_event_is_not_a_lower_balance(tmp_path):
    path = tmp_path / "daily.jsonl"
    clock = [NOW]
    guard = budget.TransferBudget(path, data_kind="synthetic", clock=lambda: clock[0])
    with WorkerClaim(tmp_path / "claims", "transfer", PLAN) as owner:
        reservation = reserve(guard, owner, reconciliation(path))
        clock[0] = NOW - timedelta(seconds=1)
        with pytest.raises(budget.BudgetAdmissionError, match="clock reversal"):
            check(guard, owner, reservation, reconciliation(path, at=clock[0]))
