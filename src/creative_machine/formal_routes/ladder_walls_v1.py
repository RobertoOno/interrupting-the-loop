"""A7 — wall candidates (no model calls here).

Same world layout, prover-mode pipeline and checker as ladder_v1 (Mathlib worlds); new steps built to be hard for the base
model with full thinking. Each candidate has a reference proof verified by the session checker, a falsification check, and a
brute-force CERTIFICATE that no simpler invariant separates start and target: no exact linear invariant over Z and no linear
invariant modulo m (2 <= m <= M) other than the ones listed as intended.

  W1 pell_mod       2 fields; Pell automorph of x^2 - D y^2 plus translations by a prime p; the quantity is conserved only
                    MOD p; targets <t, 0> have t^2, a square residue, the start a non-residue.   (composition: E/L5 form + L3 residue)
  W2 plane_lattice  3 fields; translations inside the plane of a hidden form ax + by + z. That exact linear invariant exists
                    but does NOT separate (the target lies on the plane); the obstruction is a linear form mod k, the index of
                    the move lattice inside the plane.                                              (trap: L2 invariant fails, L3 needed)
  W3 hyperbolic4    4 fields with offsets; SL2 shears acting on two vectors at once preserve (x-cx)(w-cw) - (y-cy)(z-cz);
                    targets have value a^2 + b^2 >= 0 > start.                                      (harder single ingredient: L4 in 4D)
  W4 lattice_mod_p  2 fields; the L3 construction with a large prime modulus (11..19).             (calibration: parameter inference)
  W5 hyperbolic4_mod_p (A9, 19/09; added without touching W1..W4, whose random streams are per (seed, step)): 4 fields with offsets;
                    two SL2 shears that preserve the bilinear form of W3 exactly, plus translations of x and w by a prime p, which
                    preserve it only MOD p; a point target whose form value has another residue.   (composition: W3 form + W1 residue)

One step per instance (the runner keys example sources by (instance, arm)): instance ids are "W" + hash of the seed.
"""
from __future__ import annotations
import copy, hashlib, itertools, json, random, subprocess, tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from . import ladder_v1 as L

VERSION = "0.1.0"
WALLS = ("W1", "W2", "W3", "W4")
WALLS_V2 = ("W5",)   # A9; kept out of WALLS so that the default build of the A7/A8 families is unchanged
SCHEMAS = {"W1": "pell_mod", "W2": "plane_lattice", "W3": "hyperbolic4", "W4": "lattice_mod_p", "W5": "hyperbolic4_mod_p"}
VERSION_BY_STEP = {"W5": "0.2.0"}
ENV = "mathlib"


def wall_instance_id(seed: str) -> str:
    return "W" + hashlib.sha256(f"a7-walls-v1:{seed}".encode()).hexdigest()[:8].upper()


def wall_rng(seed: str, step: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"a7-walls-v1:{seed}:{step}".encode()).hexdigest()[:16], 16))


@dataclass
class WallWorld(L.StepWorld):
    @property
    def instance(self) -> str:   # one step per instance: the id covers the seed AND the step
        return wall_instance_id(f"{self.seed}:{self.step}")

    @property
    def namespace(self) -> str:
        return f"A7.{self.instance}.{self.step}"


def _qnr(p: int) -> set[int]:
    sq = {(i * i) % p for i in range(p)}
    return {r for r in range(1, p) if r not in sq}


def _affine(M, c):
    return {"M": [list(r) for r in M], "c": list(c)}


# ----------------------------------------------------------------------------------------------- constructions

