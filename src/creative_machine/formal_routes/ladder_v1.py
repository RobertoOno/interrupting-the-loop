"""A1 — sibling ladder worlds, v1 (no model calls here).

One schema, "unreachability by a conserved quantity", in five graded steps; each step is a small Lean 4.33.1
world (Std only) in the P3 layout, with a reference proof verified by the SAME checker the sessions use.
Sibling instances are seeded: the constants differ, the schema does not.

  L1  difference      2 fields; moves add the same constant to both; measure y - x            (omega)
  L2  linear form     3 fields; two moves annihilated by a hidden form ax + by + z; point target (omega)
  L3  modular         2 fields; moves generate an index-n sublattice; measure (ax + by) mod n  (omega)
  L4  quadratic shear 3 fields; the P3 shears with offsets; measure (x-cx)(z-cz) - (y-cy)^2    (grind)
  L5  Vieta map       2 fields; (x,y) -> (y, ky - x) and inverse; measure x^2 - kxy + y^2      (grind)

Sources for the arms: `Sources/Ladder.lean` = the PREVIOUS step's world and complete proof, rewritten as a
separate problem in namespace Source (the ladder); `Sources/Sham.lean` = the fixed P3 InvariantSham asset
(a same-schema but generic worked example). Step 1 has no ladder source.
"""
from __future__ import annotations
import hashlib, json, random, shutil, subprocess, tempfile
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "0.1.0"
TOOLCHAIN = "leanprover/lean4:v4.33.1"
STATEMENT = "LadderStatement"
STEPS = ("L1", "L2", "L3", "L4", "L5")
SCHEMAS = {"L1": "difference", "L2": "linear_form", "L3": "modular", "L4": "quadratic_shear", "L5": "vieta", "E": "pell_form"}
ALLOWED_AXIOMS = ("propext", "Quot.sound", "Classical.choice")
SHAM_ASSET = Path(__file__).parent / "assets/conceptual_v3/InvariantSham.lean"
SOURCE_HEADER = "# Worked example\n\nA separate formal problem and its complete proof.\n\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def lit(n: int) -> str:
    """Integer literal for Lean; negative numbers in parentheses."""
    return f"({n})" if n < 0 else str(n)


def instance_id(seed: str) -> str:
    return "S" + hashlib.sha256(f"a1-ladder-v1:{seed}".encode()).hexdigest()[:8].upper()


def rng(seed: str, step: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"a1-ladder-v1:{seed}:{step}".encode()).hexdigest()[:16], 16))


@dataclass
class StepWorld:
    seed: str
    step: str
    params: dict
    fields: tuple[str, ...]
    moves: list[str]                 # move bodies in terms of s.<field>, e.g. "⟨s.x + 2, s.y + 2⟩"
    start: tuple[int, ...]
    statement: str                   # the Prop after "def LadderStatement : Prop :="
    measure: str                     # body in terms of s.<field>
    step_tactic: str                 # "omega" or "grind"
    solution_intro: str              # e.g. "intro t h" / "intro h" / "intro a b h"
    solution_hints: list[str] = field(default_factory=list)   # e.g. ["have na := Int.sq_nonneg a"]
    solution_close: str = "omega"    # "omega" or "grind [measure, start]"
    hint_target: str = ""           # prose: the value of the quantity on the target family (content arm, v2)

    @property
    def instance(self) -> str:
        return instance_id(self.seed)

    @property
    def namespace(self) -> str:
        return f"A1.{self.instance}.{self.step}"


# ----------------------------------------------------------------------------------------------- parameters

def _nonzero(r: random.Random, lo: int, hi: int) -> int:
    while True:
        v = r.randint(lo, hi)
        if v != 0:
            return v


