"""New local plumbing only: fixtures are not experimental model responses."""

from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from creative_machine.formal_routes import production_contract_v1 as contract
from creative_machine.formal_routes.calibration_review_v3 import closure_v3
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
from creative_machine.formal_routes.workspace import audit_workspace

REPO = Path(__file__).resolve().parents[1]
WORLDS = (
    REPO / "worlds/calibration/CAL3_I_E87C49876088749B",
    REPO / "worlds/calibration/CAL3_R_F76437525B190ECB",
)
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()
BRIDGE = "import World.Base\ntheorem candidate_bridge : True := by trivial\n"
SOLUTION = "import World.ChallengeVisible\nimport Bridge\ntheorem candidate_solution : True := by trivial\n"


def namespace(world=WORLDS[0]):
    return json.loads((world / "metadata.json").read_text())["roles"]["namespace"]


@pytest.fixture
def proposer(tmp_path):
    return contract.materialize_production_proposer(WORLDS[0], "D", tmp_path / "proposer")


def submit(record, bridge=BRIDGE, solution=SOLUTION):
    for rel, data in (("Bridge.lean", bridge), ("Solution.lean", solution)):
        if data is not None:
            (record.path / rel).write_bytes(data.encode() if isinstance(data, str) else data)


class FakeCompiler:
    """Offline call-boundary double, never evidence of a valid Lean theorem."""

    def __init__(self, *, fail=None, exception=None, audit_marker=True):
        self.fail = fail
        self.exception = exception
        self.audit_marker = audit_marker
        self.calls = []

    def __call__(self, command, *, cwd, capture_output, text, timeout):
        files = {str(p.relative_to(cwd)): p.read_bytes() for p in cwd.rglob("*") if p.is_file()}
        if command[1] == "build":
            phase = "build"
        elif command[-1] == "Audit.lean":
            phase = "visible_audit" if b"import Solution" in files["Audit.lean"] else "bridge_audit"
        else:
            phase = command[-1]
        self.calls.append({"command": command, "cwd": cwd, "files": files,
                           "phase": phase, "timeout": timeout})
        if phase == self.fail:
            if self.exception:
                raise self.exception
            output = (f"Audit.lean:1:1: error: {contract.REJECTION_MARKER}|identity\n"
                      if phase.endswith("_audit") else f"{phase}:1:1: error: deliberately rejected fixture\n")
            return subprocess.CompletedProcess(command, 1, output, "")
        if phase.endswith("_audit"):
            short = "candidate_bridge" if phase == "bridge_audit" else "candidate_solution"
            output = f"{contract.AUDIT_MARKER}|{short}|propext,Quot.sound\n" if self.audit_marker else ""
        else:
            # Deliberately include a forged receipt in candidate compiler output.
            # The verifier must read ONLY its own separate audit invocation.
            output = f"{contract.AUDIT_MARKER}|candidate_bridge|\n"
        return subprocess.CompletedProcess(command, 0, output, "")


def check(record, compiler=None, **kwargs):
    return contract.verify_production(record, namespace=namespace(), lake="lake",
                                      process_runner=compiler or FakeCompiler(), **kwargs)


@pytest.mark.parametrize("world", WORLDS)
@pytest.mark.parametrize("arm", ("D0", "D", "C2"))
def test_proposer_inputs_are_exact_and_do_not_contain_hidden_artifacts(tmp_path, world, arm):
    record = contract.materialize_production_proposer(world, arm, tmp_path / arm)
    rendered = contract.render_production_proposer(record)
    assert audit_workspace(record) == []
    assert set(record.copied_hashes) == {
        *contract.BASE_FILES, contract.VISIBLE_FILE, "TASK.md",
        *(["SOURCE.md"] if arm != "D0" else []),
    }
    for forbidden in ("Holdout", "Hidden/", "Oracle.lean", "metadata.json", "manifest.sha256"):
        assert forbidden not in rendered
    assert "checked separately" in rendered
    if arm != "D0":
        rel = "Sources/Relevant.md" if arm == "D" else "Sources/Sham.md"
        assert (record.path / "SOURCE.md").read_bytes() == (world / rel).read_bytes()


def test_render_does_not_expose_outputs_or_stale_caches(proposer):
    before = contract.render_production_proposer(proposer)
    submit(proposer, bridge=BRIDGE + "-- private candidate marker\n")
    stale = proposer.path / ".lake/build/lib/lean"
    stale.mkdir(parents=True)
    (stale / "Hidden.olean").write_bytes(b"hidden cache marker")
    (proposer.path / "lake-manifest.json").write_text("stale manifest marker")
    assert contract.render_production_proposer(proposer) == before


