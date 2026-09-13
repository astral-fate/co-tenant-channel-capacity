import itertools
letters = list('ABCDEFGHJK')
# allowed per position based on constraints
allowed = [
    set(['C','D','F','G','H']),   # pos0
    set(['A','C','D','E','G','H']), # pos1
    set(['A','D','E','F','H']),   # pos2
    set(['A','C','E','F','G'])    # pos3
]

candidates = []
for p in itertools.product(letters, repeat=4):
    code = ''.join(p)
    # check per position
    if any(code[i] not in allowed[i] for i in range(4)):
        continue
    # exactly one A
    if code.count('A') != 1:
        continue
    candidates.append(code)
print('Total candidates:', len(candidates))
print(candidates[:100])
