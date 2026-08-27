import numpy as np

def construct(L):
    # A deliberately crude member of the Bellec-Fritz family: an atom at zero
    # plus a few atoms accumulating dyadically toward the top. Wrong zero-mass
    # and far too few levels; nothing optimized.
    p = np.zeros(L)
    top = L - 1
    p[0] = 0.25
    for i in (1, 2, 3):
        p[int(round((1.0 - 2.0 ** (-i)) * top))] += 0.75 / 3
    return p.tolist()
