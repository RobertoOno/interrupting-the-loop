"""Synthetic receipt references exercise chronology, not experimental evidence."""
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from copy import deepcopy
from decimal import Decimal
import os
import multiprocessing
from pathlib import Path

import pytest

from creative_machine.formal_routes import transfer_lifecycle_v1 as life
from creative_machine.formal_routes.transfer_design_v1 import load_blueprint, sha, encoded

REPO = Path(__file__).resolve().parents[1]
AT = "2026-09-08T13:00:00+00:00"


def digest(label):
    return sha(label.encode())


@pytest.fixture(scope="module")
def blueprint():
    return load_blueprint(REPO)


def opening(blueprint, **changes):
    result = life.opening_payload(blueprint, execution_plan_sha256=digest("plan"), data_kind="synthetic",
        reservation_sha256=digest("reservation"), provenance_sha256=digest("provenance"), preflight_sha256=digest("preflight"))
    result.update(changes)
    return result


class History:
    def __init__(self, blueprint):
        self.blueprint = blueprint
        self.rows = []
        self.add("batch_opened", opening(blueprint))

    def add(self, kind, payload):
        row = life.entry(kind, payload, seq=len(self.rows) + 1,
                         previous_sha256=self.rows[-1]["sha256"] if self.rows else None, at=AT)
        result = life.replay(self.blueprint, [*self.rows, row])
        self.rows.append(row)
        self.state = result
        return result

    def start(self, cell=None, **changes):
        cell = cell or next(c for c in self.blueprint["cells"] if c["cell_id"] == self.state["next_cell_id"])
        bridge = None
        if cell["bridge_kind"] == "candidate":
            bridge = self.state["cells"][cell["parent_proposer_id"]]["selected_bridge_sha256"]
        elif cell["bridge_kind"] == "oracle":
            bridge = next(w["oracle_bridge_sha256"] for w in self.blueprint["worlds"] if w["world_id"] == cell["world_id"])
        self.add("cell_started", {"cell_id": cell["cell_id"], "bridge_sha256": bridge,
                                 "workspace_record_sha256": digest("workspace:" + cell["cell_id"]), **changes})
        return cell

    def close(self, cell, **changes):
        self.add("cell_closed", {"cell_id": cell["cell_id"], "evidence_sha256": digest("raw:" + cell["cell_id"]),
            "reported_cost_usd": "0.001", "accounting_complete": True, "technical_failure": False, **changes})

    def audit(self, cell, outcome="valid_bridge", **changes):
        self.add("trace_audited", {"cell_id": cell["cell_id"], "evidence_sha256": digest("raw:" + cell["cell_id"]),
            "audit_sha256": digest("audit:" + cell["cell_id"]), "status": "passed",
            "production_outcome": outcome if cell["role"] == "proposer" else None,
            "selected_bridge_sha256": digest("bridge:" + cell["cell_id"]) if cell["role"] == "proposer" and outcome == "valid_bridge" else None,
            **changes})

    def review_binding(self, cell):
        return {"cell_id": cell["cell_id"], "binding_sha256": digest("binding:" + cell["cell_id"]),
                "packet_sha256": digest("packet:" + cell["cell_id"]), "review_id": "CR_" + digest(cell["cell_id"])[:24]}

    def review(self, cell, status="passed", **changes):
        self.add("review_recorded", {**self.review_binding(cell), "receipt_sha256": digest("review:" + cell["cell_id"]),
                                     "content_status": status, **changes})

    def proposers(self, *, outcome="valid_bridge", content="passed", barrier=True):
        for cell in self.blueprint["cells"][:6]:
            self.start(cell)
            self.close(cell)
            self.audit(cell, outcome)
        if outcome == "valid_bridge":
            for cell in self.blueprint["cells"][:6]:
                self.add("review_prepared", self.review_binding(cell))
                self.review(cell, content)
        if barrier:
            self.barrier()

    def barrier(self):
        self.add("phase_barrier", {"proposer_bindings_sha256": self.state["ready_proposer_bindings_sha256"]})

    def recipients(self):
        for cell in self.blueprint["cells"][6:]:
            if cell["bridge_kind"] == "candidate":
                parent = self.state["cells"][cell["parent_proposer_id"]]
                eligible, reason = life._eligibility(parent)
                if eligible is False:
                    self.add("cell_skipped", {"cell_id": cell["cell_id"], "reason": reason,
                                              "parent_evidence_sha256": parent["evidence_sha256"]})
                    continue
            self.start(cell)
            self.close(cell)
            self.audit(cell)


