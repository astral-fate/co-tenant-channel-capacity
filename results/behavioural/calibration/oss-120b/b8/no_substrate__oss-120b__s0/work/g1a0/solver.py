import itertools, collections, math, sys

letters = list('AB CDEFGHJK'.replace(' ',''))
# Actually set: A B C D E F G H J K
letters = ['A','B','C','D','E','F','G','H','J','K']

# Load previous results
prev = []
# We'll store tuples (candidate, score)

# Function to compute score

def score(cand, secret):
    return sum(1 for a,b in zip(cand, secret) if a==b)

# Generate all possible secrets consistent with prev

def possible_secrets(prev):
    all_secrets = [''.join(p) for p in itertools.product(letters, repeat=4)]
    res = []
    for s in all_secrets:
        ok = True
        for cand, sc in prev:
            if score(cand, s) != sc:
                ok = False
                break
        if ok:
            res.append(s)
    return res

# Choose best next guess
def best_guess(possible):
    # Evaluate all candidates (could limit to possible set for efficiency)
    candidates = possible  # for simplicity
    best = None
    best_worst = None
    for cand in candidates:
        # compute distribution
        dist = collections.Counter()
        for secret in possible:
            sc = score(cand, secret)
            dist[sc] += 1
        worst = max(dist.values())
        if best_worst is None or worst < best_worst:
            best_worst = worst
            best = cand
    return best, best_worst

if __name__=='__main__':
    # Example usage: read prev from a file maybe
    pass
