"""Candidate scanning and exact Lean verification for Program 3 submissions."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_FORBIDDEN = (
    "admit",
    "axiom",
    "builtin_initialize",
    "constant",
    "elab",
    "elab_rules",
    "extern",
    "implemented_by",
    "include_str",
    "initialize",
    "macro",
    "macro_rules",
    "native_decide",
    "partial",
    "run_tac",
    "sorry",
    "syntax",
    "declare_syntax_cat",
    "unsafe",
)

_FORBIDDEN_DIRECTIVES = {
    "#compile": r"#\s*compile\b",
    "#eval": r"#\s*eval\b",
    "#exit": r"#\s*exit\b",
    "#reduce": r"#\s*reduce\b",
}


def scan_forbidden_lean(source: str) -> list[str]:
    """Return forbidden declaration/metaprogramming tokens found in Lean source.

    This scanner is defense in depth.  Candidate execution must still happen in an
    allowlisted workspace with network disabled; source filtering is not a sandbox.
    """
    # Comments are prose, not declarations: strip block comments (/- ... -/, including doc comments) and line
    # comments (-- to end of line) before looking for tokens. Added 2026-09-13 before the A2 pilot, after an open
    # model was rejected for the word "constant" inside a comment; no earlier archived result depended on this.
    code = re.sub(r"/-.*?-/", " ", source, flags=re.S)
    code = re.sub(r"--[^\n]*", " ", code)
    findings = [
        token
        for token in _FORBIDDEN
        if re.search(rf"(?<![A-Za-z0-9_]){token}(?![A-Za-z0-9_])", code)
    ]
    findings.extend(
        label for label, pattern in _FORBIDDEN_DIRECTIVES.items() if re.search(pattern, code)
    )
    return findings


STANDARD_LEAN_AXIOMS = ("propext", "Quot.sound", "Classical.choice")


def axiom_audit_ok(output: str, allowed: tuple[str, ...] = (), minimum: int = 1) -> bool:
    lists = re.findall(r"depends on axioms: \[([^\]]*)\]", output)
    seen = {name.strip() for group in lists for name in group.split(",") if name.strip()}
    clean = output.count("does not depend on any axioms")
    return "sorryAx" not in output and seen <= set(allowed) and clean + len(lists) >= minimum


@dataclass
class SubmissionReport:
    ok: bool = False
    bridge_valid: bool = False
    solution_valid: bool = False
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    bridge_declaration: str | None = None
    solution_declaration: str | None = None


@dataclass
class EvaluationReport:
    """Exact verification result for one fresh evaluator session."""

    ok: bool = False
    solution_valid: bool = False
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    declaration: str | None = None


def _imports(source: str) -> list[str]:
    modules: list[str] = []
    for line in source.splitlines():
        match = re.match(r"^\s*import\s+(.+?)\s*$", line)
        if match:
            modules.extend(match.group(1).split())
    return modules


def attach_shared_lake(staged: Path) -> bool:
    """If the staged lakefile requires mathlib and CM_LAKE_SHARED names a prepared project (with .lake/packages and
    lake-manifest.json, e.g. the Mathlib v4.33.1 cache), link the packages and copy the manifest so that lake does
    not clone or rebuild Mathlib per check. Read-only reuse; our own modules still build inside the staged dir."""
    import os, shutil
    shared = os.environ.get("CM_LAKE_SHARED")
    lakefile = staged / "lakefile.toml"
    if not shared or not lakefile.is_file() or "mathlib" not in lakefile.read_text(encoding="utf-8"):
        return False
    src = Path(shared)
    if not (src / ".lake/packages").is_dir() or not (src / "lake-manifest.json").is_file():
        raise RuntimeError(f"CM_LAKE_SHARED={shared} has no .lake/packages or lake-manifest.json")
    (staged / ".lake").mkdir(exist_ok=True)
    os.symlink(src / ".lake/packages", staged / ".lake/packages")
    shutil.copy2(src / "lake-manifest.json", staged / "lake-manifest.json")
    return True


def _stage_sources(root: Path, staged: Path, names: tuple[str, ...]) -> None:
    """Never trust precompiled caches or unrelated agent-produced files."""
    staged.mkdir()
    for name in names:
        source = root / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"required source is missing or a symlink: {name}")
        target = staged / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    attach_shared_lake(staged)


def verify_submission(
    workspace: Path | str,
    *,
    namespace: str,
    lake: str | None = None,
    timeout_s: float = 120.0,
) -> SubmissionReport:
    """Compile Bridge/Solution and check the solution has the frozen target type."""
    root = Path(workspace).resolve()
    report = SubmissionReport()
    bridge_path = root / "Bridge.lean"
    solution_path = root / "Solution.lean"
    if not bridge_path.is_file() or not solution_path.is_file():
        report.errors.append("Bridge.lean and Solution.lean are both required")
        return report
    bridge = bridge_path.read_text(encoding="utf-8")
    solution = solution_path.read_text(encoding="utf-8")
    for label, source in (("Bridge.lean", bridge), ("Solution.lean", solution)):
        findings = scan_forbidden_lean(source)
        if findings:
            report.errors.append(f"{label} contains forbidden constructs: {', '.join(findings)}")
    if _imports(bridge) != ["World.Base"]:
        report.errors.append("Bridge.lean must import only World.Base")
    solution_imports = _imports(solution)
    if set(solution_imports) != {"World.ChallengeVisible", "Bridge"}:
        report.errors.append("Solution.lean must import exactly World.ChallengeVisible and Bridge")
    if not re.search(r"\b(theorem|lemma)\s+candidate_bridge\b", bridge):
        report.errors.append("Bridge.lean must declare candidate_bridge")
    if not re.search(r"\b(theorem|lemma)\s+candidate_solution\b", solution):
        report.errors.append("Solution.lean must declare candidate_solution")
    if report.errors:
        return report

    lake_bin = lake or shutil.which("lake")
    if not lake_bin:
        report.errors.append("lake executable not found")
        return report
    with tempfile.TemporaryDirectory(prefix="p3-submission-") as temp:
        staged = Path(temp) / "workspace"
        _stage_sources(root, staged, (
            "lakefile.toml", "lean-toolchain", "World/Base.lean",
            "World/ChallengeVisible.lean", "Bridge.lean", "Solution.lean",
        ))
        build = subprocess.run(
            [lake_bin, "build", "World.Base", "World.ChallengeVisible"],
            cwd=staged,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if build.returncode != 0:
            detail = (build.stderr or build.stdout).strip().splitlines()
            report.errors.append(f"frozen world failed to build: {(detail or ['unknown error'])[-1]}")
            return report
        output_dir = staged / ".lake" / "build" / "lib" / "lean"
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[str] = []
        for rel, output in (
            ("Bridge.lean", output_dir / "Bridge.olean"),
            ("Solution.lean", output_dir / "Solution.olean"),
        ):
            command = [lake_bin, "env", "lean"]
            if output is not None:
                command.extend(["-o", str(output)])
            command.append(rel)
            try:
                proc = subprocess.run(
                    command,
                    cwd=staged,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                report.errors.append(f"Lean timeout while checking {rel}")
                return report
            outputs.append(proc.stdout)
            report.stdout = "\n".join(outputs)
            report.stderr += proc.stderr
            if proc.returncode != 0:
                detail = (proc.stderr + "\n" + proc.stdout).strip().splitlines()
                error_lines = [line for line in detail if "error:" in line]
                report.errors.append(
                    f"Lean rejected {rel}: {(error_lines or detail or ['unknown error'])[0]}"
                )
                return report
            if rel == "Bridge.lean":
                report.bridge_valid = True
            if rel == "Solution.lean":
                report.solution_valid = True
        audit = staged / "Audit.lean"
        audit_failures: list[str] = []
        bridge_names = ("candidate_bridge", f"{namespace}.candidate_bridge")
        solution_names = ("candidate_solution", f"{namespace}.candidate_solution")
        for bridge_name in bridge_names:
            for solution_name in solution_names:
                audit.write_text(
                    "import Solution\n"
                    f"#check ({solution_name} : {namespace}.VisibleStatement)\n"
                    f"#print axioms {bridge_name}\n"
                    f"#print axioms {solution_name}\n",
                    encoding="utf-8",
                )
                try:
                    proc = subprocess.run(
                        [lake_bin, "env", "lean", "Audit.lean"],
                        cwd=staged,
                        capture_output=True,
                        text=True,
                        timeout=timeout_s,
                    )
                except subprocess.TimeoutExpired:
                    report.errors.append("Lean timeout while checking Audit.lean")
                    return report
                if proc.returncode == 0:
                    report.stdout += "\n" + proc.stdout
                    report.stderr += proc.stderr
                    report.bridge_declaration = bridge_name
                    report.solution_declaration = solution_name
                    break
                detail = (proc.stderr + "\n" + proc.stdout).strip().splitlines()
                error_lines = [line for line in detail if "error:" in line]
                audit_failures.append((error_lines or detail or ["unknown error"])[0])
            if report.solution_declaration is not None:
                break
        if report.solution_declaration is None:
            report.errors.append(
                "Lean rejected Audit.lean for root/world namespace declarations: "
                + " | ".join(audit_failures)
            )
            return report
    if "sorryAx" in report.stdout + report.stderr:
        report.errors.append("submission depends on sorryAx")
        return report
    if "depends on axioms: [" in report.stdout + report.stderr:
        report.errors.append("submission depends on a non-allowlisted axiom")
        return report
    if (report.stdout + report.stderr).count("does not depend on any axioms") < 2:
        report.errors.append("submission axiom audit was incomplete")
        return report
    report.ok = report.bridge_valid and report.solution_valid
    return report


def verify_evaluator_solution(
    workspace: Path | str,
    *,
    namespace: str,
    statement: str,
    bridge_supplied: bool,
    lake: str | None = None,
    timeout_s: float = 120.0,
    process_runner: Callable | None = None,
    allowed_axioms: tuple[str, ...] = (),
) -> EvaluationReport:
    """Compile an evaluator output and check its exact frozen sibling target.

    The bridge, when present, is immutable workspace input.  It is compiled before
    the solution, while the axiom audit on ``evaluation_solution`` checks the full
    transitive proof dependency.
    """
    root = Path(workspace).resolve()
    run_process = process_runner or subprocess.run
    report = EvaluationReport()
    solution_path = root / "Solution.lean"
    if not solution_path.is_file():
        report.errors.append("Solution.lean is required")
        return report
    solution = solution_path.read_text(encoding="utf-8")
    findings = scan_forbidden_lean(solution)
    if findings:
        report.errors.append(
            f"Solution.lean contains forbidden constructs: {', '.join(findings)}"
        )
    expected_imports = {"World.ChallengeEvaluation"}
    if bridge_supplied:
        expected_imports.add("Bridge")
        if not (root / "Bridge.lean").is_file():
            report.errors.append("the declared bridge input is missing")
    imports = _imports(solution)
    if len(imports) != len(expected_imports) or set(imports) != expected_imports:
        expected = " and ".join(sorted(expected_imports))
        report.errors.append(f"Solution.lean must import exactly {expected}")
    if not re.search(r"\b(theorem|lemma)\s+evaluation_solution\b", solution):
        report.errors.append("Solution.lean must declare evaluation_solution")
    if report.errors:
        return report

    lake_bin = lake or shutil.which("lake")
    if not lake_bin:
        report.errors.append("lake executable not found")
        return report
    with tempfile.TemporaryDirectory(prefix="p3-evaluation-") as temp:
        staged = Path(temp) / "workspace"
        names = ("lakefile.toml", "lean-toolchain", "World/Base.lean",
                 "World/ChallengeEvaluation.lean", "Solution.lean")
        if bridge_supplied:
            names += ("Bridge.lean",)
        _stage_sources(root, staged, names)
        build = run_process(
            [lake_bin, "build", "World.Base", "World.ChallengeEvaluation"],
            cwd=staged,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if build.returncode != 0:
            detail = (build.stderr or build.stdout).strip().splitlines()
            report.errors.append("frozen target failed to build: " + " | ".join(detail[-8:] or ["unknown error"]))
            return report
        output_dir = staged / ".lake" / "build" / "lib" / "lean"
        output_dir.mkdir(parents=True, exist_ok=True)
        checks: list[tuple[str, Path | None]] = []
        if bridge_supplied:
            checks.append(("Bridge.lean", output_dir / "Bridge.olean"))
        checks.extend(
            (
                ("Solution.lean", output_dir / "Solution.olean"),
            )
        )
        outputs: list[str] = []
        for rel, output in checks:
            command = [lake_bin, "env", "lean"]
            if output is not None:
                command.extend(["-o", str(output)])
            command.append(rel)
            try:
                proc = run_process(
                    command,
                    cwd=staged,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                report.errors.append(f"Lean timeout while checking {rel}")
                return report
            outputs.append(proc.stdout)
            report.stdout = "\n".join(outputs)
            report.stderr += proc.stderr
            if proc.returncode != 0:
                detail = (proc.stderr + "\n" + proc.stdout).strip().splitlines()
                error_lines = [line for line in detail if "error:" in line]
                report.errors.append(
                    f"Lean rejected {rel}: {(error_lines or detail or ['unknown error'])[0]}"
                )
                return report
            if rel == "Solution.lean":
                report.solution_valid = True
        audit = staged / "Audit.lean"
        audit_failures: list[str] = []
        for declaration in ("evaluation_solution", f"{namespace}.evaluation_solution"):
            audit.write_text(
                "import Solution\n"
                f"#check ({declaration} : {namespace}.{statement})\n"
                f"#print axioms {declaration}\n",
                encoding="utf-8",
            )
            try:
                proc = run_process(
                    [lake_bin, "env", "lean", "Audit.lean"],
                    cwd=staged,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                report.errors.append("Lean timeout while checking Audit.lean")
                return report
            if proc.returncode == 0:
                report.stdout += "\n" + proc.stdout
                report.stderr += proc.stderr
                report.declaration = declaration
                break
            detail = (proc.stderr + "\n" + proc.stdout).strip().splitlines()
            error_lines = [line for line in detail if "error:" in line]
            audit_failures.append((error_lines or detail or ["unknown error"])[0])
        if report.declaration is None:
            report.errors.append(
                "Lean rejected Audit.lean for root and world-namespace declarations: "
                + " | ".join(audit_failures)
            )
            return report
    audit_output = report.stdout + report.stderr
    if "sorryAx" in audit_output:
        report.errors.append("evaluation solution depends on sorryAx")
        return report
    if not axiom_audit_ok(audit_output, allowed_axioms):
        report.errors.append("evaluation solution has a non-allowlisted or incomplete axiom audit")
        return report
    report.ok = report.solution_valid
    return report
