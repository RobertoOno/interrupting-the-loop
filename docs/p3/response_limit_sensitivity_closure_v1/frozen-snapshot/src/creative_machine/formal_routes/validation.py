"""Static and Lean-kernel validation for generated Program 3 worlds."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .submission import axiom_audit_ok, scan_forbidden_lean


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class LeanCheck:
    path: str
    expected: str
    returncode: int
    stdout: str
    stderr: str


@dataclass
class ValidationReport:
    world: Path
    static_ok: bool = False
    lean_ok: bool | None = None
    errors: list[str] = field(default_factory=list)
    checks: list[LeanCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.static_ok and self.lean_ok is not False and not self.errors

    def require_ok(self) -> "ValidationReport":
        if not self.ok:
            raise ValueError("; ".join(self.errors) or "world validation failed")
        return self


def _safe_relative(path: str) -> bool:
    candidate = Path(path)
    return bool(path) and not candidate.is_absolute() and ".." not in candidate.parts


def _load_metadata(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid metadata.json: {exc}")
        return {}
    if data.get("schema_version") != 1:
        errors.append("unsupported metadata schema")
    if data.get("phase") == "calibration" and data.get("eligible_for_main") is not False:
        errors.append("calibration world is incorrectly eligible for main")
    return data


def _validate_manifest(root: Path, errors: list[str]) -> None:
    manifest = root / "manifest.sha256"
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"missing manifest.sha256: {exc}")
        return
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        try:
            expected, rel = line.split("  ", 1)
        except ValueError:
            errors.append(f"malformed manifest line {number}")
            continue
        if len(expected) != 64 or not _safe_relative(rel):
            errors.append(f"unsafe manifest line {number}")
            continue
        if rel in seen:
            errors.append(f"duplicate manifest path: {rel}")
            continue
        seen.add(rel)
        target = root / rel
        if not target.is_file():
            errors.append(f"manifest file missing: {rel}")
        elif _sha256(target) != expected:
            errors.append(f"manifest hash mismatch: {rel}")


def _validate_static(root: Path, report: ValidationReport) -> dict[str, Any]:
    metadata = _load_metadata(root, report.errors)
    _validate_manifest(root, report.errors)
    hashes = metadata.get("artifact_hashes", {})
    if not isinstance(hashes, dict):
        report.errors.append("artifact_hashes must be an object")
        hashes = {}
    expected_files = set(hashes) | {"metadata.json", "manifest.sha256"}
    actual_files: set[str] = set()
    for path in root.rglob("*"):
        if ".lake" in path.parts or path.name == "lake-manifest.json":
            continue
        if path.is_symlink():
            report.errors.append(f"symlink forbidden in frozen world: {path.relative_to(root)}")
        elif path.is_file():
            actual_files.add(str(path.relative_to(root)))
    for rel in sorted(actual_files - expected_files):
        report.errors.append(f"unmanifested file: {rel}")
    for rel in sorted(expected_files - actual_files):
        report.errors.append(f"manifested file missing: {rel}")
    for rel, expected in hashes.items():
        if not isinstance(rel, str) or not _safe_relative(rel):
            report.errors.append(f"unsafe artifact path: {rel!r}")
            continue
        target = root / rel
        if not target.is_file():
            report.errors.append(f"artifact missing: {rel}")
        elif _sha256(target) != expected:
            report.errors.append(f"artifact hash mismatch: {rel}")

    public = metadata.get("public_files", [])
    hidden = metadata.get("hidden_files", [])
    if set(public) & set(hidden):
        report.errors.append("public and hidden file lists overlap")
    if not {"World/Holdout1.lean", "World/Holdout2.lean", "Hidden/Oracle.lean"}.issubset(
        set(hidden)
    ):
        report.errors.append("holdouts or oracle are not classified as hidden")

    for path in root.rglob("*.lean"):
        findings = scan_forbidden_lean(path.read_text(encoding="utf-8"))
        if findings:
            rel = path.relative_to(root)
            report.errors.append(f"forbidden Lean construct in {rel}: {', '.join(findings)}")
    report.static_ok = not report.errors
    return metadata


def _run_lean(root: Path, rel: str, expected: str, lake: str, timeout_s: float) -> LeanCheck:
    module = rel.removesuffix(".lean").replace("/", ".")
    try:
        proc = subprocess.run(
            [lake, "build", module],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return LeanCheck(rel, expected, proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        return LeanCheck(rel, expected, 124, exc.stdout or "", exc.stderr or "timeout")


def _run_lean_audit(root: Path, rel: str, lake: str, timeout_s: float) -> LeanCheck:
    try:
        proc = subprocess.run(
            [lake, "env", "lean", rel],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return LeanCheck(rel, "axiom_audit", proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        return LeanCheck(rel, "axiom_audit", 124, exc.stdout or "", exc.stderr or "timeout")


def validate_world(
    world: Path | str,
    *,
    run_lean: bool = False,
    lake: str | None = None,
    timeout_s: float = 120.0,
) -> ValidationReport:
    """Validate hashes/isolation metadata and optionally every Lean quality gate."""
    root = Path(world).resolve()
    report = ValidationReport(world=root)
    metadata = _validate_static(root, report)
    if not run_lean:
        return report
    if not report.static_ok:
        report.lean_ok = False
        return report

    lake_bin = lake or shutil.which("lake")
    if not lake_bin:
        report.lean_ok = False
        report.errors.append("lake executable not found")
        return report

    config = metadata.get("lean_checks", {})
    for rel in config.get("must_compile", []):
        check = _run_lean(root, rel, "compile", lake_bin, timeout_s)
        report.checks.append(check)
        if check.returncode != 0:
            detail = (check.stderr or check.stdout).strip().splitlines()
            report.errors.append(f"Lean rejected {rel}: {(detail or ['unknown error'])[-1]}")
    for rel in config.get("must_fail", []):
        check = _run_lean(root, rel, "reject", lake_bin, timeout_s)
        report.checks.append(check)
        if check.returncode == 0:
            report.errors.append(f"negative control unexpectedly compiled: {rel}")
        elif not any(
            marker in check.stdout + check.stderr
            for marker in ("unsolved goals", "type mismatch", "`grind` failed")
        ):
            report.errors.append(f"negative control failed for an unexpected reason: {rel}")

    if not report.errors:
        for rel, expected_count in config.get("axiom_audits", {}).items():
            audit = _run_lean_audit(root, rel, lake_bin, timeout_s)
            report.checks.append(audit)
            audit_output = audit.stdout + "\n" + audit.stderr
            if audit.returncode != 0:
                report.errors.append(f"axiom audit did not compile: {rel}")
            if not axiom_audit_ok(audit_output, tuple(metadata.get("allowed_axioms", [])), expected_count):
                report.errors.append(
                    f"axiom audit for {rel} is incomplete or contains non-allowlisted axioms"
                )
    report.lean_ok = not report.errors
    return report
