import itertools
chars = ['A','B','C','D','E','F','G','H','J','K']
solutions = []
for p in itertools.product(chars, repeat=4):
    cand = ''.join(p)
    # constraints from exclusions
    if p[0] in ['A','E','B']:
        continue
    if p[1] in ['B','F']:
        continue
    if p[2] in ['C','G']:
        continue
    if p[3] in ['D','H','J']:
        continue
    # feedback functions
    def feedback(guess, target):
        return sum(g==t for g,t in zip(guess, target))
    # known feedbacks
    if feedback('ABCD', cand) != 0:
        continue
    if feedback('EFGH', cand) != 0:
        continue
    if feedback('BCDJ', cand) != 1:
        continue
    if feedback('BBCD', cand) != 0:
        continue
    if feedback('ACGH', cand) != 1:
        continue
    if feedback('CCAA', cand) != 2:
        continue
    solutions.append(cand)
print('solutions count', len(solutions))
for s in solutions:
    print(s)
