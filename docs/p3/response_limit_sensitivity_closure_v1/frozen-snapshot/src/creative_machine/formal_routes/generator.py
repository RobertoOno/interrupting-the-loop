"""Generate deterministic, prior-empty Lean micro-worlds for Program 3A.

Only calibration infrastructure lives here.  The generator has no clock, network,
or model dependency; identical specs produce byte-identical artifacts.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

SCHEMA_VERSION = 1
GENERATOR_VERSION = "0.2.0"
HARD_GENERATOR_VERSION = "0.3.0"
DEFAULT_TOOLCHAIN = "leanprover/lean4:v4.33.1"
TEMPLATES = ("T1", "T2")

_WORLD_ID = re.compile(r"^[A-Z][A-Z0-9_]{2,47}$")
_CONSONANTS = "bcdfghjklmnpqrstvwxyz"
_VOWELS = "aeiou"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value: str) -> str:
    """Normalize generated text to one trailing LF."""
    return value.strip() + "\n"


def _opaque_name(rng: random.Random, prefix: str, syllables: int = 3) -> str:
    tail = "".join(rng.choice(_CONSONANTS) + rng.choice(_VOWELS) for _ in range(syllables))
    return f"{prefix}_{tail}"


@dataclass(frozen=True)
class WorldSpec:
    """The complete deterministic input to one generated world."""

    world_id: str
    template: str
    seed: int
    phase: str = "calibration"
    eligible_for_main: bool = False
    toolchain: str = DEFAULT_TOOLCHAIN
    difficulty: str = "standard"

    def __post_init__(self) -> None:
        if not _WORLD_ID.fullmatch(self.world_id):
            raise ValueError("world_id must match [A-Z][A-Z0-9_]{2,47}")
        if self.template not in TEMPLATES:
            raise ValueError(f"unknown template: {self.template!r}")
        if self.difficulty not in {"standard", "hard"}:
            raise ValueError("difficulty must be standard or hard")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must be an unsigned 64-bit integer")
        if self.phase not in {"calibration", "main"}:
            raise ValueError("phase must be calibration or main")
        if self.phase == "calibration" and self.eligible_for_main:
            raise ValueError("calibration worlds can never be eligible for the main sample")
        if not re.fullmatch(r"leanprover/lean4:v[0-9]+\.[0-9]+\.[0-9]+", self.toolchain):
            raise ValueError("toolchain must pin an exact Lean release")


@dataclass(frozen=True)
class GeneratedWorld:
    """An in-memory world ready for byte-identical materialization."""

    spec: WorldSpec
    files: Mapping[str, str]
    metadata: Mapping[str, object]


def _lakefile(spec: WorldSpec) -> str:
    package = f"p3_{spec.world_id.lower()}"
    return _text(
        f"""
name = "{package}"
version = "0.1.0"

[[lean_lib]]
name = "World"

[[lean_lib]]
name = "Hidden"
"""
    )


def _t1_files(spec: WorldSpec, rng: random.Random) -> tuple[dict[str, str], dict[str, str]]:
    ns = f"P3.{spec.world_id}"
    chain = _opaque_name(rng, "Q").capitalize()
    halt = _opaque_name(rng, "q")
    step = _opaque_name(rng, "q")
    carries = _opaque_name(rng, "q")
    src_ns = _opaque_name(rng, "S").capitalize()
    src_chain = _opaque_name(rng, "Q").capitalize()
    src_halt = _opaque_name(rng, "q")
    src_step = _opaque_name(rng, "q")
    src_rule = _opaque_name(rng, "q")
    sham_ns = _opaque_name(rng, "S").capitalize()
    sham_chain = _opaque_name(rng, "Q").capitalize()
    sham_halt = _opaque_name(rng, "q")
    sham_step = _opaque_name(rng, "q")
    sham_rule = _opaque_name(rng, "q")

    base = _text(
        f"""
namespace {ns}

universe u

inductive {chain} {{α : Type u}} (R : α → α → Prop) : α → α → Type u where
  | {halt} (x : α) : {chain} R x x
  | {step} {{x y z : α}} : R x y → {chain} R y z → {chain} R x z

def {carries} {{α : Type u}} (R : α → α → Prop) (P : α → Prop) : Prop :=
  ∀ (x y : α), R x y → P x → P y

end {ns}
"""
    )
    visible = _text(
        f"""
import World.Base

namespace {ns}

def VisibleStatement : Prop :=
  ∀ (α : Type) (R : α → α → Prop) (P : α → Prop)
    (x y z : α),
    {carries} R P →
    R x y → {chain} R y z →
    P x → P z

end {ns}
"""
    )
    holdout1 = _text(
        f"""
import World.Base

namespace {ns}

def Holdout1Statement : Prop :=
  ∀ (α : Type) (R : α → α → Prop) (P : α → Prop)
    (x y z : α),
    {carries} R P →
    {chain} R x y → {chain} R y z →
    P x → P z

end {ns}
"""
    )
    holdout2 = _text(
        f"""
import World.Base

namespace {ns}

def Holdout2Statement : Prop :=
  ∀ (α : Type) (R : α → α → Prop) (P : α → Prop)
    (w x y z : α),
    {carries} R P →
    {chain} R w x → R x y → {chain} R y z →
    P w → P z

end {ns}
"""
    )
    oracle = _text(
        f"""
import World.Base

namespace {ns}

universe u

theorem oracle_bridge {{α : Type u}} {{R : α → α → Prop}} {{P : α → Prop}}
    (h : {carries} R P) {{x z : α}}
    (route : {chain} R x z) (hx : P x) : P z := by
  induction route with
  | {halt} point => exact hx
  | {step} hxy tail ih => exact ih (h _ _ hxy hx)

end {ns}
"""
    )
    checks = _text(
        f"""
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle

namespace {ns}

theorem oracle_visible : VisibleStatement := by
  intro α R P x y z h hxy route hx
  exact oracle_bridge h route (h x y hxy hx)

theorem oracle_holdout1 : Holdout1Statement := by
  intro α R P x y z h first second hx
  exact oracle_bridge h second (oracle_bridge h first hx)

