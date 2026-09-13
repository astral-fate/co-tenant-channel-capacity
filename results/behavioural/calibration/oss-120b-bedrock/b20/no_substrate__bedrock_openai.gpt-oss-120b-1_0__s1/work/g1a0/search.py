import itertools, json

allowed = list('ABCDEFGHJK')

def consistent(code):
    # constraints from guesses
    # 1 AAAA -> 0 correct: positions not A
    if any(c=='A' for c in code):
        return False
    # 2 BAAA -> 1 correct: pos1 must be B, others not A
    if code[0] != 'B':
        return False
    if code[1] == 'A' or code[2]=='A' or code[3]=='A':
        return False
    # 3 BBBB -> 1 correct: only pos1 B, others not B
    if code[1]=='B' or code[2]=='B' or code[3]=='B':
        return False
    # 4 CCCC ->0 correct: no C at any position
    if any(c=='C' for c in code):
        return False
    # 5 BDDD ->1 correct: pos1 B, others not D
    if code[1]=='D' or code[2]=='D' or code[3]=='D':
        return False
    # 6 ECCC ->0 correct: positions:1 E,2 C,3 C,4 C must not match secret
    # Since we already know pos2-4 not C, this just says pos1 != E
    if code[0]=='E':
        return False
    # 7 EEEE ->0 correct: positions all E cannot match, i.e., none of pos i equal E
    if any(code[i]=='E' for i in range(4)):
        return False
    # 8 FGHJ ->0 correct: pos1 !=F, pos2!=G, pos3!=H, pos4!=J
    if code[0]=='F' or code[1]=='G' or code[2]=='H' or code[3]=='J':
        return False
    # 9 DDDD ->0 correct: already covered D not in pos2-4, also pos1 not D (it's B), okay.
    return True

cands = [''.join(p) for p in itertools.product(allowed, repeat=4) if consistent(''.join(p))]
print('candidates', len(cands))
print(cands[:50])
