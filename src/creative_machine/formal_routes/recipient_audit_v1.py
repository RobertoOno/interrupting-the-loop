"""Independent reconstruction of sealed recipient traces, with fresh Lean checks.

Only frozen interface constants come from the runner. Low-level safe inventory,
strict JSON and timestamp utilities are shared with the proposer auditor. No
runner execution, request/feedback helper, TokenBudget or provider call is used.
The future batch layer must validate parent/content/barrier and external costs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math
from pathlib import Path
import re
import tempfile
from typing import Callable

from . import production_audit_v1 as evidence
from . import recipient_contract_v1 as contract
from . import recipient_runner_v1 as interface
from .production_contract_v1 import BridgeArtifact, WorkspaceIntegrityError
from .production_audit_v1 import (
    TraceAuditError, TraceAuditBlocked, _require, _equal, _keys, _number,
    _integer, _decode, _wire, _snapshot, _Events,
)
from .recipient_runner_v1 import SYSTEM_PROMPT, SOLUTION_TOOL, SELECTION_POLICY, VERSION as RUNNER_VERSION
from .transfer_design_v1 import encoded, load_blueprint, sha
from .workspace import WorkspaceRecord

VERSION = "p3_recipient_audit_v1"
EXPECTED_CLIENT = "anthropic.lib.bedrock._mantle.AnthropicBedrockMantle"
USAGE = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
COMPONENT_KEYS = {"status", "source_sha256", "declaration", "axioms", "errors", "stdout", "stderr"}


def _implementation():
    paths = (Path(__file__), Path(evidence.__file__), Path(contract.__file__), Path(interface.__file__))
    _require(all(p.is_file() and not p.is_symlink() for p in paths), "unsafe audit implementation")
    return {p.name: sha(p.read_bytes()) for p in paths}


def _context(repository, cell_id, data_kind, execution_plan_sha256, candidate):
    _require(isinstance(data_kind, str) and data_kind in {"synthetic", "experimental"},
             "explicit evidence kind required")
    _require(execution_plan_sha256 is None or (isinstance(execution_plan_sha256, str)
             and re.fullmatch(r"[0-9a-f]{64}", execution_plan_sha256)), "invalid execution-plan hash")
    _require(data_kind != "experimental" or execution_plan_sha256 is not None,
             "experimental evidence needs a separate frozen execution-plan reference")
    try:
        blueprint = load_blueprint(repository)
        # This is the published formal contract's input authority, not the runner.
        spec = contract._spec(repository, cell_id, candidate)
    except (OSError, ValueError) as exc:
        raise TraceAuditError("trusted recipient inputs: " + str(exc)) from exc
    digest = sha(encoded(blueprint))
    _require(execution_plan_sha256 != digest, "blueprint is not the final execution plan")
    cell = spec["cell"]
    bound = None if candidate is None else {k: v for k, v in asdict(candidate).items() if k != "source"}
    context = {"schema_version": 1, "evidence_kind": "recipient_raw_trace",
        "design_id": blueprint["design_id"], "blueprint_sha256": digest,
        "execution_plan_sha256": execution_plan_sha256, "data_kind": data_kind,
        "cell_id": cell_id, "world_id": cell["world_id"], "arm": cell["arm"],
        "holdout": cell["holdout"], "parent_proposer_id": cell["parent_proposer_id"],
        "bridge_sha256": sha(spec["bridge"]) if spec["bridge"] is not None else None,
        "candidate_artifact": bound}
    return blueprint, spec, context


def _manifest(context, files, directories):
    return {**context, "files_sha256": {rel: sha(data) for rel, data in sorted(files.items())},
            "directories": sorted(directories)}


def build_evidence_manifest(repository: Path, artifacts: Path, *, cell_id: str,
                            data_kind: str, candidate: BridgeArtifact | None = None,
                            execution_plan_sha256: str | None = None) -> dict:
    """Inventory only. The trusted launcher must retain the seal outside raw files."""
    *_, context = _context(Path(repository), cell_id, data_kind, execution_plan_sha256, candidate)
    return _manifest(context, *_snapshot(Path(artifacts)))


def _workspace(destination, spec):
    """Reconstruct exact canonical source inputs, never caches or a live session.

    No admission is inferred from this staging. verify_recipient subsequently
    recompiles the supplied bridge Base-only, even for a no-submission trace.
    """
    destination.mkdir()
    for rel, data in spec["inputs"].items():
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    record = WorkspaceRecord(destination, spec["cell"]["world_id"], "evaluator", spec["condition"],
                             {rel: sha(data) for rel, data in spec["inputs"].items()}, ("Solution.lean",))
    contract._snapshot(record, spec)
    return record


def _request(messages, config):
    return {"model": config["model"], "system": SYSTEM_PROMPT, "messages": deepcopy(messages),
            "tools": [deepcopy(SOLUTION_TOOL)], "output_config": {"effort": config["effort"]},
            "thinking": {"type": "adaptive"},
            "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}}


def _feedback(report):
    solution = report["solution"]
    text = "\n".join(solution["errors"])
    return {"status": solution["status"], "valid": solution["status"] == "valid",
            "errors": [text[:10000]] if text else [], "feedback_truncated": len(text) > 10000}


def _component(raw, digest, names, *, missing=False, bridge=False):
    _keys(raw, COMPONENT_KEYS, "component")
    _equal(raw["source_sha256"], digest, "submitted bytes")
    for key in ("axioms", "errors"):
        _require(isinstance(raw[key], list) and all(isinstance(item, str) for item in raw[key]), key + " type")
    _require(all(isinstance(raw[key], str) for key in ("stdout", "stderr")), "diagnostic type")
    _require(raw["declaration"] is None or isinstance(raw["declaration"], str), "declaration type")
    status = raw["status"]
    allowed = {"valid"} if bridge else {"missing"} if missing else {"valid", "rejected"}
    _require(isinstance(status, str) and status in allowed, "component status")
    if status == "valid":
        _require(raw["declaration"] in names and not raw["errors"], "invalid success receipt")
        _require(not set(raw["axioms"]) - {"propext", "Quot.sound", "Classical.choice"}, "forbidden axioms")
    else:
        _require(raw["declaration"] is None and not raw["axioms"] and bool(raw["errors"]),
                 "contradictory rejection/absence receipt")


def _report(raw, source, spec, candidate):
    _keys(raw, {"solution", "bridge", "input_hashes", "cell_id", "world_id", "namespace",
                "statement", "bridge_sha256"}, "verification report")
    cell, namespace = spec["cell"], spec["namespace"]
    expected = {"cell_id": cell["cell_id"], "world_id": cell["world_id"],
                "namespace": namespace, "statement": spec["statement"],
                "bridge_sha256": sha(spec["bridge"]) if spec["bridge"] is not None else None}
    for key, value in expected.items():
        _equal(raw[key], value, "checker " + key)
    hashes = raw["input_hashes"]
    _require(isinstance(hashes, list) and all(isinstance(row, list) and len(row) == 2
             and all(isinstance(v, str) for v in row) for row in hashes), "input hash schema")
    _require(len(hashes) == len(spec["inputs"]) == len(dict(hashes)), "input hash inventory")
    _equal(dict(hashes), {rel: sha(data) for rel, data in spec["inputs"].items()}, "checker input hashes")
    _component(raw["solution"], sha(source) if source is not None else None,
               ("evaluation_solution", namespace + ".evaluation_solution"), missing=source is None)
    if spec["bridge"] is None:
        _require(raw["bridge"] is None, "baseline invented a bridge")
    else:
        short = spec["bridge_name"]
        _component(raw["bridge"], sha(spec["bridge"]), (short, namespace + "." + short), bridge=True)
        if candidate is not None:
            _equal(raw["bridge"]["declaration"], candidate.declaration, "bound candidate declaration")


def _formal_fields(raw):
    result = deepcopy(raw)
    # Pair order carries no semantics; duplicate keys were rejected above.
    result["input_hashes"] = sorted(result["input_hashes"])
    for key in ("solution", "bridge"):
        if result[key] is not None:
            result[key] = {k: v for k, v in result[key].items() if k not in {"stdout", "stderr"}}
    return result


def _fresh_check(repository, spec, candidate, source, checker):
    with tempfile.TemporaryDirectory(prefix="p3-recipient-reaudit-") as temp:
        record = _workspace(Path(temp) / "workspace", spec)
        if source is not None:
            (record.path / "Solution.lean").write_bytes(source)
        try:
            checked = (checker or contract.verify_recipient)(record, repository=repository,
                cell_id=spec["cell"]["cell_id"], candidate=candidate, timeout_s=120.0)
        except Exception as exc:
            # Preserve original exception/partial compiler receipts as the cause.
            raise TraceAuditBlocked("fresh verification infrastructure: " + str(exc)) from exc
        _require(isinstance(checked, contract.RecipientReport), "fresh checker report type")
        raw = _decode(_wire(asdict(checked)).encode())
        _report(raw, source, spec, candidate)
        try:
            contract._snapshot(record, spec)
            output = record.path / "Solution.lean"
            after = output.read_bytes() if output.exists() else None
            _require(after == source, "fresh checker changed submitted bytes")
        except (WorkspaceIntegrityError, OSError) as exc:
            raise TraceAuditError("fresh workspace integrity: " + str(exc)) from exc
        return raw


def audit_recipient_trace(repository: Path, artifacts: Path, *, cell_id: str, data_kind: str,
                          candidate: BridgeArtifact | None = None,
                          execution_plan_sha256: str | None = None,
                          expected_evidence_sha256: str | None = None,
                          checker: Callable | None = None) -> dict:
    """Reconstruct the session and return a projection only after fresh checking.

    Experimental mode requires a separately retained seal/plan reference and
    real verification. Provenance, parent selection, content review, the phase
    barrier and external settlement remain requirements of the batch layer.
    """
    repository, artifacts = Path(repository), Path(artifacts)
    implementation = _implementation()
    blueprint, spec, context = _context(repository, cell_id, data_kind, execution_plan_sha256, candidate)
    _require(data_kind != "experimental" or checker is None, "experimental checker injection forbidden")
    _require(data_kind != "experimental" or expected_evidence_sha256 is not None,
             "experimental evidence needs an independently retained closure seal")
    files, directories = _snapshot(artifacts)
    manifest = _manifest(context, files, directories)
    digest = sha(encoded(manifest))
    if expected_evidence_sha256 is not None:
        _equal(digest, expected_evidence_sha256, "external evidence seal")
    _require({"input.json", "events.jsonl", "session.json"} <= set(files), "incomplete session evidence")
    initial, summary = _decode(files["input.json"]), _decode(files["session.json"])
    _require(isinstance(summary, dict), "session summary must be an object")
    _keys(initial, {"version", "config", "system", "tools", "messages", "selection_policy", "interface_hashes",
        "cell_id", "world_id", "condition", "holdout", "namespace", "statement", "bridge_sha256",
        "copied_hashes", "checker_injected", "client_class", "started_at"}, "input")
    _equal(initial["config"], blueprint["agent"], "exact development configuration")
    config, cell = initial["config"], spec["cell"]
    _require(type(initial["checker_injected"]) is bool and isinstance(initial["client_class"], str)
             and bool(initial["client_class"]), "checker/client provenance labels")
    if data_kind == "experimental":
        _require(initial["checker_injected"] is False and initial["client_class"] == EXPECTED_CLIENT,
                 "experimental trace reports a synthetic checker/client")
    hashes = {"system": sha(SYSTEM_PROMPT.encode()), "tool": sha(_wire(SOLUTION_TOOL).encode()),
              "selection_policy": sha(SELECTION_POLICY.encode())}
    expected_inputs = {"version": RUNNER_VERSION, "system": SYSTEM_PROMPT, "tools": [SOLUTION_TOOL],
        "selection_policy": SELECTION_POLICY, "interface_hashes": hashes, "cell_id": cell_id,
        "world_id": cell["world_id"], "condition": spec["condition"], "holdout": cell["holdout"],
        "namespace": spec["namespace"], "statement": spec["statement"], "bridge_sha256": context["bridge_sha256"],
        "copied_hashes": {rel: sha(data) for rel, data in spec["inputs"].items()}}
    for key, value in expected_inputs.items():
        _equal(initial[key], value, "input " + key)
    with tempfile.TemporaryDirectory(prefix="p3-recipient-audit-input-") as temp:
        fresh = _workspace(Path(temp) / "workspace", spec)
        messages = [{"role": "user", "content": contract.render_recipient(fresh, repository=repository,
                     cell_id=cell_id, candidate=candidate)}]
    _equal(initial["messages"], messages, "initial positive-allowlist payload")
    stream = _Events(files["events.jsonl"], initial["started_at"])
    _require(len(stream.rows) >= 2, "incomplete event log")
    _equal(stream.rows[-1].get("result"), summary, "terminal summary/event")
    _require(stream.rows[-1]["event"] == "session_finished", "missing final event")
    if any(row["event"] == "infrastructure_failure" for row in stream.rows) or summary.get("infrastructure_failure"):
        raise TraceAuditBlocked("technical session: retain raw evidence and reconcile reservations; no scoring/retry")
    _equal(stream.take("session_started", {"selection_policy"})["selection_policy"], SELECTION_POLICY, "selection policy")
    expected_files = {"input.json", "events.jsonl", "session.json"}
    totals = dict.fromkeys(USAGE, 0)
    input_reserved = output_reserved = requests = revisions = 0
    reports, rechecked, models, used_ids = [], [], [], set()
    last_source = None
    status = error = None

    for turn in range(1, config["max_turns"] + 1):
        if stream.kind() == "session_finished":
            status = "session_limit"
            break
        counted_start = stream.take("count_started", {"turn", "body", "timeout_seconds"})
        _equal(counted_start["turn"], turn, "count turn")
        _equal(counted_start["body"], _request(messages, config), "native-count request history")
        stream.timeout(counted_start, 30.0)
        counted_end = stream.take("count_finished", {"turn", "input_tokens", "duration_seconds"})
        _equal(counted_end["turn"], turn, "count result turn")
        stream.duration(counted_start, counted_end)
        counted = _integer(counted_end["input_tokens"], "native input count")
        _require(counted <= 2**53 - 1, "native count outside exact integer range")
        in_bound = math.ceil(counted * 1.10) + 1024
        out_bound = min(16384, 20000 - output_reserved)
        insufficient = input_reserved + in_bound > 200000 or out_bound < 256
        if stream.kind() == "session_finished":
            claimed = summary.get("status")
            _require(claimed == "session_limit" or insufficient, "missing affordable inference request")
            status = "session_limit" if claimed == "session_limit" else "token_budget"
            break
        _require(not insufficient, "inference exceeds token reservation budget")
        input_reserved += in_bound
        output_reserved += out_bound
        request = stream.take("request", {"turn", "body", "timeout_seconds", "counted_input", "reservation"})
        _equal(request["turn"], turn, "inference turn")
        _equal(request["body"], {**_request(messages, config), "max_tokens": out_bound}, "inference request history")
        _equal(request["counted_input"], counted, "count/inference binding")
        _equal(request["reservation"], [in_bound, out_bound], "per-request reservation")
        stream.timeout(request, 300.0)
        requests += 1
        response = stream.take("response", {"turn", "body", "duration_seconds"})
        _equal(response["turn"], turn, "response turn")
        stream.duration(request, response)
        payload = response["body"]
        _require(isinstance(payload, dict) and isinstance(payload.get("usage"), dict), "missing raw usage")
        usage = payload["usage"]
        _require({"input_tokens", "output_tokens"} <= set(usage), "required usage absent")
        for name in USAGE:
            _integer(usage.get(name, 0), "usage " + name)
        charged = usage["input_tokens"] + 2 * usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
        _require(charged <= in_bound and usage["output_tokens"] <= out_bound, "usage overrun not classified technical")
        for name in USAGE:
            totals[name] += usage.get(name, 0)
        output_reserved -= out_bound - usage["output_tokens"]
        settled = stream.take("request_settled", {"turn", "tokens", "input_reserved", "output_reserved"})
        _equal({k: settled[k] for k in ("turn", "tokens", "input_reserved", "output_reserved")},
               {"turn": turn, "tokens": usage, "input_reserved": input_reserved, "output_reserved": output_reserved}, "settlement")
        model = payload.get("model")
        _require(isinstance(model, str) and model.removeprefix("anthropic.") == config["model"].removeprefix("anthropic."),
                 "response model drift")
        models.append(model)
        content, reason = payload.get("content"), payload.get("stop_reason")
        _require(isinstance(content, list) and all(isinstance(b, dict) for b in content) and isinstance(reason, str)
                 and reason in {"tool_use", "end_turn", "max_tokens", "refusal"}, "response shape drift")
        _require(all(isinstance(b.get("type"), str) and b["type"] in
                     {"text", "thinking", "redacted_thinking", "tool_use"} for b in content), "unknown block type")
        messages.append({"role": "assistant", "content": deepcopy(content)})
        if reason == "max_tokens":
            _equal(stream.take("truncated_response_ignored", {"turn"})["turn"], turn, "truncation turn")
            status = "output_limit"
            break
        calls = [b for b in content if b.get("type") == "tool_use"]
        if reason in {"end_turn", "refusal"} and not calls:
            status = "model_stopped"
            break
        if reason != "tool_use" or len(calls) != 1:
            status, error = "invalid_output", "expected exactly one complete solution submission"
            break
        call, arguments = calls[0], calls[0].get("input")
        if (call.get("name") != "check_solution" or not isinstance(call.get("id"), str) or not call["id"]
                or call["id"] in used_ids or not isinstance(arguments, dict)
                or set(arguments) != {"solution_source"} or not isinstance(arguments["solution_source"], str)):
            status, error = "invalid_output", "check_solution arguments or identity violate the contract"
            break
        used_ids.add(call["id"])
        try:
            source = arguments["solution_source"].encode("utf-8")
        except UnicodeEncodeError:
            status, error = "invalid_output", "submitted source is not valid UTF-8"
            break
        revisions += 1
        last_source = source
        prefix = f"revisions/{revisions:04d}/"
        expected_files.update({prefix + rel for rel in ("Solution.lean", "submission.json", "verification.json")})
        _require(files.get(prefix + "Solution.lean") == source, "revision source differs from raw response")
        _require(prefix + "submission.json" in files and prefix + "verification.json" in files, "missing revision receipts")
        submission = {"turn": turn, "tool_use_id": call["id"], "revision": revisions, "source_sha256": sha(source)}
        _equal(_decode(files[prefix + "submission.json"]), submission, "submission receipt")
        recorded = stream.take("submission", {"turn", "revision", "source_sha256"})
        _equal({k: recorded[k] for k in ("turn", "revision", "source_sha256")},
               {k: submission[k] for k in ("turn", "revision", "source_sha256")}, "submission event")
        checking = stream.take("verification_started", {"turn", "revision", "timeout_seconds"})
        _equal([checking["turn"], checking["revision"]], [turn, revisions], "verification identity")
        stream.timeout(checking, 120.0)
        verified = stream.take("verification", {"turn", "revision", "report", "duration_seconds"})
        _equal([verified["turn"], verified["revision"]], [turn, revisions], "verification result identity")
        stream.duration(checking, verified)
        raw = _decode(files[prefix + "verification.json"])
        _equal(verified["report"], raw, "verification receipt/event")
        _report(raw, source, spec, candidate)
        fresh = _fresh_check(repository, spec, candidate, source, checker)
        _equal(_formal_fields(fresh), _formal_fields(raw), "fresh Lean verification")
        reports.append(raw)
        rechecked.append({"revision": revisions, "report": fresh})
        feedback = _feedback(raw)
        fed = stream.take("feedback", {"turn", "revision", "body"})
        _equal([fed["turn"], fed["revision"], fed["body"]], [turn, revisions, feedback], "bounded checker feedback")
        if raw["solution"]["status"] == "valid":
            status = "proof_verified"
            break
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call["id"],
                         "content": _wire(feedback)}]})
    else:
        status = "request_limit"

    finished = stream.take("session_finished", {"result"})
    _require(stream.index == len(stream.rows), "events after session finished")
    elapsed = _number(summary.get("elapsed_seconds"), "session elapsed")
    _require(stream.rows[-2]["elapsed_seconds"] <= elapsed <= finished["elapsed_seconds"], "terminal time outside event interval")
    if status == "session_limit":
        _require(elapsed >= 600.0, "premature session deadline")
    elif status == "token_budget":
        _require(counted_end["elapsed_seconds"] < 600.0, "deadline must precede token budget")
    last, selected = reports[-1] if reports else None, None
    if status != "invalid_output" and last is not None:
        selected = {"revision": revisions, "relative_path": "selected_solution/Solution.lean",
                    "sha256": sha(last_source), "status": last["solution"]["status"],
                    "declaration": last["solution"]["declaration"]}
        expected_files.update({"selected_solution/Solution.lean", "selected_solution/artifact.json"})
        _require(files.get("selected_solution/Solution.lean") == last_source, "selection is not the last complete solution")
        _require("selected_solution/artifact.json" in files, "missing selected artifact receipt")
        _equal(_decode(files["selected_solution/artifact.json"]), selected, "selected artifact")
    outcome = "verified" if status == "proof_verified" else "invalid_protocol_output" if status == "invalid_output" else "not_solved"
    cost = (5.5 * (totals["input_tokens"] + 2 * totals["cache_creation_input_tokens"] + .1 * totals["cache_read_input_tokens"])
            + 27.5 * totals["output_tokens"]) / 1_000_000
    expected_summary = {"version": RUNNER_VERSION, "status": status, "recipient_outcome": outcome,
        "selection_policy": SELECTION_POLICY, "requests": requests, "revisions": revisions,
        "last_verification": last, "selected_solution": selected, "target_solved": status == "proof_verified",
        "bridge_sha256": context["bridge_sha256"], "infrastructure_failure": False, "halt_admissions": False,
        "error": error, "tokens": totals, "accounting_complete": True, "external_reservation_must_remain_open": False,
        "uncertain_request": False, "unresolved_charge_upper_estimate_usd": 0.0,
        "cost_usd_at_configured_rates": cost, "session_cost_ceiling_usd": 1.65,
        "input_reserved": input_reserved, "output_reserved": output_reserved,
        "reported_models": models, "elapsed_seconds": elapsed,
        "cost_basis": "configured regional rates; cache writes conservatively at 1h rate; not an AWS invoice"}
    _equal(summary, expected_summary, "independently reconstructed session")
    _equal(sorted(files), sorted(expected_files), "exact evidence file inventory")
    expected_dirs = {p.as_posix() for rel in expected_files for p in Path(rel).parents if p != Path(".")}
    _equal(sorted(directories), sorted(expected_dirs), "exact evidence directory inventory")
    # Even without a submitted proof, ensure the supplied bridge can be checked.
    no_submission_check = None if reports else _fresh_check(repository, spec, candidate, None, checker)
    _equal(_manifest(context, *_snapshot(artifacts)), manifest, "evidence changed during audit")
    _require(_context(repository, cell_id, data_kind, execution_plan_sha256, candidate) ==
             (blueprint, spec, context), "frozen inputs changed during audit")
    _equal(_implementation(), implementation, "audit implementation changed during audit")
    observation = {"outcome": outcome, "target_solved": status == "proof_verified", "bridge_sha256": context["bridge_sha256"]}
    return {"audit_version": VERSION, "status": "passed", "data_kind": data_kind,
        "evidence_manifest": manifest, "evidence_sha256": digest, "implementation_sha256": implementation,
        "verification": "synthetic_injected_checker" if checker else "fresh_sandboxed_Lean_per_revision",
        "rechecked_revisions": rechecked, "no_submission_input_check": no_submission_check,
        "reconstructed_session": expected_summary,
        "cell_projection": {"cell_id": cell_id, "state": "completed", "trace_audit": "passed",
                            "accounting": "complete", "evidence_sha256": digest, "observation": observation},
        "accounting_scope": "logged request usage only; external daily/batch reconciliation remains required",
        "provenance_scope": "local consistency and external seal reference; not provider-signed authenticity",
        "parent_and_content_validated": False, "phase_barrier_verified": False, "batch_audit_passed": False,
        "inference_admitted": False, "recipient_admitted": False,
        "main_sample_admitted": False, "mechanistic_stage_admitted": False}