def make_wall(seed: str, step: str) -> WallWorld:
    r = wall_rng(seed, step)
    if step == "W1":
        while True:
            D, (a, b) = r.choice([(2, (3, 2)), (3, (2, 1)), (5, (9, 4)), (6, (5, 2))])
            p = r.choice([5, 7, 11, 13])
            if D % p == 0 or (2 * (a - 1)) % p == 0:
                continue
            starts = [(x, y) for x in range(-3, 4) for y in range(1, 4) if ((x * x - D * y * y) % p) in _qnr(p)]
            if not starts:
                continue
            st = r.choice(starts)
            break
        q0 = (st[0] * st[0] - D * st[1] * st[1]) % p
        moves = [f"⟨{a} * s.x + {D * b} * s.y, {b} * s.x + {a} * s.y⟩", f"⟨{a} * s.x - {D * b} * s.y, {a} * s.y - {b} * s.x⟩",
                 f"⟨s.x + {p}, s.y⟩", f"⟨s.x, s.y + {p}⟩"]
        aff = [_affine([[a, D * b], [b, a]], [0, 0]), _affine([[a, -D * b], [-b, a]], [0, 0]), _affine([[1, 0], [0, 1]], [p, 0]), _affine([[1, 0], [0, 1]], [0, p])]
        cases = " ∨ ".join(f"t % {p} = {i}" for i in range(p))
        alts = " | ".join("hr" for _ in range(p))
        hints = ["simp only [measure, start] at conserved",
                 f"have hsq : t * t % {p} = (t % {p}) * (t % {p}) % {p} := Int.mul_emod t t {p}",
                 f"have hr : {cases} := by omega"]
        return WallWorld(seed, step, {"D": D, "unit": [a, b], "p": p, "start": list(st), "start_residue": q0, "affine": aff, "family": "t0"},
                         ("x", "y"), moves, st, "∀ (t : Int), ¬ Reaches start ⟨t, 0⟩", f"(s.x * s.x - {D} * s.y * s.y) % {p}", "grind",
                         "intro t h", hints, f"rcases hr with {alts} <;> rw [hr] at hsq <;> omega",
                         f"on every target state ⟨t, 0⟩ it equals t·t mod {p}, a square residue, and {q0} is not a square mod {p}")
    if step == "W2":
        while True:
            al, be = L._nonzero(r, -3, 3), L._nonzero(r, -3, 3); k = r.choice([3, 5, 7])
            p1, q1, p2, q2 = (r.randint(-4, 4) for _ in range(4))
            if abs(p1 * q2 - p2 * q1) != k:
                continue
            g, d = (q1 % k, (-p1) % k) if (q1 % k, (-p1) % k) != (0, 0) else (q2 % k, (-p2) % k)
            if (g * p1 + d * q1) % k or (g * p2 + d * q2) % k:
                continue
            st = tuple(r.randint(-4, 4) for _ in range(3))
            opts = [(u, w) for u in range(-5, 6) for w in range(-5, 6) if (g * u + d * w) % k]
            u, w = r.choice(opts)
            t = (st[0] + u, st[1] + w, st[2] - (al * u + be * w))
            break
        r1, r2 = -(al * p1 + be * q1), -(al * p2 + be * q2)
        mv = lambda pp, qq, rr: f"⟨s.x {'+' if pp >= 0 else '-'} {abs(pp)}, s.y {'+' if qq >= 0 else '-'} {abs(qq)}, s.z {'+' if rr >= 0 else '-'} {abs(rr)}⟩"
        I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        aff = [_affine(I3, [p1, q1, r1]), _affine(I3, [p2, q2, r2]), _affine(I3, [-p1, -q1, -r1]), _affine(I3, [-p2, -q2, -r2])]
        return WallWorld(seed, step, {"alpha": al, "beta": be, "k": k, "m1": [p1, q1, r1], "m2": [p2, q2, r2], "gamma": g, "delta": d,
                                      "start": list(st), "target": list(t), "affine": aff, "family": "point"},
                         ("x", "y", "z"), [mv(p1, q1, r1), mv(p2, q2, r2), mv(-p1, -q1, -r1), mv(-p2, -q2, -r2)], st,
                         f"¬ Reaches start ⟨{L.lit(t[0])}, {L.lit(t[1])}, {L.lit(t[2])}⟩", f"({g} * s.x + {d} * s.y) % {k}", "omega", "intro h", [], "omega",
                         f"on the target state it equals {(g * t[0] + d * t[1]) % k}")
    if step == "W3":
        cx, cy, cz, cw = (r.randint(-4, 4) for _ in range(4))
        while True:
            X, Y, Z, W = (r.randint(-3, 3) for _ in range(4))
            if X * W - Y * Z <= -1:
                break
        st = (cx + X, cy + Y, cz + Z, cw + W)
        m1 = f"⟨s.x, s.y + s.x - {L.lit(cx)}, s.z, s.w + s.z - {L.lit(cz)}⟩"
        m2 = f"⟨s.x, s.y - s.x + {L.lit(cx)}, s.z, s.w - s.z + {L.lit(cz)}⟩"
        m3 = f"⟨s.x + s.y - {L.lit(cy)}, s.y, s.z + s.w - {L.lit(cw)}, s.w⟩"
        m4 = f"⟨s.x - s.y + {L.lit(cy)}, s.y, s.z - s.w + {L.lit(cw)}, s.w⟩"
        aff = [_affine([[1, 0, 0, 0], [1, 1, 0, 0], [0, 0, 1, 0], [0, 0, 1, 1]], [0, -cx, 0, -cz]),
               _affine([[1, 0, 0, 0], [-1, 1, 0, 0], [0, 0, 1, 0], [0, 0, -1, 1]], [0, cx, 0, cz]),
               _affine([[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]], [-cy, 0, -cw, 0]),
               _affine([[1, -1, 0, 0], [0, 1, 0, 0], [0, 0, 1, -1], [0, 0, 0, 1]], [cy, 0, cw, 0])]
        return WallWorld(seed, step, {"offsets": [cx, cy, cz, cw], "start": list(st), "start_measure": X * W - Y * Z, "affine": aff, "family": "hyperbolic_ab"},
                         ("x", "y", "z", "w"), [m1, m2, m3, m4], st,
                         f"∀ (a b : Int), ¬ Reaches start ⟨a + {L.lit(cx)}, b + {L.lit(cy)}, -b + {L.lit(cz)}, a + {L.lit(cw)}⟩",
                         f"(s.x - {L.lit(cx)}) * (s.w - {L.lit(cw)}) - (s.y - {L.lit(cy)}) * (s.z - {L.lit(cz)})", "grind", "intro a b h",
                         ["have na := Int.sq_nonneg a", "have nb := Int.sq_nonneg b"], "grind [measure, start]",
                         "on every target state it equals a·a + b·b, which is at least 0")
    if step == "W4":
        n = r.choice([11, 13, 17, 19]); c2 = r.randint(1, n - 1); inv = pow(c2, -1, n)
        while True:   # lattice index exactly n: Z^2 / L is cyclic of prime order, so the only invariants are mod n (no parity shortcut)
            p1, p2 = r.randint(1, 6), r.randint(1, 6)
            q1 = (-p1 * inv) % n + n * r.randint(0, 1); q2 = (-p2 * inv) % n + n * r.randint(0, 1)
            if abs(p1 * q2 - p2 * q1) == n:
                break
        st = (r.randint(-6, 6), r.randint(-6, 6))
        while True:
            t = (r.randint(-9, 9), r.randint(-9, 9))
            if (t[0] + c2 * t[1]) % n != (st[0] + c2 * st[1]) % n:
                break
        mv = lambda pp, qq: f"⟨s.x {'+' if pp >= 0 else '-'} {abs(pp)}, s.y {'+' if qq >= 0 else '-'} {abs(qq)}⟩"
        I2 = [[1, 0], [0, 1]]
        aff = [_affine(I2, [p1, q1]), _affine(I2, [p2, q2]), _affine(I2, [-p1, -q1]), _affine(I2, [-p2, -q2])]
        return WallWorld(seed, step, {"n": n, "c2": c2, "m1": [p1, q1], "m2": [p2, q2], "start": list(st), "target": list(t), "affine": aff, "family": "point"},
                         ("x", "y"), [mv(p1, q1), mv(p2, q2), mv(-p1, -q1), mv(-p2, -q2)], st,
                         f"¬ Reaches start ⟨{L.lit(t[0])}, {L.lit(t[1])}⟩", f"(s.x + {c2} * s.y) % {n}", "omega", "intro h", [], "omega",
                         f"on the target state it equals {(t[0] + c2 * t[1]) % n}")
    if step == "W5":
        p = r.choice([5, 7, 11])
        cx, cy, cz, cw = (r.randint(-3, 3) for _ in range(4))
        while True:
            X, Y, Z, W = (r.randint(-3, 3) for _ in range(4)); T = tuple(r.randint(-4, 4) for _ in range(4))
            q0, qt = (X * W - Y * Z) % p, (T[0] * T[3] - T[1] * T[2]) % p
            if q0 != qt and (X, Y, Z, W) != (0, 0, 0, 0):
                break
        st = (cx + X, cy + Y, cz + Z, cw + W); tg = (cx + T[0], cy + T[1], cz + T[2], cw + T[3])
        m1 = f"⟨s.x, s.y + s.x - {L.lit(cx)}, s.z, s.w + s.z - {L.lit(cz)}⟩"
        m2 = f"⟨s.x + s.y - {L.lit(cy)}, s.y, s.z + s.w - {L.lit(cw)}, s.w⟩"
        m3 = f"⟨s.x + {p}, s.y, s.z, s.w⟩"
        m4 = f"⟨s.x, s.y, s.z, s.w + {p}⟩"
        I4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        aff = [_affine([[1, 0, 0, 0], [1, 1, 0, 0], [0, 0, 1, 0], [0, 0, 1, 1]], [0, -cx, 0, -cz]),
               _affine([[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]], [-cy, 0, -cw, 0]),
               _affine(I4, [p, 0, 0, 0]), _affine(I4, [0, 0, 0, p])]
        return WallWorld(seed, step, {"offsets": [cx, cy, cz, cw], "p": p, "start": list(st), "target": list(tg), "start_residue": q0, "target_residue": qt,
                                      "affine": aff, "family": "point"},
                         ("x", "y", "z", "w"), [m1, m2, m3, m4], st,
                         f"¬ Reaches start ⟨{', '.join(L.lit(v) for v in tg)}⟩",
                         f"((s.x - {L.lit(cx)}) * (s.w - {L.lit(cw)}) - (s.y - {L.lit(cy)}) * (s.z - {L.lit(cz)})) % {p}", "grind", "intro h", [], "omega",
                         f"on the target state it equals {qt}, and on the start it equals {q0}")
    raise ValueError(step)