def make_step(seed: str, step: str) -> StepWorld:
    r = rng(seed, step)
    if step == "L1":
        a = r.randint(1, 3); b = r.randint(a + 1, 5); s0 = r.randint(-5, 5); d = _nonzero(r, -3, 3)
        return StepWorld(seed, step, {"a": a, "b": b, "s0": s0, "d": d}, ("x", "y"),
            [f"⟨s.x + {a}, s.y + {a}⟩", f"⟨s.x - {a}, s.y - {a}⟩", f"⟨s.x + {b}, s.y + {b}⟩", f"⟨s.x - {b}, s.y - {b}⟩"],
            (s0, s0 + d), "∀ (t : Int), ¬ Reaches start ⟨t, t⟩", "s.y - s.x", "omega", "intro t h", [], "omega", "on every target state ⟨t, t⟩ the quantity equals 0")
    if step == "L2":
        while True:
            al = _nonzero(r, -3, 3); be = _nonzero(r, -3, 3)
            p1, q1, p2, q2 = (_nonzero(r, -3, 3) for _ in range(4))
            if p1 * q2 - p2 * q1 == 0:
                continue
            r1, r2 = -(al * p1 + be * q1), -(al * p2 + be * q2)
            st = tuple(r.randint(-4, 4) for _ in range(3))
            v = tuple(r.randint(-5, 5) for _ in range(3))
            if al * v[0] + be * v[1] + v[2] == 0:
                continue
            t = tuple(s + w for s, w in zip(st, v))
            break
        mv = lambda p, q, rr: f"⟨s.x {'+' if p >= 0 else '-'} {abs(p)}, s.y {'+' if q >= 0 else '-'} {abs(q)}, s.z {'+' if rr >= 0 else '-'} {abs(rr)}⟩"
        return StepWorld(seed, step, {"alpha": al, "beta": be, "m1": [p1, q1, r1], "m2": [p2, q2, r2], "start": list(st), "target": list(t)},
            ("x", "y", "z"), [mv(p1, q1, r1), mv(p2, q2, r2), mv(-p1, -q1, -r1), mv(-p2, -q2, -r2)], st,
            f"¬ Reaches start ⟨{lit(t[0])}, {lit(t[1])}, {lit(t[2])}⟩",
            f"{lit(al)} * s.x + {lit(be)} * s.y + s.z", "omega", "intro h", [], "omega", f"on the target state it equals {al * t[0] + be * t[1] + t[2]}")
    if step == "L3":
        n = r.choice([3, 5, 7]); c2 = r.randint(1, n - 1)
        inv = pow(c2, -1, n)
        while True:
            p1, p2 = r.randint(1, 4), r.randint(1, 4)
            q1 = (-p1 * inv) % n + n * r.randint(0, 1); q2 = (-p2 * inv) % n + n * r.randint(0, 1)
            if p1 * q2 - p2 * q1 != 0:
                break
        st = (r.randint(-4, 4), r.randint(-4, 4))
        while True:
            t = (r.randint(-6, 6), r.randint(-6, 6))
            if (t[0] + c2 * t[1]) % n != (st[0] + c2 * st[1]) % n:
                break
        mv = lambda p, q: f"⟨s.x {'+' if p >= 0 else '-'} {abs(p)}, s.y {'+' if q >= 0 else '-'} {abs(q)}⟩"
        return StepWorld(seed, step, {"n": n, "c2": c2, "m1": [p1, q1], "m2": [p2, q2], "start": list(st), "target": list(t)},
            ("x", "y"), [mv(p1, q1), mv(p2, q2), mv(-p1, -q1), mv(-p2, -q2)], st,
            f"¬ Reaches start ⟨{lit(t[0])}, {lit(t[1])}⟩", f"(s.x + {c2} * s.y) % {n}", "omega", "intro h", [], "omega", f"on the target state it equals {(t[0] + c2 * t[1]) % n}")
    if step == "L4":
        cx, cy, cz = (r.randint(-4, 4) for _ in range(3))
        while True:
            u, v, w = r.randint(-3, 3), r.randint(-3, 3), r.randint(-3, 3)
            if u * w - v * v >= 1:
                break
        st = (cx + u, cy + v, cz + w)
        # shears preserving (x-cx)(z-cz) - (y-cy)^2, exactly as the P3 worlds
        m1 = f"⟨s.x + 2 * s.y + s.z - 2 * {lit(cy)} - {lit(cz)}, s.y + s.z - {lit(cz)}, s.z⟩"
        m2 = f"⟨s.x - 2 * s.y + s.z + 2 * {lit(cy)} - {lit(cz)}, s.y - s.z + {lit(cz)}, s.z⟩"
        m3 = f"⟨s.x, s.x + s.y - {lit(cx)}, s.x + 2 * s.y + s.z - {lit(cx)} - 2 * {lit(cy)}⟩"
        m4 = f"⟨s.x, s.y - s.x + {lit(cx)}, s.x - 2 * s.y + s.z - {lit(cx)} + 2 * {lit(cy)}⟩"
        return StepWorld(seed, step, {"offsets": [cx, cy, cz], "start": list(st), "start_measure": u * w - v * v}, ("x", "y", "z"),
            [m1, m2, m3, m4], st, f"∀ (a b : Int), ¬ Reaches start ⟨a + {lit(cx)}, b + {lit(cy)}, -a + {lit(cz)}⟩",
            f"(s.x - {lit(cx)}) * (s.z - {lit(cz)}) - (s.y - {lit(cy)}) * (s.y - {lit(cy)})", "grind", "intro a b h",
            ["have na := Int.sq_nonneg a", "have nb := Int.sq_nonneg b"], "grind [measure, start]", "on every target state it equals −a·a − b·b, which is at most 0")
    if step == "E":
        D, (a, b) = r.choice([(2, (3, 2)), (3, (2, 1)), (5, (9, 4))])   # a^2 - D b^2 = 1: the map preserves x^2 - D y^2
        st = r.choice([(1, 1), (1, 2), (2, 3), (1, 3)]); q0 = st[0] * st[0] - D * st[1] * st[1]
        assert q0 < 0, (D, st, q0)
        return StepWorld(seed, step, {"D": D, "unit": [a, b], "start": list(st), "start_measure": q0}, ("x", "y"),
            [f"⟨{a} * s.x + {2 * b if D == 2 else D * b} * s.y, {b} * s.x + {a} * s.y⟩", f"⟨{a} * s.x - {2 * b if D == 2 else D * b} * s.y, {a} * s.y - {b} * s.x⟩"],
            st, "∀ (t : Int), ¬ Reaches start ⟨t, 0⟩", f"s.x * s.x - {D} * s.y * s.y", "grind", "intro t h",
            ["have nt := Int.sq_nonneg t"], "grind [measure, start]", "on every target state ⟨t, 0⟩ it equals t·t, which is at least 0")
    if step == "L5":
        k = r.choice([3, 4, 5])
        st = r.choice([(1, 1), (1, 2), (2, 3), (1, k - 1)])
        q0 = st[0] * st[0] - k * st[0] * st[1] + st[1] * st[1]
        assert q0 < 0, (k, st, q0)
        return StepWorld(seed, step, {"k": k, "start": list(st), "start_measure": q0}, ("x", "y"),
            [f"⟨s.y, {k} * s.y - s.x⟩", f"⟨{k} * s.x - s.y, s.x⟩"], st, "∀ (t : Int), ¬ Reaches start ⟨t, 0⟩",
            f"s.x * s.x - {k} * s.x * s.y + s.y * s.y", "grind", "intro t h", ["have nt := Int.sq_nonneg t"], "grind [measure, start]", "on every target state ⟨t, 0⟩ it equals t·t, which is at least 0")
    raise ValueError(step)


