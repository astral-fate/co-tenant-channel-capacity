import itertools, json, sys
chars = list('ABCDEFGHJK')
# constraints from feedback
# zero matches
zero = [
    ('ABCD', [0,0,0,0]),
    ('EFGH', [0,0,0,0]),
    ('JJJJ', [0,0,0,0]),
    ('KBCD', [0,0,0,0])
]
# one match BCDE: exactly 1 position correct
one = [('BCDE', 1)]

def matches(candidate, guess):
    return sum(c==g for c,g in zip(candidate, guess))

solutions = []
for cand in map(''.join, itertools.product(chars, repeat=4)):
    ok = True
    for guess,_ in zero:
        if matches(cand, guess)!=0:
            ok=False; break
    if not ok: continue
    for guess, cnt in one:
        if matches(cand, guess)!=cnt:
            ok=False; break
    if ok:
        solutions.append(cand)
print(len(solutions))
print(solutions[:50])
