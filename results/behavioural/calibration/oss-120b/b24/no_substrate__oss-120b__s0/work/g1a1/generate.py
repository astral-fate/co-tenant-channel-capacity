import itertools, json
allowed = list('CDEFGHJK')
solutions = []
for code in itertools.product(allowed, repeat=4):
    # exactly one C
    if sum(ch=='C' for ch in code)!=1:
        continue
    # exactly one match with CDEF
    cand = ('C','D','E','F')
    if sum(code[i]==cand[i] for i in range(4))!=1:
        continue
    solutions.append(''.join(code))
print('total', len(solutions))
print(solutions[:50])
