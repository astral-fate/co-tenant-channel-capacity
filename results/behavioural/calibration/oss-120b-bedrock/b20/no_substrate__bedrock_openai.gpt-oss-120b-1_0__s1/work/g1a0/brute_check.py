import itertools
allowed = list('ABCDEFGHJK')
observations = [
    ('AAAA',0),('BAAA',1),('BBBB',1),('CCCC',0),('BDDD',1),('ECCC',0),('EEEE',0),('FGHJ',0),('DDDD',0),('BFGK',2),('BHGK',2),('BJGF',1)
]

def matches(cand, guess, correct):
    return sum(c==g for c,g in zip(cand, guess)) == correct

candidates = []
for p in itertools.product(allowed, repeat=4):
    cand = ''.join(p)
    ok = True
    for guess, corr in observations:
        if not matches(cand, guess, corr):
            ok=False
            break
    if ok:
        candidates.append(cand)
print('candidates count', len(candidates))
print(candidates)
