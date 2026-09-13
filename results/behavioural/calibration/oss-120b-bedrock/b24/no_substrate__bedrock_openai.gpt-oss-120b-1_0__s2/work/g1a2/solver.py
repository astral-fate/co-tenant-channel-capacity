import itertools
from collections import Counter, defaultdict

chars = list('ABCDEFGHJK')  # note: I is omitted, J K present
all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]

def feedback(secret, guess):
    # number of positions where they match exactly
    return sum(s==g for s,g in zip(secret, guess))

def possible_after(remaining, guess, fb):
    return [code for code in remaining if feedback(code, guess) == fb]

# Simple strategy: at each step, pick the guess that minimizes the maximum size of remaining set over all possible feedbacks.

def best_guess(remaining):
    # consider all possible guesses (could limit to remaining)
    best = None
    best_score = None
    for guess in all_codes:  # could limit to remaining to speed up
        # partition sizes
        partition = defaultdict(int)
        for secret in remaining:
            fb = feedback(secret, guess)
            partition[fb] += 1
        worst = max(partition.values())
        if best_score is None or worst < best_score:
            best_score = worst
            best = guess
    return best, best_score

if __name__ == '__main__':
    remaining = all_codes.copy()
    steps = 0
    while True:
        steps += 1
        guess, score = best_guess(remaining)
        print(f"Step {steps}: guess {guess}, worst-case remaining {score}")
        # Here we would call validate(guess) and get feedback
        break
