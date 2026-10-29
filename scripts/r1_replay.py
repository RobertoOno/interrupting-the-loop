#!/usr/bin/env python3
"""R1 replay: the model-based checks on the frozen documents (docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md).

    python scripts/r1_replay.py smoke --out runs/r1/smoke                       # one trivial prompt per model, no project text
    python scripts/r1_replay.py c1 --frozen runs/r1/frozen --out runs/r1/c1     # document-only review, six families x 2 runs
    python scripts/r1_replay.py c2 --frozen runs/r1/frozen --out runs/r1/c2     # records-level audit with read-only tools

Rules:
- every request and response goes to raw.jsonl before anything is parsed;
- transport-level retries (throttling, connection) happen inside the SDK, before any answer exists; a call that fails after
  that (for example an overload in mid-stream) is recorded and retried once after 60 s; once a model has answered, nothing is
  rerun, and an unparseable answer stays unparsed;
- each batch reserves its ceiling in the shared daily journal (runs/aws-budget/claude_daily.jsonl) before the first call, and
  settles at the frozen upper-bound rates in MODELS when it ends (these are bounds, not invoices);
- the checkers see the document with LaTeX comments blanked (line structure kept) and, in C2, tools confined to the snapshot.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from creative_machine.aws_daily_budget import DailyBudget  # noqa: E402

ZONE = ZoneInfo("America/Sao_Paulo")
JOURNAL = ROOT / "runs/aws-budget/claude_daily.jsonl"
DOCS = ["P1", "PS", "P2", "P3", "P4", "P6"]
# USD per million tokens. Claude rates are the project's frozen list rates; the others are deliberate upper bounds.
MODELS = {
    "opus": {"api": "mantle", "id": "anthropic.claude-opus-5-5", "family": "Anthropic", "in": 4.40, "out": 22.0,
             "cache_read": 0.44, "cache_write": 5.50, "max_out": 32000},
    "gpt": {"api": "converse", "id": "global.openai.gpt-6.1-sol", "family": "OpenAI", "in": 15.0, "out": 60.0, "max_out": 32000},
    "kimi": {"api": "converse", "id": "global.moonshotai.kimi-k3", "family": "Moonshot", "in": 3.0, "out": 12.0, "max_out": 32000},
    "deepseek": {"api": "converse", "id": "deepseek.v3.2", "family": "DeepSeek", "in": 2.0, "out": 8.0, "max_out": 16000},
    "mistral": {"api": "converse", "id": "mistral.mistral-large-3-675b-instruct", "family": "Mistral", "in": 4.0, "out": 12.0,
                "max_out": 16000},
    "qwen": {"api": "converse", "id": "qwen.qwen3-next-80b-a3b", "family": "Qwen", "in": 2.0, "out": 8.0, "max_out": 16000},
    # matcher and second coder (not checkers)
    "sonnet": {"api": "converse", "id": "us.anthropic.claude-sonnet-5-5", "family": "Anthropic", "in": 3.30, "out": 16.50,
               "max_out": 32000},
}
C1_MODELS = ["opus", "gpt", "kimi", "deepseek", "mistral", "qwen"]
C2_MODELS = ["opus"]
C2_MAX_TOOL_CALLS = 40
C2_MAX_INPUT_TOKENS = 2_000_000     # cumulative, counting cached reads
CEILING = {"smoke": 1.0, "c1": 40.0, "c2": 30.0}

C1_PROMPT = (
    "You are reviewing a research paper (LaTeX source below) before publication. Find errors of any kind: numbers that are "
    "inconsistent within the paper (text against tables or appendix), claims not supported by the reported results, statements "
    "broader than what was measured, contradictions between sections, false or unverifiable statements about the work itself (its "
    "status, the availability of its data or code, its review process), and citation problems. For each problem give: the exact "
    "quote where it occurs (verbatim, at most 40 words); what is wrong; the evidence inside the paper, if any; and the severity "
    "(high: changes a main claim; medium; low). Do not report style or wording preferences. Return a JSON list of objects with the "
    "keys \"quote\", \"problem\", \"evidence\" and \"severity\", and return an empty list if you find nothing."
)
C2_EXTRA = (
    " You also have read-only tools over a snapshot of the project's repository as it was when this version was written (lab "
    "notebook docs/PLANO.md, generated appendices docs/APPENDIX_*.md, scripts, evidence archives). Check every claim you can "
    "against these records, and in \"evidence\" cite the file and line of the contradicting record. You can make at most "
    f"{C2_MAX_TOOL_CALLS} tool calls. When you are done, answer with the JSON list only."
)
C2_FINAL = "Your tool budget is exhausted. Answer now with the JSON list only, from what you have checked."
SMOKE_PROMPT = "Reply with the two characters [] and nothing else."


def now() -> str:
    return datetime.now(ZONE).isoformat(timespec="seconds")


def blank_comments(text: str) -> str:
    """LaTeX comments removed, line structure kept (checkers see what a reader of the PDF would see)."""
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.split("\n"))


def document(frozen: Path, doc: str) -> str:
    """The flattened source with comments blanked, followed by the document's own BibTeX files."""
    text = blank_comments((frozen / doc / "flat.tex").read_text(encoding="utf-8"))
    bibs = sorted((frozen / doc / "src").rglob("*.bib"))
    if bibs:
        text += "\n\n=== BIBLIOGRAPHY (BibTeX source) ===\n" + "\n".join(b.read_text(encoding="utf-8", errors="replace")
                                                                       for b in bibs)
    return text


