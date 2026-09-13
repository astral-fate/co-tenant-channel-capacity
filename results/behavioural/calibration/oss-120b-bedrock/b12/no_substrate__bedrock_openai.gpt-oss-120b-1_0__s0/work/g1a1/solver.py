import itertools, json, sys

letters = list('ABCDEFGHJK')

def all_codes():
    return [''.join(p) for p in itertools.product(letters, repeat=4)]

def feedback(guess, target):
    return sum(g==t for g,t in zip(guess, target))

def solve():
    candidates = all_codes()
    attempts = []
    for attempt_num in range(1, 13):
        guess = candidates[0]
        # call validate
        from functions import validate
        res = validate(candidate=guess)
        attempts.append((guess, res))
        if isinstance(res, dict) and res.get('status') == 'accepted':
            print('Found', guess)
            return guess
        # else res is e.g., {'status':'rejected','correct':n}
        correct = res.get('correct')
        # filter candidates
        candidates = [c for c in candidates if feedback(guess, c) == correct]
        print(f'Attempt {attempt_num}: guess {guess}, correct {correct}, remaining {len(candidates)}')
    print('Failed, remaining candidates:', candidates[:10])
    return None

if __name__ == '__main__':
    solve()
