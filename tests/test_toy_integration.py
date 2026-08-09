"""Full-loop integration on the ToyLM: sampler + telemetry over a real
generation loop, no weights involved. The toy alternates peaked (even context
length) and flat (odd) steps, so the entropy gate must alternate in lockstep.
"""

import numpy as np

from creative_machine import AntiprobableSampler, SamplerConfig
from creative_machine.toy import ToyLM


def run_toy(lam: float, seed: int = 0, steps: int = 60) -> tuple[list[int], AntiprobableSampler]:
    toy = ToyLM(seed=0)
    cfg = SamplerConfig(entropy_trigger=2.0, lam=lam, seed=seed)
    s = AntiprobableSampler(cfg, embed_fn=toy.embed)
    ids = [0]
    s.observe(0)
    for _ in range(steps):
        ids.append(s.step(toy.next_logits(ids)))
    return ids, s


def test_gate_alternates_with_toy_entropy():
    ids, s = run_toy(lam=1.5)
    recs = s.telemetry.records
    # step i sees context length 1+i: odd length -> flat -> perturbed
    assert all(r.perturbed == (i % 2 == 0) for i, r in enumerate(recs))
    assert all(0 <= t < 64 for t in ids)


def test_toy_distances_are_structured():
    _, s = run_toy(lam=1.5)
    pert = [r for r in s.telemetry.records if r.perturbed]
    assert np.mean([r.distance for r in pert]) > 0.2  # clusters, not noise
    assert any(r.distance_spread > 0.01 for r in pert)


def test_toy_deterministic_and_lambda_sensitive():
    assert run_toy(lam=1.5)[0] == run_toy(lam=1.5)[0]
    assert run_toy(lam=0.0)[0] != run_toy(lam=3.0)[0]
