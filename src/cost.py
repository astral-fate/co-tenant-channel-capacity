"""What each rung of closure costs to enforce, measured rather than estimated.

    python src/cost.py

Writes `results/capacity/closure-cost.json`.

Why this exists
---------------
Track 1's judging criterion has two halves: whether a third party could verify compliance
without access to the lab's network, and whether a lab would actually adopt the control. The
measurement in `capacity.py` answers neither. It says how much a channel carries, not what
closing it costs, and a residual figure with no cost beside it is a recommendation a lab can
decline for free.

What this module does NOT do
----------------------------
**It does not estimate engineer-weeks.** We have not built any of these controls in a production
artefact store, we have no telemetry from one, and a number invented here would be exactly the
kind of unmeasured quantity this project exists to argue against. An earlier version of this work
shipped a cost table whose numbers were arithmetic on constants the authors chose, and it was
wrong; the discipline since then is that a number appears only if something computed it.

What it does instead
--------------------
Two cost axes, both derived from the shared resource matrix, both checkable by a third party
from an API specification alone:

1. **Mediation points** -- how many distinct substrate primitives a control has to sit on. This
   is the integration surface. An auditor cannot see a lab's diff, but the lab's own API surface
   is public enough to count call sites, and the count does not depend on the implementation.

2. **Enforcement class** -- what the control has to *do* at those call sites. A control that
   constrains a namespace is O(1) per call and has no operating point. A control that reads or
   rewrites artefact bodies is O(bytes) and needs a threshold, which is where false positives
   live. These are different cost regimes, not different points on one scale.

The finding the two axes produce together is the one that matters for adoption, and it is
uncomfortable: the rung that reaches zero is `structural`, and the rung the July remediation
actually reached for is `payload`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from srm import CLOSURE_LADDER, CHANNELS, ENFORCEMENT_CLASSES, MATRIX  # noqa: E402

#: Rungs the paper reports, in ladder order. Each closes itself and every row before it.
REPORTED_RUNGS: tuple[str, ...] = ("open", "content", "filename", "dirname", "existence", "sealed")


def _rungs_to_level(rung: str) -> int:
    if rung == "open":
        return 0
    if rung == "sealed":
        return len(CLOSURE_LADDER)
    for i, cid in enumerate(CLOSURE_LADDER):
        if CHANNELS[cid].attribute.value == rung:
            return i + 1
    raise ValueError(f"unknown rung {rung!r}")


def _measured_bits() -> dict[str, float]:
    """Achievable bits per rung, from the capacity measurement -- not from nominal constants."""
    path = ROOT / "results" / "capacity" / "capacity.json"
    if not path.exists():
        return {}
    cap = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for m in cap["measurements"]:
        out[m["rung"]] = out.get(m["rung"], 0.0) + m["bits_achieved"]
    return out


def cumulative(rung: str) -> dict:
    """Cost of holding a rung: every row at or before it must stay closed simultaneously."""
    level = _rungs_to_level(rung)
    closed = [CHANNELS[cid] for cid in CLOSURE_LADDER[:level]]

    points: set[str] = set()
    for c in closed:
        points.update(c.mediation_points)

    classes: dict[str, int] = {}
    for c in closed:
        classes[c.enforcement] = classes.get(c.enforcement, 0) + 1

    return {
        "rung": rung,
        "level": level,
        "rows_closed": [c.cid for c in closed],
        "mediation_points": sorted(points),
        "n_mediation_points": len(points),
        "enforcement_classes": classes,
        "touches_payload": any(c.enforcement == "payload" for c in closed),
        "n_payload_rows": classes.get("payload", 0),
    }


def main() -> int:
    bits = _measured_bits()

    rows = []
    for rung in REPORTED_RUNGS:
        r = cumulative(rung)
        r["bits_achieved"] = bits.get(rung)
        rows.append(r)

    report = {
        "note": (
            "Structural cost model. Mediation points and enforcement classes are derived from "
            "the shared resource matrix and are checkable from an API specification without "
            "access to any lab's network. THESE ARE NOT ENGINEER-WEEKS and must never be "
            "reported as such."
        ),
        "enforcement_classes": ENFORCEMENT_CLASSES,
        "per_row": [
            {
                "cid": c.cid,
                "attribute": c.attribute.value,
                "enforcement": c.enforcement,
                "mediation_points": list(c.mediation_points),
                "n_mediation_points": len(c.mediation_points),
                "closable_by": c.closable_by,
                "cost_note": c.cost_note,
            }
            for c in MATRIX
        ],
        "per_rung": rows,
    }

    out = ROOT / "results" / "capacity" / "closure-cost.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("CLOSURE COST -- structural model, not engineer-weeks")
    print("=" * 78)
    print(f"  {'rung':10} {'rows':>4} {'mediation':>10} {'payload rows':>13} {'bits':>8}")
    for r in rows:
        b = "--" if r["bits_achieved"] is None else f"{r['bits_achieved']:.0f}"
        print(f"  {r['rung']:10} {r['level']:>4} {r['n_mediation_points']:>10} "
              f"{r['n_payload_rows']:>13} {b:>8}")

    print("\nPer row, in ladder order:")
    for c in MATRIX:
        print(f"  {c.attribute.value:10} {c.enforcement:11} "
              f"{len(c.mediation_points)} points  {c.closable_by}")

    # The adoption argument, stated only if the artifacts actually support it.
    dirname = next((r for r in rows if r["rung"] == "dirname"), None)
    content = next((r for r in rows if r["rung"] == "content"), None)
    if dirname and content and dirname["bits_achieved"] == 0:
        c_pay = CHANNELS["C0_content"].enforcement
        d_pay = CHANNELS["C2_dirname"].enforcement
        print(f"""
  The rung that reaches zero is enforced by a {d_pay} control; the rung the July
  remediation reached for is enforced by a {c_pay} control and leaves
  {content['bits_achieved']:.0f} bits reachable. Closure is not ordered by cost.""")
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
