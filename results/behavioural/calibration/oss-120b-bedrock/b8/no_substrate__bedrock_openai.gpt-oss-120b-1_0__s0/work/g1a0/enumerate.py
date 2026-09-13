pos2_choices = ['F','G','H','J','K']
pos3_choices = ['F','H','J','K']
pos4_choices = ['C','G','H','K']
solutions = []
for p2 in pos2_choices:
    for p3 in pos3_choices:
        for p4 in pos4_choices:
            # exactly one of conditions true
            cond = (p2=='G') + (p3=='H') + (p4=='K')
            if cond == 1:
                solutions.append('B'+p2+p3+p4)
print(len(solutions))
print(solutions)
