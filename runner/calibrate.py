"""
Turn-budget calibration.

The inheritance advantage Δ is a difference of two success rates. It can only be observed if
solo success sits away from both floor and ceiling: if an unaided agent almost always solves the
task, there is nothing for an inherited hint to add, and Δ is driven to zero by the ceiling rather
than by the absence of a channel.

That is a live risk here. A correct consistency solver clears the search tasks in a mean of about
9 probes (max 11), so at a generous turn budget a competent model saturates. Enlarging the search
space is a weak lever -- positional feedback is very informative, and taking the code from 4 to 6
characters (a 100x larger space) moves optimal probes only from ~9 to ~12. The effective lever is
the probe budget, which run.py enforces at the oracle via --max-probes.

This script therefore sweeps the budget on the `no_substrate` condition only and reports the
success curve, so the operating budget is chosen from evidence rather than guessed.

METHODOLOGICAL NOTE, and the reason this is a separate script rather than a flag: calibration
must see ONLY the baseline arm. It never runs a treatment condition and never looks at deposit,
pickup or Δ. Choosing a budget from baseline difficulty is a design decision; choosing it from
treatment outcomes would be tuning on the result. The chosen budget is frozen into
docs/03-preregistration.md as a dated amendment before the main matrix runs.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

import providers                                   # noqa: E402
from run import CONDITIONS, run_condition          # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sweep the probe budget on the baseline arm only.")
    ap.add_argument("--models", default="claude-haiku")
    ap.add_argument("--budgets", default="5,6,7,8,9,10,12",
                    help="PROBE budgets to sweep (oracle calls per episode).")
    ap.add_argument("--max-turns", type=int, default=30,
                    help="Turn ceiling, held fixed while the probe budget is swept. "
                         "Must exceed the largest probe budget or turns bind first.")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--generations", type=int, default=2)
    ap.add_argument("--agents", type=int, default=3)
    ap.add_argument("--target", type=float, default=0.45,
                    help="solo success rate to aim for; mid-range leaves room for Delta")
    ap.add_argument("--outdir", default=str(HERE.parent / "results" / "behavioural" / "calibration" / "kimi"))
    a = ap.parse_args(argv)

    providers.load_env(HERE.parent / ".env")
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    budgets = [int(b) for b in a.budgets.split(",") if b.strip()]
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]

    if models != ["mock"]:
        have = providers.available()
        missing = [m for m in models if m not in have and ":" not in m]
        if missing:
            print(f"ERROR: no API key for {missing}. Available: {have or '(none)'}", file=sys.stderr)
            return 2

    n_eps = len(models) * len(budgets) * len(seeds) * a.generations * a.agents
    print(f"calibration: baseline arm only, {n_eps} episodes "
          f"({len(budgets)} budgets x {len(models)} models x {len(seeds)} seeds)")
    print()

    curve: dict[str, list[tuple[int, float, int, float]]] = {}

    for model in models:
        curve[model] = []
        for budget in budgets:
            eps = []
            for i, s in enumerate(seeds, 1):
                # Progress is printed per seed, not withheld until the table. Calibration on a
                # local 8B is minutes per episode; a run that prints nothing until it finishes
                # is indistinguishable from one that has hung, and the first thing it does --
                # fetching ~16 GB of weights -- is the longest silent step of all.
                print(f"  [{i}/{len(seeds)}] {model} budget={budget} seed={s} ...",
                      flush=True)
                t0 = time.time()
                got = run_condition(
                    condition=CONDITIONS["no_substrate"], model_alias=model, seed=s,
                    generations=a.generations, agents_per_gen=a.agents,
                    outdir=Path(a.outdir) / f"b{budget}", max_turns=a.max_turns,
                    max_probes=budget, verbose=True,
                )
                # An episode that ended in an API error is not evidence about the model, and
                # counting it as a failure is how a provider outage becomes a reported difficulty
                # floor. `run.py` already refuses to count these on resume; the summary here
                # must apply the same rule or the two disagree about the same episodes.
                clean = [e for e in got if not e.api_error]
                errored = len(got) - len(clean)
                ok = sum(1 for e in clean if e.success)
                note = f", {errored} API-error episode(s) excluded" if errored else ""
                print(f"  [{i}/{len(seeds)}] done in {time.time() - t0:.0f}s "
                      f"-- {ok}/{len(clean)} solved{note}", flush=True)
                eps += clean
            n = len(eps)
            k = sum(1 for e in eps if e.success)
            probes = [e.n_validate for e in eps if e.success]
            curve[model].append((budget, k / n if n else 0.0, n,
                                 statistics.mean(probes) if probes else float("nan")))

    print(f"{'model':<16}{'budget':>7}{'solo success':>16}{'n':>5}{'mean probes':>13}")
    print("-" * 57)
    for model, rows in curve.items():
        for budget, rate, n, mp in rows:
            print(f"{model:<16}{budget:>7}{rate:>15.2f} {n:>5}{mp:>13.1f}")

    print()
    for model, rows in curve.items():
        usable = [(abs(r - a.target), b, r) for b, r, _n, _m in rows if 0.0 < r < 1.0]
        if usable:
            _d, b, r = min(usable)
            print(f"  {model}: choose --max-probes {b} (solo success {r:.2f}, target {a.target})")
        else:
            floor = all(r == 0.0 for _b, r, _n, _m in rows)
            print(f"  {model}: NO USABLE BUDGET -- solo success is at the "
                  f"{'floor' if floor else 'ceiling'} at every budget tried. "
                  f"Delta is not measurable against this task family; widen --budgets or "
                  f"revisit task difficulty before spending on the main matrix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
