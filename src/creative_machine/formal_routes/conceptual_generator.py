"""Seeded DEVELOPMENT instances of known mathematical families; no model calls.

This repo-local generator deliberately cannot produce main/calibration-eligible
worlds. A future behavioral freeze needs its own sampled fixtures and protocol.
Neither this module nor its assets modify the fingerprinted v1/v2 harness.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from .prototypes import TARGETS, load_prototype
from .submission import STANDARD_LEAN_AXIOMS
from .validation import validate_world

VERSION = "0.1.0"
REPO = Path(__file__).resolve().parents[3]
ASSETS = Path(__file__).parent / "assets/conceptual_v3"
FAMILIES = {"invariant": "DEV_INVARIANT_V3", "representation": "DEV_REPRESENTATION_V3"}
SOURCE_PAIRS = (("aaabbb", "bbbaaa"), ("aaabbb", "bbbbaa"))
PROTOTYPE_PAIRS = (("aabb", "abab"), ("abba", "baab"), ("aaabbb", "ababab"))
SOURCE_HEADER = "# Worked example\n\nA separate formal problem and its complete proof.\n\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConceptualSpec:
    family: str
    seed: str

    def __post_init__(self):
        if self.family not in FAMILIES or not re.fullmatch(r"[0-9a-f]{16}", self.seed):
            raise ValueError("known family and 16 lowercase hexadecimal seed characters required")

    @property
    def world_id(self) -> str:
        return f"DEV3_{self.family[0].upper()}_{self.seed.upper()}"


@dataclass(frozen=True)
class ConceptualWorld:
    spec: ConceptualSpec
    files: dict[str, str]
    metadata: dict


def word(value: str) -> str:
    return "[" + ", ".join(value) + "]"


def pair_orbit(pair: tuple[str, str]) -> tuple[str, str]:
    """Only a literal orbit: context trimming, reversal, swap, pair order.

    NOT a test of algebraic equivalence under arbitrary rewrite sequences.
    """
    u, v = pair
    while u and v and u[0] == v[0]:
        u, v = u[1:], v[1:]
    while u and v and u[-1] == v[-1]:
        u, v = u[:-1], v[:-1]
    variants = []
    for reverse, swap in itertools.product((False, True), repeat=2):
        items = [u, v]
        if reverse:
            items = [w[::-1] for w in items]
        if swap:
            items = [w.translate(str.maketrans("ab", "ba")) for w in items]
        variants.append(tuple(sorted(items)))
    return min(variants)


def action_at(w: str, point: tuple[int, int] = (1, 0), *, bits: bool = False) -> tuple[int, int]:
    x, y = point
    for mark in w:
        if mark == "a":
            x = (x ^ y) if bits else x + y
        elif mark == "b":
            y = (y ^ x) if bits else y - x
        else:
            raise ValueError("only a and b are supported")
    return x, y


def _sample_pairs(rng: random.Random) -> tuple[list[tuple[str, str]], list[int]]:
    excluded = {pair_orbit(pair) for pair in (*SOURCE_PAIRS, *PROTOTYPE_PAIRS)}
    selected, sizes = [], []
    for length, bit_requirement in ((6, "different_at_10"), (6, "same_action"), (8, "any")):
        words = ["".join(w) for w in itertools.product("ab", repeat=length) if w.count("a") == length // 2]
        candidates = []
        for u, v in itertools.combinations(words, 2):
            if (u[0] == v[0] or u[-1] == v[-1] or pair_orbit((u, v)) in excluded
                    or action_at(u) == action_at(v)):
                continue
            if bit_requirement == "different_at_10" and action_at(u, bits=True) == action_at(v, bits=True):
                continue
            if bit_requirement == "same_action" and any(
                action_at(u, p, bits=True) != action_at(v, p, bits=True)
                for p in itertools.product((0, 1), repeat=2)
            ):
                continue
            candidates.append((u, v))
        if not candidates:
            raise ValueError("empty structural sampling stratum")
        sizes.append(len(candidates))
        pair = rng.choice(candidates)
        excluded.add(pair_orbit(pair))
        selected.append(pair)
    return selected, sizes


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"template anchor is not unique: {old}")
    return text.replace(old, new, 1)


def _audited(text: str) -> str:
    """Audit every local theorem, retaining explicit namespace qualification."""
    text = re.sub(r"^#print axioms .*\n", "", text, flags=re.M)
    namespace = re.search(r"^namespace (\S+)", text, re.M).group(1)
    names = re.findall(r"^theorem (\w+)", text, re.M)
    return text.rstrip() + "\n\n" + "".join(f"#print axioms {namespace}.{name}\n" for name in names)


def source_body(source: str, family: str) -> str:
    start = "def measure " if family == "invariant" else "abbrev Point "
    if source.count(start) != 1 or source.count("theorem source_solution") != 1:
        raise ValueError("source bridge boundaries must be unique")
    return start + source.split(start, 1)[1].split("theorem source_solution", 1)[0]


def adapt_source(source: str, family: str, namespace: str, offsets: list[int], label: str) -> str:
    """Transplant source definitions/proofs, never substitute the target oracle.

    Invariant map: (source.u,source.v,source.w)=(Z,X,Y), decoded by
    the target's affine offsets. Representation map: l→a, r→b.
    Constructors and induction schemes retain their corresponding names.
    """
    body = source_body(source, family)
    if family == "invariant":
        x, y, z = offsets
        mapping = {"s.u": f"(s.z - ({z}))", "s.v": f"(s.x - ({x}))", "s.w": f"(s.y - ({y}))"}
        body = re.sub(r"s\.[uvw]", lambda m: mapping[m.group()], body)
    else:
        body = re.sub(r"\b[lr]\b", lambda m: {"l": "a", "r": "b"}[m.group()], body)
    opens = "open Mark\n" if family == "representation" else ""
    return f"import World.Base\n\nnamespace {namespace}.{label}\n{opens}\n{body}end {namespace}.{label}\n"


def _invariant_files(files: dict[str, str], rng: random.Random) -> dict:
    n = rng.randrange(3, 10)
    x, y, z = [rng.choice([i for i in range(-5, 6) if i]) for _ in range(3)]
    base = files["World/Base.lean"]
    moves = [
        f"⟨s.x + 2 * s.y + s.z - 2 * ({y}) - ({z}), s.y + s.z - ({z}), s.z⟩",
        f"⟨s.x - 2 * s.y + s.z + 2 * ({y}) - ({z}), s.y - s.z + ({z}), s.z⟩",
        f"⟨s.x, s.x + s.y - ({x}), s.x + 2 * s.y + s.z - ({x}) - 2 * ({y})⟩",
        f"⟨s.x, s.y - s.x + ({x}), s.x - 2 * s.y + s.z - ({x}) + 2 * ({y})⟩",
    ]
    for i, move in enumerate(moves, 1):
        base, count = re.subn(rf"^def move{i} .*", f"def move{i} (s : State) : State := {move}", base, flags=re.M)
        if count != 1:
            raise ValueError("move template changed")
    files["World/Base.lean"] = _replace_once(base, "⟨2, 1, 1⟩", f"⟨{n*n+1+x}, {n+y}, {1+z}⟩")
    for target, old, new in (
        ("visible", "⟨0, b, c⟩", f"⟨{x}, b + ({y}), c + ({z})⟩"),
        ("holdout1", "⟨a, b, -a⟩", f"⟨a + ({x}), b + ({y}), -a + ({z})⟩"),
        ("holdout2", "⟨a, a, a⟩", f"⟨a + ({x}), a + ({y}), a + ({z})⟩"),
    ):
        relative = TARGETS[target][0]
        files[relative] = _replace_once(files[relative], old, new)
    files["Hidden/Oracle.lean"] = _replace_once(files["Hidden/Oracle.lean"],
        "s.x * s.z - s.y * s.y", f"(s.x - ({x})) * (s.z - ({z})) - (s.y - ({y})) * (s.y - ({y}))")
    return {"initial_parameter": n, "offsets": [x, y, z], "unit_shears": True,
            "variation": "affine_coordinate_change_and_initial_state_only"}


def _representation_files(files: dict[str, str], rng: random.Random, prototype: Path) -> dict:
    pairs, sizes = _sample_pairs(rng)
    files["Hidden/Diagnostics.lean"] = (prototype / "Hidden/Diagnostics.lean").read_text()
    for relative in (*[row[0] for row in TARGETS.values()], "Hidden/OracleChecks.lean", "Hidden/Diagnostics.lean"):
        text = files[relative]
        # Single-pass replacement avoids cascading if a generated word equals an old one.
        mapping = {word(a): word(b) for old, new in zip(PROTOTYPE_PAIRS, pairs) for a, b in zip(old, new)}
        text = re.sub("|".join(re.escape(w) for w in sorted(mapping, key=len, reverse=True)),
                      lambda m: mapping[m.group()], text)
        files[relative] = text
    return {"pairs": [list(p) for p in pairs], "candidate_counts": sizes,
            "source_pairs_excluded": [list(p) for p in SOURCE_PAIRS],
            "literal_orbit_exclusion": "common_context_then_pair_order_symbol_swap_word_reversal",
            "variation": "new_target_word_pairs_same_known_relation"}


def _source_checks(files: dict[str, str], family: str, namespace: str, parameters: dict) -> None:
    checks = files["Hidden/OracleChecks.lean"].replace("import Hidden.Oracle", "import Hidden.AdaptedRelevant")
    checks = re.sub(r"^#print axioms .*\n", "", checks, flags=re.M)
    checks = checks.replace("oracle_bridge", "Adapted.bridge").replace("theorem oracle_", "theorem adapted_")
    if family == "invariant":
        checks = checks.replace("[balance, start]", "[Adapted.measure, start]")
        sham = "def measure " + files["Hidden/AdaptedSham.lean"].split("def measure ", 1)[1].split("theorem step_measure", 1)[0]
        extra = sham.replace("def measure", "def shamMeasure") + (
            "\ntheorem sham_incompatibility : shamMeasure start ≠ shamMeasure (move1 start) := by decide\n")
    else:
        checks = re.sub(r"\brun\b", "Adapted.run", checks).replace("(1, 0)", "(0, 1)")
        sham = files["Hidden/AdaptedSham.lean"].split("abbrev Point", 1)[1].split("theorem related_action", 1)[0]
        extra = ""  # Keep this independent interpretation in its own audited module.
        negative = (f"import World.Base\nnamespace {namespace}.ShamInterpretation\nopen Mark\n"
            + "abbrev Point" + sham
            + "theorem sham_incompatibility : run [a, b, a] (0, 1) ≠ run [b, a, b] (0, 1) := by decide\n\n")
        for target, (u, v) in zip(TARGETS, parameters["pairs"]):
            negative += (f"theorem sham_cannot_distinguish_{target} (q : Point) : run {word(u)} q = run {word(v)} q := by\n"
                         + "  cases q\n  simp only [run, action] <;> (apply Prod.ext <;> dsimp <;> omega)\n\n")
        files["Hidden/ShamChecks.lean"] = _audited(negative + f"end {namespace}.ShamInterpretation\n")
    checks = checks.replace(f"end {namespace}", extra + f"\nend {namespace}")
    files["Hidden/SourceChecks.lean"] = _audited(checks)


def generate_conceptual(spec: ConceptualSpec) -> ConceptualWorld:
    prototype = REPO / "worlds/prototypes" / FAMILIES[spec.family]
    original = load_prototype(prototype)
    base_files = ["World/Base.lean", *[row[0] for row in TARGETS.values()],
                  "Hidden/Oracle.lean", "Hidden/OracleChecks.lean"]
    files = {relative: (prototype / relative).read_text() for relative in base_files}
    rng = random.Random(int(spec.seed, 16))
    parameters = (_invariant_files(files, rng) if spec.family == "invariant"
                  else _representation_files(files, rng, prototype))
    namespace = f"P3.{spec.world_id}"
    files = {relative: text.replace(original["roles"]["namespace"], namespace) for relative, text in files.items()}
    files["Hidden/OracleChecks.lean"] = _audited(files["Hidden/OracleChecks.lean"])
    files["lean-toolchain"] = "leanprover/lean4:v4.33.1\n"
    files["lakefile.toml"] = (f'name = "{spec.world_id.lower()}"\nversion = "0.1.0"\n'
        + "".join(f'\n[[lean_lib]]\nname = "{name}"\n' for name in ("World", "Hidden", "Sources")))
    source_hashes = {}
    for kind in ("Relevant", "Sham"):
        asset = f"{spec.family.title()}{kind}.lean"
        source = (ASSETS / asset).read_text()
        source_hashes[asset] = sha(source)
        files[f"Sources/{kind}.lean"] = _audited(source)
        # The model payload is byte-for-byte the proof source, minus audit commands.
        files[f"Sources/{kind}.md"] = SOURCE_HEADER + "```lean\n" + source + "```\n"
        files[f"Hidden/Adapted{kind}.lean"] = adapt_source(source, spec.family, namespace,
            parameters.get("offsets", []), "Adapted" if kind == "Relevant" else "AdaptedSham")
    _source_checks(files, spec.family, namespace, parameters)
    if spec.family == "invariant":
        files["Hidden/Diagnostics.lean"] = _audited(f"""import World.Base
