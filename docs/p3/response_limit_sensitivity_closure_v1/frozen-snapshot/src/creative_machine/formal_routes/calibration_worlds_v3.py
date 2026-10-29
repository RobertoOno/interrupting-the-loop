"""Prospective P3 calibration worlds with explicit development exclusions.

Known families, not new mathematical routes. Keep all older generators immutable.
Every permitted development seed is declared here before calibration sampling.
"""

from __future__ import annotations

import itertools
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from . import conceptual_generator as development
from .prototypes import TARGETS, load_prototype
from .submission import STANDARD_LEAN_AXIOMS
from .validation import validate_world

REPO = development.REPO
VERSION = "1.0.0"
DEV_SEEDS = ("9300000000000001", "9300000000000002")
CALIBRATION_LEVELS = (5, 7, 11, 13, 17, 19)
STRATA = ((6, "different_at_10"), (8, "same_action"), (8, "any"))
REGISTRY = "docs/p3/development_exclusions_v3.json"


@dataclass(frozen=True)
class WorldV3Spec:
    family: str
    seed: str
    phase: str

    def __post_init__(self):
        development.ConceptualSpec(self.family, self.seed)
        if self.phase not in ("development", "calibration"):
            raise ValueError("v3 never enables the main sample")
        if (self.phase == "development") != (self.seed in DEV_SEEDS):
            raise ValueError("development must use a declared seed; calibration must not reuse one")

    @property
    def world_id(self):
        prefix = "CAL3" if self.phase == "calibration" else "DEV3X"
        opaque = development.sha(f"{VERSION}:{self.family}:{self.seed}:{self.phase}")[:16].upper()
        return f"{prefix}_{self.family[0].upper()}_{opaque}"


def development_orbits() -> set[tuple[str, str]]:
    registry = json.loads((REPO / REGISTRY).read_text())
    if development.sha(Path(development.__file__).read_text()) != registry["generator_sha256"]:
        raise ValueError("historical generator drift; cannot reconstruct exclusions")
    seen = {development.pair_orbit(p) for p in (*development.SOURCE_PAIRS, *development.PROTOTYPE_PAIRS,
                                               *registry["additional_literal_pair_used_in_tests"])}
    for seed in registry["all_known_development_seeds_by_family"]["representation"]:
        world = development.generate_conceptual(development.ConceptualSpec("representation", seed))
        seen.update(development.pair_orbit(p) for p in world.metadata["parameters"]["pairs"])
    return seen


