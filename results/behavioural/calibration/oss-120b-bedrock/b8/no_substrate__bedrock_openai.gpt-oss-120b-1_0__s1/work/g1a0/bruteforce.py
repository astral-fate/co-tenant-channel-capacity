import itertools
chars = list('ABCDEFGHJK')
# Position constraints
pos1 = [c for c in chars if c not in ('A','E','J','K')]
pos2 = [c for c in chars if c not in ('B','F','J')]
pos3 = [c for c in chars if c not in ('C','G','J')]
pos4 = [c for c in chars if c not in ('D','H','J')]

def match(a,b):
    return sum(x==y for x,y in zip(a,b))
solutions=[]
for w,x,y,z in itertools.product(pos1,pos2,pos3,pos4):
    cand = w+x+y+z
    # zero matches
    if match(cand,'ABCD')!=0: continue
    if match(cand,'EFGH')!=0: continue
    if match(cand,'JJJJ')!=0: continue
    if match(cand,'KBCD')!=0: continue
    # feedback
    if match(cand,'BCDE')!=1: continue
    if match(cand,'BAAA')!=1: continue
    if match(cand,'BDBC')!=1: continue
    if match(cand,'BEEB')!=1: continue
    solutions.append(cand)
print('solutions',solutions)
