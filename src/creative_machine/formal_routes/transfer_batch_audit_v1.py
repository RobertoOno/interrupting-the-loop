"""Read-only independent audit of the sealed synthetic transfer package.

Reuses the chronology contract, per-session auditors and content-receipt
validator, never the integrator, its runner calls or its summary as evidence.
This profile does not accept experimental provenance or settle real budgets.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal, localcontext
import os
from pathlib import Path
import stat
import tempfile

from . import bridge_content_v1 as content
from . import production_audit_v1 as proposer_audit
from . import production_contract_v1 as production
from . import recipient_audit_v1 as recipient_audit
from . import recipient_contract_v1 as recipient
from . import transfer_lifecycle_v1 as lifecycle
from .transfer_analysis_v1 import analyze, blank_dataset, transfer_eligibility
from .transfer_design_v1 import encoded, load_blueprint, sha

VERSION = "p3_transfer_batch_audit_v1"
PACKAGE_VERSION = "p3_transfer_rehearsal_v1"
MAX_ENTRIES = 10000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class BatchAuditError(ValueError):
    """Contradictory evidence, never an experimental failure or zero utility."""


class BatchAuditBlocked(RuntimeError):
    """Incomplete/technical package: preserve evidence and reservations, no retry."""


def require(value, message):
    if not value:
        raise BatchAuditError(message)


def equal(actual, expected, label):
    require(encoded(actual) == encoded(expected), label + " mismatch")


def snapshot(root):
    """Own descriptor-relative reader; bounds memory and rejects all links.

    The byte inventory is portable. The identities additionally detect local
    replacement during this invocation; neither authenticates the writer.
    """
    files, directories, identities = {}, {"."}, {}
    total = entries = 0
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")

    def walk(fd, prefix=""):
        nonlocal total, entries
        for name in sorted(os.listdir(fd)):
            entries += 1
            require(entries <= MAX_ENTRIES, "package entry limit")
            rel = prefix + name
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            folder = stat.S_ISDIR(before.st_mode)
            require(folder or (stat.S_ISREG(before.st_mode) and before.st_nlink == 1), "unsafe package entry: " + rel)
            flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if folder else os.O_NONBLOCK)
            child = os.open(name, flags, dir_fd=fd)
            try:
                opened = os.fstat(child)
                require(all(getattr(before, k) == getattr(opened, k) for k in stable), "entry replaced during open")
                identities[rel] = (opened.st_dev, opened.st_ino)
                if folder:
                    directories.add(rel)
                    walk(child, rel + "/")
                else:
                    require(opened.st_size <= MAX_FILE_BYTES and total + opened.st_size <= MAX_TOTAL_BYTES, "package byte limit")
                    chunks, size = [], 0
                    while chunk := os.read(child, min(1024 * 1024, MAX_FILE_BYTES + 1 - size)):
                        size += len(chunk)
                        total += len(chunk)
                        require(size <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES, "package byte limit")
                        chunks.append(chunk)
                    require(size == opened.st_size, "package file size changed")
                    files[rel] = b"".join(chunks)
                after, linked = os.fstat(child), os.stat(name, dir_fd=fd, follow_symlinks=False)
                require(all(getattr(opened, k) == getattr(after, k) == getattr(linked, k) for k in stable), "entry changed during read")
            finally:
                os.close(child)

    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            identities["."] = (before.st_dev, before.st_ino)
            walk(fd)
            after, linked = os.fstat(fd), os.stat(root, follow_symlinks=False)
            require(all(getattr(before, k) == getattr(after, k) == getattr(linked, k) for k in stable), "package root changed")
        finally:
            os.close(fd)
    except OSError as exc:
        raise BatchAuditError("cannot safely read package: " + str(exc)) from exc
    return files, directories, identities


def _formal(value):
    # Fresh compiler diagnostic streams can contain ephemeral workspace paths.
    # All verdicts, errors, declarations, hashes, counters and flags still match.
    if isinstance(value, dict):
        return {k: _formal(v) for k, v in value.items() if k not in ("stdout", "stderr")}
    if isinstance(value, list):
        return [_formal(v) for v in value]
    return value


def audit_rehearsal_batch(repository: Path, package: Path, *, expected_closure_sha256: str,
                         expected_plan_sha256: str, expected_lifecycle_head_sha256: str,
                         permitted_reviewer_ids: tuple[str, ...], proposer_checker=None,
                         recipient_checker=None) -> dict:
    """Audit a complete synthetic package without mutating it or calling a model.

    All three expected hashes and the reviewer allowlist come from the caller,
    not from the package's own claims. A copied package is supported; historical
    absolute paths are validated as metadata and never opened. Partial/technical
    packages block, with no normalization, semantic re-review or reconciliation.
    """
    for digest in (expected_closure_sha256, expected_plan_sha256, expected_lifecycle_head_sha256):
        require(lifecycle.is_hash(digest), "three external hash references required")
    require(isinstance(permitted_reviewer_ids, tuple) and bool(permitted_reviewer_ids)
        and all(isinstance(x, str) and x.strip() for x in permitted_reviewer_ids)
        and len(set(permitted_reviewer_ids)) == len(permitted_reviewer_ids), "external reviewer allowlist required")
    repository, package = Path(repository), Path(package)
    blueprint = load_blueprint(repository)
    sources = ("transfer_batch_audit_v1.py", "transfer_rehearsal_v1.py", "transfer_lifecycle_v1.py",
               "bridge_content_v1.py", "production_audit_v1.py", "production_contract_v1.py",
               "recipient_audit_v1.py", "recipient_contract_v1.py")
    source_root = repository / "src/creative_machine/formal_routes"
    implementation = {name: sha((source_root / name).read_bytes()) for name in sources}
    before = snapshot(package)
    files, directories, _ = before
    used = set()

    def raw(rel):
        require(rel in files, "missing package file: " + rel)
        used.add(rel)
        return files[rel]

    def read(rel):
        return proposer_audit._decode(raw(rel))

    def bound(rel, digest):
        require(sha(raw(rel)) == digest, "external/file reference mismatch: " + rel)
        return read(rel)

    manifest = bound("closure_manifest.json", expected_closure_sha256)
    entries = {rel: {"kind": "directory"} for rel in directories}
    entries.update({rel: {"kind": "file", "size": len(data), "sha256": sha(data)}
                    for rel, data in files.items() if rel != "closure_manifest.json"})
    equal(manifest, {"version": PACKAGE_VERSION, "data_kind": "synthetic", "entries": entries,
        "lifecycle_head_sha256": expected_lifecycle_head_sha256, "excludes": ["closure_manifest.json"],
        "independent_batch_audit_passed": False}, "whole closure inventory")
    plan = bound("rehearsal_plan.json", expected_plan_sha256)
    scenario = read("scenario.json")
    equal(plan, {"version": PACKAGE_VERSION, "data_kind": "synthetic", "source": "recorded_responses_only",
        "blueprint_sha256": sha(encoded(blueprint)), "scenario_sha256": sha(encoded(scenario)),
        "implementation_sha256": implementation["transfer_rehearsal_v1.py"],
        "permitted_reviewer_ids": list(permitted_reviewer_ids), "inference_admitted": False}, "synthetic plan")
    require(isinstance(scenario, dict) and set(scenario) == {c["cell_id"] for c in blueprint["cells"]}, "fixed scenario positions")
    for steps in scenario.values():
        require(isinstance(steps, list) and len(steps) <= 12, "scenario step limit")
        require(all(isinstance(s, dict) and set(s) == {"input_tokens", "response"} for s in steps), "scenario step schema")
    journal_bytes = raw("lifecycle.jsonl")
    require(len(journal_bytes) <= lifecycle.MAX_BYTES and journal_bytes.endswith(b"\n"), "incomplete/oversize journal")
    rows = [proposer_audit._decode(line) for line in journal_bytes.splitlines()]
    state = lifecycle.replay(blueprint, rows, expected_head_sha256=expected_lifecycle_head_sha256)
    equal([state["header"]["data_kind"], state["header"]["execution_plan_sha256"]],
          ["synthetic", expected_plan_sha256], "journal plan/kind")
    header = state["header"]
    for field, expected in (
        ("reservation_sha256", {"kind": "synthetic_reservation_fixture", "usd": "50", "real_reservation": False}),
        ("provenance_sha256", {"kind": "synthetic_provenance_fixture", "plan_sha256": expected_plan_sha256, "provider_authenticated": False}),
        ("preflight_sha256", {"kind": "synthetic_preflight_fixture", "plan_sha256": expected_plan_sha256, "experimental_preflight": False}),
    ):
        equal(bound("receipts/" + header[field] + ".json", header[field]), expected, "synthetic prerequisite receipt")
    if state["status"] != "closed" or state["consumed_positions"] != 26:
        raise BatchAuditBlocked("incomplete/technical lifecycle; preserve package and reservations, no scientific projection or retry")
    for row in rows:
        equal(read(f"checkpoints/{row['seq']:04d}.json"),
              {"head_sha256": row["sha256"], "events": row["seq"], "data_kind": "synthetic"}, "external checkpoint")
    by_event = {(r["event"], r["payload"].get("cell_id")): r for r in rows}
    dataset = blank_dataset(blueprint, data_kind="synthetic")
    projections, reports, candidates, costs = {}, {}, {}, []
    fresh_receipts = {}

    def compare_report(stored, fresh, input_record):
        require(set(stored) == set(fresh), "stored trace audit schema")
        require(stored["verification"] == ("synthetic_injected_checker" if input_record["checker_injected"]
                                          else "fresh_sandboxed_Lean_per_revision"), "original verification label")
        equal(_formal({k: v for k, v in stored.items() if k != "verification"}),
              _formal({k: v for k, v in fresh.items() if k != "verification"}), "fresh audit/retained audit")

    for cell in blueprint["cells"]:
        identity = cell["cell_id"]
        recorded = state["cells"][identity]
        prefix = "cells/" + identity + "/"
        if recorded["state"] == "skipped_no_bridge":
            parent = projections[cell["parent_proposer_id"]]
            eligible, reason = transfer_eligibility(parent["observation"])
            require(eligible is False and recorded["skip_reason"] == reason, "independently derived skip reason")
            projections[identity] = {"cell_id": identity, "state": "skipped_no_bridge", "trace_audit": "not_applicable",
                                    "accounting": "not_applicable", "evidence_sha256": None, "observation": None}
            continue
        candidate = candidates.get(cell["parent_proposer_id"]) if cell["bridge_kind"] == "candidate" else None
        if cell["bridge_kind"] == "candidate":
            require(transfer_eligibility(projections[cell["parent_proposer_id"]]["observation"])[0] is True,
                    "recipient lacks independently reviewed parent")
            require(candidate is not None and candidate.sha256 == recorded["bridge_sha256"], "exact parent bridge binding")
        start, close, audited = (by_event[(kind, identity)] for kind in ("cell_started", "cell_closed", "trace_audited"))
        workspace = bound(prefix + "workspace_record.json", start["payload"]["workspace_record_sha256"])
        source = read(prefix + "artifacts/input.json")
        require(source["client_class"] == "creative_machine.formal_routes.transfer_rehearsal_v1.RecordedClient", "rehearsal provider label")
        require(isinstance(workspace.get("path"), str) and Path(workspace["path"]).is_absolute()
                and Path(workspace["path"]).parts[-3:] == ("cells", identity, "workspace"), "historical workspace path metadata")
        # Reconstruct canonical immutable inputs rather than accepting a
        # self-selected copied_hashes allowlist from the archived workspace.
        if cell["role"] == "proposer":
            with tempfile.TemporaryDirectory(prefix="p3-batch-input-") as temp:
                record = production.materialize_production_proposer(repository / cell["world"], cell["arm"], Path(temp) / "workspace")
                expected_workspace = {**asdict(record), "path": workspace["path"]}
                inputs = {rel: (record.path / rel).read_bytes() for rel in record.copied_hashes}
            module, audit_fn, checker = proposer_audit, proposer_audit.audit_proposer_trace, proposer_checker
        else:
            spec = recipient._spec(repository, identity, candidate)
            inputs = spec["inputs"]
            expected_workspace = {"path": workspace["path"], "world_id": cell["world_id"], "role": "evaluator",
                "condition": spec["condition"], "copied_hashes": {rel: sha(data) for rel, data in inputs.items()},
                "allowed_outputs": ["Solution.lean"]}
            module, audit_fn, checker = recipient_audit, recipient_audit.audit_recipient_trace, recipient_checker
        equal(workspace, expected_workspace, "canonical workspace receipt")
        equal(source["copied_hashes"], workspace["copied_hashes"], "workspace/input linkage")
        context = {"cell_id": identity, "data_kind": "synthetic", "execution_plan_sha256": expected_plan_sha256}
        if cell["role"] == "recipient":
            context["candidate"] = candidate
        seal = bound(prefix + "evidence_manifest.json", recorded["evidence_sha256"])
        try:
            fresh = audit_fn(repository, package / prefix / "artifacts", **context,
                expected_evidence_sha256=recorded["evidence_sha256"], checker=checker)
        except proposer_audit.TraceAuditBlocked as exc:
            raise BatchAuditBlocked("fresh session audit blocked: " + identity + ": " + str(exc)) from exc
        equal(seal, fresh["evidence_manifest"], "raw evidence inventory")
        retained = bound(prefix + "trace_audit.json", recorded["audit_sha256"])
        compare_report(retained, fresh, source)
        fresh_receipts[identity] = fresh
        reports[identity] = fresh
        summary = fresh["reconstructed_session"]
        equal(close["payload"], {"cell_id": identity, "evidence_sha256": fresh["evidence_sha256"],
            "reported_cost_usd": format(Decimal(str(summary["cost_usd_at_configured_rates"])), "f"),
            "accounting_complete": summary["accounting_complete"], "technical_failure": summary["infrastructure_failure"]}, "journal/independent cost")
        costs.append(Decimal(close["payload"]["reported_cost_usd"]))
        obs = fresh["cell_projection"]["observation"]
        equal(audited["payload"], {"cell_id": identity, "evidence_sha256": fresh["evidence_sha256"],
            "audit_sha256": sha(raw(prefix + "trace_audit.json")), "status": "passed",
            "production_outcome": obs.get("production_outcome"), "selected_bridge_sha256": obs.get("selected_bridge_sha256")}, "journal/fresh projection")
        events = [proposer_audit._decode(line) for line in raw(prefix + "artifacts/events.jsonl").splitlines()]
        lower, upper = lifecycle.instant(start["at"]), lifecycle.instant(close["at"])
        require(lower <= lifecycle.instant(source["started_at"]) <= upper
                and all(lower <= lifecycle.instant(e["at"]) <= upper for e in events), "raw session outside lifecycle interval")
        step = 0
        for event in events:
            if event["event"] in ("count_finished", "response"):
                require(step < len(scenario[identity]), "scenario exhausted before logged provider event")
                expected = scenario[identity][step]
                if event["event"] == "count_finished":
                    equal(event["input_tokens"], expected["input_tokens"], "recorded token count")
                else:
                    equal(event["body"], expected["response"], "recorded provider response")
                    step += 1
        work_files = dict(inputs)
        for name in expected_workspace["allowed_outputs"]:
            rel = prefix + f"artifacts/revisions/{summary['revisions']:04d}/" + name
            if rel in files:
                work_files[name] = files[rel]
        actual_work = {rel.removeprefix(prefix + "workspace/"): data for rel, data in files.items() if rel.startswith(prefix + "workspace/")}
        require(actual_work == work_files, "final workspace differs from immutable inputs/last submission")
        for rel in files:
            if rel.startswith(prefix + "artifacts/") or rel.startswith(prefix + "workspace/"):
                used.add(rel)
        projection = deepcopy(fresh["cell_projection"])
        if cell["role"] == "proposer" and obs["production_outcome"] == "valid_bridge":
            prepared, reviewed = (by_event[(kind, identity)] for kind in ("review_prepared", "review_recorded"))
            bundle = read("review_host/" + identity + ".json")
            equal(sha(encoded(bundle["binding"])), prepared["payload"]["binding_sha256"], "prepared binding")
            compare_report(bundle["trace_audit"], fresh, source)
            packet = bound("review_packets/" + prepared["payload"]["review_id"] + ".json", prepared["payload"]["packet_sha256"])
            equal(packet, bundle["packet"], "separate reviewer packet")
            receipt = bound("review_host/" + identity + "-review.json", reviewed["payload"]["receipt_sha256"])
            checked = content.record_content_review(repository, bundle, receipt["review"],
                expected_binding_sha256=prepared["payload"]["binding_sha256"], permitted_reviewer_ids=permitted_reviewer_ids)
            equal({k: v for k, v in receipt.items() if k != "recorded_at"},
                  {k: v for k, v in checked.items() if k != "recorded_at"}, "recorded content judgment")
            require(lifecycle.instant(prepared["at"]) <= lifecycle.instant(receipt["recorded_at"]) <= lifecycle.instant(reviewed["at"]), "review outside lifecycle interval")
            equal(checked["content_status"], recorded["content_status"], "journal/content status")
            projection = checked["cell_projection"]
            selected = fresh["reconstructed_session"]["selected_bridge"]
            bridge = raw(prefix + "artifacts/selected_bridge/Bridge.lean")
            candidates[identity] = production.BridgeArtifact(bridge, selected["sha256"], selected["world_id"],
                selected["namespace"], selected["declaration"], tuple(tuple(pair) for pair in selected["base_hashes"]))
        projections[identity] = projection

    prepared = [r["seq"] for r in rows if r["event"] == "review_prepared"]
    reviewed = [r["seq"] for r in rows if r["event"] == "review_recorded"]
    require(not prepared or (reviewed and max(prepared) < min(reviewed)), "all packets must precede first content review")
    dataset["cells"] = [projections[c["cell_id"]] for c in blueprint["cells"]]
    equal(read("dataset.json"), dataset, "independently reconstructed dataset")
    analysis = analyze(blueprint, dataset)
    equal(read("analysis.json"), analysis, "independently reconstructed blocked analysis")
    with localcontext() as ctx:
        ctx.prec = 80
        total = format(sum(costs, Decimal(0)), "f")
    require(Decimal(total) == Decimal(state["known_reported_cost_usd"]), "whole logged cost mismatch")
    expected_summary = {"version": PACKAGE_VERSION, "status": "complete_rehearsal", "data_kind": "synthetic",
        "plan_sha256": expected_plan_sha256, "lifecycle_head_sha256": expected_lifecycle_head_sha256,
        "recorded_session_count": len(reports), "audited_session_count": len(reports), "review_packet_count": len(prepared),
        "slot_count": 26, "analysis_status": analysis["status"], "external_reservation_must_remain_open": True,
        "real_reservation_created": False, "independent_batch_audit_passed": False, "inference_admitted": False,
        "main_sample_admitted": False, "mechanistic_stage_admitted": False}
    equal(read("summary.json"), expected_summary, "independent batch summary")
    require(used == set(files), "unbound/extra package file")
    expected_dirs = {".", "receipts", "cells", "review_packets", "review_host", "checkpoints"}
    expected_dirs.update(p.as_posix() for rel in used for p in Path(rel).parents)
    equal(sorted(directories), sorted(expected_dirs), "unbound/extra package directory")
    require(snapshot(package) == before, "package changed during independent audit")
    equal(load_blueprint(repository), blueprint, "blueprint changed during batch audit")
    equal({name: sha((source_root / name).read_bytes()) for name in sources}, implementation, "implementation changed during batch audit")
    return {"version": VERSION, "status": "passed", "data_kind": "synthetic",
        "scope": "complete synthetic package consistency; not experimental admission or authenticated provenance",
        "closure_sha256": expected_closure_sha256, "execution_plan_sha256": expected_plan_sha256,
        "lifecycle_head_sha256": expected_lifecycle_head_sha256, "implementation_sha256": implementation,
        "reaudited_sessions": len(reports), "review_receipts_validated": len(prepared),
        "skipped_candidate_positions": 26 - len(reports), "logged_synthetic_cost_usd": total,
        "fresh_trace_audits": fresh_receipts, "reconstructed_dataset": dataset, "analysis": analysis,
        "internal_phase_barrier_verified": True, "semantic_judgments_reissued": False,
        "provider_origin_authenticated": False, "external_financial_reconciliation_verified": False,
        "worker_ownership_verified": False, "external_reservation_must_remain_open": True,
        "inference_admitted": False, "main_sample_admitted": False, "mechanistic_stage_admitted": False}