def test_complete_twenty_six_session_chronology_is_not_admission(blueprint):
    history = History(blueprint)
    history.proposers()
    history.recipients()
    result = history.add("batch_closed", {})
    assert result["status"] == "closed" and result["admissions"] == result["consumed_positions"] == 26
    assert Decimal(result["nominal_admitted_reservations_usd"]) == Decimal("42.9")
    assert Decimal(result["known_reported_cost_usd"]) == Decimal("0.026")
    assert result["next_cell_id"] is None and not result["active_cells"]
    assert result["external_reservation_must_remain_open"]
    assert not any(result[key] for key in ("receipt_contents_verified", "worker_ownership_verified",
        "batch_audit_passed", "inference_admitted", "main_sample_admitted", "mechanistic_stage_admitted"))
    with pytest.raises(life.LifecycleError): history.add("batch_closed", {})


@pytest.mark.parametrize("outcome,content", [
    ("invalid_bridge", None), ("no_complete_submission", None), ("invalid_protocol_output", None),
    ("valid_bridge", "rejected"),
])
def test_all_ineligible_candidates_keep_twelve_explicit_skips(blueprint, outcome, content):
    history = History(blueprint)
    history.proposers(outcome=outcome, content=content)
    history.recipients()
    result = history.add("batch_closed", {})
    assert result["admissions"] == 14 and result["consumed_positions"] == 26
    skipped = [s for s in result["cells"].values() if s["state"] == "skipped_no_bridge"]
    assert len(skipped) == 12 and all(s["evidence_sha256"] is None and s["start_seq"] is None for s in skipped)
    assert all(result["cells"][c["cell_id"]]["state"] == "closed" for c in blueprint["cells"] if c["arm"] in ("B", "O"))


def test_two_parallel_sessions_and_out_of_order_completions(blueprint):
    history = History(blueprint)
    first, second = history.start(), history.start()
    with pytest.raises(life.LifecycleError, match="concurrency"): history.start()
    history.close(second)
    history.audit(second)
    third = history.start()
    assert len(history.state["active_cells"]) == 2
    history.close(first)
    history.close(third)
    assert not history.state["active_cells"] and history.state["admissions"] == 3


@pytest.mark.parametrize("offset", range(1, 26))
def test_fixed_order_rejects_every_noninitial_position(blueprint, offset):
    history = History(blueprint)
    with pytest.raises(life.LifecycleError): history.start(blueprint["cells"][offset])


def test_duplicate_admission_remains_consumed_after_closure(blueprint):
    history = History(blueprint)
    first = history.start()
    history.close(first)
    history.audit(first)
    with pytest.raises(life.LifecycleError): history.start(first)


@pytest.mark.parametrize("stage", ["unaudited", "unreviewed", "pending_review", "ready_without_barrier"])
def test_no_recipient_can_start_before_global_barrier(blueprint, stage):
    history = History(blueprint)
    for cell in blueprint["cells"][:6]:
        history.start(cell)
        history.close(cell)
        if stage != "unaudited" or cell != blueprint["cells"][5]: history.audit(cell)
    if stage in ("pending_review", "ready_without_barrier"):
        for cell in blueprint["cells"][:6]:
            history.add("review_prepared", history.review_binding(cell))
            history.review(cell, "pending" if stage == "pending_review" else "passed")
    with pytest.raises(life.LifecycleError, match="barrier"): history.start()
    if stage != "ready_without_barrier":
        with pytest.raises(life.LifecycleError): history.barrier()


@pytest.mark.parametrize("stage", ["running", "closed", "audited_one"])
def test_review_cannot_precede_all_six_audits(blueprint, stage):
    history = History(blueprint)
    cell = history.start()
    if stage != "running": history.close(cell)
    if stage == "audited_one": history.audit(cell)
    with pytest.raises(life.LifecycleError): history.add("review_prepared", history.review_binding(cell))


