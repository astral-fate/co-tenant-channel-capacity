"""Residual left by a monitor as a function of WHICH carriers it inspects.

    python analyze/monitor_residual.py

Writes `results/capacity/monitor-residual.json`.

Why this exists
---------------
`src/joint.py` measures the residual after *content* closure: one encoder carrying one payload
across every carrier except content. That is the residual a **content-inspecting** monitor
leaves -- the control a payload-scanning DLP implements. A reviewer asked the operationally
sharper question: real data-loss-prevention also inspects file *paths*, so it would additionally
neutralise the two sender-chosen name carriers (filename, dirname). What residual survives a
**path-inspecting** monitor?

This answers it with the same joint encoder, the same content-closed substrate state, and the
same zero-error criterion over 8 trials. It does not re-estimate or hand-wave a number: it removes
the carriers the monitor is assumed to catch and re-runs the identical binary search over the
carriers that remain. The result is therefore directly comparable to the content-monitor residual
-- same method, same substrate, only the inspected carrier set differs.

Monitor scenarios (each strictly stronger than the one above)
-------------------------------------------------------------
  content        inspects file bodies              carriers left: dirname, filename, existence, size, mtime
  content+path   also inspects path strings        carriers left: existence, size, mtime

Why `existence` survives a path monitor
---------------------------------------
The name carriers (filename, dirname) encode in the sender-CHOSEN string of a path, which a
path-content monitor reads. The existence carrier encodes in the presence pattern of
protocol-fixed slot names (`d000`, `d001`, ...), whose strings carry nothing; the bit is in which
slots are present. A path-content DLP inspecting each path against a policy does not flag a benign
`d000` and does not model the expected slot set, so the presence-pattern channel passes it. A
stricter structural monitor that also modelled directory presence would additionally close
existence, leaving only {size, mtime}; that variant is reported alongside for completeness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from joint import _measured_widths, search, TRIALS  # noqa: E402

#: monitor -> the carriers it leaves uninspected (i.e. still available to the sender).
MONITORS = {
    "content":            ("dirname", "filename", "existence", "size", "mtime"),
    "content+path":       ("existence", "size", "mtime"),
    "content+path+struct": ("size", "mtime"),
}


def main() -> int:
    base = _measured_widths("content")  # content-rung widths for every carrier
    out = []
    print("MONITOR residual -- same joint encoder, content-closed substrate, 8-trial zero-error")
    print("=" * 78)
    for name, carriers in MONITORS.items():
        caps = {c: base[c] for c in carriers if c in base}
        best, attempted, used = search("content", caps)
        out.append({
            "monitor": name,
            "inspects": {"content": True,
                         "paths": "path" in name,
                         "structure": "struct" in name},
            "carriers_left": list(caps),
            "bits": best,
            "sum_of_parts": attempted,
            "widths_used": used,
            "trials": TRIALS,
        })
        print(f"  {name:20} leaves {list(caps)}")
        print(f"  {'':20}   -> {best} bits recovered jointly (sum of parts {attempted})")
    dest = ROOT / "results" / "capacity" / "monitor-residual.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
