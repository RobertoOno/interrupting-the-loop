"""Development-only proposer/transfer contract; no model or provider calls.

Historical verifiers stay frozen. Bridge validity here is independent of visible
success, and every compilation starts from an allowlist of source bytes. The
compiler runs in the existing network/filesystem sandbox by default. Injectable
process runners are for offline tests, not a production sandbox bypass.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from .lean_sandbox import sandbox_process
from .submission import STANDARD_LEAN_AXIOMS, scan_forbidden_lean
from .workspace import (
    EvaluatorCondition, ProposerArm, WorkspaceRecord, audit_workspace,
    materialize_evaluator, materialize_proposer,
)

VERSION = "p3_production_contract_v1"
MAX_SOURCE_BYTES = 100_000
BASE_FILES = ("lakefile.toml", "lean-toolchain", "World/Base.lean")
VISIBLE_FILE = "World/ChallengeVisible.lean"
OUTPUTS = ("Bridge.lean", "Solution.lean")
AUDIT_MARKER = "P3_PRODUCTION_AUDIT_V1"
REJECTION_MARKER = "P3_PRODUCTION_REJECT_V1"
AUDIT_REJECTIONS = {
    "identity": "exactly one public candidate declaration is required",
    "kind": "candidate declaration must be a theorem",
    "origin": "candidate declaration must originate in its required output module",
    "visible_type": "candidate_solution does not have the frozen visible type",
    "axioms": "nonstandard axiom dependency",
}
_NAME = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
_EXTRA_FORBIDDEN = (
    "run_elab", "simproc", "simproc_decl", "notation", "infix", "infixl",
    "infixr", "prefix", "postfix", "prelude", "module",
)

TASK_APPENDIX = """
The two files are checked separately. A valid bridge remains valid even if the
visible solution is absent or rejected. Only Bridge.lean can be passed onward;
do not include the visible solution, source text, or conversation in that file.
Use ordinary Lean proofs and helper definitions, with no Mathlib. Only propext,
Quot.sound, and Classical.choice are allowed as transitive axiom dependencies.
No new axioms, admitted proofs, custom syntax/notation, metaprogramming, or hash
commands are allowed. The only permitted set_option names are maxRecDepth and
maxHeartbeats. Imports must be unmodified import commands at the beginning of
each file, one command per line. Each file may contain at most 100000 UTF-8 bytes.
The required declaration must be a public theorem, with exactly one of the
allowed names (global or in the supplied world namespace), not a definition.
"""


class WorkspaceIntegrityError(ValueError):
    """Host-side integrity failure; never turn this into mathematical failure."""


class VerificationInfrastructureError(RuntimeError):
    """Stop admissions on compiler/runtime/timeouts; retain any partial report."""

    def __init__(self, phase: str, detail: str, *, stdout: str = "", stderr: str = ""):
        super().__init__(f"{phase}: {detail}")
        self.phase = phase
        self.stdout = stdout
        self.stderr = stderr
        self.partial_bridge: ComponentReport | None = None


@dataclass(frozen=True)
class ComponentReport:
    status: Literal["missing", "rejected", "valid", "blocked_by_bridge"]
    source_sha256: str | None = None
    declaration: str | None = None
    axioms: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""

    @property
    def valid(self) -> bool:
        return self.status == "valid"


@dataclass(frozen=True)
class ProductionReport:
    bridge: ComponentReport
    visible: ComponentReport
    base_hashes: tuple[tuple[str, str], ...]
    namespace: str

    @property
    def bridge_transferable(self) -> bool:
        return self.bridge.valid

    def feedback(self) -> dict:
        """Only the two component outcomes; no hidden-world or host diagnostics."""
        return {
            label: {"status": report.status, "valid": report.valid,
                    "errors": list(report.errors)}
            for label, report in (("bridge", self.bridge), ("visible", self.visible))
        }


@dataclass(frozen=True)
class BridgeArtifact:
    """Verified bytes, not an instruction to choose this revision or run siblings.

    This is not a security capability. Recipients recompile it against their
    frozen base, so even a manually constructed artifact cannot bypass checking.
    No proposer arm, source, solution, or conversation is stored here.
    """

    source: bytes
    sha256: str
    world_id: str
    namespace: str
    declaration: str
    base_hashes: tuple[tuple[str, str], ...]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _namespace(namespace: str) -> None:
    if not re.fullmatch(_NAME, namespace):
        raise WorkspaceIntegrityError("invalid trusted namespace")


def _regular_bytes(root: Path, rel: str) -> bytes:
    path = root / rel
    current = path
    while current != root:
        if current.is_symlink():
            raise WorkspaceIntegrityError(f"symlink forbidden: {rel}")
        current = current.parent
    if not path.is_file():
        raise FileNotFoundError(rel)
    return path.read_bytes()


def _snapshot_proposer(record: WorkspaceRecord) -> dict[str, bytes]:
    expected = {*BASE_FILES, VISIBLE_FILE, "TASK.md"}
    if record.condition in (ProposerArm.D.value, ProposerArm.C2.value):
        expected.add("SOURCE.md")
    if (record.role != "proposer" or record.condition not in {arm.value for arm in ProposerArm}
            or record.allowed_outputs != OUTPUTS or set(record.copied_hashes) != expected):
        raise WorkspaceIntegrityError("unexpected proposer allowlist")
    if record.path.is_symlink():
        raise WorkspaceIntegrityError("workspace root is a symlink")
    # Do not expose names of unexpected/hidden files as compiler feedback.
    if audit_workspace(record):
        raise WorkspaceIntegrityError("proposer workspace integrity check failed")
    root = record.path.resolve()
    snapshot = {}
    for rel in sorted(expected):
        try:
            data = _regular_bytes(root, rel)
        except FileNotFoundError as exc:
            raise WorkspaceIntegrityError("immutable input missing") from exc
        if _sha(data) != record.copied_hashes[rel]:
            raise WorkspaceIntegrityError("immutable input changed during snapshot")
        snapshot[rel] = data
    return snapshot


def materialize_production_proposer(
    world: Path | str, arm: ProposerArm | str, destination: Path | str,
) -> WorkspaceRecord:
    """Version the two-output instructions without editing historical workspaces."""
    record = materialize_proposer(world, arm, destination)
    task_path = record.path / "TASK.md"
    task_path.write_bytes(task_path.read_bytes() + TASK_APPENDIX.encode("utf-8"))
    hashes = {**record.copied_hashes, "TASK.md": _sha(task_path.read_bytes())}
    return WorkspaceRecord(record.path, record.world_id, record.role,
                           record.condition, hashes, record.allowed_outputs)


def render_production_proposer(record: WorkspaceRecord) -> str:
    """Render only immutable model inputs, never paths, outputs, or build caches."""
    snapshot = _snapshot_proposer(record)
    return "\n\n".join(f"FILE {rel}\n{data.decode('utf-8')}" for rel, data in snapshot.items())


def _without_comments(source: str) -> str:
    """Mask nested Lean comments without joining tokens or touching string data."""
    out: list[str] = []
    i, depth, quoted = 0, 0, False
    while i < len(source):
        pair = source[i:i + 2]
        if depth:
            if pair == "/-":
                depth += 1
                out.append("  ")
                i += 2
            elif pair == "-/":
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
        elif quoted:
            out.append(source[i])
            if source[i] == "\\" and i + 1 < len(source):
                out.append(source[i + 1])
                i += 2
                continue
            if source[i] == '"':
                quoted = False
            i += 1
        elif pair == "/-":
            depth = 1
            out.append("  ")
            i += 2
        elif pair == "--":
            end = source.find("\n", i)
            end = len(source) if end < 0 else end
            out.append(" " * (end - i))
            i = end
        else:
            quoted = source[i] == '"'
            out.append(source[i])
            i += 1
    if depth:
        raise ValueError("unterminated block comment")
    return "".join(out)


def _source_errors(source: str, *, bridge: bool) -> tuple[str, ...]:
    findings = scan_forbidden_lean(source)
    try:
        code = _without_comments(source)
    except ValueError as exc:
        return (str(exc),)
    # Also scan the masked form: e.g. '# /- comment -/ eval' is still forbidden.
    findings.extend(scan_forbidden_lean(code))
    findings.extend(token for token in _EXTRA_FORBIDDEN if re.search(rf"\b{token}\b", code))
    if re.search(r"#\s*[A-Za-z_]", code):
        findings.append("hash command")
    for match in re.finditer(r"\bset_option\s+(\S+)", code):
        if match[1] not in ("maxRecDepth", "maxHeartbeats"):
            findings.append("unapproved set_option")
    if findings:
        return ("forbidden constructs: " + ", ".join(sorted(set(findings))),)
    body, imports = code.lstrip(), []
    while match := re.match(rf"import[ \t]+({_NAME}(?:[ \t]+{_NAME})*)[ \t]*\r?(?:\n|$)", body):
        imports.extend(match[1].split())
        body = body[match.end():].lstrip()
    expected = {"World.Base"} if bridge else {"World.ChallengeVisible", "Bridge"}
    if set(imports) != expected or len(imports) != len(expected) or re.search(r"\bimport\b", body):
        return ("imports must be exactly " + ", ".join(sorted(expected)) + " at the file start",)
    # Actual theorem kind, identity, ambiguity, and dependencies are checked in
    # Lean's environment, not inferred from a regex or model-produced #print.
    return ()


def _candidate(root: Path, rel: str) -> tuple[bytes | None, ComponentReport | None]:
    try:
        data = _regular_bytes(root, rel)
    except FileNotFoundError:
        return None, ComponentReport("missing", errors=(f"{rel} is absent",))
    except WorkspaceIntegrityError:
        return None, ComponentReport("rejected", errors=(f"{rel} must be a regular file",))
    if len(data) > MAX_SOURCE_BYTES:
        return None, ComponentReport("rejected", _sha(data), errors=(f"{rel} exceeds byte limit",))
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None, ComponentReport("rejected", _sha(data), errors=(f"{rel} must be UTF-8",))
    return data, None


def _base_hashes(inputs: dict[str, bytes]) -> tuple[tuple[str, str], ...]:
    return tuple((rel, _sha(inputs[rel])) for rel in BASE_FILES)


def _audit_source(namespace: str, *, bridge: bool) -> str:
    """Trusted checker code only. Candidate syntax cannot define the acceptance log."""
    short = "candidate_bridge" if bridge else "candidate_solution"
    module = "Bridge" if bridge else "Solution"
    target_check = "" if bridge else f"""
  let candidate ← Lean.Meta.mkConstWithFreshMVarLevels name
  let actual ← Lean.Meta.inferType candidate
  let expected ← Lean.Meta.mkConstWithFreshMVarLevels `{namespace}.VisibleStatement
  unless ← Lean.Meta.isDefEq actual expected do
    throwError "{REJECTION_MARKER}|visible_type"
"""
    return f"""import Lean
import {module}

open Lean Elab Command in
run_elab do
  let env ← getEnv
  let names : List Lean.Name := [`{short}, `{namespace}.{short}]
  let present := names.filter fun name => (env.find? name).isSome
  unless present.length == 1 do
    throwError "{REJECTION_MARKER}|identity"
  let name := present.head!
  let some (.thmInfo _) := env.find? name
    | throwError "{REJECTION_MARKER}|kind"
  unless (← Lean.findModuleOf? name) == some `{module} do
    throwError "{REJECTION_MARKER}|origin"
{target_check}
  let axioms ← Lean.collectAxioms name
  let allowed : List Lean.Name := [`propext, `Quot.sound, `Classical.choice]
  unless axioms.all (fun ax => allowed.contains ax) do
    throwError "{REJECTION_MARKER}|axioms"
  let axText := String.intercalate "," (axioms.toList.map toString)
  logInfo m!"{AUDIT_MARKER}|{{name}}|{{axText}}"
"""


def _compile_component(
    inputs: dict[str, bytes], source: bytes, *, namespace: str, bridge: bool,
    accepted_bridge: bytes | None, lake: str, deadline: float, process_runner: Callable,
) -> ComponentReport:
    digest = _sha(source)
    errors = _source_errors(source.decode("utf-8"), bridge=bridge)
    if errors:
        return ComponentReport("rejected", digest, errors=errors)
    outputs: list[str] = []
    stderr: list[str] = []

    with tempfile.TemporaryDirectory(prefix="p3-production-check-") as temp:
        staged = Path(temp) / "workspace"
        staged.mkdir()
        names = BASE_FILES if bridge else (*BASE_FILES, VISIBLE_FILE)
        for rel in names:
            path = staged / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(inputs[rel])

        def run(command: list[str], phase: str):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VerificationInfrastructureError(phase, "verification deadline exhausted")
            try:
                proc = process_runner(command, cwd=staged, capture_output=True,
                                      text=True, timeout=remaining)
            except (OSError, subprocess.TimeoutExpired) as exc:
                def decoded(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                raise VerificationInfrastructureError(
                    phase, type(exc).__name__, stdout=decoded(getattr(exc, "stdout", "")),
                    stderr=decoded(getattr(exc, "stderr", ""))) from exc
            outputs.append(proc.stdout)
            stderr.append(proc.stderr)
            if proc.returncode < 0:
                raise VerificationInfrastructureError(phase, f"compiler signal {-proc.returncode}",
                                                      stdout=proc.stdout, stderr=proc.stderr)
            return proc

        # Build frozen inputs before placing any candidate files in the workspace.
        modules = ["World.Base"] if bridge else ["World.Base", "World.ChallengeVisible"]
        built = run([lake, "build", *modules], "frozen_build")
        if built.returncode:
            raise VerificationInfrastructureError("frozen_build", "frozen inputs failed to build",
                                                  stdout=built.stdout, stderr=built.stderr)
        output_dir = staged / ".lake/build/lib/lean"
        output_dir.mkdir(parents=True, exist_ok=True)
        if not bridge:
            if accepted_bridge is None:
                raise WorkspaceIntegrityError("visible verification requires checked bridge bytes")
            (staged / "Bridge.lean").write_bytes(accepted_bridge)
            proc = run([lake, "env", "lean", "-o", str(output_dir / "Bridge.olean"), "Bridge.lean"],
                       "bridge_rebuild")
            if proc.returncode:
                raise VerificationInfrastructureError("bridge_rebuild", "previously checked bridge failed",
                                                      stdout=proc.stdout, stderr=proc.stderr)
        rel = "Bridge.lean" if bridge else "Solution.lean"
        (staged / rel).write_bytes(source)
        proc = run([lake, "env", "lean", "-o", str(output_dir / rel.replace(".lean", ".olean")), rel],
                   "bridge_compile" if bridge else "visible_compile")
        if proc.returncode:
            detail = (proc.stdout + "\n" + proc.stderr).strip()
            if (not re.search(rf"(?m)^{re.escape(rel)}:\d+:\d+: error:", detail)
                    or any(marker in detail.lower() for marker in (
                        "maximum recursion depth", "maximum number of heartbeats", "out of memory",
                        "segmentation fault", "stack overflow", "interrupted", "(deterministic) timeout"))):
                raise VerificationInfrastructureError("candidate_compile", "non-proof or resource failure",
                                                      stdout=proc.stdout, stderr=proc.stderr)
            detail = detail.replace(str(staged.resolve()), "<workspace>").replace(str(staged), "<workspace>")
            return ComponentReport("rejected", digest, errors=(detail or "Lean rejected source",),
                                   stdout="\n".join(outputs), stderr="\n".join(stderr))
        (staged / "Audit.lean").write_text(_audit_source(namespace, bridge=bridge), encoding="utf-8")
        audited = run([lake, "env", "lean", "Audit.lean"], "bridge_audit" if bridge else "visible_audit")
        if audited.returncode:
            detail = (audited.stdout + "\n" + audited.stderr).strip()
            # A bug in the trusted checker, or a broken runtime, must not look
            # like a mathematical rejection. Only explicit verifier outcomes do.
            codes = re.findall(rf"(?m)^Audit\.lean:\d+:\d+: error: {REJECTION_MARKER}\|([a-z_]+)$", detail)
            if len(codes) != 1 or codes[0] not in AUDIT_REJECTIONS or detail.count("error:") != 1:
                raise VerificationInfrastructureError("trusted_audit", "unclassified audit failure",
                                                      stdout=audited.stdout, stderr=audited.stderr)
            return ComponentReport("rejected", digest, errors=(AUDIT_REJECTIONS[codes[0]],),
                                   stdout="\n".join(outputs), stderr="\n".join(stderr))
        # Read only this trusted audit invocation, never earlier compile output.
        pattern = rf"^{AUDIT_MARKER}\|({_NAME})\|([A-Za-z0-9_.,]*)$"
        markers = re.findall(pattern, audited.stdout, flags=re.MULTILINE)
        short = "candidate_bridge" if bridge else "candidate_solution"
        if (len(markers) != 1 or markers[0][0] not in (short, f"{namespace}.{short}")
                or set(filter(None, markers[0][1].split(","))) - set(STANDARD_LEAN_AXIOMS)):
            raise VerificationInfrastructureError("audit_receipt", "missing or invalid trusted audit receipt",
                                                  stdout=audited.stdout, stderr=audited.stderr)
        declaration, ax_text = markers[0]
        return ComponentReport("valid", digest, declaration, tuple(filter(None, ax_text.split(","))),
                               stdout="\n".join(outputs), stderr="\n".join(stderr))


def verify_production(
    record: WorkspaceRecord, *, namespace: str, lake: str | None = None,
    timeout_s: float = 120.0, process_runner: Callable | None = None,
) -> ProductionReport:
    """Check bridge alone, then visible with the same bytes; no sibling arguments.

    timeout_s is a shared wall-clock verification budget, not one new budget per
    compiler command. Runtime/timeouts are infrastructure exceptions, not U=0.
    The caller must stop new admissions on these exceptions, without auto retry.
    """
    _namespace(namespace)
    if timeout_s <= 0:
        raise ValueError("verification timeout must be positive")
    deadline = time.monotonic() + timeout_s
    inputs = _snapshot_proposer(record)
    bridge_data, bridge_report = _candidate(record.path.resolve(), "Bridge.lean")
    solution_data, solution_report = _candidate(record.path.resolve(), "Solution.lean")
    lake_bin = lake or shutil.which("lake")
    if not lake_bin:
        raise VerificationInfrastructureError("runtime", "lake executable not found")
    runner = process_runner or sandbox_process
    if bridge_report is None:
        assert bridge_data is not None
        bridge_report = _compile_component(inputs, bridge_data, namespace=namespace, bridge=True,
                                          accepted_bridge=None, lake=lake_bin, deadline=deadline,
                                          process_runner=runner)
    if solution_report is None:
        assert solution_data is not None
        if not bridge_report.valid:
            solution_report = ComponentReport("blocked_by_bridge", _sha(solution_data),
                                               errors=("visible proof requires a valid bridge",))
        else:
            try:
                solution_report = _compile_component(
                    inputs, solution_data, namespace=namespace, bridge=False,
                    accepted_bridge=bridge_data, lake=lake_bin, deadline=deadline, process_runner=runner)
            except VerificationInfrastructureError as exc:
                exc.partial_bridge = bridge_report
                raise
    return ProductionReport(bridge_report, solution_report, _base_hashes(inputs), namespace)


def bridge_artifact(record: WorkspaceRecord, report: ProductionReport) -> BridgeArtifact:
    """Capture the verified bytes; no revision selection or sibling evaluation."""
    if not report.bridge.valid or not report.bridge.declaration:
        raise ValueError("invalid or absent bridge cannot be transferred")
    inputs = _snapshot_proposer(record)
    if _base_hashes(inputs) != report.base_hashes:
        raise WorkspaceIntegrityError("base changed after bridge verification")
    data, error = _candidate(record.path.resolve(), "Bridge.lean")
    if error is not None or data is None or _sha(data) != report.bridge.source_sha256:
        raise WorkspaceIntegrityError("bridge changed after verification")
    return BridgeArtifact(data, _sha(data), record.world_id, report.namespace,
                          report.bridge.declaration, report.base_hashes)


def materialize_candidate_recipient(
    world: Path | str, holdout: int, artifact: BridgeArtifact, destination: Path | str,
    *, lake: str | None = None, timeout_s: float = 120.0,
    process_runner: Callable | None = None,
) -> WorkspaceRecord:
    """Recheck a bridge against Base alone, then publish fresh recipient sources.

    No historical caches or proposer conversation cross this boundary. Recipient
    targets never enter the bridge checker or produce feedback for the proposer.
    """
    _namespace(artifact.namespace)
    if len(artifact.source) > MAX_SOURCE_BYTES or _sha(artifact.source) != artifact.sha256:
        raise WorkspaceIntegrityError("artifact byte limit or hash mismatch")
    try:
        artifact.source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceIntegrityError("artifact is not UTF-8") from exc
    if timeout_s <= 0:
        raise ValueError("verification timeout must be positive")
    lake_bin = lake or shutil.which("lake")
    if not lake_bin:
        raise VerificationInfrastructureError("runtime", "lake executable not found")
    with tempfile.TemporaryDirectory(prefix="p3-transfer-staging-") as temp:
        temp_root = Path(temp)
        candidate = temp_root / "accepted.lean"
        candidate.write_bytes(artifact.source)
        record = materialize_evaluator(world, holdout, EvaluatorCondition.CANDIDATE_BRIDGE,
                                       temp_root / "recipient", candidate_bridge=candidate)
        inputs = {rel: _regular_bytes(record.path, rel) for rel in BASE_FILES}
        if record.world_id != artifact.world_id or _base_hashes(inputs) != artifact.base_hashes:
            raise WorkspaceIntegrityError("artifact does not belong to recipient frozen base")
        checked = _compile_component(
            inputs, artifact.source, namespace=artifact.namespace, bridge=True, accepted_bridge=None,
            lake=lake_bin, deadline=time.monotonic() + timeout_s,
            process_runner=process_runner or sandbox_process)
        if not checked.valid or checked.declaration != artifact.declaration:
            raise WorkspaceIntegrityError("artifact failed independent bridge recheck")
        dest = Path(destination)
        if dest.is_symlink() or (dest.exists() and (not dest.is_dir() or any(dest.iterdir()))):
            raise FileExistsError("recipient destination must be a fresh empty directory")
        dest.mkdir(parents=True, exist_ok=True)
        for rel, digest in record.copied_hashes.items():
            data = _regular_bytes(record.path, rel)
            if _sha(data) != digest:
                raise WorkspaceIntegrityError("recipient staging input changed")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        result = WorkspaceRecord(dest, record.world_id, record.role, record.condition,
                                 record.copied_hashes.copy(), record.allowed_outputs)
        if audit_workspace(result):
            raise WorkspaceIntegrityError("recipient materialization integrity check failed")
        return result
