chars = ['C','D','E','F','G','H','J','K']
pos2_opts = ['F','G','H','J','K']
pos3_opts = ['F','H','J','K']
pos4_opts = ['C','G','H','K']
solutions = []
for p2 in pos2_opts:
    for p3 in pos3_opts:
        for p4 in pos4_opts:
            if len({p2,p3,p4})<3: continue  # distinct
            solutions.append(('B',p2,p3,p4))
print(len(solutions))
print(solutions[:20])
