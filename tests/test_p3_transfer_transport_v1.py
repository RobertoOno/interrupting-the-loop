"""Offline transport gates with a temporary journal; no provider requests."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from creative_machine import aws_daily_budget as legacy
from creative_machine.formal_routes import production_runner_v1 as production
from creative_machine.formal_routes import recipient_runner_v1 as recipient
from creative_machine.formal_routes import transfer_transport_v1 as transport
from creative_machine.formal_routes.transfer_budget_v1 import TransferBudget, BudgetAdmissionError
from creative_machine.formal_routes.transfer_design_v1 import encoded, matrix, sha
from creative_machine.formal_routes.transfer_worker_v1 import WorkerClaim, WorkerOwnershipError
from test_p3_transfer_budget_v1 import NOW, PLAN, ALLOW, reconciliation, reserve
from test_p3_production_runner_v1 import FakeClient, FakeChecker, stopped, reply, WORLD, NS
from creative_machine.formal_routes.production_contract_v1 import materialize_production_proposer, render_production_proposer


@contextmanager
def fixture(tmp_path, *, role="proposer", client=None, initial=None, cell=None):
    cell = cell or next(c for c in matrix() if c["role"] == role)
    builder = production.build_production_request if role == "proposer" else recipient.build_recipient_request
    body = initial or builder([{"role": "user", "content": "synthetic input"}], production.production_config())
    path = tmp_path / "daily.jsonl"
    clock = [NOW]
    budget = TransferBudget(path, data_kind="synthetic", clock=lambda: clock[0])
    receipt = reconciliation(path)
    logs = []
    def supplier():
        logs.append(True)
        return receipt, sha(encoded(receipt))
    with WorkerClaim(tmp_path / "claims", "synthetic-run", PLAN) as owner:
        reservation = reserve(budget, owner, receipt)
        raw = client or FakeClient([stopped()])
        guarded = transport.ProtectedSession(raw, owner=owner, budget=budget, reservation=reservation,
            expected_reservation_sha256=sha(encoded(reservation)), reconciliation_supplier=supplier,
            permitted_reconcilers=ALLOW, cell_id=cell["cell_id"], initial_request=body,
            artifacts=tmp_path / "transport")
        yield SimpleNamespace(guard=guarded, client=raw, owner=owner, budget=budget, reservation=reservation,
            receipt=receipt, logs=logs, clock=clock, body=body, path=path)


def count(f):
    return f.client.messages.count_tokens(**deepcopy(f.body), timeout=30)


def create(f, **changes):
    args = {**deepcopy(f.body), "max_tokens": 16384, "timeout": 300}
    args.update(changes)
    return f.client.messages.create(**args)


@pytest.mark.parametrize("role", ("proposer", "recipient"))
def test_native_class_exact_request_and_financial_checks_each_time(tmp_path, role):
    with fixture(tmp_path, role=role) as f:
        original_type = type(f.client)
        with f.guard as client:
            assert client is f.client and type(client) is original_type
            assert count(f).input_tokens == 100
            create(f)
            assert len(f.logs) == 3
        assert f.client.count_calls == [{**f.body, "timeout": 30}]
        assert f.client.create_calls == [{**f.body, "max_tokens": 16384, "timeout": 300}]
        with pytest.raises(transport.TransportGateError): count(f)
        with pytest.raises(transport.TransportGateError): f.guard.__enter__()
    root = tmp_path / "transport"
    closure = json.loads((root / "closure.json").read_bytes())
    assert not closure["failed"] and not closure["provider_authenticated"]
    assert closure["external_reservation_must_remain_open"]
    assert closure["events"] == 4
    previous = None
    for index in range(1, 5):
        data = (root / f"{index:04d}.json").read_bytes()
        row = json.loads(data)
        assert row["previous_sha256"] == previous and row["seq"] == index
        previous = sha(data)
    assert closure["head_sha256"] == previous
    assert all(sha((root / name).read_bytes()) == digest for name, digest in closure["files"].items())


@pytest.mark.parametrize("change", ("create_first", "count_twice", "model", "input", "tool", "extra", "tokens", "timeout"))
def test_request_drift_or_out_of_order_never_reaches_provider(tmp_path, change):
    with fixture(tmp_path) as f, f.guard:
        if change != "create_first": count(f)
        with pytest.raises(transport.TransportGateError):
            if change == "count_twice": count(f)
            elif change == "create_first": create(f)
            else:
                args = {"model": "different"} if change == "model" else (
                    {"messages": [{"role": "user", "content": "different"}]} if change == "input" else
                    {"tools": []} if change == "tool" else {"stream": True} if change == "extra" else
                    {"max_tokens": 16385} if change == "tokens" else {"timeout": 301})
                create(f, **args)
        assert not f.client.create_calls
        with pytest.raises(transport.TransportGateError): count(f)


@pytest.mark.parametrize("change", ("stale", "owner_closed", "retry", "settled", "messages", "journal"))
def test_changed_external_gate_blocks_inference_after_count(tmp_path, change):
    with fixture(tmp_path) as f, f.guard:
        count(f)
        if change == "stale": f.clock[0] += timedelta(minutes=31)
        elif change == "owner_closed": f.owner.close()
        elif change == "retry": f.client.max_retries = 2
        elif change == "messages": f.client.messages = f.guard.original
        elif change == "journal":
            with f.path.open("ab") as handle: handle.write(b"partial")
        else:
            event = {"event": "settle", "run_id": "synthetic-run", "usd": "0",
                     "at": NOW.astimezone(legacy.ZONE).isoformat(),
                     "basis": "reported tokens at frozen list rates; not invoice"}
            with f.path.open("ab") as handle: handle.write((json.dumps(event) + "\n").encode())
        with pytest.raises((transport.TransportGateError, BudgetAdmissionError, WorkerOwnershipError, ValueError)):
            f.guard.create(**f.body, max_tokens=16384, timeout=300)
        assert not f.client.create_calls


def test_provider_failure_is_not_retried_and_preserves_before_receipt(tmp_path):
    with fixture(tmp_path, client=FakeClient([RuntimeError("synthetic timeout")])) as f, f.guard:
        count(f)
        with pytest.raises(RuntimeError, match="synthetic timeout"): create(f)
        with pytest.raises(transport.TransportGateError): create(f)
        assert len(f.client.create_calls) == 1
    closure = json.loads((tmp_path / "transport/closure.json").read_bytes())
    assert closure["failed"] and closure["events"] == 3
    assert len(f.path.read_bytes().splitlines()) == 1  # Reservation remains.


@pytest.mark.parametrize("change", ("model", "usage", "overrun"))
def test_response_error_preserves_raw_payload_before_failure(tmp_path, change):
    payload = stopped()
    if change == "model": payload["model"] = "unknown"
    elif change == "usage": payload["usage"].pop("input_tokens")
    else: payload["usage"]["output_tokens"] = 16385
    with fixture(tmp_path, client=FakeClient([payload])) as f, f.guard:
        count(f)
        with pytest.raises(RuntimeError): create(f)
        row = json.loads((tmp_path / "transport/0004.json").read_bytes())
        assert row["response"] == payload and row["response_sha256"] == sha(encoded(payload))
        with pytest.raises(transport.TransportGateError): create(f)


def test_terminal_response_forbids_additional_turn(tmp_path):
    with fixture(tmp_path) as f, f.guard:
        count(f)
        create(f)
        with pytest.raises(transport.TransportGateError, match="terminal"): count(f)
        assert len(f.client.count_calls) == 1


def test_guard_works_with_unchanged_proposer_runner(tmp_path):
    record = materialize_production_proposer(WORLD, "D", tmp_path / "workspace")
    initial = production.build_production_request([{"role": "user", "content": render_production_proposer(record)}], production.production_config())
    client = FakeClient([reply()])
    with fixture(tmp_path, client=client, initial=initial) as f, f.guard as supplied:
        result = production.run_production_session(record, namespace=NS, artifacts=tmp_path / "raw",
            config=production.production_config(), client=supplied, checker=FakeChecker())
    assert result["status"] == "both_verified" and result["accounting_complete"]
    raw = json.loads((tmp_path / "raw/input.json").read_bytes())
    assert raw["client_class"] == f"{type(client).__module__}.{type(client).__qualname__}"


def test_revision_keeps_the_original_total_output_ceiling(tmp_path):
    record = materialize_production_proposer(WORLD, "D", tmp_path / "workspace")
    initial = production.build_production_request([{"role": "user", "content": render_production_proposer(record)}], production.production_config())
    client = FakeClient([reply(output=16000), reply(identity="call2", output=100)])
    with fixture(tmp_path, client=client, initial=initial) as f, f.guard as supplied:
        result = production.run_production_session(record, namespace=NS, artifacts=tmp_path / "raw",
            config=production.production_config(), client=supplied,
            checker=FakeChecker(outcomes=(("rejected", "blocked_by_bridge"), ("valid", "valid"))))
    assert result["status"] == "both_verified"
    assert [call["max_tokens"] for call in client.create_calls] == [16384, 4000]


def test_guard_works_with_unchanged_recipient_runner(tmp_path):
    from test_p3_recipient_runner_v1 import B, REPO, FakeChecker as RecipientChecker, prepare, reply as recipient_reply
    from creative_machine.formal_routes.recipient_contract_v1 import render_recipient
    record, candidate = prepare(tmp_path)
    initial = recipient.build_recipient_request([{"role": "user", "content": render_recipient(record,
        repository=REPO, cell_id=B["cell_id"], candidate=candidate)}], recipient.recipient_config())
    client = FakeClient([recipient_reply()])
    with fixture(tmp_path, role="recipient", cell=B, client=client, initial=initial) as f, f.guard as supplied:
        result = recipient.run_recipient_session(record, repository=REPO, cell_id=B["cell_id"], candidate=candidate,
            artifacts=tmp_path / "raw", config=recipient.recipient_config(), client=supplied, checker=RecipientChecker())
    assert result["status"] == "proof_verified" and result["accounting_complete"]


def test_twelfth_request_is_the_last_admissible_turn(tmp_path):
    with fixture(tmp_path, client=FakeClient([reply(identity=f"call{i}") for i in range(12)])) as f, f.guard:
        for _ in range(12):
            count(f)
            create(f)
        with pytest.raises(transport.TransportGateError, match="turn ceiling"): count(f)
        assert len(f.client.create_calls) == len(f.client.count_calls) == 12


def test_native_count_over_budget_does_not_admit_inference(tmp_path):
    with fixture(tmp_path, client=FakeClient([], count=200000)) as f, f.guard:
        count(f)
        with pytest.raises(transport.TransportGateError, match="admitted native count"): create(f)
        assert not f.client.create_calls


def test_reentrant_call_never_dispatches_nested_request(tmp_path):
    with fixture(tmp_path) as f, f.guard:
        f.client.on_count = lambda: f.guard.count_tokens(**f.body, timeout=30)
        with pytest.raises(transport.TransportGateError, match="reentrant"): count(f)
        assert len(f.client.count_calls) == 1 and not f.client.create_calls


def test_catching_nested_error_does_not_reopen_guard(tmp_path):
    with fixture(tmp_path) as f, f.guard:
        def nested():
            with pytest.raises(transport.TransportGateError): f.guard.count_tokens(**f.body, timeout=30)
        f.client.on_count = nested
        with pytest.raises(transport.TransportGateError, match="nested operation"): count(f)
        with pytest.raises(transport.TransportGateError): create(f)
        assert not f.client.create_calls


def test_admission_failure_happens_before_transport_creation(tmp_path):
    with fixture(tmp_path) as f:
        f.clock[0] += timedelta(minutes=31)
        with pytest.raises(BudgetAdmissionError): f.guard.__enter__()
        assert not f.guard.artifacts.exists() and not f.client.count_calls


def test_evidence_tamper_blocks_request_and_never_overwrites(tmp_path):
    with fixture(tmp_path) as f:
        with pytest.raises(transport.TransportGateError, match="evidence changed"):
            with f.guard:
                path = f.guard.artifacts / "binding.json"
                path.write_bytes(b"tampered")
                with pytest.raises(transport.TransportGateError): count(f)
        assert path.read_bytes() == b"tampered" and not f.client.count_calls


def test_failed_durable_intent_never_calls_provider(tmp_path, monkeypatch):
    with fixture(tmp_path) as f, f.guard:
        original = production._write_new
        def fail(path, data):
            if path.name == "0001.json": raise OSError("synthetic fsync failure")
            return original(path, data)
        monkeypatch.setattr(production, "_write_new", fail)
        with pytest.raises(OSError): count(f)
        assert not f.client.count_calls


def test_native_client_validation_is_offline_and_rejects_fake():
    pytest.importorskip("anthropic")
    with pytest.raises(transport.TransportGateError, match="native Mantle"):
        transport.validate_experimental_client(FakeClient([]), production.production_config())


def test_actual_sdk_configuration_checked_without_requests(monkeypatch):
    sdk = pytest.importorskip("anthropic")
    client = sdk.AnthropicBedrockMantle(aws_profile="main-account", aws_region="us-east-1",
        base_url=transport.ENDPOINT, max_retries=0, timeout=300)
    try:
        transport.validate_experimental_client(client, production.production_config())
        client.max_retries = 1
        with pytest.raises(transport.TransportGateError):
            transport.validate_experimental_client(client, production.production_config())
    finally:
        client.close()
