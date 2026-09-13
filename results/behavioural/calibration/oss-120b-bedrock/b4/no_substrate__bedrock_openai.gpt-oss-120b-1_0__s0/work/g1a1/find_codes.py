allowed = ['A','B','C','D','E','F','G','H','J','K']
forbidden = {
    0: set(['A','E','B','J']),
    1: set(['B','F','C','A']),
    2: set(['C','G','A','C']),
    3: set(['D','H','E','K'])
}
valid = []
for a in allowed:
    if a in forbidden[0]: continue
    for b in allowed:
        if b in forbidden[1]: continue
        for c in allowed:
            if c in forbidden[2]: continue
            for d in allowed:
                if d in forbidden[3]: continue
                valid.append(a+b+c+d)
print('count', len(valid))
print(valid[:200])
