import itertools, json, sys, os
chars = list('ABCDEFGHIJK')
# Actually allowed: A B C D E F G H J K (no I) -> remove I
chars = ['A','B','C','D','E','F','G','H','J','K']
all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]
print('total', len(all_codes))
