"""Recipient plumbing tests; known proofs are fixtures, not experimental answers."""
from dataclasses import replace
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from creative_machine.formal_routes import recipient_contract_v1 as contract
from creative_machine.formal_routes import production_contract_v1 as production
from creative_machine.formal_routes.calibration_review_v3 import closure_v3
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
from creative_machine.formal_routes.transfer_design_v1 import matrix, load_blueprint, sha, encoded

REPO = Path(__file__).resolve().parents[1]
CELLS = [cell for cell in matrix() if cell["role"] == "recipient"]
B = next(c for c in CELLS if c["arm"] == "B")
O = next(c for c in CELLS if c["arm"] == "O")
C = next(c for c in CELLS if c["arm"] == "D0")
BRIDGE = b"import World.Base\ntheorem candidate_bridge : True := by trivial\n"
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()


def artifact(cell, source=BRIDGE, declaration="candidate_bridge"):
    world = REPO / cell["world"]
    return production.BridgeArtifact(source, sha(source), cell["world_id"], "P3." + cell["world_id"], declaration,
                                    tuple((rel, sha((world / rel).read_bytes())) for rel in production.BASE_FILES))


class FakeCompiler:
    """Fake process boundary, handles frozen candidate staging and new checker."""
    def __init__(self, *, fail=None, error=None, output=None, audit_code="target_type", audit_receipt=True, on_call=None):
        self.fail, self.error, self.output = fail, error, output
        self.audit_code, self.audit_receipt, self.on_call = audit_code, audit_receipt, on_call
        self.calls = []

    def __call__(self, command, *, cwd, capture_output, text, timeout):
        files = {p.relative_to(cwd).as_posix(): p.read_bytes() for p in cwd.rglob("*") if p.is_file()}
        audit_source = files.get("Audit.lean", b"").decode()
        if command[1] == "build":
            phase = "target_build" if "World.ChallengeEvaluation" in command else "base_build"
        elif command[-1] == "Audit.lean":
            phase = "solution_audit" if "import Solution" in audit_source else "bridge_audit"
        elif command[-1] == "Bridge.lean":
            phase = "bridge_rebuild" if contract.TARGET_FILE in files else "bridge_compile"
        else:
            phase = "solution_compile"
        self.calls.append({"phase": phase, "command": command, "files": files, "cwd": cwd, "timeout": timeout})
        if self.on_call:
            self.on_call(self.calls[-1])
        old = production.AUDIT_MARKER in audit_source
        marker = production.AUDIT_MARKER if old else contract.AUDIT_MARKER
        rejection = production.REJECTION_MARKER if old else contract.REJECTION_MARKER
        if phase == self.fail:
            if self.error:
                raise self.error
            default = (f"Audit.lean:1:1: error: {rejection}|{self.audit_code}\n" if phase.endswith("audit")
                       else f"{'Bridge' if 'bridge' in phase else 'Solution'}.lean:1:1: error: synthetic proof rejection\n")
            return subprocess.CompletedProcess(command, 1, self.output if self.output is not None else default, "")
        if phase.endswith("audit"):
            short = re.search(r"let names : List Lean.Name := \[`([^,]+),", audit_source)[1]
            output = f"{marker}|{short}|propext,Quot.sound\n" if self.audit_receipt else ""
        else:
            output = f"{contract.AUDIT_MARKER}|evaluation_solution|\n"  # Forged compile output must not be used.
        return subprocess.CompletedProcess(command, 0, output, "")


def prepare(tmp_path, cell=B, candidate=None):
    candidate = artifact(cell) if candidate is None and cell["bridge_kind"] == "candidate" else candidate
    record = contract.materialize_recipient(REPO, cell["cell_id"], tmp_path / "workspace",
        candidate=candidate, lake="fixture-lake", process_runner=FakeCompiler())
    return record, candidate


def solution(cell=B):
    return ("import World.ChallengeEvaluation\n" + ("import Bridge\n" if cell["bridge_kind"] != "none" else "")
            + "theorem evaluation_solution : True := by trivial\n").encode()


