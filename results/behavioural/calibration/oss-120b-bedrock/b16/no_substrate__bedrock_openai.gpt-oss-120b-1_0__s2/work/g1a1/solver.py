import itertools, json, sys
chars = ['B','E','F','G','H','J','K']
# secret is 4 chars, could repeat? Probably yes, but we know exactly one B.
solutions = []
for combo in itertools.product(chars, repeat=4):
    if combo.count('B') != 1:
        continue
    # check constraints
    # AAAA: 0 matches
    if sum(1 for i,c in enumerate(combo) if c=='A') != 0:
        continue  # but A not in chars
    # actually A not in chars, so ok
    # BBBB: 1 match
    if sum(1 for i,c in enumerate(combo) if c=='B') != 1:
        continue
    # CCCC: 0 match
    if sum(1 for i,c in enumerate(combo) if c=='C') != 0:
        continue
    # DDDD: 0 match
    if sum(1 for i,c in enumerate(combo) if c=='D') != 0:
        continue
    solutions.append(''.join(combo))
print(len(solutions))
print(solutions[:20])
