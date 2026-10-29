"""Run only the local compiler in a filesystem/network sandbox; no model calls."""

from pathlib import Path
import subprocess

from .codex_runner import (
    PERMISSION_PROFILE, filesystem_profile_override, resolve_codex, sanitized_environment,
)

CODEX_BINARY = "/Applications/ChatGPT.app/Contents/Resources/codex"


def sandbox_process(command, *, cwd, capture_output=True, text=True, timeout=120):
    root = Path(cwd).resolve()
    args = [str(resolve_codex(CODEX_BINARY)), "sandbox", "-P", PERMISSION_PROFILE,
            "-C", str(root), "-c", filesystem_profile_override(root),
            "-c", f"permissions.{PERMISSION_PROFILE}.network.enabled=false", "--", *command]
    return subprocess.run(args, cwd=root, capture_output=capture_output, text=text,
                          timeout=timeout, env=sanitized_environment(), check=False)


def probe_sandbox(workspace: Path, forbidden: Path) -> dict:
    commands = {
        "outside_read_denied": (["/bin/cat", str(forbidden.resolve())], False),
        "network_denied": (["/usr/bin/curl", "-Is", "--max-time", "3", "https://example.com"], False),
        "lean_ok": (["/opt/homebrew/bin/lake", "build", "World.ChallengeEvaluation"], True),
    }
    result = {}
    for name, (command, success_expected) in commands.items():
        proc = sandbox_process(command, cwd=workspace)
        result[name] = (proc.returncode == 0) == success_expected
    result["ok"] = all(result.values())
    return result
