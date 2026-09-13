import itertools, json
letters = list('ABCDEFGHJK')

# constraints: list of (guess, score)
constraints = [ ('ABCD',0), ('EFGH',0), ('JJJJ',0) ]

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

candidates = []
for p in itertools.product(letters, repeat=4):
    code = ''.join(p)
    ok = True
    for guess, score in constraints:
        if feedback(code, guess) != score:
            ok = False
            break
    if ok:
        candidates.append(code)
print('Remaining candidates:', len(candidates))
print(candidates[:50])
