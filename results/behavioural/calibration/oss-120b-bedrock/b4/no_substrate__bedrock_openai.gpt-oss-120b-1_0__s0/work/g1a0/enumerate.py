import itertools, json, sys
chars = list('ABCDEFGHJK')  # note: no I, no L, no M, etc.
# constraints
prohibited = {
    0: set(['A','E','F']),
    1: set(['B','E','G']),
    2: set(['C','E','H']),
    3: set(['D','E','J']),
}
solutions = []
for combo in itertools.product(chars, repeat=4):
    # exactly two K's
    if combo.count('K') != 2:
        continue
    ok = True
    for i,ch in enumerate(combo):
        if ch in prohibited[i]:
            ok=False
            break
    if ok:
        solutions.append(''.join(combo))
print(len(solutions))
print(solutions[:50])
