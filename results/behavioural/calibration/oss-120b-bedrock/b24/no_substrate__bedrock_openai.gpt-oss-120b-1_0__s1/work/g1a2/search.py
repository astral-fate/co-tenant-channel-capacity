import itertools

chars = 'ABCDEFGHJK'

def feedback(guess, code):
    # returns number of positions where guess matches code
    return sum(g==c for g,c in zip(guess, code))

def is_consistent(code):
    # constraints from previous attempts
    # AAAA -> 1
    if feedback('AAAA', code) != 1:
        return False
    if feedback('ABCD', code) != 0:
        return False
    if feedback('BBBB', code) != 0:
        return False
    if feedback('EEEE', code) != 0:
        return False
    if feedback('FAAA', code) != 2:
        return False
    if feedback('FGHJ', code) != 1:
        return False
    return True

cands = []
for code in map(''.join, itertools.product(chars, repeat=4)):
    if is_consistent(code):
        cands.append(code)
print('consistent candidates:', len(cands))
print(cands)
"""
"""