def check(record, cell=B, candidate=None, compiler=None, **kwargs):
    return contract.verify_recipient(record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate,
        lake="fixture-lake", process_runner=compiler or FakeCompiler(), **kwargs)


@pytest.mark.parametrize("cell", CELLS)
def test_all_twenty_recipient_slots_have_exact_allowlisted_inputs(tmp_path, cell):
    record, candidate = prepare(tmp_path, cell)
    rendered = contract.render_recipient(record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate)
    world = REPO / cell["world"]
    assert (record.path / contract.TARGET_FILE).read_bytes() == (world / f"World/Holdout{cell['holdout']}.lean").read_bytes()
    assert set(record.copied_hashes) == {*production.BASE_FILES, contract.TARGET_FILE, "TASK.md",
                                        *(["Bridge.lean"] if cell["bridge_kind"] != "none" else [])}
    for forbidden in ("SOURCE.md", "ChallengeVisible", "VisibleStatement", "Hidden/", "metadata.json", "cell_id", "arm:", "transcript"):
        assert forbidden not in rendered
    assert f"Holdout{3 - cell['holdout']}Statement" not in rendered
    if cell["bridge_kind"] == "candidate":
        assert (record.path / "Bridge.lean").read_bytes() == BRIDGE
    if cell["bridge_kind"] == "oracle":
        assert (record.path / "Bridge.lean").read_bytes() == (world / "Hidden/Oracle.lean").read_bytes()
        assert "oracle_bridge" in rendered  # Existing identifier is honestly preserved, not called full blinding.
    before = rendered
    (record.path / "Solution.lean").write_text("-- private output not in next initial input")
    assert contract.render_recipient(record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate) == before


def test_same_bridge_yields_identical_payloads_for_D0_D_C2_origin(tmp_path):
    cells = [c for c in CELLS if c["world_id"] == C["world_id"] and c["holdout"] == C["holdout"] and c["bridge_kind"] == "candidate"]
    rendered = []
    for cell in cells:
        record, candidate = prepare(tmp_path / cell["arm"], cell)
        rendered.append(contract.render_recipient(record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate))
    assert len(rendered) == 3 and len(set(rendered)) == 1


@pytest.mark.parametrize("cell", (B, O, C))
def test_fresh_compiler_stages_never_get_proposer_source_history_other_target_or_live_cache(tmp_path, cell):
    record, candidate = prepare(tmp_path, cell)
    (record.path / "Solution.lean").write_bytes(solution(cell))
    compiler = FakeCompiler()
    result = check(record, cell, candidate, compiler)
    assert result.target_solved and result.solution.valid
    assert set(result.feedback()) == {"status", "valid", "errors"}
    assert result.bridge_sha256 == (sha((record.path / "Bridge.lean").read_bytes()) if cell["bridge_kind"] != "none" else None)
    assert all(call["cwd"] != record.path for call in compiler.calls)
    for call in compiler.calls:
        assert not {"TASK.md", "SOURCE.md", "metadata.json", "World/ChallengeVisible.lean"} & set(call["files"])
        assert not any("Hidden" in rel or "Holdout" in rel for rel in call["files"])
        if call["phase"] in ("base_build", "bridge_compile", "bridge_audit"):
            assert contract.TARGET_FILE not in call["files"] and "Solution.lean" not in call["files"]
        if call["phase"] == "target_build":
            assert "Bridge.lean" not in call["files"] and "Solution.lean" not in call["files"]
    assert len({call["cwd"] for call in compiler.calls}) == (1 if cell["bridge_kind"] == "none" else 2)
    assert not (record.path / ".lake").exists()


@pytest.mark.parametrize("bad", ("identity", "hashes", "base", "target", "task", "unknown_file", "cache", "empty_dir", "symlink", "output_link"))
def test_mutated_or_undeclared_workspace_is_technical_not_mathematical_failure(tmp_path, bad):
    record, _ = prepare(tmp_path)
    if bad == "identity": record = replace(record, world_id="other")
    elif bad == "hashes": record = replace(record, copied_hashes={})
    elif bad == "base": (record.path / "World/Base.lean").write_text("changed base")
    elif bad == "target": (record.path / contract.TARGET_FILE).write_text("changed target")
    elif bad == "task": (record.path / "TASK.md").write_text("leaked task")
    elif bad == "unknown_file": (record.path / "SOURCE.md").write_text("leaked")
    elif bad == "cache": (record.path / ".lake").mkdir()
    elif bad == "empty_dir": (record.path / "Hidden").mkdir()
    elif bad == "symlink": (record.path / "alias").symlink_to(record.path / "TASK.md")
    else: (record.path / "Solution.lean").symlink_to(record.path / "TASK.md")
    with pytest.raises(production.WorkspaceIntegrityError):
        check(record)


