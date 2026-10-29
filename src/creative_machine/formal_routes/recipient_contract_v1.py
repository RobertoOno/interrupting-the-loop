"""Fresh, exact recipient proof checking for the development transfer matrix.

No provider client, admission, review of bridge content or revision selection.
The caller must first audit/seal production and content and enforce the batch
barrier. A BridgeArtifact is a byte binding, never an admission capability.
Historical contracts/runners remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Callable

from .calibration_worlds_v3 import load_v3
from .lean_sandbox import sandbox_process
from .production_contract_v1 import (
    BASE_FILES, MAX_SOURCE_BYTES, BridgeArtifact, ComponentReport,
    VerificationInfrastructureError, WorkspaceIntegrityError,
    _without_comments, materialize_candidate_recipient,
)
from .submission import STANDARD_LEAN_AXIOMS, scan_forbidden_lean
from .transfer_design_v1 import load_blueprint, sha
from .workspace import WorkspaceRecord, materialize_evaluator

VERSION = "p3_recipient_contract_v1"
TARGET_FILE = "World/ChallengeEvaluation.lean"
AUDIT_MARKER = "P3_RECIPIENT_AUDIT_V1"
REJECTION_MARKER = "P3_RECIPIENT_REJECT_V1"
CHECK_TIMEOUT_SECONDS = 120.0
REJECTIONS = {"identity": "exactly one public required declaration is required",
              "kind": "required declaration must be a theorem",
              "origin": "required declaration must originate in its output module",
              "target_type": "evaluation_solution does not have the frozen recipient target type",
              "axioms": "nonstandard axiom dependency"}
_NAME = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
_EXTRA_FORBIDDEN = ("run_elab", "simproc", "simproc_decl", "notation", "infix", "infixl",
                    "infixr", "prefix", "postfix", "prelude", "module")
_RESOURCE_MARKERS = ("maximum recursion depth", "maximum number of heartbeats", "out of memory",
                     "segmentation fault", "stack overflow", "interrupted", "(deterministic) timeout")
TASK_RULES = """Use Lean 4.33.1 and Std, without Mathlib. Write only Solution.lean.
Do not edit supplied inputs or any bridge. The solution must be a public theorem,
not a definition, with exactly one allowed name. Only propext, Quot.sound and
Classical.choice may occur as transitive axiom dependencies. No new axioms,
admitted proofs, custom notation, hash commands, metaprogramming or unsafe
declarations. Only maxRecDepth/maxHeartbeats options may be adjusted. Imports
must be unmodified commands at the beginning of the file, one command per line.
Solution.lean may contain at most 100000 UTF-8 bytes. Mathematical helper lemmas
are allowed. Only this target is available; there is no external information,
filesystem-reading tool or other task. A successful verification ends the session.
"""


@dataclass(frozen=True)
class RecipientReport:
    solution: ComponentReport
    bridge: ComponentReport | None
    input_hashes: tuple[tuple[str, str], ...]
    cell_id: str
    world_id: str
    namespace: str
    statement: str
    bridge_sha256: str | None

    @property
    def target_solved(self) -> bool:
        return self.solution.valid

    def feedback(self) -> dict:
        """Only local solution status/errors; no host identity or bridge review."""
        return {"status": self.solution.status, "valid": self.solution.valid,
                "errors": list(self.solution.errors)}


def _require(value, message):
    if not value:
        raise WorkspaceIntegrityError(message)


def _check_timeout(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= CHECK_TIMEOUT_SECONDS:
        raise ValueError("recipient check timeout must be finite, positive and at most 120 seconds")


def _regular(root: Path, rel: str) -> bytes:
    path = root / rel
    current = path
    while current != root:
        _require(not current.is_symlink(), "symlink in required recipient input/output")
        current = current.parent
    _require(path.is_file(), "missing required recipient input/output")
    return path.read_bytes()


def _spec(repository: Path, cell_id: str, candidate: BridgeArtifact | None) -> dict:
    blueprint = load_blueprint(repository)
    cell = next((c for c in blueprint["cells"] if c["cell_id"] == cell_id and c["role"] == "recipient"), None)
    _require(cell is not None, "unknown development recipient cell")
    world = repository / cell["world"]
    metadata = load_v3(world, phase="calibration")
    namespace = metadata["roles"]["namespace"]
    statement = metadata["roles"]["holdout_statements"][cell["holdout"] - 1]
    _require(re.fullmatch(_NAME, namespace) and re.fullmatch(_NAME, statement), "unsafe trusted target identifier")
    base_hashes = tuple((rel, sha(_regular(world, rel))) for rel in BASE_FILES)
    condition = {"none": "no_bridge", "oracle": "oracle_bridge", "candidate": "candidate_bridge"}[cell["bridge_kind"]]
    bridge, short = None, None
    if cell["bridge_kind"] == "candidate":
        _require(isinstance(candidate, BridgeArtifact), "candidate recipient requires bound bridge bytes")
        _require(isinstance(candidate.source, bytes) and len(candidate.source) <= MAX_SOURCE_BYTES
                 and sha(candidate.source) == candidate.sha256, "candidate bytes/hash/size mismatch")
        _require(candidate.world_id == cell["world_id"] and candidate.namespace == namespace
                 and candidate.base_hashes == base_hashes, "candidate belongs to another frozen base")
        _require(candidate.declaration in ("candidate_bridge", namespace + ".candidate_bridge"), "unexpected candidate theorem name")
        try:
            candidate.source.decode("utf-8")
        except UnicodeError as exc:
            raise WorkspaceIntegrityError("candidate bridge must be UTF-8") from exc
        bridge, short = candidate.source, "candidate_bridge"
    else:
        _require(candidate is None, "baseline/oracle cannot receive a candidate artifact")
        if cell["bridge_kind"] == "oracle":
            bridge, short = _regular(world, "Hidden/Oracle.lean"), metadata["roles"]["oracle_bridge"]
            frozen = next(w for w in blueprint["worlds"] if w["world_id"] == cell["world_id"])
            _require(sha(bridge) == frozen["oracle_bridge_sha256"] and short == "oracle_bridge", "frozen oracle changed")
    inputs = {rel: _regular(world, rel) for rel in BASE_FILES}
    inputs[TARGET_FILE] = _regular(world, f"World/Holdout{cell['holdout']}.lean")
    if bridge is not None:
        inputs["Bridge.lean"] = bridge
    task = (f"Prove {namespace}.{statement} from {TARGET_FILE}.\n"
            + (f"An immutable bridge named {short} is available in Bridge.lean.\n" if bridge is not None else "No bridge is supplied.\n")
            + ("Solution.lean must import exactly World.ChallengeEvaluation and Bridge.\n" if bridge is not None
               else "Solution.lean must import only World.ChallengeEvaluation.\n")
            + "Declare theorem evaluation_solution with exactly that frozen statement type, either\n"
            + f"globally or inside exactly namespace {namespace}.\n" + TASK_RULES)
    inputs["TASK.md"] = task.encode("utf-8")
    return {"cell": cell, "world": world, "namespace": namespace, "statement": statement,
            "condition": condition, "bridge": bridge, "bridge_name": short, "inputs": inputs}


def _snapshot(record: WorkspaceRecord, spec: dict) -> dict[str, bytes]:
    expected = spec["inputs"]
    _require(record.role == "evaluator" and record.condition == spec["condition"]
             and record.world_id == spec["cell"]["world_id"] and record.allowed_outputs == ("Solution.lean",),
             "recipient identity/output contract mismatch")
    _require(record.copied_hashes == {rel: sha(data) for rel, data in expected.items()}, "recipient frozen hashes mismatch")
    _require(record.path.is_dir() and not record.path.is_symlink(), "unsafe recipient workspace")
    # Nothing compiles in this live model workspace. Even an empty cache or
    # unrelated directory is unexpected here; compiler stages are always fresh.
    for path in record.path.rglob("*"):
        rel = path.relative_to(record.path).as_posix()
        _require(not path.is_symlink(), "recipient workspace symlink")
        if path.is_dir():
            _require(rel == "World", "unexpected recipient directory")
        else:
            _require(path.is_file() and rel in {*expected, "Solution.lean"}, "unexpected recipient file")
    snapshot = {rel: _regular(record.path, rel) for rel in sorted(expected)}
    _require(snapshot == expected, "recipient immutable inputs changed")
    return snapshot


def materialize_recipient(repository: Path, cell_id: str, destination: Path, *, candidate: BridgeArtifact | None = None,
                          lake: str | None = None, timeout_s: float = 120.0,
                          process_runner: Callable | None = None) -> WorkspaceRecord:
    """Fresh source workspace; not proof that production/content/barrier passed."""
    _check_timeout(timeout_s)
    spec = _spec(Path(repository), cell_id, candidate)
    destination = Path(destination)
    _require(not destination.is_symlink() and not destination.exists(), "recipient destination must be new")
    if candidate is not None:
        record = materialize_candidate_recipient(spec["world"], spec["cell"]["holdout"], candidate, destination,
            lake=lake, timeout_s=timeout_s, process_runner=process_runner)
    else:
        record = materialize_evaluator(spec["world"], spec["cell"]["holdout"], spec["condition"], destination)
    (record.path / "TASK.md").write_bytes(spec["inputs"]["TASK.md"])
    record = WorkspaceRecord(record.path, record.world_id, record.role, record.condition,
                             {rel: sha(data) for rel, data in spec["inputs"].items()}, record.allowed_outputs)
    _snapshot(record, spec)
    return record


def render_recipient(record: WorkspaceRecord, *, repository: Path, cell_id: str,
                     candidate: BridgeArtifact | None = None) -> str:
    """Positive allowlist only; no output, host labels, sources or content packet."""
    inputs = _snapshot(record, _spec(Path(repository), cell_id, candidate))
    return "\n\n".join(f"FILE {rel}\n{data.decode('utf-8')}" for rel, data in inputs.items())


def _source_errors(source: str, imports: set[str]) -> tuple[str, ...]:
    findings = scan_forbidden_lean(source)
    try:
        code = _without_comments(source)
    except ValueError as exc:
        return (str(exc),)
    findings.extend(scan_forbidden_lean(code))
    findings.extend(token for token in _EXTRA_FORBIDDEN if re.search(rf"\b{token}\b", code))
    if re.search(r"#\s*[A-Za-z_]", code):
        findings.append("hash command")
    if any(match[1] not in ("maxRecDepth", "maxHeartbeats") for match in re.finditer(r"\bset_option\s+(\S+)", code)):
        findings.append("unapproved set_option")
    if findings:
        return ("forbidden constructs: " + ", ".join(sorted(set(findings))),)
    body, found = code.lstrip(), []
    while match := re.match(rf"import[ \t]+({_NAME}(?:[ \t]+{_NAME})*)[ \t]*\r?(?:\n|$)", body):
        found.extend(match[1].split())
        body = body[match.end():].lstrip()
    if set(found) != imports or len(found) != len(imports) or re.search(r"\bimport\b", body):
        return ("imports must be exactly " + ", ".join(sorted(imports)) + " at the file start",)
    return ()


def _audit_source(namespace: str, short: str, target: str | None) -> str:
    module = "Bridge" if target is None else "Solution"
    target_check = "" if target is None else f"""
  let candidate ← Lean.Meta.mkConstWithFreshMVarLevels name
  let actual ← Lean.Meta.inferType candidate
  let expected ← Lean.Meta.mkConstWithFreshMVarLevels `{namespace}.{target}
  unless ← Lean.Meta.isDefEq actual expected do
    throwError "{REJECTION_MARKER}|target_type"
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


def _compile(inputs: dict[str, bytes], source: bytes, *, namespace: str, short: str, target: str | None,
             bridge_source: bytes | None, lake: str, deadline: float, process_runner: Callable) -> ComponentReport:
    module = "Bridge" if target is None else "Solution"
    rel = module + ".lean"
    imports = {"World.Base"} if target is None else {"World.ChallengeEvaluation"} | ({"Bridge"} if bridge_source is not None else set())
    errors = _source_errors(source.decode("utf-8"), imports)
    if errors:
        return ComponentReport("rejected", sha(source), errors=errors)
    stdout, stderr = [], []
    with tempfile.TemporaryDirectory(prefix="p3-recipient-check-") as temp:
        staged = Path(temp) / "workspace"
        staged.mkdir()
        for name in (BASE_FILES if target is None else (*BASE_FILES, TARGET_FILE)):
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(inputs[name])

        def run(command, phase):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VerificationInfrastructureError(phase, "shared verification deadline exhausted")
            try:
                proc = process_runner(command, cwd=staged, capture_output=True, text=True, timeout=remaining)
            except Exception as exc:
                def decoded(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value or "")
                # Adapter/decoder errors are also technical. Never disguise a
                # host bug as a rejected proof; retain the exception chain.
                raise VerificationInfrastructureError(phase, f"{type(exc).__name__}: {exc}",
                    stdout=decoded(getattr(exc, "stdout", "")), stderr=decoded(getattr(exc, "stderr", ""))) from exc
            if (not isinstance(proc, subprocess.CompletedProcess) or type(proc.returncode) is not int
                    or not isinstance(proc.stdout, str) or not isinstance(proc.stderr, str)):
                raise VerificationInfrastructureError(phase, "invalid compiler process receipt")
            stdout.append(proc.stdout)
            stderr.append(proc.stderr)
            if time.monotonic() > deadline:
                raise VerificationInfrastructureError(phase, "compiler returned after shared deadline",
                                                      stdout=proc.stdout, stderr=proc.stderr)
            if proc.returncode < 0:
                raise VerificationInfrastructureError(phase, f"compiler signal {-proc.returncode}", stdout=proc.stdout, stderr=proc.stderr)
            return proc

        built = run([lake, "build", "World.Base", *(["World.ChallengeEvaluation"] if target else [])], "frozen_build")
        if built.returncode:
            raise VerificationInfrastructureError("frozen_build", "frozen recipient inputs failed", stdout=built.stdout, stderr=built.stderr)
        output = staged / ".lake/build/lib/lean"
        output.mkdir(parents=True, exist_ok=True)
        if bridge_source is not None:
            (staged / "Bridge.lean").write_bytes(bridge_source)
            rebuilt = run([lake, "env", "lean", "-o", str(output / "Bridge.olean"), "Bridge.lean"], "bridge_rebuild")
            if rebuilt.returncode:
                raise VerificationInfrastructureError("bridge_rebuild", "previously checked immutable bridge failed", stdout=rebuilt.stdout, stderr=rebuilt.stderr)
        (staged / rel).write_bytes(source)
        compiled = run([lake, "env", "lean", "-o", str(output / (module + ".olean")), rel], "bridge_compile" if target is None else "solution_compile")
        if compiled.returncode:
            detail = (compiled.stdout + "\n" + compiled.stderr).strip()
            if (not re.search(rf"(?m)^{re.escape(rel)}:\d+:\d+: error:", detail)
                    or any(marker in detail.lower() for marker in _RESOURCE_MARKERS)):
                raise VerificationInfrastructureError("candidate_compile", "non-proof or resource failure", stdout=compiled.stdout, stderr=compiled.stderr)
            detail = detail.replace(str(staged.resolve()), "<workspace>").replace(str(staged), "<workspace>")
            return ComponentReport("rejected", sha(source), errors=(detail,), stdout="\n".join(stdout), stderr="\n".join(stderr))
        (staged / "Audit.lean").write_text(_audit_source(namespace, short, target), encoding="utf-8")
        audited = run([lake, "env", "lean", "Audit.lean"], "bridge_audit" if target is None else "solution_audit")
        if audited.returncode:
            detail = (audited.stdout + "\n" + audited.stderr).strip()
            codes = re.findall(rf"(?m)^Audit\.lean:\d+:\d+: error: {REJECTION_MARKER}\|([a-z_]+)$", detail)
            if len(codes) != 1 or codes[0] not in REJECTIONS or detail.count("error:") != 1:
                raise VerificationInfrastructureError("trusted_audit", "unclassified checker failure", stdout=audited.stdout, stderr=audited.stderr)
            return ComponentReport("rejected", sha(source), errors=(REJECTIONS[codes[0]],), stdout="\n".join(stdout), stderr="\n".join(stderr))
        matches = re.findall(rf"(?m)^{AUDIT_MARKER}\|({_NAME})\|([A-Za-z0-9_.,]*)$", audited.stdout)
        if (len(matches) != 1 or matches[0][0] not in (short, namespace + "." + short)
                or set(filter(None, matches[0][1].split(","))) - set(STANDARD_LEAN_AXIOMS)):
            raise VerificationInfrastructureError("audit_receipt", "missing or invalid trusted receipt", stdout=audited.stdout, stderr=audited.stderr)
        return ComponentReport("valid", sha(source), matches[0][0], tuple(filter(None, matches[0][1].split(","))),
                               stdout="\n".join(stdout), stderr="\n".join(stderr))


def verify_recipient(record: WorkspaceRecord, *, repository: Path, cell_id: str,
                     candidate: BridgeArtifact | None = None, lake: str | None = None,
                     timeout_s: float = 120.0, process_runner: Callable | None = None) -> RecipientReport:
    """Base-only bridge audit, then exact target checking in a second fresh stage.

    All compiler commands share one <=120-second wall-clock budget. Failure of
    a supplied immutable bridge is a host/infrastructure failure, never evidence
    that the recipient could not solve its task. No exception authorizes retry.
    """
    _check_timeout(timeout_s)
    deadline = time.monotonic() + timeout_s
    spec = _spec(Path(repository), cell_id, candidate)
    inputs = _snapshot(record, spec)
    path = record.path / "Solution.lean"
    source = _regular(record.path, "Solution.lean") if path.exists() else None
    solution = None
    if source is None:
        solution = ComponentReport("missing", errors=("Solution.lean is absent",))
    elif len(source) > MAX_SOURCE_BYTES:
        solution = ComponentReport("rejected", sha(source), errors=("Solution.lean exceeds byte limit",))
    else:
        try:
            source.decode("utf-8")
        except UnicodeError:
            solution = ComponentReport("rejected", sha(source), errors=("Solution.lean must be UTF-8",))
    lake_bin = lake or shutil.which("lake")
    if not lake_bin:
        raise VerificationInfrastructureError("runtime", "lake executable not found")
    runner = process_runner or sandbox_process
    checked_bridge = None
    if spec["bridge"] is not None:
        checked_bridge = _compile(inputs, spec["bridge"], namespace=spec["namespace"], short=spec["bridge_name"],
            target=None, bridge_source=None, lake=lake_bin, deadline=deadline, process_runner=runner)
        if not checked_bridge.valid or (candidate and checked_bridge.declaration != candidate.declaration):
            exc = VerificationInfrastructureError("admitted_bridge", "supplied bridge failed its frozen contract",
                stdout=checked_bridge.stdout, stderr=checked_bridge.stderr)
            exc.partial_bridge = checked_bridge
            raise exc
    if solution is None:
        try:
            solution = _compile(inputs, source, namespace=spec["namespace"], short="evaluation_solution",
                target=spec["statement"], bridge_source=spec["bridge"], lake=lake_bin, deadline=deadline, process_runner=runner)
        except VerificationInfrastructureError as exc:
            exc.partial_bridge = checked_bridge
            raise
    _require(_snapshot(record, _spec(Path(repository), cell_id, candidate)) == inputs, "recipient inputs changed during verification")
    after = _regular(record.path, "Solution.lean") if path.exists() else None
    _require(after == source, "recipient output changed during verification")
    if time.monotonic() > deadline:
        exc = VerificationInfrastructureError("verification_deadline", "shared verification budget exhausted",
                                             stdout=solution.stdout, stderr=solution.stderr)
        exc.partial_bridge = checked_bridge
        raise exc
    return RecipientReport(solution, checked_bridge, tuple((rel, sha(data)) for rel, data in inputs.items()),
        cell_id, record.world_id, spec["namespace"], spec["statement"], sha(spec["bridge"]) if spec["bridge"] is not None else None)