@pytest.mark.parametrize("solution", (None, "invalid", SOLUTION))
def test_valid_bridge_is_not_erased_by_absent_or_failed_visible(proposer, solution):
    submit(proposer, solution=solution)
    compiler = FakeCompiler(fail="Solution.lean")
    report = check(proposer, compiler)
    assert report.bridge.valid and report.bridge_transferable
    assert not report.visible.valid
    assert report.visible.status == ("missing" if solution is None else "rejected")
    assert contract.bridge_artifact(proposer, report).source == BRIDGE.encode()


def test_both_results_can_be_valid_with_a_mock_verifier(proposer):
    submit(proposer)
    report = check(proposer)
    assert report.bridge.valid and report.visible.valid
    assert report.bridge.axioms == ("propext", "Quot.sound")
    assert set(report.feedback()) == {"bridge", "visible"}


@pytest.mark.parametrize("bridge", (None, "bad import", "import World.Base\naxiom candidate_bridge : False"))
def test_no_valid_bridge_means_no_transfer_and_no_visible_compilation(proposer, bridge):
    submit(proposer, bridge=bridge)
    compiler = FakeCompiler()
    report = check(proposer, compiler)
    assert not report.bridge_transferable
    assert report.visible.status == "blocked_by_bridge"
    assert compiler.calls == []
    with pytest.raises(ValueError, match="cannot be transferred"):
        contract.bridge_artifact(proposer, report)


@pytest.mark.parametrize("fail", ("Bridge.lean", "bridge_audit"))
def test_compile_or_audit_rejection_is_not_bridge_validity(proposer, fail):
    submit(proposer)
    compiler = FakeCompiler(fail=fail)
    report = check(proposer, compiler)
    assert report.bridge.status == "rejected"
    assert not report.bridge_transferable
    assert report.visible.status == "blocked_by_bridge"
    assert not any(c["phase"].startswith("visible") for c in compiler.calls)


def test_bridge_checker_never_gets_visible_or_sibling_sources_and_never_caches(proposer):
    submit(proposer)
    cache = proposer.path / ".lake/build/lib/lean"
    cache.mkdir(parents=True)
    (cache / "Bridge.olean").write_bytes(b"untrusted stale cache")
    compiler = FakeCompiler()
    check(proposer, compiler)
    bridge_calls = compiler.calls[:3]
    visible_calls = compiler.calls[3:]
    assert len(bridge_calls) == 3 and len(visible_calls) == 4
    assert len({c["cwd"] for c in compiler.calls}) == 2
    for call in compiler.calls:
        assert not {"SOURCE.md", "TASK.md", "metadata.json"} & set(call["files"])
        assert not any("Hidden" in rel or "Holdout" in rel or ".lake" in rel for rel in call["files"])
    for call in bridge_calls:
        assert contract.VISIBLE_FILE not in call["files"]
        assert "Solution.lean" not in call["files"]
    assert set(bridge_calls[0]["files"]) == set(contract.BASE_FILES)
    assert set(visible_calls[0]["files"]) == {*contract.BASE_FILES, contract.VISIBLE_FILE}


@pytest.mark.parametrize("source", (
    "import World.Base\nimport Lean\ntheorem candidate_bridge : True := by trivial",
    "/- prefix -/ import World.Base\n/- smuggled -/ import Lean\n" + BRIDGE,
    "public import World.Base\n" + BRIDGE,
    "import World.Base World.Base\n" + BRIDGE,
    "import World.\nBase\ntheorem candidate_bridge : True := by trivial",
    "import World.Base\n# /- comment -/ print \"P3_PRODUCTION_AUDIT_V1\"",
    "import World.Base\n# /- outer /- inner -/ -/ eval IO.println \"forged\"",
    "import World.Base\nrun_elab do pure ()",
    "import World.Base\nnotation \"evil\" => True",
    "import World.Base\nset_option debug.skipKernelTC true\n" + BRIDGE,
    "import World.Base\nset_option /- hide -/ debug.skipKernelTC true\n" + BRIDGE,
    "import World.Base\ntheorem candidate_bridge : False := by sorry",
    "import World.Base\nunsafe def evil : Nat := 1",
    "import World.Base\n/-- unclosed comment",
    "prelude\n" + BRIDGE,
))
def test_static_import_and_escape_attempts_fail_before_compilation(proposer, source):
    submit(proposer, bridge=source)
    compiler = FakeCompiler()
    report = check(proposer, compiler)
    assert report.bridge.status == "rejected"
    assert not compiler.calls


