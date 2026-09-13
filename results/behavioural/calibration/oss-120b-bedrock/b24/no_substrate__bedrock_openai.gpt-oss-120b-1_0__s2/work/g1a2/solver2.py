import itertools, json, os

chars = list('ABCDEFGHJK')

# Store constraints as list of (guess, count)
constraints = []

def feedback(secret, guess):
    return sum(s==g for s,g in zip(secret, guess))

def load_constraints():
    if os.path.exists('constraints.json'):
        with open('constraints.json') as f:
            return json.load(f)
    return []

def save_constraints(constraints):
    with open('constraints.json','w') as f:
        json.dump(constraints, f)

def add_constraint(guess, count):
    constraints = load_constraints()
    constraints.append([guess, count])
    save_constraints(constraints)

def possible_codes():
    constraints = load_constraints()
    poss = []
    for p in itertools.product(chars, repeat=4):
        code = ''.join(p)
        ok = True
        for guess, cnt in constraints:
            if feedback(code, guess) != cnt:
                ok = False
                break
        if ok:
            poss.append(code)
    return poss

if __name__ == '__main__':
    # Example: add some known constraints
    # add_constraint('ABCD', 0)
    # add_constraint('AAAA', 1)
    # add_constraint('EFGH', 0)
    # add_constraint('BBBB', 0)
    # add_constraint('JJJJ', 0)
    # add_constraint('BACD', 0)
    # add_constraint('CCCC', 1)
    # add_constraint('ACDK', 1)
    poss = possible_codes()
    print('Possible codes count:', len(poss))
    print(poss[:50])