# ----------------------------------------------------------------------------------------------- certificate

def _targets(w: WallWorld, m: int) -> list[tuple[int, ...]]:
    """Enough target states to decide whether a linear form mod m separates the whole target family."""
    fam = w.params["family"]
    if fam == "point":
        return [tuple(w.params["target"])]
    if fam == "t0":
        return [(t, 0) for t in range(0, m * w.params["p"])]
    if fam == "hyperbolic_ab":
        cx, cy, cz, cw = w.params["offsets"]
        return [(a + cx, b + cy, -b + cz, a + cw) for a in range(m) for b in range(m)]
    raise ValueError(fam)


def _invariant_mod(l, aff, m) -> bool:
    d = len(l)
    for mv in aff:
        M, c = mv["M"], mv["c"]
        for j in range(d):   # coefficient of x_j in l·(M x + c) - l·x
            if (sum(l[i] * M[i][j] for i in range(d)) - l[j]) % m:
                return False
        if sum(l[i] * c[i] for i in range(d)) % m:
            return False
    return True


def _exact_linear_invariants(aff, d) -> list[list[Fraction]]:
    """Basis of {l : l·(M - I) = 0 and l·c = 0 for every move} over Q (Gaussian elimination)."""
    rows = []
    for mv in aff:
        M, c = mv["M"], mv["c"]
        for j in range(d):
            rows.append([Fraction(M[i][j] - (1 if i == j else 0)) for i in range(d)])
        rows.append([Fraction(c[i]) for i in range(d)])
    piv, R = [], [r[:] for r in rows]
    row = 0
    for col in range(d):
        k = next((i for i in range(row, len(R)) if R[i][col] != 0), None)
        if k is None:
            continue
        R[row], R[k] = R[k], R[row]
        R[row] = [v / R[row][col] for v in R[row]]
        for i in range(len(R)):
            if i != row and R[i][col] != 0:
                R[i] = [a - R[i][col] * b for a, b in zip(R[i], R[row])]
        piv.append(col); row += 1
    free = [c for c in range(d) if c not in piv]
    basis = []
    for f in free:
        v = [Fraction(0)] * d; v[f] = Fraction(1)
        for i, pc in enumerate(piv):
            v[pc] = -R[i][f]
        basis.append(v)
    return basis


