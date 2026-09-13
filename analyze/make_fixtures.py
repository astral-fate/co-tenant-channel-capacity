"""Regenerate the scripted fixture sweep the regression suite runs against.

Kept separate from `results/behavioural/runs` so that live experiment output can never make the tests fail,
and so the tests can be re-run at any time without touching real data.

Run:  python analyze/make_fixtures.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "analysis" / "fixtures"

CHAN = "depositor,solo,solo,reader,reader,solo,reader,reader,solo,reader,reader,solo,reader,reader,solo"
LEGIT = ("legit,legit,solo,legit_consumer,legit_consumer,legit,legit_consumer,legit_consumer,"
         "solo,legit_consumer,legit,legit_consumer,legit_consumer,legit_consumer,solo")
NAME = ("namer,solo,solo,name_reader,name_reader,solo,name_reader,name_reader,solo,"
        "name_reader,name_reader,solo,name_reader,name_reader,solo")

PLAN = [
    ("open", CHAN), ("wipe", CHAN), ("scrub", CHAN),
    ("content", NAME), ("dirname", NAME), ("existence", NAME),
    ("no_substrate", "solo"), ("legit", LEGIT),
]


def main() -> int:
    import shutil
    if OUT.exists():
        shutil.rmtree(OUT)
    runner = ROOT / "runner" / "run.py"
    for cond, pol in PLAN:
        cmd = [sys.executable, "-u", str(runner), "--conditions", cond, "--models", "mock",
               "--seeds", "0", "--generations", "5", "--agents", "3", "--pool-size", "2",
               "--mock-policies", pol, "--outdir", str(OUT)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  {cond:<14} {'ok' if r.returncode == 0 else 'FAIL'}")
    print(f"\nfixtures written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
