"""Session loop for an OpenAI-compatible endpoint (vLLM on a pod), in two modes.

`tool` (default) mirrors `run_bedrock_session` exactly in protocol: same system prompt, same single `check_solution`
tool, one tool call per turn, the same Lean checker, the same statuses and session record fields.

`prover` (A2 Mathlib pilot, 2026-09-13) serves whole-proof provers (Pythagoras-Prover, Goedel-Prover-V2) that were
trained on ONE template and no tools: the user turn is their native "Complete the following Lean 4 code" prompt with
the world's definitions inlined (Mathlib environment) and the target as an unfolded theorem statement; the answer's
LAST fenced Lean block is transplanted into Solution.lean (namespace wrapper, the same header, auxiliary declarations
kept, re-emitted definitions dropped) and submitted through the SAME checker, whose audit accepts the unfolded
statement by definitional equality; a rejection returns as a plain-text feedback turn. Turn limit, output budget,
statuses and the session record are those of tool mode. A worked example (the SOURCE.md of the example arms)
precedes the template as text, since a prover has no file system.

Differences from Bedrock in both modes: no prior token count (usage is read from the response), no per-token cost
(the GPU is accounted per hour by the launcher), sampling parameters recorded in the config. A 400 answer that names
the context window ends the session as `budget_exhausted` (an observed failed attempt), not as an infrastructure
failure. `post` is injectable for offline tests; production posts JSON with httpx (SSE streaming by default).
"""
from __future__ import annotations
import json, re, subprocess, time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .bedrock_runner import SOLUTION_TOOL, SYSTEM_PROMPT, render_workspace
from .lean_sandbox import sandbox_process
from .submission import EvaluationReport, STANDARD_LEAN_AXIOMS, verify_evaluator_solution
from .workspace import WorkspaceRecord, audit_workspace


@dataclass(frozen=True)
class OpenAIAgentConfig:
    base_url: str                      # e.g. https://<pod>-8000.proxy.runpod.net/v1
    model: str                         # served model name
    provider: str = "openai_compatible"
    max_turns: int = 12
    timeout_seconds: float = 600.0
    request_timeout_seconds: float = 300.0
    max_output_tokens: int = 8192      # session cap
    output_per_request: int = 8192
    temperature: float = 0.7
    top_p: float = 0.8
    api_key: str = "EMPTY"
    stream: bool = True                # SSE streaming through the proxy; assembled into the non-streaming shape
    mode: str = "tool"                 # "tool" | "prover"
    check_timeout_seconds: float = 60.0   # Lean checker per submission (Mathlib worlds take ~3x the Std time)
    extra_body: dict = field(default_factory=dict)   # request fields passed through (e.g. reasoning_effort); recorded


class ContextOverflow(RuntimeError):
    """The endpoint refused the request because the conversation exceeds the model's context window."""


OPENAI_TOOL = {"type": "function", "function": {"name": SOLUTION_TOOL["name"], "description": SOLUTION_TOOL["description"],
                                                "parameters": SOLUTION_TOOL["input_schema"]}}

# ---------------------------------------------------------------------------------------------- prover mode
PROVER_HEADER = "import Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\nopen BigOperators Real Nat Topology Rat\n"
PROVER_TEMPLATE = ("Complete the following Lean 4 code:\n\n```lean4\n{formal}```\n\n"
                   "Before producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan "
                   "outlining the main proof steps and strategies.")
PROVER_EXAMPLE_NOTE = ("Below is a worked example: a separate formal problem and its complete proof, supplied for reference. "
                       "It may or may not be useful for the target that follows it.\n\n")
PROVER_CONTENT_NOTE = "Below is a mathematical hint about the target, in prose, with no Lean code.\n\n"
PROVER_FEEDBACK = ("The proof was rejected by Lean 4:\n\n{feedback}\n\nFix the proof and provide the complete corrected Lean 4 "
                   "code in a single ```lean4 code block, keeping the theorem statement unchanged.")
PROVER_FEEDBACK_CHARS = 6000
_SKIP_LINE = re.compile(r"^\s*(import|namespace|section|end)\b")