@pytest.mark.parametrize("bad", ("missing", "other_world", "hash", "base", "name", "oversize", "utf8"))
def test_forged_or_mismatched_candidate_artifacts_cannot_define_their_own_base(tmp_path, bad):
    candidate = artifact(C)
    if bad == "missing": candidate = None
    elif bad == "other_world": candidate = replace(candidate, world_id="unknown")
    elif bad == "hash": candidate = replace(candidate, sha256="0" * 64)
    elif bad == "base": candidate = replace(candidate, base_hashes=())
    elif bad == "name": candidate = replace(candidate, declaration="oracle_bridge")
    else:
        source = b"x" * 100001 if bad == "oversize" else b"\xff"
        candidate = replace(candidate, source=source, sha256=sha(source))
    with pytest.raises(production.WorkspaceIntegrityError):
        contract.materialize_recipient(REPO, C["cell_id"], tmp_path / "workspace", candidate=candidate,
                                       lake="fixture-lake", process_runner=FakeCompiler())


@pytest.mark.parametrize("cell", (B, O))
def test_controls_cannot_receive_a_candidate_artifact(tmp_path, cell):
    with pytest.raises(production.WorkspaceIntegrityError):
        contract.materialize_recipient(REPO, cell["cell_id"], tmp_path / "workspace", candidate=artifact(C))


@pytest.mark.parametrize("source", (
    b"import World.ChallengeEvaluation\nimport Bridge\ntheorem evaluation_solution : True := by trivial",
    b"public import World.ChallengeEvaluation\ntheorem evaluation_solution : True := by trivial",
    b"import World.ChallengeEvaluation World.ChallengeEvaluation\ntheorem evaluation_solution : True := by trivial",
    b"import World.\nChallengeEvaluation\ntheorem evaluation_solution : True := by trivial",
    b"import World.ChallengeEvaluation\n# /- nested /- inner -/ -/ eval IO.println \"forged\"",
    b"import World.ChallengeEvaluation\nrun_elab do pure ()",
    b"import World.ChallengeEvaluation\naxiom evaluation_solution : False",
    b"import World.ChallengeEvaluation\ntheorem evaluation_solution : False := by sorry",
    b"import World.ChallengeEvaluation\nset_option maxRecDepth 1000\nset_option pp.all true",
    b"import World.ChallengeEvaluation\nnotation \"accept\" => True",
    b"import World.ChallengeEvaluation\n/- unclosed",
    b"\xff", b"x" * 100001,
))
def test_forbidden_outputs_are_rejected_before_solution_compilation(tmp_path, source):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(source)
    compiler = FakeCompiler()
    result = check(record, compiler=compiler)
    assert result.solution.status == "rejected" and not result.target_solved
    assert result.solution.source_sha256 == sha(source) and not compiler.calls


def test_missing_output_is_distinct_and_valid_options_are_allowed(tmp_path):
    record, _ = prepare(tmp_path)
    result = check(record)
    assert result.solution.status == "missing" and result.solution.source_sha256 is None
    (record.path / "Solution.lean").write_bytes(solution() + b"set_option maxHeartbeats 1000\nset_option maxRecDepth 100\n")
    assert check(record).target_solved


@pytest.mark.parametrize("code", tuple(contract.REJECTIONS))
def test_only_explicit_trusted_audit_rejections_are_mathematical(tmp_path, code):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(solution())
    result = check(record, compiler=FakeCompiler(fail="solution_audit", audit_code=code))
    assert result.solution.status == "rejected" and result.solution.errors == (contract.REJECTIONS[code],)