theorem oracle_holdout2 : Holdout2Statement := by
  intro α R P w x y z h first hxy second hw
  exact oracle_bridge h second (h x y hxy (oracle_bridge h first hw))

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end {ns}
"""
    )

    relevant_source_lean = _text(
        f"""
namespace {src_ns}

universe u

inductive {src_chain} {{α : Type u}} (S : α → α → Prop) : α → α → Type u where
  | {src_halt} (x : α) : {src_chain} S x x
  | {src_step} {{x y z : α}} : S x y → {src_chain} S y z → {src_chain} S x z

def {src_rule} {{α : Type u}} (S : α → α → Prop) (Q : α → Prop) : Prop :=
  ∀ (x y : α), S x y → Q x → Q y

theorem solved_bridge {{α : Type u}} {{S : α → α → Prop}} {{Q : α → Prop}}
    (h : {src_rule} S Q) {{x z : α}}
    (route : {src_chain} S x z) (hx : Q x) : Q z := by
  induction route with
  | {src_halt} point => exact hx
  | {src_step} hxy tail ih => exact ih (h _ _ hxy hx)

#print axioms solved_bridge

end {src_ns}
"""
    )
    sham_source_lean = _text(
        f"""
namespace {sham_ns}

universe u

inductive {sham_chain} {{α : Type u}} (S : α → α → Prop) : α → α → Type u where
  | {sham_halt} (x : α) : {sham_chain} S x x
  | {sham_step} {{x y z : α}} : S x y → {sham_chain} S y z → {sham_chain} S x z

def {sham_rule} {{α : Type u}} (S : α → α → Prop) (Q : α → Prop) : Prop :=
  ∀ (x y : α), S x y → Q y → Q x

theorem solved_bridge {{α : Type u}} {{S : α → α → Prop}} {{Q : α → Prop}}
    (h : {sham_rule} S Q) {{x z : α}}
    (route : {sham_chain} S x z) (hz : Q z) : Q x := by
  induction route with
  | {sham_halt} point => exact hz
  | {sham_step} hxy tail ih => exact h _ _ hxy (ih hz)

#print axioms solved_bridge

end {sham_ns}
"""
    )
    relevant_md = _text(
        f"""
# Solved source world

This independent world establishes transport over an arbitrary finite route.

```lean
{relevant_source_lean.rstrip()}
```
"""
    )
    sham_md = _text(
        f"""
# Solved source world

This independent world establishes reflection over an arbitrary finite route.

```lean
{sham_source_lean.rstrip()}
```
"""
    )
    relevant_adapter = oracle.replace("oracle_bridge", "relevant_adapter_bridge")
    sham_adapter = _text(
        f"""
import World.Base

namespace {ns}

universe u

theorem sham_adapter_bridge {{α : Type u}} {{R : α → α → Prop}} {{P : α → Prop}}
    (h : {carries} R P) {{x z : α}}
    (route : {chain} R x z) (hz : P z) : P x := by
  induction route with
  | {halt} point => exact hz
  | {step} hxy tail ih => exact h _ _ hxy (ih hz)

end {ns}
"""
    )
    nonvacuity = _text(
        f"""
import World.Base

namespace {ns}

def witnessRelation (_ _ : Unit) : Prop := True
def witnessProperty (_ : Unit) : Prop := True
def routeWitness : {chain} witnessRelation () () := .{halt} ()

theorem nonvacuity : {carries} witnessRelation witnessProperty := by
  intro _x _y _hxy _hx
  exact True.intro

#print axioms nonvacuity

end {ns}
"""
    )
    automatic_simp = _text(
        f"""
import World.ChallengeVisible

namespace {ns}

theorem automatic_simp : VisibleStatement := by
  simp [VisibleStatement, {carries}]

end {ns}
"""
    )
    automatic_grind = _text(
        f"""
import World.ChallengeVisible

namespace {ns}

theorem automatic_grind : VisibleStatement := by
  grind [VisibleStatement, {carries}]

end {ns}
"""
    )
    files = {
        "World/Base.lean": base,
        "World/ChallengeVisible.lean": visible,
        "World/Holdout1.lean": holdout1,
        "World/Holdout2.lean": holdout2,
        "Sources/Relevant.md": relevant_md,
        "Sources/Sham.md": sham_md,
        "Hidden/Oracle.lean": oracle,
        "Hidden/OracleChecks.lean": checks,
        "Hidden/RelevantSource.lean": relevant_source_lean,
        "Hidden/ShamSource.lean": sham_source_lean,
        "Hidden/RelevantAdapter.lean": relevant_adapter,
        "Hidden/ShamAdapter.lean": sham_adapter,
        "Hidden/NonVacuity.lean": nonvacuity,
        "Hidden/AutomationSimp.lean": automatic_simp,
        "Hidden/AutomationGrind.lean": automatic_grind,
    }
    roles = {
        "namespace": ns,
        "chain_type": chain,
        "halt_constructor": halt,
        "step_constructor": step,
        "preservation_predicate": carries,
        "visible_statement": "VisibleStatement",
        "holdout_statements": ["Holdout1Statement", "Holdout2Statement"],
        "oracle_bridge": "oracle_bridge",
        "relevant_source_namespace": src_ns,
        "sham_source_namespace": sham_ns,
    }
    return files, roles


def _t1_hard_source(
    namespace: str,
    mode: str,
    modes: list[str],
    route: str,
    halt: str,
    edges: list[str],
    join: str,
    braid: str,
    laws: str,
    fields: list[str],
    *,
    reverse: bool,
) -> str:
    relations = [f"S{i}" for i in range(5)]
    relation_args = " ".join(relations)
    mode_declarations = "\n".join(f"  | {name}" for name in modes)
    edge_declarations = "\n".join(
        f"  | {edges[i]} {{x y : α}} {{finish : {mode}}} {{z : α}} :\n"
        f"      {relations[i]} x y → "
        f"{route} {relation_args} .{modes[(i + 1) % 5]} y finish z →\n"
        f"      {route} {relation_args} .{modes[i]} x finish z"
        for i in range(5)
    )
    if reverse:
        field_declarations = "\n".join(
            f"  {fields[i]} : ∀ x y, {relations[i]} x y → "
            f"P .{modes[(i + 1) % 5]} y → P .{modes[i]} x"
            for i in range(5)
        )
        edge_proofs = "\n".join(
            f"  | {edges[i]} edge tail ih => exact rules.{fields[i]} _ _ edge (ih hz)"
            for i in range(5)
        )
        theorem_tail = (
            f"(path : {route} {relation_args} start x finish z) (hz : P finish z) : "
            "P start x := by\n"
            "  induction path with\n"
            f"  | {halt} pointMode point => exact hz\n"
            f"{edge_proofs}\n"
            f"  | {join} first second ihFirst ihSecond => exact ihFirst (ihSecond hz)\n"
            f"  | {braid} first second third ihFirst ihSecond ihThird =>\n"
            "      exact ihFirst (ihSecond (ihThird hz))"
        )
    else:
        field_declarations = "\n".join(
            f"  {fields[i]} : ∀ x y, {relations[i]} x y → "
            f"P .{modes[i]} x → P .{modes[(i + 1) % 5]} y"
            for i in range(5)
        )
        edge_proofs = "\n".join(
            f"  | {edges[i]} edge tail ih => exact ih (rules.{fields[i]} _ _ edge hx)"
            for i in range(5)
        )
        theorem_tail = (
            f"(path : {route} {relation_args} start x finish z) (hx : P start x) : "
            "P finish z := by\n"
            "  induction path with\n"
            f"  | {halt} pointMode point => exact hx\n"
            f"{edge_proofs}\n"
            f"  | {join} first second ihFirst ihSecond => exact ihSecond (ihFirst hx)\n"
            f"  | {braid} first second third ihFirst ihSecond ihThird =>\n"
            "      exact ihThird (ihSecond (ihFirst hx))"
        )
    return _text(
        f"""
