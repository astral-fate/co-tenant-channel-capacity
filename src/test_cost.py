"""
Tests for the P5.1 cost arm.

These guard the properties that make the cost number mean what the paper will
say it means. The most important is the first one: if more than one agent
principal ever touched this substrate, a drop in success at a high rung could
be read either as "closure damaged legitimate cache use" or as "closure removed
inheritance", and those are different claims. The arm is only interpretable if
there is demonstrably no inheritance in it to remove.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cost import (  # noqa: E402
    ABANDON_AFTER, CACHE_DIRS, EXPERIMENTER, Cell, cumulative_policies,
    isolated_policies, measure_placement, measure_success, run_episode,
    solo_probe_table, warm_cache, warm_survival,
)
from srm import Attribute, ClosurePolicy  # noqa: E402
from substrate import Substrate  # noqa: E402
from tasks import build_pool  # noqa: E402

BUDGETS = [4, 8, 12, 16, 20]
SEEDS = [11, 12, 13]


def _pool():
    return build_pool()


def _cells(rung_policies, budgets=BUDGETS, seeds=SEEDS):
    pool = _pool()
    solo = solo_probe_table(pool, seeds)
    out: dict[str, dict[int, float]] = {}
    for label, pol in rung_policies:
        for c in measure_success(pol, label, pool, budgets, seeds, solo):
            out.setdefault(label, {})[c.budget] = c.success
    return out


def test_arm_is_single_agent_with_no_inheritance() -> None:
    """Exactly one agent principal, and the cache warmed by the experimenter.

    This is what separates the cost claim from an inheritance claim.
    """
    pool = _pool()
    seeds = [11]
    solo = solo_probe_table(pool, seeds)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sub = Substrate(root / "cache", ClosurePolicy.from_rung("open"), root / "c.jsonl")
        sub.seed()
        warm_cache(sub, pool)
        for t in [x for x in pool if x.kind == "search"]:
            run_episode(sub, t, 12, random.Random(1), solo[(t.task_id, 11)])
        events = [json.loads(l) for l in sub.log_path.read_text(encoding="utf-8").splitlines()]

    principals = {e["agent"] for e in events}
    agents = principals - {EXPERIMENTER, "unbound"}
    assert agents == {"cost_agent"}, f"more than one agent touched the cost arm: {principals}"
    # And every write came from the experimenter: nothing was deposited by an agent.
    writers = {e["agent"] for e in events if e["attrs_mod"] and e["ok"]}
    assert writers <= {EXPERIMENTER, "unbound"}, f"an agent deposited into the cost arm: {writers}"
    print("  ok  cost arm is single-agent: no inheritance to confound the cost")


def test_open_cache_succeeds_cheaply() -> None:
    got = _cells([("open", ClosurePolicy.from_rung("open"))], budgets=[4])
    assert got["open"][4] == 1.0, got
    print("  ok  an open cache answers the task within 4 calls")


def test_closure_never_helps() -> None:
    """`open` dominates every closure at every budget: cost is never negative."""
    got = _cells(isolated_policies())
    for label, row in got.items():
        for b, v in row.items():
            assert v <= got["open"][b] + 1e-9, (
                f"{label} beat an open cache at budget {b}: {v} > {got['open'][b]}"
            )
    print("  ok  no closure ever improves task success (cost >= 0 everywhere)")


def test_content_closure_is_the_dominant_cost() -> None:
    """Scrubbing bodies is what actually costs task success."""
    got = _cells(isolated_policies())
    b = 12
    assert got["only_content"][b] < got["open"][b] - 0.5, got["only_content"]
    for cheap in ("only_dirname", "only_size", "only_order"):
        assert got[cheap][b] >= got["open"][b] - 1e-9, (cheap, got[cheap])
    print("  ok  content closure dominates; dirname/size/order are free on the read path")


def test_no_closure_can_show_a_cost_once_the_budget_is_generous() -> None:
    """Above the recomputation cost every rung converges: the curve is the result.

    This is why P5.1 must be reported as a curve. A single generous budget would
    make every closure look free, and a single tight one would make them all look
    ruinous; neither is a property of closure.
    """
    got = _cells(isolated_policies(), budgets=[20])
    assert all(abs(row[20] - 1.0) < 1e-9 for row in got.values()), got
    print("  ok  at a generous budget every rung reaches 1.00 -- cost is budget-relative")


def test_cumulative_ladder_adds_almost_nothing_after_content() -> None:
    """The marginal usefulness cost of the rungs beyond content is ~zero."""
    got = _cells(cumulative_policies(), budgets=[12, 16])
    labels = [l for l in got if l.startswith("L")]
    content = next(l for l in labels if l.endswith("_content"))
    last = labels[-1]
    for b in (12, 16):
        gap = got[content][b] - got[last][b]
        assert gap < 0.35, (
            f"closing every remaining row after content cost {gap:.2f} at budget {b}; "
            "if this is large the 'content dominates' claim is wrong"
        )
    print("  ok  after content is closed, the remaining eight rungs add little further cost")


def test_warm_cache_survival_matches_the_mechanism() -> None:
    """Retention explains the read-path costs: scrub erases, fixed slots evict."""
    pool = _pool()
    by = {label: warm_survival(pol, pool) for label, pol in isolated_policies()}
    assert by["open"] == 1.0, by
    assert by["only_content"] == 0.0, by
    assert by["only_existence"] < 1.0, by            # slot collisions evict
    for free in ("only_size", "only_mtime", "only_order", "only_count", "only_dirname"):
        assert by[free] == 1.0, (free, by[free])
    print(f"  ok  warm-cache survival explains the costs: "
          f"content {by['only_content']:.2f}, existence {by['only_existence']:.2f}")


def test_placement_prices_the_write_path_rows() -> None:
    """DIRNAME and EXISTENCE cost placement, which the read path cannot see."""
    pool = _pool()
    by = {label: measure_placement(pol, label, pool) for label, pol in isolated_policies()}
    assert by["only_dirname"].mkdir_ok == 0.0, by["only_dirname"]
    assert by["only_existence"].intent_honoured == 0.0, by["only_existence"]
    assert by["only_filename"].intent_honoured == 0.0, by["only_filename"]
    assert by["open"].intent_honoured == 1.0, by["open"]
    print("  ok  placement axis prices dirname/existence/filename, which axis A scores free")


def test_between_seed_spread_is_reported_not_pooled() -> None:
    pool = _pool()
    solo = solo_probe_table(pool, SEEDS)
    cells = measure_success(ClosurePolicy(rung="only_mtime", level=-1,
                                          closed={Attribute.MTIME}),
                            "only_mtime", pool, [4], SEEDS, solo)
    c = cells[0]
    assert c.n_seeds == len(SEEDS)
    assert c.success_min <= c.success <= c.success_max
    assert c.success_sd >= 0.0
    print(f"  ok  between-seed spread retained: {c.success:.2f} "
          f"[{c.success_min:.2f}, {c.success_max:.2f}], sd {c.success_sd:.3f}")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"running {len(tests)} cost-arm tests\n")
    for t in tests:
        t()
    print(f"\nAll {len(tests)} cost-arm tests passed.")
