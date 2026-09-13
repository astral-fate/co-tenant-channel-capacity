import itertools
letters = list('CDEFGHJK')
solutions=[]
for p in itertools.product(letters, repeat=4):
    p1,p2,p3,p4 = p
    # constraint 1
    if p1 == 'C':
        continue
    # exactly one C among positions 2-4
    if sum([p2=='C', p3=='C', p4=='C']) != 1:
        continue
    # exactly one D in correct position (i.e., total count of D)
    if sum([p1=='D', p2=='D', p3=='D', p4=='D']) != 1:
        continue
    # exactly one E in correct position
    if sum([p1=='E', p2=='E', p3=='E', p4=='E']) != 1:
        continue
    # DCEF matches exactly 2
    matches = (p1=='D') + (p2=='C') + (p3=='E') + (p4=='F')
    if matches != 2:
        continue
    solutions.append(''.join(p))
print('solutions', len(solutions))
print(solutions)
