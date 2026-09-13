import itertools, json, sys

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

def next_guess(possible):
    # simple: return first
    return possible[0]

def main():
    chars = list('ABCDEFGHJK')
    all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]
    possible = all_codes
    attempts = []
    for turn in range(12):
        guess = next_guess(possible)
        print('GUESS', guess)
        # call validate via external? We'll just placeholder
        # In real loop, we need to interact with validate tool manually.
        # Here we just exit.
        break

if __name__ == '__main__':
    main()
