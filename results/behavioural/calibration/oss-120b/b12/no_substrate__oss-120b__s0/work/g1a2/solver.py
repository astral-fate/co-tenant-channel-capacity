import itertools, json, sys, os

alphabet = list('ABCDEFGHJK')  # note J and K, no I

def all_codes():
    return [''.join(p) for p in itertools.product(alphabet, repeat=4)]

def match(a, b):
    return sum(1 for x, y in zip(a, b) if x == y)

# Load possible set from file if exists
possible_path = 'possible.txt'
if os.path.exists(possible_path):
    with open(possible_path) as f:
        possible = json.load(f)
else:
    possible = all_codes()

# Choose next guess using simple heuristic: pick the first candidate
# could implement minimax later if needed
next_guess = possible[0]
print(next_guess)
