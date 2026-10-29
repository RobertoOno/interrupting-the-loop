#!/usr/bin/env python3
"""One frozen M1-U pilot; isolate every cell, recover evidence, remove only its pod."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.mechanism_use import PLAN_PATH, validate
from creative_machine.mechanism_use_deployment import SNAPSHOT_FILES, validate_snapshot, IMAGE, REMOTE_LIMIT_SECONDS
from creative_machine.mechanism_pilot import file_sha256, write_json_new
from mechanism_archive_use_preflight import validate_closed

ADMISSION_PATH = "runs/mechanisms/m1-use-v1-admission-attempt3.json"
ARCHIVE_PATH = "docs/mechanisms/m1_use_evidence_v1/result.json"
CLI_VERSION = "2.12.0-51ca7f0"


def prepare_snapshot(root):
    """No cloud calls before replay/plan/source checks, including in a clone."""
    if (root / ADMISSION_PATH).exists() or (root / ARCHIVE_PATH).exists():
        raise RuntimeError("M1-U already admitted or archived; reconcile, do not repeat")
    previous = validate_closed(root / "docs/mechanisms/m1_use_deployment_failure_v1")
    if previous["failed_snapshot"] != "6efc9d984076f864c65c3f1365872dc89e92fb6a" or previous["task_sessions_started"] != 0:
        raise RuntimeError("prior preflight has not been reconciled as zero-task")
    second = validate_closed(root / "docs/mechanisms/m1_use_deployment_failure_v2")
    if second["failed_snapshot"] != "4f38cad64c616ec3cea0eaadbc065b0140501a93" or second["task_sessions_started"] != 0:
        raise RuntimeError("second preflight has not been reconciled as zero-task")
    for version in (1,2):
        archive = root / f"docs/mechanisms/m1_cuda_isolation_diagnostic_v{version}"
        record = json.loads((archive / "reconciliation.json").read_text())
        if not record["closed"] or record["task_sessions_started"] != 0 or record["model_weights_loaded"] is not False:
            raise ValueError("diagnostic not reconciled")
        from mechanism_archive_use_preflight import catalog
        if {k:v for k,v in catalog(archive).items() if k != "archive_manifest.json"} != json.loads((archive / "archive_manifest.json").read_text()):
            raise ValueError("diagnostic archive changed")
    plan = json.loads((root / PLAN_PATH).read_text())
    validate(plan)
    hashes = {}
    for name in SNAPSHOT_FILES:
        if (root / name).is_symlink():
            raise ValueError(f"snapshot source is a symlink: {name}")
        digest = file_sha256(root / name)
        committed = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=root)
        if hashlib.sha256(committed).hexdigest() != digest:
            raise ValueError(f"commit source before M1-U: {name}")
        hashes[name] = digest
    snapshot = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "files": hashes}
    validate_snapshot(snapshot, root)
    return plan, snapshot


def run_json(argv, timeout=60):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{argv[:3]}: {result.stderr[-1500:]}")
    return json.loads(result.stdout)


def main():
    plan, snapshot = prepare_snapshot(ROOT)
    cli = subprocess.check_output(["runpodctl", "version"], text=True).strip()
    if CLI_VERSION not in cli:
        raise RuntimeError("RunPod CLI changed after preflight")
    run_json(["runpodctl", "user"])  # Authentication only; no balance in logs.
    volumes = run_json(["runpodctl", "network-volume", "list"])
    matches = [v for v in volumes if v["id"] == "dioyamohbc" and v["name"] == "cm-vol" and v["dataCenterId"] == "EU-RO-1"]
    if len(matches) != 1:
        raise RuntimeError("existing cm-vol placement not confirmed")
    volume = matches[0]
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"cm-m1-use-{suffix.lower()}"
    out = ROOT / "runs/mechanisms" / f"m1-use-{suffix}"
    out.mkdir(parents=True, exist_ok=False)
    remote = f"/workspace/cm-mechanisms/m1-use-{suffix}"
    write_json_new(out / "snapshot.json", snapshot)
    write_json_new(out / "intent.json", {"name": name, "remote_root": remote, "volume_id": volume["id"], "cli_version": cli})
    log_path = out / "execution.log"
    pod_id, connection = None, None
    started = time.monotonic()
    remote_success = False
    recovered, removed, ownership_resolved = False, False, False
    cleanup_errors = []

    def interrupted(_signal, _frame):
        raise KeyboardInterrupt("interrupted; recover evidence and remove owned pod")
    signal.signal(signal.SIGTERM, interrupted)

    def remote_command(command, log, timeout):
        result = subprocess.run([*connection, command], stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise RuntimeError(f"remote phase failed ({result.returncode}); see {log_path}")

    print(f"M1-U_RUN_DIR={out}", flush=True)
    try:
        resource = run_json([
            "runpodctl", "pod", "create", "--name", name, "--image", IMAGE,
            "--gpu-id", plan["gpu"], "--gpu-count", "1", "--cloud-type", "SECURE",
            "--container-disk-in-gb", "30", "--network-volume-id", volume["id"],
            "--data-center-ids", volume["dataCenterId"], "--ports", "22/tcp",
            "--wait", "--wait-timeout", "5m",
        ], timeout=400)
        pod_id = resource["id"]
        if not re.fullmatch(r"[a-z0-9]+", pod_id):
            pod_id = None
            raise RuntimeError("invalid pod ID; reconcile by unique name")
        ownership_resolved = True
        write_json_new(out / "resource.json", {
            "id": pod_id, "name": name, "remote_root": remote, "volume_id": volume["id"],
            "created_at": datetime.now(timezone.utc).isoformat(), "cli_version": cli,
            "image": IMAGE, "gpu": plan["gpu"],
        })
        print(f"M1-U_POD={pod_id}", flush=True)
        info = run_json(["runpodctl", "ssh", "info", pod_id], timeout=30)
        connection = ["ssh", "-i", info["ssh_key"]["path"], "-o", "BatchMode=yes",
                      "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10",
                      "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
                      "-p", str(info["port"]), f"root@{info['ip']}"]
        with log_path.open("x") as log:
            remote_command("nvidia-smi -L", log, 30)
            # Fresh run root on the existing volume; never edit another checkout.
            remote_command(f"mkdir -p /workspace/cm-mechanisms; mkdir {remote}", log, 30)
            directories = sorted({str(Path(remote) / Path(n).parent) for n in SNAPSHOT_FILES})
            remote_command("mkdir -p " + shlex.join(directories), log, 30)
            transport, host = shlex.join(connection[:-1]), connection[-1]
            for source in [*SNAPSHOT_FILES, "snapshot.json"]:
                local = out / source if source == "snapshot.json" else ROOT / source
                subprocess.run(["rsync", "-rltz", "-e", transport, str(local), f"{host}:{remote}/{source}"],
                               check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90)
            print("M1-U PHASE: isolated environment and offline tests", flush=True)
            remote_command(
                f"set -eu; cd {remote}; export UV_CACHE_DIR=/workspace/uv-cache; "
                "uv venv --system-site-packages .venv; "
                "uv pip install --python .venv/bin/python -r docs/mechanisms/requirements-m0.txt; "
                "PYTHONPATH=src .venv/bin/python -m pytest tests/test_mechanism_actions.py tests/test_mechanism_use.py tests/test_mechanism_use_deployment.py -q; "
                ".venv/bin/python -m pip freeze", log, 600)
            # Exclusive admission immediately before remote tokenizer/weights.
            write_json_new(ROOT / ADMISSION_PATH, {
                "run_dir": str(out), "pod_id": pod_id, "snapshot": snapshot,
                "status": "submitted_for_kernel_gpu_preflight_and_prospective_pilot",
            })
            print("M1-U PHASE: Linux/CUDA preflight and prospective oracle pilot", flush=True)
            remote_command(
                f"set -eu; cd {remote}; "
                "export HF_HOME=/workspace/hf-cache HF_HUB_DOWNLOAD_TIMEOUT=60 "
                "HF_HUB_DISABLE_XET=1 PYTHONUNBUFFERED=1; "
                ".venv/bin/python scripts/mechanism_run_use.py --snapshot snapshot.json --out evidence "
                f"--runtime {remote}/.venv --model-store /workspace/hf-cache/hub/models--Qwen--Qwen3.5-4B", log, REMOTE_LIMIT_SECONDS)
            remote_success = True  # Numerical gates can still fail.
    except BaseException as exc:
        write_json_new(out / "failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        # CLI timeout may occur after creation. Never create a second pod here.
        if pod_id is None:
            try:
                owned = [p for p in run_json(["runpodctl", "pod", "list"]) if p.get("name") == name]
                if len(owned) > 1:
                    raise RuntimeError("ambiguous unique-name ownership; manual reconciliation required")
                pod_id = owned[0]["id"] if owned else None
                ownership_resolved = True
            except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
                cleanup_errors.append(f"ownership: {exc}")
        if connection is not None:
            try:
                subprocess.run(["rsync", "-rltz", "-e", shlex.join(connection[:-1]),
                                f"{connection[-1]}:{remote}/evidence/", str(out / "evidence") + "/"],
                               check=True, timeout=180)
                recovered = True
            except (subprocess.SubprocessError, OSError) as exc:
                cleanup_errors.append(f"recovery: {exc}; persistent path {remote}")
        if pod_id is not None:
            for attempt in range(3):
                try:
                    pods = run_json(["runpodctl", "pod", "list"])
                    if any(p["id"] == pod_id for p in pods):
                        run_json(["runpodctl", "pod", "remove", pod_id])
                    removed = not any(p["id"] == pod_id for p in run_json(["runpodctl", "pod", "list"]))
                    if removed:
                        break
                except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
                    cleanup_errors.append(f"removal attempt {attempt+1}: {exc}")
                time.sleep(2 ** attempt)
        write_json_new(out / "lifecycle.json", {
            "pod_id": pod_id, "pod_removed": removed, "ownership_resolved": ownership_resolved,
            "evidence_recovered": recovered, "remote_exit_success": remote_success,
            "elapsed_seconds": time.monotonic() - started, "cleanup_errors": cleanup_errors,
            "persistent_volume_preserved": volume["id"],
        })
        print(f"M1-U FINISHED: remote_success={remote_success}, evidence_recovered={recovered}, pod_removed={removed}", flush=True)
        if not ownership_resolved or (pod_id is not None and not removed):
            raise RuntimeError(f"pod lifecycle unresolved for {name}; inspect lifecycle before continuing")
        if remote_success and not recovered:
            raise RuntimeError(f"measurement completed but recovery incomplete: {remote}/evidence")


if __name__ == "__main__":
    main()
