#!/usr/bin/env python3
"""Fresh, kernel-isolated Q38 worker; never receives evaluator state."""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if not (HERE / "mechanism_qwen38_guard.py").is_file():
    sys.path.insert(0, str(HERE.parent / "src/creative_machine"))
from mechanism_qwen38_guard import enforce
from mechanism_qwen38 import MODEL_ID, MODEL_REVISION, write_new
from mechanism_actions import PINNED_CONTROLS, synthetic_action, replay
from mechanism_qwen38_session import (TEMPLATE_SHA256, BACKEND_SHA256, LOAD_SECONDS,
    GENERATION_SECONDS, generate_once, validate)


def write(name, value):
    write_new(HERE / name, value)


def kernel_probe():
    data = json.loads((HERE / "probe.json").read_text())
    def denied(fn):
        try:
            fn()
            return False
        except PermissionError:
            return True
    checks = {"allowed_read": (HERE / "allowed.txt").read_text() == "worker-only"}
    (HERE / "allowed-output.txt").write_text("worker-output")
    checks["allowed_write"] = True
    for key, path in data["forbidden_reads"].items():
        checks[key] = denied(lambda p=path: Path(p).read_bytes())
    checks["symlink_read_denied"] = denied(lambda: (HERE / "outside-link").read_bytes())
    checks["outside_write_denied"] = denied(lambda: Path(data["outside_write"]).write_text("x"))
    checks["tcp_denied"] = denied(lambda: socket.create_connection(("127.0.0.1", data["tcp_port"]), timeout=2))
    checks["udp_denied"] = denied(lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as unix:
        unix.bind("\0cm-q38-worker-" + HERE.name)
        unix.listen(1)
        checks["unix_listener_allowed"] = True
        checks["unix_accept_denied"] = denied(lambda: unix.accept())
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as unix:
        checks["unix_connect_denied"] = denied(lambda: unix.connect(data["unix_address"]))
    code = "from pathlib import Path; Path(" + repr(data["forbidden_reads"]["canary_read_denied"]) + ").read_bytes()"
    child = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, close_fds=True)
    checks["descendant_read_denied"] = child.returncode != 0 and "PermissionError" in child.stderr
    write("filesystem-network-probes.json", checks)
    import torch
    checks["cuda_arithmetic"] = (torch.ones(16, device="cuda", dtype=torch.float32)*3).sum().item() == 48.0
    if not all(v is True for v in checks.values()):
        raise ValueError("Linux/CUDA isolation probe failed")
    return {"passed": True, "checks": checks, "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__}


def value_signature(model, torch):
    # Same canonical named-value algorithm as M1-U, with a new checkpoint's
    # reference established in the isolated preflight BEFORE task responses.
    digest = hashlib.sha256()
    counts, tensors = {"parameters": 0, "buffers": 0}, 0
    for kind, items in (("parameters", model.named_parameters()), ("buffers", model.named_buffers())):
        for name, tensor in items:
            if tensor.is_complex() or tensor.layout != torch.strided or (tensor.is_floating_point() and tensor.dtype != torch.float32):
                raise ValueError("noncanonical FP32 tensor")
            category = "float32" if tensor.is_floating_point() else str(tensor.dtype)
            digest.update((json.dumps([kind, name, list(tensor.shape), category], sort_keys=True,
                separators=(",", ":"), allow_nan=False) + "\n").encode())
            counts[kind] += tensor.numel()
            tensors += 1
            flat = tensor.detach().reshape(-1)
            for start in range(0, tensor.numel(), 1_048_576):
                part = flat[start:start+1_048_576]
                array = (part.float() if tensor.is_floating_point() else part).cpu().numpy()
                array = array.astype("<f4" if tensor.is_floating_point() else array.dtype.newbyteorder("<"), copy=False)
                digest.update(array.tobytes(order="C"))
    return {"canonical_sha256": digest.hexdigest(), "numel": counts, "named_tensors": tensors}


def load_model(store, expected):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    if (torch.__version__ != "2.8.0+cu128" or importlib.metadata.version("transformers") != "5.5.0"
            or torch.cuda.device_count() != 1 or torch.cuda.get_device_name(0) != "NVIDIA H200"
            or any(importlib.util.find_spec(n) is not None for n in ("fla", "causal_conv1d"))):
        raise ValueError("unadmitted GPU, packages or optimized kernels")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")
    snapshot = store / "snapshots" / MODEL_REVISION
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("native template changed")
    print("Q38 loading fixed checkpoint", file=sys.stderr, flush=True)
    model = AutoModelForCausalLM.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False,
        dtype=torch.bfloat16, attn_implementation="eager").cuda().eval().float().requires_grad_(False)
    if (type(model).__name__ != "Qwen3_5ForCausalLM"
            or hashlib.sha256(Path(inspect.getfile(type(model))).read_bytes()).hexdigest() != BACKEND_SHA256
            or sum(p.numel() for p in model.parameters()) != 26895998464):
        raise ValueError("checkpoint architecture or backend changed")
    print("Q38 hashing canonical loaded values", file=sys.stderr, flush=True)
    signature = value_signature(model, torch)
    if expected is not None and signature["canonical_sha256"] != expected:
        raise ValueError("model values changed after isolated reference preflight")
    torch.cuda.synchronize()
    write("runtime.json", {"model_id": MODEL_ID, "model_revision": MODEL_REVISION, "weights": signature,
        "dtype": str(model.dtype), "gpu": torch.cuda.get_device_name(0), "backend_sha256": BACKEND_SHA256,
        "packages": {n: importlib.metadata.version(n) for n in ("torch", "transformers", "numpy", "huggingface-hub", "safetensors")},
        "tf32_matmul": False, "tf32_cudnn": False, "optimized_delta_kernels": False})
    return model, tokenizer, torch


