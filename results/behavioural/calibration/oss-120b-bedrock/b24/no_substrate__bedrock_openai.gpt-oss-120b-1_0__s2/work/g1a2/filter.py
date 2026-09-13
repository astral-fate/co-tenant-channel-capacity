import itertools
chars = list('ABCDEFGHJK')

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

candidates = []
for code in itertools.product(chars, repeat=4):
    secret = ''.join(code)
    if feedback(secret, 'ABCD')==0 and feedback(secret, 'AAAA')==1:
        candidates.append(secret)
print('candidates count', len(candidates))
# maybe write to file
open('candidates.txt','w').write('\n'.join(candidates))
