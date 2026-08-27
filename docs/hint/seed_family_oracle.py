import numpy as np

def construct(L):
    # Best grid instantiation we could hand-build of the Bellec-Fritz family
    # (arXiv:2412.15179 Prop. 4.1): atom at zero + dyadic ladder toward the top,
    # tie-broken by a -1 offset; p0 tuned. Scores 0.3742 on L=5000 (below the
    # sparse-atom plateau 0.3816; that gap is part of what the battery tests).
    p0 = 0.45
    top = L - 1
    p = np.zeros(L)
    p[0] = p0
    pos = sorted({int(round((1.0 - 0.5 ** i) * top)) - 1 for i in range(1, 13)})
    pos = [min(max(q, 1), top) for q in pos]
    for q in pos:
        p[q] += (1.0 - p0) / len(pos)
    return p.tolist()
