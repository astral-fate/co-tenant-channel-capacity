import itertools, json, sys
allowed = list('ABCDEFGHJK')
# constraints from known info
candidates = []
for p2 in ['F','H','J','K']:
    for p3 in ['F','G','J','K']:
        for p4 in ['F','G','H','K']:
            cand = 'B' + p2 + p3 + p4
            candidates.append(cand)
print('num candidates', len(candidates))
print(candidates)
