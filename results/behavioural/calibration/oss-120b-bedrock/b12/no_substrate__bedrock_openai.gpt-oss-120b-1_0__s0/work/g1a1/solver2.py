import itertools
letters = list('CDEFGHJK')

def matches(code, guess):
    return sum(c==g for c,g in zip(code, guess))

candidates = []
for code in itertools.product(letters, repeat=4):
    code = ''.join(code)
    # constraint: position1 != 'C' (from CAAA 0 correct)
    if code[0] == 'C':
        continue
    # CCCC exactly 1 correct
    if matches(code, 'CCCC') != 1:
        continue
    # DDDD exactly 1 correct
    if matches(code, 'DDDD') != 1:
        continue
    # EEEE exactly 1 correct
    if matches(code, 'EEEE') != 1:
        continue
    # DCEF exactly 2 correct
    if matches(code, 'DCEF') != 2:
        continue
    candidates.append(code)
print('candidates', len(candidates))
print(candidates)