namespace {namespace}

universe u

inductive {mode} where
{mode_declarations}

inductive {route} {{α : Type u}}
    ({relation_args} : α → α → Prop) :
    {mode} → α → {mode} → α → Type u where
  | {halt} (pointMode : {mode}) (point : α) :
      {route} {relation_args} pointMode point pointMode point
{edge_declarations}
  | {join} {{start middle finish : {mode}}} {{x y z : α}} :
      {route} {relation_args} start x middle y →
      {route} {relation_args} middle y finish z →
      {route} {relation_args} start x finish z
  | {braid} {{m0 m1 m2 m3 : {mode}}} {{w x y z : α}} :
      {route} {relation_args} m0 w m1 x →
      {route} {relation_args} m1 x m2 y →
      {route} {relation_args} m2 y m3 z →
      {route} {relation_args} m0 w m3 z

structure {laws} {{α : Type u}}
    ({relation_args} : α → α → Prop)
    (P : {mode} → α → Prop) : Prop where
{field_declarations}

theorem solved_bridge {{α : Type u}}
    {{{relation_args} : α → α → Prop}}
    {{P : {mode} → α → Prop}}
    (rules : {laws} {relation_args} P)
    {{start finish : {mode}}} {{x z : α}}
    {theorem_tail}

#print axioms solved_bridge

end {namespace}
"""
    )


def _t1_hard_files(
    spec: WorldSpec, rng: random.Random
) -> tuple[dict[str, str], dict[str, str]]:
    ns = f"P3.{spec.world_id}"

    def names() -> tuple[str, list[str], str, str, list[str], str, str, str, list[str]]:
        return (
            _opaque_name(rng, "Q").capitalize(),
            [_opaque_name(rng, "q") for _ in range(5)],
            _opaque_name(rng, "Q").capitalize(),
            _opaque_name(rng, "q"),
            [_opaque_name(rng, "q") for _ in range(5)],
            _opaque_name(rng, "q"),
            _opaque_name(rng, "q"),
            _opaque_name(rng, "Q").capitalize(),
            [_opaque_name(rng, "q") for _ in range(5)],
        )

    mode, modes, route, halt, edges, join, braid, laws, fields = names()
    src_ns = _opaque_name(rng, "S").capitalize()
    src = names()
    sham_ns = _opaque_name(rng, "S").capitalize()
    sham = names()
    relations = [f"R{i}" for i in range(5)]
    relation_args = " ".join(relations)
    mode_declarations = "\n".join(f"  | {name}" for name in modes)
    edge_declarations = "\n".join(
        f"  | {edges[i]} {{x y : α}} {{finish : {mode}}} {{z : α}} :\n"
        f"      {relations[i]} x y → "
        f"{route} {relation_args} .{modes[(i + 1) % 5]} y finish z →\n"
        f"      {route} {relation_args} .{modes[i]} x finish z"
        for i in range(5)
    )
    field_declarations = "\n".join(
        f"  {fields[i]} : ∀ x y, {relations[i]} x y → "
        f"P .{modes[i]} x → P .{modes[(i + 1) % 5]} y"
        for i in range(5)
    )
    base = _text(
        f"""
namespace {ns}

universe u

inductive {mode} where
{mode_declarations}

inductive {route} {{α : Type u}}
    ({relation_args} : α → α → Prop) :
    {mode} → α → {mode} → α → Type u where
  | {halt} (pointMode : {mode}) (point : α) :
      {route} {relation_args} pointMode point pointMode point
{edge_declarations}
  | {join} {{start middle finish : {mode}}} {{x y z : α}} :
      {route} {relation_args} start x middle y →
      {route} {relation_args} middle y finish z →
      {route} {relation_args} start x finish z
  | {braid} {{m0 m1 m2 m3 : {mode}}} {{w x y z : α}} :
      {route} {relation_args} m0 w m1 x →
      {route} {relation_args} m1 x m2 y →
      {route} {relation_args} m2 y m3 z →
      {route} {relation_args} m0 w m3 z

structure {laws} {{α : Type u}}
    ({relation_args} : α → α → Prop)
    (P : {mode} → α → Prop) : Prop where
{field_declarations}

end {ns}
"""
    )
    signature = (
        f"∀ (α : Type) ({' '.join(relations)} : α → α → Prop)\n"
        f"    (P : {mode} → α → Prop),\n"
        f"    {laws} {relation_args} P →\n"
    )
    visible = _text(
        f"""