def world_context(workspace: Path) -> dict:
    """Definitions and unfolded target of a staged world, for the prover prompt: Base.lean without its import and
    namespace lines (a Mathlib-environment world is required), the namespace, and the Prop behind LadderStatement."""
    workspace = Path(workspace)
    base = (workspace / "World/Base.lean").read_text(encoding="utf-8")
    target = (workspace / "World/ChallengeEvaluation.lean").read_text(encoding="utf-8")
    if not re.search(r"^import Mathlib\s*$", base, re.M):
        raise ValueError("prover mode needs a Mathlib-environment world (World/Base.lean must import Mathlib)")
    m = re.search(r"^namespace (\S+)\s*$", base, re.M)
    if not m:
        raise ValueError("World/Base.lean without a namespace")
    ns = m.group(1); body = base[m.end():]; end = body.rfind(f"\nend {ns}")
    if end < 0:
        raise ValueError("World/Base.lean without the closing end")
    s = re.search(r"^def LadderStatement : Prop :=\n(.*?)\n\nend ", target, re.M | re.S)
    if not s:
        raise ValueError("World/ChallengeEvaluation.lean without LadderStatement")
    return {"namespace": ns, "definitions": body[:end].strip("\n") + "\n",
            "statement": " ".join(line.strip() for line in s.group(1).splitlines()).strip()}


def render_prover_prompt(record: WorkspaceRecord) -> str:
    """The user turn of prover mode: (example or hint text, if the arm has one) + the native template with the world's
    definitions and `theorem evaluation_solution : <unfolded statement> := by` to complete."""
    ctx = world_context(record.path)
    formal = f"{PROVER_HEADER}\n{ctx['definitions']}\ntheorem evaluation_solution : {ctx['statement']} := by\n"
    pre = ""
    src = Path(record.path) / "SOURCE.md"
    if src.exists():
        pre = (PROVER_CONTENT_NOTE if record.condition == "content" else PROVER_EXAMPLE_NOTE) + src.read_text(encoding="utf-8").rstrip("\n") + "\n\n"
    return pre + PROVER_TEMPLATE.format(formal=formal)


def extract_from_reasoning(reasoning: str, ctx: dict) -> tuple[str | None, bool, str]:
    """E5 (replication, 2026-09-14): with thinking on, an adapter trained without thinking may write the whole Lean file inside
    the reasoning and leave the content empty. Fallback, used only when the content yields no submission: the last fenced
    block of the reasoning; else the segment from the LAST `import Mathlib` line (the final file the model wrote), through
    the same extraction rule."""
    if not reasoning:
        return None, False, "no reasoning text"
    if "```" in reasoning:
        src, found, why = extract_prover_solution(reasoning, ctx)
        if found:
            return src, found, why
    i = reasoning.rfind("import Mathlib")
    if i < 0:
        return None, False, "no Lean file in the reasoning"
    return extract_prover_solution(reasoning[i:], ctx)


def extract_prover_solution(content: str, ctx: dict) -> tuple[str | None, bool, str]:
    """Solution.lean built from the LAST fenced Lean block of a prover answer, or from the whole answer when it has no
    fence but declares the theorem (E1): (source, block_found, reason).
    Kept: everything from the last `theorem/lemma evaluation_solution` line to the end of the block (a rewritten
    statement is settled by the audit's #check), and the earlier lines that are neither header lines (import,
    namespace, section, end) nor re-emitted lines of the world's definitions or of the prover header (compared with
    whitespace stripped). A trailing `end` and blank lines are dropped. The file imports only
    World.ChallengeEvaluation, repeats the header's set_option/open lines and wraps everything in the namespace."""
    blocks = re.findall(r"```(?:lean4|lean)?[ \t]*\n(.*?)```", content, re.S)
    thm_line = re.compile(r"\s*(theorem|lemma)\s+evaluation_solution\b")
    if not blocks:
        # amendment E1 (2026-09-13, before any cell): Pythagoras-Prover answers with the completed file as plain text, no
        # fence and no prose plan; an unfenced answer that declares the theorem is taken whole as the block
        if not any(thm_line.match(l) for l in content.splitlines()):
            return None, False, "no fenced Lean code block in the answer"
        blocks = [content]
    lines = blocks[-1].splitlines()
    idx = [i for i, l in enumerate(lines) if thm_line.match(l)]
    if not idx:
        return None, True, "the code block does not declare theorem evaluation_solution"
    i0 = idx[-1]
    known = {l.strip() for l in ctx["definitions"].splitlines()} | {l.strip() for l in PROVER_HEADER.splitlines()}
    aux = [l for l in lines[:i0] if l.strip() and l.strip() not in known and not _SKIP_LINE.match(l)]
    thm = lines[i0:]
    while thm and (not thm[-1].strip() or re.match(r"\s*end\b", thm[-1])):
        thm.pop()
    header = "".join(l + "\n" for l in PROVER_HEADER.splitlines() if not l.startswith("import"))
    source = ("import World.ChallengeEvaluation\n\n" + header + f"\nnamespace {ctx['namespace']}\n\n"
              + ("\n".join(aux) + "\n\n" if aux else "") + "\n".join(thm) + f"\n\nend {ctx['namespace']}\n")
    return source, True, "ok"


