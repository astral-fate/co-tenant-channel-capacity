import itertools
letters = list('ABCDEFGHJK')
valid = []
for combo in itertools.product(letters, repeat=4):
    s = ''.join(combo)
    # constraints
    def matches(a,b):
        return sum(c1==c2 for c1,c2 in zip(a,b))
    if matches(s, 'ABCD') != 0: continue
    if matches(s, 'EFGH') != 0: continue
    if matches(s, 'JKAB') != 1: continue
    valid.append(s)
print(len(valid))
print(valid[:50])
