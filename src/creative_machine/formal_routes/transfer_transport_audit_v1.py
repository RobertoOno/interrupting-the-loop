"""Read-only cross-check of host transport receipts against a session trace.

Does not call a runner/client, redo content judgment, authenticate the provider,
validate the real budget attestation or substitute for the independent Lean
trace/batch audits. Both source trees remain unmodified.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from .production_audit_v1 import _decode, _snapshot
from .production_runner_v1 import build_production_request, production_config
from .recipient_runner_v1 import build_recipient_request
from .transfer_design_v1 import encoded, matrix, sha
from .transfer_lifecycle_v1 import instant, is_hash, money
from .transfer_transport_v1 import VERSION


class TransportAuditError(ValueError):
    pass


class TransportAuditBlocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise TransportAuditError(message)


def equal(actual, expected, label):
    require(encoded(actual) == encoded(expected), "transport mismatch: " + label)


def audit_transport_links(transport_artifacts: Path, session_artifacts: Path, *, cell_id: str,
                          data_kind: str, expected_closure_sha256: str, expected_plan_sha256: str,
                          expected_worker_claim_sha256: str, expected_reservation_sha256: str):
    refs = (expected_closure_sha256, expected_plan_sha256, expected_worker_claim_sha256, expected_reservation_sha256)
    require(all(is_hash(x) for x in refs), "external transport references required")
    require(data_kind in ("synthetic", "experimental"), "explicit transport profile required")
    cells = {c["cell_id"]: c for c in matrix()}
    require(cell_id in cells, "unknown transport cell")
    files, dirs = _snapshot(Path(transport_artifacts))
    raw, raw_dirs = _snapshot(Path(session_artifacts))
    require(not dirs and "closure.json" in files, "transport closure missing or unexpected directory")
    require(sha(files["closure.json"]) == expected_closure_sha256, "external transport closure reference")
    closure = _decode(files["closure.json"])
    require(isinstance(closure, dict) and type(closure.get("events")) is int
            and 0 <= closure["events"] <= 48 and type(closure.get("failed")) is bool, "closure schema")
    equal(closure, {"version": VERSION, "data_kind": data_kind, "events": closure["events"],
        "head_sha256": closure.get("head_sha256"), "files": {k: sha(v) for k, v in files.items() if k != "closure.json"},
        "failed": closure["failed"], "provider_authenticated": False, "external_reservation_must_remain_open": True}, "closure inventory/schema")
    require(set(files) == {"binding.json", "closure.json"} | {f"{i:04d}.json" for i in range(1, closure["events"] + 1)}, "transport event inventory")
    if closure["failed"]:
        raise TransportAuditBlocked("failed/uncertain transport; preserve reservation, no scientific projection")
    binding = _decode(files["binding.json"])
    require(isinstance(binding, dict) and "admission_financial_check" in binding, "binding schema")
    config = production_config()
    require("input.json" in raw and "events.jsonl" in raw, "missing raw session input/events")
    source = _decode(raw["input.json"])
    builder = build_production_request if cells[cell_id]["role"] == "proposer" else build_recipient_request
    equal(source["config"], asdict(config), "raw configuration")
    if data_kind == "experimental":
        require(source.get("client_class") == "anthropic.lib.bedrock._mantle.AnthropicBedrockMantle"
                and source.get("checker_injected") is False, "experimental raw profile drift")
    equal(binding, {"version": VERSION, "data_kind": data_kind, "cell_id": cell_id,
        "execution_plan_sha256": expected_plan_sha256, "worker_claim_sha256": expected_worker_claim_sha256,
        "reservation_sha256": expected_reservation_sha256,
        "initial_request_sha256": sha(encoded(builder(source["messages"], config))), "config": asdict(config),
        "admission_financial_check": binding["admission_financial_check"], "provider_authenticated": False}, "cell/plan/worker/reservation binding")

    financial_refs = set()

    def financial(value):
        require(isinstance(value, dict) and is_hash(value.get("ledger_sha256"))
                and is_hash(value.get("reconciliation_sha256")), "financial reference shape")
        equal(value, {"status": "local_reservation_checked", "data_kind": data_kind,
            "ledger_sha256": value["ledger_sha256"], "reconciliation_sha256": value["reconciliation_sha256"],
            "local_committed_usd": value.get("local_committed_usd"), "external_upper_usd": value.get("external_upper_usd"),
            "external_reservation_must_remain_open": True, "inference_admitted": False}, "financial check schema")
        # The live financial gate supplies the precise sum; here check bounds
        # independently using the bounded decimal parser (not binary floats).
        from decimal import localcontext
        with localcontext() as ctx:
            ctx.prec = 100
            local, external = money(value["local_committed_usd"]), money(value["external_upper_usd"])
            require(local >= Decimal("50") and local + external <= Decimal("150"), "financial check bounds")
        financial_refs.add(value["reconciliation_sha256"])

    financial(binding["admission_financial_check"])
    require(raw["events.jsonl"].endswith(b"\n"), "partial raw event stream")
    events = [_decode(line) for line in raw["events.jsonl"].splitlines()]
    dispatch = [r for r in events if r["event"] in ("count_started", "request")]
    finished = {(r["event"], r["turn"]): r for r in events if r["event"] in ("count_finished", "response")}
    require(len(finished) == sum(r["event"] in ("count_finished", "response") for r in events), "duplicate raw completion")
    require(closure["events"] == len(dispatch) * 2, "unpaired/missing transport operation")
    previous, at = None, None
    used_finishes = set()
    for index, start in enumerate(dispatch):
        method, end_kind = ("count_tokens", "count_finished") if start["event"] == "count_started" else ("create", "response")
        end_key = (end_kind, start["turn"])
        require(end_key in finished, "missing raw completion")
        end = finished[end_key]
        used_finishes.add(end_key)
        for offset, kind in ((1, "before_request"), (2, "after_request")):
            seq = index * 2 + offset
            data = files[f"{seq:04d}.json"]
            row = _decode(data)
            current = instant(row["at"])
            require((at is None or current >= at) and instant(start["at"]) <= current <= instant(end["at"]), "transport/raw chronology mismatch")
            base = {"seq": seq, "previous_sha256": previous, "event": kind, "at": row["at"], "method": method, "turn": start["turn"]}
            if offset == 1:
                financial(row["financial_check"])
                expected = {**base, "body_sha256": sha(encoded(start["body"])),
                            "timeout_seconds": start["timeout_seconds"], "financial_check": row["financial_check"]}
            elif method == "count_tokens":
                expected = {**base, "input_tokens": end["input_tokens"]}
            else:
                expected = {**base, "response_sha256": sha(encoded(end["body"])), "response": end["body"]}
            equal(row, expected, "raw request/response link")
            previous, at = sha(data), current
    require(used_finishes == set(finished) and previous == closure["head_sha256"], "transport tail or extra completion")
    require(_snapshot(Path(transport_artifacts)) == (files, dirs) and _snapshot(Path(session_artifacts)) == (raw, raw_dirs), "transport/raw changed during audit")
    return {"version": "p3_transfer_transport_audit_v1", "status": "passed", "data_kind": data_kind,
        "cell_id": cell_id, "transport_closure_sha256": expected_closure_sha256,
        "execution_plan_sha256": expected_plan_sha256, "worker_claim_sha256": expected_worker_claim_sha256,
        "reservation_sha256": expected_reservation_sha256, "operations": len(dispatch),
        "reconciliation_sha256": sorted(financial_refs), "raw_file_sha256": {name: sha(data) for name, data in raw.items()},
        "raw_directories": sorted(raw_dirs), "raw_trace_independently_verified": False,
        "financial_attestations_verified": False, "provider_authenticated": False, "inference_admitted": False,
        "scope": "host transport/raw cross-links only; requires independent trace, budget and batch audits"}
