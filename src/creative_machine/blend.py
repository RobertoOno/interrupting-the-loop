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

DEVELOP_SYSTEM = (
    "You are an idea-development engine. You receive an input context. Develop "
    "from it ONE new idea — a mechanism, practice, object, institution, theory "
    "or phenomenon with working internal logic. FIRST derive the mechanism "
    "(2-3 sentences, no hand-waving); THEN name it; THEN state one "
    "non-obvious consequence. Take everything in the input as material to "
    "build from, however strange; never dismiss or normalize it."
)

REVERIE_JUDGE_SYSTEM = (
    "You judge a stretch of a language model's unsupervised reverie — text it "
    "generated with no task, feeding on its own output. You see the RECENT "
    "window and the EARLIER text. Return ONLY a JSON object with keys: "
    '"coherence" (0-10: does the recent window hold together?), '
    '"connects_distant" (0-10: does it bring together two regions of the '
    "earlier text that were far apart, or a region of it with something "
    "new, in a way that makes sense — 0 if it merely continues one thread "
    "or copies a document form like a web page/quiz/citation), "
    '"nearest_equivalent" (closest existing idea or trope — always name one), '
    '"novel_delta" (what the window adds over that, or null), '
    '"delta_significance" (0-10; 0 when novel_delta is null), '
    '"verdict" (one blunt sentence). Score harshly; 7+ must be rare.'
)

JUDGE_SYSTEM = (
    "You are a strict judge of conceptual inventions. Every idea has "
    "relatives; what matters is the delta over the nearest one (blockchain "
    "had ledgers and gossip protocols as relatives — the delta was removing "
    "the central authority). Return ONLY a JSON object with keys: "
    '"coherence" (0-10: does the blend have working internal logic?), '
    '"nearest_equivalent" (the closest existing thing — always name one), '
    '"novel_delta" (what the blend genuinely adds over that nearest thing, '
    "or null if it adds nothing but vocabulary), "
    '"delta_significance" (0-10: how consequential that delta would be if '
    "real; 0 when novel_delta is null), "
    '"value" (0-10: generative — new questions, uses, consequences?), '
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


class BedrockClient:
    """Claude via Amazon Bedrock (Mantle), same .chat() contract as OpenRouterClient.

    Credentials come from the AWS profile/env (SigV4) — nothing stored here.
    Model ids carry the `anthropic.` prefix (e.g. anthropic.claude-opus-5).
    """

    def __init__(self, aws_region: str = "us-east-1", effort: str = "high") -> None:
        from anthropic import AnthropicBedrockMantle

        self._client = AnthropicBedrockMantle(aws_region=aws_region)
        self.effort = effort
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, model: str, system: str, user: str, max_tokens: int = 400) -> str:
        # Adaptive thinking on Opus 5 shares max_tokens with the answer, so
        # give it real headroom regardless of the caller's small budgets.
        response = self._client.messages.create(
            model=model,
            max_tokens=max(max_tokens, 4000),
            system=system,
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": user}],
        )
        self.usage["prompt_tokens"] += response.usage.input_tokens
        self.usage["completion_tokens"] += response.usage.output_tokens
        if response.stop_reason == "refusal":
            raise RuntimeError("model refused (stop_reason=refusal)")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise RuntimeError(f"empty content (stop_reason={response.stop_reason})")
        return text


def couture(client: OpenRouterClient, model: str, concept_a: str, concept_b: str) -> str:
    return client.chat(
        model, COUTURE_SYSTEM, f"Concepts: {concept_a} + {concept_b}", max_tokens=300
    ).strip()


def develop(client, model: str, input_text: str) -> str:
    """Improbable-input experiment: same task for every arm, only the input differs."""
    return client.chat(model, DEVELOP_SYSTEM, f"Input:\n{input_text}", max_tokens=500).strip()


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
    for k in ("coherence", "delta_significance", "value"):
        out[k] = float(out[k])
    out.setdefault("nearest_equivalent", None)
    out.setdefault("novel_delta", None)
    out.setdefault("verdict", "")
    return out


def judge_reverie(client, model: str, window_text: str, earlier_text: str) -> dict:
    """The Review step of the reverie loop: three questions on the recent window."""
    raw = client.chat(
        model,
        REVERIE_JUDGE_SYSTEM,
        f"EARLIER TEXT:\n{earlier_text}\n\nRECENT WINDOW:\n{window_text}",
        max_tokens=600,
    )
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in judgment: {raw[:120]!r}")
    out = json.loads(match.group(0))
    for k in ("coherence", "connects_distant", "delta_significance"):
        out[k] = float(out.get(k, 0))
    out.setdefault("nearest_equivalent", None)
    out.setdefault("novel_delta", None)
    out.setdefault("verdict", "")
    out["score"] = round(
        (out["coherence"] * out["connects_distant"] * out["delta_significance"]) ** (1 / 3), 2
    )
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
    out["score"] = round(
        (out["coherence"] * out["delta_significance"] * out["value"]) ** (1 / 3), 2
    )
    return out
