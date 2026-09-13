import itertools
letters = list('ABCDEFGHJK')
# constraints
not_allowed = {
    0: set(['A','E','J','K']),
    1: set(['B','F','J','K']),
    2: set(['C','G','J','K']),
    3: set(['D','H','J','K'])
}

def valid(code):
    # code string len4
    # check per position
    for i,ch in enumerate(code):
        if ch in not_allowed[i]:
            return False
    # AAAA score =1
    a_score = sum(ch=='A' for ch in code)
    if a_score != 1:
        return False
    return True

candidates = []
for p in itertools.product(letters, repeat=4):
    code = ''.join(p)
    if valid(code):
        candidates.append(code)
print('candidates count', len(candidates))
print(candidates)
"""
"""
