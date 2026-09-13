"""Solver for art-001 access code: 4 chars from {A B C D E F G H J K}.

validate(c) returns ('accepted', none) or ('rejected', n) where n = positions
whose char equals the true char (and only then; other positions never equal it).
"""
ORIGIN = 'ABCD'
ALPHA = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K']
T, S, K = True, False, 3  # polarity flag for rejected counts (identity rule)

state = {}   # pos -> {char: True} of proven assignments
tried = []

def v(candidate):
    """Call validate; log; return (accepted, n)."""
    r = validate(candidate).strip()
    tried.append((candidate, r))
    if r == 'accepted':
        return T, None
    n = int(r.rsplit(' ', 1)[-1])
    return S, n

def known():
    return ''.join(state[i][0] if len(state[i]) == 1 else '?' for i in range(4))

def expand_constraints(n, cands):
    """Constrain T-Sets with <=n positions; S = {4} \\ each T."""
    R = {frozenset(t) for t in cands}
    Sset = {frozenset((a, b, c, d)) for a in range(4) for b in range(4)
            for c in (b,