# ----------------------------------------------------------------------------------------------- transport
def _append(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _raise_for_status(r) -> None:
    import httpx
    if r.status_code < 400:
        return
    try:
        r.read()
    except Exception:  # noqa: BLE001 - the body is only for the message
        pass
    text = (r.text or "")[:1000]
    if r.status_code == 400 and re.search(r"context length|maximum context|max_model_len|longer than the maximum", text, re.I):
        raise ContextOverflow(text)
    raise httpx.HTTPStatusError(f"HTTP {r.status_code}: {text[:300]}", request=r.request, response=r)


def http_post(url: str, body: dict, *, timeout: float, api_key: str) -> dict:
    import httpx
    r = httpx.post(url, json=body, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})
    _raise_for_status(r)
    return r.json()


def assemble_stream(lines) -> dict:
    """Rebuild a non-streaming chat.completions payload from SSE `data:` lines (OpenAI/vLLM chunk format): text and
    reasoning deltas (`reasoning_content` or, in newer builds, `reasoning`) are concatenated into `reasoning_content`,
    tool-call fragments are merged by index, usage comes from the final chunk."""
    import json as _json
    content, reasoning, calls, finish, model, usage = [], [], {}, None, "", {}
    for raw in lines:
        line = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = _json.loads(data); model = chunk.get("model") or model
        if chunk.get("usage"):
            usage = chunk["usage"]
        for ch in chunk.get("choices") or []:
            d = ch.get("delta") or {}
            if d.get("content"):
                content.append(d["content"])
            if d.get("reasoning_content"):
                reasoning.append(d["reasoning_content"])
            if d.get("reasoning"):   # newer vLLM builds (2026-09) stream the thinking as `reasoning` (E5)
                reasoning.append(d["reasoning"])
            for tc in d.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", 0), {"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    msg = {"role": "assistant", "content": "".join(content)}
    if reasoning:
        msg["reasoning_content"] = "".join(reasoning)
    if calls:
        msg["tool_calls"] = [calls[i] for i in sorted(calls)]
    return {"model": model, "choices": [{"message": msg, "finish_reason": finish}], "usage": usage}


STREAM_READ_GAP_S = 600.0   # longest silence accepted between two chunks of a stream (A9 E2, 19/09); CM_STREAM_READ_GAP_S overrides


def _keepalive_options() -> list:
    """TCP keepalive on the client socket, so that a connection that died silently (NAT reset, Wi-Fi roam: on 19/09 twelve
    streams went deaf at the same second and were only noticed by the 2 400 s read timeout) is aborted by the OS in about
    a minute. Probe after 30 s idle, every 10 s, 3 failures."""
    import socket
    opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    idle = getattr(socket, "TCP_KEEPIDLE", None) or getattr(socket, "TCP_KEEPALIVE", 0x10)   # 0x10 = TCP_KEEPALIVE on macOS
    opts.append((socket.IPPROTO_TCP, idle, 30))
    if hasattr(socket, "TCP_KEEPINTVL"):
        opts.append((socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10))
    if hasattr(socket, "TCP_KEEPCNT"):
        opts.append((socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3))
    return opts


