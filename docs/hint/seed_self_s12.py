import numpy as np

def construct(L):
    # Initialize probability mass function
    p = np.zeros(L)
    
    # Place substantial mass at 0
    p[0] = 0.34
    
    # Remaining mass to distribute
    remaining_mass = 1.0 - p[0]
    
    # Use geometric decay toward L-1 with r = 0.92
    r = 0.92
    
    # Place atoms at geometrically spaced positions
    total_atoms = 50
    
    for i in range(1, total_atoms):
        pos = int((1 - r**i) * (L - 1))
        if pos >= L:
            break
        # Assign portion of remaining mass to this position
        p[pos] = remaining_mass * (1 - r) * r**(i-1)
    
    # Normalize to ensure sum equals 1
    p = p / np.sum(p)
    
    return p.tolist()
