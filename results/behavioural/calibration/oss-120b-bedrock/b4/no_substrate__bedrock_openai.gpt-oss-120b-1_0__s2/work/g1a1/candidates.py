import itertools
chars = ['A','B','C','D','E','F','G','H','J','K']
all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

valid = []
for secret in all_codes:
    if feedback(secret, 'ABCD') != 0:
        continue
    if feedback(secret, 'EFGH') != 0:
        continue
    if feedback(secret, 'JJJJ') != 0:
        continue
    if feedback(secret, 'KKKK') != 2:
        continue
    valid.append(secret)
print('Valid count:', len(valid))
print(valid)
