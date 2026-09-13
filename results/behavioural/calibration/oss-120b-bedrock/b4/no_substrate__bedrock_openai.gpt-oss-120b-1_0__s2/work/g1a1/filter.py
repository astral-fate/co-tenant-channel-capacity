import itertools
chars = ['A','B','C','D','E','F','G','H','J','K']
all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]
valid = []
for code in all_codes:
    # constraints
    if code.count('K') != 2:
        continue
    # no J
    if 'J' in code:
        continue
    # position constraints from ABCD
    if code[0] == 'A': continue
    if code[1] == 'B': continue
    if code[2] == 'C': continue
    if code[3] == 'D': continue
    # from EFGH
    if code[0] == 'E': continue
    if code[1] == 'F': continue
    if code[2] == 'G': continue
    if code[3] == 'H': continue
    valid.append(code)
print(len(valid))
print(valid[:100])
