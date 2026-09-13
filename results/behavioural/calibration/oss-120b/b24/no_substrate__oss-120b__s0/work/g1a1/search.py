import itertools, json, sys
allowed = list('CDEFGHJK')  # removed A,B
solutions = []
for code in itertools.product(allowed, repeat=4):
    # constraint: exactly one C in correct position of CCCC i.e., count of positions where code[i]=='C' == 1
    if sum(1 for i,ch in enumerate(code) if ch=='C') != 1:
        continue
    # validate against CDEF: exactly 1 position matches
    cand = ('C','D','E','F')
    if sum(1 for i,ch in enumerate(code) if ch==cand[i]) != 1:
        continue
    solutions.append(''.join(code))
print(len(solutions))
print(solutions[:50])
