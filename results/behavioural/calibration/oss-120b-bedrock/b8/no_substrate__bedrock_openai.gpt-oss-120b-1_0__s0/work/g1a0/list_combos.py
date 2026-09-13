pos2 = ['F','G','H','J','K']
pos3 = ['F','H','J','K']
pos4 = ['C','G','H','K']
combos = []
for p2 in pos2:
    for p3 in pos3:
        for p4 in pos4:
            if len({p2,p3,p4})==3:
                combos.append(('B',p2,p3,p4))
print(len(combos))
print(combos)
