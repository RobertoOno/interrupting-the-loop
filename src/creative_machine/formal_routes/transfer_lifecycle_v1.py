"""Prospective batch chronology and durable intents, not experiment admission.

This journal constrains local scheduling and receipt ordering. Receipt hashes
are references, not verified proofs, reviews, billing records or provenance.
A trusted launcher and independent batch auditor must validate those objects,
the final execution plan, worker ownership and external budget before use.
No provider, Lean, budget settlement, retry or scientific scoring is executed.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import fcntl
import os
from pathlib import Path
import re
import stat

from .production_audit_v1 import _decode, _wire
from .transfer_analysis_v1 import NO_BRIDGE
from .transfer_design_v1 import encoded, sha, validate_design_rules

VERSION = "p3_transfer_lifecycle_v1"
MAX_BYTES = 1024 * 1024
MAX_EVENTS = 256
SESSION_RESERVE = Decimal("1.65")
BATCH_RESERVE = Decimal("50")
SCHEMAS = {
    "batch_opened": {"version", "implementation_sha256", "blueprint_sha256", "execution_plan_sha256",
        "data_kind", "reservation_sha256", "provenance_sha256", "preflight_sha256",
        "batch_reserve_usd", "session_reserve_usd", "max_parallel"},
    "cell_started": {"cell_id", "bridge_sha256", "workspace_record_sha256"},
    "cell_closed": {"cell_id", "evidence_sha256", "reported_cost_usd", "accounting_complete", "technical_failure"},
    "trace_audited": {"cell_id", "evidence_sha256", "audit_sha256", "status",
                      "production_outcome", "selected_bridge_sha256"},
    "review_prepared": {"cell_id", "binding_sha256", "packet_sha256", "review_id"},
    "review_recorded": {"cell_id", "binding_sha256", "packet_sha256", "review_id",
                        "receipt_sha256", "content_status"},
    "phase_barrier": {"proposer_bindings_sha256"},
    "cell_skipped": {"cell_id", "parent_evidence_sha256", "reason"},
    "halted": {"reason", "evidence_sha256"},
    "batch_closed": set(),
}
ENVELOPE = {"seq", "event", "at", "payload", "previous_sha256", "sha256"}


class LifecycleError(ValueError):
    """Invalid/ambiguous chronology: retain the journal, never retry a cell."""


def require(condition, message):
    if not condition:
        raise LifecycleError(message)


def is_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def instant(value):
    require(isinstance(value, str) and len(value) <= 64, "timestamp must be UTC text")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise LifecycleError("invalid timestamp") from exc
    require(result.tzinfo is not None and result.utcoffset() == timedelta(0), "timestamp must be UTC")
    return result


def money(value):
    require(isinstance(value, str) and len(value) <= 64
            and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is not None, "USD must be nonnegative decimal text")
    return Decimal(value)


def implementation_sha256():
    path = Path(__file__)
    require(path.is_file() and not path.is_symlink(), "unsafe lifecycle implementation")
    return sha(path.read_bytes())


def opening_payload(blueprint, *, execution_plan_sha256, data_kind,
                    reservation_sha256, provenance_sha256, preflight_sha256):
    """References only. In particular, a reservation hash is not a budget check."""
    return {"version": VERSION, "implementation_sha256": implementation_sha256(),
        "blueprint_sha256": sha(encoded(blueprint)), "execution_plan_sha256": execution_plan_sha256,
        "data_kind": data_kind, "reservation_sha256": reservation_sha256,
        "provenance_sha256": provenance_sha256, "preflight_sha256": preflight_sha256,
        "batch_reserve_usd": "50", "session_reserve_usd": "1.65", "max_parallel": 2}


def entry(event, payload, *, seq, previous_sha256, at=None):
    base = {"seq": seq, "event": event, "at": at or datetime.now(timezone.utc).isoformat(),
            "payload": deepcopy(payload), "previous_sha256": previous_sha256}
    return {**base, "sha256": sha(_wire(base).encode())}


def _eligibility(cell):
    if cell["audit_status"] != "passed":
        return None, None
    if cell["production_outcome"] in NO_BRIDGE:
        return False, cell["production_outcome"]
    if cell["content_status"] == "rejected":
        return False, "content_contract_rejected"
    return (True, None) if cell["content_status"] == "passed" else (None, None)


def _bindings(blueprint, states):
    return [{"cell_id": c["cell_id"], **{key: states[c["cell_id"]][key] for key in (
        "evidence_sha256", "audit_sha256", "production_outcome", "selected_bridge_sha256",
        "review_binding", "review_receipt_sha256", "content_status")}}
        for c in blueprint["cells"][:6]]


def replay(blueprint: dict, rows: list[dict], *, expected_head_sha256=None) -> dict:
    """Validate chronology of claims. Never convert claims into audited data.

    The external head reference detects truncation/substitution against that
    reference. An internally consistent hash chain alone cannot authenticate
    its author or detect a fully rewritten/rehashed history.
    """
    validate_design_rules(blueprint)
    require(isinstance(rows, list) and 1 <= len(rows) <= MAX_EVENTS, "invalid journal event count")
    cells = blueprint["cells"]
    states = {c["cell_id"]: {"state": "not_started", "start_seq": None, "close_seq": None,
        "bridge_sha256": None, "evidence_sha256": None, "audit_sha256": None, "audit_status": "pending",
        "production_outcome": None, "selected_bridge_sha256": None, "content_status": "not_applicable",
        "review_binding": None, "review_receipt_sha256": None, "reported_cost_usd": None,
        "accounting_complete": False, "technical_failure": False, "skip_reason": None} for c in cells}
    indexed = {c["cell_id"]: c for c in cells}
    cursor, active, halted, closed, barrier = 0, set(), False, False, None
    used_evidence, used_reviews, used_packets, used_audits, used_receipts = set(), set(), set(), set(), set()
    previous, previous_at, header = None, None, None
    admissions = 0
    for seq, row in enumerate(rows, 1):
        require(isinstance(row, dict) and set(row) == ENVELOPE, "journal envelope schema")
        require(type(row["seq"]) is int and row["seq"] == seq, "sequence gap or reorder")
        require(row["previous_sha256"] == previous, "broken event hash chain")
        require(is_hash(row["sha256"]) and row["sha256"] == sha(_wire({k: v for k, v in row.items() if k != "sha256"}).encode()),
                "event digest mismatch")
        current_at = instant(row["at"])
        require(previous_at is None or current_at >= previous_at, "journal clock reversal")
        previous, previous_at = row["sha256"], current_at
        kind, payload = row["event"], row["payload"]
        require(isinstance(kind, str) and kind in SCHEMAS, "unknown lifecycle event")
        require(isinstance(payload, dict) and set(payload) == SCHEMAS[kind], kind + " schema")
        require(not closed, "events after batch closure")
        require((seq == 1) == (kind == "batch_opened"), "exactly one initial batch opening required")
        if kind == "batch_opened":
            require(payload["version"] == VERSION and payload["implementation_sha256"] == implementation_sha256(),
                    "lifecycle implementation drift")
            require(payload["blueprint_sha256"] == sha(encoded(blueprint)), "blueprint binding")
            require(payload["data_kind"] in ("synthetic", "experimental"), "explicit data kind required")
            for key in ("execution_plan_sha256", "reservation_sha256", "provenance_sha256", "preflight_sha256"):
                require(is_hash(payload[key]), "missing external reference: " + key)
            require(payload["execution_plan_sha256"] != payload["blueprint_sha256"], "blueprint is not final execution plan")
            require(money(payload["batch_reserve_usd"]) == BATCH_RESERVE
                    and money(payload["session_reserve_usd"]) == SESSION_RESERVE
                    and type(payload["max_parallel"]) is int and payload["max_parallel"] == 2, "frozen operational limits")
            header = deepcopy(payload)
            continue
        identity = payload.get("cell_id")
        cell = state = None
        if "cell_id" in payload:
            require(isinstance(identity, str) and identity in indexed, "unknown cell")
            cell, state = indexed[identity], states[identity]
        if kind in ("cell_started", "cell_skipped"):
            require(not halted and cursor < len(cells) and cells[cursor]["cell_id"] == identity,
                    "admission halted, duplicated or outside fixed order")
            require(state["state"] == "not_started", "cell already consumed")
            if cell["role"] == "recipient":
                require(barrier is not None, "recipient before six-proposer/content barrier")
            expected_bridge = None
            eligible, reason = True, None
            if cell["bridge_kind"] == "candidate":
                parent = states[cell["parent_proposer_id"]]
                eligible, reason = _eligibility(parent)
                expected_bridge = parent["selected_bridge_sha256"]
            elif cell["bridge_kind"] == "oracle":
                expected_bridge = next(w["oracle_bridge_sha256"] for w in blueprint["worlds"] if w["world_id"] == cell["world_id"])
            if kind == "cell_skipped":
                require(cell["bridge_kind"] == "candidate" and eligible is False, "cannot omit eligible/undecided bridge or control")
                require(payload["reason"] == reason and payload["parent_evidence_sha256"] == parent["evidence_sha256"],
                        "skip reason or parent binding")
                state.update(state="skipped_no_bridge", skip_reason=reason)
            else:
                require(eligible is True and len(active) < 2, "ineligible bridge or concurrency overrun")
                require(not any(s["state"] == "closed" and s["audit_status"] == "pending" for s in states.values()),
                        "closed session audit must precede another admission")
                require(payload["bridge_sha256"] == expected_bridge, "wrong supplied bridge bytes")
                require(is_hash(payload["workspace_record_sha256"]), "workspace receipt required")
                admissions += 1
                require(admissions * SESSION_RESERVE <= BATCH_RESERVE, "batch reservation overrun")
                state.update(state="running", start_seq=seq, bridge_sha256=expected_bridge)
                active.add(identity)
            cursor += 1
        elif kind == "cell_closed":
            require(state["state"] == "running" and identity in active, "closure without unique admission")
            require(is_hash(payload["evidence_sha256"]) and payload["evidence_sha256"] not in used_evidence, "missing or reused raw evidence seal")
            require(type(payload["technical_failure"]) is bool and type(payload["accounting_complete"]) is bool, "closure booleans")
            cost = None if payload["reported_cost_usd"] is None else money(payload["reported_cost_usd"])
            require(not payload["accounting_complete"] or cost is not None, "complete usage needs reported cost")
            if not payload["technical_failure"]:
                require(payload["accounting_complete"] and cost <= SESSION_RESERVE, "normal closure has uncertain/excess usage")
            else:
                halted = True
            # Preserve even a technical cost overrun, without releasing any
            # reservation or interpreting it as a mathematical observation.
            state.update({k: deepcopy(payload[k]) for k in ("evidence_sha256", "reported_cost_usd", "accounting_complete", "technical_failure")})
            state.update(state="closed", close_seq=seq)
            used_evidence.add(payload["evidence_sha256"])
            active.remove(identity)
        elif kind == "trace_audited":
            require(state["state"] == "closed" and state["audit_status"] == "pending", "trace audit must be first and follow closure")
            require(payload["evidence_sha256"] == state["evidence_sha256"] and is_hash(payload["audit_sha256"])
                    and payload["audit_sha256"] not in used_audits, "audit/raw seal binding or reused audit")
            require(payload["status"] in ("passed", "failed"), "trace audit status")
            if payload["status"] == "failed":
                require(payload["production_outcome"] is None and payload["selected_bridge_sha256"] is None, "failed audit cannot select bridge")
                halted = True
            else:
                require(not state["technical_failure"] and state["accounting_complete"], "technical/uncertain session cannot pass audit")
                if cell["role"] == "proposer":
                    outcome = payload["production_outcome"]
                    require(isinstance(outcome, str) and outcome in NO_BRIDGE | {"valid_bridge"}, "production outcome")
                    require(is_hash(payload["selected_bridge_sha256"]) if outcome == "valid_bridge"
                            else payload["selected_bridge_sha256"] is None, "selected final bridge binding")
                    state.update(production_outcome=outcome, selected_bridge_sha256=payload["selected_bridge_sha256"],
                                 content_status="pending" if outcome == "valid_bridge" else "not_applicable")
                else:
                    require(payload["production_outcome"] is None and payload["selected_bridge_sha256"] is None, "recipient cannot supply a proposer selection")
            state.update(audit_status=payload["status"], audit_sha256=payload["audit_sha256"])
            used_audits.add(payload["audit_sha256"])
        elif kind in ("review_prepared", "review_recorded"):
            require(not halted and barrier is None and not active
                    and all(states[c["cell_id"]]["audit_status"] == "passed" for c in cells[:6]),
                    "review requires all six audited proposers before barrier")
            require(cell["role"] == "proposer" and state["production_outcome"] == "valid_bridge", "only final valid bridges need review")
            binding = {k: payload[k] for k in ("binding_sha256", "packet_sha256", "review_id")}
            require(all(is_hash(binding[k]) for k in ("binding_sha256", "packet_sha256"))
                    and isinstance(binding["review_id"], str) and re.fullmatch(r"CR_[0-9a-f]{24}", binding["review_id"]), "review linkage schema")
            if kind == "review_prepared":
                require(state["review_binding"] is None and binding["review_id"] not in used_reviews
                        and binding["packet_sha256"] not in used_packets, "duplicate review packet")
                state["review_binding"] = deepcopy(binding)
                used_reviews.add(binding["review_id"])
                used_packets.add(binding["packet_sha256"])
            else:
                require(binding == state["review_binding"] and state["review_receipt_sha256"] is None, "review must be first receipt for its prepared packet")
                require(is_hash(payload["receipt_sha256"]) and payload["receipt_sha256"] not in used_receipts
                        and payload["content_status"] in ("passed", "rejected", "pending"), "content receipt schema or reused receipt")
                state.update(review_receipt_sha256=payload["receipt_sha256"], content_status=payload["content_status"])
                used_receipts.add(payload["receipt_sha256"])
        elif kind == "phase_barrier":
            require(not halted and not active and cursor == 6 and barrier is None,
                    "phase barrier must occur once after exactly six closed proposers")
            require(all(_eligibility(states[c["cell_id"]])[0] is not None for c in cells[:6]), "proposer audit or content decision remains pending")
            expected = sha(encoded(_bindings(blueprint, states)))
            require(payload["proposer_bindings_sha256"] == expected, "phase barrier receipt linkage")
            barrier = {"seq": seq, "proposer_bindings_sha256": expected}
        elif kind == "halted":
            require(not halted and isinstance(payload["reason"], str) and bool(payload["reason"].strip()) and len(payload["reason"]) <= 1000
                    and is_hash(payload["evidence_sha256"]), "invalid or repeated halt")
            halted = True
        elif kind == "batch_closed":
            require(not active, "cannot close batch while sessions may still be running")
            require(halted or (cursor == 26 and barrier is not None and all(
                s["state"] == "skipped_no_bridge" or s["audit_status"] == "passed" for s in states.values())),
                "normal closure requires all fixed positions and audits")
            closed = True
    if expected_head_sha256 is not None:
        require(is_hash(expected_head_sha256) and previous == expected_head_sha256, "external journal head mismatch")
    ready = not halted and not active and barrier is None and cursor == 6 and all(_eligibility(states[c["cell_id"]])[0] is not None for c in cells[:6])
    with localcontext() as context:
        context.prec = 80  # At most 26 bounded decimal strings, without rounding.
        known_cost = sum((money(s["reported_cost_usd"]) for s in states.values() if s["reported_cost_usd"] is not None), Decimal(0))
    return {"version": VERSION, "status": "halted_closed" if closed and halted else "closed" if closed else "halted" if halted else "open",
        "header": header, "head_sha256": previous, "events": len(rows), "cells": states,
        "next_cell_id": cells[cursor]["cell_id"] if cursor < 26 else None,
        "active_cells": sorted(active), "admissions": admissions, "consumed_positions": cursor,
        "phase_barrier": barrier, "ready_proposer_bindings_sha256": sha(encoded(_bindings(blueprint, states))) if ready else None,
        "nominal_admitted_reservations_usd": str(admissions * SESSION_RESERVE), "known_reported_cost_usd": str(known_cost),
        "unresolved_cost_cells": sorted(identity for identity, s in states.items()
            if s["start_seq"] is not None and (not s["accounting_complete"] or s["technical_failure"] or s["audit_status"] != "passed")),
        "external_checkpoint_verified": expected_head_sha256 is not None,
        "chronology_only": True,
        "external_reservation_must_remain_open": True, "receipt_contents_verified": False,
        "batch_audit_passed": False, "inference_admitted": False, "main_sample_admitted": False,
        "mechanistic_stage_admitted": False, "worker_ownership_verified": False}


def decode_journal(data: bytes):
    require(isinstance(data, bytes) and 0 < len(data) <= MAX_BYTES and data.endswith(b"\n"), "incomplete/oversized journal")
    lines = data.splitlines()
    require(len(lines) <= MAX_EVENTS, "journal event limit")
    try:
        return [_decode(line) for line in lines]
    except ValueError as exc:
        raise LifecycleError("invalid journal JSON: " + str(exc)) from exc


class Journal:
    """Single-file locked append + compare-and-swap; never repairs crash tails.

    This is not a lifetime worker lease. The launcher must separately prevent
    duplicate workers and must not resume ambiguous live session intents.
    Keep an independent closure head reference outside this mutable file.
    """
    def __init__(self, path: Path, blueprint: dict):
        self.path, self.blueprint = Path(path), deepcopy(blueprint)
        validate_design_rules(self.blueprint)

    @contextmanager
    def _handle(self, *, create=False):
        parent = self.path.parent.resolve(strict=True)
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptor = None
        try:
            if not create:
                node = os.stat(self.path.name, dir_fd=parent_fd, follow_symlinks=False)
                require(stat.S_ISREG(node.st_mode) and node.st_nlink == 1, "unsafe journal node")
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_CREAT | os.O_EXCL if create else 0)
            descriptor = os.open(self.path.name, flags, 0o600, dir_fd=parent_fd)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._identity(parent_fd, descriptor)
            yield parent_fd, descriptor
            self._identity(parent_fd, descriptor)
            actual_parent, opened_parent = parent.stat(), os.fstat(parent_fd)
            require(self.path.parent.resolve(strict=True) == parent
                    and (actual_parent.st_dev, actual_parent.st_ino) == (opened_parent.st_dev, opened_parent.st_ino),
                    "journal parent changed during operation")
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(parent_fd)

    def _identity(self, parent_fd, descriptor):
        opened = os.fstat(descriptor)
        current = os.stat(self.path.name, dir_fd=parent_fd, follow_symlinks=False)
        require(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1
                and (current.st_dev, current.st_ino, current.st_mode, current.st_nlink)
                == (opened.st_dev, opened.st_ino, opened.st_mode, opened.st_nlink), "unsafe/replaced journal")

    @staticmethod
    def _read(descriptor):
        before = os.fstat(descriptor)
        require(before.st_size <= MAX_BYTES, "journal size limit")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks, size = [], 0
        while True:
            part = os.read(descriptor, min(65536, MAX_BYTES + 1 - size))
            if not part:
                break
            chunks.append(part)
            size += len(part)
            require(size <= MAX_BYTES, "journal size limit")
        after = os.fstat(descriptor)
        require(size == before.st_size and all(getattr(before, key) == getattr(after, key)
                for key in ("st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")), "journal changed while reading")
        return b"".join(chunks)

    @staticmethod
    def _write(parent_fd, descriptor, data):
        require(os.fstat(descriptor).st_size + len(data) <= MAX_BYTES, "journal size limit")
        os.lseek(descriptor, 0, os.SEEK_END)
        remaining = memoryview(data)
        while remaining:
            count = os.write(descriptor, remaining)
            require(count > 0, "short journal write")
            remaining = remaining[count:]
        os.fsync(descriptor)
        os.fsync(parent_fd)

    def create(self, payload, *, at=None):
        row = entry("batch_opened", payload, seq=1, previous_sha256=None, at=at)
        result = replay(self.blueprint, [row])
        line = (_wire(row) + "\n").encode()
        with self._handle(create=True) as (parent_fd, descriptor):
            self._write(parent_fd, descriptor, line)
            require(self._read(descriptor) == line, "journal changed during creation")
        return result

    def read(self, *, expected_head_sha256=None):
        with self._handle() as (_, descriptor):
            data = self._read(descriptor)
            result = replay(self.blueprint, decode_journal(data), expected_head_sha256=expected_head_sha256)
            require(self._read(descriptor) == data, "journal changed during validation")
            return result

    def append(self, event, payload, *, expected_head_sha256, at=None):
        with self._handle() as (parent_fd, descriptor):
            data = self._read(descriptor)
            rows = decode_journal(data)
            require(is_hash(expected_head_sha256), "explicit compare-and-swap head required")
            replay(self.blueprint, rows, expected_head_sha256=expected_head_sha256)
            row = entry(event, payload, seq=len(rows) + 1, previous_sha256=expected_head_sha256, at=at)
            result = replay(self.blueprint, [*rows, row])
            line = (_wire(row) + "\n").encode()
            self._identity(parent_fd, descriptor)
            require(self._read(descriptor) == data, "journal changed before append")
            self._write(parent_fd, descriptor, line)
            require(self._read(descriptor) == data + line, "journal changed during append")
            return result