@pytest.mark.parametrize("status", ["passed", "rejected", "pending"])
def test_first_review_cannot_be_replaced_or_reprepared(blueprint, status):
    history = History(blueprint)
    history.proposers(content=status, barrier=False)
    cell = blueprint["cells"][0]
    with pytest.raises(life.LifecycleError): history.review(cell, "passed")
    with pytest.raises(life.LifecycleError): history.add("review_prepared", history.review_binding(cell))
    if status == "pending":
        assert history.state["ready_proposer_bindings_sha256"] is None


def test_barrier_binds_all_audits_selections_and_content_receipts(blueprint):
    history = History(blueprint)
    history.proposers(barrier=False)
    with pytest.raises(life.LifecycleError): history.add("phase_barrier", {"proposer_bindings_sha256": digest("other")})
    expected = history.state["ready_proposer_bindings_sha256"]
    history.barrier()
    assert history.state["phase_barrier"]["proposer_bindings_sha256"] == expected
    assert history.state["ready_proposer_bindings_sha256"] is None
    with pytest.raises(life.LifecycleError): history.barrier()


@pytest.mark.parametrize("kind", ["candidate", "oracle", "none"])
def test_recipient_bridge_hash_is_bound_to_parent_or_frozen_oracle(blueprint, kind):
    history = History(blueprint)
    history.proposers()
    for cell in blueprint["cells"][6:]:
        if cell["bridge_kind"] == kind:
            with pytest.raises(life.LifecycleError, match="bridge bytes"):
                history.start(cell, bridge_sha256=digest("wrong bridge"))
            return
        history.start(cell)
        history.close(cell)
        history.audit(cell)
    pytest.fail("missing fixture kind")


@pytest.mark.parametrize("kind", ["candidate", "oracle", "none"])
def test_cannot_skip_eligible_candidate_or_control(blueprint, kind):
    history = History(blueprint)
    history.proposers()
    for cell in blueprint["cells"][6:]:
        if cell["bridge_kind"] == kind:
            with pytest.raises(life.LifecycleError):
                history.add("cell_skipped", {"cell_id": cell["cell_id"], "reason": "invalid_bridge", "parent_evidence_sha256": digest("fake")})
            return
        history.start(cell)
        history.close(cell)
        history.audit(cell)


@pytest.mark.parametrize("kind", ["technical", "failed_audit", "explicit_halt"])
def test_halt_stops_new_admissions_but_retains_inflight_completion(blueprint, kind):
    history = History(blueprint)
    first, second = history.start(), history.start()
    if kind == "explicit_halt": history.add("halted", {"reason": "uncertain worker ownership", "evidence_sha256": digest("failure")})
    history.close(first, technical_failure=kind == "technical", accounting_complete=kind != "technical",
                  reported_cost_usd=None if kind == "technical" else "0.001")
    if kind == "failed_audit": history.audit(first, status="failed", production_outcome=None, selected_bridge_sha256=None)
    with pytest.raises(life.LifecycleError): history.start()
    with pytest.raises(life.LifecycleError): history.add("batch_closed", {})
    history.close(second)
    history.audit(second)
    result = history.add("batch_closed", {})
    assert result["status"] == "halted_closed" and result["consumed_positions"] == 2
    assert len([s for s in result["cells"].values() if s["state"] == "not_started"]) == 24
    assert result["external_reservation_must_remain_open"]


@pytest.mark.parametrize("cost", ["1.6500000000000001", "9000000000000000000000000000000.000000000000000001"])
def test_technical_overrun_is_retained_without_release_or_rounding(blueprint, cost):
    history = History(blueprint)
    cell = history.start()
    with pytest.raises(life.LifecycleError): history.close(cell, reported_cost_usd=cost)
    history.close(cell, reported_cost_usd=cost, technical_failure=True)
    assert history.state["known_reported_cost_usd"] == cost
    assert history.state["status"] == "halted" and history.state["external_reservation_must_remain_open"]
    with pytest.raises(life.LifecycleError): history.audit(cell)


@pytest.mark.parametrize("value", [True, -1, 1.65, "NaN", "Infinity", "-0.01", "1e-4", "", "0" * 65])
def test_noncanonical_money_rejected(blueprint, value):
    history = History(blueprint)
    cell = history.start()
    with pytest.raises(life.LifecycleError): history.close(cell, reported_cost_usd=value)


