"""State-space operators on the residual stream (phase 5).

Every operator is a rank-1/rank-2 update built from stored unit vectors —
O(d) per position, never a d x d matrix. The rotor uses the closed
(Rodrigues) form of exp(theta * (w u^T - u w^T)) on the plane spanned by an
orthonormal pair {u, w}, so no matrix exponential is ever materialized.

Backend-agnostic: every function takes ``xp`` (numpy or mlx.core). States
``h`` have shape (..., d); directions are (d,). Randomness stays with the
caller (pass the noise sample in), so runs are reproducible under either
backend.

Conventions: directions are unit-normalized by the caller (helpers below);
``theta`` in radians; guards (norm shell, anchor) are separate composable
functions applied after an operator.
"""

from __future__ import annotations


def unit(v, xp, eps: float = 1e-8):
    """v / ||v|| along the last axis (eps-guarded)."""
    n = xp.sqrt(xp.sum(v * v, axis=-1, keepdims=True))
    return v / (n + eps)


def norms(h, xp):
    """||h|| along the last axis, keepdims — shape (..., 1)."""
    return xp.sqrt(xp.sum(h * h, axis=-1, keepdims=True))


def coord(h, d, xp):
    """Coordinate of h along direction d: (h . d), keepdims — shape (..., 1)."""
    return xp.sum(h * d, axis=-1, keepdims=True)


def orthonormal_pair(u, v, xp, eps: float = 1e-8):
    """Gram-Schmidt: returns (u_hat, w_hat) spanning plane(u, v) with
    u_hat . w_hat = 0. Exact normalization (no additive eps: the rotor needs
    the pair orthonormal to machine precision). Raises on degenerate input."""
    un = float(xp.sqrt(xp.sum(u * u)))
    if un < eps:
        raise ValueError("rotor plane is degenerate: u is null")
    u_hat = u / un
    w = v - xp.sum(v * u_hat, axis=-1, keepdims=True) * u_hat
    wn = float(xp.sqrt(xp.sum(w * w)))
    if wn < eps:
        raise ValueError("rotor plane is degenerate: v is parallel to u")
    return u_hat, w / wn


def orthonormalize(rows, xp, eps: float = 1e-8):
    """Gram-Schmidt over the rows of a (k, d) matrix; drops near-null rows.
    Returns a (k', d) matrix with orthonormal rows (k' <= k)."""
    out = []
    for i in range(rows.shape[0]):
        r = rows[i]
        for q in out:
            r = r - xp.sum(r * q, axis=-1, keepdims=True) * q
        n = float(xp.sqrt(xp.sum(r * r)))
        if n > eps:
            out.append(r / n)
    return xp.stack(out) if out else rows[:0]


# ---------------------------------------------------------------- operators

def translate(h, v, alpha: float):
    """h + alpha * v — the interruption transposed to the state (essay op 1)."""
    return h + alpha * v


def rotate(h, u_hat, w_hat, theta: float, xp):
    """Apply R(theta) = exp(theta (w u^T - u w^T)) to h in closed form:
    h + sin(t)((u.h) w - (w.h) u) + (cos(t) - 1)((u.h) u + (w.h) w).
    {u_hat, w_hat} must be orthonormal (see orthonormal_pair). Rotates the
    in-plane component of h by theta (u toward w); the orthogonal complement
    is untouched, so norms are preserved exactly (essay op 2)."""
    import math

    cu = coord(h, u_hat, xp)
    cw = coord(h, w_hat, xp)
    s, c = math.sin(theta), math.cos(theta)
    return h + s * (cu * w_hat - cw * u_hat) + (c - 1.0) * (cu * u_hat + cw * w_hat)


def project_out(h, basis, xp):
    """Erase the subspace spanned by the orthonormal rows of ``basis`` (k, d):
    h - (h B^T) B — forgetting a dimension of thought (essay op 3)."""
    return h - (h @ basis.T) @ basis


def dilate(h, basis, gamma: float, xp):
    """Scale the in-subspace component by gamma (sharpen > 1, flatten < 1):
    h + (gamma - 1) (h B^T) B (essay op 3)."""
    return h + (gamma - 1.0) * ((h @ basis.T) @ basis)


def manifold_noise(h, basis, z, sigma: float):
    """Tremor along the manifold: h + sigma * (z B), with z the caller's
    (..., k) noise sample and ``basis`` (k, d) the trajectory's principal
    subspace (essay op 5). Noise never leaves span(basis)."""
    return h + sigma * (z @ basis)


def repel(h, mu, beta: float, xp, eps: float = 1e-8):
    """Push away from a running mean: h + beta * (h - mu)/||h - mu|| —
    continuous, deep habituation (essay op 6; the stage of H4)."""
    d = h - mu
    return h + beta * (d / (norms(d, xp) + eps))


# ------------------------------------------------------------------ guards

def restore_coord(h, p_hat, target, xp):
    """Anchor: pin the coordinate along unit direction p_hat back to
    ``target`` (shape (..., 1) or scalar): h + (target - h.p) p."""
    return h + (target - coord(h, p_hat, xp)) * p_hat


def renorm(h, target, xp, eps: float = 1e-8):
    """Norm-shell guard: rescale h so ||h|| equals ``target`` (shape (..., 1)
    or scalar) — stay on the typical shell (essay: banda de norma)."""
    return h * (target / (norms(h, xp) + eps))


# --------------------------------------------------------------- schedules

class Schedule:
    """Which generation steps an operator fires on: [start, stop) every k.
    stop=0 means no upper bound. Steps are 1-based (first generated token)."""

    def __init__(self, start: int = 1, stop: int = 0, every: int = 1):
        if start < 1 or every < 1:
            raise ValueError("start and every must be >= 1")
        self.start, self.stop, self.every = start, stop, every

    def active(self, step: int) -> bool:
        if step < self.start or (self.stop and step >= self.stop):
            return False
        return (step - self.start) % self.every == 0

    @classmethod
    def parse(cls, spec: str) -> "Schedule":
        """'start:stop:every' with blanks defaulting (e.g. '::' = always,
        '97::' = from step 97 on, '1:481:32' = first 480 steps, every 32nd)."""
        parts = (spec.split(":") + ["", "", ""])[:3]
        return cls(int(parts[0] or 1), int(parts[1] or 0), int(parts[2] or 1))

    def describe(self) -> str:
        return f"{self.start}:{self.stop or ''}:{self.every}"