def parse_findings(text: str):
    """The JSON list in a reply, or None when there is none to parse (recorded as unparsed, never repaired by a retry)."""
    text = text.strip()
    candidates = [text]
    m = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.S)
    if m:
        candidates.append(m.group(1))
    i, j = text.find("["), text.rfind("]")
    if 0 <= i < j:
        candidates.append(text[i:j + 1])
    for c in candidates:
        try:
            val = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(val, list):
            return [f if isinstance(f, dict) else {"problem": str(f)} for f in val]
    return None


def cost(key: str, usage: dict) -> float:
    p = MODELS[key]
    return (usage.get("in", 0) * p["in"] + usage.get("out", 0) * p["out"] + usage.get("cache_read", 0) * p.get("cache_read", p["in"])
            + usage.get("cache_write", 0) * p.get("cache_write", p["in"])) / 1e6


# ------------------------------------------------------------------------------------------------------------------ adapters
class Mantle:
    """Claude through the Anthropic SDK on Bedrock (Mantle), streamed, adaptive thinking, prompt caching on."""

    def __init__(self, key: str):
        from anthropic import AnthropicBedrockMantle
        self.key, self.model = key, MODELS[key]["id"]
        self.client = AnthropicBedrockMantle(aws_profile="main-account", aws_region="us-east-1", max_retries=3, timeout=1800.0)

    def first(self, text):
        return [{"role": "user", "content": text}]

    def step(self, messages, tools=None, max_out=None):
        kw = dict(model=self.model, max_tokens=max_out or MODELS[self.key]["max_out"], messages=messages,
                  thinking={"type": "adaptive"}, cache_control={"type": "ephemeral"})
        if tools:
            kw["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["schema"]} for t in tools]
        with self.client.messages.stream(**kw) as s:
            r = s.get_final_message()
        u = r.usage
        usage = {"in": u.input_tokens, "out": u.output_tokens, "cache_read": u.cache_read_input_tokens or 0,
                 "cache_write": u.cache_creation_input_tokens or 0}
        text = "".join(b.text for b in r.content if b.type == "text")
        calls = [{"id": b.id, "name": b.name, "input": b.input} for b in r.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": r.content})
        return str(r.stop_reason), text, calls, usage, r.model_dump(mode="json")

    def results(self, messages, results):
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": i, "content": out, "is_error": err}
                                                     for i, out, err in results]})

    def say(self, messages, text):
        messages.append({"role": "user", "content": text})