@pytest.mark.parametrize("change", [
    {"accounting_complete": False}, {"accounting_complete": 1}, {"technical_failure": 0}, {"reported_cost_usd": None},
])
def test_uncertain_usage_cannot_be_normal_closure(blueprint, change):
    history = History(blueprint)
    cell = history.start()
    with pytest.raises(life.LifecycleError): history.close(cell, **change)


@pytest.mark.parametrize("key,value", [
    ("max_parallel", 3), ("max_parallel", True), ("batch_reserve_usd", "51"), ("session_reserve_usd", "1.64"),
    ("execution_plan_sha256", None), ("reservation_sha256", ""), ("provenance_sha256", True),
    ("preflight_sha256", "missing"), ("data_kind", "assumed"), ("implementation_sha256", "0" * 64),
])
def test_opening_cannot_change_limits_or_omit_references(blueprint, key, value):
    row = life.entry("batch_opened", opening(blueprint, **{key: value}), seq=1, previous_sha256=None, at=AT)
    with pytest.raises(life.LifecycleError): life.replay(blueprint, [row])


def test_blueprint_is_not_final_plan(blueprint):
    row = life.entry("batch_opened", opening(blueprint, execution_plan_sha256=sha(encoded(blueprint))), seq=1, previous_sha256=None, at=AT)
    with pytest.raises(life.LifecycleError): life.replay(blueprint, [row])


@pytest.mark.parametrize("kind", ["sequence", "chain", "digest", "timestamp", "extra", "event"])
def test_envelope_tampering(blueprint, kind):
    history = History(blueprint)
    history.start()
    rows = deepcopy(history.rows)
    if kind == "sequence": rows[1]["seq"] = True
    elif kind == "chain": rows[1]["previous_sha256"] = None
    elif kind == "digest": rows[1]["sha256"] = digest("forged")
    elif kind == "timestamp": rows[1]["at"] = "2020-01-01T00:00:00+00:00"
    elif kind == "extra": rows[1]["extra"] = 1
    else: rows[1]["event"] = "retry"
    if kind in {"timestamp", "event"}:
        rows[1]["sha256"] = sha(life._wire({k: v for k, v in rows[1].items() if k != "sha256"}).encode())
    with pytest.raises(life.LifecycleError): life.replay(blueprint, rows)


def test_internal_chain_is_not_authentication_or_tail_truncation_detection(blueprint):
    history = History(blueprint)
    history.start()
    head = history.state["head_sha256"]
    assert life.replay(blueprint, history.rows, expected_head_sha256=head)["external_checkpoint_verified"]
    assert not life.replay(blueprint, history.rows[:1])["external_checkpoint_verified"]
    with pytest.raises(life.LifecycleError): life.replay(blueprint, history.rows[:1], expected_head_sha256=head)


def test_receipts_cannot_be_reused_for_another_cell(blueprint):
    history = History(blueprint)
    first = history.start()
    history.close(first)
    history.audit(first)
    second = history.start()
    with pytest.raises(life.LifecycleError): history.close(second, evidence_sha256=digest("raw:" + first["cell_id"]))
    history.close(second)
    with pytest.raises(life.LifecycleError): history.audit(second, audit_sha256=digest("audit:" + first["cell_id"]))


def test_missing_and_mismatched_review_bindings(blueprint):
    history = History(blueprint)
    for cell in blueprint["cells"][:6]:
        history.start(cell)
        history.close(cell)
        history.audit(cell)
    first, second = blueprint["cells"][:2]
    with pytest.raises(life.LifecycleError): history.review(first)
    history.add("review_prepared", history.review_binding(first))
    with pytest.raises(life.LifecycleError): history.review(first, binding_sha256=digest("other"))
    history.review(first)
    bad = {**history.review_binding(first), "cell_id": second["cell_id"]}
    with pytest.raises(life.LifecycleError): history.add("review_prepared", bad)
    history.add("review_prepared", history.review_binding(second))
    with pytest.raises(life.LifecycleError): history.review(second, receipt_sha256=digest("review:" + first["cell_id"]))


def test_normal_batch_cannot_close_early_or_with_unaudited_recipient(blueprint):
    history = History(blueprint)
    with pytest.raises(life.LifecycleError): history.add("batch_closed", {})
    history.proposers()
    history.recipients()
    rows = history.rows[:-1]  # Last recipient is closed but its audit is absent.
    row = life.entry("batch_closed", {}, seq=len(rows) + 1, previous_sha256=rows[-1]["sha256"], at=AT)
    with pytest.raises(life.LifecycleError): life.replay(blueprint, [*rows, row])


