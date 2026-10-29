"""Integrated synthetic choreography, not experimental observations or judges."""
from copy import deepcopy
import json
import os

import pytest

from creative_machine.formal_routes import transfer_rehearsal_v1 as rehearsal
from creative_machine.formal_routes import bridge_content_v1 as content
from creative_machine.formal_routes.transfer_design_v1 import encoded, load_blueprint, sha
from test_p3_production_audit_v1 import REPO, BRIDGE, BAD, LOCAL_LEAN, fixture_check, submission, terminal
from test_p3_recipient_audit_v1 import check as recipient_check
from test_p3_recipient_runner_v1 import FakeLean, reply, stopped
from test_p3_bridge_content_v1 import review_for, judgment

BLUEPRINT = load_blueprint(REPO)
CELLS = BLUEPRINT["cells"]


def scenario(proposer=None):
    return {cell["cell_id"]: [{"input_tokens": 100, "response": response}
        for response in ((proposer if proposer is not None else [submission()])
                         if cell["role"] == "proposer" else [reply()])]
        for cell in CELLS}


def review(packet):
    return review_for({"packet": packet, "binding": {"packet_sha256": sha(encoded(packet))}})


def run(tmp_path, fixtures=None, reviewer=review, **kwargs):
    return rehearsal.run_rehearsal(REPO, tmp_path / "run", scenario() if fixtures is None else fixtures,
        reviewer=reviewer, permitted_reviewer_ids=("fixture-reviewer",), proposer_checker=fixture_check,
        recipient_checker=recipient_check, bridge_process_runner=FakeLean(), bridge_lake="fixture-lake", **kwargs)


def read(tmp_path, rel):
    return json.loads((tmp_path / "run" / rel).read_text())


def history(tmp_path):
    return [json.loads(line) for line in (tmp_path / "run/lifecycle.jsonl").read_text().splitlines()]


def test_full_26_positions_review_barrier_exact_bridge_and_sealed_package(tmp_path):
    seen = []
    fixtures = scenario([submission(solution=BAD), terminal()])
    before = deepcopy(fixtures)

    def reviewer(packet):
        assert len(list((tmp_path / "run/cells").iterdir())) == 6
        assert set(packet) == content.PACKET_KEYS
        seen.append(packet["review_id"])
        return review(packet)

    result = run(tmp_path, fixtures, reviewer)
    assert fixtures == before
    assert result["status"] == "complete_rehearsal"
    assert result["recorded_session_count"] == result["audited_session_count"] == 26
    assert result["review_packet_count"] == 6 and seen == sorted(seen)
    assert result["data_kind"] == "synthetic" and not result["inference_admitted"]
    assert not result["independent_batch_audit_passed"] and not result["real_reservation_created"]
    dataset, analysis = read(tmp_path, "dataset.json"), read(tmp_path, "analysis.json")
    assert analysis["status"] == "not_interpretable" and analysis["contrasts"] is None
    assert dataset["batch_audit"]["status"] == "pending" and not dataset["batch_audit"]["phase_barrier_verified"]
    rows = {row["cell_id"]: row for row in dataset["cells"]}
    assert all(row["state"] == "completed" for row in rows.values())
    for cell in CELLS[:6]:
        assert rows[cell["cell_id"]]["observation"]["visible_solved"] is False
        assert rows[cell["cell_id"]]["observation"]["content_audit"] == "passed"
    for cell in CELLS[6:]:
        if cell["bridge_kind"] == "candidate":
            assert (tmp_path / "run/cells" / cell["cell_id"] / "workspace/Bridge.lean").read_bytes() == BRIDGE.encode()
            assert rows[cell["cell_id"]]["observation"]["bridge_sha256"] == rows[cell["parent_proposer_id"]]["observation"]["selected_bridge_sha256"]
    events = history(tmp_path)
    started = [event["payload"]["cell_id"] for event in events if event["event"] == "cell_started"]
    assert started == [cell["cell_id"] for cell in CELLS]
    barrier = next(event["seq"] for event in events if event["event"] == "phase_barrier")
    assert all(event["seq"] < barrier for event in events if event["event"] == "review_recorded")
    assert events[-1]["event"] == "batch_closed"
    manifest = read(tmp_path, "closure_manifest.json")
    assert sha((tmp_path / "run/closure_manifest.json").read_bytes()) == result["closure_manifest_sha256"]
    actual = rehearsal._inventory(tmp_path / "run")
    actual.pop("closure_manifest.json")
    assert len(actual) > 256
    assert manifest["entries"] == {rel: {k: v for k, v in item.items() if k not in ("device", "inode")} for rel, item in actual.items()}


