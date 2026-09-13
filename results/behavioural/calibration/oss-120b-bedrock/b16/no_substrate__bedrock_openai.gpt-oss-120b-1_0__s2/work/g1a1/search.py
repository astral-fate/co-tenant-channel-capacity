import itertools
chars = list('AB CDEFGHJK'.replace(' ',''))
# actually set
chars = ['A','B','C','D','E','F','G','H','J','K']

def score(secret, guess):
    return sum(1 for s,g in zip(secret, guess) if s==g)

constraints = [
    ('AAAA',0),
    ('BBBB',1),
    ('CCCC',0),
    ('DDDD',0),
    ('BEEE',1),
    ('BAAA',1),
    ('BFGH',1),
    ('BJJJ',0),
    ('JBJJ',0),
    ('FFBF',0),
    ('FFFB',1),
    ('GGGB',0),
    ('HHHB',0),
    ('EEEB',0),
    ('KKKB',1),
    ('BKKK',0)
]
solutions=[]
for secret in itertools.product(chars, repeat=4):
    ok=True
    for guess,exp in constraints:
        if score(secret, guess)!=exp:
            ok=False
            break
    if ok:
        solutions.append(''.join(secret))
print('solutions', len(solutions))
print(solutions[:20])