def http_post_stream(url: str, body: dict, *, timeout: float, api_key: str) -> dict:
    """Streaming variant: keeps the proxy connection alive during long generations (RunPod's proxy cuts idle
    responses near 100 s), then returns the same payload shape as `http_post`. A stream sends chunks while the model
    generates, so the silence accepted BETWEEN chunks is capped (STREAM_READ_GAP_S) instead of being the whole request
    timeout, and the socket carries TCP keepalive; a failure here is an infrastructure failure for the caller, as before."""
    import os
    import httpx
    gap = min(float(timeout), float(os.environ.get("CM_STREAM_READ_GAP_S") or STREAM_READ_GAP_S))
    req = {**body, "stream": True, "stream_options": {"include_usage": True}}
    try:
        transport = httpx.HTTPTransport(socket_options=_keepalive_options())
    except TypeError:   # an httpx without socket_options: keep the capped read gap only
        transport = httpx.HTTPTransport()
    with httpx.Client(transport=transport, timeout=httpx.Timeout(timeout, read=gap)) as client:
        with client.stream("POST", url, json=req, headers={"Authorization": f"Bearer {api_key}"}) as r:
            _raise_for_status(r)
            return assemble_stream(r.iter_lines())


# ------------------------------------------------------------------------------------------------- session
def run_openai_session(record: WorkspaceRecord, *, namespace: str, statement: str, bridge_supplied: bool, artifacts: Path,
                       config: OpenAIAgentConfig, post: Callable | None = None, checker: Callable | None = None) -> dict:
    if config.mode not in ("tool", "prover"):
        raise ValueError(f"unknown session mode {config.mode!r}")
    prover = config.mode == "prover"
    artifacts.mkdir(parents=True, exist_ok=False)
    if prover:
        ctx = world_context(record.path)
        messages = [{"role": "user", "content": render_prover_prompt(record)}]
        (artifacts / "input.json").write_text(json.dumps({"mode": "prover", "messages": messages, "config": asdict(config), "world_context": ctx},
                                                         ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        ctx = None
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": render_workspace(record)}]
        (artifacts / "input.json").write_text(json.dumps({"mode": "tool", "system": SYSTEM_PROMPT, "tools": [OPENAI_TOOL], "messages": messages[1:],
                                                          "config": asdict(config)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    events = artifacts / "events.jsonl"
    post = post or (http_post_stream if config.stream else http_post)
    started = time.monotonic(); deadline = started + config.timeout_seconds
    usage = {"input_tokens": 0, "output_tokens": 0}
    checks = []; status = "turn_limit"; error = None; requests_made = 0; uncertain = False; models = []; output_used = 0

    def limited_process(command, **kwargs):
        kwargs["timeout"] = max(0.01, min(kwargs.get("timeout", 60), deadline - time.monotonic()))
        return sandbox_process(command, **kwargs)

    def check(source: str):
        (record.path / "Solution.lean").write_text(source, encoding="utf-8")
        if checker is not None:
            return checker(source)
        return verify_evaluator_solution(record.path, namespace=namespace, statement=statement, bridge_supplied=bridge_supplied,
                                         timeout_s=config.check_timeout_seconds, process_runner=limited_process, allowed_axioms=STANDARD_LEAN_AXIOMS)

    def submit(source: str):
        """(report, fatal): the checker's verdict, or the infrastructure error that ends the session."""
        if len(source.encode()) > 100_000:
            return EvaluationReport(errors=["solution exceeds the 100000-byte source limit"]), None
        try:
            return check(source), None
        except subprocess.TimeoutExpired:
            return EvaluationReport(errors=["Lean verification timeout"]), None
        except Exception as exc:  # noqa: BLE001 - recorded as an infrastructure failure
            return None, f"checker: {type(exc).__name__}: {exc}"

    for turn in range(1, config.max_turns + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "timeout"; break
        max_tokens = min(config.output_per_request, config.max_output_tokens - output_used)
        if max_tokens < 256:
            status = "budget_exhausted"; break
        body = {"model": config.model, "messages": messages, "max_tokens": max_tokens, "temperature": config.temperature, "top_p": config.top_p,
                **config.extra_body}
        if not prover:
            body.update({"tools": [OPENAI_TOOL], "tool_choice": "auto"})
        _append(events, {"event": "request", "turn": turn, "max_tokens": max_tokens, "body": body})
        requests_made += 1
        try:
            payload = post(f"{config.base_url.rstrip('/')}/chat/completions", body, timeout=min(config.request_timeout_seconds, remaining), api_key=config.api_key)
        except ContextOverflow as exc:
            status, error = "budget_exhausted", f"context window: {str(exc)[:300]}"; break
        except Exception as exc:  # noqa: BLE001 - any transport error is an uncertain request
            status, error, uncertain = "infrastructure_failure", f"inference: {type(exc).__name__}: {exc}", True; break
        _append(events, {"event": "response", "turn": turn, "body": payload})
        u = payload.get("usage") or {}
        try:
            pi, po = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
        except (TypeError, ValueError):
            status, error = "infrastructure_failure", "usage missing"; break
        usage["input_tokens"] += pi; usage["output_tokens"] += po; output_used += po
        models.append(payload.get("model", ""))
        choice = (payload.get("choices") or [{}])[0]; msg = choice.get("message") or {}
        assistant = {"role": "assistant", "content": msg.get("content") or ""}
        if prover:
            messages.append(assistant)
            if choice.get("finish_reason") == "length":   # cut at the cap: an incomplete file is not a submission (as in tool mode)
                _append(events, {"event": "no_submission", "turn": turn, "reason": "truncated at max_tokens"})
                status = "output_limit"; break
            source, found, why = extract_prover_solution(assistant["content"], ctx)
            if not found and msg.get("reasoning_content"):   # E5: the file may live in the thinking
                source, found, why = extract_from_reasoning(msg["reasoning_content"], ctx)
                if found:
                    _append(events, {"event": "submission_from_reasoning", "turn": turn})
            if not found:
                _append(events, {"event": "no_submission", "turn": turn, "reason": why})
                status = "output_limit" if choice.get("finish_reason") == "length" else "unsolved"; break
            if source is None:
                report, fatal = EvaluationReport(errors=[why]), None
            else:
                report, fatal = submit(source)
            if fatal:
                status, error = "infrastructure_failure", fatal; break
            rec = asdict(report); checks.append(rec); _append(events, {"event": "verification", "turn": turn, "report": rec, "source": source})
            if report.ok:
                status = "solved"; break
            feedback = "\n".join(report.errors) + "\n" + (report.stdout + "\n" + report.stderr).strip()
            messages.append({"role": "user", "content": PROVER_FEEDBACK.format(feedback=feedback[-PROVER_FEEDBACK_CHARS:])})
            continue
        calls = msg.get("tool_calls") or []
        if calls:
            assistant["tool_calls"] = calls
        messages.append(assistant)
        if not calls:
            status = "output_limit" if choice.get("finish_reason") == "length" else "unsolved"; break
        if len(calls) != 1 or (calls[0].get("function") or {}).get("name") != SOLUTION_TOOL["name"]:
            status = "protocol_violation"; break
        call = calls[0]
        try:
            args = json.loads((call.get("function") or {}).get("arguments") or "")
        except json.JSONDecodeError:
            args = None
        if not isinstance(args, dict) or set(args) != {"source"} or not isinstance(args.get("source"), str):
            report, fatal = EvaluationReport(errors=["check_solution requires exactly a string source"]), None
        else:
            report, fatal = submit(args["source"])
        if fatal:
            status, error = "infrastructure_failure", fatal; break
        rec = asdict(report); checks.append(rec); _append(events, {"event": "verification", "turn": turn, "report": rec})
        feedback = {"ok": report.ok, "errors": report.errors, "compiler_output": (report.stdout + "\n" + report.stderr)[-20000:]}
        if report.ok:
            status = "solved"; break
        messages.append({"role": "tool", "tool_call_id": call.get("id", f"call_{turn}"), "content": json.dumps(feedback)})
    audit_errors = audit_workspace(record)
    if audit_errors:
        status = "protocol_violation"
    result = {"status": status, "target_solved": status == "solved", "requests": requests_made, "submissions": len(checks), "mode": config.mode,
              "infrastructure_failure": status == "infrastructure_failure", "error": error, "uncertain_request": uncertain,
              "tokens": usage, "cost_usd_at_published_rates": 0.0, "cost_basis": "open model on a rented GPU; hours accounted by the launcher, not per token",
              "provider": config.provider, "base_url": config.base_url, "elapsed_seconds": time.monotonic() - started,
              "verification": checks, "workspace_audit_errors": audit_errors, "reported_models": models}
    (artifacts / "session.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
