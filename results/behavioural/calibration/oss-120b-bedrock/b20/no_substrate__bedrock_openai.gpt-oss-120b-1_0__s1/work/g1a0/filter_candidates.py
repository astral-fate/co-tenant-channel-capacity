import itertools
allowed = list('ABCDEFGHJK')
# constraints from observations
observations = [
    ('AAAA', 0),
    ('BAAA', 1),
    ('BBBB', 1),
    ('CCCC', 0),
    ('BDDD', 1),
    ('ECCC', 0),
    ('EEEE', 0),
    ('FGHJ', 0),
    ('DDDD', 0),
]

def matches(candidate, guess, correct):
    return sum(c==g for c,g in zip(candidate, guess)) == correct

candidates = []
for p in itertools.product(allowed, repeat=4):
    cand = ''.join(p)
    ok = True
    for guess, correct in observations:
        if not matches(cand, guess, correct):
            ok = False
            break
    if ok:
        candidates.append(cand)
print('possible candidates count:', len(candidates))
print(candidates)
