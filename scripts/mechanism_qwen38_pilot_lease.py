#!/usr/bin/env python3
"""Admit Q38-12 on the existing H200 lease; never create paid resources."""

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
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.mechanism_qwen38 import write_new, digest, owned_pod, lease_seconds
from creative_machine.mechanism_qwen38_pilot import plan
from creative_machine.mechanism_qwen38_deployment import SOURCE_FILES, validate_snapshot
from mechanism_qwen38_pod import api, connection_for, remove_owned, recover

PREVIOUS = ROOT / "runs/mechanisms/qwen38-preflight-20260907T102647Z"
LAUNCH = ROOT / "runs/mechanisms/qwen38-pilot-v1-launch.json"
POD_ID = "j523fcxcu3d1cw"
HEARTBEAT_MAX_AGE = 180


def read(path):
    return json.loads(Path(path).read_text())


def replace_state(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    write_new(temporary, value)
    os.replace(temporary, path)


def publish_once(path, value):
    """Atomic appearance AND exclusive creation for files observed by the guard."""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    write_new(temporary, value)
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def process_identity(pid):
    if type(pid) is not int or pid <= 1:
        raise ValueError("unsafe process identifier")
    result = subprocess.run(["ps", "-p", str(pid), "-o", "pid=,ppid=,lstart=,command="],
        capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"}, timeout=10)
    if result.returncode == 1 and not result.stdout.strip():
        return None
    if result.returncode:
        raise RuntimeError("cannot inspect watchdog identity")
    fields = result.stdout.strip().split(None, 7)
    if len(fields) != 8 or int(fields[0]) != pid:
        raise ValueError("unrecognized process identity")
    return {"pid": pid, "ppid": int(fields[1]), "started": " ".join(fields[2:7]), "command": fields[7]}


def stop_prior_guard(expected, expected_suffix):
    if not expected["command"].endswith(expected_suffix):
        raise ValueError("not the exact owned preflight watchdog")
    current = process_identity(expected["pid"])
    if current is None:
        return {"already_exited": True, "signal_sent": False}
    if current != expected:
        raise ValueError("watchdog identity changed; refusing signal")
    try:
        os.kill(expected["pid"], signal.SIGTERM)
    except ProcessLookupError:
        return {"already_exited": True, "signal_sent": False}
    # Never send a second signal if the old PID disappears or is reused.
    for _ in range(50):
        observed = process_identity(expected["pid"])
        if observed is None or observed != expected:
            return {"already_exited": False, "signal_sent": True, "original_identity_absent": True}
        time.sleep(0.1)
    raise RuntimeError("old watchdog did not exit; do not start pilot under conflicting deadlines")


def validate_guard_ready(ready, guard, deadline, expected_suffix):
    if guard.poll() is not None or ready["inherited_delete_by_epoch"] != deadline:
        raise ValueError("new watchdog exited or changed original deadline")
    observed = process_identity(ready["pid"])
    if observed is None or not observed["command"].endswith(expected_suffix):
        raise ValueError("new watchdog readiness has no matching live process")
    return observed


def deadline_reason(config, out, now):
    hard = config["inherited_delete_by_epoch"]
    if now >= hard:
        return "original_lease_deadline"
    completed = out / "completed.json"
    if completed.exists():
        return "idle_deadline" if now >= min(hard, read(completed)["at"] + 7200) else None
    job = out / "job.json"
    if now >= (read(job)["stop_by_epoch"] if job.exists() else config["created_epoch"] + 900):
        return "job_or_setup_deadline"
    heartbeat = out / "heartbeat.json"
    if not heartbeat.exists() or now - read(heartbeat)["at"] > HEARTBEAT_MAX_AGE:
        return "controller_heartbeat_stale"
    return None


def cleanup(config, out, reason):
    if (out / "released.json").exists():
        released = read(out / "released.json")
        if owned_pod(api(["pod", "list"]), config["pod_name"], POD_ID) is None:
            return released
    recovery = {"attempted": False}
    try:
        if owned_pod(api(["pod", "list"]), config["pod_name"], POD_ID) is not None:
            recover(out, connection_for(POD_ID), config["remote_root"])
            recovery = {"attempted": True, "recovered": True}
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        recovery = {"attempted": True, "recovered": False, "error": str(exc)}
    result = remove_owned(read(out / "inherited-intent.json"), out, reason)
    result.update({"at": time.time(), "recovery": recovery, "network_volumes_preserved": True})
    try:
        publish_once(out / "released.json", result)
    except FileExistsError:
        pass
    return result


def watch(out):
    config = read(out / "config.json")
    publish_once(out / "guard-ready.json", {"pid": os.getpid(), "at": time.time(),
        "inherited_delete_by_epoch": config["inherited_delete_by_epoch"], "provider_side": False})
    while True:
        if (out / "released.json").exists():
            if owned_pod(api(["pod", "list"]), config["pod_name"], POD_ID) is None:
                return
        try:
            reason = deadline_reason(config, out, time.time())
        except (OSError, ValueError, KeyError, TypeError):
            reason = "invalid_watchdog_state"
        if reason:
            print("Q38 GUARD CLEANUP " + reason, flush=True)
            for attempt in range(6):
                try:
                    result = cleanup(config, out, reason)
                    print(json.dumps(result), flush=True)
                    return
                except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                    print(f"cleanup attempt {attempt+1}: {exc}", flush=True)
                    time.sleep(min(30, 2**attempt))
            raise RuntimeError("cleanup not verified; reconcile exact H200 resource")
        replace_state(out / "guard-state.json", {"at": time.time(), "phase": "idle" if (out / "completed.json").exists() else "active",
            "inherited_delete_by_epoch": config["inherited_delete_by_epoch"]})
        time.sleep(15)


def check_sources():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = {}
    for name in SOURCE_FILES:
        original = subprocess.check_output(["git", "show", "HEAD:"+name], cwd=ROOT)
        files[name] = digest(ROOT / name)
        if hashlib.sha256(original).hexdigest() != files[name]:
            raise ValueError("uncommitted pilot source: " + name)
    remote = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/main"], cwd=ROOT, text=True, timeout=30).split()
    if not remote or remote[0] != commit:
        raise ValueError("publish prospective sources before admission")
    snapshot = {"commit": commit, "files": files}
    validate_snapshot(snapshot, ROOT)
    return snapshot


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--watch", type=Path)
    args = p.parse_args()
    if args.watch:
        watch(args.watch.resolve())
        return
    if LAUNCH.exists():
        raise ValueError("pilot already attempted; never rerun the launcher")
    snapshot = check_sources()
    if "2.12.0-51ca7f0" not in subprocess.check_output(["runpodctl", "version"], text=True):
        raise ValueError("CLI differs from pinned lease")
    original = read(PREVIOUS / "intent.json")
    resource = read(PREVIOUS / "resource.json")
    previous = read(PREVIOUS / "preflight-completed.json")
    now = time.time()
    if (resource["id"] != POD_ID or not previous["report"]["runtime_preflight_passed"]
            or now >= previous["completed_epoch"] + 7200 - 180
            or original["delete_requested_by_epoch"] - now < plan()["maximum_remote_seconds"] + 900):
        raise ValueError("preflight/remaining original lease does not admit this complete pilot")
    live = owned_pod(api(["pod", "list"]), original["name"], POD_ID)
    if live is None or live.get("runtimeStatus") != "running" or live.get("gpuCount") != 1:
        raise ValueError("original H200 not available; no reallocation authorized here")
    lease_seconds(live["costPerHr"])
    account = api(["user"])
    remaining = max(0, 60 - (now-original["created_epoch"])*4.8/3600)
    if account.get("clientBalance", -1) < remaining:
        raise ValueError("balance does not cover remaining original reserve")
    old_pid = read(PREVIOUS / "watchdog-started.json")["pid"]
    old_identity = process_identity(old_pid)
    suffix = str(ROOT / "scripts/mechanism_qwen38_pod.py") + " --watch " + str(PREVIOUS)
    if old_identity is None or not old_identity["command"].endswith(suffix):
        raise ValueError("prior watchdog must be reconciled before handoff")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "runs/mechanisms" / ("qwen38-pilot-" + stamp)
    out.mkdir(parents=True, exist_ok=False)
    config = {"created_epoch": time.time(), "pod_id": POD_ID, "pod_name": original["name"],
        "inherited_delete_by_epoch": original["delete_requested_by_epoch"],
        "inherited_absolute_end_epoch": original["absolute_lease_end_epoch"], "budget_usd": 60,
        "remote_root": "/workspace/cm-qwen38/qwen38-pilot-" + stamp,
        "original_preflight": str(PREVIOUS), "prior_guard_identity": old_identity,
        "no_reallocation": True, "no_original_deadline_extension": True}
    for name, value in (("config.json", config), ("snapshot.json", snapshot),
            ("inherited-intent.json", original), ("resource.json", resource)):
        write_new(out / name, value)
    write_new(LAUNCH, {"run_dir": str(out), "snapshot": snapshot, "pod_id": POD_ID})
    replace_state(out / "heartbeat.json", {"at": time.time()})
    done = threading.Event()
    def beat():
        while not done.wait(20):
            replace_state(out / "heartbeat.json", {"at": time.time()})
    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    with (out / "guard.log").open("x") as log:
        guard = subprocess.Popen(["caffeinate", "-i", sys.executable, str(Path(__file__).resolve()), "--watch", str(out)],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    print("Q38_PILOT_RUN_DIR="+str(out), flush=True)
    success, connection = False, None
    def interrupted(_sig, _frame):
        raise KeyboardInterrupt("interrupted Q38 pilot; recover and release exact pod")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        until = time.monotonic() + 10
        while not (out / "guard-ready.json").exists():
            if guard.poll() is not None or time.monotonic() >= until:
                raise RuntimeError("new watchdog not ready")
            time.sleep(0.1)
        ready = read(out / "guard-ready.json")
        ready_identity = validate_guard_ready(ready, guard, original["delete_requested_by_epoch"],
            str(Path(__file__).resolve()) + " --watch " + str(out))
        report = stop_prior_guard(old_identity, suffix)
        write_new(out / "handoff.json", {"at": time.time(), "new_guard": ready, "old_guard": report,
            "new_guard_identity": ready_identity, "prior_identity": old_identity,
            "original_deadline_preserved": True})
        if owned_pod(api(["pod", "list"]), original["name"], POD_ID) is None:
            raise ValueError("pod disappeared during handoff; no retry")
        connection = connection_for(POD_ID)
        remote, code = config["remote_root"], config["remote_root"] + "/repo"
        runtime = resource["remote_root"] + "/.venv"
        with (out / "execution.log").open("x") as log:
            def remote_command(command, timeout):
                result = subprocess.run([*connection, command], stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                if result.returncode:
                    raise RuntimeError(f"remote phase failed ({result.returncode}); preserve evidence")
            remote_command("mkdir -p " + shlex.quote(code), 30)
            subprocess.run(["rsync", "-rltzR", "-e", shlex.join(connection[:-1]), *SOURCE_FILES,
                connection[-1] + ":" + code + "/"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
            subprocess.run(["rsync", "-rltz", "-e", shlex.join(connection[:-1]), str(out / "snapshot.json"),
                connection[-1] + ":" + remote + "/snapshot.json"], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
            print("Q38 PHASE: remote offline tests", flush=True)
            remote_command(f"cd {code}; PYTHONPATH=src {runtime}/bin/python -m pytest "
                "tests/test_mechanism_qwen38_pilot.py tests/test_mechanism_qwen38_lease.py -q", 300)
            if original["delete_requested_by_epoch"] - time.time() < plan()["maximum_remote_seconds"] + 180:
                raise ValueError("setup depleted the full-pilot time reserve")
            stop_by = time.time() + plan()["maximum_remote_seconds"]
            publish_once(out / "job.json", {"started_epoch": time.time(), "stop_by_epoch": stop_by,
                "maximum_seconds": plan()["maximum_remote_seconds"], "snapshot": snapshot})
            print("Q38 PHASE: isolated admission then fixed twelve-session pilot", flush=True)
            remote_command(f"cd {code}; export PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1; "
                f"timeout --signal=TERM --kill-after=30s {plan()['maximum_remote_seconds']} "
                f"{runtime}/bin/python -u scripts/mechanism_run_qwen38_pilot.py --snapshot {remote}/snapshot.json "
                f"--out {remote}/evidence --runtime {runtime} "
                "--model-store /workspace/hf-cache/hub/models--Qwen--Qwen3.8-27B "
                f"--stop-by-epoch {stop_by}", plan()["maximum_remote_seconds"] + 60)
        recovered = recover(out, connection, config["remote_root"])
        result = read(recovered / "result.json")
        if result["model_sessions"] != 12:
            raise ValueError("unexpected task count")
        publish_once(out / "completed.json", {"at": time.time(), "pod_id": POD_ID, "result": result,
            "recovered": str(recovered), "next_step": "offline_audit_and_interpretation_no_automatic_followup"})
        success = True
        print("Q38 PILOT COMPLETE " + result["next_step"], flush=True)
    except BaseException as exc:
        write_new(out / "controller-failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        if not success:
            cleanup(config, out, "pilot_controller_failed")
        done.set()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
