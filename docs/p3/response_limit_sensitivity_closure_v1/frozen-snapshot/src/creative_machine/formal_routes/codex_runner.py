"""Reproducible, least-privilege Codex CLI adapter for Program 3.

This module is deliberately provider-specific.  It builds a fresh one-turn Codex
process, restricts command reads to the exact experimental workspace plus the Lean
runtime, disables command network access and optional external tools, and preserves
the complete JSONL event stream outside the agent-visible workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_PROMPT = (
    "Read TASK.md and complete the task exactly. Use the local Lean toolchain to check "
    "your final answer. Work only inside this workspace, do not use external information, "
    "and do not ask questions."
)
PERMISSION_PROFILE = "p3_cell"


@dataclass(frozen=True)
class CodexAgentConfig:
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    expected_cli_version: str | None = None
    prompt: str = DEFAULT_PROMPT
    codex_executable: str = "codex"


@dataclass
class CodexSessionResult:
    command: list[str]
    returncode: int | None
    timed_out: bool
    elapsed_seconds: float
    stdout: str
    stderr: str
    events: list[dict[str, Any]] = field(default_factory=list)
    event_errors: list[str] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)
    lean_calls: list[dict[str, Any]] = field(default_factory=list)
    turn_started: bool = False


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_digest(copied_hashes: dict[str, str]) -> str:
    """Hash the exact relative-path/hash inventory exposed to one agent."""
    payload = json.dumps(
        sorted(copied_hashes.items()),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def output_hashes(workspace: Path | str, allowed_outputs: tuple[str, ...]) -> dict[str, str]:
    root = Path(workspace)
    return {
        rel: sha256_file(root / rel)
        for rel in allowed_outputs
        if (root / rel).is_file() and not (root / rel).is_symlink()
    }


def prompt_sha256(prompt: str = DEFAULT_PROMPT) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def resolve_codex(executable: str = "codex") -> Path:
    resolved = shutil.which(executable)
    if not resolved:
        raise FileNotFoundError(f"Codex executable not found: {executable}")
    return Path(resolved).resolve()


def codex_cli_version(executable: str = "codex") -> str:
    binary = resolve_codex(executable)
    proc = subprocess.run(
        [str(binary), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "codex --version failed")
    return proc.stdout.strip()


def _toml_string(value: str) -> str:
    # JSON double-quoted strings are valid TOML basic strings for these paths/values.
    return json.dumps(value, ensure_ascii=True)


def filesystem_profile_override(workspace: Path | str) -> str:
    workspace = Path(workspace).resolve()
    entries: list[tuple[str, str]] = [
        (":root", "deny"),
        (":minimal", "read"),
        (str(workspace), "write"),
    ]
    elan = Path.home() / ".elan"
    if elan.exists():
        entries.append((str(elan), "read"))
    homebrew = Path("/opt/homebrew")
    if homebrew.exists():
        entries.append((str(homebrew), "read"))
    body = ",".join(f"{_toml_string(key)}={_toml_string(value)}" for key, value in entries)
    return f"permissions.{PERMISSION_PROFILE}.filesystem={{{body}}}"


def build_codex_command(
    workspace: Path | str,
    last_message_path: Path | str,
    config: CodexAgentConfig,
) -> list[str]:
    """Build the exact one-turn command without invoking a model."""
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    binary = resolve_codex(config.codex_executable)
    disabled_features = (
        "apps",
        "browser_use",
        "browser_use_external",
        "browser_use_full_cdp_access",
        "computer_use",
        "hooks",
        "image_generation",
        "in_app_browser",
        "multi_agent",
        "plugins",
        "skill_search",
        "tool_suggest",
    )
    command = [
        str(binary),
        "-a",
        "never",
        "exec",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "-C",
        str(root),
        "-m",
        config.model,
        "-o",
        str(Path(last_message_path).resolve()),
        "-c",
        f"model_reasoning_effort={_toml_string(config.reasoning_effort)}",
        "-c",
        f"default_permissions={_toml_string(PERMISSION_PROFILE)}",
        "-c",
        filesystem_profile_override(root),
        "-c",
        f"permissions.{PERMISSION_PROFILE}.network.enabled=false",
        "-c",
        'web_search="disabled"',
        "-c",
        "mcp_servers={}",
        "-c",
        "plugins={}",
        "-c",
        "apps._default.enabled=false",
        "-c",
        "skills.bundled.enabled=false",
        "-c",
        "skills.config=[]",
        "-c",
        "project_doc_max_bytes=0",
        "-c",
        "allow_login_shell=false",
        "-c",
        'shell_environment_policy.inherit="all"',
    ]
    for feature in disabled_features:
        command.extend(("--disable", feature))
    command.append("-")
    return command


def sanitized_environment() -> dict[str, str]:
    """Pass only process/runtime variables; never pass provider or cloud secrets."""
    keep = (
        "COLORTERM",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "NO_COLOR",
        "PATH",
        "SHELL",
        "TERM",
        "TMPDIR",
        "TZ",
    )
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.setdefault("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("NO_COLOR", "1")
    env.setdefault("TERM", "dumb")
    return env


def parse_event_stream(stdout: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for number, line in enumerate(stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {number}: {exc.msg}")
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            errors.append(f"line {number}: JSON event is not an object")
    return events, errors


def extract_tokens(events: list[dict[str, Any]]) -> dict[str, int]:
    """Return the last cumulative turn usage emitted by Codex."""
    usage: dict[str, Any] = {}
    for event in events:
        candidate = event.get("usage")
        if isinstance(candidate, dict):
            usage = candidate
        payload = event.get("turn")
        if isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
            usage = payload["usage"]
    aliases = {
        "input_tokens": ("input_tokens", "inputTokens"),
        "cached_input_tokens": ("cached_input_tokens", "cachedInputTokens"),
        "output_tokens": ("output_tokens", "outputTokens"),
        "reasoning_output_tokens": ("reasoning_output_tokens", "reasoningOutputTokens"),
        "total_tokens": ("total_tokens", "totalTokens"),
    }
    normalized: dict[str, int] = {}
    for label, keys in aliases.items():
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                normalized[label] = value
                break
    return normalized


def extract_lean_calls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract completed shell calls whose command mentions Lean or Lake."""
    calls: dict[str, dict[str, Any]] = {}
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        command = item.get("command")
        rendered = command if isinstance(command, str) else json.dumps(command, sort_keys=True)
        if "lean" not in rendered.lower() and "lake" not in rendered.lower():
            continue
        identifier = str(item.get("id", len(calls)))
        call = {"command": rendered}
        for source, target in (
            ("exit_code", "exit_code"),
            ("status", "status"),
            ("duration_ms", "duration_ms"),
        ):
            value = item.get(source)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                call[target] = value
        calls[identifier] = call
    return list(calls.values())


