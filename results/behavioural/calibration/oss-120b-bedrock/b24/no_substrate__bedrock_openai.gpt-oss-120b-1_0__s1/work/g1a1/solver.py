import itertools, json
letters = ['A','B','C','D','E','F','G','H','J','K']

# constraints: list of (candidate, correct_count)
constraints = [
    ("AAAA",0),
    ("BAAA",0),
    ("CAAA",0),
    ("DEFG",1),
    ("EDFG",0),
    ("DBBB",1),
    ("DEHH",1),
    ("DKKK",1),
]

def matches(candidate, guess):
    return sum(c==g for c,g in zip(candidate, guess))

solutions = []
for cand in map(''.join, itertools.product(letters, repeat=4)):
    ok=True
    for guess, cnt in constraints:
        if matches(cand, guess)!=cnt:
            ok=False
            break
    if ok:
        solutions.append(cand)
print('solutions', solutions)
