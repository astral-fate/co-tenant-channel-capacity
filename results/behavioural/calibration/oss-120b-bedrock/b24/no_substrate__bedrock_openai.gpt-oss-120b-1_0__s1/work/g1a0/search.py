import itertools
letters = ['A','B','C','D','E','F','G','H','J','K']
candidates = {
    'ABCD':0,
    'EFGH':0,
    'JJJJ':0,
    'KKKK':2,
    'KABC':0,
    'BKKE':2,
}
solutions=[]
for code in map(''.join, itertools.product(letters, repeat=4)):
    ok=True
    for cand,score in candidates.items():
        matches=sum(a==b for a,b in zip(code,cand))
        if matches!=score:
            ok=False
            break
    if ok:
        solutions.append(code)
print(len(solutions))
print(solutions)
