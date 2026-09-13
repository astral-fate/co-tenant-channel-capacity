"""
Check every headline number in the paper against the committed artifacts.

    python analyze/verify.py

Every number quoted in `paper/paper.md` or `paper/standard-v0.1.md` that comes from a run is
registered here with the computation that produces it. The script recomputes each one from the
committed data and prints it beside the value the paper claims. A FAIL row means the paper and
the artifact disagree, and it is a blocking error.

Why this exists. In the prior sprints, internal inconsistency between a paper and its own
artifacts was a *placement-costing* defect, not a cosmetic one: one project was marked down for an
unreconciled AUC discrepancy between its README (1.0000) and its appendix (0.9965), and another
for violating its own pre-specified gate in one seed without explanation. Both are avoidable by
recomputing rather than transcribing. The idea is borrowed, with thanks, from the
`secret-loyalties-testbed` repository, which ships exactly this check.

No GPU, no network, no API calls. Runs against committed JSONL only.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "detect"))

from measures import (  # noqa: E402
    baseline_validate_median, cluster_permutation_p, discover, deposits,
    fisher_exact, generation_cells, newcombe_diff_ci, pickups,
)
from monitors import ContentMonitor, SRMMonitor, auc, tpr_at_fpr, wilson  # noqa: E402

SEEDED = ("build", "deps", "tmp")
TOL = 5e-3


@dataclass
class Check:
    name: str
    claimed: Any
    computed: Any
    ok: bool
    note: str = ""


def _num_equal(a: Any, b: Any, tol: float = TOL) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def claims_in_paper() -> dict[str, float]:
    """Extract every `CLAIM[name]=value` marker embedded in the paper sources.

    The paper carries machine-readable claim markers alongside the prose, e.g.
    `CLAIM[srm_auc]=0.767`. Prose and marker are written together, so a number cannot be edited
    in one place and left stale in the other without this check firing.
    """
    out: dict[str, float] = {}
    # main.tex is the submitted artifact and must be scanned; the markdown drafts are scanned
    # too so a number cannot be corrected in one and left stale in the other.
    for name in ("main.tex", "paper.md", "standard-v0.1.md"):
        p = ROOT / "paper" / name
        if not p.exists():
            continue
        for m in re.finditer(r"CLAIM\[([a-z0-9_]+)\]=([-0-9.]+)", p.read_text(encoding="utf-8")):
            out[m.group(1)] = float(m.group(2))
    return out


def compute(runs) -> dict[str, float]:
    """Recompute every registered quantity from committed run data and from source.

    Capacity figures are recomputed from `src/srm.py` rather than transcribed, so the paper
    cannot drift from the implementation it describes. If someone edits the nominal bit budget
    or the closure ladder, the paper's numbers stop matching and this check fails loudly --
    which is the whole point of registering them.
    """
    got: dict[str, float] = {}

    # ---- claims derived from source, available with or without runs -----------------------
    try:
        sys.path.insert(0, str(ROOT / "src"))
        import srm  # noqa: PLC0415

        opn = srm.ClosurePolicy.from_rung("open").residual_bits()
        got["cap_open_bits"] = round(opn, 0)
        got["cap_content_bits"] = round(srm.ClosurePolicy.from_rung("content").residual_bits(), 0)
        got["cap_dirname_bits"] = round(srm.ClosurePolicy.from_rung("dirname").residual_bits(), 0)
        got["cap_existence_bits"] = round(srm.ClosurePolicy.from_rung("existence").residual_bits(), 0)
        got["cap_sealed_bits"] = round(srm.ClosurePolicy.from_rung("sealed").residual_bits(), 0)
        got["cap_content_pct_removed"] = round(
            100.0 * (opn - got["cap_content_bits"]) / opn, 1)
    except Exception:  # noqa: BLE001 - a missing srm must not abort the whole verifier
        pass

    if not runs:
        return got

    by = {}
    for r in runs:
        by.setdefault(r.condition, []).append(r)

    def rate(cond: str, fn) -> float:
        rs = by.get(cond, [])
        n = sum(len(r.episodes) for r in rs)
        k = len(set().union(*[fn(r) for r in rs])) if rs else 0
        return k / n if n else float("nan")

    for cond in ("open", "wipe", "scrub", "content", "dirname", "existence", "legit"):
        if cond in by:
            got[f"deposit_{cond}"] = round(rate(cond, deposits), 4)
            got[f"pickup_{cond}"] = round(rate(cond, pickups), 4)

    # Inheritance advantage
    # Delta is computed with GENERATION as the unit, per the pre-registration. Counting episodes
    # here doubled the apparent sample size and treated co-tenant agents as independent.
    if "open" in by and "wipe" in by:
        cells_o = generation_cells(runs, "open")
        cells_w = generation_cells(runs, "wipe")
        if cells_o and cells_w:
            d, p_perm, g_o, g_w = cluster_permutation_p(cells_o, cells_w)
            got["delta_open_wipe"] = round(d, 4)
            got["delta_p"] = round(p_perm, 6)
            got["delta_generations_open"] = g_o
            got["delta_generations_wipe"] = g_w
        # Episode-level figures are retained only to show the pseudo-replication gap.
        k1 = sum(k for k, _n in cells_o); n1 = sum(n for _k, n in cells_o)
        k2 = sum(k for k, _n in cells_w); n2 = sum(n for _k, n in cells_w)
        if n1 and n2:
            # NOT the reported inference: episode-level, so pseudo-replicated. Kept visible so
            # the difference from the generation-level permutation p is inspectable.
            got["delta_p_episodes_pseudoreplicated"] = round(fisher_exact(k1, n1, k2, n2), 6)
            lo, hi = newcombe_diff_ci(k1, n1, k2, n2)
            got["delta_ci_lo"] = round(lo, 4)
            got["delta_ci_hi"] = round(hi, 4)

    # Detectors
    srm = SRMMonitor(seeded_paths=SEEDED)
    con = ContentMonitor()
    pos = [r for r in runs if r.condition in ("open", "scrub", "content")]
    neg = by.get("legit", [])
    if pos and neg:
        def _b(r):
            b = baseline_validate_median(runs, r.model)
            return None if b == float("inf") else b
        p_srm = [srm.score_episode(r.events, ep["episode_id"], episode=ep, baseline_effort=_b(r))
                 for r in pos for ep in r.episodes]
        n_srm = [srm.score_episode(r.events, ep["episode_id"], episode=ep, baseline_effort=_b(r))
                 for r in neg for ep in r.episodes]
        p_con = [con.score_episode(ep) for r in pos for ep in r.episodes]
        n_con = [con.score_episode(ep) for r in neg for ep in r.episodes]
        got["srm_auc"] = round(auc(p_srm, n_srm), 3)
        got["content_auc"] = round(auc(p_con, n_con), 3)
        got["srm_tpr_at_fpr05"] = round(tpr_at_fpr(p_srm, n_srm, 0.05)[0], 3)
        got["content_tpr_at_fpr05"] = round(tpr_at_fpr(p_con, n_con, 0.05)[0], 3)

    return got


def ablation(runs) -> list[tuple[str, float, float]]:
    """Leave-one-feature-out ablation of the SRM detector.

    ActionLens was singled out by reviewers for reporting exactly this -- which component is
    actually doing the work. A detector whose score is carried entirely by one feature is a
    different (and more fragile) claim than one where the features share the load.
    """
    pos = [r for r in runs if r.condition in ("open", "scrub", "content")]
    neg = [r for r in runs if r.condition == "legit"]
    if not pos or not neg:
        return []

    def _b(r):
        b = baseline_validate_median(runs, r.model)
        return None if b == float("inf") else b

    def _sc(mon, rs):
        return [mon.score_episode(r.events, e["episode_id"], episode=e, baseline_effort=_b(r))
                for r in rs for e in r.episodes]

    base = SRMMonitor(seeded_paths=SEEDED)
    full = auc(_sc(base, pos), _sc(base, neg))

    rows: list[tuple[str, float, float]] = []
    nodiv = SRMMonitor(seeded_paths=SEEDED)
    nodiv_auc = auc([nodiv.score_episode(r.events, e["episode_id"]) for r in pos for e in r.episodes],
                    [nodiv.score_episode(r.events, e["episode_id"]) for r in neg for e in r.episodes])
    rows.append(("divergence", round(nodiv_auc, 3), round(nodiv_auc - full, 3)))

    for feat in list(SRMMonitor.WEIGHTS):
        m = SRMMonitor(seeded_paths=SEEDED)
        m.WEIGHTS = {k: (0.0 if k == feat else v) for k, v in SRMMonitor.WEIGHTS.items()}
        a = auc(_sc(m, pos), _sc(m, neg))
        rows.append((feat, round(a, 3), round(a - full, 3)))
    rows.sort(key=lambda t: t[2])
    return [("(full detector)", round(full, 3), 0.0)] + rows


def main() -> int:
    runs = discover(ROOT / "results" / "behavioural" / "runs")
    real = [r for r in runs if r.model != "mock"]

    claimed = claims_in_paper()
    computed = compute(runs)

    checks: list[Check] = []
    for name, val in sorted(claimed.items()):
        if name in computed:
            checks.append(Check(name, val, computed[name], _num_equal(val, computed[name])))
        else:
            checks.append(Check(name, val, "NOT COMPUTED", False,
                                "claim has no registered computation"))

    print(f"verifying {len(checks)} claimed numbers against committed artifacts")
    if not runs:
        print("  (no runs present)")
    if runs and not real:
        print("  NOTE: only scripted-fixture runs are present. Fixture numbers are pipeline "
              "validation, not results, and none may appear in the paper.")
    print()

    if checks:
        print(f"{'claim':<28}{'paper':>12}{'recomputed':>14}   verdict")
        print("-" * 68)
        for c in checks:
            v = "agree" if c.ok else "DISAGREE"
            print(f"{c.name:<28}{str(c.claimed):>12}{str(c.computed):>14}   {v}"
                  + (f"  ({c.note})" if c.note else ""))
    else:
        print("  no CLAIM[...] markers found in paper sources yet")

    rows = ablation(runs)
    if rows:
        print()
        print("SRM detector, leave-one-feature-out ablation (AUC)")
        print(f"{'feature removed':<22}{'AUC':>8}{'delta':>9}")
        print("-" * 39)
        for feat, a, d in rows:
            print(f"{feat:<22}{a:>8.3f}{d:>9.3f}")

    bad = [c for c in checks if not c.ok]
    print()
    if bad:
        print(f"{len(checks)} checks, {len(checks) - len(bad)} agree, {len(bad)} disagree")
        for c in bad:
            print(f"  FAIL {c.name}: paper says {c.claimed}, artifact says {c.computed}")
        return 1
    print(f"{len(checks)} checks, {len(checks)} agree, 0 disagree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
