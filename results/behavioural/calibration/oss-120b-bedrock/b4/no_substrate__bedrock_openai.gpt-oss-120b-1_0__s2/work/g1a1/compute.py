import itertools
chars = ['A','B','C','D','E','F','G','H','J','K']
all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]
def matches(guess, secret):
    return sum(g==s for g,s in zip(guess, secret))

guesses = ["ABCD","EFGH","JJJJ"]
candidates = []
for secret in all_codes:
    ok = True
    for g in guesses:
        if matches(g, secret) != 0:
            ok = False
            break
    if ok:
        candidates.append(secret)
print('Number of candidates:', len(candidates))
print(candidates[:50])
# If many, we could try to design next guess to narrow further.
