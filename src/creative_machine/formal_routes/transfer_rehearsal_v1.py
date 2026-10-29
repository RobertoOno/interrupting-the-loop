"""End-to-end integration rehearsal with recorded responses, never a live client.

Uses real materializers, session runners, trace auditors, content receipts and
lifecycle journal. Only the provider is intrinsically simulated. Lean checkers
may be supplied for portable fixtures, or omitted for real kernel verification.
This is not the production launcher, independent batch auditor or admission.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import stat
from types import SimpleNamespace

from . import bridge_content_v1 as content
from . import production_audit_v1 as proposer_audit
from . import production_contract_v1 as proposer_contract
from . import production_runner_v1 as proposer_runner
from . import recipient_audit_v1 as recipient_audit
from . import recipient_contract_v1 as recipient_contract
from . import recipient_runner_v1 as recipient_runner
from . import transfer_lifecycle_v1 as lifecycle
from .transfer_analysis_v1 import blank_dataset, analyze, transfer_eligibility
from .transfer_design_v1 import encoded, load_blueprint, sha

VERSION = "p3_transfer_rehearsal_v1"


def _inventory(root):
    """Bounded, descriptor-relative fingerprint; never follow links.

    Inodes detect replacements during this process. The portable closure uses
    only bytes/types; neither constitutes authentication or a worker lease.
    The whole rehearsal can exceed the per-session auditor's 256-entry limit.
    """
    result = {}
    total = 0
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")

    def walk(fd, prefix=""):
        nonlocal total
        for name in sorted(os.listdir(fd)):
            lifecycle.require(len(result) < 10000, "rehearsal inventory entry limit")
            rel = prefix + name
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            is_dir = stat.S_ISDIR(before.st_mode)
            lifecycle.require(is_dir or (stat.S_ISREG(before.st_mode) and before.st_nlink == 1),
                              "unsafe rehearsal entry: " + rel)
            flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if is_dir else os.O_NONBLOCK)
            child = os.open(name, flags, dir_fd=fd)
            try:
                opened = os.fstat(child)
                lifecycle.require(all(getattr(before, k) == getattr(opened, k) for k in stable),
                                  "rehearsal entry replaced while opening: " + rel)
                item = {"kind": "directory" if is_dir else "file", "device": opened.st_dev, "inode": opened.st_ino}
                result[rel] = item
                if is_dir:
                    walk(child, rel + "/")
                else:
                    lifecycle.require(opened.st_size <= proposer_audit.MAX_FILE_BYTES, "rehearsal file size limit")
                    digest, size = hashlib.sha256(), 0
                    while chunk := os.read(child, 1024 * 1024):
                        size += len(chunk)
                        total += len(chunk)
                        lifecycle.require(size <= proposer_audit.MAX_FILE_BYTES and total <= proposer_audit.MAX_TOTAL_BYTES,
                                          "rehearsal byte limit")
                        digest.update(chunk)
                    lifecycle.require(size == opened.st_size, "rehearsal file size changed")
                    item.update(sha256=digest.hexdigest(), size=size)
                after = os.fstat(child)
                linked = os.stat(name, dir_fd=fd, follow_symlinks=False)
                lifecycle.require(all(getattr(opened, k) == getattr(after, k) == getattr(linked, k) for k in stable),
                                  "rehearsal entry changed while reading: " + rel)
            finally:
                os.close(child)

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        result["."] = {"kind": "directory", "device": before.st_dev, "inode": before.st_ino}
        walk(fd)
        after, linked = os.fstat(fd), os.stat(root, follow_symlinks=False)
        lifecycle.require(all(getattr(before, k) == getattr(after, k) == getattr(linked, k) for k in stable),
                          "rehearsal root changed while reading")
    finally:
        os.close(fd)
    return result


class RecordedClient:
    """No SDK, credentials, network or client factory; consumes explicit fixtures."""
    max_retries = 0

    def __init__(self, steps):
        self.steps = deepcopy(steps)
        self.index = 0
        self.messages = self

    def count_tokens(self, **kwargs):
        if self.index >= len(self.steps):
            raise RuntimeError("recorded fixture exhausted before token count")
        return SimpleNamespace(input_tokens=self.steps[self.index]["input_tokens"])

    def create(self, **kwargs):
        if self.index >= len(self.steps):
            raise RuntimeError("recorded fixture exhausted before response")
        response = deepcopy(self.steps[self.index]["response"])
        self.index += 1
        return SimpleNamespace(model_dump=lambda **_: deepcopy(response))


def _save_new(path, value):
    data = encoded(value)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return sha(data)


def _ref(root, value, save):
    data = encoded(value)
    digest = sha(data)
    path = root / "receipts" / (digest + ".json")
    if path.exists() or path.is_symlink():
        lifecycle.require(not path.is_symlink() and path.is_file() and path.stat().st_nlink == 1
                          and path.read_bytes() == data, "receipt collision or replacement")
    else:
        save(path, value)
    return digest


def _candidate(root, cell, audit):
    selected = audit["reconstructed_session"]["selected_bridge"]
    lifecycle.require(selected is not None, "missing audited final bridge")
    path = root / "cells" / cell["cell_id"] / "artifacts" / "selected_bridge" / "Bridge.lean"
    lifecycle.require(not path.is_symlink() and path.is_file() and path.stat().st_nlink == 1, "unsafe selected bridge")
    source = path.read_bytes()
    lifecycle.require(sha(source) == selected["sha256"], "selected bridge changed after audit")
    return proposer_contract.BridgeArtifact(source, selected["sha256"], selected["world_id"],
        selected["namespace"], selected["declaration"], tuple(tuple(pair) for pair in selected["base_hashes"]))


def run_rehearsal(repository: Path, destination: Path, scenario: dict, *, reviewer,
                  permitted_reviewer_ids: tuple[str, ...], proposer_checker=None,
                  recipient_checker=None, bridge_process_runner=None, bridge_lake=None) -> dict:
    """Run one exclusive synthetic directory; never resume or overwrite it.

    Scenario contains all 26 fixed positions even when candidates will be
    skipped. Reviewer receives ONLY a copied, label-masked packet. Its callback
    and any injected checkers are trusted test code, not sandboxed judges.
    Returning None pauses without a content decision; pending cannot be replaced.
    The caller must keep every artifact synthetic and retain the returned head.
    """
    repository, root = Path(repository), Path(destination)
    blueprint = load_blueprint(repository)
    expected_ids = {c["cell_id"] for c in blueprint["cells"]}
    lifecycle.require(isinstance(scenario, dict) and set(scenario) == expected_ids, "scenario must contain all 26 fixed positions")
    for steps in scenario.values():
        lifecycle.require(isinstance(steps, list) and len(steps) <= 12, "recorded scenario steps")
        for step in steps:
            lifecycle.require(isinstance(step, dict) and set(step) == {"input_tokens", "response"}, "recorded step schema")
    # JSON round-trip also detaches all inputs from caller mutation. Native count
    # and response shape errors remain intentional runner failure fixtures.
    frozen_scenario = proposer_audit._decode(encoded(scenario))
    lifecycle.require(callable(reviewer) and isinstance(permitted_reviewer_ids, tuple)
        and bool(permitted_reviewer_ids) and all(isinstance(x, str) and x.strip() for x in permitted_reviewer_ids),
        "explicit synthetic reviewer and allowlist required")
    root.mkdir(exist_ok=False)  # A second process or ambiguous restart cannot win.
    for name in ("receipts", "cells", "review_packets", "review_host", "checkpoints"):
        (root / name).mkdir()
    expected = _inventory(root)

    def retain(path):
        # Called only for a newly created file or a cell just finished by the
        # trusted runner. Previously retained members must remain identical.
        prefix = path.relative_to(root).as_posix()
        if path.is_dir():
            items = {prefix if rel == "." else prefix + "/" + rel: item
                     for rel, item in _inventory(path).items()}
        else:
            items = {prefix: _inventory(path.parent)[path.name]}
        for rel, item in items.items():
            lifecycle.require(rel not in expected or expected[rel] == item, "retained rehearsal artifact changed: " + rel)
            expected[rel] = item

    def intact():
        lifecycle.require(_inventory(root) == expected, "rehearsal package changed after retention")

    def save(path, value):
        digest = _save_new(path, value)
        retain(path)
        lifecycle.require(expected[path.relative_to(root).as_posix()]["sha256"] == digest, "saved receipt changed")
        return digest

    def ref(value):
        return _ref(root, value, save)

    plan = {"version": VERSION, "data_kind": "synthetic", "source": "recorded_responses_only",
        "blueprint_sha256": sha(encoded(blueprint)), "scenario_sha256": sha(encoded(frozen_scenario)),
        "implementation_sha256": sha(Path(__file__).read_bytes()),
        "permitted_reviewer_ids": list(permitted_reviewer_ids), "inference_admitted": False}
    plan_sha = save(root / "rehearsal_plan.json", plan)
    save(root / "scenario.json", frozen_scenario)
    reservation = ref({"kind": "synthetic_reservation_fixture", "usd": "50", "real_reservation": False})
    provenance = ref({"kind": "synthetic_provenance_fixture", "plan_sha256": plan_sha, "provider_authenticated": False})
    preflight = ref({"kind": "synthetic_preflight_fixture", "plan_sha256": plan_sha, "experimental_preflight": False})
    journal = lifecycle.Journal(root / "lifecycle.jsonl", blueprint)
    state = journal.create(lifecycle.opening_payload(blueprint, execution_plan_sha256=plan_sha,
        data_kind="synthetic", reservation_sha256=reservation, provenance_sha256=provenance, preflight_sha256=preflight))
    retain(root / "lifecycle.jsonl")
    audits, projections, bundles = {}, {}, {}

    def checkpoint():
        save(root / "checkpoints" / f"{state['events']:04d}.json",
                  {"head_sha256": state["head_sha256"], "events": state["events"], "data_kind": "synthetic"})

    def emit(event, payload):
        nonlocal state
        before = _inventory(root)["lifecycle.jsonl"]
        lifecycle.require(before == expected["lifecycle.jsonl"], "journal changed outside lifecycle writer")
        state = journal.append(event, payload, expected_head_sha256=state["head_sha256"])
        after = _inventory(root)["lifecycle.jsonl"]
        lifecycle.require((after["device"], after["inode"]) == (before["device"], before["inode"]), "journal replaced")
        expected["lifecycle.jsonl"] = after
        checkpoint()

    def failed(phase, exc, cell_id=None):
        return ref({"kind": "synthetic_integration_failure", "phase": phase, "cell_id": cell_id,
            "error_type": type(exc).__name__, "error": str(exc), "data_kind": "synthetic"})

    def close_summary(status):
        intact()
        # A lifecycle history is not the independent batch audit or external
        # settlement. Even a complete rehearsal cannot unlock scientific scores.
        dataset = blank_dataset(blueprint, data_kind="synthetic")
        dataset["cells"] = [deepcopy(projections.get(c["cell_id"], c)) for c in dataset["cells"]]
        analysis = analyze(blueprint, dataset)
        save(root / "dataset.json", dataset)
        save(root / "analysis.json", analysis)
        actual = journal.read(expected_head_sha256=state["head_sha256"])
        lifecycle.require(load_blueprint(repository) == blueprint, "blueprint changed during rehearsal")
        lifecycle.require(sha(Path(__file__).read_bytes()) == plan["implementation_sha256"], "rehearsal implementation changed")
        result = {"version": VERSION, "status": status, "data_kind": "synthetic",
            "plan_sha256": plan_sha, "lifecycle_head_sha256": actual["head_sha256"],
            "recorded_session_count": actual["admissions"], "audited_session_count": len(audits),
            "review_packet_count": len(bundles), "slot_count": 26, "analysis_status": analysis["status"],
            "external_reservation_must_remain_open": True, "real_reservation_created": False,
            "independent_batch_audit_passed": False, "inference_admitted": False,
            "main_sample_admitted": False, "mechanistic_stage_admitted": False}
        save(root / "summary.json", result)
        intact()
        manifest = {"version": VERSION, "data_kind": "synthetic", "lifecycle_head_sha256": actual["head_sha256"],
            "entries": {rel: {k: v for k, v in item.items() if k not in ("device", "inode")}
                        for rel, item in sorted(expected.items())},
            "excludes": ["closure_manifest.json"], "independent_batch_audit_passed": False}
        seal = save(root / "closure_manifest.json", manifest)
        intact()
        return {**result, "closure_manifest_sha256": seal}

    def run_one(cell, candidate=None):
        intact()
        identity = cell["cell_id"]
        cell_root = root / "cells" / identity
        started = False
        evidence_sha = None
        try:
            cell_root.mkdir()
            if cell["role"] == "proposer":
                record = proposer_contract.materialize_production_proposer(repository / cell["world"], cell["arm"], cell_root / "workspace")
            else:
                record = recipient_contract.materialize_recipient(repository, identity, cell_root / "workspace", candidate=candidate,
                    process_runner=bridge_process_runner, lake=bridge_lake)
            workspace = {**asdict(record), "path": str(record.path)}
            workspace_sha = save(cell_root / "workspace_record.json", workspace)
            supplied = record.copied_hashes.get("Bridge.lean") if cell["role"] == "recipient" else None
            emit("cell_started", {"cell_id": identity, "bridge_sha256": supplied, "workspace_record_sha256": workspace_sha})
            started = True
            client = RecordedClient(frozen_scenario[identity])
            if cell["role"] == "proposer":
                result = proposer_runner.run_production_session(record, namespace="P3." + cell["world_id"],
                    artifacts=cell_root / "artifacts", config=proposer_runner.production_config(), client=client, checker=proposer_checker)
                module, kwargs = proposer_audit, {"checker": proposer_checker}
            else:
                result = recipient_runner.run_recipient_session(record, repository=repository, cell_id=identity,
                    candidate=candidate, artifacts=cell_root / "artifacts", config=recipient_runner.recipient_config(),
                    client=client, checker=recipient_checker)
                module, kwargs = recipient_audit, {"checker": recipient_checker, "candidate": candidate}
            context = {"cell_id": identity, "data_kind": "synthetic", "execution_plan_sha256": plan_sha}
            manifest_kwargs = {**context, **({"candidate": candidate} if cell["role"] == "recipient" else {})}
            manifest = module.build_evidence_manifest(repository, cell_root / "artifacts", **manifest_kwargs)
            evidence_sha = save(cell_root / "evidence_manifest.json", manifest)
            emit("cell_closed", {"cell_id": identity, "evidence_sha256": evidence_sha,
                "reported_cost_usd": format(Decimal(str(result["cost_usd_at_configured_rates"])), "f"),
                "accounting_complete": result["accounting_complete"], "technical_failure": result["infrastructure_failure"]})
            try:
                audit_function = module.audit_proposer_trace if cell["role"] == "proposer" else module.audit_recipient_trace
                report = audit_function(repository, cell_root / "artifacts", **context,
                    expected_evidence_sha256=evidence_sha, **kwargs)
            except Exception as exc:
                projections[identity] = {"cell_id": identity, "state": "technical_failure",
                    "trace_audit": "failed", "accounting": "pending", "evidence_sha256": evidence_sha, "observation": None}
                failure_sha = failed("trace_audit", exc, identity)
                emit("trace_audited", {"cell_id": identity, "evidence_sha256": evidence_sha, "audit_sha256": failure_sha,
                    "status": "failed", "production_outcome": None, "selected_bridge_sha256": None})
                return False
            audit_sha = save(cell_root / "trace_audit.json", report)
            observation = report["cell_projection"]["observation"]
            emit("trace_audited", {"cell_id": identity, "evidence_sha256": evidence_sha, "audit_sha256": audit_sha,
                "status": "passed", "production_outcome": observation.get("production_outcome"),
                "selected_bridge_sha256": observation.get("selected_bridge_sha256")})
            audits[identity] = report
            projections[identity] = report["cell_projection"]
            return True
        except Exception as exc:
            # append may have succeeded even when saving its external
            # checkpoint failed. The durable state wins over the local flag.
            started = started or state["cells"][identity]["start_seq"] is not None
            if started:
                projections[identity] = {"cell_id": identity, "state": "technical_failure",
                    "trace_audit": "pending", "accounting": "pending", "evidence_sha256": evidence_sha, "observation": None}
            failure_sha = failed("session_or_persistence_after_intent" if started else "preparation", exc, identity)
            # If a write failed ambiguously, never repair its prefix or assert
            # that an admitted session has safely closed. Preserve active intent.
            try:
                actual = journal.read(expected_head_sha256=state["head_sha256"])
                if actual["status"] == "open":
                    emit("halted", {"reason": "rehearsal preparation/session/persistence failure", "evidence_sha256": failure_sha})
            except Exception:
                raise RuntimeError("ambiguous rehearsal journal; preserve all files, no restart") from exc
            return False
        finally:
            if cell_root.exists():
                retain(cell_root)
            intact()

    checkpoint()
    for cell in blueprint["cells"][:6]:
        if not run_one(cell):
            if not state["active_cells"]:
                emit("batch_closed", {})
            return close_summary("halted_rehearsal")

    # Prepare every packet only after all six independent trace audits. The
    # existing content API performs another fresh audit. Preserve both receipts;
    # diagnostic text may differ, but the evidence and projection must not.
    try:
        for cell in blueprint["cells"][:6]:
            identity = cell["cell_id"]
            if transfer_eligibility(projections[identity]["observation"])[0] is False:
                continue
            report = audits[identity]
            bundle = content.prepare_content_review(repository, root / "cells" / identity / "artifacts", cell_id=identity,
                data_kind="synthetic", execution_plan_sha256=plan_sha,
                expected_evidence_sha256=report["evidence_sha256"], checker=proposer_checker)
            lifecycle.require(encoded(bundle["trace_audit"]["cell_projection"]) == encoded(report["cell_projection"]),
                              "content preparation disagrees with first trace audit")
            save(root / "review_host" / (identity + ".json"), bundle)
            packet, binding = bundle["packet"], bundle["binding"]
            packet_sha = save(root / "review_packets" / (packet["review_id"] + ".json"), packet)
            emit("review_prepared", {"cell_id": identity, "binding_sha256": sha(encoded(binding)),
                "packet_sha256": packet_sha, "review_id": packet["review_id"]})
            bundles[identity] = bundle
        unresolved = False
        for identity, bundle in sorted(bundles.items(), key=lambda pair: pair[1]["packet"]["review_id"]):
            intact()
            judgment = reviewer(deepcopy(bundle["packet"]))
            intact()
            if judgment is None:
                unresolved = True
                continue
            receipt = content.record_content_review(repository, bundle, judgment,
                expected_binding_sha256=sha(encoded(bundle["binding"])), permitted_reviewer_ids=permitted_reviewer_ids)
            receipt_sha = save(root / "review_host" / (identity + "-review.json"), receipt)
            emit("review_recorded", {"cell_id": identity, "binding_sha256": sha(encoded(bundle["binding"])),
                "packet_sha256": bundle["binding"]["packet_sha256"], "review_id": bundle["packet"]["review_id"],
                "receipt_sha256": receipt_sha, "content_status": receipt["content_status"]})
            projections[identity] = receipt["cell_projection"]
            unresolved = unresolved or receipt["content_status"] == "pending"
        if unresolved:
            return close_summary("awaiting_synthetic_review")
        emit("phase_barrier", {"proposer_bindings_sha256": state["ready_proposer_bindings_sha256"]})
    except Exception as exc:
        emit("halted", {"reason": "rehearsal content process failed", "evidence_sha256": failed("content_review", exc)})
        emit("batch_closed", {})
        return close_summary("halted_rehearsal")

    by_id = {c["cell_id"]: c for c in blueprint["cells"]}
    for cell in blueprint["cells"][6:]:
        candidate = None
        if cell["bridge_kind"] == "candidate":
            parent = cell["parent_proposer_id"]
            eligible, reason = transfer_eligibility(projections[parent]["observation"])
            if eligible is False:
                emit("cell_skipped", {"cell_id": cell["cell_id"], "reason": reason,
                    "parent_evidence_sha256": projections[parent]["evidence_sha256"]})
                projections[cell["cell_id"]] = {"cell_id": cell["cell_id"], "state": "skipped_no_bridge",
                    "trace_audit": "not_applicable", "accounting": "not_applicable", "evidence_sha256": None, "observation": None}
                continue
            try:
                candidate = _candidate(root, by_id[parent], audits[parent])
            except Exception as exc:
                emit("halted", {"reason": "audited selected bridge changed", "evidence_sha256": failed("candidate_binding", exc, cell["cell_id"])})
                emit("batch_closed", {})
                return close_summary("halted_rehearsal")
        if not run_one(cell, candidate):
            if not state["active_cells"]:
                emit("batch_closed", {})
            return close_summary("halted_rehearsal")
    emit("batch_closed", {})
    return close_summary("complete_rehearsal")