def processor_check(model, torch, value):
    from transformers import GenerationConfig, LogitsProcessorList
    from transformers.generation.logits_process import TopKLogitsWarper, TopPLogitsWarper, MinPLogitsWarper
    config = GenerationConfig(**value["generation"], eos_token_id=[248046, 248044], pad_token_id=248044)
    model._prepare_special_tokens(config, kwargs_has_attention_mask=True, device="cuda")
    ids = torch.tensor([[1, 2, 3, 4]], device="cuda")
    raw = torch.arange(32, dtype=torch.float32, device="cuda").reshape(1, -1)/8
    processors = model._get_logits_processor(config, input_ids_seq_length=4,
        logits_processor=LogitsProcessorList(), device="cuda")
    names = [type(p).__name__ for p in processors]
    if names != ["TopKLogitsWarper", "TopPLogitsWarper", "MinPLogitsWarper"]:
        raise ValueError("unexpected sampling processors")
    expected = raw.clone()
    for p in (TopKLogitsWarper(20), TopPLogitsWarper(0.95), MinPLogitsWarper(0.0)):
        expected = p(ids, expected)
    if not torch.equal(processors(ids, raw.clone()), expected):
        raise ValueError("sampling formula differs")
    return {"passed": True, "order": names, "formula_exact_match": True, "presence_penalty": 0.0}


def gpu_preflight(model, tokenizer, torch, value):
    from mechanism_qwen38_probe import numerical_checks, timed_decode
    numerical = numerical_checks(model, tokenizer, torch, HERE)
    timing = timed_decode(model, torch)
    write("timing.json", timing)
    values = [{"kind": "path", "moves": []}, {"kind": "quadratic", "coefficients": [1, 0, 0, 0, 0, 0]}, {"kind": "gcd"}]
    actions = [synthetic_action("submit_solution", v) for v in values]
    actions.append(actions[0].replace("<function=submit_solution>", "<function=invalid>"))
    reports = []
    for i, action in enumerate(actions):
        forced = tokenizer.encode("</think>\n"+action+actions[0], add_special_tokens=False)
        expected = replay(tokenizer, PINNED_CONTROLS, "submit_solution", forced)
        response = generate_once(model, tokenizer, value, forced)
        write(f"forced-{i}.json", response)
        if any(response[k] != v for k, v in expected.items()) or response["envelope_valid"] != (i < 3):
            raise ValueError("new isolated generation path failed first-action transport")
        reports.append({"index": i, "passed": True})
    return {"passed": True, "numerical": numerical, "timing": timing, "forced_transports": reports,
        "execution_kind": "isolated_engineering_preflight_not_task", "task_sessions": 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--model-store", type=Path, required=True)
    p.add_argument("--mode", choices=("kernel", "preflight", "cell"), required=True)
    args = p.parse_args()
    write("isolation.json", enforce(HERE, args.runtime, args.model_store))
    def expired(_sig, _frame):
        raise TimeoutError("Q38 worker deadline")
    signal.signal(signal.SIGALRM, expired)
    try:
        signal.alarm(LOAD_SECONDS)
        if args.mode == "kernel":
            write("probe-result.json", kernel_probe())
            return
        value = json.loads((HERE / "payload.json").read_text())
        validate(value)
        if args.mode == "cell" and value["expected_weights_sha256"] is None:
            raise ValueError("task requires preflight weight signature")
        model, tokenizer, torch = load_model(args.model_store, value["expected_weights_sha256"])
        write("processors.json", processor_check(model, torch, value))
        write("ready.json", {"pid": os.getpid(), "load_complete_monotonic": time.monotonic()})
        signal.alarm(600 if args.mode == "preflight" else GENERATION_SECONDS + 10)
        if args.mode == "preflight":
            write("preflight-result.json", gpu_preflight(model, tokenizer, torch, value))
        else:
            write("response.json", generate_once(model, tokenizer, value))
    except BaseException as exc:
        write("failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