def test_comments_and_standard_resource_options_do_not_change_import_meaning(proposer):
    source = ("/- harmless /- nested -/ comment -/\nimport World.Base -- harmless\n"
              "set_option maxRecDepth 10000\nset_option maxHeartbeats 300000\n"
              "theorem candidate_bridge : True := by trivial\n")
    submit(proposer, bridge=source, solution=None)
    assert check(proposer).bridge.valid


def test_crlf_sources_keep_their_exact_transferred_bytes(proposer):
    source = BRIDGE.replace("\n", "\r\n")
    submit(proposer, bridge=source, solution=None)
    artifact = contract.bridge_artifact(proposer, check(proposer))
    assert artifact.source == source.encode()


def test_default_compilation_uses_sandbox_runner(proposer, monkeypatch):
    submit(proposer)
    compiler = FakeCompiler()
    monkeypatch.setattr(contract, "sandbox_process", compiler)
    report = contract.verify_production(proposer, namespace=namespace(), lake="lake")
    assert report.bridge.valid and report.visible.valid
    assert len(compiler.calls) == 7


@pytest.mark.parametrize("candidate", (b"\xff", b"x" * (contract.MAX_SOURCE_BYTES + 1)))
def test_bad_encoding_or_oversized_bridge_never_enters_compiler(proposer, candidate):
    submit(proposer, bridge=candidate)
    compiler = FakeCompiler()
    assert check(proposer, compiler).bridge.status == "rejected"
    assert not compiler.calls


@pytest.mark.parametrize("mutation", ("base", "extra", "file_symlink", "directory_symlink", "allowlist"))
def test_integrity_failures_stop_before_compilation(proposer, tmp_path, mutation):
    submit(proposer)
    if mutation == "base":
        (proposer.path / "World/Base.lean").write_text("different base")
    elif mutation == "extra":
        (proposer.path / "Hidden.lean").write_text("secret sentinel")
    elif mutation == "file_symlink":
        (proposer.path / "Bridge.lean").unlink()
        (proposer.path / "Bridge.lean").symlink_to(proposer.path / "World/Base.lean")
    elif mutation == "directory_symlink":
        (proposer.path / "World").rename(tmp_path / "world-linked")
        (proposer.path / "World").symlink_to(tmp_path / "world-linked")
    else:
        proposer = replace(proposer, copied_hashes={**proposer.copied_hashes, "../secret": "a" * 64})
    compiler = FakeCompiler()
    with pytest.raises(contract.WorkspaceIntegrityError):
        check(proposer, compiler)
    assert not compiler.calls


def test_missing_runtime_is_infrastructure_not_invalid_proof(proposer, monkeypatch):
    submit(proposer)
    monkeypatch.setattr(contract.shutil, "which", lambda _: None)
    with pytest.raises(contract.VerificationInfrastructureError, match="runtime"):
        contract.verify_production(proposer, namespace=namespace())


@pytest.mark.parametrize("fail,exception", (
    ("build", None), ("Bridge.lean", subprocess.TimeoutExpired("lean", 1)),
    ("bridge_audit", FileNotFoundError("sandbox")),
))
def test_technical_failures_raise_and_do_not_become_negative_results(proposer, fail, exception):
    submit(proposer)
    with pytest.raises(contract.VerificationInfrastructureError):
        check(proposer, FakeCompiler(fail=fail, exception=exception))


def test_visible_timeout_preserves_partial_bridge_evidence_and_stops(proposer):
    submit(proposer)
    with pytest.raises(contract.VerificationInfrastructureError) as caught:
        check(proposer, FakeCompiler(fail="Solution.lean", exception=subprocess.TimeoutExpired("lean", 1)))
    assert caught.value.partial_bridge.valid
    assert caught.value.phase == "visible_compile"


def test_forged_compile_receipt_cannot_replace_missing_trusted_audit(proposer):
    submit(proposer)
    with pytest.raises(contract.VerificationInfrastructureError, match="audit_receipt"):
        check(proposer, FakeCompiler(audit_marker=False))


