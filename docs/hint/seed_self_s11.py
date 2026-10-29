import numpy as np

def construct(L):
    # Initialize probability mass function
    p = np.zeros(L)
    
    # Place substantial mass at 0
    p[0] = 0.55
    
    # Remaining mass to distribute
    remaining = 1.0 - p[0]
    
    # Use geometric distribution with r = 0.5 to place atoms
    # towards L-1, but use a different approach for better tail coverage
    r = 0.5
    cumulative_mass = p[0]
    
    # Place atoms at geometrically increasing positions
    i = 1
    while True:
        # Use a modified geometric distribution
        pos = int(L * (1 - r**i))
        if pos <= 0 or pos >= L:
            break
            
        # Mass for this atom
        mass = remaining * (1 - r) * (r**(i-1))
        if cumulative_mass + mass > 1.0:
            mass = 1.0 - cumulative_mass
            
        p[pos] = mass
        cumulative_mass += mass
        
        if mass < 1e-10 or cumulative_mass > 0.9999:
            break
        i += 1
    
    # Add small atoms at positions near L-1 to improve tail behavior
    p[L-1] += 0.005
    p[L-2] += 0.003
    p[L-3] += 0.002
    
    # Normalize
    p = p / np.sum(p)
    
    return p.tolist()
