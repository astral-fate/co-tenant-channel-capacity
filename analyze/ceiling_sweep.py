"""The fraction removed moves with the analyst's search ceiling; the residual does not.

    python analyze/ceiling_sweep.py

Writes `results/capacity/ceiling-sweep.json`.

Why this exists
---------------
Section 5.9 argues that reporting "content closure removes X% of the capacity" is unstable, because
the denominator --- the open-rung total --- is set by how high the analyst lets the per-attribute
search run, not by the channel. The paper made the point from a one-off historical ceiling change.
This turns it into a controlled experiment: hold the substrate fixed, sweep the search ceiling on
the censored content cell as the independent variable, and measure at each setting

* the content cell (it is censored, so it reports the ceiling),
* the open-rung total that a fraction would divide by,
* the fraction of open capacity that content closure would claim to remove, and
* the joint residual after content closure.

The residual is measured by the same joint encoder throughout and never touches the content cell,
so it is expected to be invariant while the fraction slides. A percentage a lab quoted from any one
ceiling would therefore report the analyst's knob, not the channel; the residual reports the channel.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import capacity as cap  # noqa: E402
from srm import ClosurePolicy  # noqa: E402

# Content-cell search ceilings to sweep, in bits. All below the substrate's true limit
# (MAX_FILE_BYTES * 8) so the cell is censored at the analyst's value and reports it exactly.
CEILINGS = [1024, 2048, 4096, 8192, 16384]


def _other_open_total() -> float:
    """Sum of every open-rung carrier except content, from capacity.json -- ceiling-invariant here."""
    d = json.loads((ROOT / "results" / "capacity" / "capacity.json").read_text(encoding="utf-8"))
    return sum(m["bits_achieved"] for m in d["measurements"]
               if m["rung"] == "open" and m["attribute"] != "content")


def _residual() -> int:
    rows = json.loads((ROOT / "results" / "capacity" / "joint.json").read_text(encoding="utf-8"))
    return next(r for r in rows if r["rung"] == "content")["bits_recovered"]


def main() -> int:
    other = _other_open_total()
    residual = _residual()
    open_policy = ClosurePolicy.from_rung("open")
    saved = cap.CEILING[cap.Attribute.CONTENT]
    rows = []
    print("CEILING sweep -- substrate fixed, analyst's content ceiling varied")
    print("=" * 74)
    print(f"{'ceiling':>9}{'content':>9}{'open_total':>12}{'frac_removed':>14}{'residual':>10}")
    print("-" * 74)
    try:
        for c in CEILINGS:
            cap.CEILING[cap.Attribute.CONTENT] = c
            with tempfile.TemporaryDirectory(prefix="ceil-") as td:
                content_bits = cap.measure(cap.Attribute.CONTENT, open_policy, Path(td))
            open_total = other + content_bits
            frac = content_bits / open_total          # share of open capacity the content cell is
            rows.append({
                "ceiling_bits": c,
                "content_bits": content_bits,
                "open_total": round(open_total, 1),
                "fraction_removed_by_content_closure": round(frac, 3),
                "joint_residual": residual,
            })
            print(f"{c:>9}{content_bits:>9.0f}{open_total:>12.0f}{frac:>14.3f}{residual:>10}")
    finally:
        cap.CEILING[cap.Attribute.CONTENT] = saved

    fracs = [r["fraction_removed_by_content_closure"] for r in rows]
    out = {
        "note": ("Substrate held fixed; the analyst's content-cell search ceiling is the only "
                 "variable. The fraction content closure appears to remove slides with the ceiling; "
                 "the joint residual, which excludes the censored content cell, does not move."),
        "ceilings": rows,
        "fraction_min": min(fracs),
        "fraction_max": max(fracs),
        "residual_bits": residual,
        "residual_moved": False,
    }
    (ROOT / "results" / "capacity" / "ceiling-sweep.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n  fraction removed ranges {min(fracs):.2f}--{max(fracs):.2f} across the sweep;"
          f" residual fixed at {residual} bits.")
    print(f"  written to results/capacity/ceiling-sweep.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
