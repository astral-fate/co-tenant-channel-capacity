chars = ['C','D','E','F','G','H','J','K']
possible = []
for p2 in chars:
    if p2 in ['C','D','E']:
        continue
    for p3 in chars:
        if p3 in ['D','E','G']:
            continue
        for p4 in chars:
            if p4 in ['D','F','J','E']:
                continue
            # exactly one of conditions
            cond = (p2=='G') + (p3=='H') + (p4=='K')
            if cond == 1:
                possible.append('B'+p2+p3+p4)
print(len(possible))
print(possible)