@pytest.mark.parametrize("output", (
    "unexpected runtime failure", "Solution.lean:1:1: error: maximum number of heartbeats exceeded",
    "Solution.lean:1:1: error: maximum recursion depth reached", "Solution.lean:1:1: error: out of memory",
    "Solution.lean:1:1: error: (deterministic) timeout", "segmentation fault", "stack overflow",
))
def test_resource_or_unclassified_compile_failure_never_becomes_unsolved(tmp_path, output):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(solution())
    with pytest.raises(production.VerificationInfrastructureError):
        check(record, compiler=FakeCompiler(fail="solution_compile", output=output))


@pytest.mark.parametrize("phase", ("base_build", "target_build", "bridge_compile", "bridge_audit", "bridge_rebuild", "solution_compile", "solution_audit"))
def test_timeouts_in_every_phase_are_technical_and_keep_diagnostics(tmp_path, phase):
    record, candidate = prepare(tmp_path, C)
    (record.path / "Solution.lean").write_bytes(solution(C))
    compiler = FakeCompiler(fail=phase, error=subprocess.TimeoutExpired("lean", 1, output=b"partial stdout", stderr=b"partial stderr"))
    with pytest.raises(production.VerificationInfrastructureError) as caught:
        check(record, C, candidate, compiler)
    assert caught.value.stdout == "partial stdout" and caught.value.stderr == "partial stderr"
    if phase in ("target_build", "bridge_rebuild", "solution_compile", "solution_audit"):
        assert caught.value.partial_bridge.valid


@pytest.mark.parametrize("phase", ("base_build", "target_build", "bridge_compile", "bridge_audit", "bridge_rebuild"))
def test_admitted_input_failure_cannot_be_attributed_to_recipient(tmp_path, phase):
    record, candidate = prepare(tmp_path, C)
    (record.path / "Solution.lean").write_bytes(solution(C))
    with pytest.raises(production.VerificationInfrastructureError):
        check(record, C, candidate, FakeCompiler(fail=phase, audit_code="identity"))


def test_ordinary_solution_compile_error_is_rejection_with_original_hash(tmp_path):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(solution())
    result = check(record, compiler=FakeCompiler(fail="solution_compile"))
    assert result.solution.status == "rejected" and result.solution.source_sha256 == sha(solution())


@pytest.mark.parametrize("kind", ("missing_receipt", "unknown_code", "double_error", "wrong_name", "forbidden_axiom", "bad_process", "signal"))
def test_spoofed_receipts_and_checker_bugs_are_technical(tmp_path, kind):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(solution())
    base = FakeCompiler(audit_receipt=kind != "missing_receipt")
    def compiler(command, **kwargs):
        result = base(command, **kwargs)
        if kind == "signal": return subprocess.CompletedProcess(command, -9, "killed", "")
        if kind == "bad_process": return {"returncode": 0, "stdout": "untrusted mapping", "stderr": ""}
        if command[-1] == "Audit.lean":
            if kind == "unknown_code": return subprocess.CompletedProcess(command, 1, f"Audit.lean:1:1: error: {contract.REJECTION_MARKER}|bug\n", "")
            if kind == "double_error": return subprocess.CompletedProcess(command, 1, f"Audit.lean:1:1: error: {contract.REJECTION_MARKER}|identity\nAudit.lean:2:1: error: other\n", "")
            if kind == "wrong_name": return subprocess.CompletedProcess(command, 0, f"{contract.AUDIT_MARKER}|candidate_solution|\n", "")
            if kind == "forbidden_axiom": return subprocess.CompletedProcess(command, 0, f"{contract.AUDIT_MARKER}|evaluation_solution|sorryAx\n", "")
        return result
    with pytest.raises(production.VerificationInfrastructureError):
        check(record, compiler=compiler)


@pytest.mark.parametrize("timeout", (0, -1, 121, True, float("nan"), float("inf"), "120"))
def test_timeout_validation(tmp_path, timeout):
    record, _ = prepare(tmp_path)
    with pytest.raises(ValueError): check(record, timeout_s=timeout)
    with pytest.raises(ValueError): contract.materialize_recipient(REPO, B["cell_id"], tmp_path / "invalid", timeout_s=timeout)


