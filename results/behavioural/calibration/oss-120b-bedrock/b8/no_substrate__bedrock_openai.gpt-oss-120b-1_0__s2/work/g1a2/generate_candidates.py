import itertools, sys
chars = list('ABCDEFGHIJK')
# Note: original set excludes I? Provided set: A B C D E F G H J K (no I). So adjust.
chars = ['A','B','C','D','E','F','G','H','J','K']
with open('candidates.txt','w') as f:
    for p in itertools.product(chars, repeat=4):
        f.write(''.join(p)+'\n')
print('Generated', 10**4, 'candidates')
