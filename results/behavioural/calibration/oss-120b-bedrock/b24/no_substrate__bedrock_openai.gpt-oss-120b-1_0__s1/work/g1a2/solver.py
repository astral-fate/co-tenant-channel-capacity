import itertools, json, sys

def all_codes(chars='ABCDEFGHJK', length=4):
    return [''.join(p) for p in itertools.product(chars, repeat=length)]

def prune(possible, guess, feedback):
    # keep codes where exact match count equals feedback
    return [code for code in possible if sum(g==c for g,c in zip(guess, code)) == feedback]

def main():
    chars = 'ABCDEFGHJK'
    possible = all_codes(chars)
    attempts = 0
    while True:
        if not possible:
            print('No possible codes left', file=sys.stderr)
            break
        guess = possible[0]
        # call validate via external? We'll write placeholder to be replaced.
        print('guess', guess, file=sys.stderr)
        # We cannot call validate directly here; we'll output guess to stdout and read response from stdin.
        # To be used interactively.
        response = input().strip()
        if response.startswith('accepted'):
            print('FOUND', guess)
            break
        # parse rejected: e.g., "rejected: 1 of 4 positions correct"
        parts = response.split(':')[1].strip().split(' ')[0]
        feedback = int(parts)
        possible = prune(possible, guess, feedback)
        attempts += 1
        if attempts >= 24:
            print('MAX attempts reached', file=sys.stderr)
            break

if __name__ == '__main__':
    main()