# ------------------------------------------------------------------------------------------------ rendering

MOVE_NAMES = ("first", "second", "third", "fourth")


def _state_block(fields: tuple[str, ...]) -> str:
    return "structure State where\n" + "".join(f"  {f} : Int\n" for f in fields) + "deriving DecidableEq, Repr\n"


def _moves_block(w: StepWorld, fields: tuple[str, ...]) -> str:
    ren = dict(zip(w.fields, fields))
    def sub(body: str) -> str:
        for a, b in ren.items():
            body = body.replace(f"s.{a}", f"s.__{b}")
        return body.replace("s.__", "s.")
    out = "".join(f"def move{i + 1} (s : State) : State := {sub(m)}\n" for i, m in enumerate(w.moves))
    out += "\ninductive Step : State → State → Prop where\n"
    out += "".join(f"  | {MOVE_NAMES[i]} (s) : Step s (move{i + 1} s)\n" for i in range(len(w.moves)))
    out += "\ninductive Reaches : State → State → Prop where\n  | refl (s) : Reaches s s\n  | tail {s t u} : Reaches s t → Step t u → Reaches s u\n"
    out += f"\ndef start : State := ⟨{', '.join(lit(v) for v in w.start)}⟩\n"
    return out


def _measure_block(w: StepWorld, fields: tuple[str, ...], bridge_name: str) -> str:
    ren = dict(zip(w.fields, fields))
    body = w.measure
    for a, b in ren.items():
        body = body.replace(f"s.{a}", f"s.__{b}")
    body = body.replace("s.__", "s.")
    moves = ", ".join(f"move{i + 1}" for i in range(len(w.moves)))
    return (f"def measure (s : State) : Int := {body}\n\n"
            f"theorem step_measure {{s t : State}} (h : Step s t) : measure s = measure t := by\n"
            f"  cases h <;> simp only [measure, {moves}] <;> {w.step_tactic}\n\n"
            f"theorem {bridge_name} {{s t : State}} (h : Reaches s t) : measure s = measure t := by\n"
            f"  induction h with\n  | refl => rfl\n  | tail _ step ih => exact ih.trans (step_measure step)\n")


