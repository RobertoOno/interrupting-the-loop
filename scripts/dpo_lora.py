#!/usr/bin/env python3
"""C-repel: DPO on LoRA in MLX (attractors into repulsors).

Pairs {prompt, chosen, rejected}; reference = the frozen base model (reference
log-probabilities precomputed before the LoRA layers are attached); loss =
-log sigmoid(beta * ((pi_c - ref_c) - (pi_r - ref_r))) on completion tokens.
Saves an mlx_lm-compatible adapter (adapters.safetensors + adapter_config.json)
so `mlx_lm.load(..., adapter_path=...)` works unchanged.

    python scripts/dpo_lora.py --pairs pairs.jsonl --adapter-path out --iters 80
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten, tree_map
from mlx_lm import load
from mlx_lm.tuner.utils import linear_to_lora_layers

def encode_pair(tok, prompt, completion, max_len):
    p = tok.encode(prompt); c = tok.encode(completion, add_special_tokens=False) if hasattr(tok, "encode") else []
    ids = (p + c)[:max_len]
    return mx.array(ids)[None], len(p)

def seq_logprob(model, ids, prompt_len):
    """Sum of log-probabilities of the completion tokens (positions >= prompt_len) given the prefix."""
    logits = model(ids[:, :-1]).astype(mx.float32)
    logp = nn.log_softmax(logits, axis=-1)
    tgt = ids[:, 1:]
    tok_lp = mx.take_along_axis(logp, tgt[..., None], axis=-1)[..., 0]
    T = tok_lp.shape[1]
    mask = (mx.arange(T) >= (prompt_len - 1)).astype(mx.float32)[None]
    return (tok_lp * mask).sum(axis=1)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    ap.add_argument("--pairs", required=True); ap.add_argument("--adapter-path", required=True)
    ap.add_argument("--iters", type=int, default=80); ap.add_argument("--pairs-per-step", type=int, default=2)
    ap.add_argument("--beta", type=float, default=0.1); ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--num-layers", type=int, default=16); ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=1024); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    mx.random.seed(a.seed)
    model, tok = load(str(Path(a.model).expanduser()))
    pairs = [json.loads(l) for l in open(a.pairs) if l.strip()]
    enc = []
    for pr in pairs:
        c_ids, pl = encode_pair(tok, pr["prompt"], pr["chosen"], a.max_len)
        r_ids, _ = encode_pair(tok, pr["prompt"], pr["rejected"], a.max_len)
        enc.append((c_ids, r_ids, pl))
    # reference log-probs with the frozen base (no adapter yet)
    model.freeze()
    refs = []
    for c_ids, r_ids, pl in enc:
        rc = seq_logprob(model, c_ids, pl); rr = seq_logprob(model, r_ids, pl); mx.eval(rc, rr)
        refs.append((rc, rr))
    print(f"reference log-probs computed for {len(enc)} pairs", flush=True)
    lora_cfg = {"rank": a.rank, "dropout": 0.0, "scale": 20.0}
    linear_to_lora_layers(model, a.num_layers, lora_cfg)
    n_tr = sum(v.size for _, v in tree_flatten(model.trainable_parameters()))
    print(f"trainable parameters: {n_tr/1e6:.3f}M", flush=True)
    opt = optim.Adam(learning_rate=a.lr)

    def loss_fn(model, c_ids, r_ids, pl, rc, rr):
        lc = seq_logprob(model, c_ids, pl); lr_ = seq_logprob(model, r_ids, pl)
        margin = a.beta * ((lc - rc) - (lr_ - rr))
        return -nn.log_sigmoid(margin).mean(), margin.mean()

    vg = nn.value_and_grad(model, lambda m, *x: loss_fn(m, *x)[0])
    rng = __import__("random").Random(a.seed)
    order = list(range(len(enc)))
    t0 = time.time(); acc_loss = 0.0; acc_margin = 0.0
    for it in range(1, a.iters + 1):
        grads_sum = None; losses = []
        for _ in range(a.pairs_per_step):
            if not order:
                order = list(range(len(enc))); rng.shuffle(order)
            i = order.pop()
            c_ids, r_ids, pl = enc[i]; rc, rr = refs[i]
            loss, grads = vg(model, c_ids, r_ids, pl, rc, rr)
            grads_sum = grads if grads_sum is None else tree_map(lambda x, y: x + y, grads_sum, grads)
            losses.append(loss)
        grads_avg = tree_map(lambda g: g / a.pairs_per_step, grads_sum)
        opt.update(model, grads_avg)
        mx.eval(model.parameters(), opt.state, *losses)
        acc_loss += float(sum(float(l) for l in losses) / len(losses))
        if it % 10 == 0 or it == a.iters:
            print(f"Iter {it}: DPO loss {acc_loss/ (10 if it % 10 == 0 else it % 10 or 10):.4f}, {time.time()-t0:.0f}s", flush=True); acc_loss = 0.0
    out = Path(a.adapter_path); out.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(out / "adapters.safetensors"), dict(tree_flatten(model.trainable_parameters())))
    (out / "adapter_config.json").write_text(json.dumps({"fine_tune_type": "lora", "lora_parameters": lora_cfg, "num_layers": a.num_layers,
                                                          "method": "dpo", "beta": a.beta, "iters": a.iters, "learning_rate": a.lr,
                                                          "pairs": a.pairs, "model": str(Path(a.model).expanduser())}, indent=2))
    print(f"saved adapter to {out}", flush=True)

if __name__ == "__main__":
    main()
