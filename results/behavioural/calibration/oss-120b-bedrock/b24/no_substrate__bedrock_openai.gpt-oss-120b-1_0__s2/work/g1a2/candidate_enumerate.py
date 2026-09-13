import itertools
chars = list('ABCDEFGHJK')

def valid(code):
    # constraints
    # 0 matches with ABCD
    if sum(c==g for c,g in zip(code, 'ABCD')) != 0:
        return False
    # 1 match with AAAA
    if sum(c=='A' for c in code) != 1:
        return False
    # 0 matches with EFGH
    if sum(c==g for c,g in zip(code, 'EFGH')) != 0:
        return False
    # 0 matches with BBBB
    if sum(c=='B' for c in code) != 0:
        return False
    # 0 matches with JJJJ
    if sum(c=='J' for c in code) != 0:
        return False
    return True

candidates = [''.join(p) for p in itertools.product(chars, repeat=4) if valid(''.join(p))]
print(len(candidates))
print(candidates[:50])
with open('candidates.txt','w') as f:
    f.write('\n'.join(candidates))
