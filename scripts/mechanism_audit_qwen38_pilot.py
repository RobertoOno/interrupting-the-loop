#!/usr/bin/env python3
"""Read-only audit of Q38-12; optional native token reconstruction, no inference."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.mechanism_qwen38 import manifest, digest
from creative_machine.mechanism_qwen38_pilot import plan, prepare, render, fixtures, score, aggregate
from creative_machine.mechanism_qwen38_session import payload
from creative_machine.mechanism_qwen38_deployment import validate_snapshot, WORKER_FILES, KERNEL_CHECKS
from creative_machine.mechanism_qwen38_guard import DENIED_SYSCALLS, HANDLED, UNIX_SEQPACKET_CLOEXEC
from creative_machine.mechanism_actions import ActionStream, PINNED_CONTROLS, parse_action, replay


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(source, tokenizer=None, source_root=ROOT):
    source = Path(source).resolve()
    read = lambda name: json.loads((source / name).read_text())
    for p in source.rglob("*"):
        require(p.resolve().is_relative_to(source), "escaping evidence symlink")
    require(manifest(source) == read("manifest.json"), "evidence manifest changed")
    snapshot = read("snapshot.json")
    # Historical unit fixtures may be maintained after lease closure; their
    # original bytes remain in source_snapshot. Executed code stays pinned.
    validate_snapshot(snapshot, Path(source_root))
    for name, expected in snapshot["files"].items():
        if name.startswith(("src/", "scripts/")):
            require(digest(ROOT/name) == expected, "live audit dependency differs from executed code")
    require(read("plan.json") == json.loads(json.dumps(plan())), "plan changed")
    inputs = read("inputs.json")
    if tokenizer is not None:
        require(prepare(tokenizer) == inputs, "native prompt reconstruction differs")
    require(read("task-admission.json")["snapshot"] == snapshot, "admission changed")
    preflight = read("gpu-preflight.json")
    weights = preflight["weights"]["canonical_sha256"]
    require(weights == "c0da48f82fd5baa942511db975389536d304d38b14616142577d7a4229dbb2a4", "reference weights changed")
    require(read("task-admission.json")["weights"] == preflight["weights"], "admitted weights changed")
    seen = set()

    def worker(worker_id, expected_payload=None, mode="cell"):
        require(len(worker_id) == 32 and all(c in "0123456789abcdef" for c in worker_id)
            and worker_id not in seen, "unsafe or reused worker")
        seen.add(worker_id)
        path = source / "workers" / worker_id
        wr = lambda name: json.loads((path / name).read_text())
        for original, name in WORKER_FILES.items():
            require(digest(path / name) == snapshot["files"][original], "worker source changed")
        isolation, supervisor = wr("isolation.json"), wr("supervisor.json")
        require(isolation["landlock_abi"] >= 3 and isolation["handled_filesystem_rights"] == HANDLED
            and isolation["no_new_privs"] is True and isolation["single_thread_at_enforcement"] is True
            and isolation["seccomp_denied_syscalls"] == list(DENIED_SYSCALLS)
            and isolation["socket_allowlist"] == {"domain": 1, "type": UNIX_SEQPACKET_CLOEXEC,
                "protocol": 0, "connect_denied": True, "accept_denied": True}, "isolation changed")
        require(supervisor["returncode"] == 0 and supervisor["watchdog_reason"] is None
            and supervisor["fresh_process"] is True and supervisor["inherited_fds_closed"] is True,
            "worker did not finish cleanly")
        if mode != "kernel":
            runtime, processors = wr("runtime.json"), wr("processors.json")
            require(runtime["model_id"] == plan()["model_id"] and runtime["model_revision"] == plan()["model_revision"]
                and runtime["dtype"] == "torch.float32" and runtime["gpu"] == plan()["gpu"]
                and runtime["backend_sha256"] == plan()["backend_sha256"]
                and runtime["weights"] == preflight["weights"]
                and runtime["packages"]["torch"] == plan()["torch"]
                and runtime["packages"]["transformers"] == plan()["transformers"]
                and runtime["tf32_matmul"] is False and runtime["tf32_cudnn"] is False
                and runtime["optimized_delta_kernels"] is False, "runtime changed")
            require(processors == {"passed": True, "order": ["TopKLogitsWarper", "TopPLogitsWarper", "MinPLogitsWarper"],
                "formula_exact_match": True, "presence_penalty": 0.0}, "sampling processors changed")
        if expected_payload is not None:
            require(wr("payload.json") == expected_payload, "worker payload differs")
        return wr

    def response_check(response, kind):
        require(response["execution_kind"] == kind, "execution kind differs")
        ids = response["output_ids"]
        require(len(ids) == response["output_tokens"], "output token count differs")
        stream = ActionStream(PINNED_CONTROLS, "submit_solution", 32768, 2100, clock=lambda: 0)
        for i, token in enumerate(ids):
            if stream.feed(token):
                require(i == len(ids)-1, "tokens after first stop")
        require(stream.finish_reason == response["finish_reason"] == "tool_submission"
            and stream.action_start == response["action_start_index"]
            and stream.action_end == response["action_end_exclusive"], "first-action trace differs")
        if response["envelope_valid"]:
            require(parse_action(response["raw_action"], "submit_solution") == response["submitted"], "raw action differs")
        if tokenizer is not None:
            reparsed = replay(tokenizer, PINNED_CONTROLS, "submit_solution", ids)
            require(all(response[k] == v for k, v in reparsed.items()), "native response reconstruction differs")
        return response

    kernel = read("kernel-preflight.json")
    kr = worker(kernel["worker"], mode="kernel")
    require(kernel["report"] == kr("probe-result.json") and kernel["report"]["passed"] is True
        and set(kernel["report"]["checks"]) == KERNEL_CHECKS
        and all(v is True for v in kernel["report"]["checks"].values())
        and all(kernel[k] is True for k in ("file_positive_controls", "tcp_positive_control", "unix_positive_control")),
        "kernel admission failed")
    expected = None
    if tokenizer is not None:
        expected = payload({**render(tokenizer, "Transport diagnostic; no mathematical problem.\n"), "seed": 2026092901})
    pr = worker(preflight["worker"], expected, "preflight")
    report = preflight["report"]
    require(report == pr("preflight-result.json") and report["passed"] is True
        and report["task_sessions"] == 0 and report["numerical"] == pr("numerical.json")
        and report["numerical"]["passed"] is True and report["numerical"]["identity_exact"] is True
        and report["timing"] == pr("timing.json") and len(report["forced_transports"]) == 4, "GPU admission changed")
    for i in range(4):
        r = response_check(pr(f"forced-{i}.json"), "forced_transport_not_task")
        require(r["envelope_valid"] == (i < 3), "forced invalid-first-call control differs")
    cases, rows, details = {f["id"]: f for f in fixtures()}, [], []
    require(len(inputs["sessions"]) == 12, "input denominator differs")
    for cell, record in zip(plan()["cells"], inputs["sessions"]):
        require(all(record[k] == v for k, v in cell.items()), "input order differs")
        require(hashlib.sha256(record["rendered_prompt"].encode()).hexdigest() == record["prompt_sha256"], "prompt hash differs")
        row, started = read(record["id"]+".json"), read(record["id"]+".started.json")
        require(started["id"] == row["id"] == record["id"] and started["worker"] == row["worker"]
            and started["prompt_sha256"] == record["prompt_sha256"], "started marker differs")
        wr = worker(row["worker"], payload(record, weights))
        response = response_check(wr("response.json"), "model_inference")
        require(response["prompt_sha256"] == record["prompt_sha256"]
            and score(cases[record["fixture_id"]], response) == row["score"]
            and all(row[k] == response[k] for k in ("output_tokens", "finish_reason", "elapsed_seconds")), "score/provenance differs")
        rows.append(row)
        details.append({**row, "input_tokens": record["input_tokens"], "submitted": response["submitted"]})
    require({p.name for p in source.glob("*.started.json")} == {r["id"]+".started.json" for r in rows}, "started denominator differs")
    require({p.name for p in (source/"workers").iterdir()} == seen, "unaccounted worker")
    result = aggregate(rows)
    require(result == read("result.json"), "aggregate differs")
    return {"schema": "cm-q38-pilot-audit-v1", "manifest_verified": True,
        "manifest_entries": len(read("manifest.json")), "prospective_source_files": len(snapshot["files"]),
        "native_tokenizer_reconstruction": tokenizer is not None, "task_workers": 12, "preflight_workers": 2,
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "generation_seconds": sum(r["elapsed_seconds"] for r in rows), "rows": details, "result": result,
        "scope": "Offline replay and exact certificate verification; no model inference or proof of causal internal use."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args()
    tokenizer = None
    if args.tokenizer:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True, trust_remote_code=False)
    print(json.dumps(audit(args.source, tokenizer, args.source_root), indent=2))
