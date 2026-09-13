import itertools
chars = ['E','F','G','H','J','K']
possible = []
for p2 in chars:
    for p3 in ['C','E','F','G','H','J','K']:
        for p4 in ['C','F','G','H','J','K']:
            # constraints
            if (p2=='E') == (p3=='E'): # need exactly one E among p2,p3
                continue
            if (p3=='C') == (p4=='C'): # need exactly one C among p3,p4
                continue
            # also ensure p3 not D, p4 not D already satisfied
            possible.append('D'+p2+p3+p4)
print(len(possible))
print(possible[:20])
