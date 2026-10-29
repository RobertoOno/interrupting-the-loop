#!/usr/bin/env python3
"""A2 consolidation — LoRA SFT of one arm, run ON THE POD (docs/A2_CONSOLIDACAO_V1.md; recipe frozen there).
  python a2c_train.py --model Qwen/Qwen3.8-27B --data p1.jsonl --out adapters/a2c-p1 --steps 108 [--seed 2026091301]
Each row: {"prompt", "completion"} -> chat [user: prompt, assistant: completion] through the model's chat template with
enable_thinking=False; loss only on the assistant tokens; LoRA r=16, alpha=32, dropout 0.05 on q/k/v/o/gate/up/down of the
language model; AdamW lr 2e-4, cosine, warmup 5%, effective batch 8 (micro 1 x accumulation 8), max length 4096, bf16; exactly
--steps optimizer steps over the data (epochs follow from the size); the LAST state is saved (no selection). Writes
train_log.jsonl (loss per step) and manifest.json (data hash, recipe, library versions, adapter file hashes)."""
from __future__ import annotations
import argparse, hashlib, json, math, os, random, time
from pathlib import Path


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--data", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=108); ap.add_argument("--seed", type=int, default=2026091301); ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--accum", type=int, default=8); ap.add_argument("--max-len", type=int, default=4096); ap.add_argument("--rank", type=int, default=16)
    a = ap.parse_args()
    import torch, transformers, peft
    from transformers import AutoTokenizer, get_cosine_schedule_with_warmup
    from peft import LoraConfig, get_peft_model
    random.seed(a.seed); torch.manual_seed(a.seed)
    rows = [json.loads(l) for l in a.data.read_text(encoding="utf-8").splitlines() if l.strip()]
    tok = AutoTokenizer.from_pretrained(a.model)
    # tokenize: prompt part (with generation prompt) masked, completion part supervised
    def encode(r):
        msgs = [{"role": "user", "content": r["prompt"]}]
        try:
            ptxt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            full = tok.apply_chat_template(msgs + [{"role": "assistant", "content": r["completion"]}], tokenize=False, enable_thinking=False)
        except TypeError:
            ptxt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            full = tok.apply_chat_template(msgs + [{"role": "assistant", "content": r["completion"]}], tokenize=False)
        if not full.startswith(ptxt):
            # fall back: supervise from the first index where the two diverge
            i = 0
            while i < min(len(ptxt), len(full)) and ptxt[i] == full[i]:
                i += 1
            ptxt = full[:i]
        p_ids = tok(ptxt, add_special_tokens=False)["input_ids"]; f_ids = tok(full, add_special_tokens=False)["input_ids"]
        f_ids = f_ids[: a.max_len]; labels = [-100] * min(len(p_ids), len(f_ids)) + f_ids[len(p_ids):]
        return torch.tensor(f_ids), torch.tensor(labels[: len(f_ids)])
    data = [encode(r) for r in rows]
    sup = sum(int((l != -100).sum()) for _, l in data); print(f"examples {len(data)} | supervised tokens {sup} | max len {max(len(x) for x, _ in data)}", flush=True)
    loader = None
    for name in ("AutoModelForMultimodalLM", "AutoModelForImageTextToText", "AutoModelForCausalLM"):   # Qwen3.8 is a multimodal checkpoint
        if hasattr(transformers, name):
            try:
                model = getattr(transformers, name).from_pretrained(a.model, dtype=torch.bfloat16, device_map="cuda"); loader = name; break
            except (ValueError, KeyError) as exc:
                print(f"{name}: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
    if loader is None:
        raise SystemExit("no auto class could load the checkpoint")
    print("loaded with", loader, "| params", sum(p.numel() for p in model.parameters()) // 10**6, "M", flush=True)
    model.gradient_checkpointing_enable(); model.config.use_cache = False
    targets = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    cfg = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, target_modules=targets, task_type="CAUSAL_LM",
                     exclude_modules=r".*(visual|vision|mm_projector|merger).*")
    model = get_peft_model(model, cfg); model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(opt, int(round(0.05 * a.steps)), a.steps)
    a.out.mkdir(parents=True, exist_ok=True); log = (a.out / "train_log.jsonl").open("w")
    order = list(range(len(data))); random.shuffle(order); pos = 0; step = 0; t0 = time.time(); model.train()
    while step < a.steps:
        opt.zero_grad(set_to_none=True); losses = []
        for _ in range(a.accum):
            if pos >= len(order):
                random.shuffle(order); pos = 0
            ids, labels = data[order[pos]]; pos += 1
            out = model(input_ids=ids[None].cuda(), labels=labels[None].cuda())
            (out.loss / a.accum).backward(); losses.append(float(out.loss))
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step(); step += 1
        rec = {"step": step, "loss": sum(losses) / len(losses), "lr": sched.get_last_lr()[0], "elapsed_s": round(time.time() - t0, 1)}
        log.write(json.dumps(rec) + "\n"); log.flush()
        if step % 10 == 0 or step == 1:
            print(json.dumps(rec), flush=True)
    model.save_pretrained(str(a.out)); log.close()
    files = {p.name: sha_file(p) for p in sorted(a.out.iterdir()) if p.is_file() and p.name != "manifest.json"}
    manifest = {"model": a.model, "loader": loader, "data": str(a.data), "data_sha256": sha_file(a.data), "examples": len(rows), "steps": a.steps, "seed": a.seed, "lr": a.lr,
                "accum": a.accum, "max_len": a.max_len, "rank": a.rank, "alpha": 2 * a.rank, "dropout": 0.05, "targets": targets,
                "epochs_equivalent": round(a.steps * a.accum / len(rows), 3), "supervised_tokens": sup,
                "versions": {"torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__}, "files": files,
                "elapsed_s": round(time.time() - t0, 1)}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n"); print(json.dumps({k: manifest[k] for k in ("examples", "steps", "epochs_equivalent", "elapsed_s")}))


if __name__ == "__main__":
    main()
