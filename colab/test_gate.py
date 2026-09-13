"""Tests for the gate's answer extraction.

    python colab/test_gate.py

The original extractor scanned the entire response for alphabet characters. It passed against
Qwen3 -- whose reasoning is stripped into `step.reasoning`, leaving a bare "C D G" -- and produced
a false negative against every model that reasons in visible text, because such a response
restates the evidence and therefore mentions all ten letters.

That is a scorer defect masquerading as a capability finding, and it would have rejected an
otherwise usable model. These cases pin the shapes that actually occur.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate import EXPECTED, answer_letters  # noqa: E402

CASES: list[tuple[str, str, list[str]]] = [
    ("terse (Qwen3 after think-stripping)", "C D G", ["C", "D", "G"]),
    ("comma separated", "C, D, G", ["C", "D", "G"]),
    ("run together", "CDG", ["C", "D", "G"]),
    ("markdown emphasis", "**C D G**", ["C", "D", "G"]),
    ("trailing period", "C D G.", ["C", "D", "G"]),
    (
        "prose with 'and' -- the A and D inside 'and' must not be harvested",
        "The code contains C, D, and G.",
        ["C", "D", "G"],
    ),
    (
        "reasoning then answer -- the shape that broke the original",
        "I need to find which letters are in the code.\n\n"
        "From the clues:\n"
        "- AAA, BBB, EEE, FFF, HHH, JJJ, KKK each give 0 of 3, so those are all excluded.\n"
        "- CCC, DDD and GGG each give 1 of 3, so each appears exactly once.\n\n"
        "C D G",
        ["C", "D", "G"],
    ),
    (
        "reasoning then a sentence answer",
        "Working through the eliminations, the letters must be:\n\nC, D and G",
        ["C", "D", "G"],
    ),
    ("empty", "", []),
    ("none", None, []),
    ("whitespace only", "   \n\n  ", []),
    (
        "a genuinely wrong answer is still wrong",
        "After checking, the code contains A, B and E.",
        ["A", "B", "E"],
    ),
]

CHECKS: list[tuple[str, bool]] = []


def check(label: str, cond: bool) -> None:
    CHECKS.append((label, bool(cond)))


def main() -> int:
    for label, text, expect in CASES:
        got = answer_letters(text)
        check(f"{label}: {got}", got == expect)

    # The whole-text scan the fix replaces: assert the new extractor does NOT reproduce it.
    verbose = ("From the clues: AAA, BBB, EEE, FFF, HHH, JJJ, KKK give 0 of 3.\n\nC D G")
    naive = sorted({c for c in verbose.upper() if c in "ABCDEFGHJK"})
    check(f"the old whole-text scan would have returned {len(naive)} letters",
          len(naive) == 10)
    check("the fixed extractor returns exactly the answer",
          answer_letters(verbose) == EXPECTED)

    width = max(len(lbl) for lbl, _ in CHECKS)
    for lbl, ok in CHECKS:
        print(f"  {'ok  ' if ok else 'FAIL'} {lbl:<{width}}")
    bad = [lbl for lbl, ok in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(bad)}/{len(CHECKS)} checks pass")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