import World.Base

namespace {ns}

def VisibleStatement : Prop :=
  {signature}    ∀ (w x y z : α),
      {route} {relation_args} .{modes[0]} w .{modes[2]} x →
      {relations[2]} x y →
      {route} {relation_args} .{modes[3]} y .{modes[4]} z →
      P .{modes[0]} w → P .{modes[4]} z

end {ns}
"""
    )
    holdout1 = _text(
        f"""
import World.Base

namespace {ns}

def Holdout1Statement : Prop :=
  {signature}    ∀ (x y z : α),
      {route} {relation_args} .{modes[1]} x .{modes[3]} y →
      {route} {relation_args} .{modes[3]} y .{modes[0]} z →
      P .{modes[1]} x → P .{modes[0]} z

end {ns}
"""
    )
    holdout2 = _text(
        f"""
import World.Base

namespace {ns}

def Holdout2Statement : Prop :=
  {signature}    ∀ (w x y z : α),
      {relations[4]} w x →
      {route} {relation_args} .{modes[0]} x .{modes[4]} y →
      {relations[4]} y z →
      P .{modes[4]} w → P .{modes[0]} z

end {ns}
"""
    )
    edge_proofs = "\n".join(
        f"  | {edges[i]} edge tail ih => exact ih (rules.{fields[i]} _ _ edge hx)"
        for i in range(5)
    )
    oracle = _text(
        f"""
import World.Base

namespace {ns}

universe u

theorem oracle_bridge {{α : Type u}}
    {{{relation_args} : α → α → Prop}}
    {{P : {mode} → α → Prop}}
    (rules : {laws} {relation_args} P)
    {{start finish : {mode}}} {{x z : α}}
    (path : {route} {relation_args} start x finish z) (hx : P start x) :
    P finish z := by
  induction path with
  | {halt} pointMode point => exact hx
{edge_proofs}
  | {join} first second ihFirst ihSecond => exact ihSecond (ihFirst hx)
  | {braid} first second third ihFirst ihSecond ihThird =>
      exact ihThird (ihSecond (ihFirst hx))

end {ns}
"""
    )
    checks = _text(
        f"""
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle

namespace {ns}

theorem oracle_visible : VisibleStatement := by
  intro α R0 R1 R2 R3 R4 P rules w x y z first edge second hw
  exact oracle_bridge rules second (rules.{fields[2]} _ _ edge (oracle_bridge rules first hw))

theorem oracle_holdout1 : Holdout1Statement := by
  intro α R0 R1 R2 R3 R4 P rules x y z first second hx
  exact oracle_bridge rules second (oracle_bridge rules first hx)

theorem oracle_holdout2 : Holdout2Statement := by
  intro α R0 R1 R2 R3 R4 P rules w x y z first path last hw
  exact rules.{fields[4]} _ _ last (oracle_bridge rules path (rules.{fields[4]} _ _ first hw))

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end {ns}
"""
    )
    relevant_source_lean = _t1_hard_source(src_ns, *src, reverse=False)
    sham_source_lean = _t1_hard_source(sham_ns, *sham, reverse=True)
    relevant_md = _text(
        f"""
# Solved source world

This independent world establishes transport over an indexed route.

```lean
{relevant_source_lean.rstrip()}
```
"""
    )
    sham_md = _text(
        f"""
# Solved source world

This independent world establishes transport over an indexed route.

```lean
{sham_source_lean.rstrip()}
```
"""
    )
    relevant_adapter = oracle.replace("oracle_bridge", "relevant_adapter_bridge")
    reverse_edge_proofs = "\n".join(
        f"  | {edges[i]} edge tail ih => exact rules.{fields[i]} _ _ edge (ih hz)"
        for i in range(5)
    )
    sham_adapter = _text(
        f"""
import World.Base

namespace {ns}

universe u

theorem sham_adapter_bridge {{α : Type u}}
    {{{relation_args} : α → α → Prop}}
    {{P : {mode} → α → Prop}}
    (rules : {laws} {relation_args} P)
    {{start finish : {mode}}} {{x z : α}}
    (path : {route} {relation_args} start x finish z) (hz : P finish z) :
    P start x := by
  induction path with
  | {halt} pointMode point => exact hz
{reverse_edge_proofs}
  | {join} first second ihFirst ihSecond => exact ihFirst (ihSecond hz)
  | {braid} first second third ihFirst ihSecond ihThird =>
      exact ihFirst (ihSecond (ihThird hz))

end {ns}
"""
    )
    witness_fields = "\n".join(
        f"  {fields[i]} := by intro x y edge hx; exact True.intro" for i in range(5)
    )
    nonvacuity = _text(
        f"""
import World.Base

namespace {ns}

def witnessRelation (_ _ : Unit) : Prop := True
def witnessProperty (_ : {mode}) (_ : Unit) : Prop := True

def witnessRules : {laws} witnessRelation witnessRelation witnessRelation
    witnessRelation witnessRelation witnessProperty where
{witness_fields}

theorem nonvacuity : witnessProperty .{modes[0]} () := True.intro

#print axioms nonvacuity

end {ns}
"""
    )
    automatic_simp = _text(
        f"""
import World.ChallengeVisible

namespace {ns}

theorem automatic_simp : VisibleStatement := by
  simp [VisibleStatement, {laws}]

end {ns}
"""
    )
    automatic_grind = _text(
        f"""
import World.ChallengeVisible

namespace {ns}

theorem automatic_grind : VisibleStatement := by
  grind [VisibleStatement, {laws}]