def _solution_body(w: StepWorld, bridge_name: str) -> str:
    hints = "".join(f"  {h}\n" for h in w.solution_hints)
    close = w.solution_close
    if close == "omega":
        return f"  {w.solution_intro}\n  have conserved := {bridge_name} h\n  simp only [measure, start] at conserved\n{hints}  omega\n"
    return f"  {w.solution_intro}\n  have conserved := {bridge_name} h\n{hints}  {close}\n"


def render_base(w: StepWorld, env: str = "std") -> str:
    imp = "import Mathlib" if env == "mathlib" else "import Std"
    return f"{imp}\n\nnamespace {w.namespace}\n\n{_state_block(w.fields)}\n{_moves_block(w, w.fields)}\nend {w.namespace}\n"


def render_target(w: StepWorld) -> str:
    return f"import World.Base\n\nnamespace {w.namespace}\n\ndef {STATEMENT} : Prop :=\n  {w.statement}\n\nend {w.namespace}\n"


def render_oracle(w: StepWorld) -> str:
    return f"import World.Base\n\nnamespace {w.namespace}\n\n{_measure_block(w, w.fields, 'oracle_bridge')}\nend {w.namespace}\n"


def render_reference_solution(w: StepWorld) -> str:
    return (f"import World.ChallengeEvaluation\n\nnamespace {w.namespace}\n\n{_measure_block(w, w.fields, 'bridge')}\n"
            f"theorem evaluation_solution : {STATEMENT} := by\n{_solution_body(w, 'bridge')}\nend {w.namespace}\n")


def render_source(w: StepWorld) -> str:
    """The step as a separate worked example: namespace Source, fields u v (w), complete proof, axiom prints."""
    fields = ("u", "v", "w")[:len(w.fields)]
    stmt = w.statement
    for a, b in zip(w.fields, fields):
        stmt = stmt.replace(f"s.{a}", f"s.{b}")
    return (f"import Std\n\nnamespace Source\n\n{_state_block(fields)}\n{_moves_block(w, fields)}\n{_measure_block(w, fields, 'bridge')}\n"
            f"theorem source_solution : {stmt} := by\n{_solution_body(w, 'bridge')}\nend Source\n\n"
            f"#print axioms Source.step_measure\n#print axioms Source.bridge\n#print axioms Source.source_solution\n")


