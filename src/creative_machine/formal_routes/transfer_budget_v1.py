"""Transfer reservations on the existing Claude/AWS journal, with reconciliation.

No automatic settlement, expiration, purchase or inference admission. The local
journal and explicit external attestation are not an AWS-enforced account cap.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import fcntl
import json
import os
from pathlib import Path
import stat

from creative_machine import aws_daily_budget as legacy
from .production_audit_v1 import _decode
from .transfer_design_v1 import encoded, sha
from .transfer_lifecycle_v1 import instant, is_hash, money
from .transfer_worker_v1 import WorkerClaim

VERSION = "p3_transfer_budget_v1"
RESERVE = Decimal("50")
DAILY_CAP = Decimal("150")
MAX_RECONCILIATION_AGE_SECONDS = 1800
MAX_JOURNAL_BYTES = 4 * 1024 * 1024


class BudgetAdmissionError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise BudgetAdmissionError(message)


def events_from(data):
    with localcontext() as ctx:
        ctx.prec = 100
        return _events_from(data)


def _events_from(data):
    require(not data or data.endswith(b"\n"), "partial financial journal; preserve without repair")
    rows = [_decode(line) for line in data.splitlines()]
    previous = None
    prefix = []
    for row in rows:
        require(isinstance(row, dict) and row.get("event") in ("reserve", "settle"), "financial event schema")
        fields = ({"event", "run_id", "usd", "at", "daily_limit_usd", "timezone", "committed_today_usd"}
                  if row["event"] == "reserve" else {"event", "run_id", "usd", "at", "basis"})
        require(set(row) == fields and isinstance(row["run_id"], str) and bool(row["run_id"]), "financial event schema")
        at = datetime.fromisoformat(row["at"])
        require(at.tzinfo is not None and at.isoformat() == at.astimezone(legacy.ZONE).isoformat(), "financial timestamp must use local zone")
        require(previous is None or at >= previous, "financial journal clock reversal")
        previous = at
        amount = money(row["usd"])
        if row["event"] == "reserve":
            require(money(row["daily_limit_usd"]) == DAILY_CAP and row["timezone"] == str(legacy.ZONE), "daily cap/zone drift")
            expected = legacy.balance(prefix, at.date().isoformat()) + amount
            require(money(row["committed_today_usd"]) == expected and expected <= DAILY_CAP, "historical reservation accounting drift")
        else:
            require(row["basis"] == "reported tokens at frozen list rates; not invoice", "settlement basis drift")
        prefix.append(row)
        legacy.balance(prefix, at.date().isoformat())  # Duplicate/overrun checks.
    return rows


def validate_reconciliation(receipt, expected_sha256, *, permitted_reconcilers, data_kind, now):
    fields = {"version", "data_kind", "observed_at", "day", "timezone", "ledger_sha256",
              "reconciler_id", "covered_scopes", "evidence_sha256", "external_accounting_complete",
              "untracked_usage_upper_usd", "untracked_open_commitments_usd"}
    require(is_hash(expected_sha256) and isinstance(receipt, dict) and set(receipt) == fields
            and sha(encoded(receipt)) == expected_sha256, "external reconciliation reference/schema")
    require(receipt["version"] == VERSION and receipt["data_kind"] == data_kind, "reconciliation profile drift")
    require(isinstance(permitted_reconcilers, tuple) and bool(permitted_reconcilers)
            and all(isinstance(x, str) and x.strip() for x in permitted_reconcilers)
            and receipt["reconciler_id"] in permitted_reconcilers, "unapproved reconciler")
    observed = instant(receipt["observed_at"])
    age = (now - observed).total_seconds()
    require(0 <= age <= MAX_RECONCILIATION_AGE_SECONDS, "stale/future reconciliation")
    local = now.astimezone(legacy.ZONE)
    require(receipt["timezone"] == str(legacy.ZONE) and receipt["day"] == local.date().isoformat()
            == observed.astimezone(legacy.ZONE).date().isoformat(), "new civil day requires reconciliation")
    require(receipt["external_accounting_complete"] is True, "unknown external usage/commitments; reconcile before admission")
    require(isinstance(receipt["covered_scopes"], list) and bool(receipt["covered_scopes"])
            and all(isinstance(x, str) and x.strip() for x in receipt["covered_scopes"])
            and len(set(receipt["covered_scopes"])) == len(receipt["covered_scopes"]), "explicit external accounting scopes required")
    require(isinstance(receipt["evidence_sha256"], list) and bool(receipt["evidence_sha256"])
            and all(is_hash(x) for x in receipt["evidence_sha256"]) and is_hash(receipt["ledger_sha256"]), "reconciliation evidence references required")
    with localcontext() as ctx:
        ctx.prec = 100
        return money(receipt["untracked_usage_upper_usd"]) + money(receipt["untracked_open_commitments_usd"])


class TransferBudget:
    def __init__(self, path: Path, *, data_kind: str, clock=None):
        require(data_kind in ("synthetic", "experimental"), "explicit budget profile required")
        require(data_kind != "experimental" or clock is None, "experimental clock injection forbidden")
        self.path, self.data_kind = Path(path), data_kind
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @contextmanager
    def _journal(self, *, create):
        parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd = None
        try:
            parent_info = os.fstat(parent)
            fd = os.open(self.path.name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_CREAT if create else 0),
                         0o600, dir_fd=parent)
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "unsafe financial journal")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            def check():
                linked = os.stat(self.path.name, dir_fd=parent, follow_symlinks=False)
                current = os.fstat(fd)
                outer = os.stat(self.path.parent, follow_symlinks=False)
                require(stat.S_ISREG(linked.st_mode) and linked.st_nlink == current.st_nlink == 1
                    and (linked.st_dev, linked.st_ino) == (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino),
                    "financial journal replaced/linked")
                require(stat.S_ISDIR(outer.st_mode) and (outer.st_dev, outer.st_ino) == (parent_info.st_dev, parent_info.st_ino), "financial directory replaced")
            check()
            require(os.fstat(fd).st_size <= MAX_JOURNAL_BYTES, "financial journal size limit")
            data = os.pread(fd, MAX_JOURNAL_BYTES + 1, 0)
            require(len(data) <= MAX_JOURNAL_BYTES and len(data) == os.fstat(fd).st_size, "financial journal read drift")
            check()
            yield fd, parent, data, check
            check()
        finally:
            if fd is not None: os.close(fd)
            os.close(parent)

    def _external(self, receipt, expected, allowlist):
        now = self.clock()
        require(isinstance(now, datetime) and now.tzinfo is not None, "aware financial clock required")
        amount = validate_reconciliation(receipt, expected, permitted_reconcilers=allowlist, data_kind=self.data_kind, now=now)
        return now, amount

    def reserve(self, owner: WorkerClaim, reconciliation: dict, *, expected_reconciliation_sha256: str,
                permitted_reconcilers: tuple[str, ...]):
        require(isinstance(owner, WorkerClaim), "live worker ownership required")
        reconciliation = deepcopy(reconciliation)
        claim = owner.assert_owned()
        now, external = self._external(reconciliation, expected_reconciliation_sha256, permitted_reconcilers)
        with self._journal(create=True) as (fd, parent, before, check):
            rows = events_from(before)
            require(sha(before) == reconciliation["ledger_sha256"], "reconciliation ledger snapshot changed")
            require(not any(row["run_id"] == claim["run_id"] for row in rows), "run already reserved; no retry/replacement")
            local = now.astimezone(legacy.ZONE)
            require(not rows or local >= datetime.fromisoformat(rows[-1]["at"]), "financial admission clock reversal")
            with localcontext() as ctx:
                ctx.prec = 100
                used = legacy.balance(rows, local.date().isoformat())
                require(used + external + RESERVE <= DAILY_CAP, "USD150/day would be exceeded; stop for Roberto's decision")
                committed = used + RESERVE
            event = {"event": "reserve", "run_id": claim["run_id"], "usd": "50", "at": local.isoformat(),
                "daily_limit_usd": "150", "timezone": str(legacy.ZONE), "committed_today_usd": str(committed)}
            appended = (json.dumps(event, sort_keys=True) + "\n").encode()
            require(len(before) + len(appended) <= MAX_JOURNAL_BYTES, "financial journal size limit")
            owner.assert_owned()
            check()
            require(os.pread(fd, MAX_JOURNAL_BYTES + 1, 0) == before, "financial journal changed before append")
            os.lseek(fd, 0, os.SEEK_END)
            offset = 0
            while offset < len(appended):
                written = os.write(fd, appended[offset:])
                require(written > 0, "short financial append")
                offset += written
            os.fsync(fd)
            os.fsync(parent)
            check()
            require(os.pread(fd, MAX_JOURNAL_BYTES + 1, 0) == before + appended, "ambiguous financial append; preserve reservation")
            owner.assert_owned()
            return {"version": VERSION, "data_kind": self.data_kind, "run_id": claim["run_id"],
                "execution_plan_sha256": claim["execution_plan_sha256"], "worker_claim_sha256": owner.sha256,
                "reservation": event, "ledger_before_sha256": sha(before), "ledger_after_sha256": sha(before + appended),
                "reconciliation_sha256": expected_reconciliation_sha256,
                "external_reservation_must_remain_open": True, "inference_admitted": False}

    def check_before_request(self, owner: WorkerClaim, reservation: dict, *, expected_reservation_sha256: str, reconciliation: dict,
                             expected_reconciliation_sha256: str, permitted_reconcilers: tuple[str, ...]):
        reservation, reconciliation = deepcopy(reservation), deepcopy(reconciliation)
        require(is_hash(expected_reservation_sha256) and sha(encoded(reservation)) == expected_reservation_sha256
            and set(reservation) == {"version", "data_kind", "run_id", "execution_plan_sha256", "worker_claim_sha256",
                "reservation", "ledger_before_sha256", "ledger_after_sha256", "reconciliation_sha256",
                "external_reservation_must_remain_open", "inference_admitted"}
            and reservation["external_reservation_must_remain_open"] is True and reservation["inference_admitted"] is False,
            "external reservation receipt reference/schema")
        claim = owner.assert_owned()
        now, external = self._external(reconciliation, expected_reconciliation_sha256, permitted_reconcilers)
        require(reservation["version"] == VERSION and reservation["data_kind"] == self.data_kind
            and reservation["run_id"] == claim["run_id"] and reservation["execution_plan_sha256"] == claim["execution_plan_sha256"]
            and reservation["worker_claim_sha256"] == owner.sha256, "reservation/worker/plan binding")
        with self._journal(create=False) as (_, _, data, check):
            rows = events_from(data)
            require(not rows or now >= datetime.fromisoformat(rows[-1]["at"]), "financial request clock reversal")
            own = [row for row in rows if row["run_id"] == claim["run_id"]]
            require(own == [reservation["reservation"]] and own[0]["event"] == "reserve" and money(own[0]["usd"]) == RESERVE,
                    "reservation missing, changed or already settled")
            current = sha(data)
            same_admission = (current == reservation["ledger_after_sha256"]
                and reconciliation["ledger_sha256"] == reservation["ledger_before_sha256"]
                and expected_reconciliation_sha256 == reservation["reconciliation_sha256"])
            require(same_admission or reconciliation["ledger_sha256"] == current, "changed ledger needs fresh reconciliation")
            with localcontext() as ctx:
                ctx.prec = 100
                used = legacy.balance(rows, now.astimezone(legacy.ZONE).date().isoformat())
                require(used + external <= DAILY_CAP, "USD150/day exceeded after external reconciliation")
            owner.assert_owned()
            check()
            return {"status": "local_reservation_checked", "data_kind": self.data_kind,
                "ledger_sha256": current, "reconciliation_sha256": expected_reconciliation_sha256,
                "local_committed_usd": str(used), "external_upper_usd": str(external),
                "external_reservation_must_remain_open": True, "inference_admitted": False}
