"""Independent, fail-closed reconstruction of sealed proposer traces.

No provider calls, replay through the session runner, recipient admission, budget
settlement, or content approval. The frozen Lean contract is the proof authority;
the state machine, accounting, request history and selection are checked here
without the runner's execution/feedback/TokenBudget helpers. Synthetic tests may
inject a checker, but experimental audits must use fresh sandboxed Lean checks.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable

from .production_contract_v1 import (
    BASE_FILES, ProductionReport, VerificationInfrastructureError,
    materialize_production_proposer, render_production_proposer, verify_production,
)
from .production_runner_v1 import (
    SYSTEM_PROMPT, SUBMISSION_TOOL, SELECTION_POLICY, VERSION as RUNNER_VERSION,
)
from .transfer_design_v1 import BLUEPRINT_PATH, encoded, load_blueprint, sha

VERSION = "p3_production_audit_v1"
EXPECTED_CLIENT = "anthropic.lib.bedrock._mantle.AnthropicBedrockMantle"
USAGE = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
EVENT_BASE = {"seq", "event", "at", "elapsed_seconds"}
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 256
EPSILON_SECONDS = 0.00001


class TraceAuditError(ValueError):
    """Contradictory/unsafe evidence: halt admissions, never score as U=0."""


class TraceAuditBlocked(RuntimeError):
    """Technical trace or failed fresh checking: preserve evidence and reconcile.

    No cost, release of reservation, mathematical outcome or retry is authorized
    by this exception. The batch auditor must retain a technical/pending cell.
    """


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TraceAuditError(message)


def _wire(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)


def _equal(actual, expected, label: str) -> None:
    # JSON comparison distinguishes bool/int, and forbids extra fields.
    _require(_wire(actual) == _wire(expected), label + " mismatch")


def _keys(value, expected, label: str) -> None:
    _require(isinstance(value, dict) and set(value) == set(expected), label + " schema")


def _number(value, label: str, *, positive: bool = False) -> float:
    _require(type(value) in (int, float) and math.isfinite(value)
             and (value > 0 if positive else value >= 0), "invalid " + label)
    return value


def _integer(value, label: str) -> int:
    _require(type(value) is int and value >= 0, "invalid " + label)
    return value


def _timestamp(value) -> datetime:
    _require(isinstance(value, str), "timestamp must be a UTC string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise TraceAuditError("invalid timestamp") from exc
    _require(parsed.utcoffset() == timedelta(0), "timestamp must explicitly be UTC")
    return parsed


def _decode(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise TraceAuditError("nonfinite JSON constant: " + value)

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        _wire(value)  # Also rejects overflow floats such as 1e999.
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise TraceAuditError("invalid evidence JSON: " + str(exc)) from exc


def _snapshot(root: Path) -> tuple[dict[str, bytes], set[str]]:
    """Read regular unlinked files only, bound memory, and record empty dirs too."""
    _require(root.is_dir() and not root.is_symlink(), "unsafe or missing evidence directory")
    files, directories = {}, set()
    total = entries = 0

    def walk(directory_fd, prefix=""):
        nonlocal total, entries
        # Relative descriptor opens prevent traversal through a directory that
        # is replaced with a symlink between inspection and reading.
        for name in sorted(os.listdir(directory_fd)):
            entries += 1
            _require(entries <= MAX_ENTRIES, "evidence entry limit")
            rel = prefix + name
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            _require(not stat.S_ISLNK(info.st_mode), "evidence symlink: " + rel)
            if stat.S_ISDIR(info.st_mode):
                directories.add(rel)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                try:
                    opened = os.fstat(child)
                    _require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino), "evidence directory replaced")
                    walk(child, rel + "/")
                finally:
                    os.close(child)
                continue
            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "nonregular/linked evidence: " + rel)
            _require(info.st_size <= MAX_FILE_BYTES, "evidence file size limit")
            with os.fdopen(os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd), "rb") as handle:
                opened = os.fstat(handle.fileno())
                _require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino), "evidence replaced while opening")
                data = handle.read(MAX_FILE_BYTES + 1)
                after = os.fstat(handle.fileno())
            stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
            _require(len(data) == info.st_size and all(getattr(after, k) == getattr(opened, k) for k in stable),
                     "evidence changed while reading")
            total += len(data)
            _require(total <= MAX_TOTAL_BYTES, "evidence total size limit")
            files[rel] = data
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            walk(root_fd)
        finally:
            os.close(root_fd)
    except OSError as exc:
        raise TraceAuditError("cannot safely snapshot evidence: " + str(exc)) from exc
    return files, directories


def _context(repository: Path, cell_id: str, data_kind: str, execution_plan_sha256):
    _require(data_kind in {"synthetic", "experimental"}, "explicit evidence kind required")
    _require(execution_plan_sha256 is None or (isinstance(execution_plan_sha256, str)
             and re.fullmatch(r"[0-9a-f]{64}", execution_plan_sha256) is not None), "invalid execution-plan hash")
    _require(data_kind != "experimental" or execution_plan_sha256 is not None,
             "experimental evidence needs a separate frozen execution-plan reference")
    blueprint = load_blueprint(repository)
    cells = [c for c in blueprint["cells"] if c["cell_id"] == cell_id and c["role"] == "proposer"]
    _require(len(cells) == 1, "not a development proposer cell")
    digest = sha((repository / BLUEPRINT_PATH).read_bytes())
    _require(execution_plan_sha256 != digest, "blueprint is not the final execution plan")
    cell = cells[0]
    world = next(w for w in blueprint["worlds"] if w["world_id"] == cell["world_id"])
    return blueprint, cell, world, {"schema_version": 1, "evidence_kind": "proposer_raw_trace",
        "design_id": blueprint["design_id"], "blueprint_sha256": digest,
        "execution_plan_sha256": execution_plan_sha256, "data_kind": data_kind,
        "cell_id": cell_id, "world_id": cell["world_id"], "arm": cell["arm"]}


def _manifest(context, files, directories):
    return {**context, "files_sha256": {rel: sha(data) for rel, data in sorted(files.items())},
            "directories": sorted(directories)}


def build_evidence_manifest(repository: Path, artifacts: Path, *, cell_id: str,
                            data_kind: str, execution_plan_sha256: str | None = None) -> dict:
    """Inventory only, not an audit. Save the seal OUTSIDE the raw directory.

    A future trusted launcher must seal experimental evidence on session closure.
    A manifest computed post hoc from altered files is not provenance/authenticity.
    """
    *_, context = _context(Path(repository), cell_id, data_kind, execution_plan_sha256)
    return _manifest(context, *_snapshot(Path(artifacts)))


class _Events:
    def __init__(self, data: bytes, started_at):
        _require(data.endswith(b"\n"), "event log is not durably terminated")
        self.rows = [_decode(line) for line in data.splitlines()]
        self.index = 0
        previous_time, previous_elapsed = _timestamp(started_at), 0.0
        for seq, row in enumerate(self.rows, 1):
            _require(isinstance(row, dict) and EVENT_BASE <= set(row), "event envelope schema")
            _require(type(row["seq"]) is int and row["seq"] == seq, "event sequence gap/reorder")
            at, elapsed = _timestamp(row["at"]), _number(row["elapsed_seconds"], "event elapsed")
            _require(at >= previous_time and elapsed >= previous_elapsed, "event clock reversal")
            previous_time, previous_elapsed = at, elapsed

    def kind(self):
        return self.rows[self.index]["event"] if self.index < len(self.rows) else None

    def take(self, kind: str, fields) -> dict:
        _require(self.kind() == kind, "expected event " + kind + ", got " + str(self.kind()))
        row = self.rows[self.index]
        _keys(row, EVENT_BASE | set(fields), kind + " event")
        self.index += 1
        return row

    def timeout(self, row, cap):
        current = row["elapsed_seconds"]
        previous = self.rows[self.index - 2]["elapsed_seconds"] if self.index >= 2 else 0
        timeout = _number(row["timeout_seconds"], "timeout", positive=True)
        # Runner samples remaining time before writing the event: bound it by
        # adjacent monotonic timestamps, not an invented exact sampling instant.
        lower, upper = max(0, min(cap, 600.0 - current)), min(cap, 600.0 - previous)
        _require(lower - EPSILON_SECONDS <= timeout <= upper + EPSILON_SECONDS, "timeout outside sampled bounds")

    def duration(self, start, end):
        duration = _number(end["duration_seconds"], "operation duration")
        _require(duration <= end["elapsed_seconds"] - start["elapsed_seconds"] + EPSILON_SECONDS,
                 "duration exceeds event interval")


def _request(messages, config):
    return {"model": config["model"], "system": SYSTEM_PROMPT, "messages": deepcopy(messages),
            "tools": [deepcopy(SUBMISSION_TOOL)], "output_config": {"effort": config["effort"]},
            "thinking": {"type": "adaptive"}, "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}}


def _feedback(report):
    result = {}
    for name in ("bridge", "visible"):
        component = report[name]
        joined = "\n".join(component["errors"])
        result[name] = {"status": component["status"], "valid": component["status"] == "valid",
                        "errors": [joined[:10000]] if joined else [], "feedback_truncated": len(joined) > 10000}
    return result


def _report(raw, sources, base_hashes, namespace):
    _keys(raw, {"bridge", "visible", "base_hashes", "namespace"}, "verification report")
    _equal(raw["namespace"], namespace, "checker namespace")
    _equal(raw["base_hashes"], base_hashes, "checker base hashes")
    for label, filename in (("bridge", "Bridge.lean"), ("visible", "Solution.lean")):
        component = raw[label]
        _keys(component, {"status", "source_sha256", "declaration", "axioms", "errors", "stdout", "stderr"}, "component")
        source = sources[filename]
        _equal(component["source_sha256"], sha(source) if source is not None else None, "submitted bytes")
        _require(isinstance(component["status"], str) and component["status"] in
                 {"valid", "rejected", "missing", "blocked_by_bridge"}, "component status")
        _require((component["status"] == "missing") == (source is None), "component presence mismatch")
        _require(all(isinstance(component[k], str) for k in ("stdout", "stderr")), "compiler diagnostics type")
        _require(component["declaration"] is None or isinstance(component["declaration"], str), "declaration type")
        for key in ("axioms", "errors"):
            _require(isinstance(component[key], list) and all(isinstance(s, str) for s in component[key]), key + " type")
        if component["status"] == "valid":
            name = "candidate_bridge" if label == "bridge" else "candidate_solution"
            _require(component["declaration"] in (name, namespace + "." + name), "wrong candidate name")
            _require(not set(component["axioms"]) - {"propext", "Quot.sound", "Classical.choice"}, "forbidden axioms")
            _require(not component["errors"], "accepted component contains errors")
    _require(raw["bridge"]["status"] != "blocked_by_bridge", "bridge cannot depend on itself")
    if raw["bridge"]["status"] == "valid":
        _require(raw["visible"]["status"] != "blocked_by_bridge", "spurious dependency block")
    else:
        _require(raw["visible"]["status"] in {"missing", "blocked_by_bridge", "rejected"}, "visible without bridge")


def _formal_fields(report):
    # Errors feed the next request, so they must match too. We deliberately do
    # not normalize arbitrary diagnostic text. Nondeterministic errors block a
    # trace for review; stdout/stderr (build timings, temp paths) are preserved
    # in both reports but are not used as a semantic equality criterion.
    return {key: ({k: v for k, v in value.items() if k not in {"stdout", "stderr"}}
                  if key in {"bridge", "visible"} else value) for key, value in report.items()}


def audit_proposer_trace(repository: Path, artifacts: Path, *, cell_id: str, data_kind: str,
                         execution_plan_sha256: str | None = None,
                         expected_evidence_sha256: str | None = None,
                         checker: Callable | None = None) -> dict:
    """Return a session projection only after exact reconstruction + fresh Lean.

    Experimental sealing and its execution-plan hash must come from the trusted
    future launcher; these references alone do not validate that plan or prove
    provider origin. Synthetic injection is never an experimental certificate.
    Any exception is fail-closed: no observation/zero, budget release or rerun.
    """
    repository, artifacts = Path(repository), Path(artifacts)
    auditor_source = Path(__file__).read_bytes()
    blueprint, cell, world, context = _context(repository, cell_id, data_kind, execution_plan_sha256)
    _require(data_kind != "experimental" or checker is None, "experimental checker injection forbidden")
    _require(data_kind != "experimental" or expected_evidence_sha256 is not None,
             "experimental evidence needs an independently retained closure seal")
    files, directories = _snapshot(artifacts)
    manifest = _manifest(context, files, directories)
    digest = sha(encoded(manifest))
    if expected_evidence_sha256 is not None:
        _equal(digest, expected_evidence_sha256, "external evidence seal")
    _require({"input.json", "events.jsonl", "session.json"} <= set(files), "incomplete session evidence")
    source, summary = _decode(files["input.json"]), _decode(files["session.json"])
    _require(isinstance(summary, dict), "session summary must be an object")
    _keys(source, {"version", "config", "system", "tools", "messages", "selection_policy", "interface_hashes",
                   "world_id", "arm", "namespace", "copied_hashes", "checker_injected", "client_class", "started_at"}, "input")
    _equal(source["config"], blueprint["agent"], "exact development configuration")
    config = source["config"]
    _require(type(source["checker_injected"]) is bool and isinstance(source["client_class"], str)
             and bool(source["client_class"]), "checker/client provenance labels")
    if data_kind == "experimental":
        _require(source["checker_injected"] is False and source["client_class"] == EXPECTED_CLIENT,
                 "experimental trace reports a synthetic checker/client")
    interface = {"system": sha(SYSTEM_PROMPT.encode()), "tool": sha(_wire(SUBMISSION_TOOL).encode()),
                 "selection_policy": sha(SELECTION_POLICY.encode())}
    for name, expected in {"version": RUNNER_VERSION, "system": SYSTEM_PROMPT, "tools": [SUBMISSION_TOOL],
            "selection_policy": SELECTION_POLICY, "interface_hashes": interface, "world_id": cell["world_id"],
            "arm": cell["arm"], "namespace": world["namespace"]}.items():
        _equal(source[name], expected, "input " + name)
    # Host validates the world/manifest, but the model payload contains only the
    # positive allowlist. Never trust input.json to define its own visible data.
    with tempfile.TemporaryDirectory(prefix="p3-proposer-audit-input-") as temp:
        record = materialize_production_proposer(repository / cell["world"], cell["arm"], Path(temp) / "workspace")
        messages = [{"role": "user", "content": render_production_proposer(record)}]
        _equal(source["copied_hashes"], record.copied_hashes, "immutable input hashes")
        _equal(source["messages"], messages, "initial positive-allowlist payload")
        base_hashes = [[rel, record.copied_hashes[rel]] for rel in BASE_FILES]
    stream = _Events(files["events.jsonl"], source["started_at"])
    _require(bool(stream.rows), "empty trace")
    _equal(stream.rows[-1].get("result"), summary, "terminal summary/event")
    _require(stream.rows[-1]["event"] == "session_finished", "missing final event")
    if any(row["event"] == "infrastructure_failure" for row in stream.rows) or summary.get("infrastructure_failure"):
        # Deliberately no passed projection or inferred settled cost for technical
        # traces, including partial compiler reports. Preserve the raw manifest;
        # reconciliation needs the trusted launcher/provider records separately.
        raise TraceAuditBlocked("technical session: retain raw evidence and reconcile all reservations; no scoring/retry")

    first = stream.take("session_started", {"selection_policy"})
    _equal(first["selection_policy"], SELECTION_POLICY, "session selection policy")
    expected_files = {"input.json", "events.jsonl", "session.json"}
    totals = dict.fromkeys(USAGE, 0)
    input_reserved = output_reserved = requests = revisions = 0
    reports, rechecked, models, used_ids = [], [], [], set()
    last_sources = None
    status, error = None, None

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
            # The deadline has priority over reserve() after counting. The
            # unlogged sampling instant can only be bounded by the event times.
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
        charged_input_bound = usage["input_tokens"] + 2 * usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
        _require(charged_input_bound <= in_bound and usage["output_tokens"] <= out_bound, "usage overrun not classified technical")
        for name in USAGE:
            totals[name] += usage.get(name, 0)
        output_reserved -= out_bound - usage["output_tokens"]
        settled = stream.take("request_settled", {"turn", "tokens", "input_reserved", "output_reserved"})
        _equal({k: settled[k] for k in ("turn", "tokens", "input_reserved", "output_reserved")},
               {"turn": turn, "tokens": usage, "input_reserved": input_reserved, "output_reserved": output_reserved}, "settlement")
        model = payload.get("model")
        _require(isinstance(model, str) and model.removeprefix("anthropic.") == config["model"].removeprefix("anthropic."), "response model drift")
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
        calls = [block for block in content if block.get("type") == "tool_use"]
        if reason in {"end_turn", "refusal"} and not calls:
            status = "model_stopped"
            break
        if reason != "tool_use" or len(calls) != 1:
            status, error = "invalid_output", "expected exactly one complete tool submission"
            break
        call, arguments = calls[0], calls[0].get("input")
        if (call.get("name") != "check_submission" or not isinstance(call.get("id"), str) or not call["id"]
                or call["id"] in used_ids or not isinstance(arguments, dict)
                or set(arguments) != {"bridge_source", "solution_source"}
                or not isinstance(arguments["bridge_source"], str)
                or not (arguments["solution_source"] is None or isinstance(arguments["solution_source"], str))):
            status, error = "invalid_output", "check_submission arguments or identity violate the contract"
            break
        used_ids.add(call["id"])
        try:
            sources = {"Bridge.lean": arguments["bridge_source"].encode("utf-8"),
                       "Solution.lean": None if arguments["solution_source"] is None else arguments["solution_source"].encode("utf-8")}
        except UnicodeEncodeError:
            status, error = "invalid_output", "submitted source is not valid UTF-8"
            break
        revisions += 1
        last_sources = sources
        prefix = f"revisions/{revisions:04d}/"
        hashes = {rel: None if data is None else sha(data) for rel, data in sources.items()}
        for rel, data in sources.items():
            if data is not None:
                expected_files.add(prefix + rel)
                _require(files.get(prefix + rel) == data, "revision source differs from raw response")
        submission = {"turn": turn, "tool_use_id": call["id"], "revision": revisions, "source_hashes": hashes}
        expected_files.update({prefix + "submission.json", prefix + "verification.json"})
        _require(prefix + "submission.json" in files and prefix + "verification.json" in files, "missing revision receipts")
        _equal(_decode(files[prefix + "submission.json"]), submission, "submission receipt")
        recorded = stream.take("submission", {"turn", "revision", "source_hashes"})
        _equal({k: recorded[k] for k in ("turn", "revision", "source_hashes")},
               {k: submission[k] for k in ("turn", "revision", "source_hashes")}, "submission event")
        checking = stream.take("verification_started", {"turn", "revision", "timeout_seconds"})
        _equal([checking["turn"], checking["revision"]], [turn, revisions], "verification identity")
        stream.timeout(checking, 120.0)
        verified = stream.take("verification", {"turn", "revision", "report", "duration_seconds"})
        _equal([verified["turn"], verified["revision"]], [turn, revisions], "verification result identity")
        stream.duration(checking, verified)
        raw = _decode(files[prefix + "verification.json"])
        _equal(verified["report"], raw, "verification receipt/event")
        _report(raw, sources, base_hashes, world["namespace"])
        reports.append(raw)
        # Each revision gets a fresh positive-allowlist workspace, never the
        # producer's live directory, a previous revision or inherited .olean.
        try:
            with tempfile.TemporaryDirectory(prefix="p3-proposer-recheck-") as temp:
                fresh = materialize_production_proposer(repository / cell["world"], cell["arm"], Path(temp) / "workspace")
                for rel, data in sources.items():
                    if data is not None:
                        (fresh.path / rel).write_bytes(data)
                checked = (checker or verify_production)(fresh, namespace=world["namespace"], timeout_s=120.0)
                _require(isinstance(checked, ProductionReport), "fresh checker report type")
                checked_json = _decode(_wire(asdict(checked)).encode())
                _report(checked_json, sources, base_hashes, world["namespace"])
        except (VerificationInfrastructureError, OSError) as exc:
            raise TraceAuditBlocked("fresh verification infrastructure: " + str(exc)) from exc
        _equal(_formal_fields(checked_json), _formal_fields(raw), "fresh Lean verification")
        rechecked.append({"revision": revisions, "report": checked_json})
        feedback = _feedback(raw)
        fed = stream.take("feedback", {"turn", "revision", "body"})
        _equal([fed["turn"], fed["revision"], fed["body"]], [turn, revisions, feedback], "bounded checker feedback")
        if raw["bridge"]["status"] == raw["visible"]["status"] == "valid":
            status = "both_verified"
            break
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call["id"], "content": _wire(feedback)}]})
    else:
        status = "request_limit"

    finished = stream.take("session_finished", {"result"})
    _require(stream.index == len(stream.rows), "events after session finished")
    elapsed = _number(summary.get("elapsed_seconds"), "session elapsed")
    previous = stream.rows[-2]["elapsed_seconds"]
    _require(previous <= elapsed <= finished["elapsed_seconds"], "terminal time outside event interval")
    if status == "session_limit":
        _require(elapsed >= 600.0, "premature session deadline")
    elif status == "token_budget":
        _require(counted_end["elapsed_seconds"] < 600.0, "deadline must precede token budget")
    last = reports[-1] if reports else None
    selected = None
    if status != "invalid_output" and last is not None and last["bridge"]["status"] == "valid":
        selected = {"sha256": sha(last_sources["Bridge.lean"]), "world_id": cell["world_id"],
                    "namespace": world["namespace"], "declaration": last["bridge"]["declaration"],
                    "base_hashes": base_hashes, "revision": revisions, "relative_path": "selected_bridge/Bridge.lean"}
        expected_files.update({"selected_bridge/Bridge.lean", "selected_bridge/artifact.json"})
        _require(files.get("selected_bridge/Bridge.lean") == last_sources["Bridge.lean"], "selection is not the last complete bridge")
        _require("selected_bridge/artifact.json" in files, "missing selected artifact receipt")
        _equal(_decode(files["selected_bridge/artifact.json"]), selected, "selected artifact")
    outcome = ("invalid_protocol_output" if status == "invalid_output" else "no_complete_submission" if last is None
               else "valid_bridge" if last["bridge"]["status"] == "valid" else "invalid_bridge")
    cost = (5.5 * (totals["input_tokens"] + 2 * totals["cache_creation_input_tokens"] + .1 * totals["cache_read_input_tokens"])
            + 27.5 * totals["output_tokens"]) / 1_000_000
    expected_summary = {"version": RUNNER_VERSION, "status": status, "production_outcome": outcome,
        "selection_policy": SELECTION_POLICY, "requests": requests, "revisions": revisions,
        "last_verification": last, "selected_bridge": selected, "bridge_eligible_pending_audit": selected is not None,
        "visible_solved": status == "both_verified", "infrastructure_failure": False, "halt_admissions": False,
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
    _equal(_manifest(context, *_snapshot(artifacts)), manifest, "evidence changed during audit")
    _equal(load_blueprint(repository), blueprint, "frozen dependencies changed during audit")
    _require(Path(__file__).read_bytes() == auditor_source, "auditor implementation changed during audit")
    observation = {"production_outcome": outcome, "termination": status, "revisions": revisions,
        "last_bridge_status": last["bridge"]["status"] if last else "not_submitted",
        "earlier_valid_bridge": any(r["bridge"]["status"] == "valid" for r in reports[:-1]),
        "visible_solved": status == "both_verified", "selected_bridge_sha256": selected["sha256"] if selected else None,
        "content_audit": "pending" if selected else "not_applicable", "selection_policy": SELECTION_POLICY}
    return {"audit_version": VERSION, "status": "passed", "data_kind": data_kind,
        "evidence_manifest": manifest, "evidence_sha256": digest,
        "auditor_source_sha256": sha(auditor_source),
        "verification": "synthetic_injected_checker" if checker else "fresh_sandboxed_Lean_per_revision",
        "rechecked_revisions": rechecked, "reconstructed_session": expected_summary,
        "cell_projection": {"cell_id": cell_id, "state": "completed", "trace_audit": "passed",
                            "accounting": "complete", "evidence_sha256": digest, "observation": observation},
        "accounting_scope": "logged request usage only; external daily/batch reconciliation remains required",
        "provenance_scope": "local trace consistency and external seal reference; not provider-signed authenticity",
        "content_audit": observation["content_audit"], "batch_audit_passed": False,
        "inference_admitted": False, "recipient_admitted": False, "main_sample_admitted": False,
        "mechanistic_stage_admitted": False}
