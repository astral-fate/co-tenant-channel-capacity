import itertools
allowed = ['A','B','C','D','E','F','G','H','J','K']
# constraints: list of (guess, correct count)
constraints = [
    ('AAAA',0),
    ('BBBB',1),
    ('BAAA',1),
    ('BCCC',1),
    ('DDDD',0),
    ('BEAA',1),
    ('BFFF',2),
    ('BFEE',1),
    ('BEFG',2),
    ('BGFH',2),
]

def score(g, s):
    return sum(gi==si for gi,si in zip(g,s))

solutions = []
for p in itertools.product(allowed, repeat=4):
    cand = ''.join(p)
    ok = True
    for guess, cnt in constraints:
        if score(guess, cand)!=cnt:
            ok=False
            break
    if ok:
        solutions.append(cand)
print('solutions count', len(solutions))
print(solutions[:50])
