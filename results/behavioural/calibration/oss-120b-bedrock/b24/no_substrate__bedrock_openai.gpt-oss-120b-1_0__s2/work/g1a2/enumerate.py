import itertools
chars = list('ABCDEFGHJK')

def valid(code):
    # code is string length4
    # constraints from earlier guesses
    # 1) ABCD -> 0 matches
    if sum(c==g for c,g in zip(code, 'ABCD')) != 0:
        return False
    # 2) AAAA -> 1 match (exact position)
    if sum(c==g for c,g in zip(code, 'AAAA')) != 1:
        return False
    # 3) EFGH -> 0 matches
    if sum(c==g for c,g in zip(code, 'EFGH')) != 0:
        return False
    # 4) BBBB -> 0 matches
    if sum(c==g for c,g in zip(code, 'BBBB')) != 0:
        return False
    # 5) JJJJ -> 0 matches
    if sum(c==g for c,g in zip(code, 'JJJJ')) != 0:
        return False
    # 6) BACD -> 0 matches
    if sum(c==g for c,g in zip(code, 'BACD')) != 0:
        return False
    # 7) CCCC -> 1 match
    if sum(c==g for c,g in zip(code, 'CCCC')) != 1:
        return False
    # 8) ACDK -> 1 match
    if sum(c==g for c,g in zip(code, 'ACDK')) != 1:
        return False
    return True

candidates = [''.join(p) for p in itertools.product(chars, repeat=4) if valid(''.join(p))]
print('candidates count', len(candidates))
print(candidates)
with open('candidates.txt','w') as f:
    f.write('\n'.join(candidates))
