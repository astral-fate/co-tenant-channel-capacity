import itertools, json
letters = list('AB C D E F G H J K'.replace(' ',''))
# Actually letters: A B C D E F G H J K
letters = ['A','B','C','D','E','F','G','H','J','K']
for combo in itertools.product(letters, repeat=4):
    # apply banned positions constraints from earlier tests
    if combo[0] in ('A','E','J'): continue
    if combo[1] in ('B','F','K'): continue
    if combo[2] in ('C','G','J'): continue
    if combo[3] in ('D','H','K'): continue
    # Additionally, we could consider that ABCD,EFGH,JKJK each gave 0 correct positions.
    # That already enforced, but also those combos themselves must have 0 matches, which we already enforce.
    # No further info.
    print(''.join(combo))
    break
