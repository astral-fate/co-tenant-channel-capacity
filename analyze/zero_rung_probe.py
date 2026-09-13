"""Is the dirname-rung zero real, or a property of name-locating encoders?

    python analyze/zero_rung_probe.py

The per-attribute coders in `capacity.py` locate their observables by sender-chosen name, so
they collapse to 0 once names are closed, and Table 1 reports the dirname rung as zero. But the
joint decoder in `joint.py` finds its file and marker by *enumeration* (`list_dir`), not by name.
This asks the honest question the review raised: run that enumeration-based encoder at the
dirname-closure rung over the carriers that do not depend on a sender-chosen name --- size (the
body length of the single file) and mtime (the timestamp of the single marker) --- and see whether
a determined encoder recovers anything the name-locating coders missed.

A non-zero result means "dirname closure reaches zero" is a statement about the encoder family,
not a proof of non-interference, and the true residual after name closure is this number. A zero
means the substrate's name closure also removes the enumeration-reachable size/mtime observables
(e.g. by not preserving the suffixes the decoder keys on), and the clean zero stands.

Writes `results/capacity/zero-rung-probe.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from joint import search, measure, TRIALS  # noqa: E402

# Open-rung widths for the two name-independent carriers, from capacity.json.
CAP = json.loads((ROOT / "results" / "capacity" / "capacity.json").read_text(encoding="utf-8"))
OPEN = {m["attribute"]: int(m["bits_achieved"])
        for m in CAP["measurements"] if m["rung"] == "open"}


def main() -> int:
    caps = {c: OPEN[c] for c in ("size", "mtime") if OPEN.get(c, 0) > 0}
    print("ZERO-RUNG probe -- enumeration-based joint encoder under name closure")
    print("=" * 74)
    print(f"carriers under test: {caps}")
    out = []
    for rung in ("dirname", "sealed"):
        best, attempted, used = search(rung, dict(caps))
        # Also record the raw exact-trial count at the full width, to distinguish
        # "search found a smaller working width" from "nothing works at all".
        exact_full, total_full = measure(rung, dict(caps))
        out.append({
            "rung": rung,
            "carriers": list(caps),
            "bits": best,
            "sum_of_parts": attempted,
            "widths_used": used,
            "exact_at_full_width": f"{exact_full}/{TRIALS}",
            "trials": TRIALS,
        })
        verdict = f"{best} bits recovered" if best else "0 bits -- closure holds"
        print(f"  rung {rung:8}  -> {verdict}   (full-width {exact_full}/{TRIALS} exact)")
    dest = ROOT / "results" / "capacity" / "zero-rung-probe.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
