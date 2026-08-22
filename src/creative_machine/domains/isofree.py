"""Isosceles-free subsets of the n x n grid (AlphaEvolve repository problem 59).
Candidate: `construct(n)` -> list of distinct integer points (x, y) with 0 <= x, y < n such that no three
distinct points a, b, c have dist(a, b) == dist(b, c) (no isosceles triangle, degenerate ones included).
Score (MAXIMIZE): the number of points. Records: best known 110 (n = 64) before; AlphaEvolve 112 (n = 64), 164 (n = 100)."""

def verify(points, n):
    if not isinstance(points, (list, tuple)) or len(points) < 1:
        return {"ok": False, "error": "need a non-empty list of points"}
    pts = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            return {"ok": False, "error": "each point must be (x, y)"}
        x, y = p
        if not (isinstance(x, int) and isinstance(y, int)) or isinstance(x, bool) or isinstance(y, bool):
            return {"ok": False, "error": "coordinates must be ints"}
        if not (0 <= x < n and 0 <= y < n):
            return {"ok": False, "error": "point outside the grid"}
        pts.append((x, y))
    if len(set(pts)) != len(pts):
        return {"ok": False, "error": "duplicate points"}
    for b in pts:
        seen = set()
        for a in pts:
            if a is b or a == b:
                continue
            d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
            if d in seen:
                return {"ok": False, "error": f"isosceles configuration at apex {b}"}
            seen.add(d)
    return {"ok": True, "score": float(len(pts))}