def test_one_shared_deadline_instead_of_a_new_budget_per_compiler_command(tmp_path, monkeypatch):
    record, candidate = prepare(tmp_path, C)
    (record.path / "Solution.lean").write_bytes(solution(C))
    clock = [0.0]
    monkeypatch.setattr(contract.time, "monotonic", lambda: clock[0])
    compiler = FakeCompiler(on_call=lambda _: clock.__setitem__(0, clock[0] + 10))
    assert check(record, C, candidate, compiler).target_solved
    assert [call["timeout"] for call in compiler.calls] == [120, 110, 100, 90, 80, 70, 60]
    clock[0] = 0
    late = FakeCompiler(on_call=lambda _: clock.__setitem__(0, clock[0] + 61))
    with pytest.raises(production.VerificationInfrastructureError, match="shared deadline"):
        check(record, C, candidate, late)


@pytest.mark.parametrize("which", ("base", "target", "bridge", "solution"))
def test_live_mutation_during_check_is_not_accepted(tmp_path, which):
    record, candidate = prepare(tmp_path, C)
    (record.path / "Solution.lean").write_bytes(solution(C))
    rel = {"base": "World/Base.lean", "target": contract.TARGET_FILE, "bridge": "Bridge.lean", "solution": "Solution.lean"}[which]
    compiler = FakeCompiler(on_call=lambda _: (record.path / rel).write_bytes(b"changed during verification"))
    with pytest.raises(production.WorkspaceIntegrityError):
        check(record, C, candidate, compiler)


def test_world_or_holdout_relabelling_cannot_change_the_trusted_goal(tmp_path):
    record, _ = prepare(tmp_path)
    other = next(c for c in CELLS if c["arm"] == "B" and c["world_id"] == B["world_id"] and c["holdout"] != B["holdout"])
    with pytest.raises(production.WorkspaceIntegrityError): check(record, other)
    with pytest.raises(production.WorkspaceIntegrityError): contract.materialize_recipient(REPO, "unknown", tmp_path / "other")
    assert sha(encoded(load_blueprint(REPO))) == "74e0ee9e49aa92797d6951023345c5d38dc46dd1d28eea1fae3db0db1035fa81"


def test_rehashing_a_modified_goal_cannot_make_it_the_frozen_target(tmp_path):
    record, _ = prepare(tmp_path)
    forged = b"def differentGoal : Prop := True\n"
    (record.path / contract.TARGET_FILE).write_bytes(forged)
    record = replace(record, copied_hashes={**record.copied_hashes, contract.TARGET_FILE: sha(forged)})
    with pytest.raises(production.WorkspaceIntegrityError):
        check(record)