class Converse:
    """Every other family through the Bedrock Converse API."""

    def __init__(self, key: str):
        import boto3
        from botocore.config import Config
        self.key, self.model = key, MODELS[key]["id"]
        self.client = boto3.Session(profile_name="main-account", region_name="us-east-1").client(
            "bedrock-runtime", config=Config(read_timeout=1800, retries={"max_attempts": 4, "mode": "adaptive"}))

    def first(self, text):
        return [{"role": "user", "content": [{"text": text}]}]

    def step(self, messages, tools=None, max_out=None):
        kw = dict(modelId=self.model, messages=messages, inferenceConfig={"maxTokens": max_out or MODELS[self.key]["max_out"]})
        if tools:
            kw["toolConfig"] = {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"],
                                                        "inputSchema": {"json": t["schema"]}}} for t in tools]}
        r = self.client.converse(**kw)
        content = r["output"]["message"]["content"]
        u = r["usage"]
        usage = {"in": u.get("inputTokens", 0), "out": u.get("outputTokens", 0), "cache_read": u.get("cacheReadInputTokens", 0),
                 "cache_write": u.get("cacheWriteInputTokens", 0)}
        text = "".join(b["text"] for b in content if "text" in b)
        calls = [{"id": b["toolUse"]["toolUseId"], "name": b["toolUse"]["name"], "input": b["toolUse"]["input"]}
                 for b in content if "toolUse" in b]
        messages.append({"role": "assistant", "content": content})
        return r["stopReason"], text, calls, usage, {"output": r["output"], "stopReason": r["stopReason"], "usage": r["usage"]}

    def results(self, messages, results):
        messages.append({"role": "user", "content": [{"toolResult": {"toolUseId": i, "content": [{"text": out}],
                                                                     "status": "error" if err else "success"}}
                                                     for i, out, err in results]})

    def say(self, messages, text):
        messages.append({"role": "user", "content": [{"text": text}]})


def adapter(key: str):
    return Mantle(key) if MODELS[key]["api"] == "mantle" else Converse(key)


# ------------------------------------------------------------------------------------------------------- read-only tools
class Snapshot:
    """list_dir / read_file / grep confined to one snapshot directory."""

    TOOLS = [
        {"name": "list_dir", "description": "List a directory of the repository snapshot (directories end with /).",
         "schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        {"name": "read_file", "description": "Read lines start..end (1-based, at most 300 lines) of a file in the snapshot.",
         "schema": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
                                                     "end": {"type": "integer"}}, "required": ["path"]}},
        {"name": "grep", "description": "Search a regular expression (case-insensitive) in the text files under a path; "
                                        "returns file:line: text, at most 100 matches.",
         "schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                    "required": ["pattern"]}},
    ]

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, rel: str) -> Path:
        p = (self.root / (rel or ".").lstrip("/")).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError("path outside the snapshot")
        return p

    def run(self, name: str, args: dict) -> tuple[str, bool]:
        try:
            if name == "list_dir":
                p = self._path(args.get("path", "."))
                items = sorted((c.name + ("/" if c.is_dir() else "")) for c in p.iterdir())
                return "\n".join(items[:300]) + ("\n[... more entries]" if len(items) > 300 else ""), False
            if name == "read_file":
                p = self._path(args["path"])
                lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
                start = max(1, int(args.get("start", 1)))
                end = min(len(lines), int(args.get("end", start + 299)), start + 299)
                body = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
                return body[:60000], False
            if name == "grep":
                rx = re.compile(args["pattern"], re.I)
                base = self._path(args.get("path", "."))
                files = [base] if base.is_file() else sorted(f for f in base.rglob("*") if f.is_file())
                out = []
                for f in files:
                    for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                        if rx.search(line):
                            out.append(f"{f.relative_to(self.root)}:{n}: {line[:300]}")
                            if len(out) >= 100:
                                return "\n".join(out) + "\n[... stopped at 100 matches]", False
                return "\n".join(out) or "[no matches]", False
            return f"unknown tool {name}", True
        except Exception as e:  # tool errors go back to the model as errors; they never stop the session
            return f"error: {type(e).__name__}: {e}", True