def _terminate_process_group(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_codex_session(
    workspace: Path | str,
    artifact_dir: Path | str,
    config: CodexAgentConfig,
) -> CodexSessionResult:
    """Run one isolated Codex turn and preserve its raw, unmodified artifacts."""
    root = Path(workspace).resolve()
    artifacts = Path(artifact_dir).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    version = codex_cli_version(config.codex_executable)
    if config.expected_cli_version and version != config.expected_cli_version:
        raise RuntimeError(
            f"Codex CLI drift: expected {config.expected_cli_version!r}, observed {version!r}"
        )
    last_message = artifacts / "last_message.txt"
    command = build_codex_command(root, last_message, config)
    (artifacts / "invocation.json").write_text(
        json.dumps(
            {
                "command": command,
                "config": asdict(config),
                "codex_cli_version": version,
                "codex_executable_sha256": sha256_file(resolve_codex(config.codex_executable)),
                "workspace": str(root),
                "prompt_sha256": prompt_sha256(config.prompt),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=sanitized_environment(),
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(config.prompt, timeout=config.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(proc)
        stdout, stderr = proc.communicate()
    elapsed = time.monotonic() - started
    (artifacts / "events.jsonl").write_text(stdout, encoding="utf-8")
    (artifacts / "stderr.log").write_text(stderr, encoding="utf-8")
    events, event_errors = parse_event_stream(stdout)
    types = {event.get("type") for event in events}
    return CodexSessionResult(
        command=command,
        returncode=proc.returncode,
        timed_out=timed_out,
        elapsed_seconds=elapsed,
        stdout=stdout,
        stderr=stderr,
        events=events,
        event_errors=event_errors,
        tokens=extract_tokens(events),
        lean_calls=extract_lean_calls(events),
        turn_started="turn.started" in types or "thread.started" in types,
    )
