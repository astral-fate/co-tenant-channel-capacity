import itertools
chars = list('ABCDEFGHJK')

def matches(secret, guess, correct):
    return sum(s==g for s,g in zip(secret, guess)) == correct

def valid(secret):
    # constraints from guesses
    if matches(secret, 'ABCD', 0) is False: return False
    if matches(secret, 'AAAA', 1) is False: return False
    if matches(secret, 'EFGH', 0) is False: return False
    if matches(secret, 'BBBB', 0) is False: return False
    if matches(secret, 'JJJJ', 0) is False: return False
    if matches(secret, 'BACD', 0) is False: return False
    if matches(secret, 'CCCC', 1) is False: return False
    if matches(secret, 'ACDK', 1) is False: return False
    return True

candidates = [''.join(p) for p in itertools.product(chars, repeat=4) if valid(''.join(p))]
print('candidates count', len(candidates))
print(candidates)
with open('candidates.txt','w') as f:
    f.write('\n'.join(candidates))
