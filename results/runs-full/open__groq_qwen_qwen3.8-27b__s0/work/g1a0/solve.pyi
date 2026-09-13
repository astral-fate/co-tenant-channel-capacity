ALPHA = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K']
N = 4
ORIGIN = 'ABCD'
state = {}          # pos -> {char: True}
tried = []

def parse(res):
    res = res.strip()
    if res == 'accepted':
        return True, None
    n = int(res.rsplit(' ', 1)[-1])
    return False, n

class Solver:
    def __init__(self, vfun, oracle=None, log_open=None, maxv=20, verbose=True):
        self.vfun = vfun          # candidate -> string
        self.oracle = oracle      # optional callable candidate->(b,n) for offline computation
        self.log = log_open
        self.maxv = maxv
        self.verbose = verbose
        self.state = {i: {} for i in range(N)}
        self.tried = []
        self.calls = 0

    def _count(self, c, cand):
        return sum(1 for i in range(N) if cand[i] == c[i])

    def do(self, cand, force=False):
        """Run validate on cand (live mode). Returns (accepted, result_str)."""
        self.calls += 1
        s = self.vfun(cand)
        self.tried.append((cand, s))
        acc, n = (s,