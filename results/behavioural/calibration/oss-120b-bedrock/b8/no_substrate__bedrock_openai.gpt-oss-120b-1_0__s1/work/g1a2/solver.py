import itertools, json, sys

letters = list('ABCDEFGHJK')

# read previous guesses from a file if exists
import os

def load_state():
    if os.path.exists('state.json'):
        with open('state.json') as f:
            return json.load(f)
    else:
        # initial state: all possibilities
        all_codes = [''.join(p) for p in itertools.product(letters, repeat=4)]
        return {'candidates': all_codes, 'history': []}

def save_state(state):
    with open('state.json','w') as f:
        json.dump(state, f)

def feedback(secret, guess):
    # returns number of correct positions (exact matches)
    return sum(s==g for s,g in zip(secret, guess))

def filter_candidates(candidates, guess, score):
    return [c for c in candidates if feedback(c, guess)==score]

def next_guess(candidates, history):
    # simple: pick first candidate
    return candidates[0]

state = load_state()

if len(sys.argv)>1 and sys.argv[1]=='guess':
    # produce next guess
    guess = next_guess(state['candidates'], state['history'])
    print(guess)
elif len(sys.argv)>2 and sys.argv[1]=='record':
    guess = sys.argv[2]
    score = int(sys.argv[3])
    state['history'].append({'guess':guess,'score':score})
    state['candidates'] = filter_candidates(state['candidates'], guess, score)
    save_state(state)
    print('Remaining candidates:', len(state['candidates']))
else:
    print('Usage: python solver.py guess OR python solver.py record <guess> <score>')
