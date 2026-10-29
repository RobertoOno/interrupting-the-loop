#!/usr/bin/env python3
"""Create one immutable S16 evidence copy and operational/source closure."""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess

from creative_machine.formal_routes import sensitivity_protocol_v1 as protocol
from creative_machine.formal_routes.calibration import write_raw_manifest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("s16_archive_auditor", ROOT / "scripts/p3_audit_sensitivity_v1.py")
auditor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auditor)
CLOSURE = "docs/p3/response_limit_sensitivity_closure_v1"
TOOLS = ("scripts/p3_audit_sensitivity_v1.py", "scripts/p3_archive_sensitivity_v1.py",
    "tests/test_p3_sensitivity_audit.py", "tests/test_p3_sensitivity_archive.py")


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def budget_subset(journal, reservation, settlement):
    selected = [line for line in journal.splitlines(keepends=True)
        if line.strip() and json.loads(line)["run_id"] == protocol.PLAN_ID]
    auditor.require(protocol.same([json.loads(line) for line in selected], [reservation, settlement]),
                    "local budget journal differs from run receipts")
    return "".join(selected)


def check_log(log, rows, receipt, intent):
    events = []
    for line in log.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and "event" in value:
            events.append(value)
    auditor.require(len(events) == len(rows) + 1 and events[0] == {"event": "batch_started",
        "plan_id": protocol.PLAN_ID, "pid": receipt["pid"], "commit": auditor.FROZEN_COMMIT}, "batch log drift")
    auditor.require(receipt["commit"] == intent["commit"] == auditor.FROZEN_COMMIT and
        intent["plan_id"] == protocol.PLAN_ID, "launch receipt drift")
    expected = {r["cell"]["cell_id"]: r["result"]["status"] for r in rows}
    seen = set()
    for index, event in enumerate(events[1:], 1):
        identity = event["cell_id"]
        auditor.require(identity in expected and identity not in seen and event == {
            "event": "cell_completed", "cell_id": identity, "completed": index,
            "total": 16, "status": expected[identity]}, "cell completion log drift")
        seen.add(identity)


def archive(repository):
    raw = repository / protocol.RUN_PATH
    manifest = Path(str(raw) + ".sha256")
    destination = repository / protocol.ARCHIVE_PATH
    closure = repository / CLOSURE
    closure_manifest = Path(str(closure) + ".sha256")
    for path in (destination, closure, closure_manifest):
        if path.exists() or path.is_symlink():
            raise FileExistsError("archive already started; verify existing evidence, never overwrite")
    checked = auditor.audit(repository, raw, manifest)
    entries = auditor.verify_manifest(raw, manifest)
    plan = auditor.read(raw / "plan.json")
    intent_path = raw.parent / (protocol.PLAN_ID + "-launch.json")
    receipt_path = raw.parent / (protocol.PLAN_ID + "-process.json")
    log_path = raw.parent / (protocol.PLAN_ID + ".log")
    intent, receipt = auditor.read(intent_path), auditor.read(receipt_path)
    rows = [auditor.read(raw / c["cell_id"] / "result.json") for c in plan["cells"]]
    check_log(log_path.read_text(), rows, receipt, intent)
    budget = budget_subset((repository / "runs/aws-budget/claude_daily.jsonl").read_text(),
        auditor.read(raw / "budget-reservation.json"), auditor.read(raw / "budget-settlement.json"))
    names = {*plan["harness_sha256"], protocol.PLAN_PATH,
        auditor.read(repository / protocol.PARENT_PATH)["local_evidence"]["path"]}
    for world in plan["worlds"]:
        metadata = auditor.read(repository / world["path"] / "metadata.json")
        names.update(world["path"] + "/" + name for name in (*metadata["artifact_hashes"], "metadata.json", "manifest.sha256"))
    # Resolve all frozen blobs before creating the archive; no broad tree copies.
    blobs = {name: subprocess.check_output(["git", "show", auditor.FROZEN_COMMIT + ":" + name],
        cwd=repository, timeout=15) for name in sorted(names)}
    for name, blob in blobs.items():
        auditor.require(blob == (repository / name).read_bytes(), "frozen snapshot drift: " + name)
    destination.mkdir(parents=True, exist_ok=False)
    closure.mkdir(parents=True, exist_ok=False)
    for name in entries:
        write_new(destination / name, (raw / name).read_bytes())
    write_new(closure / "raw-manifest.sha256", manifest.read_bytes())
    protocol.historical.save_new(closure / "audit-source.json", checked)
    copied = auditor.audit(repository, destination, closure / "raw-manifest.sha256")
    auditor.require(protocol.same(checked, copied), "copied audit differs")
    protocol.historical.save_new(closure / "audit-archive.json", copied)
    for name, blob in blobs.items():
        write_new(closure / "frozen-snapshot" / name, blob)
    for name in TOOLS:
        write_new(closure / "audit-tools" / name, (repository / name).read_bytes())
    for path in (intent_path, receipt_path, log_path):
        write_new(closure / "operational" / path.name, path.read_bytes())
    write_new(closure / "operational/aws-budget-s16.jsonl", budget.encode())
    protocol.historical.save_new(closure / "provenance.json", {
        "schema_version": 1, "plan_id": protocol.PLAN_ID, "created_at": datetime.now(timezone.utc).isoformat(),
        "frozen_commit": auditor.FROZEN_COMMIT, "raw_files": len(entries),
        "raw_bytes": sum((destination / name).stat().st_size for name in entries),
        "snapshot_sha256": {name: auditor.digest(closure / "frozen-snapshot" / name) for name in blobs},
        "audit_tools_sha256": {name: auditor.digest(repository / name) for name in TOOLS},
        "raw_manifest_sha256": auditor.digest(manifest), "audits_match": True,
        "operational_log_verified": True, "budget_receipts_match_local_journal": True,
        "source_run": str(raw), "archive": protocol.ARCHIVE_PATH,
        "note": "Audit tools, archived copies and provenance are sealed; do not edit after this closure."})
    write_raw_manifest(closure, closure_manifest)
    return verify(repository)


def verify(repository):
    closure = repository / CLOSURE
    provenance = auditor.read(closure / "provenance.json")
    entries = auditor.verify_manifest(repository / protocol.ARCHIVE_PATH, closure / "raw-manifest.sha256")
    closed = auditor.verify_manifest(closure, Path(str(closure) + ".sha256"))
    auditor.require(provenance["frozen_commit"] == auditor.FROZEN_COMMIT and
        provenance["raw_manifest_sha256"] == auditor.digest(closure / "raw-manifest.sha256"), "closure provenance drift")
    for name, expected in provenance["snapshot_sha256"].items():
        auditor.require(auditor.digest(closure / "frozen-snapshot" / name) == expected, "snapshot hash drift")
    for name, expected in provenance["audit_tools_sha256"].items():
        auditor.require(auditor.digest(repository / name) == expected and
            auditor.digest(closure / "audit-tools" / name) == expected, "sealed audit tool drift")
    auditor.require(protocol.same(auditor.read(closure / "audit-source.json"), auditor.read(closure / "audit-archive.json")),
                    "sealed audits differ")
    return {"ok": True, "model_calls": 0, "raw_files": len(entries), "closure_files": len(closed),
        "raw_bytes": provenance["raw_bytes"], "snapshot_files": len(provenance["snapshot_sha256"]),
        "archive": protocol.ARCHIVE_PATH, "closure": CLOSURE}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(ROOT) if args.verify else archive(ROOT), ensure_ascii=False, indent=2))
