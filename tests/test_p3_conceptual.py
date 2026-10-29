"""Known-family generation, genuine source transplantation, isolation and controls."""

import json
from pathlib import Path
import shutil

import pytest

from creative_machine.formal_routes.conceptual_generator import (
    ASSETS, FAMILIES, PROTOTYPE_PAIRS, SOURCE_HEADER, SOURCE_PAIRS, ConceptualSpec,
    action_at, adapt_source, generate_conceptual, load_conceptual, pair_orbit, write_conceptual,
    sha,
)
from creative_machine.formal_routes.conceptual_review import (
    LAKE, closure_source, expected_proof_rejection, materialize_conceptual_cell, review_conceptual,
)
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY, sandbox_process
from creative_machine.formal_routes.prototypes import TARGETS
from creative_machine.formal_routes.workspace import audit_workspace, materialize_proposer

SEEDS = {"invariant": "43be3d3ca20476f1", "representation": "cd4dc332561f4980"}
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()


@pytest.fixture(params=FAMILIES)
def world(request, tmp_path):
    family = request.param
    generated = generate_conceptual(ConceptualSpec(family, SEEDS[family]))
    root = write_conceptual(generated, tmp_path.resolve() / generated.spec.world_id)
    return root, generated


@pytest.mark.parametrize("family,seed", [("unknown", "0" * 16), ("invariant", "short"),
    ("representation", "A" * 16), ("invariant", "../" + "0" * 13)])
def test_bad_spec_is_rejected(family, seed):
    with pytest.raises(ValueError):
        ConceptualSpec(family, seed)


@pytest.mark.parametrize("family", FAMILIES)
def test_deterministic_known_family_development_only(family):
    for seed in ("0" * 16, "f" * 16, SEEDS[family]):
        spec = ConceptualSpec(family, seed)
        one, two = generate_conceptual(spec), generate_conceptual(spec)
        assert one.files == two.files
        assert one.metadata["phase"] == "development"
        assert one.metadata["eligible_for_main"] is False
        assert one.metadata["eligible_for_calibration"] is False
        assert one.metadata["structural_novelty_claimed"] is False
    assert one.metadata["parameters"] != generate_conceptual(ConceptualSpec(family, "0" * 16)).metadata["parameters"]


def test_representation_constraints_are_not_model_outcomes():
    for index in range(16):
        generated = generate_conceptual(ConceptualSpec("representation", f"{index:016x}"))
        pairs = generated.metadata["parameters"]["pairs"]
        excluded = {pair_orbit(p) for p in (*SOURCE_PAIRS, *PROTOTYPE_PAIRS)}
        for u, v in pairs:
            assert len(u) == len(v) and u.count("a") == v.count("a")
            assert u[0] != v[0] and u[-1] != v[-1]
            assert pair_orbit((u, v)) not in excluded
            excluded.add(pair_orbit((u, v)))
            assert action_at(u) != action_at(v)
        assert action_at(pairs[0][0], bits=True) != action_at(pairs[0][1], bits=True)
        for point in ((0, 0), (0, 1), (1, 0), (1, 1)):
            assert action_at(pairs[1][0], point, bits=True) == action_at(pairs[1][1], point, bits=True)


def test_pair_orbit_is_only_an_explicit_literal_filter():
    pair = ("aaabbb", "babbaa")
    assert pair_orbit(pair) == pair_orbit(tuple(reversed(pair)))
    assert pair_orbit(pair) == pair_orbit(tuple(w[::-1] for w in pair))
    assert pair_orbit(pair) == pair_orbit(tuple("abba" + w + "ba" for w in pair))
    assert pair_orbit(pair) == pair_orbit(tuple(w.translate(str.maketrans("ab", "ba")) for w in pair))


def test_sources_are_matched_and_payload_is_the_checked_proof(world):
    root, generated = world
    matching = generated.metadata["source_matching"]
    assert matching["relative_word_gap"] <= 0.05
    assert matching["theorems"]["Relevant"] == matching["theorems"]["Sham"]
    assert matching["tokenizer_matched"] is False and matching["difficulty_matched"] is False
    family = generated.spec.family
    for kind in ("Relevant", "Sham"):
        asset = (ASSETS / f"{family.title()}{kind}.lean").read_text()
        payload = (root / f"Sources/{kind}.md").read_text()
        assert payload == SOURCE_HEADER + "```lean\n" + asset + "```\n"
        assert asset in (root / f"Sources/{kind}.lean").read_text()
        assert not any(marker in payload for marker in ("Holdout", generated.spec.world_id, "Relevant", "Sham"))
        adapted = adapt_source(asset, family, generated.metadata["roles"]["namespace"],
            generated.metadata["parameters"].get("offsets", []), "Adapted" if kind == "Relevant" else "AdaptedSham")
        assert adapted == (root / f"Hidden/Adapted{kind}.lean").read_text()
        assert "source_solution" not in adapted
        assert adapted != (root / "Hidden/Oracle.lean").read_text()


