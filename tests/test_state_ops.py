import math

import numpy as np
import pytest

from creative_machine import state_ops as so

RNG = np.random.default_rng(7)
D = 24


def rand_h(*lead):
    return RNG.normal(size=(*lead, D)).astype(np.float64)


def test_unit_and_norms():
    h = rand_h(5)
    u = so.unit(h, np)
    assert np.allclose(np.linalg.norm(u, axis=-1), 1.0)
    assert np.allclose(so.norms(h, np)[:, 0], np.linalg.norm(h, axis=-1))


def test_orthonormal_pair_and_degenerate():
    u, v = rand_h(), rand_h()
    uh, wh = so.orthonormal_pair(u, v, np)
    assert np.allclose(np.linalg.norm(uh), 1.0) and np.allclose(np.linalg.norm(wh), 1.0)
    assert abs(float(uh @ wh)) < 1e-10
    with pytest.raises(ValueError):
        so.orthonormal_pair(u, 3.0 * u, np)


def test_translate():
    h, v = rand_h(3), so.unit(rand_h(), np)
    assert np.allclose(so.translate(h, v, 2.5), h + 2.5 * v)


def test_rotor_matches_matrix_exponential():
    scipy_linalg = pytest.importorskip("scipy.linalg", reason="expm verification is local-only (CI installs no scipy)")
    expm = scipy_linalg.expm

    u, v = rand_h(), rand_h()
    uh, wh = so.orthonormal_pair(u, v, np)
    theta = 0.83
    G = np.outer(wh, uh) - np.outer(uh, wh)
    R = expm(theta * G)
    h = rand_h(6)
    assert np.allclose(so.rotate(h, uh, wh, theta, np), h @ R.T, atol=1e-10)


def test_rotor_geometry():
    uh, wh = so.orthonormal_pair(rand_h(), rand_h(), np)
    # u rotated by pi/2 lands on w; norms preserved; off-plane fixed
    assert np.allclose(so.rotate(uh, uh, wh, math.pi / 2, np), wh, atol=1e-10)
    h = rand_h(8)
    r = so.rotate(h, uh, wh, 1.2, np)
    assert np.allclose(np.linalg.norm(r, axis=-1), np.linalg.norm(h, axis=-1))
    perp = h - np.outer(h @ uh, uh) - np.outer(h @ wh, wh)
    r_perp = r - np.outer(r @ uh, uh) - np.outer(r @ wh, wh)
    assert np.allclose(perp, r_perp, atol=1e-10)
    # composition on the plane: R(a) then R(b) == R(a+b)
    ab = so.rotate(so.rotate(h, uh, wh, 0.4, np), uh, wh, 0.9, np)
    assert np.allclose(ab, so.rotate(h, uh, wh, 1.3, np), atol=1e-10)


def test_project_out_and_dilate():
    B = so.orthonormalize(rand_h(3), np)
    h = rand_h(5)
    p = so.project_out(h, B, np)
    assert np.allclose(p @ B.T, 0.0, atol=1e-10)          # component erased
    assert np.allclose(so.project_out(p, B, np), p)        # idempotent
    d = so.dilate(h, B, 2.0, np)
    assert np.allclose(d @ B.T, 2.0 * (h @ B.T))           # in-subspace doubled
    assert np.allclose(d - (d @ B.T) @ B, h - (h @ B.T) @ B)  # complement fixed


def test_orthonormalize_drops_dependent_rows():
    r = rand_h()
    rows = np.stack([r, 2.0 * r, rand_h()])
    B = so.orthonormalize(rows, np)
    assert B.shape[0] == 2
    assert np.allclose(B @ B.T, np.eye(2), atol=1e-10)


def test_manifold_noise_stays_in_subspace():
    B = so.orthonormalize(rand_h(4), np)
    h = rand_h()
    z = RNG.normal(size=4)
    n = so.manifold_noise(h, B, z, 0.7)
    delta = n - h
    # the delta lies entirely in span(B)
    assert np.allclose(delta, (delta @ B.T) @ B, atol=1e-10)


def test_repel_unit_step_away_from_mean():
    h, mu = rand_h(), rand_h()
    r = so.repel(h, mu, 0.5, np)
    d = h - mu
    assert np.allclose(r - h, 0.5 * d / np.linalg.norm(d))
    # moving away: distance to mu strictly grows
    assert np.linalg.norm(r - mu) > np.linalg.norm(h - mu)


def test_anchor_restores_premise_coordinate():
    p = so.unit(rand_h(), np)
    h = rand_h(4)
    target = so.coord(h, p, np)                    # pre-op coordinate
    pushed = so.repel(h, rand_h(), 3.0, np)        # arbitrary op
    anchored = so.restore_coord(pushed, p, target, np)
    assert np.allclose(so.coord(anchored, p, np), target, atol=1e-10)


def test_renorm_hits_target_shell():
    h = rand_h(4)
    tgt = so.norms(h, np)
    blown = h * 17.0
    back = so.renorm(blown, tgt, np)
    assert np.allclose(so.norms(back, np), tgt)


def test_schedule_parse_and_fire():
    s = so.Schedule.parse("::")
    assert s.active(1) and s.active(999)
    s = so.Schedule.parse("97::")
    assert not s.active(96) and s.active(97) and s.active(98)
    s = so.Schedule.parse("1:481:32")
    fires = [t for t in range(1, 600) if s.active(t)]
    assert fires[0] == 1 and fires[-1] == 449 and len(fires) == 15
    assert so.Schedule.parse("5:10:2").describe() == "5:10:2"
    with pytest.raises(ValueError):
        so.Schedule(start=0)


def test_batched_shapes_broadcast():
    # (B, T, d) states against (d,) directions — the generation-loop shape
    h = rand_h(2, 3)
    v = so.unit(rand_h(), np)
    uh, wh = so.orthonormal_pair(rand_h(), rand_h(), np)
    for out in (so.translate(h, v, 1.0), so.rotate(h, uh, wh, 0.3, np),
                so.repel(h, rand_h(), 1.0, np), so.renorm(h, 1.0, np)):
        assert out.shape == h.shape