end {ns}
"""
    )
    files = {
        "World/Base.lean": base,
        "World/ChallengeVisible.lean": visible,
        "World/Holdout1.lean": holdout1,
        "World/Holdout2.lean": holdout2,
        "Sources/Relevant.md": relevant_md,
        "Sources/Sham.md": sham_md,
        "Hidden/Oracle.lean": oracle,
        "Hidden/OracleChecks.lean": checks,
        "Hidden/RelevantSource.lean": relevant_source_lean,
        "Hidden/ShamSource.lean": sham_source_lean,
        "Hidden/RelevantAdapter.lean": relevant_adapter,
        "Hidden/ShamAdapter.lean": sham_adapter,
        "Hidden/NonVacuity.lean": nonvacuity,
        "Hidden/AutomationSimp.lean": automatic_simp,
        "Hidden/AutomationGrind.lean": automatic_grind,
    }
    roles = {
        "namespace": ns,
        "mode_type": mode,
        "mode_constructors": modes,
        "route_type": route,
        "halt_constructor": halt,
        "edge_constructors": edges,
        "join_constructor": join,
        "braid_constructor": braid,
        "laws_type": laws,
        "law_fields": fields,
        "visible_statement": "VisibleStatement",
        "holdout_statements": ["Holdout1Statement", "Holdout2Statement"],
        "oracle_bridge": "oracle_bridge",
        "relevant_source_namespace": src_ns,
        "sham_source_namespace": sham_ns,
    }
    return files, roles


def _t2_source(
    namespace: str,
    tree: str,
    leaf: str,
    fork: str,
    mapper: str,
    evaluator: str,
    law: str,
    *,
    mirrored: bool,
) -> str:
    left_map = f"{mapper} f right" if mirrored else f"{mapper} f left"
    right_map = f"{mapper} f left" if mirrored else f"{mapper} f right"
    law_rhs = "opB (encode y) (encode x)" if mirrored else "opB (encode x) (encode y)"
    rewrite_order = "ihRight, ihLeft" if mirrored else "ihLeft, ihRight"
    return _text(
        f"""
namespace {namespace}

universe u v

inductive {tree} (α : Type u) where
  | {leaf} : α → {tree} α
  | {fork} : {tree} α → {tree} α → {tree} α

def {mapper} {{α : Type u}} {{β : Type v}} (f : α → β) : {tree} α → {tree} β
  | .{leaf} x => .{leaf} (f x)
  | .{fork} left right => .{fork} ({left_map}) ({right_map})

def {evaluator} {{α : Type u}} (op : α → α → α) : {tree} α → α
  | .{leaf} x => x
  | .{fork} left right => op ({evaluator} op left) ({evaluator} op right)

