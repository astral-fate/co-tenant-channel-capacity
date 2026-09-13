import itertools, sys
letters = list('ABCDEFGHJK')
valid = []
for combo in itertools.product(letters, repeat=4):
    # assume distinct? comment out later
    # if len(set(combo))!=4:
    #    continue
    # constraints
    # ABCD 0 correct
    if combo[0]=='A' or combo[1]=='B' or combo[2]=='C' or combo[3]=='D':
        continue
    # EFGH 1 correct position
    matches = sum([combo[i]==c for i,c in enumerate('EFGH')])
    if matches!=1:
        continue
    # EJKJ 0 correct
    if combo[0]=='E' or combo[1]=='J' or combo[2]=='K' or combo[3]=='J':
        continue
    valid.append(''.join(combo))
print('total', len(valid))
# print first few
for v in valid[:20]:
    print(v)