def journal(tmp_path, blueprint):
    store = life.Journal(tmp_path / "lifecycle.jsonl", blueprint)
    return store, store.create(opening(blueprint), at=AT)


def start_payload(blueprint):
    return {"cell_id": blueprint["cells"][0]["cell_id"], "bridge_sha256": None, "workspace_record_sha256": digest("workspace")}


def test_durable_exclusive_creation_and_compare_and_swap(tmp_path, blueprint):
    store, initial = journal(tmp_path, blueprint)
    with pytest.raises(FileExistsError): store.create(opening(blueprint), at=AT)
    updated = store.append("cell_started", start_payload(blueprint), expected_head_sha256=initial["head_sha256"], at=AT)
    assert store.read(expected_head_sha256=updated["head_sha256"])["admissions"] == 1
    before = store.path.read_bytes()
    with pytest.raises(life.LifecycleError): store.append("cell_started", start_payload(blueprint), expected_head_sha256=initial["head_sha256"], at=AT)
    assert store.path.read_bytes() == before
    assert stat_mode(store.path) == 0o600


def stat_mode(path):
    return path.stat().st_mode & 0o777


def test_two_competing_writers_cannot_both_consume_same_head(tmp_path, blueprint):
    store, initial = journal(tmp_path, blueprint)
    def append():
        try:
            life.Journal(store.path, blueprint).append("cell_started", start_payload(blueprint),
                expected_head_sha256=initial["head_sha256"], at=AT)
            return "written"
        except life.LifecycleError:
            return "stale"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: append(), range(2)))
    assert sorted(results) == ["stale", "written"]
    assert store.read()["admissions"] == 1


def process_append(arguments):
    path, blueprint, head = arguments
    try:
        life.Journal(path, blueprint).append("cell_started", start_payload(blueprint), expected_head_sha256=head, at=AT)
        return "written"
    except life.LifecycleError:
        return "stale"


def test_competing_processes_share_the_file_lock_and_head(tmp_path, blueprint):
    store, initial = journal(tmp_path, blueprint)
    arguments = (store.path, blueprint, initial["head_sha256"])
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as pool:
        results = list(pool.map(process_append, [arguments, arguments]))
    assert sorted(results) == ["stale", "written"]
    assert store.read()["admissions"] == 1


def test_completed_session_must_be_audited_before_refilling_capacity(blueprint):
    history = History(blueprint)
    cell = history.start()
    history.close(cell)
    with pytest.raises(life.LifecycleError, match="audit must precede"): history.start()
    history.audit(cell)
    history.start()
    assert history.state["admissions"] == 2


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "fifo"])
def test_unsafe_journal_nodes_are_rejected(tmp_path, blueprint, kind):
    store, _ = journal(tmp_path, blueprint)
    target = tmp_path / "other"
    if kind == "symlink": target.symlink_to(store.path)
    elif kind == "hardlink": os.link(store.path, target)
    elif kind == "directory": target.mkdir()
    else: os.mkfifo(target)
    with pytest.raises((life.LifecycleError, OSError)): life.Journal(target, blueprint).read()


@pytest.mark.parametrize("tail", [b"partial", b'{"seq":1,"seq":2}\n', b"\n", b'{"n":NaN}\n'])
def test_crash_tail_and_invalid_json_are_never_repaired(tmp_path, blueprint, tail):
    store, state = journal(tmp_path, blueprint)
    store.path.write_bytes(store.path.read_bytes() + tail)
    original = store.path.read_bytes()
    with pytest.raises(life.LifecycleError): store.read()
    with pytest.raises(life.LifecycleError): store.append("cell_started", start_payload(blueprint), expected_head_sha256=state["head_sha256"], at=AT)
    assert store.path.read_bytes() == original


def test_partial_write_retains_ambiguous_tail(tmp_path, blueprint, monkeypatch):
    store, state = journal(tmp_path, blueprint)
    original_write = os.write
    calls = []
    def failing(fd, data):
        calls.append(1)
        if len(calls) == 1: return original_write(fd, data[:7])
        raise OSError("synthetic disk failure")
    with monkeypatch.context() as patch:
        patch.setattr(life.os, "write", failing)
        with pytest.raises(OSError):
            store.append("cell_started", start_payload(blueprint), expected_head_sha256=state["head_sha256"], at=AT)
    assert not store.path.read_bytes().endswith(b"\n")
    with pytest.raises(life.LifecycleError): store.read()