namespace {namespace}
theorem nonempty_dynamics : Reaches start (move1 start) :=
  Reaches.tail (Reaches.refl start) (Step.first start)
theorem nontrivial_dynamics : start ≠ move1 start := by decide
theorem inverse_round_trip : move2 (move1 start) = start ∧ move4 (move3 start) = start := by decide
end {namespace}
""")
    else:
        files["Hidden/Diagnostics.lean"] = _audited(files["Hidden/Diagnostics.lean"])
    lengths = {kind: len(files[f"Sources/{kind}.md"].split()) for kind in ("Relevant", "Sham")}
    gap = abs(lengths["Relevant"] - lengths["Sham"]) / max(lengths.values())
    declarations = {kind: len(re.findall(r"^theorem ", files[f"Sources/{kind}.lean"], re.M))
                    for kind in lengths}
    if gap > 0.05 or len(set(declarations.values())) != 1:
        raise ValueError("source pair does not meet the declared word-count/theorem-count match")
    public = ["lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeVisible.lean"]
    metadata = {
        "schema_version": 1, "generator_version": VERSION, "world_id": spec.world_id,
        "family": spec.family, "seed": spec.seed, "phase": "development", "status": "DEVELOPMENT_ONLY",
        "eligible_for_main": False, "eligible_for_calibration": False, "structural_novelty_claimed": False,
        "sources_ready": True, "behavioral_gate_tested": False, "parameters": parameters,
        "sampling": "seeded_subject_to_declared_structural_constraints_not_model_outcomes",
        "toolchain": "leanprover/lean4:v4.33.1", "allowed_axioms": list(STANDARD_LEAN_AXIOMS),
        "source_matching": {"words": lengths, "relative_word_gap": gap, "theorems": declarations,
                            "tokenizer_matched": False, "difficulty_matched": False},
        "provenance": {"prototype_manifest_sha256": sha((prototype / "manifest.sha256").read_text()),
                       "source_assets_sha256": source_hashes, "generator_sha256": sha(Path(__file__).read_text())},
        "public_files": public, "hidden_files": sorted(set(files) - set(public)),
        "roles": {"namespace": namespace, "oracle_bridge": "oracle_bridge", "visible_statement": "VisibleStatement",
                  "holdout_statements": ["Holdout1Statement", "Holdout2Statement"]},
        "artifact_hashes": {relative: sha(text) for relative, text in sorted(files.items())},
        "lean_checks": {
            "must_compile": sorted(rel for rel in files if rel.endswith(".lean") and rel != "Hidden/AdaptedSham.lean"),
            "must_fail": ["Hidden/AdaptedSham.lean"],
            "axiom_audits": {rel: text.count("#print axioms ") for rel, text in files.items() if "#print axioms " in text},
        },
    }
    files["metadata.json"] = json.dumps(metadata, sort_keys=True, indent=2) + "\n"
    files["manifest.sha256"] = "".join(f"{sha(text)}  {rel}\n" for rel, text in sorted(files.items()))
    return ConceptualWorld(spec, files, metadata)


def write_conceptual(world: ConceptualWorld, destination: Path) -> Path:
    """Create a new package only; never reseal or overwrite a reviewed instance."""
    if destination.exists() or destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
        raise FileExistsError(f"new, non-symlink destination required: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    for relative, text in world.files.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    validate_world(destination).require_ok()
    return destination


def load_conceptual(root: Path) -> dict:
    if root.is_symlink():
        raise ValueError("world root must not be a symlink")
    validate_world(root).require_ok()
    metadata = json.loads((root / "metadata.json").read_text())
    spec = ConceptualSpec(metadata["family"], metadata["seed"])
    if (metadata.get("world_id") != spec.world_id or metadata.get("phase") != "development"
            or metadata.get("status") != "DEVELOPMENT_ONLY" or metadata.get("eligible_for_main") is not False
            or metadata.get("eligible_for_calibration") is not False or metadata.get("structural_novelty_claimed") is not False
            or metadata.get("allowed_axioms") != list(STANDARD_LEAN_AXIOMS)):
        raise ValueError("an explicitly development-only conceptual package is required")
    expected = generate_conceptual(spec)
    if metadata != expected.metadata or any(
        (root / relative).read_text() != text for relative, text in expected.files.items()
    ):
        raise ValueError("package differs from the recorded generator/assets; use its original code revision")
    return metadata
