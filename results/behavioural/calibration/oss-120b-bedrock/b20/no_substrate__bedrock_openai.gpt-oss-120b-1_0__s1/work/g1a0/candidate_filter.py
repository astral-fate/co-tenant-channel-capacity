import itertools
allowed = list('ABCDEFGHJK')
# known constraints from earlier deduced
candidates = []
for p2 in ['F','H','J','K']:
    for p3 in ['F','G','J','K']:
        for p4 in ['F','G','H','K']:
            cand = 'B' + p2 + p3 + p4
            candidates.append(cand)

# observations list
obs = [
    ('AAAA',0),
    ('BAAA',1),
    ('BBBB',1),
    ('CCCC',0),
    ('BDDD',1),
    ('ECCC',0),
    ('EEEE',0),
    ('FGHJ',0),
    ('DDDD',0),
    ('BFGK',2),
    ('BHGK',2),
    ('BJGF',1),
]

def matches(cand, guess, correct):
    return sum(c==g for c,g in zip(cand, guess)) == correct

valid = []
for cand in candidates:
    ok=True
    for guess, corr in obs:
        if not matches(cand, guess, corr):
            ok=False
            break
    if ok:
        valid.append(cand)
print(len(valid))
print(valid)