# ---------------------------------------------------------------------------------------------------------------- batches
class Log:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = path.open("a", encoding="utf-8")

    def __call__(self, row: dict):
        self.f.write(json.dumps({"at": now(), **row}, ensure_ascii=False, default=str) + "\n")
        self.f.flush()


def run_c1_cell(key: str, doc: str, run: int, frozen: Path, out: Path, log: Log) -> dict:
    cell = f"c1_{key}_{doc}_r{run}"
    ad = adapter(key)
    prompt = C1_PROMPT + "\n\n=== PAPER (LaTeX source) ===\n" + document(frozen, doc)
    messages = ad.first(prompt)
    log({"event": "request", "cell": cell, "model": MODELS[key]["id"], "prompt_chars": len(prompt)})
    t0 = time.time()
    for attempt in (1, 2):
        try:
            stop, text, _, usage, raw = ad.step(messages)
            break
        except Exception as e:
            log({"event": "call_error", "cell": cell, "attempt": attempt, "error": f"{type(e).__name__}: {e}"})
            if attempt == 2:
                res = {"cell": cell, "model": key, "doc": doc, "run": run, "status": "call_error", "usage": {}, "usd": 0.0,
                       "error": f"{type(e).__name__}: {str(e)[:300]}"}
                (out / f"{cell}.json").write_text(json.dumps(res, indent=1))
                return res
            time.sleep(60)
            messages = ad.first(prompt)
    log({"event": "response", "cell": cell, "stop": stop, "usage": usage, "seconds": round(time.time() - t0, 1), "raw": raw})
    findings = parse_findings(text)
    res = {"cell": cell, "model": key, "doc": doc, "run": run, "status": "ok" if findings is not None else "unparsed",
           "stop": stop, "n_findings": None if findings is None else len(findings), "findings": findings, "text": text,
           "usage": usage, "usd": round(cost(key, usage), 4)}
    (out / f"{cell}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def run_c2_cell(key: str, doc: str, frozen: Path, out: Path, log: Log) -> dict:
    cell = f"c2_{key}_{doc}"
    ad = adapter(key)
    snap = Snapshot(frozen / doc / "snapshot")
    prompt = C1_PROMPT + C2_EXTRA + "\n\n=== PAPER (LaTeX source) ===\n" + document(frozen, doc)
    messages = ad.first(prompt)
    total = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    calls_made, text, stop = 0, "", ""
    log({"event": "request", "cell": cell, "model": MODELS[key]["id"], "prompt_chars": len(prompt)})
    try:
        while True:
            budget_left = calls_made < C2_MAX_TOOL_CALLS and (total["in"] + total["cache_read"]) < C2_MAX_INPUT_TOKENS
            stop, text, calls, usage, raw = ad.step(messages, tools=Snapshot.TOOLS)
            for k in total:
                total[k] += usage.get(k, 0)
            log({"event": "response", "cell": cell, "stop": stop, "usage": usage, "n_calls": len(calls), "raw": raw})
            if not calls:
                break
            if not budget_left:
                ad.results(messages, [(c["id"], "tool budget exhausted", True) for c in calls])
                ad.say(messages, C2_FINAL)
                stop, text, _, usage, raw = ad.step(messages, tools=Snapshot.TOOLS)
                for k in total:
                    total[k] += usage.get(k, 0)
                log({"event": "final", "cell": cell, "stop": stop, "usage": usage, "raw": raw})
                break
            results = []
            for c in calls:
                calls_made += 1
                body, err = snap.run(c["name"], c["input"])
                log({"event": "tool", "cell": cell, "n": calls_made, "name": c["name"], "input": c["input"], "error": err,
                     "chars": len(body)})
                results.append((c["id"], body, err))
            ad.results(messages, results)
    except Exception as e:
        log({"event": "transport_error", "cell": cell, "error": f"{type(e).__name__}: {e}", "usage_so_far": total})
        res = {"cell": cell, "status": "transport_error", "usage": total, "usd": round(cost(key, total), 4)}
        (out / f"{cell}.json").write_text(json.dumps(res, indent=1))
        return res
    findings = parse_findings(text)
    res = {"cell": cell, "model": key, "doc": doc, "status": "ok" if findings is not None else "unparsed", "stop": stop,
           "tool_calls": calls_made, "n_findings": None if findings is None else len(findings), "findings": findings,
           "text": text, "usage": total, "usd": round(cost(key, total), 4)}
    (out / f"{cell}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def batch(kind: str, out: Path, cells, run_cell, label: str = "", ceiling: float | None = None) -> None:
    """One budgeted batch. `label` and `ceiling` let a pre-registered batch run as parallel parts (operational amendment 1 of
    docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V1.md): each part has its own run id and a share of the batch's ceiling."""
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} is not empty; every R1 batch runs once, into a fresh directory")
    out.mkdir(parents=True, exist_ok=True)
    cap = CEILING[kind] if ceiling is None else min(ceiling, CEILING[kind])
    run_id = f"r1-{kind}{'-' + label if label else ''}-{datetime.now(ZONE).strftime('%Y%m%dT%H%M%S')}"
    budget = DailyBudget(JOURNAL)
    budget.reserve(run_id, cap)
    log = Log(out / "raw.jsonl")
    log({"event": "batch_start", "run_id": run_id, "ceiling_usd": cap, "cells": len(cells)})
    spent, results = 0.0, []
    try:
        for c in cells:
            if spent >= 0.8 * cap:
                log({"event": "ceiling_margin_reached", "spent_usd": spent})
                break
            r = run_cell(*c, log)
            spent += r.get("usd", 0.0)
            results.append({k: v for k, v in r.items() if k not in ("findings", "text")})
            print(json.dumps(results[-1]), flush=True)
    finally:
        log({"event": "batch_end", "spent_usd_upper_bound": round(spent, 4)})
        (out / "summary.json").write_text(json.dumps({"run_id": run_id, "spent_usd_upper_bound": round(spent, 4),
                                                      "cells": results}, indent=1))
        budget.settle(run_id, round(spent, 4))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["smoke", "c1", "c2"])
    ap.add_argument("--frozen", type=Path, default=ROOT / "runs/r1/frozen")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--docs", nargs="*", default=DOCS)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--label", default="")
    ap.add_argument("--ceiling", type=float)
    a = ap.parse_args()
    out = a.out.resolve()
    if a.kind == "smoke":
        keys = a.models or list(MODELS)

        def smoke_cell(key, log):
            ad = adapter(key)
            try:
                stop, text, _, usage, raw = ad.step(ad.first(SMOKE_PROMPT))
            except Exception as e:
                log({"event": "transport_error", "model": key, "error": f"{type(e).__name__}: {e}"})
                return {"model": key, "status": "transport_error", "error": f"{type(e).__name__}: {str(e)[:300]}", "usd": 0.0}
            log({"event": "response", "model": key, "stop": stop, "usage": usage, "raw": raw})
            return {"model": key, "status": "ok", "stop": stop, "text": text[:200], "usage": usage,
                    "usd": round(cost(key, usage), 5)}
        batch("smoke", out, [(k,) for k in keys], smoke_cell)
    elif a.kind == "c1":
        keys = a.models or C1_MODELS
        cells = [(k, d, r) for r in range(1, a.runs + 1) for k in keys for d in a.docs]
        batch("c1", out, cells, lambda k, d, r, log: run_c1_cell(k, d, r, a.frozen.resolve(), out, log), a.label, a.ceiling)
    else:
        keys = a.models or C2_MODELS
        cells = [(k, d) for k in keys for d in a.docs]
        batch("c2", out, cells, lambda k, d, log: run_c2_cell(k, d, a.frozen.resolve(), out, log), a.label, a.ceiling)


if __name__ == "__main__":
    main()