def test_adapter_really_depends_on_source_body(world):
    _, generated = world
    family = generated.spec.family
    source = (ASSETS / f"{family.title()}Relevant.lean").read_text()
    original = adapt_source(source, family, "P3.Check", [1, 2, 3], "Adapted")
    changed = adapt_source(source.replace("theorem bridge", "theorem source_changed_bridge"),
                           family, "P3.Check", [1, 2, 3], "Adapted")
    assert changed != original and "source_changed_bridge" in changed


def test_refuse_overwrite_and_detect_tampering(world, tmp_path):
    root, generated = world
    assert load_conceptual(root)["world_id"] == generated.spec.world_id
    with pytest.raises(FileExistsError):
        write_conceptual(generated, root)
    link = tmp_path / "symlink-world"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        load_conceptual(link)
    with pytest.raises(FileExistsError):
        write_conceptual(generated, link)
    (root / "Sources/Relevant.md").write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_conceptual(root)


def test_resealing_cannot_skip_source_audits(world):
    root, _ = world
    metadata = json.loads((root / "metadata.json").read_text())
    metadata["lean_checks"]["axiom_audits"] = {}
    (root / "metadata.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    manifest = "".join(f"{sha((root / relative).read_text())}  {relative}\n"
                       for relative in sorted([*metadata["artifact_hashes"], "metadata.json"]))
    (root / "manifest.sha256").write_text(manifest)
    with pytest.raises(ValueError, match="generator/assets"):
        load_conceptual(root)


@pytest.mark.parametrize("arm", ("D0", "D", "C2"))
def test_proposer_receives_only_its_source_and_visible_target(world, tmp_path, arm):
    root, _ = world
    record = materialize_proposer(root, arm, tmp_path / f"proposer-{arm}")
    assert not audit_workspace(record)
    all_text = "\n".join(p.read_text() for p in record.path.rglob("*") if p.is_file())
    assert all(s not in all_text for s in ("Holdout1Statement", "Holdout2Statement", "sham_incompatibility"))
    assert (record.path / "SOURCE.md").exists() == (arm != "D0")
    if arm != "D0":
        assert (record.path / "SOURCE.md").read_text() == (root / f"Sources/{'Relevant' if arm == 'D' else 'Sham'}.md").read_text()


def test_isolated_closures_never_import_source_examples_or_other_targets(world, tmp_path):
    root, _ = world
    for target in TARGETS:
        for bridge in (None, "oracle", "adapted"):
            record = materialize_conceptual_cell(root, target, bridge, tmp_path / f"{target}-{bridge}")
            assert not audit_workspace(record)
            files = {str(p.relative_to(record.path)) for p in record.path.rglob("*") if p.is_file()}
            assert files == {"lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeEvaluation.lean"} | ({"Bridge.lean"} if bridge else set())
            all_text = "\n".join(p.read_text() for p in record.path.rglob("*.lean"))
            assert "source_solution" not in all_text
            for other, (_, statement, _) in TARGETS.items():
                assert (statement in all_text) == (other == target)
            if bridge:
                source = closure_source(root, target, bridge)
                assert "theorem evaluation_solution : " + TARGETS[target][1] in source
                assert "import Hidden" not in source and "import Sources" not in source


@pytest.mark.parametrize("message", ["unknown identifier X", "unexpected token", "timeout",
    "maximum number of heartbeats", "No goals to be solved", "unknown module prefix"])
def test_bad_failures_are_not_negative_control_evidence(message):
    assert not expected_proof_rejection(1, "unsolved goals\n" + message, "")


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_development_kernel_sources_closures_probes_and_mutations(world):
    root, _ = world
    result = review_conceptual(root)
    assert result["model_calls"] == 0 and result["behavioral_gate_tested"] is False
    assert result["structural_checks_passed"], json.dumps(result)
    assert len(result["closure_checks"]) == 6
    assert len(result["automatic_probes"]) == 9
    assert result["sham_adapter"]["expected_rejection"]


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_second_seed_has_valid_sources_and_closures(tmp_path, family):
    spec = ConceptualSpec(family, "fffffffffffffffe")
    generated = generate_conceptual(spec)
    root = write_conceptual(generated, tmp_path.resolve() / spec.world_id)
    modules = [rel.removesuffix(".lean").replace("/", ".") for rel in generated.metadata["lean_checks"]["must_compile"]]
    built = sandbox_process([LAKE, "build", *modules], cwd=root, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
