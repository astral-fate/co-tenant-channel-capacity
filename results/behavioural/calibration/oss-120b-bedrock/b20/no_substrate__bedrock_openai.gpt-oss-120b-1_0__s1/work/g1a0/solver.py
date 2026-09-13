import itertools, json, sys

def all_codes():
    chars = list('ABCDEFGHIJK')
    # but excluded I and L? Actually allowed are A B C D E F G H J K (no I, no L)
    chars = list('ABCDEFGHJK')
    return [''.join(p) for p in itertools.product(chars, repeat=4)]

def feedback(guess, secret):
    # returns count of positions equal
    return sum(g==s for g,s in zip(guess, secret))

def next_guess(candidates):
    # simple: return first candidate
    return candidates[0]

if __name__ == '__main__':
    # interactive driver will be external
    pass