def test_disk_durability_includes_file_and_parent(tmp_path, blueprint, monkeypatch):
    calls = []
    original = os.fsync
    def syncing(fd):
        calls.append(os.fstat(fd).st_mode)
        original(fd)
    monkeypatch.setattr(life.os, "fsync", syncing)
    store, state = journal(tmp_path, blueprint)
    store.append("cell_started", start_payload(blueprint), expected_head_sha256=state["head_sha256"], at=AT)
    assert len(calls) == 4


def test_oversized_journal_is_rejected_before_decode(tmp_path, blueprint):
    store, _ = journal(tmp_path, blueprint)
    store.path.write_bytes(b" " * (life.MAX_BYTES + 1))
    with pytest.raises(life.LifecycleError): store.read()


@pytest.mark.parametrize("operation", ["read", "append"])
def test_noncooperating_writer_during_validation_is_detected(tmp_path, blueprint, monkeypatch, operation):
    store, state = journal(tmp_path, blueprint)
    original = life.replay
    modified = []
    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        if not modified:
            store.path.write_bytes(store.path.read_bytes() + b"\n")
            modified.append(True)
        return result
    monkeypatch.setattr(life, "replay", changing)
    with pytest.raises(life.LifecycleError, match="changed"):
        if operation == "read": store.read()
        else: store.append("cell_started", start_payload(blueprint), expected_head_sha256=state["head_sha256"], at=AT)
    assert store.path.read_bytes().endswith(b"\n\n")


def test_replacing_journal_inode_while_locked_is_detected(tmp_path, blueprint, monkeypatch):
    store, _ = journal(tmp_path, blueprint)
    original = life.replay
    def replacing(*args, **kwargs):
        result = original(*args, **kwargs)
        replacement = tmp_path / "replacement"
        replacement.write_bytes(store.path.read_bytes())
        replacement.replace(store.path)
        return result
    monkeypatch.setattr(life, "replay", replacing)
    with pytest.raises(life.LifecycleError, match="journal"): store.read()


def test_parent_replacement_while_locked_is_detected(tmp_path, blueprint, monkeypatch):
    parent = tmp_path / "original"
    parent.mkdir()
    store, _ = journal(parent, blueprint)
    original = life.replay
    def replacing(*args, **kwargs):
        result = original(*args, **kwargs)
        parent.rename(tmp_path / "preserved")
        parent.mkdir()
        return result
    monkeypatch.setattr(life, "replay", replacing)
    with pytest.raises(life.LifecycleError, match="parent changed"): store.read()
    assert (tmp_path / "preserved/lifecycle.jsonl").is_file()


def test_known_cost_subtotal_does_not_hide_unresolved_usage(blueprint):
    history = History(blueprint)
    first, second = history.start(), history.start()
    history.close(first)
    history.audit(first)
    assert history.state["unresolved_cost_cells"] == [second["cell_id"]]
    history.close(second, technical_failure=True, accounting_complete=False, reported_cost_usd=None)
    assert history.state["unresolved_cost_cells"] == [second["cell_id"]]
    assert history.state["known_reported_cost_usd"] == "0.001"


def test_no_runner_auditor_provider_or_budget_is_invoked(blueprint, monkeypatch):
    from creative_machine.formal_routes import production_runner_v1, recipient_runner_v1, production_audit_v1, recipient_audit_v1
    from creative_machine.aws_daily_budget import DailyBudget
    def forbidden(*args, **kwargs): raise AssertionError("lifecycle invoked external work")
    for module, name in ((production_runner_v1, "run_production_session"), (recipient_runner_v1, "run_recipient_session"),
                         (production_audit_v1, "audit_proposer_trace"), (recipient_audit_v1, "audit_recipient_trace"),
                         (DailyBudget, "reserve"), (DailyBudget, "settle")):
        monkeypatch.setattr(module, name, forbidden)
    history = History(blueprint)
    history.proposers()
    history.recipients()
    assert history.add("batch_closed", {})["status"] == "closed"
