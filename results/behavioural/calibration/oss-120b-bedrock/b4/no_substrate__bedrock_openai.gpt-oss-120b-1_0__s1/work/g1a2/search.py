import itertools, sys, json
chars = list('ABCDEFGHIJK')
# Actually allowed chars are A B C D E F G H J K (no I)
allowed = ['A','B','C','D','E','F','G','H','J','K']
solutions = []
for combo in itertools.product(allowed, repeat=4):
    x1,x2,x3,x4 = combo
    # constraints from attempt1: J A C K not in those positions
    if x1 == 'J': continue
    if x2 == 'A': continue
    if x3 == 'C': continue
    if x4 == 'K': continue
    # exactly one position matches B D F H respectively
    matches = 0
    if x1 == 'B': matches += 1
    if x2 == 'D': matches += 1
    if x3 == 'F': matches += 1
    if x4 == 'H': matches += 1
    if matches != 1:
        continue
    solutions.append(''.join(combo))
print(len(solutions))
# Optionally print a few
for s in solutions[:50]:
    print(s)
# Save to file
with open('solutions.txt','w') as f:
    for s in solutions:
        f.write(s+'\n')
