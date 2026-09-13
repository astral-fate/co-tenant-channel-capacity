import itertools
letters = list('ACDEFGH')  # allowed after eliminating B,J,K
# constraints per position from 0 matches
bad_pos = {
    0: set(['A','E']),
    1: set(['F']),
    2: set(['C','G']),
    3: set(['D','H']),
}

def valid(code):
    # exactly one A
    if code.count('A') != 1:
        return False
    # per position restrictions
    for i,ch in enumerate(code):
        if ch in bad_pos[i]:
            return False
    return True

candidates = [''.join(p) for p in itertools.product(letters, repeat=4) if valid(''.join(p))]
print('candidates count', len(candidates))
print(candidates)
