#!/usr/bin/env python3
"""Pinned 27B GPU engineering probe. No task evaluator or model-generated execution."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/creative_machine"))
from mechanism_qwen38 import MODEL_ID, MODEL_REVISION, plan, validate_plan, write_new, digest, manifest
from mechanism_actions import PINNED_CONTROLS, ActionStream, tool_definition, synthetic_action, replay


def native_prompt(tokenizer, text):
    rendered = tokenizer.apply_chat_template([{"role": "user", "content": text}],
        tools=[tool_definition("submit_solution")], tokenize=False,
        add_generation_prompt=True, enable_thinking=True, reasoning_effort="xhigh")
    ids = tokenizer.encode(rendered, add_special_tokens=False)
    if (not rendered.endswith("<think>\n") or not 1 <= len(ids) <= 2048
            or tokenizer.decode(ids, skip_special_tokens=False) != rendered):
        raise ValueError("native tool/thinking prompt is not compatible")
    return {"text": rendered, "ids": ids, "sha256": hashlib.sha256(rendered.encode()).hexdigest()}


def generate(model, tokenizer, torch, prompt, *, forced=None):
    from transformers import GenerationConfig, LogitsProcessorList, StoppingCriteria, StoppingCriteriaList
    config = plan()
    limit = len(forced) if forced is not None else config["free_copy_max_new_tokens"]
    generation = GenerationConfig(**config["generation"], max_new_tokens=limit,
        eos_token_id=[PINNED_CONTROLS["eos"], PINNED_CONTROLS["endoftext"]],
        pad_token_id=PINNED_CONTROLS["endoftext"])
    stream = ActionStream(PINNED_CONTROLS, "submit_solution", limit, config["free_copy_timeout_seconds"])
    ids = torch.tensor([prompt["ids"]], device="cuda")
    class FirstAction(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            if input_ids.shape != (1, len(prompt["ids"]) + len(stream.ids) + 1):
                raise ValueError("non-sequential transport")
            stop = stream.feed(int(input_ids[0, -1]))
            if len(stream.ids) % 256 == 0:
                print(f"COPY {len(stream.ids)} tokens", flush=True)
            return stop
    class Forced:
        def __call__(self, input_ids, scores):
            step = input_ids.shape[-1] - len(prompt["ids"])
            out = torch.full_like(scores, float("-inf"))
            out[:, forced[step]] = 0.0
            return out
    processors = LogitsProcessorList([Forced()] if forced is not None else [])
    torch.manual_seed(config["free_copy_seed"])
    torch.cuda.synchronize()
    started = time.monotonic()
    with torch.inference_mode():
        output = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
            generation_config=generation, logits_to_keep=1,
            logits_processor=processors, stopping_criteria=StoppingCriteriaList([FirstAction()]))
    torch.cuda.synchronize()
    if output[0, len(prompt["ids"]):].tolist() != stream.ids:
        raise ValueError("output and first-action trace differ")
    return {**stream.result(tokenizer), "prompt_sha256": prompt["sha256"],
        "elapsed_seconds": time.monotonic() - started, "generation": generation.to_dict(),
        "execution_kind": "forced_token_transport" if forced is not None else "unforced_copy_diagnostic"}


def numerical_checks(model, tokenizer, torch, out):
    sequence = tokenizer.encode("Runtime check: a number can be written as a sum of two integers.", add_special_tokens=False)
    ids = torch.tensor([sequence], device="cuda")
    prefix = len(sequence) - 4
    checks = []
    with torch.inference_mode():
        initial = model(input_ids=ids[:, :prefix], use_cache=True, logits_to_keep=1)
        cache = initial.past_key_values
        del initial
        for i in range(prefix, len(sequence)):
            cached = model(input_ids=ids[:, i:i+1], attention_mask=torch.ones_like(ids[:, :i+1]),
                past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = cached.past_key_values
            full = model(input_ids=ids[:, :i+1], use_cache=False, logits_to_keep=1)
            error = float((cached.logits - full.logits).abs().max())
            finite = bool(torch.isfinite(cached.logits).all() and torch.isfinite(full.logits).all())
            record = {"position": i, "max_abs_logit_error": error, "finite": finite,
                "same_argmax": int(cached.logits.argmax()) == int(full.logits.argmax()),
                "cache_length": int(cache.get_seq_length()),
                "passed": finite and error <= plan()["cache_absolute_tolerance"] and int(cache.get_seq_length()) == i+1}
            checks.append(record)
            torch.save({"cached_logits": cached.logits.cpu(), "full_logits": full.logits.cpu()}, out / f"cache-{i}.pt")
            del cached, full
        del cache
        original = model(input_ids=ids, use_cache=False, logits_to_keep=1).logits
        layer_index = len(model.model.layers) // 2
        def identity(_module, _input, output):
            return (output[0].clone(), *output[1:]) if isinstance(output, tuple) else output.clone()
        handle = model.model.layers[layer_index].register_forward_hook(identity)
        try:
            replaced = model(input_ids=ids, use_cache=False, logits_to_keep=1).logits
        finally:
            handle.remove()
        identity_error = float((original - replaced).abs().max())
        exact_identity = bool(torch.equal(original, replaced))
        torch.save({"original": original.cpu(), "identity": replaced.cpu()}, out / "identity.pt")
    report = {"cache_checks": checks, "identity_layer": layer_index,
        "identity_max_abs_error": identity_error, "identity_exact": exact_identity,
        "passed": all(c["passed"] for c in checks) and exact_identity}
    write_new(out / "numerical.json", report)
    if not report["passed"]:
        raise ValueError("numerical/cache/identity preflight failed; preserve and review")
    return report


def timed_decode(model, torch):
    # A fixed-token microbenchmark, not sampled reasoning and not a task score.
    count = plan()["decode_timing_tokens"]
    ids = torch.full((1, 2048), PINNED_CONTROLS["endoftext"], device="cuda", dtype=torch.long)
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    started = time.monotonic()
    with torch.inference_mode():
        result = model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=True, logits_to_keep=1)
        cache = result.past_key_values
        if not bool(torch.isfinite(result.logits).all()):
            raise ValueError("2048-token prefill returned non-finite logits")
        del result
        torch.cuda.synchronize()
        prefill = time.monotonic() - started
        token = ids[:, :1]
        started = time.monotonic()
        for _ in range(count):
            result = model(input_ids=token, past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = result.past_key_values
            if not bool(torch.isfinite(result.logits).all()):
                raise ValueError("cached decode returned non-finite logits")
            del result
        torch.cuda.synchronize()
        elapsed = time.monotonic() - started
        length = int(cache.get_seq_length())
        if length != 2048 + count:
            raise ValueError("decode cache length mismatch")
        peak = torch.cuda.max_memory_allocated() / 1024**3
    return {"execution_kind": "synthetic_fixed_token_microbenchmark_not_reasoning",
        "prefill_tokens": 2048, "prefill_seconds": prefill, "decode_tokens": count,
        "decode_seconds": elapsed, "decode_tokens_per_second": count / elapsed,
        "final_cache_tokens": length, "peak_allocated_gib": peak,
        "validated_32k_generation": False, "validated_backward": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-store", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = plan()
    write_new(out / "plan.json", config)
    def expired(_signum, _frame):
        raise TimeoutError("Qwen3.8 preflight phase deadline")
    signal.signal(signal.SIGALRM, expired)
    started = time.monotonic()
    try:
        signal.alarm(config["load_timeout_seconds"])
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        if (torch.__version__ != config["torch"] or importlib.metadata.version("transformers") != config["transformers"]
                or torch.cuda.device_count() != 1 or "H200" not in torch.cuda.get_device_name(0)
                or any(importlib.util.find_spec(n) is not None for n in ("fla", "causal_conv1d"))):
            raise ValueError("runtime differs from the preflight plan")
        snapshot = args.model_store.resolve() / "snapshots" / MODEL_REVISION
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
        for key, token in {"think_open": "<think>", "think_close": "</think>", "tool_open": "<tool_call>",
                "tool_close": "</tool_call>", "eos": "<|im_end|>", "endoftext": "<|endoftext|>"}.items():
            if tokenizer.encode(token, add_special_tokens=False) != [PINNED_CONTROLS[key]]:
                raise ValueError("native transport control changed: " + key)
        write_new(out / "tokenizer.json", {"model_id": MODEL_ID, "revision": MODEL_REVISION,
            "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
            "control_ids": PINNED_CONTROLS, "native_tools_thinking": True})
        prompt = native_prompt(tokenizer, config["free_copy_prompt"])
        write_new(out / "copy-input.json", prompt)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.set_float32_matmul_precision("highest")
        print("LOAD Qwen3.8-27B, BF16 checkpoint -> FP32 execution", flush=True)
        model = AutoModelForCausalLM.from_pretrained(snapshot, local_files_only=True,
            trust_remote_code=False, dtype=torch.bfloat16, attn_implementation="eager").cuda().eval()
        model.float().requires_grad_(False)
        torch.cuda.synchronize()
        if (type(model).__name__ != "Qwen3_5ForCausalLM" or model.config.vocab_size != 248320
                or any(p.dtype != torch.float32 for p in model.parameters() if p.is_floating_point())):
            raise ValueError("unexpected model class, vocabulary or execution precision")
        runtime = {"model_id": MODEL_ID, "model_revision": MODEL_REVISION,
            "model_class": type(model).__name__, "model_source_sha256": digest(inspect.getfile(type(model))),
            "parameter_count_loaded": sum(p.numel() for p in model.parameters()),
            "load_seconds": time.monotonic() - started, "dtype": str(model.dtype),
            "gpu": torch.cuda.get_device_name(0), "gpu_total_gib": torch.cuda.get_device_properties(0).total_memory/1024**3,
            "allocated_gib": torch.cuda.memory_allocated()/1024**3,
            "peak_load_allocated_gib": torch.cuda.max_memory_allocated()/1024**3,
            "packages": {n: importlib.metadata.version(n) for n in ("torch", "transformers", "huggingface-hub", "safetensors", "numpy")},
            "tf32_matmul": torch.backends.cuda.matmul.allow_tf32, "tf32_cudnn": torch.backends.cudnn.allow_tf32,
            "training": model.training, "optimized_delta_kernels": False,
            "scope": "no evaluator/hidden targets; no execution of model-generated code; kernel task-isolation admission is separate"}
        write_new(out / "runtime.json", runtime)
        print("LOAD COMPLETE " + json.dumps(runtime), flush=True)
        signal.alarm(config["probe_timeout_seconds"])
        numerical = numerical_checks(model, tokenizer, torch, out)
        print("NUMERICAL/CACHE/IDENTITY PASS", flush=True)
        timing = timed_decode(model, torch)
        write_new(out / "timing.json", timing)
        print("TIMING " + json.dumps(timing), flush=True)
        transports = []
        values = [{"kind": "path", "moves": []}, {"kind": "quadratic", "coefficients": [1, 0, 0, 0, 0, 0]}, {"kind": "gcd"}]
        strings = [synthetic_action("submit_solution", v) for v in values]
        strings.append(strings[0].replace("<function=submit_solution>", "<function=invalid>"))
        for index, first in enumerate(strings):
            forced = tokenizer.encode("</think>\n" + first + strings[0], add_special_tokens=False)
            expected = replay(tokenizer, PINNED_CONTROLS, "submit_solution", forced)
            result = generate(model, tokenizer, torch, prompt, forced=forced)
            write_new(out / f"forced-{index}.json", result)
            if any(result[k] != value for k, value in expected.items()) or result["envelope_valid"] != (index < 3):
                raise ValueError("first-action transport failed")
            transports.append({"index": index, "passed": True, "envelope_valid": result["envelope_valid"]})
        print("FORCED TRANSPORT PASS; beginning one unforced copy diagnostic", flush=True)
        copied = generate(model, tokenizer, torch, prompt)
        write_new(out / "copy-response.json", copied)
        copy_ok = copied["envelope_valid"] and copied["submitted"] == config["free_copy_expected"]
        report = {"schema": config["schema"], "numerical_passed": numerical["passed"],
            "forced_transports": transports, "copy_delivery_passed": copy_ok,
            "runtime_preflight_passed": bool(numerical["passed"] and copy_ok),
            "task_sessions": 0, "unforced_transport_sessions": 1,
            "interpretation": "engineering readiness only; no mathematical competence, bridge benefit or causal mechanism established",
            "timing": timing, "elapsed_seconds": time.monotonic() - started,
            "next_step": "freeze_separate_behavioral_pilot_after_budget_and_isolation_review" if copy_ok else "review_transport_diagnostic_no_automatic_retry"}
        write_new(out / "result.json", report)
        print("PREFLIGHT COMPLETE " + json.dumps(report), flush=True)
    except BaseException as exc:
        write_new(out / "failure.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        signal.alarm(0)
        write_new(out / "manifest.json", manifest(out))


if __name__ == "__main__":
    main()
