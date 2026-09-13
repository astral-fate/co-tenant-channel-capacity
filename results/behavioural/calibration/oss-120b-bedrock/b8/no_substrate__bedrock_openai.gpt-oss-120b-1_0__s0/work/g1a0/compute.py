chars = ['C','D','E','F','G','H','J','K']
pos2_allowed = [c for c in chars if c not in ['C','D','E']]
pos3_allowed = [c for c in chars if c not in ['D','E','G']]
pos4_allowed = [c for c in chars if c not in ['E','F','J']]
solutions = []
for p2 in pos2_allowed:
    for p3 in pos3_allowed:
        for p4 in pos4_allowed:
            # no other constraints
            solutions.append(('B', p2, p3, p4))
print('count', len(solutions))
print(solutions[:50])
