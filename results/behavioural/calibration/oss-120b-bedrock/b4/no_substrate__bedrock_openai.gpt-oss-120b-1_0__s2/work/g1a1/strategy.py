import itertools, collections, sys, math

chars = list('AB CDEFGHJK'.replace(' ',''))
# Actually list of chars
chars = ['A','B','C','D','E','F','G','H','J','K']

# all possible 4-length codes (allow repetitions)
all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]

# function to compute feedback count
def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

# first guess fixed
first_guess = 'ABCD'
first_feedback = feedback('????', first_guess)  # placeholder not needed
# We'll filter according to known feedback: 0 positions correct.
remaining = [c for c in all_codes if feedback(c, first_guess)==0]
print('Remaining after first guess:', len(remaining))

# Now we need to find a set of up to 3 further guesses that for any secret in remaining, the sequence of feedbacks leads to unique identification.
# Brute force search limited? Space large: 10^4=10000, after first filter maybe less.

remaining_set = set(remaining)

# Let's attempt to search greedily for next guesses.

def find_strategy(max_depth=3):
    # BFS of decision tree
    from functools import lru_cache
    @lru_cache(None)
    def recurse(possible_codes, depth):
        if len(possible_codes)==1:
            return []  # no more guesses needed
        if depth==0:
            return None
        # iterate over candidate guesses (maybe all codes) to split possibilities
        for guess in all_codes:
            # compute partition of possible_codes by feedback
            parts = collections.defaultdict(list)
            for sec in possible_codes:
                fb = feedback(sec, guess)
                parts[fb].append(sec)
            # ensure each part can be solved with depth-1
            ok = True
            subplans = {}
            for fb, subset in parts.items():
                sub = recurse(tuple(sorted(subset)), depth-1)
                if sub is None:
                    ok=False
                    break
                subplans[fb]=sub
            if ok:
                # return plan: guess plus dict of subplans
                return (guess, subplans)
        return None
    return recurse(tuple(sorted(remaining_set)), max_depth)

plan = find_strategy(3)
print('Plan:', plan)
