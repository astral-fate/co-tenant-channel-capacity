import itertools, json
chars = list('ABCDEFGHJK')
# allowed per position based on zero constraints
pos1 = [c for c in chars if c not in ('A','E','K','J')]
pos2 = [c for c in chars if c not in ('B','F','J')]
pos3 = [c for c in chars if c not in ('C','G','J')]
pos4 = [c for c in chars if c not in ('D','H','J')]

def match(a,b):
    return sum(x==y for x,y in zip(a,b))
solutions=[]
for cand in itertools.product(pos1,pos2,pos3,pos4):
    s=''.join(cand)
    if match(s,'ABCD')!=0: continue
    if match(s,'EFGH')!=0: continue
    if match(s,'JJJJ')!=0: continue
    if match(s,'KBCD')!=0: continue
    if match(s,'BCDE')!=1: continue
    if match(s,'BAAA')!=1: continue
    if match(s,'BDBC')!=1: continue
    solutions.append(s)
print(len(solutions))
print(solutions)
"""
"""
