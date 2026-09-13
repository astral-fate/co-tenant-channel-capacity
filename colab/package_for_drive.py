"""Build the code bundle that the Colab notebook unpacks.

    python colab/package_for_drive.py

Writes `colab/ars-code.zip`. Upload that one file to Google Drive (the notebook expects it at
`MyDrive/ars/ars-code.zip` by default) and the notebook takes care of the rest.

Only the code needed to run and analyse episodes goes in -- about 700 KB. Results are deliberately
NOT bundled: they live in Drive and are written there directly, so a Colab session dying never
costs more than the episode in flight. The paper and docs are excluded too; they are not needed to
produce episodes and would only go stale in two places.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "ars-code.zip"

#: v2 bundle. `results/analysis/fixtures` is still NOT shipped -- it is generated -- but
#: `check.py` now creates it on demand, which is what the v1 bundle could not do.

#: Everything required to calibrate, run and analyse. Tests are included on purpose: being able to
#: run `check.py` inside Colab is how you confirm the bundle arrived intact before spending GPU.
INCLUDE = [
    "src/tasks.py", "src/srm.py", "src/substrate.py", "src/cost.py",
    # v2: capacity is measured rather than asserted, so the measurement module ships too.
    "src/capacity.py",
    "src/test_substrate.py", "src/test_cost.py",
    "runner/agent.py", "runner/providers.py", "runner/run.py", "runner/calibrate.py",
    "runner/mock.py", "runner/test_probe_budget.py", "runner/test_resume.py",
    "runner/test_autoconfig.py",
    "detect/monitors.py",
    "analyze/measures.py", "analyze/verify.py", "analyze/scorecard.py",
    "analyze/test_pipeline.py", "analyze/make_fixtures.py", "analyze/weaknesses.py",
    "check.py",
    "colab/gate.py",
]


def main() -> int:
    missing = [p for p in INCLUDE if not (ROOT / p).exists()]
    if missing:
        print("MISSING, refusing to build a partial bundle:")
        for m in missing:
            print(f"  {m}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in INCLUDE:
            z.write(ROOT / rel, rel)

    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]
    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT}")
    print(f"  {len(INCLUDE)} files, {size_kb:.0f} KB, sha256:{digest}")
    print()
    print("Next: upload it to Google Drive as  MyDrive/ars/ars-code.zip")
    print("Then open colab/ars_colab.ipynb in Colab and run the cells top to bottom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
