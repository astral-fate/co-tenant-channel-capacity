import itertools, json, sys
chars = list('ABCDEFGHJK')  # note J K included, no I
# constraints from analysis
# We'll generate all 4-length combos
valid = []

def feedback(candidate, target):
    # compute number correct positions
    return sum(1 for a,b in zip(candidate, target) if a==b)

# We'll simulate using known feedback as constraints

def satisfies(candidate):
    # candidate string length 4
    # constraints from queries
    def check(cand, guess, expected):
        return feedback(guess, cand) == expected
    # Data: list of (guess, expected)
    data = [
        ("AAAA",1),
        ("BBBB",0),
        ("ABBB",0),
        ("CAAA",1),
        ("CDEF",0),
        ("BABB",0),
        ("CDEG",0),
        ("ECFH",2),
    ]
    return all(check(candidate, g, e) for g,e in data)

for cand in itertools.product(chars, repeat=4):
    s = ''.join(cand)
    if satisfies(s):
        valid.append(s)
print(len(valid))
print(valid[:20])
