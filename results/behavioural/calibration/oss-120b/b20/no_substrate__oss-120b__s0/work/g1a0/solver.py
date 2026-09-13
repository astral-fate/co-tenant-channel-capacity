import itertools, json, sys, os, math

def all_codes(chars='ABCDEFGHIJK'):
    # actually allowed chars: A B C D E F G H J K (no I)
    allowed = ['A','B','C','D','E','F','G','H','J','K']
    return [''.join(p) for p in itertools.product(allowed, repeat=4)]

codes = all_codes()

# placeholder for interactive validation

def validate_candidate(candidate):
    # call external validate tool
    import subprocess, json, sys
    # Not possible here; we'll define a stub.
    pass
