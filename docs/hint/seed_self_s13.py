import numpy as np

def construct(L):
    # Target: maximize P[X1 + X2 + X3 < 2*X4]
    # Improved construction using multiple carefully placed atoms
    
    p = np.zeros(L)
    
    # Place a large mass at 0
    p[0] = 0.55
    
    # Remaining mass
    remaining = 1.0 - p[0]
    
    # Use a geometric distribution but with a more refined approach
    # Place atoms at positions: 0, 1, floor((L-1)*r^i) for i = 0,1,2,...
    # But use a ratio that gives better coverage
    
    r = 0.4
    cumulative = p[0]
    i = 0
    
    # Place early atoms more densely to improve coverage
    for i in range(1, 20):
        pos = int((1 - r**i) * (L - 1))
        if pos <= 0 or pos >= L:
            break
        mass = remaining * (r**(i-1)) * (1 - r)
        if pos < L:
            p[pos] += mass
        cumulative += mass
    
    # Distribute the rest of the mass more evenly to cover the tail
    # Add one more atom at L-1 to ensure full coverage
    p[L-1] += remaining - cumulative + p[0]
    
    # Normalize
    p = p / np.sum(p)
    return p.tolist()
