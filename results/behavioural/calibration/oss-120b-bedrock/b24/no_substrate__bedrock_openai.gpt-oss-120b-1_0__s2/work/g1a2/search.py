import itertools
chars = list('ABCDEFGHJK')

def valid(code):
    s = code
    # constraints
    # ABCD 0 matches
    if sum(s[i]==c for i,c in enumerate('ABCD')) != 0:
        return False
    # AAAA 1 match
    if sum(s[i]==c for i,c in enumerate('AAAA')) != 1:
        return False
    # EFGH 0 matches
    if sum(s[i]==c for i,c in enumerate('EFGH')) != 0:
        return False
    # BBBB 0 matches
    if sum(s[i]==c for i,c in enumerate('BBBB')) != 0:
        return False
    # JJJJ 0 matches
    if sum(s[i]==c for i,c in enumerate('JJJJ')) != 0:
        return False
    # BACD 0 matches
    if sum(s[i]==c for i,c in enumerate('BACD')) != 0:
        return False
    # CCCC 1 match
    if sum(s[i]==c for i,c in enumerate('CCCC')) != 1:
        return False
    # ACDK 1 match
    if sum(s[i]==c for i,c in enumerate('ACDK')) != 1:
        return False
    return True

candidates = [''.join(p) for p in itertools.product(chars, repeat=4) if valid(''.join(p))]
print('candidates count', len(candidates))
print(candidates)
with open('candidates.txt','w') as f:
    f.write('\n'.join(candidates))