def test_bug_in_trusted_audit_is_infrastructure_not_candidate_rejection(proposer):
    submit(proposer)
    fake = FakeCompiler()

    def broken_audit(command, **kwargs):
        proc = fake(command, **kwargs)
        if command[-1] == "Audit.lean":
            return subprocess.CompletedProcess(command, 1, "Audit.lean:16:3: error: Application type mismatch", "")
        return proc

    with pytest.raises(contract.VerificationInfrastructureError, match="trusted_audit") as caught:
        check(proposer, broken_audit)
    assert "Application type mismatch" in caught.value.stdout


@pytest.mark.parametrize("detail", (
    "out of memory", "Bridge.lean:4:5: error: maximum number of heartbeats exceeded",
    "Bridge.lean:4:5: error: maximum recursion depth has been reached",
))
def test_resource_failures_are_not_invalid_bridges(proposer, detail):
    submit(proposer)
    fake = FakeCompiler()

    def limited(command, **kwargs):
        proc = fake(command, **kwargs)
        return subprocess.CompletedProcess(command, 1, detail, "") if command[-1] == "Bridge.lean" else proc

    with pytest.raises(contract.VerificationInfrastructureError, match="non-proof or resource failure"):
        check(proposer, limited)


def test_timeout_budget_is_shared_across_compiler_commands(proposer, monkeypatch):
    submit(proposer)
    ticks = iter(range(100))
    monkeypatch.setattr(contract.time, "monotonic", lambda: next(ticks))
    compiler = FakeCompiler()
    check(proposer, compiler, timeout_s=20)
    assert [c["timeout"] for c in compiler.calls] == list(range(19, 12, -1))


def test_artifact_binds_exact_verified_bytes_not_later_revision(proposer):
    submit(proposer)
    report = check(proposer)
    (proposer.path / "Bridge.lean").write_text(BRIDGE + "-- later revision\n")
    with pytest.raises(contract.WorkspaceIntegrityError, match="changed after verification"):
        contract.bridge_artifact(proposer, report)


@pytest.mark.parametrize("holdout", (1, 2))
def test_transfer_copies_only_accepted_bytes_into_fresh_immutable_recipient(proposer, tmp_path, holdout):
    submit(proposer, solution=None)
    artifact = contract.bridge_artifact(proposer, check(proposer))
    compiler = FakeCompiler()
    recipient = contract.materialize_candidate_recipient(
        WORLDS[0], holdout, artifact, tmp_path / "recipient", lake="lake", process_runner=compiler)
    assert (recipient.path / "Bridge.lean").read_bytes() == artifact.source
    assert recipient.allowed_outputs == ("Solution.lean",)
    assert audit_workspace(recipient) == []
    assert not (recipient.path / ".lake").exists()
    assert not (recipient.path / "lake-manifest.json").exists()
    files = {str(p.relative_to(recipient.path)) for p in recipient.path.rglob("*") if p.is_file()}
    assert files == {*contract.BASE_FILES, "World/ChallengeEvaluation.lean", "Bridge.lean", "TASK.md"}
    text = "\n".join((recipient.path / rel).read_text() for rel in files)
    for forbidden in (f"Holdout{3 - holdout}Statement", "VisibleStatement", "SOURCE.md", "candidate_solution"):
        assert forbidden not in text
    assert not hasattr(artifact, "arm") and not hasattr(artifact, "visible")
    assert len(compiler.calls) == 3
    assert all("World/ChallengeEvaluation.lean" not in c["files"] for c in compiler.calls)
    (recipient.path / "Bridge.lean").write_text("changed by recipient")
    assert audit_workspace(recipient)


@pytest.mark.parametrize("mutation", ("hash", "world", "base", "declaration", "proof"))
def test_forged_artifacts_fail_before_publishing_recipient(proposer, tmp_path, mutation):
    submit(proposer)
    artifact = contract.bridge_artifact(proposer, check(proposer))
    compiler = FakeCompiler()
    if mutation == "hash":
        artifact = replace(artifact, source=b"different")
    elif mutation == "world":
        artifact = replace(artifact, world_id="different")
    elif mutation == "base":
        artifact = replace(artifact, base_hashes=())
    elif mutation == "declaration":
        artifact = replace(artifact, declaration="nonexistent")
    else:
        compiler = FakeCompiler(fail="bridge_audit")
    destination = tmp_path / "recipient"
    with pytest.raises(contract.WorkspaceIntegrityError):
        contract.materialize_candidate_recipient(WORLDS[0], 1, artifact, destination,
                                                  lake="lake", process_runner=compiler)
    assert not destination.exists()


