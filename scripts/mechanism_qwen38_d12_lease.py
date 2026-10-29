#!/usr/bin/env python3
"""One D12 H200 lease, independently watched; preserves both existing volumes."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.mechanism_qwen38 import write_new, digest, owned_pod, MODEL_REVISION
from creative_machine.mechanism_qwen38_d12 import plan, aggregate
from creative_machine.mechanism_qwen38_d12_deployment import (SOURCE_FILES, validate_snapshot,
    IMAGE, GPU_ID, CLI_VERSION, DC, VOLUME_ID, RUNTIME, MODEL_STORE, BUDGET_USD, MAX_RATE_USD,
    SETUP_SECONDS, DELETE_MARGIN_SECONDS, HEARTBEAT_MAX_AGE, lease, job_deadline,
    validate_resource, verify_recovery)
from mechanism_qwen38_pilot_lease import read, replace_state, publish_once, process_identity

LAUNCH = ROOT / "runs/mechanisms/qwen38-d12-v1-launch.json"
SCRIPT = Path(__file__).resolve()


class ProviderError(RuntimeError):
    def __init__(self, value):
        self.value = value
        super().__init__(value.get("error", "RunPod command failed"))


def api(argv, timeout=45):
    response = subprocess.run(["runpodctl", *argv], capture_output=True, text=True, timeout=timeout)
    if response.returncode:
        errors = []
        for line in response.stderr.splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict) and "error" in value:
                    errors.append(value)
            except json.JSONDecodeError:
                pass
        raise ProviderError(errors[-1] if errors else {"error": response.stderr[-1200:], "code": "unparsed_error"})
    value = json.loads(response.stdout)
    if isinstance(value, dict) and "error" in value:
        raise ProviderError(value)
    return value


@contextmanager
def lock(out, name, blocking=True):
    with (out / name).open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def live_pod(intent, out):
    expected = read(out / "resource.json")["id"] if (out / "resource.json").exists() else None
    returned = out / "create-returned.json"
    if expected is None and returned.exists():
        expected = read(returned).get("id")
    return owned_pod(api(["pod", "list"]), intent["name"], expected)


def connection_for(pod_id):
    info = api(["ssh", "info", pod_id])
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


def deadline_reason(intent, out, now):
    if now >= intent["delete_requested_by_epoch"]:
        return "absolute_lease_deadline"
    if (out / "closing.json").exists():
        return read(out / "closing.json")["reason"]
    if (out / "completed.json").exists():
        return "completed_no_followup_admitted"
    job = out / "job.json"
    if job.exists():
        value = read(job)
        deadline = value["stop_by_epoch"]
        if (not math.isfinite(deadline) or deadline-value["started_epoch"] != plan()["maximum_remote_seconds"]
                or deadline > intent["delete_requested_by_epoch"]):
            raise ValueError("D12 job deadline changed")
    else:
        deadline = intent["created_epoch"] + SETUP_SECONDS
    if now >= deadline:
        return "job_or_setup_deadline"
    heartbeat = out / "heartbeat.json"
    if not heartbeat.exists() or not 0 <= now-read(heartbeat)["at"] <= HEARTBEAT_MAX_AGE:
        return "controller_heartbeat_stale_or_invalid"
    return None


def creation_settle_until(out):
    if not (out / "create-started.json").exists():
        return 0
    if (out / "create-returned.json").exists():
        returned = read(out / "create-returned.json")
        if returned.get("id") or returned.get("definitive_no_create"):
            return 0
    return read(out / "create-started.json")["at"] + 900


def cleanup(intent, out, reason):
    with lock(out, "cleanup.lock", blocking=False) as acquired:
        if not acquired:
            return None
        with lock(out, "state.lock"):
            if not (out / "closing.json").exists():
                publish_once(out / "closing.json", {"at": time.time(), "reason": reason})
        if (out / "released.json").exists() and live_pod(intent, out) is None:
            return read(out / "released.json")
        pod = live_pod(intent, out)
        # An interrupted create can still produce a resource. Never re-create,
        # and do not declare absence until its bounded reconciliation window.
        while pod is None and time.time() < creation_settle_until(out):
            time.sleep(15)
            pod = live_pod(intent, out)
        recovered = {"attempted": False}
        if pod is not None:
            if (out / "completed.json").exists():
                recovered = read(out / "completed.json")["recovery"]
            else:
                try:
                    destination = recover(out, connection_for(pod["id"]), intent["remote_root"])
                    recovered = {"attempted": True, **verify_recovery(destination)}
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                    recovered = {"attempted": True, "manifest_verified": False, "error": str(exc)}
            expected = pod["id"]
            # Record identity even if create failed before its normal response.
            if not (out / "resource.json").exists():
                publish_once(out / "resource.json", {"id": expected, "name": intent["name"], "reconciled_during_cleanup": True})
            for attempt in range(3):
                current = live_pod(intent, out)
                if current is None:
                    break
                if current["id"] != expected:
                    raise ValueError("cleanup identity changed")
                try:
                    api(["pod", "remove", expected])
                except ProviderError:
                    if live_pod(intent, out) is not None:
                        raise
                time.sleep(2**attempt)
        if live_pod(intent, out) is not None:
            raise RuntimeError("D12 removal not confirmed")
        result = {"at": time.time(), "reason": reason, "confirmed_absent": True,
            "pod_id": read(out / "resource.json")["id"] if (out / "resource.json").exists() else None,
            "recovery": recovered, "network_volumes_preserved": [VOLUME_ID, "dioyamohbc"]}
        if not (out / "released.json").exists():
            publish_once(out / "released.json", result)
        return result


def watch(out):
    intent = read(out / "intent.json")
    publish_once(out / "guard-ready.json", {"pid": os.getpid(), "at": time.time(),
        "delete_by_epoch": intent["delete_requested_by_epoch"], "provider_side": False})
    failures = 0
    while True:
        try:
            if (out / "released.json").exists() and live_pod(intent, out) is None:
                return
            try:
                reason = deadline_reason(intent, out, time.time())
            except (OSError, ValueError, KeyError, TypeError):
                reason = "invalid_watchdog_state"
            if reason:
                result = cleanup(intent, out, reason)
                if result is not None:
                    print("D12 GUARD RELEASE " + json.dumps(result), flush=True)
                    return
            replace_state(out / "guard-state.json", {"at": time.time(), "delete_by_epoch": intent["delete_requested_by_epoch"],
                "phase": "closing" if reason else "active"})
            failures = 0
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            failures += 1
            print(f"D12 GUARD failure {failures}: {exc}", flush=True)
            if failures >= 6:
                raise RuntimeError("D12 guard cannot verify state/cleanup; reconcile exact resource") from exc
        time.sleep(15)


def check_sources():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    snapshot = {"commit": commit, "files": {name: digest(ROOT / name) for name in SOURCE_FILES}}
    validate_snapshot(snapshot, ROOT)
    for name, expected in snapshot["files"].items():
        content = subprocess.check_output(["git", "show", "HEAD:"+name], cwd=ROOT)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("uncommitted D12 source: " + name)
    remote = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/main"], cwd=ROOT, text=True, timeout=30).split()
    if not remote or remote[0] != commit:
        raise ValueError("publish D12 sources before allocation")
    return snapshot


def command(argv, log, maximum_seconds, guard, out, cwd=None):
    process = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, close_fds=True)
    started = time.monotonic()
    try:
        while process.poll() is None:
            if guard.poll() is not None or (out / "closing.json").exists():
                raise RuntimeError("D12 watchdog unavailable or cleanup started")
            if time.monotonic()-started > maximum_seconds:
                raise TimeoutError("D12 bounded command expired")
            time.sleep(1)
        if process.returncode:
            raise RuntimeError(f"D12 command failed ({process.returncode}); see execution.log")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=Path)
    args = parser.parse_args()
    if args.watch:
        watch(args.watch.resolve())
        return
    if LAUNCH.exists():
        raise FileExistsError("D12 launch already attempted; never rerun")
    snapshot = check_sources()
    if subprocess.check_output(["runpodctl", "version"], text=True).strip() != "runpodctl " + CLI_VERSION:
        raise ValueError("D12 pinned CLI changed")
    account = api(["user"])
    balance = account.get("clientBalance")
    if (type(balance) not in (int, float) or not math.isfinite(balance) or balance < BUDGET_USD
            or not api(["ssh", "list-keys"]).get("keys")):
        raise ValueError("D12 reserve/registered SSH key unavailable")
    volume = api(["network-volume", "get", VOLUME_ID])
    if volume.get("dataCenterId") != DC or volume.get("size") != 200:
        raise ValueError("D12 preserved volume differs")
    offers = [g for g in api(["gpu", "list", "--include-unavailable"]) if g["gpuId"] == GPU_ID]
    if len(offers) != 1:
        raise ValueError("H200 offer missing")
    lease(offers[0].get("securePricePerHr"))
    stocks = [d for d in offers[0].get("dataCenterAvailability", []) if d["dataCenterId"] == DC]
    if len(stocks) != 1 or stocks[0]["stockStatus"].lower() not in ("low", "medium", "high"):
        raise ValueError("no H200 stock reported in the preserved volume region")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "runs/mechanisms" / ("qwen38-d12-" + stamp)
    out.mkdir(parents=True, exist_ok=False)
    started = time.time()
    intent = {"name": "cm-qwen38-"+stamp.lower(), "created_epoch": started,
        "remote_root": "/workspace/cm-qwen38/qwen38-d12-"+stamp,
        "budget_usd": BUDGET_USD, "max_rate_usd": MAX_RATE_USD, "volume_id": VOLUME_ID, "data_center": DC,
        "absolute_lease_end_epoch": started+lease(MAX_RATE_USD),
        "delete_requested_by_epoch": started+lease(MAX_RATE_USD)-DELETE_MARGIN_SECONDS,
        "guard": "independent local watchdog, not a provider billing cap", "attempts": 1,
        "authorization": "Roberto approved the separate USD54 D12 lease, up to 10h30, in this thread",
        "automatic_model_or_gpu_fallback": False, "automatic_followup": False}
    if owned_pod(api(["pod", "list"]), intent["name"]) is not None:
        raise ValueError("D12 exact name already exists; reconcile without mutation")
    for name, value in (("intent.json", intent), ("snapshot.json", snapshot), ("plan.json", plan()), ("volume.json", volume)):
        write_new(out / name, value)
    publish_once(LAUNCH, {"run_dir": str(out), "name": intent["name"], "snapshot": snapshot})
    replace_state(out / "heartbeat.json", {"at": time.time()})
    done = threading.Event()
    def beat():
        while not done.wait(20):
            replace_state(out / "heartbeat.json", {"at": time.time()})
    thread = threading.Thread(target=beat, daemon=True); thread.start()
    guard = None
    def interrupted(_sig, _frame):
        raise KeyboardInterrupt("D12 interrupted; recover and release exact owned pod")
    signal.signal(signal.SIGTERM, interrupted)
    print("D12_RUN_DIR="+str(out), flush=True)
    try:
        with (out / "guard.log").open("x") as log:
            guard = subprocess.Popen(["caffeinate", "-i", sys.executable, str(SCRIPT), "--watch", str(out)],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
        until = time.monotonic()+10
        while not (out / "guard-ready.json").exists():
            if guard.poll() is not None or time.monotonic() >= until:
                raise RuntimeError("D12 watchdog not ready; no allocation")
            time.sleep(.1)
        ready = read(out / "guard-ready.json")
        observed = process_identity(ready["pid"])
        if (guard.poll() is not None or ready["delete_by_epoch"] != intent["delete_requested_by_epoch"]
                or observed is None or not observed["command"].endswith(str(SCRIPT)+" --watch "+str(out))):
            raise ValueError("D12 guard identity/deadline mismatch")
        write_new(out / "guard-identity.json", observed)
        with lock(out, "state.lock"):
            if (out / "closing.json").exists():
                raise RuntimeError("D12 already closing")
            publish_once(out / "create-started.json", {"at": time.time(), "name": intent["name"]})
        try:
            created = api(["pod", "create", "--name", intent["name"], "--image", IMAGE,
                "--gpu-id", GPU_ID, "--gpu-count", "1", "--cloud-type", "SECURE",
                "--container-disk-in-gb", "30", "--network-volume-id", VOLUME_ID,
                "--volume-mount-path", "/workspace", "--data-center-ids", DC, "--ports", "22/tcp",
                "--min-cuda-version", "12.8", "--wait", "--wait-timeout", "10m"], timeout=700)
            publish_once(out / "create-returned.json", {"at": time.time(), "id": created["id"]})
        except ProviderError as exc:
            publish_once(out / "create-returned.json", {"at": time.time(), **exc.value,
                "definitive_no_create": exc.value.get("code") in ("usage_error", "bad_request", "no_credentials", "unauthorized", "forbidden")})
            raise
        resource = api(["pod", "get", created["id"], "--include-network-volume"])
        validate_resource(resource, intent)
        publish_once(out / "resource.json", {"id": resource["id"], "name": intent["name"],
            "cost_per_hour": resource["costPerHr"], "volume_id": VOLUME_ID, "data_center": DC, "image": IMAGE})
        if live_pod(intent, out) is None:
            raise ValueError("D12 resource disappeared")
        connection = connection_for(resource["id"])
        remote, code = intent["remote_root"], intent["remote_root"]+"/repo"
        print(f"D12_POD={resource['id']} rate={resource['costPerHr']}", flush=True)
        with (out / "execution.log").open("x") as log:
            def remote_command(text, seconds):
                command([*connection, text], log, seconds, guard, out)
            remote_command("mkdir "+shlex.quote(remote)+" && mkdir "+shlex.quote(code), 30)
            command(["rsync", "-rltzR", "-e", shlex.join(connection[:-1]), *SOURCE_FILES,
                connection[-1]+":"+code+"/"], log, 180, guard, out, cwd=ROOT)
            command(["rsync", "-rltz", "-e", shlex.join(connection[:-1]), str(out / "snapshot.json"),
                connection[-1]+":"+remote+"/snapshot.json"], log, 30, guard, out)
            # Reuse the pinned volume runtime; no installation, weights download,
            # or accidental mutation of earlier evidence/runtime directories.
            remote_command(f"set -eu; test -x {RUNTIME}/bin/python; test -d {MODEL_STORE}/snapshots/{MODEL_REVISION}; "
                f"cd {code}; PYTHONPATH=src {RUNTIME}/bin/python -m pytest -q "
                "tests/test_mechanism_qwen38_d12.py tests/test_mechanism_qwen38_d12_execution.py tests/test_mechanism_qwen38_d12_lease.py", 300)
            job_started = time.time()
            stop_by = job_deadline(intent, job_started)
            with lock(out, "state.lock"):
                if (out / "closing.json").exists() or guard.poll() is not None:
                    raise RuntimeError("D12 lease not active for task admission")
                publish_once(out / "job.json", {"started_epoch": job_started, "stop_by_epoch": stop_by, "snapshot": snapshot})
            print("D12 PHASE: isolated admission then twelve fixed sessions", flush=True)
            remote_command(f"set -eu; cd {code}; export PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1; "
                f"timeout --signal=TERM --kill-after=30s {plan()['maximum_remote_seconds']} "
                f"{RUNTIME}/bin/python -u scripts/mechanism_run_qwen38_d12.py --snapshot {remote}/snapshot.json "
                f"--out {remote}/evidence --runtime {RUNTIME} --model-store {MODEL_STORE} --stop-by-epoch {stop_by}",
                plan()["maximum_remote_seconds"]+60)
        destination = recover(out, connection, remote)
        recovery = {"attempted": True, **verify_recovery(destination)}
        rows = [read(destination / (c["id"]+".json")) for c in plan()["cells"]]
        result = aggregate(rows)
        if read(destination / "result.json") != result or (destination / "failure.json").exists():
            raise ValueError("D12 recovered result mismatch")
        publish_once(out / "completed.json", {"at": time.time(), "result": result, "recovery": recovery,
            "next_step": "independent_offline_audit_no_automatic_followup"})
        print("D12 COMPLETE " + result["next_step"], flush=True)
    except BaseException as exc:
        publish_once(out / "controller-failure.json", {"at": time.time(), "type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        try:
            for attempt in range(6):
                try:
                    result = cleanup(intent, out, "completed_no_followup_admitted" if (out / "completed.json").exists() else "controller_failed")
                    if result is not None:
                        print("D12 RELEASE " + json.dumps(result), flush=True)
                        break
                except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                    print(f"D12 cleanup failure {attempt+1}: {exc}", flush=True)
                time.sleep(15)
            else:
                raise RuntimeError("D12 release not verified; exact resource needs reconciliation")
        finally:
            done.set(); thread.join(timeout=2)


if __name__ == "__main__":
    main()
