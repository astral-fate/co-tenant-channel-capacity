import itertools
letters = list('CDEFGHJK')  # allowed letters (A,B excluded)

def matches(code, guess):
    return sum(c==g for c,g in zip(code, guess))

candidates = []
for code in itertools.product(letters, repeat=4):
    code = ''.join(code)
    # constraints
    if code[0] == 'C':
        continue  # from CAAA 0 correct
    if matches(code, 'CCCC') != 1:
        continue
    if matches(code, 'DDDD') != 1:
        continue
    if matches(code, 'EEEE') != 1:
        continue
    if matches(code, 'DCEF') != 2:
        continue
    candidates.append(code)
print('candidates', len(candidates))
print(candidates)
