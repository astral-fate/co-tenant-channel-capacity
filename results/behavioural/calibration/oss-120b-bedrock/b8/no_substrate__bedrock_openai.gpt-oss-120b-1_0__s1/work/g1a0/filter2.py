import itertools
chars = list('ABCDEFGHJK')
zero = ['ABCD','EFGH','JJJJ','KBCD']
# feedback dict
feedback = {
    'BCDE':1,
    'BAAA':1,
}

def match(cand, guess):
    return sum(c==g for c,g in zip(cand, guess))

solutions=[]
for cand in map(''.join, itertools.product(chars, repeat=4)):
    ok=True
    for g in zero:
        if match(cand,g)!=0:
            ok=False; break
    if not ok: continue
    for g,cnt in feedback.items():
        if match(cand,g)!=cnt:
            ok=False; break
    if ok:
        solutions.append(cand)
print('count', len(solutions))
print(solutions[:100])
