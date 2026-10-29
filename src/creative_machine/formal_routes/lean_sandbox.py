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
    env = sanitized_environment()
    # A2 Mathlib pilot (amendment E2): with a shared Lake cache, lake verifies the git dependency with `git`; Apple's
    # /usr/bin/git shim (xcrun) needs a writable cache the sandbox denies, so the real git of the developer tools
    # goes first in PATH. Std worlds (no CM_LAKE_SHARED) keep the historical environment.
    import os
    devbin = Path("/Library/Developer/CommandLineTools/usr/bin")
    if os.environ.get("CM_LAKE_SHARED") and devbin.is_dir():
        env["PATH"] = f"{devbin}:{env.get('PATH', '')}"
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"   # git aborts on an unreadable ~/.gitconfig (HOME is denied in the sandbox)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
    return subprocess.run(args, cwd=root, capture_output=capture_output, text=text,
                          timeout=timeout, env=env, check=False)


def probe_sandbox(workspace: Path, forbidden: Path) -> dict:
    """Three sandboxed commands in a probe workspace: an outside read must fail, the network must fail, lake must build
    the frozen target. The probe mirrors the checker's staging: with CM_LAKE_SHARED the shared packages are linked in
    first (E2), otherwise lake would try to clone Mathlib with the network denied."""
    from .submission import attach_shared_lake
    workspace = Path(workspace)
    if not (workspace / ".lake" / "packages").exists():
        attach_shared_lake(workspace)
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