def certify(w: WallWorld, max_mod: int | None = None) -> dict:
    """Search for shortcuts: exact linear invariants over Z that separate start from every target, and linear forms mod m
    (2 <= m <= max_mod) invariant under every move that separate start from every target. Intended moduli are reported
    separately (W2: multiples of k; W4: multiples of n)."""
    d = len(w.fields); aff = w.params["affine"]
    max_mod = max_mod or (30 if d <= 3 else 12)
    out = {"step": w.step, "exact_linear_invariants": [], "exact_separating": False, "modular_shortcuts": [], "max_mod": max_mod}
    basis = _exact_linear_invariants(aff, d)
    out["exact_linear_invariants"] = [[str(x) for x in v] for v in basis]
    for v in basis:
        vals_t = {sum(Fraction(t[i]) * v[i] for i in range(d)) for t in _targets(w, 3)}
        val_s = sum(Fraction(w.start[i]) * v[i] for i in range(d))
        if val_s not in vals_t and w.params["family"] == "point":
            out["exact_separating"] = True
    intended = {"W2": w.params.get("k"), "W4": w.params.get("n")}.get(w.step)
    for m in range(2, max_mod + 1):
        targets = _targets(w, m)
        for l in itertools.product(range(m), repeat=d):
            if not any(l) or not _invariant_mod(l, aff, m):
                continue
            s0 = sum(l[i] * w.start[i] for i in range(d)) % m
            if all(sum(l[i] * t[i] for i in range(d)) % m != s0 for t in targets):
                out["modular_shortcuts"].append({"m": m, "l": list(l), "intended_family": bool(intended and m % intended == 0)})
                break   # one witness per modulus is enough
    out["unintended_shortcuts"] = [s for s in out["modular_shortcuts"] if not s["intended_family"]]
    out["clean"] = (not out["exact_separating"]) and not out["unintended_shortcuts"]
    return out