@pytest.mark.parametrize("error", (RuntimeError("sandbox launcher failed"), OSError("unavailable"),
                                   UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid compiler output")))
def test_process_adapter_or_decoder_exception_is_explicit_infrastructure(tmp_path, error):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(solution())
    with pytest.raises(production.VerificationInfrastructureError) as caught:
        check(record, compiler=FakeCompiler(fail="target_build", error=error))
    assert caught.value.__cause__ is error


def test_missing_lean_runtime_is_not_an_unsolved_task(tmp_path, monkeypatch):
    record, _ = prepare(tmp_path)
    monkeypatch.setattr(contract.shutil, "which", lambda _: None)
    with pytest.raises(production.VerificationInfrastructureError, match="lake executable"):
        contract.verify_recipient(record, repository=REPO, cell_id=B["cell_id"])


def test_default_verification_uses_the_sandbox_boundary(tmp_path, monkeypatch):
    record, _ = prepare(tmp_path)
    (record.path / "Solution.lean").write_bytes(solution())
    compiler = FakeCompiler()
    monkeypatch.setattr(contract, "sandbox_process", compiler)
    assert contract.verify_recipient(record, repository=REPO, cell_id=B["cell_id"], lake="fixture-lake").target_solved
    assert compiler.calls


def known_proof(cell):
    world = REPO / cell["world"]
    proof = closure_v3(world, f"holdout{cell['holdout']}", "oracle")
    if cell["bridge_kind"] == "candidate":
        return proof.replace("oracle_bridge", "candidate_bridge").encode()
    if cell["bridge_kind"] == "none":
        helper = (world / "Hidden/Oracle.lean").read_text().replace("import World.Base", "import World.ChallengeEvaluation")
        return (helper + "\n" + proof.replace("import World.ChallengeEvaluation\nimport Bridge\n", "")).encode()
    return proof.encode()


REAL_CELLS = [c for c in CELLS if c["arm"] in ("B", "O", "D0") and c["holdout"] == 1]
REAL_CELLS += [c for c in CELLS if c["arm"] == "O" and c["holdout"] == 2]


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("cell", REAL_CELLS)
def test_real_lean_exact_target_and_unmodified_bridge_in_both_families(tmp_path, cell):
    candidate = None
    if cell["bridge_kind"] == "candidate":
        raw = (REPO / cell["world"] / "Hidden/Oracle.lean").read_bytes().replace(b"oracle_bridge", b"candidate_bridge")
        candidate = artifact(cell, raw, "P3." + cell["world_id"] + ".candidate_bridge")
    record = contract.materialize_recipient(REPO, cell["cell_id"], tmp_path / "workspace", candidate=candidate)
    source = known_proof(cell)
    (record.path / "Solution.lean").write_bytes(source)
    report = contract.verify_recipient(record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate)
    assert report.target_solved, report
    assert report.solution.declaration == "P3." + cell["world_id"] + ".evaluation_solution"
    assert report.statement == f"Holdout{cell['holdout']}Statement"
    assert report.solution.source_sha256 == sha(source)
    assert set(report.solution.axioms) <= set(production.STANDARD_LEAN_AXIOMS)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("kind", ("wrong_type", "definition", "private", "ambiguous"))
def test_real_lean_does_not_accept_wrong_type_kind_or_identity(tmp_path, kind):
    record, _ = prepare(tmp_path)
    source = known_proof(B).decode()
    if kind == "wrong_type": source = solution().decode()
    elif kind == "definition": source = source.replace("theorem evaluation_solution", "def evaluation_solution")
    elif kind == "private": source = source.replace("theorem evaluation_solution", "private theorem evaluation_solution")
    else: source += "\ntheorem evaluation_solution : True := by trivial\n"
    (record.path / "Solution.lean").write_text(source)
    report = contract.verify_recipient(record, repository=REPO, cell_id=B["cell_id"])
    expected = {"wrong_type": "target_type", "definition": "kind", "private": "identity", "ambiguous": "identity"}[kind]
    assert report.solution.status == "rejected" and report.solution.errors == (contract.REJECTIONS[expected],)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_cannot_inherit_evaluation_solution_from_bridge_instead_of_writing_solution(tmp_path):
    # This fixture is intentionally invalid as a recipient answer, regardless of
    # whether its bridge would pass the separate content review (not run here).
    source = BRIDGE + b"theorem evaluation_solution : True := by trivial\n"
    candidate = artifact(C, source)
    record = contract.materialize_recipient(REPO, C["cell_id"], tmp_path / "workspace", candidate=candidate)
    (record.path / "Solution.lean").write_text("import World.ChallengeEvaluation\nimport Bridge\n")
    report = contract.verify_recipient(record, repository=REPO, cell_id=C["cell_id"], candidate=candidate)
    assert report.solution.status == "rejected" and report.solution.errors == (contract.REJECTIONS["origin"],)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_checks_transitive_axioms_even_without_an_axiom_declaration(tmp_path):
    record, _ = prepare(tmp_path)
    ns = "P3." + B["world_id"]
    source = known_proof(B).decode().replace("theorem evaluation_solution", "theorem sound_solution")
    source += (f"\ntheorem evaluation_solution : {ns}.Holdout{B['holdout']}Statement :=\n"
               f"  And.left (And.intro {ns}.sound_solution Lean.trustCompiler)\n")
    (record.path / "Solution.lean").write_text(source)
    report = contract.verify_recipient(record, repository=REPO, cell_id=B["cell_id"])
    assert report.solution.status == "rejected" and report.solution.errors == (contract.REJECTIONS["axioms"],)
