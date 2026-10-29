"""Stable JSONL record contract for Program 3 agent sessions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TELEMETRY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AttemptRecord:
    run_id: str
    world_id: str
    phase: str
    role: str
    condition: str
    input_sha256: str
    status: str
    model: str | None = None
    holdout: int | None = None
    infrastructure_failure: bool = False
    visible_solved: bool | None = None
    bridge_valid: bool | None = None
    target_solved: bool | None = None
    tokens: dict[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    elapsed_seconds: float | None = None
    lean_calls: list[dict[str, Any]] = field(default_factory=list)
    output_hashes: dict[str, str] = field(default_factory=dict)
    schema_version: int = TELEMETRY_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != TELEMETRY_SCHEMA_VERSION:
            raise ValueError("unsupported telemetry schema")
        if self.phase not in {"calibration", "main"}:
            raise ValueError("invalid phase")
        if self.role not in {"proposer", "evaluator"}:
            raise ValueError("invalid role")
        if self.role == "proposer" and self.holdout is not None:
            raise ValueError("proposer records cannot name a holdout")
        if self.role == "evaluator" and self.holdout not in {1, 2}:
            raise ValueError("evaluator records require holdout 1 or 2")
        if len(self.input_sha256) != 64:
            raise ValueError("input_sha256 must contain 64 hexadecimal characters")
        try:
            int(self.input_sha256, 16)
        except ValueError as exc:
            raise ValueError("input_sha256 must be hexadecimal") from exc
        if self.cost_usd is not None and self.cost_usd < 0:
            raise ValueError("cost_usd cannot be negative")
        if self.elapsed_seconds is not None and self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds cannot be negative")

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_record(path: Path | str, record: AttemptRecord) -> None:
    """Append one validated record; callers own higher-level run locking."""
    line = record.to_json()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