def {law} {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ (x y : α), encode (opA x y) = {law_rhs}

theorem solved_bridge {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : {law} encode opA opB) :
    ∀ t : {tree} α,
      encode ({evaluator} opA t) = {evaluator} opB ({mapper} encode t) := by
  intro t
  induction t with
  | {leaf} x => rfl
  | {fork} left right ihLeft ihRight =>
      simp only [{evaluator}, {mapper}]
      rw [h, {rewrite_order}]

#print axioms solved_bridge

end {namespace}
"""
    )


def _t2_files(spec: WorldSpec, rng: random.Random) -> tuple[dict[str, str], dict[str, str]]:
    ns = f"P3.{spec.world_id}"
    tree = _opaque_name(rng, "q").capitalize()
    leaf = _opaque_name(rng, "q")
    fork = _opaque_name(rng, "q")
    mapper = _opaque_name(rng, "q")
    evaluator = _opaque_name(rng, "q")
    law = _opaque_name(rng, "q")

    src_ns = _opaque_name(rng, "S").capitalize()
    src_tree = _opaque_name(rng, "q").capitalize()
    src_leaf = _opaque_name(rng, "q")
    src_fork = _opaque_name(rng, "q")
    src_map = _opaque_name(rng, "q")
    src_eval = _opaque_name(rng, "q")
    src_law = _opaque_name(rng, "q")

    sham_ns = _opaque_name(rng, "S").capitalize()
    sham_tree = _opaque_name(rng, "q").capitalize()
    sham_leaf = _opaque_name(rng, "q")
    sham_fork = _opaque_name(rng, "q")
    sham_map = _opaque_name(rng, "q")
    sham_eval = _opaque_name(rng, "q")
    sham_law = _opaque_name(rng, "q")

    base = _text(
        f"""
namespace {ns}

universe u v

inductive {tree} (α : Type u) where
  | {leaf} : α → {tree} α
  | {fork} : {tree} α → {tree} α → {tree} α

def {mapper} {{α : Type u}} {{β : Type v}} (f : α → β) : {tree} α → {tree} β
  | .{leaf} x => .{leaf} (f x)
  | .{fork} left right => .{fork} ({mapper} f left) ({mapper} f right)

def {evaluator} {{α : Type u}} (op : α → α → α) : {tree} α → α
  | .{leaf} x => x
  | .{fork} left right => op ({evaluator} op left) ({evaluator} op right)

def {law} {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ (x y : α), encode (opA x y) = opB (encode x) (encode y)

end {ns}
"""
    )

    visible_term = _text(
        f"""
def visibleTerm {{α : Type}} (a b c d e : α) : {tree} α :=
  .{fork} (.{fork} (.{leaf} a) (.{fork} (.{leaf} b) (.{leaf} c)))
    (.{fork} (.{leaf} d) (.{leaf} e))
"""
    ).rstrip()
    holdout1_term = _text(
        f"""
def holdout1Term {{α : Type}} (a b c d e f : α) : {tree} α :=
  .{fork} (.{leaf} a)
    (.{fork} (.{fork} (.{leaf} b) (.{leaf} c))
      (.{fork} (.{leaf} d) (.{fork} (.{leaf} e) (.{leaf} f))))
"""
    ).rstrip()
    holdout2_term = _text(
        f"""
def holdout2Term {{α : Type}} (a b c d e f g : α) : {tree} α :=
  .{fork}
    (.{fork} (.{fork} (.{leaf} a) (.{leaf} b)) (.{leaf} c))
    (.{fork} (.{leaf} d) (.{fork} (.{leaf} e) (.{fork} (.{leaf} f) (.{leaf} g))))
"""
    ).rstrip()

    visible = _text(
        f"""
import World.Base

namespace {ns}

{visible_term}

def VisibleStatement : Prop :=
  ∀ (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β),
    {law} encode opA opB →
    ∀ (a b c d e : α),
      encode ({evaluator} opA (visibleTerm a b c d e)) =
        {evaluator} opB ({mapper} encode (visibleTerm a b c d e))

end {ns}
"""
    )
    holdout1 = _text(
        f"""
import World.Base

namespace {ns}

{holdout1_term}

def Holdout1Statement : Prop :=
  ∀ (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β),
    {law} encode opA opB →
    ∀ (a b c d e f : α),
      encode ({evaluator} opA (holdout1Term a b c d e f)) =
        {evaluator} opB ({mapper} encode (holdout1Term a b c d e f))

end {ns}
"""
    )
    holdout2 = _text(
        f"""
import World.Base

namespace {ns}

{holdout2_term}

def Holdout2Statement : Prop :=
  ∀ (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β),
    {law} encode opA opB →
    ∀ (a b c d e f g : α),
      encode ({evaluator} opA (holdout2Term a b c d e f g)) =
        {evaluator} opB ({mapper} encode (holdout2Term a b c d e f g))

end {ns}
"""
    )

    bridge_body = _text(
        f"""
import World.Base

namespace {ns}

universe u v

theorem oracle_bridge {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : {law} encode opA opB) :
    ∀ t : {tree} α,
      encode ({evaluator} opA t) = {evaluator} opB ({mapper} encode t) := by
  intro t
  induction t with
  | {leaf} x => rfl
  | {fork} left right ihLeft ihRight =>
      simp only [{evaluator}, {mapper}]
      rw [h, ihLeft, ihRight]

end {ns}
"""
    )

    checks = _text(
        f"""
import World.ChallengeVisible
import World.Holdout1
import World.Holdout2
import Hidden.Oracle

namespace {ns}

theorem oracle_visible : VisibleStatement := by
  intro α β encode opA opB h a b c d e
  exact oracle_bridge encode opA opB h (visibleTerm a b c d e)

theorem oracle_holdout1 : Holdout1Statement := by
  intro α β encode opA opB h a b c d e f
  exact oracle_bridge encode opA opB h (holdout1Term a b c d e f)

theorem oracle_holdout2 : Holdout2Statement := by
  intro α β encode opA opB h a b c d e f g
  exact oracle_bridge encode opA opB h (holdout2Term a b c d e f g)

#print axioms oracle_bridge
#print axioms oracle_visible
#print axioms oracle_holdout1
#print axioms oracle_holdout2

end {ns}
"""
    )

    relevant_source_lean = _t2_source(
        src_ns, src_tree, src_leaf, src_fork, src_map, src_eval, src_law, mirrored=False
    )
    sham_source_lean = _t2_source(
        sham_ns, sham_tree, sham_leaf, sham_fork, sham_map, sham_eval, sham_law, mirrored=True
    )
    relevant_md = _text(
        f"""
# Solved source world

This independent world proves that evaluation commutes with a structural translation.

```lean
{relevant_source_lean.rstrip()}
```
"""
    )
    sham_md = _text(
        f"""
# Solved source world

This independent world proves that evaluation commutes with a mirrored translation.

```lean
{sham_source_lean.rstrip()}
```
"""
    )

    relevant_adapter = bridge_body.replace("oracle_bridge", "relevant_adapter_bridge")
    sham_adapter = _text(
        f"""
import World.Base

namespace {ns}

universe u v

theorem sham_adapter_bridge {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : {law} encode opA opB) :
    ∀ left right : {tree} α,
      encode ({evaluator} opA (.{fork} left right)) =
        opB ({evaluator} opB ({mapper} encode right))
          ({evaluator} opB ({mapper} encode left)) := by
  intro left right
  simp only [{evaluator}]
  rw [h]

end {ns}
"""
    )
    nonvacuity = _text(
        f"""
import World.Base

namespace {ns}

def witnessEncode (value : Unit) : Unit := value
def witnessOperation (_left _right : Unit) : Unit := ()

theorem nonvacuity : {law} witnessEncode witnessOperation witnessOperation := by
  intro x y
  cases x
  cases y
  rfl

#print axioms nonvacuity

end {ns}
"""
    )
    automatic_simp = _text(
        f"""
import World.ChallengeVisible

namespace {ns}

theorem automatic_simp : VisibleStatement := by
  simp [VisibleStatement, visibleTerm, {law}, {evaluator}, {mapper}]

end {ns}
"""
    )
    automatic_grind = _text(
        f"""
import World.ChallengeVisible

namespace {ns}

theorem automatic_grind : VisibleStatement := by
  grind [VisibleStatement, visibleTerm, {law}, {evaluator}, {mapper}]

end {ns}
"""
    )

    files = {
        "World/Base.lean": base,
        "World/ChallengeVisible.lean": visible,
        "World/Holdout1.lean": holdout1,
        "World/Holdout2.lean": holdout2,
        "Sources/Relevant.md": relevant_md,
        "Sources/Sham.md": sham_md,
        "Hidden/Oracle.lean": bridge_body,
        "Hidden/OracleChecks.lean": checks,
        "Hidden/RelevantSource.lean": relevant_source_lean,
        "Hidden/ShamSource.lean": sham_source_lean,
        "Hidden/RelevantAdapter.lean": relevant_adapter,
        "Hidden/ShamAdapter.lean": sham_adapter,
        "Hidden/NonVacuity.lean": nonvacuity,
        "Hidden/AutomationSimp.lean": automatic_simp,
        "Hidden/AutomationGrind.lean": automatic_grind,
    }
    roles = {
        "namespace": ns,
        "tree_type": tree,
        "leaf_constructor": leaf,
        "fork_constructor": fork,
        "map_function": mapper,
        "eval_function": evaluator,
        "commutation_predicate": law,
        "visible_statement": "VisibleStatement",
        "holdout_statements": ["Holdout1Statement", "Holdout2Statement"],
        "oracle_bridge": "oracle_bridge",
        "relevant_source_namespace": src_ns,
        "sham_source_namespace": sham_ns,
    }
    return files, roles


def _t2_scoped_parts(namespace: str, names: tuple[str, ...], *, mirrored: bool = False):
    """Binding forces the transport proof to generalize over related environments."""
    term, var, lit, pair, bind, extend, mapper, evaluator, law = names
    mapped_left = f"{mapper} f right" if mirrored else f"{mapper} f left"
    mapped_right = f"{mapper} f left" if mirrored else f"{mapper} f right"
    law_rhs = "opB (encode y) (encode x)" if mirrored else "opB (encode x) (encode y)"
    induction_order = "ihRight envA envB related, ihLeft envA envB related" if mirrored else "ihLeft envA envB related, ihRight envA envB related"
    definitions = _text(f"""
namespace {namespace}
universe u v

inductive ScopedIndex : Nat → Type where
  | first {{n : Nat}} : ScopedIndex (Nat.succ n)
  | rest {{n : Nat}} : ScopedIndex n → ScopedIndex (Nat.succ n)

inductive {term} (α : Type u) : Nat → Type u where
  | {var} {{n : Nat}} : ScopedIndex n → {term} α n
  | {lit} {{n : Nat}} : α → {term} α n
  | {pair} {{n : Nat}} : {term} α n → {term} α n → {term} α n
  | {bind} {{n : Nat}} : {term} α n → {term} α (Nat.succ n) → {term} α n

def {extend} {{α : Type u}} {{n : Nat}} (head : α) (tail : ScopedIndex n → α) : ScopedIndex (Nat.succ n) → α
  | .first => head
  | .rest i => tail i

def {mapper} {{α : Type u}} {{β : Type v}} (f : α → β) {{n : Nat}} : {term} α n → {term} β n
  | .{var} i => .{var} i
  | .{lit} a => .{lit} (f a)
  | .{pair} left right => .{pair} ({mapped_left}) ({mapped_right})
  | .{bind} value body => .{bind} ({mapper} f value) ({mapper} f body)

def {evaluator} {{α : Type u}} (op : α → α → α) {{n : Nat}}
    (env : ScopedIndex n → α) : {term} α n → α
  | .{var} i => env i
  | .{lit} a => a
  | .{pair} left right => op ({evaluator} op env left) ({evaluator} op env right)
  | .{bind} value body => {evaluator} op ({extend} ({evaluator} op env value) env) body

def {law} {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ x y, encode (opA x y) = {law_rhs}

end {namespace}
""")
    theorem = _text(f"""
namespace {namespace}
universe u v

theorem oracle_bridge {{α : Type u}} {{β : Type v}}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : {law} encode opA opB) {{n : Nat}} (t : {term} α n) :
    ∀ (envA : ScopedIndex n → α) (envB : ScopedIndex n → β),
      (∀ i, encode (envA i) = envB i) →
      encode ({evaluator} opA envA t) = {evaluator} opB envB ({mapper} encode t) := by
  induction t with
  | {var} i =>
      intro envA envB related
      exact related i
  | {lit} a =>
      intro envA envB related
      rfl
  | {pair} left right ihLeft ihRight =>
      intro envA envB related
      simp only [{evaluator}, {mapper}]
      rw [h, {induction_order}]
  | {bind} value body ihValue ihBody =>
      intro envA envB related
      simp only [{evaluator}, {mapper}]
      apply ihBody
      intro i
      cases i with
      | first => exact ihValue envA envB related
      | rest j => exact related j

end {namespace}
""")
    return definitions, theorem


def _t2_hard_files(spec: WorldSpec, rng: random.Random):
    ns = f"P3.{spec.world_id}"

    def names():
        return (_opaque_name(rng, "Q").capitalize(),) + tuple(_opaque_name(rng, "q") for _ in range(8))

    target_names = names()
    term, var, lit, pair, bind, extend, mapper, evaluator, law = target_names
    src_ns, sham_ns = _opaque_name(rng, "S").capitalize(), _opaque_name(rng, "S").capitalize()
    src_names, sham_names = names(), names()
    base, bridge = _t2_scoped_parts(ns, target_names)
    source_base, source_bridge = _t2_scoped_parts(src_ns, src_names)
    sham_base, sham_bridge = _t2_scoped_parts(sham_ns, sham_names, mirrored=True)
    relevant_source = source_base + source_bridge.replace("oracle_bridge", "solved_bridge") + f"\n#print axioms {src_ns}.solved_bridge\n"
    sham_source = sham_base + sham_bridge.replace("oracle_bridge", "solved_bridge") + f"\n#print axioms {sham_ns}.solved_bridge\n"

    signature = f"""∀ (α β : Type) (encode : α → β) (opA : α → α → α) (opB : β → β → β),
    {law} encode opA opB → ∀ (n : Nat) (env : ScopedIndex n → α),"""
    terms = {
        "Visible": (f"(a : {term} α n) (b : {term} α (Nat.succ n))", f"(.{bind} a b)", "a b"),
        "Holdout1": (f"(a b : {term} α n)", f"(.{pair} a b)", "a b"),
        "Holdout2": (f"(a : {term} α n) (b : {term} α (Nat.succ n)) (c : {term} α (Nat.succ (Nat.succ n)))", f"(.{bind} a (.{bind} b c))", "a b c"),
    }
    targets = {}
    proofs = []
    for label, (arguments, expression, introduced) in terms.items():
        targets[label] = _text(f"""
import World.Base
namespace {ns}

def {label}Statement : Prop :=
  {signature}
    ∀ {arguments},
      encode ({evaluator} opA env {expression}) =
        {evaluator} opB (fun i => encode (env i)) ({mapper} encode {expression})

end {ns}
""")
        proofs.append(f"""theorem oracle_{label.lower()} : {label}Statement := by
  intro α β encode opA opB h n env {introduced}
  exact oracle_bridge encode opA opB h {expression} env (fun i => encode (env i)) (fun _ => rfl)

#print axioms oracle_{label.lower()}""")
    checks = _text("import World.ChallengeVisible\nimport World.Holdout1\nimport World.Holdout2\nimport Hidden.Oracle\n"
                   + f"namespace {ns}\n" + "\n\n".join(proofs) + f"\n#print axioms oracle_bridge\nend {ns}")
    nonvacuity = _text(f"""
import World.Base
namespace {ns}

theorem nonvacuity : {law} (fun x : Unit => x) (fun _ _ => ()) (fun _ _ => ()) := by
  intro x y
  rfl

#print axioms nonvacuity
end {ns}
""")
    sham_adapter = _text(f"""
import World.Base
namespace {ns}
theorem sham_adapter_bridge (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β) (h : {law} encode opA opB) :
    ∀ x y, encode (opA x y) = opB (encode y) (encode x) := by
  intro x y
  rw [h]
end {ns}
""")
    files = {
        "World/Base.lean": base,
        "World/ChallengeVisible.lean": targets["Visible"],
        "World/Holdout1.lean": targets["Holdout1"],
        "World/Holdout2.lean": targets["Holdout2"],
        "Hidden/Oracle.lean": "import World.Base\n" + bridge,
        "Hidden/OracleChecks.lean": checks,
        "Hidden/RelevantSource.lean": relevant_source,
        "Hidden/ShamSource.lean": sham_source,
        "Hidden/RelevantAdapter.lean": "import World.Base\n" + bridge.replace("oracle_bridge", "relevant_adapter_bridge"),
        "Hidden/ShamAdapter.lean": sham_adapter,
        "Hidden/NonVacuity.lean": nonvacuity,
    }
    for label, source in (("Relevant", relevant_source), ("Sham", sham_source)):
        files[f"Sources/{label}.md"] = "# Solved source world\n\nA translation commutes with evaluation under related environments.\n\n```lean\n" + source + "```\n"
    for label, tactic in (("Simp", "simp"), ("Grind", "grind")):
        files[f"Hidden/Automation{label}.lean"] = _text(f"""
import World.ChallengeVisible
namespace {ns}
theorem automatic_{tactic} : VisibleStatement := by
  {tactic} [VisibleStatement, {law}, {evaluator}, {mapper}, {extend}]
end {ns}
""")
    roles = {
        "namespace": ns, "term_type": term, "variable_constructor": var,
        "literal_constructor": lit, "pair_constructor": pair, "binding_constructor": bind,
        "extend_function": extend, "map_function": mapper, "eval_function": evaluator,
        "commutation_predicate": law, "visible_statement": "VisibleStatement",
        "holdout_statements": ["Holdout1Statement", "Holdout2Statement"],
        "oracle_bridge": "oracle_bridge", "relevant_source_namespace": src_ns,
        "sham_source_namespace": sham_ns,
    }
    return files, roles


def build_world(spec: WorldSpec) -> GeneratedWorld:
    """Build one world without touching the filesystem."""
    rng = random.Random(spec.seed)
    if spec.template == "T1":
        body, roles = _t1_hard_files(spec, rng) if spec.difficulty == "hard" else _t1_files(spec, rng)
    else:
        body, roles = _t2_hard_files(spec, rng) if spec.difficulty == "hard" else _t2_files(spec, rng)

    files: dict[str, str] = {
        "lakefile.toml": _lakefile(spec),
        "lean-toolchain": spec.toolchain + "\n",
        **body,
    }
    public_files = [
        "lakefile.toml",
        "lean-toolchain",
        "World/Base.lean",
        "World/ChallengeVisible.lean",
        "Sources/Relevant.md",
        "Sources/Sham.md",
    ]
    hidden_files = sorted(set(files) - set(public_files))
    artifact_hashes = {
        path: _sha256_bytes(content.encode("utf-8")) for path, content in sorted(files.items())
    }
    metadata: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": (
            HARD_GENERATOR_VERSION if spec.difficulty == "hard" else GENERATOR_VERSION
        ),
        "world_id": spec.world_id,
        "template": spec.template,
        "seed_hex": f"{spec.seed:016x}",
        "phase": spec.phase,
        "eligible_for_main": spec.eligible_for_main,
        "toolchain": spec.toolchain,
        "roles": roles,
        "public_files": public_files,
        "hidden_files": hidden_files,
        "lean_checks": {
            "must_compile": [
                "World/Base.lean",
                "World/ChallengeVisible.lean",
                "World/Holdout1.lean",
                "World/Holdout2.lean",
                "Hidden/Oracle.lean",
                "Hidden/OracleChecks.lean",
                "Hidden/RelevantSource.lean",
                "Hidden/ShamSource.lean",
                "Hidden/RelevantAdapter.lean",
                "Hidden/NonVacuity.lean",
            ],
            "must_fail": [
                "Hidden/ShamAdapter.lean",
                "Hidden/AutomationSimp.lean",
                "Hidden/AutomationGrind.lean",
            ],
            "axiom_audits": {
                "Hidden/OracleChecks.lean": 4,
                "Hidden/RelevantSource.lean": 1,
                "Hidden/ShamSource.lean": 1,
                "Hidden/NonVacuity.lean": 1,
            },
        },
        "source_balance": {
            "relevant_chars": len(files["Sources/Relevant.md"]),
            "sham_chars": len(files["Sources/Sham.md"]),
            "relevant_words": len(files["Sources/Relevant.md"].split()),
            "sham_words": len(files["Sources/Sham.md"].split()),
        },
        "artifact_hashes": artifact_hashes,
    }
    if spec.difficulty != "standard":
        metadata["difficulty"] = spec.difficulty
        metadata["allowed_axioms"] = ["propext", "Quot.sound", "Classical.choice"]
    metadata_text = json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    files["metadata.json"] = metadata_text
    manifest_paths = sorted(files)
    files["manifest.sha256"] = "".join(
        f"{_sha256_bytes(files[path].encode('utf-8'))}  {path}\n" for path in manifest_paths
    )
    return GeneratedWorld(spec=spec, files=files, metadata=metadata)


def write_world(world: GeneratedWorld, destination: Path | str) -> Path:
    """Materialize a generated world, refusing to overwrite different content.

    Re-running with the identical specification is idempotent.  Any divergent file or
    unexpected file requires a new destination, which protects frozen worlds.
    """
    root = Path(destination)
    expected = set(world.files)
    if root.exists():
        existing = {
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
            and ".lake" not in path.parts
            and path.name != "lake-manifest.json"
        }
        if existing != expected:
            raise FileExistsError(f"existing world differs at {root}")
        for rel, content in world.files.items():
            if (root / rel).read_text(encoding="utf-8") != content:
                raise FileExistsError(f"existing world differs at {root / rel}")
        return root

    for rel, content in world.files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return root
