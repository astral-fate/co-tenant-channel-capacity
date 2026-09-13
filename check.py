"""Run every check in the repository. No GPU, no network, no API keys.

    python check.py

Seven suites, in dependency order. Each is independently runnable; this exists so a reviewer can
establish in one command that the artifacts and the paper agree, without reading the code first.

    substrate      closure ladder semantics -- what each rung does and does not erase
    probe budget   the difficulty lever is enforced where the probes happen
    resume         a killed run loses no work and double-counts nothing
    pipeline       measures and detectors, against scripted fixtures only
    claims         every CLAIM[...] marker in the paper, recomputed from source and run data
    scorecard      verdict for each pre-registered prediction

`claims` is the one that matters most to a reader. Every run-derived number quoted in the paper
carries a machine-readable marker beside the prose, and the checker recomputes it rather than
trusting the transcription -- so a number cannot be corrected in one place and left stale in
another. In prior sprints that exact inconsistency was placement-costing, so it is checked
mechanically rather than by proofreading.

A non-zero exit means the repository disagrees with itself and the paper should not be submitted
until it does not.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SUITES: list[tuple[str, list[str]]] = [
    ("substrate", ["src/test_substrate.py"]),
    ("probe budget", ["runner/test_probe_budget.py"]),
    ("gpu autoconfig", ["runner/test_autoconfig.py"]),
    ("resume", ["runner/test_resume.py"]),
    ("pipeline", ["analyze/test_pipeline.py"]),
    ("claims", ["analyze/verify.py"]),
    ("scorecard", ["analyze/scorecard.py"]),
    # The figure is generated from the same claim table as the manuscript, so it can go stale the
    # moment an artifact changes. Checking it here gives it the property the paper already has:
    # a number in the figure cannot disagree with `results/`, because the build fails first. Three
    # slide figures drifted within a week for want of exactly this.
    ("figure", ["paper/figures/make_arch_svg.py", "--check"]),
]


def _ensure_fixtures() -> None:
    """Generate the scripted fixtures if they are absent.

    `analyze/test_pipeline.py` measures against `results/analysis/fixtures`, which is generated rather than
    committed -- so a fresh checkout, or the Colab code bundle (which ships code only), has no
    fixtures and the pipeline suite fails with "no runs under .../results/fixtures". That failure
    then trips the caller's staleness guard, whose message blames an incomplete or stale bundle.
    The bundle is neither; a generated directory simply was not generated yet.

    Regenerating is cheap, deterministic and uses no GPU, network or keys, so the honest fix is to
    do it here rather than to make every caller remember. Fixtures are scripted ground truth for
    pipeline validation and are never evidence about a model.
    """
    fixtures = ROOT / "results" / "analysis" / "fixtures"
    if fixtures.exists() and any(fixtures.glob("*/episodes.jsonl")):
        return
    maker = ROOT / "analyze" / "make_fixtures.py"
    if not maker.exists():
        return
    print("results/analysis/fixtures absent -- generating (scripted, no GPU, no network)", flush=True)
    subprocess.run([sys.executable, str(maker)], cwd=ROOT, capture_output=True)


def main() -> int:
    _ensure_fixtures()
    results: list[tuple[str, int, str]] = []
    for name, args in SUITES:
        script = ROOT / args[0]
        if not script.exists():
            results.append((name, 0, "skipped (not present)"))
            continue
        print(f"\n{'=' * 72}\n{name}\n{'=' * 72}", flush=True)
        proc = subprocess.run([sys.executable, str(script), *args[1:]], cwd=ROOT)
        tail = "ok" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
        results.append((name, proc.returncode, tail))

    print(f"\n{'=' * 72}\nsummary\n{'=' * 72}")
    width = max(len(n) for n, _, _ in results)
    for name, _code, tail in results:
        print(f"  {name:<{width}}  {tail}")

    bad = [n for n, c, _ in results if c != 0]
    skipped = [n for n, _, t in results if t.startswith("skipped")]
    print()
    if bad:
        print(f"{len(bad)} suite(s) failed: {', '.join(bad)}")
        return 1
    if skipped:
        # A skipped suite previously printed alongside "all N suites pass", which reads as a
        # clean run when a file is simply missing from the bundle -- the same class of false
        # pass this project has been bitten by before. Say what actually ran.
        print(f"{len(results) - len(skipped)}/{len(results)} suites pass; "
              f"{len(skipped)} SKIPPED (not present): {', '.join(skipped)}")
        print("A skipped suite is not a passing suite. If this is the Colab bundle, the")
        print("packaged file list is stale -- re-run colab/package_for_drive.py.")
        return 1
    print(f"all {len(results)} suites pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
