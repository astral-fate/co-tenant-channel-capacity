import itertools, json
chars = list('ABCDEFGHJK')
valid_codes = []
for code in itertools.product(chars, repeat=4):
    # Exactly two K's
    if sum(1 for c in code if c=='K') != 2:
        continue
    # constraints from feedbacks
    # ABCD -> 0 correct
    if code[0]=='A' or code[1]=='B' or code[2]=='C' or code[3]=='D':
        continue
    # EEEE -> 0 correct (no E anywhere)
    if any(c=='E' for c in code):
        continue
    # FGHJ -> 0 correct
    if code[0]=='F' or code[1]=='G' or code[2]=='H' or code[3]=='J':
        continue
    valid_codes.append(''.join(code))
print('count', len(valid_codes))
print(valid_codes[:200])
