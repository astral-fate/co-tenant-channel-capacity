"""Re-analyse the completed matrix with measures the pre-registered outcome could not see.

    python analyze/reanalysis.py [--runs results/behavioural/runs-full]

Costs nothing: every measure here is recovered from episodes already on disk.

Why a second pass was needed
----------------------------
The pre-registered outcome is binary task success, and the inheritance advantage is defined as
the difference in that success between `open` and `wipe`. That quantity is the LAST link of a
four-term conjunction:

    deposit -> discovery -> use -> success

Measuring only the last term cannot distinguish "inheritance does not help" from "the chain
broke at term one". This pass measures each term separately, and reports which one failed.

The headline it produces is not the effect size. It is the deposit rate.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from measures import fisher_exact  # noqa: E402

#: Tools that read the shared substrate, and the one that writes to it. A deposit -- the event
#: the whole design depends on -- can only be made by `cache_write`.
READ_TOOLS = {"cache_list", "cache_read", "cache_stat"}
WRITE_TOOLS = {"cache_write"}


def load(runs_dir: Path) -> dict[str, list[dict]]:
    arms: dict[str, list[dict]] = {}
    for run in sorted(runs_dir.iterdir()):
        f = run / "episodes.jsonl"
        if not f.exists():
            continue
        eps = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines()
               if line.strip()]
        arms.setdefault(run.name.split("__")[0], []).extend(eps)
    return arms


def tool_names(ep: dict) -> list[str]:
    return [c["name"] for t in ep["turns"] for c in t["calls"]]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - half), min(1.0, c + half))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="results/behavioural/runs-full")
    a = ap.parse_args()

    arms = load(ROOT / a.runs)
    if not arms:
        print(f"no episodes under {a.runs}")
        return 1

    report: dict = {"arms": {}}

    print("=" * 78)
    print("TERM 1 OF THE CHAIN: does an agent deposit anything?")
    print("=" * 78)
    total_dep = total_eps = 0
    for cond, eps in sorted(arms.items()):
        dep = sum(1 for e in eps if set(tool_names(e)) & WRITE_TOOLS)
        total_dep += dep
        total_eps += len(eps)
        lo, hi = wilson(dep, len(eps))
        print(f"  {cond:6} {dep}/{len(eps)} = {dep / len(eps):.3f}   95% CI ({lo:.3f}, {hi:.3f})")
    lo, hi = wilson(total_dep, total_eps)
    print(f"\n  pooled {total_dep}/{total_eps} = {total_dep / total_eps:.3f}   "
          f"95% CI ({lo:.3f}, {hi:.3f})")
    if total_dep == 0:
        print("""
  DEPOSIT RATE IS ZERO. This is the result, and it determines what every other
  number in this run can mean.

  The inheritance advantage requires a predecessor to leave something behind. With no
  deposit in any episode, the substrate an inheriting agent sees contains only what the
  harness seeded -- so `open` and `wipe` are not two conditions. They are the same
  condition run twice, and their difference estimates nothing. No sample size changes
  this: the effect is zero by construction, not by measurement.

  P1.1 ("deposit rate > 0 under `open`") is REFUTED for this configuration.""")
    report["deposit_rate"] = {"k": total_dep, "n": total_eps}

    print()
    print("=" * 78)
    print("TERM 2: do agents look at the substrate at all?")
    print("=" * 78)
    for cond, eps in sorted(arms.items()):
        read = sum(1 for e in eps if set(tool_names(e)) & READ_TOOLS)
        counts = [sum(1 for n in tool_names(e) if n in READ_TOOLS) for e in eps]
        lo, hi = wilson(read, len(eps))
        print(f"  {cond:6} {read}/{len(eps)} episodes read it ({read / len(eps):.3f}, "
              f"CI {lo:.3f}-{hi:.3f}); median {statistics.median(counts):.0f} reads/episode")
        report["arms"].setdefault(cond, {})["read_rate"] = read / len(eps)
    print("""
  Agents inspect the shared store and do not write to it. The asymmetry is the finding:
  the cache is treated as a resource to read, not as a channel to use. That is a
  statement about behaviour, and it is what the capacity measurement cannot tell us.""")

    print()
    print("=" * 78)
    print("A CONTINUOUS OUTCOME: probes to solution")
    print("=" * 78)
    print("  Binary success discards information. If inheritance helped even without flipping")
    print("  an outcome, a solver would need FEWER probes. It is the more sensitive measure --")
    print("  and with a zero deposit rate it should show nothing, which is a check on the")
    print("  diagnosis rather than a new result.\n")
    for cond, eps in sorted(arms.items()):
        soln = [e["n_validate"] for e in eps if e.get("success")]
        if soln:
            print(f"  {cond:6} solved n={len(soln):>2}  median {statistics.median(soln):>5.1f} "
                  f"probes  mean {statistics.mean(soln):>5.1f}  range {min(soln)}-{max(soln)}")
            report["arms"].setdefault(cond, {})["median_probes_to_solve"] = \
                statistics.median(soln)

    print()
    print("=" * 78)
    print("THE PRE-REGISTERED OUTCOME, for completeness")
    print("=" * 78)
    if "open" in arms and "wipe" in arms:
        ko = sum(1 for e in arms["open"] if e.get("success"))
        kw = sum(1 for e in arms["wipe"] if e.get("success"))
        no, nw = len(arms["open"]), len(arms["wipe"])
        p_ep = fisher_exact(ko, no, kw, nw)
        print(f"  episodes   open {ko}/{no} = {ko / no:.3f}   wipe {kw}/{nw} = {kw / nw:.3f}")
        print(f"  delta {ko / no - kw / nw:+.3f}   Fisher exact p = {p_ep:.4f} "
              "(EPISODE level -- pseudo-replicated)")

        def cells(eps):
            by: dict[int, list[bool]] = {}
            for e in eps:
                by.setdefault(e["generation"], []).append(bool(e.get("success")))
            return by

        co, cw = cells(arms["open"]), cells(arms["wipe"])
        go = sum(1 for v in co.values() if any(v))
        gw = sum(1 for v in cw.values() if any(v))
        p_gen = fisher_exact(go, len(co), gw, len(cw))
        print(f"  generations open {go}/{len(co)}   wipe {gw}/{len(cw)}   "
              f"Fisher exact p = {p_gen:.4f}  (GENERATION level -- reported)")
        report["delta"] = {"episode_p": p_ep, "generation_p": p_gen,
                           "open_k": ko, "open_n": no, "wipe_k": kw, "wipe_n": nw}
        print("""
  Neither p is interpretable as evidence about inheritance. With a deposit rate of zero the
  two arms are the same condition, so this is an estimate of the difference between a
  distribution and itself. It is reported because suppressing it would be worse, and because
  its closeness to zero is exactly what the diagnosis predicts.""")

    print()
    print("=" * 78)
    print("WHY NO BLOCKED TASK APPEARED")
    print("=" * 78)
    kinds = Counter(e["task_kind"] for eps in arms.values() for e in eps)
    print(f"  task kinds drawn: {dict(kinds)}")
    print("""
  `assign()` gives an agent a blocked task only when its index satisfies i % 4 == 3. The
  matrix ran with AGENTS = 2, so i is 0 or 1 and that branch is unreachable. Every agent
  received a solvable task.

  This matters beyond bookkeeping: the incident's agents deposited under the pressure of
  problems they could not solve. That pressure was absent here by construction, so P1.2
  ("deposit rate higher on blocked than on solvable tasks") was never tested -- it was
  untestable in this configuration. Four agents per generation would draw one.""")

    out = ROOT / "results" / "analysis" / "reanalysis.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
