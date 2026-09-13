"""Build `results/screen/calibration-grid.json`: solo success per model, per probe budget.

    python analyze/calibration_grid.py

Why a grid rather than one rate per model
-----------------------------------------
A single number per model hides the thing the gate is actually about. The calibration gate asks
whether solo success is strictly inside (0, 1) at *some* operating point, and a model can floor
at one budget and clear the window two budgets later. Reporting a pooled rate across budgets is
worse than uninformative: pooling a floored budget with a mixed one produces a figure inside
(0, 1) while no single operating point is, which manufactures a gate pass out of two results
that individually fail it.

Two rules the grid enforces, both learned the hard way in this project:

* **An API-error episode never enters a rate.** A provider cutting a run short says nothing about
  a model. Counting those as failures once reported a model that had just passed both capability
  probes as flooring at every budget tried.
* **The serving route is part of the identity.** The same open-weight model reached through two
  providers is two rows, not one: quantisation and decoding differ between stacks, and merging
  them would assert an equivalence nothing here establishes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALIB = ROOT / "results" / "behavioural" / "calibration"
OUT = ROOT / "results" / "screen" / "calibration-grid.json"

#: directory -> (display name, serving route). Order is the order the paper reports them.
SOURCES = [
    ("calib-full", "claude-haiku-4.5", "OpenRouter"),
    ("oss-120b-bedrock", "gpt-oss-120b", "Bedrock"),
    ("nova-lite", "amazon-nova-lite", "Bedrock"),
    ("nova-pro", "amazon-nova-pro", "Bedrock"),
    ("moonshotai-kimi-k2-5", "kimi-k2.5", "Bedrock"),
    ("qwen-qwen3-32b-v1-0", "qwen3-32b", "Bedrock"),
]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - half), min(1.0, c + half))


def episodes(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def sweep(directory: Path) -> dict[int, dict]:
    cells: dict[int, dict] = {}
    if not directory.exists():
        return cells
    for d in sorted(directory.glob("b*")):
        try:
            budget = int(d.name[1:])
        except ValueError:
            continue
        eps: list[dict] = []
        for f in d.rglob("episodes.jsonl"):
            eps.extend(episodes(f))
        clean = [e for e in eps if not e.get("api_error")]
        errored = len(eps) - len(clean)
        if not eps:
            continue
        k = sum(1 for e in clean if e.get("success"))
        n = len(clean)
        lo, hi = wilson(k, n)
        cells[budget] = {
            "solved": k, "n": n, "errored": errored,
            "rate": round(k / n, 3) if n else None,
            "ci": [round(lo, 2), round(hi, 2)] if n else None,
            "verdict": ("no clean episode" if n == 0 else
                        "window" if 0 < k < n else
                        "floor" if k == 0 else "ceiling"),
        }
    return cells


def build() -> dict:
    rows = []
    for directory, name, route in SOURCES:
        cells = sweep(CALIB / directory)
        if not cells:
            continue
        windows = sorted(b for b, c in cells.items() if c["verdict"] == "window")
        floors = sorted(b for b, c in cells.items() if c["verdict"] == "floor")
        rows.append({
            "model": name, "route": route, "source": directory,
            "budgets": {str(b): cells[b] for b in sorted(cells)},
            "windows": windows, "floors": floors,
            "clean_total": sum(c["n"] for c in cells.values()),
            "errored_total": sum(c["errored"] for c in cells.values()),
        })

    all_budgets = sorted({int(b) for r in rows for b in r["budgets"]})
    return {
        "note": ("Solo success in the no_substrate arm, per model per probe budget. Rates exclude "
                 "API-error episodes; the errored column reports how many were excluded. Routes "
                 "are reported because the same weights served by two providers are two rows."),
        "budgets": all_budgets,
        "n_models": len({r["model"] for r in rows}),
        "n_rows": len(rows),
        "rows": rows,
    }


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")

    bl = data["budgets"]
    print(f"{'model':22s} {'route':22s} " + "".join(f"{b:>8}" for b in bl))
    print("-" * (46 + 8 * len(bl)))
    for r in data["rows"]:
        cells = []
        for b in bl:
            c = r["budgets"].get(str(b))
            cells.append("  --  " if not c else f"{c['solved']}/{c['n']}".rjust(6))
        flag = f"  window@{r['windows']}" if r["windows"] else ""
        print(f"{r['model']:22s} {r['route']:22s} " + "".join(f"{c:>8}" for c in cells) + flag)
    print(f"\n{data['n_rows']} rows, {data['n_models']} distinct models -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
