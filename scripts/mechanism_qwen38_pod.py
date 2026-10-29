#!/usr/bin/env python3
"""One bounded H200 preflight lease; no old retention signals or scientific launch."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/creative_machine"))
from mechanism_qwen38 import (MODEL_ID, MODEL_REVISION, IMAGE, CLI_VERSION, GPU_ID,
    SOURCE_FILES, MAX_RATE_USD, MAX_BUDGET_USD, lease_seconds, owned_pod,
    write_new, digest, plan)

LAUNCH = ROOT / "runs/mechanisms/qwen38-preflight-v1-launch.json"
VOLUME_NAME = "cm-qwen38-eu-fr-1-v1"
DC = "EU-FR-1"


def api(argv, timeout=45):
    result = subprocess.run(["runpodctl", *argv], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"RunPod {argv[:2]}: {result.stderr[-1200:]}")
    return json.loads(result.stdout)


def remove_owned(intent, out, reason):
    """Idempotent API deletion; never signal unrelated or reused process IDs."""
    expected = None
    if (out / "resource.json").exists():
        expected = json.loads((out / "resource.json").read_text())["id"]
    for attempt in range(3):
        pod = owned_pod(api(["pod", "list"]), intent["name"], expected)
        if pod is None:
            return {"confirmed_absent": True, "pod_id": expected, "reason": reason}
        expected = pod["id"]
        try:
            api(["pod", "remove", expected])
        except RuntimeError:
            # A concurrent cleanup may already have removed this same exact pod.
            if owned_pod(api(["pod", "list"]), intent["name"], expected) is not None:
                raise
        time.sleep(2 ** attempt)
    if owned_pod(api(["pod", "list"]), intent["name"], expected) is not None:
        raise RuntimeError("owned pod removal not confirmed")
    return {"confirmed_absent": True, "pod_id": expected, "reason": reason}


def watchdog_deadline(intent, out):
    deadline = intent["delete_requested_by_epoch"]
    completed = out / "preflight-completed.json"
    if completed.exists():
        deadline = min(deadline, json.loads(completed.read_text())["completed_epoch"] + 7200)
    # A later job requires an explicit, bounded, separately published admission.
    # This preflight-only version has no queue or automatic follow-up launcher.
    return deadline


def watch(out):
    intent = json.loads((out / "intent.json").read_text())
    write_new(out / "watchdog-started.json", {"pid": os.getpid(), "started_epoch": time.time(),
        "provider_side": False, "depends_on_local_mac_and_network": True})
    while True:
        if (out / "released.json").exists():
            absent = owned_pod(api(["pod", "list"]), intent["name"],
                json.loads((out / "released.json").read_text()).get("pod_id")) is None
            if absent:
                print("WATCHDOG: release confirmed", flush=True)
                return
        now = time.time()
        if now >= watchdog_deadline(intent, out):
            print("WATCHDOG: bounded lease/idle deadline, removing exact owned pod", flush=True)
            for attempt in range(6):
                try:
                    result = remove_owned(intent, out, "watchdog_deadline")
                    write_new(out / "watchdog-cleanup.json", {**result, "finished_epoch": time.time()})
                    return
                except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
                    print(f"WATCHDOG cleanup attempt {attempt+1}: {exc}", flush=True)
                    time.sleep(min(30, 2 ** attempt))
            raise RuntimeError("watchdog could not verify cleanup; external state reconciliation required")
        print(json.dumps({"at": now, "deadline": watchdog_deadline(intent, out), "state": "watching"}), flush=True)
        time.sleep(30)


def check_sources():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = {}
    for name in SOURCE_FILES:
        path = ROOT / name
        if path.is_symlink():
            raise ValueError("source symlink is not admitted")
        committed = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != digest(path):
            raise ValueError("commit new preflight sources before launch: " + name)
        files[name] = digest(path)
    published = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/main"], cwd=ROOT, text=True, timeout=30).split()
    if not published or published[0] != commit:
        raise ValueError("publish the prospective snapshot before allocation")
    return {"commit": commit, "files": files}


def connection_for(pod_id):
    info = api(["ssh", "info", pod_id])
    if "error" in info:
        raise RuntimeError(info["error"])
    return ["ssh", "-i", info["ssh_key"]["path"], "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
        "-p", str(info["port"]), "root@" + info["ip"]]


def recover(out, connection, remote):
    destination = out / "recovered"
    destination.mkdir(exist_ok=True)
    subprocess.run(["rsync", "-rltz", "-e", shlex.join(connection[:-1]),
        connection[-1] + ":" + remote + "/evidence/", str(destination) + "/"],
        check=True, timeout=180)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=Path)
    args = parser.parse_args()
    if args.watch:
        watch(args.watch.resolve())
        return
    if LAUNCH.exists():
        raise RuntimeError("this preflight already attempted; reconcile its marker, do not allocate again")
    snapshot = check_sources()
    if CLI_VERSION not in subprocess.check_output(["runpodctl", "version"], text=True):
        raise ValueError("CLI changed after inspection")
    account = api(["user"])
    if not isinstance(account.get("clientBalance"), (int, float)) or account["clientBalance"] < MAX_BUDGET_USD:
        raise ValueError("insufficient verified balance for the agreed reserve")
    keys = api(["ssh", "list-keys"])
    if not keys.get("keys"):
        raise ValueError("SSH key must be registered before provisioning")
    offer = [g for g in api(["gpu", "list", "--include-unavailable"]) if g["gpuId"] == GPU_ID]
    if len(offer) != 1 or not 0 < offer[0]["securePricePerHr"] <= MAX_RATE_USD:
        raise ValueError("H200 price outside preflight envelope")
    stock = [d for d in offer[0].get("dataCenterAvailability", []) if d["dataCenterId"] == DC]
    if not stock or stock[0]["stockStatus"].lower() not in ("low", "medium", "high"):
        raise ValueError("H200 stock not reported in chosen volume region")
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "runs/mechanisms" / ("qwen38-preflight-" + suffix)
    out.mkdir(parents=True, exist_ok=False)
    started = time.time()
    intent = {"name": "cm-qwen38-" + suffix.lower(), "created_epoch": started,
        "remote_root": "/workspace/cm-qwen38/" + suffix,
        "max_rate_usd": MAX_RATE_USD, "budget_usd": MAX_BUDGET_USD,
        "absolute_lease_end_epoch": started + lease_seconds(MAX_RATE_USD),
        "delete_requested_by_epoch": started + lease_seconds(MAX_RATE_USD) - 600,
        "cleanup_reserve_seconds": 600, "max_idle_seconds_after_preflight": 7200,
        "data_center": DC, "new_volume_name": VOLUME_NAME,
        "guard": "independent local watchdog; not a provider-enforced billing cap",
        "attempts": 1, "automatic_model_or_gpu_fallback": False}
    write_new(out / "intent.json", intent)
    write_new(out / "snapshot.json", snapshot)
    write_new(out / "plan.json", plan())
    write_new(LAUNCH, {"run_dir": str(out), "name": intent["name"], "snapshot": snapshot})
    with (out / "watchdog.log").open("x") as log:
        guard = subprocess.Popen(["caffeinate", "-i", sys.executable, str(Path(__file__).resolve()),
            "--watch", str(out)], stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    write_new(out / "watchdog-process.json", {"pid": guard.pid})
    deadline = time.monotonic() + 10
    while not (out / "watchdog-started.json").exists():
        if guard.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError("watchdog did not become ready; no paid resources allocated")
        time.sleep(0.1)
    pod_id, connection = None, None
    remote = intent["remote_root"]
    success = False
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("interrupted; preserve evidence and remove owned pod")
    signal.signal(signal.SIGTERM, interrupted)
    print("QWEN38_RUN_DIR=" + str(out), flush=True)
    try:
        volumes = [v for v in api(["network-volume", "list"]) if v["name"] == VOLUME_NAME]
        if volumes:
            raise ValueError("same-name volume already exists without this admission; reconcile before reuse")
        volume = api(["network-volume", "create", "--name", VOLUME_NAME, "--size", "200", "--data-center-id", DC])
        if volume.get("dataCenterId") != DC or volume.get("size") != 200:
            raise ValueError("created volume differs from the scoped request")
        write_new(out / "volume.json", volume)
        resource = api(["pod", "create", "--name", intent["name"], "--image", IMAGE,
            "--gpu-id", GPU_ID, "--gpu-count", "1", "--cloud-type", "SECURE",
            "--container-disk-in-gb", "30", "--network-volume-id", volume["id"],
            "--data-center-ids", DC, "--ports", "22/tcp", "--min-cuda-version", "12.8",
            "--wait", "--wait-timeout", "10m"], timeout=700)
        pod_id = resource["id"]
        resolved = owned_pod(api(["pod", "list"]), intent["name"], pod_id)
        if resolved is None:
            raise ValueError("created resource not found by exact identity")
        rate = resource.get("costPerHr")
        lease_seconds(rate)
        write_new(out / "resource.json", {"id": pod_id, "name": intent["name"],
            "volume_id": volume["id"], "data_center": DC, "gpu": GPU_ID, "image": IMAGE,
            "cost_per_hour": rate, "remote_root": remote})
        connection = connection_for(pod_id)
        print(f"QWEN38_POD={pod_id} rate_usd_per_hour={rate}", flush=True)
        with (out / "execution.log").open("x") as log:
            def remote_command(command, timeout):
                result = subprocess.run([*connection, command], stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                if result.returncode:
                    raise RuntimeError(f"remote phase failed ({result.returncode}); inspect execution.log")
            remote_command("mkdir -p " + shlex.quote(remote), 30)
            subprocess.run(["rsync", "-rltzR", "-e", shlex.join(connection[:-1]),
                *SOURCE_FILES, connection[-1] + ":" + remote + "/"], cwd=ROOT,
                stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
            print("PHASE: environment", flush=True)
            remote_command(f"set -eu; cd {remote}; export UV_CACHE_DIR=/workspace/uv-cache; "
                "uv venv --system-site-packages .venv; "
                "uv pip install --python .venv/bin/python -r docs/mechanisms/requirements-m0.txt; "
                "PYTHONPATH=src .venv/bin/python -m pytest tests/test_mechanism_qwen38.py -q; "
                ".venv/bin/python -m pip freeze", 900)
            print("PHASE: pinned checkpoint download", flush=True)
            download = ("from huggingface_hub import snapshot_download; "
                f"print(snapshot_download({MODEL_ID!r},revision={MODEL_REVISION!r},"
                "cache_dir='/workspace/hf-cache/hub',allow_patterns=['*.json','*.jinja','*.safetensors','*.txt']),flush=True)")
            remote_command(f"set -eu; cd {remote}; "
                "export HF_HOME=/workspace/hf-cache HF_HUB_DOWNLOAD_TIMEOUT=60 HF_HUB_DISABLE_XET=1; "
                ".venv/bin/python -u -c " + shlex.quote(download), 3600)
            print("PHASE: numerical/runtime/transport probe", flush=True)
            remote_command(f"set -eu; cd {remote}; "
                "export PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1; "
                "timeout --signal=TERM --kill-after=30s 4800 .venv/bin/python scripts/mechanism_qwen38_probe.py "
                "--model-store /workspace/hf-cache/hub/models--Qwen--Qwen3.8-27B --out evidence", 4900)
        recovered = recover(out, connection, remote)
        report = json.loads((recovered / "result.json").read_text())
        if not report["runtime_preflight_passed"]:
            raise RuntimeError("preflight returned a failed gate; no task launch")
        write_new(out / "preflight-completed.json", {"completed_epoch": time.time(), "pod_id": pod_id,
            "recovered": str(recovered), "report": report,
            "next_step": "separate pilot design and admission before using this lease"})
        success = True
        print("PREFLIGHT READY; exact pod retained for at most two idle hours inside the original budget", flush=True)
    except BaseException as exc:
        write_new(out / "controller-failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        if not success:
            if connection is not None:
                try:
                    recover(out, connection, remote)
                except (OSError, subprocess.SubprocessError) as exc:
                    write_new(out / "recovery-failure.json", {"type": type(exc).__name__, "message": str(exc)})
            released = remove_owned(intent, out, "preflight_controller_failed")
            write_new(out / "released.json", {**released, "finished_epoch": time.time(), "network_volume_preserved": True})


if __name__ == "__main__":
    main()
