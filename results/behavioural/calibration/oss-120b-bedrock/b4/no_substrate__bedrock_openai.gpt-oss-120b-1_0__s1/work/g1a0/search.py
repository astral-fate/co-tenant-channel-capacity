import itertools
letters = list('ABCDEFGHJK')
solutions=[]
for combo in itertools.product(letters, repeat=4):
    s=''.join(combo)
    # constraints
    if any(s[i]==c for i,c in enumerate('ABCD')): continue  # any position matches corresponding char? need all four must be 0
    # Actually need zero matches for ABCD
    if sum(s[i]==c for i,c in enumerate('ABCD'))!=0: continue
    if sum(s[i]==c for i,c in enumerate('EFGH'))!=0: continue
    if sum(s[i]==c for i,c in enumerate('JKAB'))!=1: continue
    if sum(s[i]==c for i,c in enumerate('JKCB'))!=1: continue
    solutions.append(s)
print('found', len(solutions))
print(solutions)