@pytest.mark.parametrize("responses", ([terminal()], [submission(BAD, None), terminal()]))
def test_absent_or_invalid_bridge_runs_only_six_proposers_and_eight_controls(tmp_path, responses):
    def never(packet):
        pytest.fail("ineligible bridge must not be reviewed")
    result = run(tmp_path, scenario(responses), never)
    assert result["status"] == "complete_rehearsal" and result["recorded_session_count"] == 14
    assert result["review_packet_count"] == 0
    rows = read(tmp_path, "dataset.json")["cells"]
    assert sum(r["state"] == "skipped_no_bridge" for r in rows) == 12
    assert sum(r["state"] == "completed" for r in rows) == 14


@pytest.mark.parametrize("outcome", ("violation", "uncertain", "none"))
def test_content_rejection_or_pending_never_admits_candidate_recipients(tmp_path, outcome):
    def reviewer(packet):
        if outcome == "none":
            return None
        result = review(packet)
        result["criteria"]["mathematical_scope"] = judgment(outcome, packet["bridge_utf8"].encode())
        return result
    result = run(tmp_path, reviewer=reviewer)
    assert result["recorded_session_count"] == (14 if outcome == "violation" else 6)
    assert result["status"] == ("complete_rehearsal" if outcome == "violation" else "awaiting_synthetic_review")
    rows = read(tmp_path, "dataset.json")["cells"]
    if outcome != "violation":
        assert all(row["state"] == "not_started" for row in rows[6:])
        assert not any(e["event"] == "phase_barrier" for e in history(tmp_path))


@pytest.mark.parametrize("position", (0, 3, 6, 15, 25))
def test_exhausted_provider_halts_and_preserves_technical_cell_not_unstarted(tmp_path, position):
    fixtures = scenario()
    fixtures[CELLS[position]["cell_id"]] = []
    result = run(tmp_path, fixtures)
    assert result["status"] == "halted_rehearsal" and result["recorded_session_count"] == position + 1
    assert result["audited_session_count"] == position
    rows = read(tmp_path, "dataset.json")["cells"]
    assert rows[position]["state"] == "technical_failure"
    assert rows[position]["trace_audit"] == "failed" and rows[position]["accounting"] == "pending"
    assert rows[position]["observation"] is None and rows[position]["evidence_sha256"] is not None
    assert all(row["state"] == "not_started" for row in rows[position + 1:])


