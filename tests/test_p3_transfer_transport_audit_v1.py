"""Cross-links are not synthetic-to-experimental promotion or provider proofs."""
import json

import pytest

from creative_machine.formal_routes import production_runner_v1 as production
from creative_machine.formal_routes import transfer_transport_audit_v1 as audit
from creative_machine.formal_routes.transfer_design_v1 import encoded, matrix, sha
from creative_machine.formal_routes.production_contract_v1 import materialize_production_proposer, render_production_proposer
from test_p3_production_runner_v1 import FakeClient, FakeChecker, WORLD, NS, reply
from test_p3_transfer_transport_v1 import fixture, PLAN


def package(tmp_path, *, response=None):
    cell = next(c for c in matrix() if c["role"] == "proposer" and c["arm"] == "D" and c["world_id"] == WORLD.name)
    record = materialize_production_proposer(WORLD, "D", tmp_path / "workspace")
    initial = production.build_production_request([{"role": "user", "content": render_production_proposer(record)}], production.production_config())
    client = FakeClient([response or reply()])
    with fixture(tmp_path, client=client, initial=initial, cell=cell) as f, f.guard as supplied:
        production.run_production_session(record, namespace=NS, artifacts=tmp_path / "raw",
            config=production.production_config(), client=supplied, checker=FakeChecker())
        claim_sha, reserved_sha = f.owner.sha256, sha(encoded(f.reservation))
    return {"cell_id": cell["cell_id"], "data_kind": "synthetic", "expected_plan_sha256": PLAN,
            "expected_closure_sha256": sha((tmp_path / "transport/closure.json").read_bytes()),
            "expected_worker_claim_sha256": claim_sha, "expected_reservation_sha256": reserved_sha}


def check(path, refs):
    return audit.audit_transport_links(path / "transport", path / "raw", **refs)


def rewrite(path, update):
    value = json.loads(path.read_bytes())
    update(value)
    path.write_bytes(encoded(value))


def reseal(path, refs):
    root = path / "transport"
    previous = None
    for rel in sorted(root.glob("[0-9]*.json")):
        rewrite(rel, lambda r: r.update(previous_sha256=previous))
        previous = sha(rel.read_bytes())
    rewrite(root / "closure.json", lambda r: r.update(head_sha256=previous,
        files={p.name: sha(p.read_bytes()) for p in root.iterdir() if p.name != "closure.json"}))
    return {**refs, "expected_closure_sha256": sha((root / "closure.json").read_bytes())}


def test_complete_links_are_read_only_and_do_not_admit_scientific_analysis(tmp_path):
    refs = package(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = check(tmp_path, refs)
    assert result["status"] == "passed" and result["operations"] == 2
    assert result["data_kind"] == "synthetic"
    assert not any(result[k] for k in ("raw_trace_independently_verified", "financial_attestations_verified",
                                      "provider_authenticated", "inference_admitted"))
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("key", ("expected_closure_sha256", "expected_plan_sha256", "expected_worker_claim_sha256", "expected_reservation_sha256"))
def test_external_references_are_required(tmp_path, key):
    refs = package(tmp_path)
    with pytest.raises(audit.TransportAuditError): check(tmp_path, {**refs, key: "d" * 64})


@pytest.mark.parametrize("kind", ("count", "body", "response", "timeout", "timestamp", "financial", "cell", "head", "extra", "profile"))
def test_rehashing_does_not_hide_contradictions(tmp_path, kind):
    refs = package(tmp_path)
    root = tmp_path / "transport"
    if kind == "count": rewrite(root / "0002.json", lambda r: r.update(input_tokens=101))
    elif kind == "body": rewrite(root / "0003.json", lambda r: r.update(body_sha256="a" * 64))
    elif kind == "response": rewrite(root / "0004.json", lambda r: r["response"]["usage"].update(output_tokens=1))
    elif kind == "timeout": rewrite(root / "0003.json", lambda r: r.update(timeout_seconds=1))
    elif kind == "timestamp": rewrite(root / "0003.json", lambda r: r.update(at="2026-09-01T00:00:00+00:00"))
    elif kind == "financial": rewrite(root / "0003.json", lambda r: r["financial_check"].update(external_upper_usd="101"))
    elif kind == "cell": rewrite(root / "binding.json", lambda r: r.update(cell_id=matrix()[0]["cell_id"] + "wrong"))
    elif kind == "extra": (root / "unexpected.json").write_bytes(b"{}\n")
    elif kind == "profile": rewrite(root / "binding.json", lambda r: r.update(data_kind="experimental"))
    refs = reseal(tmp_path, refs)
    if kind == "head":
        rewrite(root / "closure.json", lambda r: r.update(head_sha256="a" * 64))
        refs["expected_closure_sha256"] = sha((root / "closure.json").read_bytes())
    with pytest.raises(audit.TransportAuditError): check(tmp_path, refs)


def test_synthetic_package_cannot_be_claimed_experimental(tmp_path):
    refs = package(tmp_path)
    with pytest.raises(audit.TransportAuditError): check(tmp_path, {**refs, "data_kind": "experimental"})


def test_transport_error_is_blocked_not_a_scientific_zero(tmp_path):
    refs = package(tmp_path, response=RuntimeError("synthetic timeout"))
    with pytest.raises(audit.TransportAuditBlocked): check(tmp_path, refs)


def test_raw_change_without_matching_transport_is_rejected(tmp_path):
    refs = package(tmp_path)
    path = tmp_path / "raw/events.jsonl"
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    next(r for r in events if r["event"] == "response")["body"]["usage"]["output_tokens"] = 99
    path.write_bytes(b"".join((json.dumps(row) + "\n").encode() for row in events))
    with pytest.raises(audit.TransportAuditError): check(tmp_path, refs)


def test_raw_mutation_during_audit_is_detected(tmp_path, monkeypatch):
    refs = package(tmp_path)
    original = audit._snapshot
    seen = 0
    def mutate(path):
        nonlocal seen
        result = original(path)
        seen += 1
        if seen == 2:
            with (tmp_path / "raw/events.jsonl").open("ab") as handle: handle.write(b"{}\n")
        return result
    monkeypatch.setattr(audit, "_snapshot", mutate)
    with pytest.raises(audit.TransportAuditError): check(tmp_path, refs)
