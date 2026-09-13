import itertools
chars = 'ABCDEFGHJK'
# constraints derived
possible = []
for s2,s3,s4 in itertools.product(chars, repeat=3):
    # each position cannot be B or E (global)
    if s2 in 'BE' or s3 in 'BE' or s4 in 'BE':
        continue
    # position-specific constraints
    # s1 is F fixed
    # from ABCD: s2 != B (already), s3 != C, s4 != D
    if s3 == 'C' or s4 == 'D':
        continue
    # from FGHJ: s2 != G, s3 != H, s4 != J
    if s2 == 'G' or s3 == 'H' or s4 == 'J':
        continue
    # exactly one of s2,s3,s4 is A
    a_count = sum(ch == 'A' for ch in (s2,s3,s4))
    if a_count != 1:
        continue
    # also from AAAA: exactly one of s2,s3,s4 is A (already) and s1 not A (true)
    # ensure s2 != B from earlier satisfied
    # also from AAAA we know s1 not A already satisfied.
    # no other constraints
    possible.append('F' + s2 + s3 + s4)
print('Number possible', len(possible))
print(possible[:50])
