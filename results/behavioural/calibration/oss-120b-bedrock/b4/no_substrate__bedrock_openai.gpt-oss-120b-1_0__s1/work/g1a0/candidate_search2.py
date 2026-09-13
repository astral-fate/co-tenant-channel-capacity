import itertools
letters = list('ABCDEFGHJK')

def matches(a,b):
    return sum(c1==c2 for c1,c2 in zip(a,b))

candidates=[]
for combo in itertools.product(letters, repeat=4):
    s=''.join(combo)
    if matches(s,'ABCD')!=0: continue
    if matches(s,'EFGH')!=0: continue
    if matches(s,'JKAB')!=1: continue
    candidates.append(s)
print('candidates count', len(candidates))
print(candidates[:200])