def candidates(length: int, requirement: str, excluded: set) -> list[tuple[str, str]]:
    """One qualifying representative per literal orbit, sorted before drawing.

    Canonical keys are NOT substituted for the representative: a coordinate swap
    can change whether the particular probe point (1,0) distinguishes a pair.
    """
    if requirement not in {"different_at_10", "same_action", "any"}:
        raise ValueError("unknown sampling stratum")
    words = ["".join(w) for w in itertools.product("ab", repeat=length) if w.count("a") == length // 2]
    representatives = {}
    for u, v in itertools.combinations(words, 2):
        key = development.pair_orbit((u, v))
        if (u[0] == v[0] or u[-1] == v[-1] or key in excluded
                or development.action_at(u) == development.action_at(v)):
            continue
        if requirement == "different_at_10" and development.action_at(u, bits=True) == development.action_at(v, bits=True):
            continue
        if requirement == "same_action" and any(
            development.action_at(u, p, bits=True) != development.action_at(v, p, bits=True)
            for p in itertools.product((0, 1), repeat=2)
        ):
            continue
        representatives.setdefault(key, (u, v))
    return [representatives[key] for key in sorted(representatives)]


def sample_pairs(seed: str, excluded: set) -> tuple[list[tuple[str, str]], list[int]]:
    rng, used, pairs, counts = random.Random(int(seed, 16)), set(excluded), [], []
    for length, requirement in STRATA:
        eligible = candidates(length, requirement, used)
        if not eligible:
            raise ValueError("sampling stratum exhausted; do not recycle or silently alter it")
        pair = rng.choice(eligible)
        counts.append(len(eligible))
        pairs.append(pair)
        used.add(development.pair_orbit(pair))
    return pairs, counts


def calibration_orbits() -> set[tuple[str, str]]:
    old = development_orbits()
    seen = set(old)
    for seed in DEV_SEEDS:
        seen.update(development.pair_orbit(p) for p in sample_pairs(seed, old)[0])
    return seen


def exclusion_audit() -> dict:
    old, all_seen = development_orbits(), calibration_orbits()
    return {"old_short_holdout_remaining": len(candidates(6, "same_action", old)),
            "replacement_holdout_remaining_after_old_development": len(candidates(8, "same_action", old)),
            "remaining_after_all_declared_development": [
                {"length": length, "requirement": requirement, "literal_orbits": len(candidates(length, requirement, all_seen))}
                for length, requirement in STRATA],
            "development_seeds": list(DEV_SEEDS), "calibration_invariant_levels": list(CALIBRATION_LEVELS),
            "excluded_invariant_levels": [0, 1, 2, 3], "model_calls": 0,
            "structural_novelty_claimed": False}


def build_v3(spec: WorldV3Spec) -> development.ConceptualWorld:
    prototype = REPO / "worlds/prototypes" / development.FAMILIES[spec.family]
    original = load_prototype(prototype)
    relatives = ["World/Base.lean", *[row[0] for row in TARGETS.values()], "Hidden/Oracle.lean", "Hidden/OracleChecks.lean"]
    files = {rel: (prototype / rel).read_text() for rel in relatives}
    rng = random.Random(int(spec.seed, 16))
    if spec.family == "invariant":
        parameters = development._invariant_files(files, rng)
        level = 2 + DEV_SEEDS.index(spec.seed) if spec.phase == "development" else rng.choice(CALIBRATION_LEVELS)
        n = parameters["initial_parameter"]
        x, y, z = parameters["offsets"]
        files["World/Base.lean"] = development._replace_once(files["World/Base.lean"],
            f"⟨{n*n+1+x}, {n+y}, {1+z}⟩", f"⟨{n*n+level+x}, {n+y}, {1+z}⟩")
        parameters.update({"conserved_value": level, "variation": "different_conserved_value_not_n_or_offsets_alone",
                           "exclusion_key": {"conserved_value": level, "target_forms": "zero_x_negative_diagonal_equal_coordinates"}})
    else:
        excluded = development_orbits() if spec.phase == "development" else calibration_orbits()
        pairs, counts = sample_pairs(spec.seed, excluded)
        parameters = {"pairs": [list(p) for p in pairs], "candidate_orbit_counts": counts,
                      "strata": [list(s) for s in STRATA], "sampling_unit": "qualifying_literal_orbit",
                      "excluded_orbit_count": len(excluded), "excluded_orbits_sha256": development.sha(json.dumps(sorted(excluded))),
                      "variation": "new_word_pairs_same_known_relation"}
        files["Hidden/Diagnostics.lean"] = (prototype / "Hidden/Diagnostics.lean").read_text()
        mapping = {development.word(a): development.word(b) for old, new in zip(development.PROTOTYPE_PAIRS, pairs)
                   for a, b in zip(old, new)}
        pattern = "|".join(re.escape(w) for w in sorted(mapping, key=len, reverse=True))
        for rel in (*[row[0] for row in TARGETS.values()], "Hidden/OracleChecks.lean", "Hidden/Diagnostics.lean"):
            files[rel] = re.sub(pattern, lambda m: mapping[m.group()], files[rel])
    namespace = f"P3.{spec.world_id}"
    files = {rel: text.replace(original["roles"]["namespace"], namespace) for rel, text in files.items()}
    files["Hidden/OracleChecks.lean"] = development._audited(files["Hidden/OracleChecks.lean"])
    files["lean-toolchain"] = "leanprover/lean4:v4.33.1\n"
    files["lakefile.toml"] = f'name = "{spec.world_id.lower()}"\nversion = "1.0.0"\n' + "".join(
        f'\n[[lean_lib]]\nname = "{name}"\n' for name in ("World", "Hidden", "Sources"))
    source_hashes = {}
    for kind in ("Relevant", "Sham"):
        asset = f"{spec.family.title()}{kind}.lean"
        source = (development.ASSETS / asset).read_text()
        source_hashes[asset] = development.sha(source)
        files[f"Sources/{kind}.lean"] = development._audited(source)
        files[f"Sources/{kind}.md"] = development.SOURCE_HEADER + "```lean\n" + source + "```\n"
        files[f"Hidden/Adapted{kind}.lean"] = development.adapt_source(source, spec.family, namespace,
            parameters.get("offsets", []), "Adapted" if kind == "Relevant" else "AdaptedSham")
    development._source_checks(files, spec.family, namespace, parameters)
    if spec.family == "invariant":
        files["Hidden/Diagnostics.lean"] = development._audited(f"""import Hidden.Oracle
namespace {namespace}
theorem nonempty_dynamics : Reaches start (move1 start) :=
  Reaches.tail (Reaches.refl start) (Step.first start)
theorem nontrivial_dynamics : start ≠ move1 start := by decide
theorem inverse_round_trip : move2 (move1 start) = start ∧ move4 (move3 start) = start := by decide
theorem initial_conserved_value : balance start = {level} := by decide
def comparisonSeed (d n : Int) : State := ⟨n * n + d + ({x}), n + ({y}), 1 + ({z})⟩
theorem comparison_balance (d n : Int) : balance (comparisonSeed d n) = d := by
  grind [balance, comparisonSeed]
theorem different_components (d n : Int) (hne : d ≠ {level}) : ¬ Reaches start (comparisonSeed d n) := by
  intro h
  have conserved := oracle_bridge h
  rw [initial_conserved_value, comparison_balance] at conserved
  exact hne conserved.symm
theorem excludes_original_development (n : Int) : ¬ Reaches start (comparisonSeed 1 n) :=
  different_components 1 n (by decide)
end {namespace}
""")
    else:
        files["Hidden/Diagnostics.lean"] = development._audited(files["Hidden/Diagnostics.lean"])
    public = ["lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeVisible.lean"]
    lengths = {kind: len(files[f"Sources/{kind}.md"].split()) for kind in ("Relevant", "Sham")}
    metadata = {
        "schema_version": 1, "generator": "calibration_worlds_v3", "generator_version": VERSION,
        "world_id": spec.world_id, "family": spec.family, "seed": spec.seed, "phase": spec.phase,
        "status": "CALIBRATION_ONLY" if spec.phase == "calibration" else "DEVELOPMENT_ONLY",
        "eligible_for_main": False, "eligible_for_calibration": spec.phase == "calibration",
        "structural_novelty_claimed": False, "parameters": parameters,
        "allowed_axioms": list(STANDARD_LEAN_AXIOMS), "toolchain": "leanprover/lean4:v4.33.1",
        "sources_ready": True, "source_matching": {"words": lengths,
            "relative_word_gap": abs(lengths["Relevant"] - lengths["Sham"]) / max(lengths.values()),
            "tokenizer_matched": False, "difficulty_matched": False},
        "public_files": public, "hidden_files": sorted(set(files) - set(public)),
        "roles": {"namespace": namespace, "oracle_bridge": "oracle_bridge", "visible_statement": "VisibleStatement",
                  "holdout_statements": ["Holdout1Statement", "Holdout2Statement"]},
        "provenance": {"generator_sha256": development.sha(Path(__file__).read_text()),
            "previous_generator_sha256": development.sha(Path(development.__file__).read_text()),
            "development_registry_sha256": development.sha((REPO / REGISTRY).read_text()),
            "prototype_manifest_sha256": development.sha((prototype / "manifest.sha256").read_text()),
            "source_assets_sha256": source_hashes},
        "artifact_hashes": {rel: development.sha(text) for rel, text in sorted(files.items())},
        "lean_checks": {
            "must_compile": sorted(rel for rel in files if rel.endswith(".lean") and rel != "Hidden/AdaptedSham.lean"),
            "must_fail": ["Hidden/AdaptedSham.lean"],
            "axiom_audits": {rel: text.count("#print axioms ") for rel, text in files.items() if "#print axioms " in text},
        },
    }
    files["metadata.json"] = json.dumps(metadata, sort_keys=True, indent=2) + "\n"
    files["manifest.sha256"] = "".join(f"{development.sha(text)}  {rel}\n" for rel, text in sorted(files.items()))
    return development.ConceptualWorld(spec, files, metadata)


def load_v3(root: Path, *, phase: str | None = None) -> dict:
    if root.is_symlink():
        raise ValueError("world root must not be a symlink")
    validate_world(root).require_ok()
    metadata = json.loads((root / "metadata.json").read_text())
    spec = WorldV3Spec(metadata["family"], metadata["seed"], metadata["phase"])
    if phase is not None and spec.phase != phase:
        raise ValueError("wrong world phase")
    expected = build_v3(spec)
    if metadata != expected.metadata or any((root / rel).read_text() != text for rel, text in expected.files.items()):
        raise ValueError("v3 generator/assets/exclusion drift")
    return metadata
