allowed = list('ABCDEFGHIJK')
# Actually allowed letters are A B C D E F G H J K (no I) but we include J,K.
allowed = ['A','B','C','D','E','F','G','H','J','K']
attempts = ['JACK','ABCD','EFGH','BCAE']
valid = []
for a in allowed:
    for b in allowed:
        for c in allowed:
            for d in allowed:
                cand = a+b+c+d
                ok=True
                for att in attempts:
                    cnt=sum(1 for x,y in zip(cand, att) if x==y)
                    if cnt!=0:
                        ok=False
                        break
                if ok:
                    valid.append(cand)
print('total', len(valid))
print(valid[:100])