def start_value(w: StepWorld) -> int:
    """Numeric value of the quantity at the start (the generated expressions are our own; Python % matches Int.emod)."""
    expr = w.measure
    for f, v in zip(w.fields, w.start):
        expr = expr.replace(f"s.{f}", f"({v})")
    return int(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - generated arithmetic only


def render_content_hint(w: StepWorld) -> str:
    """The IDEA of the proof in prose, with no Lean code (content arm, v2): which quantity is conserved,
    its value at the start, its value on the targets, hence unreachability."""
    pretty = w.measure
    for f in w.fields:
        pretty = pretty.replace(f"s.{f}", f)
    pretty = pretty.replace("*", "·")
    kind = "the residue" if "%" in w.measure else "the quantity"
    return ("# Hint\n\nA mathematical hint about this target, in prose. No Lean code is provided; the proof must be written from it.\n\n"
            f"Every move of this world preserves {kind} Q = {pretty}. Check it move by move: applying any move to a state does not\n"
            f"change Q. Because Q is preserved by every step, it is the same on every state reachable from the start. At the start,\n"
            f"Q = {start_value(w)}; {w.hint_target}. The two values can never coincide, so no target state is reachable from the start.\n")


MATHLIB_REV = "v4.33.1"


def render_lakefile(w: StepWorld, env: str = "std") -> str:
    req = (f'[[require]]\nname = "mathlib"\ngit = "https://github.com/leanprover-community/mathlib4"\nrev = "{MATHLIB_REV}"\n\n' if env == "mathlib" else "")
    return (f'name = "a1_{w.instance.lower()}_{w.step.lower()}"\nversion = "1.0.0"\n\n' + req + '[[lean_lib]]\nname = "World"\n\n'
            '[[lean_lib]]\nname = "Hidden"\n\n[[lean_lib]]\nname = "Sources"\n')


def md_source(lean_text: str) -> str:
    return SOURCE_HEADER + "```lean\n" + lean_text + "```\n"


# --------------------------------------------------------------------------------------------- build / verify

def build_instance(seed: str, root: Path, *, phase: str, extra: tuple[str, ...] = (), env: str = "std") -> list[Path]:
    """Write worlds/<root>/<instance>/L1..L5 with metadata and manifests. Refuses to overwrite."""
    inst = instance_id(seed); base = Path(root) / inst
    if base.exists():
        raise FileExistsError(base)
    worlds = [make_step(seed, s) for s in STEPS] + [make_step(seed, s) for s in extra]
    sham = SHAM_ASSET.read_text(encoding="utf-8")
    out = []
    for i, w in enumerate(worlds):
        d = base / w.step
        files = {"lakefile.toml": render_lakefile(w, env), "lean-toolchain": TOOLCHAIN + "\n", "World/Base.lean": render_base(w, env),
                 "World/ChallengeEvaluation.lean": render_target(w), "Hidden/Oracle.lean": render_oracle(w),
                 "Hidden/Reference.lean": render_reference_solution(w), "Sources/Sham.lean": sham, "Sources/Sham.md": md_source(sham),
                 "Sources/Content.md": render_content_hint(w)}
        if 0 < i < len(STEPS):
            src = render_source(worlds[i - 1])
            files["Sources/Ladder.lean"] = src; files["Sources/Ladder.md"] = md_source(src)
        for rel, text in files.items():
            p = d / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
        hashes = {rel: sha(text) for rel, text in files.items()}
        meta = {"schema_version": 1, "generator": "creative_machine.formal_routes.ladder_v1", "generator_version": VERSION,
                "family": "ladder_conserved_quantity_v1", "instance": inst, "seed_label": seed, "step": w.step, "step_index": (i + 1 if i < len(STEPS) else 0),
                "schema": SCHEMAS[w.step], "parameters": w.params, "fields": list(w.fields), "start": list(w.start),
                "roles": {"namespace": w.namespace, "statement": STATEMENT, "oracle_bridge": "oracle_bridge"},
                "public_files": ["lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeEvaluation.lean"],
                "source_files": {"ladder": "Sources/Ladder.md" if 0 < i < len(STEPS) else None, "sham": "Sources/Sham.md", "skeleton": "Sources/Sham.md", "content": "Sources/Content.md"},
                "hidden_files": ["Hidden/Oracle.lean", "Hidden/Reference.lean"], "allowed_axioms": list(ALLOWED_AXIOMS),
                "toolchain": TOOLCHAIN, "env": env, "phase": phase, "eligible_for_main": phase == "main", "artifact_hashes": hashes,
                "statement_text": w.statement}
        (d / "metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (d / "manifest.sha256").write_text("".join(f"{h}  {rel}\n" for rel, h in sorted(hashes.items())), encoding="utf-8")
        out.append(d)
    return out


def load_step(d: Path) -> dict:
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    for rel, h in meta["artifact_hashes"].items():
        if sha((d / rel).read_text(encoding="utf-8")) != h:
            raise ValueError(f"artifact changed: {d / rel}")
    return meta


def _stage(d: Path, dest: Path, rels: list[str]) -> None:
    from .submission import attach_shared_lake
    for rel in rels:
        p = dest / rel; p.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(d / rel, p)
    attach_shared_lake(dest)


def verify_step(d: Path, *, lake: str = "lake", timeout: float = 300.0) -> dict:
    """Compile every module, audit axioms of the sources, and pass the reference solution through the SAME
    checker the sessions use (verify_evaluator_solution with bridge_supplied=False)."""
    from .submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution
    meta = load_step(d)
    rels = list(meta["artifact_hashes"])
    result = {"step": meta["step"], "instance": meta["instance"], "modules_ok": False, "reference_ok": False, "source_axioms_ok": None, "errors": []}
    with tempfile.TemporaryDirectory(prefix="a1-verify-") as tmp:
        staged = Path(tmp) / "w"; _stage(d, staged, rels)
        modules = ["World.Base", "World.ChallengeEvaluation", "Hidden.Oracle", "Sources.Sham"] + (["Sources.Ladder"] if "Sources/Ladder.lean" in rels else [])
        built = subprocess.run([lake, "build", *modules], cwd=staged, capture_output=True, text=True, timeout=timeout)
        result["modules_ok"] = built.returncode == 0
        if built.returncode != 0:
            result["errors"].append("build: " + (built.stderr + built.stdout).strip()[-1500:])
            return result
        if "Sources/Ladder.lean" in rels:
            audit = subprocess.run([lake, "env", "lean", "Sources/Ladder.lean"], cwd=staged, capture_output=True, text=True, timeout=timeout)
            text = audit.stdout + audit.stderr
            result["source_axioms_ok"] = audit.returncode == 0 and text.count("depends on axioms") == 3 and "sorryAx" not in text
        # reference solution through the session checker
        shutil.copy2(d / "Hidden/Reference.lean", staged / "Solution.lean")
        rep = verify_evaluator_solution(staged, namespace=meta["roles"]["namespace"], statement=STATEMENT, bridge_supplied=False,
                                        timeout_s=timeout, allowed_axioms=STANDARD_LEAN_AXIOMS)
        result["reference_ok"] = rep.ok
        if not rep.ok:
            result["errors"].append("reference: " + "; ".join(rep.errors)[:1500])
    return result


# ---------------------------------------------------------------------------------------- falsification check

def mutated(w: StepWorld) -> tuple[StepWorld, str]:
    """A copy of the step whose statement is FALSE (the start lies in the target family), plus the Lean
    witness proving ¬ LadderStatement. Used to check that the reference proof depends on the world."""
    import copy
    m = copy.deepcopy(w)
    if w.step == "L1":
        m.start = (w.start[0], w.start[0]); witness = f"fun h => h {lit(w.start[0])} (Reaches.refl start)"
    elif w.step in ("L2", "L3"):
        m.statement = f"¬ Reaches start ⟨{', '.join(lit(v) for v in w.start)}⟩"; witness = "fun h => h (Reaches.refl start)"
    elif w.step == "L4":
        cx, cy, cz = w.params["offsets"]; m.start = (cx, cy, cz); witness = "fun h => h 0 0 (Reaches.refl start)"
    elif w.step in ("L5", "E"):
        m.start = (1, 0); witness = "fun h => h 1 (Reaches.refl start)"
    else:
        raise ValueError(w.step)
    return m, witness


def mutation_check(d: Path, *, lake: str = "lake", timeout: float = 300.0) -> dict:
    """(i) the reference proof is REJECTED on the mutated world; (ii) the witness proves the mutated
    statement false. Both must hold for the step to count as non-degenerate."""
    from .submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution
    meta = load_step(d)
    w = make_step(meta["seed_label"], meta["step"])
    m, witness = mutated(w)
    out = {"step": meta["step"], "reference_rejected": False, "witness_ok": False, "errors": []}
    with tempfile.TemporaryDirectory(prefix="a1-mutation-") as tmp:
        staged = Path(tmp) / "w"
        env = meta.get("env", "std")
        for rel, text in {"lakefile.toml": render_lakefile(m, env), "lean-toolchain": TOOLCHAIN + "\n", "World/Base.lean": render_base(m, env),
                          "World/ChallengeEvaluation.lean": render_target(m)}.items():
            p = staged / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
        from .submission import attach_shared_lake
        attach_shared_lake(staged)
        (staged / "Solution.lean").write_text(render_reference_solution(m), encoding="utf-8")
        rep = verify_evaluator_solution(staged, namespace=m.namespace, statement=STATEMENT, bridge_supplied=False,
                                        timeout_s=timeout, allowed_axioms=STANDARD_LEAN_AXIOMS)
        out["reference_rejected"] = not rep.ok
        if rep.ok:
            out["errors"].append("reference proof still accepted on the mutated world")
        (staged / "Witness.lean").write_text(f"import World.ChallengeEvaluation\n\nnamespace {m.namespace}\n\n"
                                             f"theorem falsified : ¬ {STATEMENT} := {witness}\n\nend {m.namespace}\n\n#print axioms {m.namespace}.falsified\n", encoding="utf-8")
        subprocess.run([lake, "build", "World.ChallengeEvaluation"], cwd=staged, capture_output=True, text=True, timeout=timeout)
        wit = subprocess.run([lake, "env", "lean", "Witness.lean"], cwd=staged, capture_output=True, text=True, timeout=timeout)
        out["witness_ok"] = wit.returncode == 0 and "sorryAx" not in wit.stdout + wit.stderr
        if wit.returncode != 0:
            out["errors"].append("witness: " + (wit.stderr + wit.stdout).strip()[-800:])
    return out
