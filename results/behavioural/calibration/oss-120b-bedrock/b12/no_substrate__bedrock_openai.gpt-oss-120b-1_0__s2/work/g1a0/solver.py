import itertools, json, sys
allowed = ['B','D','E','F','G','H','J','K']
constraints = [
    ('AAAA',0),
    ('BBBB',1),
    ('CCCC',0),
    ('BDDD',1),
    ('BDFF',2),
]
solutions = []
for combo in itertools.product(allowed, repeat=4):
    code = ''.join(combo)
    ok = True
    for cand, score in constraints:
        cnt = sum(1 for a,b in zip(code,cand) if a==b)
        if cnt != score:
            ok=False
            break
    if ok:
        solutions.append(code)
print('solutions', solutions)
