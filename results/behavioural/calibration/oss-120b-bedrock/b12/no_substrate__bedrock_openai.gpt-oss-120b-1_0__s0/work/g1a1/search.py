import itertools
letters = list('CDEFGHJK')  # no A,B

def matches(code, guess):
    return sum(c==g for c,g in zip(code, guess))

def satisfies(code):
    # constraints
    if code[0]=='C':
        return False
    # AAAA,BBBB already satisfied because no A,B
    # CAAA 0 correct: position1 C not match (already handled), others A not match any position (true)
    # DCEF 2 correct
    if matches(code, 'DCEF') != 2:
        return False
    # CCCC 1 correct
    if matches(code, 'CCCC') != 1:
        return False
    # DDDD 1 correct
    if matches(code, 'DDDD') != 1:
        return False
    # EEEE 1 correct
    if matches(code, 'EEEE') != 1:
        return False
    return True

candidates = []
for code in itertools.product(letters, repeat=4):
    if satisfies(code):
        candidates.append(''.join(code))
print('candidates', len(candidates))
print(candidates[:50])
