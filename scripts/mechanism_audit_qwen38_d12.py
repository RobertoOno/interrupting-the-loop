#!/usr/bin/env python3
"""Read-only D12 evidence audit; no model load, inference, repairs or retries."""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.mechanism_actions import ActionStream, PINNED_CONTROLS, parse_action, synthetic_action
from creative_machine.mechanism_qwen38 import digest, manifest, write_new
from creative_machine.mechanism_qwen38_d12 import (
    plan, prepare, validate_prepared, render, fixtures, aggregate, NATIVE_PATH, WEIGHTS_SHA256,
)
from creative_machine.mechanism_qwen38_d12_deployment import validate_snapshot, KERNEL_CHECKS
from creative_machine.mechanism_qwen38_deployment import WORKER_FILES
from creative_machine.mechanism_qwen38_guard import DENIED_SYSCALLS, HANDLED, UNIX_SEQPACKET_CLOEXEC
from creative_machine.mechanism_qwen38_session import payload, settings, GENERATION_SECONDS, MAX_NEW_TOKENS
from creative_machine.mechanism_interface_ab import score


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(left, right):
    """Do not let Python equality silently identify True with 1."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "duplicate evidence JSON key")
            value[key] = item
        return value
    def invalid(_):
        raise ValueError("non-finite evidence JSON")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "timestamp lacks timezone")
    return parsed.timestamp()


def check_response(response, tokenizer=None, kind="model_inference"):
    """Replay token events, including genuine terminal failures.

    No per-token clock was recorded. For time_limit, the replay imposes the
    recorded timeout on the final token and checks elapsed >= 2100 s. It does
    not claim to independently reconstruct the exact time of earlier tokens.
    """
    require(response["execution_kind"] == kind, "execution kind differs")
    require(kind in ("model_inference", "forced_transport_not_task"), "unknown execution kind")
    config = response["generation_config"]
    limit = config["max_new_tokens"]
    require(type(limit) is int and 1 <= limit <= MAX_NEW_TOKENS, "invalid generation limit")
    expected_config = {**settings(), "eos_token_id": [248046, 248044], "pad_token_id": 248044}
    if kind == "forced_transport_not_task":
        expected_config["max_new_tokens"] = limit
    require(all(k in config and same(config[k], v) for k, v in expected_config.items()), "generation recipe differs")
    ids, finish, elapsed = response["output_ids"], response["finish_reason"], response["elapsed_seconds"]
    require(isinstance(ids, list) and 1 <= len(ids) <= limit, "invalid output denominator")
    require(type(response["output_tokens"]) is int and len(ids) == response["output_tokens"], "output token count differs")
    require(number(elapsed) and number(response["peak_allocated_gib"]), "invalid runtime metric")
    require(finish in ("tool_submission", "eos", "max_new_tokens", "time_limit"), "unknown finish reason")
    if finish == "time_limit":
        require(kind == "model_inference" and elapsed >= GENERATION_SECONDS, "unsubstantiated time limit")
    now = [0.0]
    stream = ActionStream(PINNED_CONTROLS, "submit_solution", limit, GENERATION_SECONDS, clock=lambda: now[0])
    for index, token in enumerate(ids):
        if finish == "time_limit" and index == len(ids)-1:
            now[0] = float(GENERATION_SECONDS)
        if stream.feed(token):
            require(index == len(ids)-1, "tokens after first stop")
    require(stream.finish_reason == finish, "terminal trace differs")
    expected = {
        "finish_reason": stream.finish_reason,
        "thinking_closed": stream.first_thinking_close is not None,
        "thinking_active_at_stop": stream.thinking,
        "first_thinking_close_index": stream.first_thinking_close,
        "action_start_index": stream.action_start, "action_end_exclusive": stream.action_end,
        "submission_complete": stream.action_end is not None,
        "ignored_tool_open_in_thinking": stream.ignored_tool_open_in_thinking,
        "eos_observed": ids[-1] in (PINNED_CONTROLS["eos"], PINNED_CONTROLS["endoftext"]),
    }
    require(all(same(response[k], v) for k, v in expected.items()), "action/thinking metadata differs")
    raw, value, error = response["raw_action"], None, None
    if stream.action_end is None:
        require(raw is None, "unfinished stream contains a submitted action")
    else:
        require(isinstance(raw, str), "completed action has no raw envelope")
        try:
            value = parse_action(raw, "submit_solution")
        except (ValueError, RecursionError) as exc:
            error = str(exc)
    require(same(response["submitted"], value) and same(response["envelope_valid"], value is not None)
        and same(response["parse_error"], error), "envelope parse differs")
    require(isinstance(response["raw_output"], str), "missing decoded output")
    if tokenizer is not None:
        decoded = stream.result(tokenizer)
        require(same(decoded, {k: response[k] for k in decoded}),
            "native response reconstruction differs")
    return response


def audit(source, tokenizer=None, source_root=ROOT):
    source, source_root = Path(source).resolve(), Path(source_root).resolve()
    require((source / "manifest.json").is_file() and (source / "result.json").is_file()
        and not (source / "failure.json").exists(), "complete recovered D12 batch required")
    for path in source.rglob("*"):
        require(path.resolve().is_relative_to(source), "escaping evidence symlink")
        require(path.name != "manifest.json" or path == source / "manifest.json", "unmanifested nested manifest")
    evidence_manifest = read(source / "manifest.json")
    require(same(manifest(source), evidence_manifest), "evidence manifest changed")
    snapshot, frozen_plan = read(source / "snapshot.json"), plan()
    validate_snapshot(snapshot, source_root)
    for name, expected_hash in snapshot["files"].items():
        if name.startswith(("src/", "scripts/")):
            require(digest(ROOT / name) == expected_hash, "live audit dependency differs from executed code")
    require(same(read(source / "plan.json"), frozen_plan), "plan changed")
    inputs, native = read(source / "inputs.json"), read(source_root / NATIVE_PATH)
    validate_prepared(inputs, native)
    if tokenizer is not None:
        require(same(prepare(tokenizer, native), inputs), "native prompts differ")
    admission, claim = read(source / "task-admission.json"), read(source / "claim.json")
    require(same(admission["snapshot"], snapshot) and same(claim["snapshot"], snapshot), "admission snapshot differs")
    stop = admission["stop_by_epoch"]
    require(number(stop) and same(stop, claim["stop_by_epoch"]) and admission["maximum_sessions"] == 12
        and claim["phase"] == "claimed_not_yet_admitted", "claim/deadline differs")
    admitted_at = timestamp(admission["at"])
    claimed_at = timestamp(claim["at"])
    require(claimed_at <= admitted_at < stop
        and stop-claimed_at <= frozen_plan["maximum_remote_seconds"], "admission time order differs")
    preflight = read(source / "gpu-preflight.json")
    expected_weights = {"canonical_sha256": WEIGHTS_SHA256,
        "numel": {"parameters": 26895998464, "buffers": 64}, "named_tensors": 853}
    require(same(preflight["weights"], expected_weights) and same(admission["weights"], expected_weights), "admitted weights differ")
    seen = set()

    def worker(worker_id, expected_payload=None, mode="cell"):
        require(isinstance(worker_id, str) and re.fullmatch(r"[a-f0-9]{32}", worker_id)
            and worker_id not in seen, "unsafe or reused worker")
        seen.add(worker_id)
        directory = source / "workers" / worker_id
        wr = lambda name: read(directory / name)
        require(not (directory / "failure.json").exists(), "worker failure in completed batch")
        for original, name in WORKER_FILES.items():
            require(digest(directory / name) == snapshot["files"][original], "worker source changed")
        require({p.name for p in directory.glob("*.py")} == set(WORKER_FILES.values()), "extra worker code")
        isolation, supervisor = wr("isolation.json"), wr("supervisor.json")
        require(type(isolation["landlock_abi"]) is int and isolation["landlock_abi"] >= 3
            and same(isolation["handled_filesystem_rights"], HANDLED)
            and isolation["no_new_privs"] is True and isolation["single_thread_at_enforcement"] is True
            and same(isolation["seccomp_denied_syscalls"], list(DENIED_SYSCALLS))
            and same(isolation["socket_allowlist"], {"domain": 1, "type": UNIX_SEQPACKET_CLOEXEC,
                "protocol": 0, "connect_denied": True, "accept_denied": True}), "isolation differs")
        require(type(supervisor["returncode"]) is int and supervisor["returncode"] == 0
            and supervisor["watchdog_reason"] is None and supervisor["fresh_process"] is True
            and supervisor["inherited_fds_closed"] is True and number(supervisor["elapsed_seconds"])
            and supervisor["load_limit_seconds"] == (90 if mode == "kernel" else 600)
            and supervisor["phase_limit_seconds"] == (2100 if mode == "cell" else 600 if mode == "preflight" else 1800)
            and supervisor["watchdog_finalization_grace_seconds"] == 10, "supervision differs")
        if mode != "kernel":
            runtime, ready = wr("runtime.json"), wr("ready.json")
            require(supervisor["ready_observed"] is True and ready["pid"] == supervisor["pid"]
                and number(ready["load_complete_monotonic"]), "worker readiness differs")
            expected_runtime = {"model_id": frozen_plan["model_id"], "model_revision": frozen_plan["model_revision"],
                "dtype": "torch.float32", "gpu": frozen_plan["gpu"], "backend_sha256": frozen_plan["backend_sha256"],
                "weights": expected_weights, "tf32_matmul": False, "tf32_cudnn": False, "optimized_delta_kernels": False}
            require(all(same(runtime[k], v) for k, v in expected_runtime.items())
                and runtime["packages"]["torch"] == frozen_plan["torch"]
                and runtime["packages"]["transformers"] == frozen_plan["transformers"], "runtime differs")
            require(same(wr("processors.json"), {"passed": True,
                "order": ["TopKLogitsWarper", "TopPLogitsWarper", "MinPLogitsWarper"],
                "formula_exact_match": True, "presence_penalty": 0.0}), "sampling processors differ")
        if expected_payload is not None:
            require(same(wr("payload.json"), expected_payload), "worker payload differs")
        return wr

    kernel = read(source / "kernel-preflight.json")
    kr = worker(kernel["worker"], mode="kernel")
    report = kernel["report"]
    require(same(report, kr("probe-result.json")) and report["passed"] is True
        and report["gpu"] == "NVIDIA H200" and set(report["checks"]) == KERNEL_CHECKS
        and all(v is True for v in report["checks"].values())
        and all(kernel[k] is True for k in ("file_positive_controls", "tcp_positive_control", "unix_positive_control")),
        "kernel preflight differs")
    pr = worker(preflight["worker"], mode="preflight")
    diagnostic_payload = pr("payload.json")
    expected_diagnostic = payload({**diagnostic_payload, "seed": 2026093003}, WEIGHTS_SHA256)
    if tokenizer is not None:
        expected_diagnostic = payload({**render(tokenizer, "Transport diagnostic; no mathematical problem.\n"),
            "seed": 2026093003}, WEIGHTS_SHA256)
    require(same(diagnostic_payload, expected_diagnostic), "preflight payload differs")
    report, numerical = preflight["report"], pr("numerical.json")
    require(same(report, pr("preflight-result.json")) and report["passed"] is True
        and report["execution_kind"] == "isolated_engineering_preflight_not_task" and report["task_sessions"] == 0
        and same(report["numerical"], numerical) and numerical["passed"] is True
        and numerical["identity_exact"] is True and numerical["identity_max_abs_error"] == 0.0
        and len(numerical["cache_checks"]) == 4 and same(report["timing"], pr("timing.json"))
        and same(report["forced_transports"], [{"index": i, "passed": True} for i in range(4)]), "GPU preflight differs")
    for index, check in enumerate(numerical["cache_checks"], 11):
        require(check["position"] == index and check["cache_length"] == index+1 and check["finite"] is True
            and check["passed"] is True and number(check["max_abs_logit_error"])
            and check["max_abs_logit_error"] <= 0.05, "cache check differs")
    forced_actions = [synthetic_action("submit_solution", v) for v in (
        {"kind": "path", "moves": []}, {"kind": "quadratic", "coefficients": [1, 0, 0, 0, 0, 0]}, {"kind": "gcd"})]
    forced_actions.append(forced_actions[0].replace("<function=submit_solution>", "<function=invalid>"))
    for index, action in enumerate(forced_actions):
        response = check_response(pr(f"forced-{index}.json"), tokenizer, "forced_transport_not_task")
        require(response["finish_reason"] == "tool_submission" and response["envelope_valid"] == (index < 3)
            and response["prompt_sha256"] == diagnostic_payload["prompt_sha256"], "forced transport differs")
        if tokenizer is not None:
            ids = tokenizer.encode("</think>\n"+action+forced_actions[0], add_special_tokens=False)
            require(response["generation_config"]["max_new_tokens"] == len(ids)
                and response["output_ids"] == ids[:response["output_tokens"]], "forced token sequence differs")

    cases, rows, details = {f["id"]: f for f in fixtures()}, [], []
    previous_start = admitted_at
    for record in inputs["sessions"]:
        row, started = read(source / (record["id"]+".json")), read(source / (record["id"]+".started.json"))
        require(all(same(row[k], record[k]) for k in frozen_plan["cells"][0]), "cell identity/order differs")
        require(started["id"] == row["id"] == record["id"] and started["worker"] == row["worker"]
            and started["prompt_sha256"] == record["prompt_sha256"], "started marker differs")
        started_at = timestamp(started["at"])
        # The full-window check occurs before staging; its exact wall-clock
        # instant is not recorded in the later .started marker.
        require(previous_start <= started_at < stop, "cell admission time differs")
        previous_start = started_at
        wr = worker(row["worker"], payload(record, WEIGHTS_SHA256))
        response = check_response(wr("response.json"), tokenizer)
        require(response["prompt_sha256"] == record["prompt_sha256"]
            and row["execution_kind"] == "model_inference" and same(score(cases[record["fixture_id"]], response), row["score"])
            and all(same(row[k], response[k]) for k in ("output_tokens", "finish_reason", "elapsed_seconds"))
            and response["elapsed_seconds"] <= wr("supervisor.json")["elapsed_seconds"], "score/provenance differs")
        rows.append(row)
        details.append({**row, "input_tokens": record["input_tokens"], "submitted": response["submitted"]})
    require({p.name for p in source.glob("*.started.json")} == {r["id"]+".started.json" for r in rows}, "started denominator differs")
    require({p.name for p in source.glob("d[0-9][0-9].json")} == {r["id"]+".json" for r in rows}, "result denominator differs")
    require({p.name for p in (source / "workers").iterdir()} == seen, "unaccounted worker")
    result = aggregate(rows)
    require(same(result, read(source / "result.json")), "aggregate differs")
    return {"schema": "cm-q38-d12-audit-v1", "audit_complete": tokenizer is not None,
        "manifest_verified": True, "manifest_entries": len(evidence_manifest),
        "prospective_source_files": len(snapshot["files"]), "native_tokenizer_reconstruction": tokenizer is not None,
        "task_workers": len(rows), "preflight_workers": 2, "kernel_controls": len(KERNEL_CHECKS),
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "generation_seconds": sum(r["elapsed_seconds"] for r in rows), "rows": details, "result": result,
        "audit_script_sha256": digest(Path(__file__)),
        "scope": "Offline evidence replay and exact certificates; weight signatures and numerical reports reconciled, not new model loading or GPU numerical replication.",
        "time_limit_scope": "Recorded elapsed >= 2100 and terminal-token replay; exact per-token timing was not logged."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        require(not args.output.resolve().is_relative_to(args.source.resolve()), "audit output must be outside evidence")
        require(not args.output.exists(), "audit output already exists")
    tokenizer = None
    if args.tokenizer:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True, trust_remote_code=False)
    report = audit(args.source, tokenizer, args.source_root)
    if args.output:
        write_new(args.output, report)
    print(json.dumps(report, indent=2, allow_nan=False))
