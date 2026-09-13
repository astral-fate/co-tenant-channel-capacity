import itertools, json, sys

def all_codes(chars='ABCDEFGHIJK'):
    # but allowed chars A B C D E F G H J K (no I)
    allowed = ['A','B','C','D','E','F','G','H','J','K']
    return [''.join(p) for p in itertools.product(allowed, repeat=4)]

def score(guess, secret):
    return sum(g==s for g,s in zip(guess, secret))

def main():
    import os, sys
    # Simple loop to interact with validate via stdin? We'll just placeholder
    pass