def test_materialization_failure_before_intent_does_not_invent_session(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic preparation failure")
    monkeypatch.setattr(rehearsal.proposer_contract, "materialize_production_proposer", fail)
    result = run(tmp_path)
    assert result["status"] == "halted_rehearsal" and result["recorded_session_count"] == 0
    assert all(r["state"] == "not_started" for r in read(tmp_path, "dataset.json")["cells"])


def test_runner_failure_after_intent_keeps_active_unresolved_cell(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic runner crash")
    monkeypatch.setattr(rehearsal.proposer_runner, "run_production_session", fail)
    result = run(tmp_path)
    assert result["status"] == "halted_rehearsal" and result["recorded_session_count"] == 1
    assert history(tmp_path)[-1]["event"] == "halted"
    row = read(tmp_path, "dataset.json")["cells"][0]
    assert row["state"] == "technical_failure" and row["evidence_sha256"] is None


def test_invalid_review_halts_without_scoring_or_replacement(tmp_path):
    result = run(tmp_path, reviewer=lambda packet: {"passed": True})
    assert result["status"] == "halted_rehearsal" and result["recorded_session_count"] == 6
    assert not any(e["event"] == "phase_barrier" for e in history(tmp_path))


@pytest.mark.parametrize("target", ("raw", "receipt", "packet", "extra", "directory", "replacement", "symlink", "hardlink", "journal"))
def test_review_callback_cannot_change_retained_package_or_admit_recipients(tmp_path, target):
    root = tmp_path / "run"
    def corrupt(packet):
        path = root / "cells" / CELLS[0]["cell_id"] / "artifacts/session.json"
        if target == "receipt": path = root / "rehearsal_plan.json"
        if target == "packet": path = root / "review_packets" / (packet["review_id"] + ".json")
        if target == "journal": path = root / "lifecycle.jsonl"
        if target == "extra": (root / "extra").write_text("unbound")
        elif target == "directory": (root / "extra").mkdir()
        elif target == "replacement":
            replacement = root / "replacement"
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
        elif target == "symlink": (root / "extra").symlink_to(path)
        elif target == "hardlink": os.link(path, root / "extra")
        else: path.write_bytes(path.read_bytes() + b" ")
        return review(packet)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        run(tmp_path, reviewer=corrupt)
    assert len(list((root / "cells").iterdir())) == 6
    assert not (root / "summary.json").exists() and not (root / "closure_manifest.json").exists()


def test_destination_exclusive_and_scenario_complete_before_work(tmp_path):
    fixtures = scenario()
    fixtures.pop(CELLS[-1]["cell_id"])
    with pytest.raises(ValueError, match="26 fixed"):
        run(tmp_path, fixtures)
    assert not (tmp_path / "run").exists()
    (tmp_path / "run").mkdir()
    (tmp_path / "run/keep").write_text("untouched")
    with pytest.raises(FileExistsError):
        run(tmp_path)
    assert (tmp_path / "run/keep").read_text() == "untouched"


def test_recorded_client_copies_inputs_and_responses_without_factory():
    steps = [{"input_tokens": 100, "response": reply()}]
    client = rehearsal.RecordedClient(steps)
    steps.clear()
    assert client.max_retries == 0 and client.count_tokens().input_tokens == 100
    response = client.create()
    response.model_dump()["content"].clear()
    assert response.model_dump()["content"]
    with pytest.raises(RuntimeError, match="exhausted"):
        client.count_tokens()


def test_checkpoint_failure_after_durable_intent_is_not_preparation_failure(tmp_path, monkeypatch):
    original = rehearsal._save_new
    def save(path, value):
        if path.name == "0002.json":
            raise OSError("synthetic checkpoint failure after journal append")
        return original(path, value)
    monkeypatch.setattr(rehearsal, "_save_new", save)
    result = run(tmp_path)
    assert result["status"] == "halted_rehearsal" and result["recorded_session_count"] == 1
    assert history(tmp_path)[-1]["event"] == "halted"
    assert read(tmp_path, "dataset.json")["cells"][0]["state"] == "technical_failure"


def test_new_receipt_never_follows_a_replaced_parent_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "receipts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        rehearsal._save_new(tmp_path / "receipts/new.json", {"synthetic": True})
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("kind", ("list", "extra_key", "too_many_steps", "bad_step", "nonfinite"))
def test_invalid_scenario_fails_before_creating_output(tmp_path, kind):
    fixtures = scenario()
    identity = CELLS[0]["cell_id"]
    if kind == "list": fixtures = list(fixtures)
    elif kind == "extra_key": fixtures["extra"] = []
    elif kind == "too_many_steps": fixtures[identity] *= 13
    elif kind == "bad_step": fixtures[identity][0]["unexpected"] = True
    else: fixtures[identity][0]["input_tokens"] = float("inf")
    with pytest.raises(ValueError):
        run(tmp_path, fixtures)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("kind", ("symlink", "hardlink", "fifo", "large_file", "large_total"))
def test_bounded_inventory_rejects_unsafe_entries(tmp_path, monkeypatch, kind):
    root = tmp_path / "inventory"
    root.mkdir()
    source = root / "source"
    source.write_bytes(b"0123456789")
    if kind == "symlink": (root / "link").symlink_to(source)
    elif kind == "hardlink": os.link(source, root / "link")
    elif kind == "fifo": os.mkfifo(root / "pipe")
    elif kind == "large_file": monkeypatch.setattr(rehearsal.proposer_audit, "MAX_FILE_BYTES", 5)
    else: monkeypatch.setattr(rehearsal.proposer_audit, "MAX_TOTAL_BYTES", 5)
    with pytest.raises(ValueError):
        rehearsal._inventory(root)


def test_inventory_retains_empty_directories_and_detects_same_byte_replacement(tmp_path):
    root = tmp_path / "inventory"
    root.mkdir()
    (root / "empty").mkdir()
    (root / "source").write_bytes(b"fixture")
    before = rehearsal._inventory(root)
    assert before["empty"]["kind"] == "directory"
    (root / "replacement").write_bytes(b"fixture")
    os.replace(root / "replacement", root / "source")
    after = rehearsal._inventory(root)
    assert before["source"]["sha256"] == after["source"]["sha256"]
    assert before["source"]["inode"] != after["source"]["inode"]


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_two_family_proposers_then_technical_halt(tmp_path):
    # Known True lemmas only: this tests integration with the actual kernel,
    # never model ability. The third provider is deliberately exhausted.
    fixtures = scenario([submission(solution=None), terminal()])
    fixtures[CELLS[2]["cell_id"]] = []
    assert {c["family"] for c in CELLS[:2]} == {"invariant", "representation"}
    result = rehearsal.run_rehearsal(REPO, tmp_path / "run", fixtures, reviewer=review,
        permitted_reviewer_ids=("fixture-reviewer",))
    assert result["status"] == "halted_rehearsal" and result["audited_session_count"] == 2
    rows = read(tmp_path, "dataset.json")["cells"]
    for row in rows[:2]:
        assert row["state"] == "completed" and row["observation"]["production_outcome"] == "valid_bridge"
        assert row["observation"]["selected_bridge_sha256"] == sha(BRIDGE.encode())
        assert row["observation"]["visible_solved"] is False
    assert rows[2]["state"] == "technical_failure"
    assert all(row["state"] == "not_started" for row in rows[3:])
