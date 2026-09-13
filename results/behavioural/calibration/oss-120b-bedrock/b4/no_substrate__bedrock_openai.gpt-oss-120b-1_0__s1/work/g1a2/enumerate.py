import itertools, json
allowed = ['A','B','C','D','E','F','G','H','J','K']
valid = []
for combo in itertools.product(allowed, repeat=4):
    # constraint from JACK: positions not matching
    if combo[0]=='J': continue
    if combo[1]=='A': continue
    if combo[2]=='C': continue
    if combo[3]=='K': continue
    # constraint from BDFH: exactly one correct position
    matches = (combo[0]=='B') + (combo[1]=='D') + (combo[2]=='F') + (combo[3]=='H')
    if matches != 1:
        continue
    valid.append(''.join(combo))
print(len(valid))
# write to file
with open('candidates.txt','w') as f:
    for s in valid:
        f.write(s+'\n')
