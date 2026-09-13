import itertools, json
chars = list('ABCDEFGHJK')

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

candidates = []
for code in itertools.product(chars, repeat=4):
    secret = ''.join(code)
    if feedback(secret, 'ABCD')==0 and feedback(secret, 'AAAA')==1 and feedback(secret, 'EFGH')==0:
        candidates.append(secret)
print('Number candidates:', len(candidates))
# Save list
with open('candidates.txt','w') as f:
    f.write('\n'.join(candidates))
