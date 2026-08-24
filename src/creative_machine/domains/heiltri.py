"""Heilbronn problem for triangles (AlphaEvolve repository problem 48; Friedman's heiltri).
Candidate: `construct(n)` -> n points on/inside the equilateral triangle with vertices
(0,0), (1,0), (0.5, sqrt(3)/2). Score (MAXIMIZE): the minimum area over all point triples,
normalized by the triangle's area (the unit-area convention). Records (n=11): 0.036 (SOTA)
-> > 0.0365 (AlphaEvolve 2025)."""
import itertools, math

S3 = math.sqrt(3.0)
EPS = 1e-9
TRI_AREA = S3 / 4.0

def _area(a, b, c):
    return abs(a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1])) / 2.0

def verify(points, n):
    if not isinstance(points, (list, tuple)) or len(points) != n:
        return {"ok": False, "error": f"need exactly {n} points"}
    pts = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            return {"ok": False, "error": "each point must be (x, y)"}
        x, y = float(p[0]), float(p[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            return {"ok": False, "error": "non-finite point"}
        if not (y >= -EPS and S3 * x <= S3 - y + EPS and y <= S3 * x + EPS):
            return {"ok": False, "error": f"point ({x:.4f}, {y:.4f}) outside the equilateral triangle"}
        pts.append((x, y))
    mn = min(_area(a, b, c) for a, b, c in itertools.combinations(pts, 3))
    return {"ok": True, "score": float(mn / TRI_AREA)}
