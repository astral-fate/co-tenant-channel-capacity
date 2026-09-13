import itertools, json, sys, os

CHARS = ['A','B','C','D','E','F','G','H','J','K']

def generate_all():
    return [''.join(p) for p in itertools.product(CHARS, repeat=4)]

def filter_candidates(candidates, guess, matches):
    # keep codes where number of positions equal to guess equals matches
    def count_match(code):
        return sum(c1==c2 for c1,c2 in zip(code, guess))
    return [c for c in candidates if count_match(c)==matches]

if __name__ == '__main__':
    # This script will be used interactively via the assistant.
    pass
