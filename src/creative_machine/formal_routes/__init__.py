"""Deterministic formal-world infrastructure for Program 3.

World construction, isolation, Lean verification, and telemetry remain independent
of the provider-specific behavioral calibration adapter.
"""

from .generator import (
    DEFAULT_TOOLCHAIN,
    GeneratedWorld,
    WorldSpec,
    build_world,
    write_world,
)
from .submission import (
    EvaluationReport,
    SubmissionReport,
    scan_forbidden_lean,
    verify_evaluator_solution,
    verify_submission,
)
from .validation import ValidationReport, validate_world
from .workspace import (
    EvaluatorCondition,
    ProposerArm,
    WorkspaceRecord,
    audit_workspace,
    materialize_evaluator,
    materialize_proposer,
)

__all__ = [
    "DEFAULT_TOOLCHAIN",
    "EvaluatorCondition",
    "EvaluationReport",
    "GeneratedWorld",
    "ProposerArm",
    "SubmissionReport",
    "ValidationReport",
    "WorkspaceRecord",
    "WorldSpec",
    "audit_workspace",
    "build_world",
    "materialize_evaluator",
    "materialize_proposer",
    "scan_forbidden_lean",
    "validate_world",
    "verify_evaluator_solution",
    "verify_submission",
    "write_world",
]
