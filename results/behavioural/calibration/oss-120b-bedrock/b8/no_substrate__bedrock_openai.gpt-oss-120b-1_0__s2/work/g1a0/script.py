import itertools, sys
alphabet = list('AB CDEFGHJK'.replace(' ',''))
# Actually allowed chars: A B C D E F G H J K
alphabet = ['A','B','C','D','E','F','G','H','J','K']
solutions=[]
for p in itertools.product(alphabet, repeat=4):
    p1,p2,p3,p4 = p
    # constraints
    if p1 in ('A','E'): continue
    if p2 in ('B','F'): continue
    if p3 in ('C','G'): continue
    if p4 in ('D','H'): continue
    # BACE correct count
    cnt1 = (p1=='B') + (p2=='A') + (p3=='C') + (p4=='E')
    if cnt1 != 1: continue
    # JKJK count
    cnt2 = (p1=='J') + (p2=='K') + (p3=='J') + (p4=='K')
    if cnt2 != 2: continue
    solutions.append(''.join(p))
print(len(solutions))
print(solutions[:50])
