import itertools
letters = list('ABCD'+'EFGH'+'J'+'K')  # actually A B C D E F G H J K
letters = ['A','B','C','D','E','F','G','H','J','K']

def matches(candidate, guess):
    return sum(c==g for c,g in zip(candidate, guess))

candidates = []
for combo in itertools.product(letters, repeat=4):
    cand = ''.join(combo)
    if matches(cand, 'ABCD')==0 and matches(cand, 'EFGH')==0 and matches(cand, 'AEJK')==0:
        candidates.append(cand)
print('Number of candidates:', len(candidates))
# Show first few
print(candidates[:20])
