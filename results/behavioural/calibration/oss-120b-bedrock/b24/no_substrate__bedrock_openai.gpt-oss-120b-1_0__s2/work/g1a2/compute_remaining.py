import itertools
chars = list('ABCDEFGHJK')

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

constraints = [
    ('ABCD', 0),
    ('AAAA', 1),
    ('EFGH', 0),
    ('BBBB', 0),
    ('JJJJ', 0),
    ('BACD', 0),
    ('CCCC', 1),
    ('ACDK', 1)
]

candidates = []
for p in itertools.product(chars, repeat=4):
    code = ''.join(p)
    ok = True
    for guess, cnt in constraints:
        if feedback(code, guess) != cnt:
            ok = False
            break
    if ok:
        candidates.append(code)
print('Remaining candidates:', len(candidates))
print(candidates)
with open('candidates.txt','w') as f:
    f.write('\n'.join(candidates))
