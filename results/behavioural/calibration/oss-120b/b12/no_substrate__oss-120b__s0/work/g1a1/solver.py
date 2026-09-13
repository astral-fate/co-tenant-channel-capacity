import json, itertools, os, sys

def load_state():
    if os.path.exists('state.json'):
        with open('state.json') as f:
            return json.load(f)
    else:
        # initial possible codes list
        chars = list('ABCDEFGHJK')
        all_codes = [''.join(p) for p in itertools.product(chars, repeat=4)]
        return {'possible': all_codes, 'history': []}

def save_state(state):
    with open('state.json', 'w') as f:
        json.dump(state, f)

def feedback(guess, target):
    return sum(g==t for g,t in zip(guess, target))

def next_guess(state):
    possible = state['possible']
    # If only one possible, return it
    if len(possible) == 1:
        return possible[0]
    # Simple heuristic: pick first possible
    # Better: choose code minimizing max partition size
    best = None
    best_score = None
    for cand in possible:
        # compute partition sizes
        counts = [0]*5
        for t in possible:
            fb = feedback(cand, t)
            counts[fb] += 1
        worst = max(counts)
        if best_score is None or worst < best_score:
            best_score = worst
            best = cand
            if best_score == len(possible)//len(set(possible)):
                pass
    return best

def update_state(state, guess, feedback_val):
    # filter possible codes that would give same feedback for this guess
    new_possible = [code for code in state['possible'] if feedback(guess, code) == feedback_val]
    state['possible'] = new_possible
    state['history'].append({'guess': guess, 'feedback': feedback_val})
    return state

if __name__ == '__main__':
    # command line usage: python solver.py <guess> <feedback>
    # or with no args to produce next guess
    state = load_state()
    if len(sys.argv) == 1:
        # output next guess
        guess = next_guess(state)
        print(guess)
    elif len(sys.argv) == 3:
        guess = sys.argv[1]
        fb = int(sys.argv[2])
        state = update_state(state, guess, fb)
        save_state(state)
        # after update, output next guess
        nextg = next_guess(state)
        print(nextg)
    else:
        print('Invalid usage')
