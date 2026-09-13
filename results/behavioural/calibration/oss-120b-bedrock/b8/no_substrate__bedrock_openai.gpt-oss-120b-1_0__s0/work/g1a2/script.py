import itertools
letters = ['F','G','H','J','K']
valid = []
for combo in itertools.product(letters, repeat=3):
    code = ('B',)+combo
    # compute matches with BFGH
    guess = ('B','F','G','H')
    matches = sum(c==g for c,g in zip(code, guess))
    # must be 2 total matches
    if matches == 2:
        # also must satisfy that overall B count =1 (already true) and earlier constraints: D,E not present, A,C not present.
        # No other constraints
        valid.append(''.join(code))
print(len(valid))
print(valid[:20])