# ----------------------------------------------------------------------------------------------- build / verify

def build_wall(seed: str, step: str, root: Path, *, phase: str) -> Path:
    """One step per instance: worlds/<root>/<W-instance>/<step>, same file layout as ladder_v1 (Mathlib env)."""
    w = make_wall(seed, step)
    base = Path(root) / w.instance
    if base.exists():
        raise FileExistsError(base)
    sham = L.SHAM_ASSET.read_text(encoding="utf-8")
    files = {"lakefile.toml": L.render_lakefile(w, ENV), "lean-toolchain": L.TOOLCHAIN + "\n", "World/Base.lean": L.render_base(w, ENV),
             "World/ChallengeEvaluation.lean": L.render_target(w), "Hidden/Oracle.lean": L.render_oracle(w),
             "Hidden/Reference.lean": L.render_reference_solution(w), "Sources/Sham.lean": sham, "Sources/Sham.md": L.md_source(sham),
             "Sources/Content.md": L.render_content_hint(w)}
    d = base / step
    for rel, text in files.items():
        p = d / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
    hashes = {rel: L.sha(text) for rel, text in files.items()}
    cert = certify(w)
    meta = {"schema_version": 1, "generator": "creative_machine.formal_routes.ladder_walls_v1", "generator_version": VERSION_BY_STEP.get(step, VERSION),
            "family": "a7_walls_v1", "instance": w.instance, "seed_label": seed, "step": step, "step_index": 0, "schema": SCHEMAS[step],
            "parameters": {k: v for k, v in w.params.items() if k != "affine"}, "fields": list(w.fields), "start": list(w.start),
            "roles": {"namespace": w.namespace, "statement": L.STATEMENT, "oracle_bridge": "oracle_bridge"},
            "public_files": ["lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeEvaluation.lean"],
            "source_files": {"ladder": None, "sham": "Sources/Sham.md", "skeleton": "Sources/Sham.md", "content": "Sources/Content.md"},
            "hidden_files": ["Hidden/Oracle.lean", "Hidden/Reference.lean"], "allowed_axioms": list(L.ALLOWED_AXIOMS),
            "toolchain": L.TOOLCHAIN, "env": ENV, "phase": phase, "eligible_for_main": False, "artifact_hashes": hashes,
            "statement_text": w.statement, "certificate": cert}
    (d / "metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "manifest.sha256").write_text("".join(f"{h}  {rel}\n" for rel, h in sorted(hashes.items())), encoding="utf-8")
    return d


def mutated_wall(w: WallWorld) -> tuple[WallWorld, str]:
    m = copy.deepcopy(w)
    if w.step == "W1":
        m.start = (1, 0); witness = "fun h => h 1 (Reaches.refl start)"
    elif w.step in ("W2", "W4", "W5"):
        m.statement = f"¬ Reaches start ⟨{', '.join(L.lit(v) for v in w.start)}⟩"; witness = "fun h => h (Reaches.refl start)"
    elif w.step == "W3":
        m.start = tuple(w.params["offsets"]); witness = "fun h => h 0 0 (Reaches.refl start)"
    else:
        raise ValueError(w.step)
    return m, witness


def mutation_check_wall(d: Path, *, lake: str = "lake", timeout: float = 900.0) -> dict:
    """(i) the reference proof is REJECTED on the mutated world; (ii) the witness proves the mutated statement false."""
    from .submission import STANDARD_LEAN_AXIOMS, attach_shared_lake, verify_evaluator_solution
    meta = L.load_step(d)
    w = make_wall(meta["seed_label"], meta["step"]); m, witness = mutated_wall(w)
    out = {"step": meta["step"], "reference_rejected": False, "witness_ok": False, "errors": []}
    with tempfile.TemporaryDirectory(prefix="a7-mutation-") as tmp:
        staged = Path(tmp) / "w"
        for rel, text in {"lakefile.toml": L.render_lakefile(m, ENV), "lean-toolchain": L.TOOLCHAIN + "\n", "World/Base.lean": L.render_base(m, ENV),
                          "World/ChallengeEvaluation.lean": L.render_target(m)}.items():
            p = staged / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
        attach_shared_lake(staged)
        (staged / "Solution.lean").write_text(L.render_reference_solution(m), encoding="utf-8")
        rep = verify_evaluator_solution(staged, namespace=m.namespace, statement=L.STATEMENT, bridge_supplied=False, timeout_s=timeout, allowed_axioms=STANDARD_LEAN_AXIOMS)
        out["reference_rejected"] = not rep.ok
        if rep.ok:
            out["errors"].append("reference proof still accepted on the mutated world")
        (staged / "Witness.lean").write_text(f"import World.ChallengeEvaluation\n\nnamespace {m.namespace}\n\n"
                                             f"theorem falsified : ¬ {L.STATEMENT} := {witness}\n\nend {m.namespace}\n\n#print axioms {m.namespace}.falsified\n", encoding="utf-8")
        subprocess.run([lake, "build", "World.ChallengeEvaluation"], cwd=staged, capture_output=True, text=True, timeout=timeout)
        wit = subprocess.run([lake, "env", "lean", "Witness.lean"], cwd=staged, capture_output=True, text=True, timeout=timeout)
        out["witness_ok"] = wit.returncode == 0 and "sorryAx" not in wit.stdout + wit.stderr
        if wit.returncode != 0:
            out["errors"].append("witness: " + (wit.stderr + wit.stdout).strip()[-800:])
    return out
