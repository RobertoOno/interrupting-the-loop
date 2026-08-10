"""Phase 2 integrator and judge, over an OpenAI-compatible API (OpenRouter).

The couturier model weaves a forced conceptual blend (Fauconnier & Turner:
emergent structure, not comparison); the judge — from a different model
family — scores it and asks the question Phase 1 taught us to ask: is this
an invention, or a recombination of something that already exists?
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_FILE = Path.home() / ".config" / "creative-machine" / "openrouter_key"

COUTURE_SYSTEM = (
    "You are a conceptual blending engine. Given two distant concepts, invent "
    "ONE new thing that could not exist without both — a practice, object, "
    "institution, theory or phenomenon with its own internal logic. Never a "
    "metaphor, simile or comparison; the blend must be a thing in itself. "
    "Answer in 2-4 sentences: name it, define how it works, and state one "
    "non-obvious consequence of its existence."
)

HYBRID_COUTURE_SYSTEM = (
    "You are a conceptual development engine. You receive one surreal "
    "sentence produced by an anti-probable text sampler — an accident, not a "
    "quote. Take it as literally true. FIRST derive the mechanism that would "
    "have to exist for it to be true (2-3 sentences of internal logic, no "
    "hand-waving); THEN name the resulting phenomenon/practice/object; THEN "
    "state one non-obvious consequence. Never treat the sentence as metaphor."
)

JUDGE_SYSTEM = (
    "You are a strict judge of conceptual inventions. Given two source "
    "concepts and a proposed blend, return ONLY a JSON object with keys: "
    '"coherence" (0-10: does the blend have working internal logic?), '
    '"surprise" (0-10: would a domain expert not have thought of this?), '
    '"value" (0-10: is it generative — new questions, uses, consequences?), '
    '"known_equivalent" (name of an existing thing this essentially is, or null), '
    '"verdict" (one blunt sentence). Score harshly; 7+ must be rare.'
)


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
    if not key:
        raise RuntimeError(
            "no OpenRouter key: set OPENROUTER_API_KEY or write the key to "
            f"{KEY_FILE}"
        )
    return key


class OpenRouterClient:
    """Minimal chat-completions client with retry and usage accounting."""

    def __init__(self, api_key: str | None = None, max_retries: int = 4) -> None:
        self.api_key = api_key or get_api_key()
        self.max_retries = max_retries
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, model: str, system: str, user: str, max_tokens: int = 400) -> str:
        body = json.dumps(
            {
                "model": model,
                "max_tokens": max_tokens,
                # Weaving and judging need answers, not chains of thought;
                # some models (kimi-k2.6) reason by default and would spend
                # the whole budget before emitting any content.
                "reasoning": {"enabled": False},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/RobertoOno/creative-machine",
                "X-Title": "creative-machine",
            },
        )
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    out = json.loads(resp.read())
                if "error" in out:
                    raise RuntimeError(f"API error: {out['error']}")
                usage = out.get("usage", {})
                self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
                choice = out["choices"][0]
                content = choice["message"].get("content")
                if not content:
                    raise RuntimeError(
                        f"empty content (finish_reason={choice.get('finish_reason')})"
                    )
                return content
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(3.0 * (attempt + 1))
        raise RuntimeError("unreachable")


def couture(client: OpenRouterClient, model: str, concept_a: str, concept_b: str) -> str:
    return client.chat(
        model, COUTURE_SYSTEM, f"Concepts: {concept_a} + {concept_b}", max_tokens=300
    ).strip()


def couture_seed(client: OpenRouterClient, model: str, seed_sentence: str) -> str:
    """Hybrid path: develop one of our sampler's surreal sentences."""
    return client.chat(
        model, HYBRID_COUTURE_SYSTEM, f"Sentence: {seed_sentence}", max_tokens=350
    ).strip()


def parse_judgment(raw: str) -> dict:
    """Extract the judge's JSON object, tolerating fences and surrounding prose."""
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in judgment: {raw[:120]!r}")
    out = json.loads(match.group(0))
    for k in ("coherence", "surprise", "value"):
        out[k] = float(out[k])
    out.setdefault("known_equivalent", None)
    out.setdefault("verdict", "")
    return out


def judge(client: OpenRouterClient, model: str, source_desc: str, blend_text: str) -> dict:
    raw = client.chat(
        model,
        JUDGE_SYSTEM,
        f"Source: {source_desc}\n\nProposed blend:\n{blend_text}",
        max_tokens=300,
    )
    out = parse_judgment(raw)
    # geometric mean punishes any dimension near zero
    out["score"] = round((out["coherence"] * out["surprise"] * out["value"]) ** (1 / 3), 2)
    return out