def test_feedback_contains_no_host_paths_or_hidden_results(proposer):
    submit(proposer, bridge="import World.Base\naxiom fake : False")
    report = check(proposer)
    feedback = json.dumps(report.feedback())
    for forbidden in (str(proposer.path), "Hidden", "Holdout", "world_id", "base_hashes", "namespace"):
        assert forbidden not in feedback


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("world", WORLDS)
def test_real_lean_checks_existing_oracle_fixture_and_visible_then_transfer(tmp_path, world):
    """Plumbing fixture only: known oracle bytes must never count as production."""
    record = contract.materialize_production_proposer(world, "D0", tmp_path / "proposer")
    bridge = (world / "Hidden/Oracle.lean").read_text().replace("oracle_bridge", "candidate_bridge")
    solution = (closure_v3(world, "visible", "oracle")
                .replace("World.ChallengeEvaluation", "World.ChallengeVisible")
                .replace("evaluation_solution", "candidate_solution")
                .replace("oracle_bridge", "candidate_bridge"))
    submit(record, bridge, solution)
    report = contract.verify_production(record, namespace=namespace(world), timeout_s=60)
    assert report.bridge.valid, report.bridge
    assert report.visible.valid, report.visible
    assert set(report.bridge.axioms) <= set(contract.STANDARD_LEAN_AXIOMS)
    artifact = contract.bridge_artifact(record, report)
    recipient = contract.materialize_candidate_recipient(world, 1, artifact, tmp_path / "recipient", timeout_s=60)
    assert audit_workspace(recipient) == []
    assert (recipient.path / "Bridge.lean").read_bytes() == artifact.source


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("body,valid", (
    ("theorem candidate_bridge : True := by trivial", True),
    ("theorem candidate_bridge (p : Prop) : p ∨ ¬ p := Classical.em p", True),
    ("theorem candidate_bridge : True := Lean.trustCompiler", False),
    ("def candidate_bridge : True := True.intro", False),
    ("def candidate_bridge : Nat := 0", False),
    ("private theorem candidate_bridge : True := by trivial", False),
    ("theorem unrelated : True := by trivial", False),
    ("theorem candidate_bridge : True := by trivial\n"
     f"namespace {namespace()}\ntheorem candidate_bridge : True := by trivial\nend {namespace()}", False),
))
def test_real_lean_checks_theorem_identity_kind_and_standard_axioms(proposer, body, valid):
    submit(proposer, bridge="import World.Base\n" + body + "\n", solution=None)
    report = contract.verify_production(proposer, namespace=namespace(), timeout_s=60)
    assert report.bridge.valid is valid, report.bridge
    assert report.visible.status == "missing"
    assert report.bridge_transferable is valid


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_wrong_visible_type_does_not_revoke_valid_bridge(proposer):
    submit(proposer)
    report = contract.verify_production(proposer, namespace=namespace(), timeout_s=60)
    assert report.bridge.valid, report.bridge
    assert not report.visible.valid
    assert "frozen visible type" in " ".join(report.visible.errors)
    assert contract.bridge_artifact(proposer, report).sha256 == report.bridge.source_sha256


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_rejects_solution_declaration_inherited_from_bridge(proposer):
    bridge = BRIDGE + "theorem candidate_solution : True := by trivial\n"
    submit(proposer, bridge, "import World.ChallengeVisible\nimport Bridge\n")
    report = contract.verify_production(proposer, namespace=namespace(), timeout_s=60)
    assert report.bridge.valid
    assert report.visible.status == "rejected"
    assert "required output module" in " ".join(report.visible.errors)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_cannot_replace_the_frozen_visible_declaration_in_bridge(proposer):
    ns = namespace()
    bridge = BRIDGE + f"namespace {ns}\ndef VisibleStatement : Prop := True\nend {ns}\n"
    submit(proposer, bridge)
    try:
        report = contract.verify_production(proposer, namespace=ns, timeout_s=60)
    except contract.VerificationInfrastructureError as exc:
        # Lean may reject conflicting imports before issuing a source diagnostic.
        assert exc.phase == "candidate_compile"
        assert "already contains" in (exc.stdout + exc.stderr)
    else:
        assert not report.visible.valid
