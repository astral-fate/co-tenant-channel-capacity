import itertools
letters = list('ABCDEFGH')  # J,K excluded
# constraints as functions

def matches(code):
    # code is string length 4
    # ABCD -> 0
    if sum(c==g for c,g in zip(code, 'ABCD')) != 0:
        return False
    # EFGH ->0
    if sum(c==g for c,g in zip(code, 'EFGH')) != 0:
        return False
    # JJJJ ->0 (J not in allowed set anyway)
    # KKKK ->0 (K not allowed)
    # AAAA ->1
    if sum(c==g for c,g in zip(code, 'AAAA')) != 1:
        return False
    return True

candidates = []
for p in itertools.product(letters, repeat=4):
    code = ''.join(p)
    if matches(code):
        candidates.append(code)
print('candidates', len(candidates))
print(candidates)
