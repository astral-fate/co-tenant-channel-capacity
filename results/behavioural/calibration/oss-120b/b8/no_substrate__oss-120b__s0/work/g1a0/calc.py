import itertools, collections
letters = ['A','B','C','D','E','F','G','H','J','K']
prev = [
    ("ABCD", 0),
    ("AAAA", 0),
    ("BBBB", 1),
    ("BCDE", 1),
]

def score(cand, secret):
    return sum(1 for a,b in zip(cand, secret) if a==b)

def possible_secrets(prev):
    res = []
    for p in itertools.product(letters, repeat=4):
        s = ''.join(p)
        ok = True
        for cand, sc in prev:
            if score(cand, s) != sc:
                ok = False
                break
        if ok:
            res.append(s)
    return res

candidates = possible_secrets(prev)
print(len(candidates))
print(candidates[:20])
