"""Compile-check every code cell in the generated notebook.

A notebook is JSON, so a broken cell is invisible until Colab runs it — and a mangled
escape produces a syntax error the generator itself will happily emit. This catches that
before upload rather than after a 25 GB download.

Shell (`!`) and magic (`%`) lines are stripped along with their backslash continuations,
since those are not Python.

    python colab/check_notebook.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

NB = Path(__file__).resolve().parent / "kimi_selfhosted_e2e.ipynb"
CONT = "\\"


def python_only(src: str) -> str:
    keep: list[str] = []
    in_shell = False
    for line in src.split("\n"):
        stripped = line.strip()
        if in_shell:
            in_shell = stripped.endswith(CONT)
            continue
        if stripped.startswith(("%", "!")):
            in_shell = stripped.endswith(CONT)
            continue
        keep.append(line)
    return "\n".join(keep)


def main() -> int:
    nb = json.loads(NB.read_text(encoding="utf-8"))
    bad = 0
    for i, cell in enumerate(nb["cells"], 1):
        if cell["cell_type"] != "code":
            continue
        body = python_only("".join(cell["source"]))
        try:
            compile(body, f"<cell {i}>", "exec")
        except SyntaxError as e:
            bad += 1
            print(f"CELL {i}: {e.msg} (line {e.lineno})")
            for n, line in enumerate(body.split("\n"), 1):
                if abs(n - (e.lineno or 1)) <= 1:
                    print(f"    {n}: {line!r}")

    n_cells = len(nb["cells"])
    n_code = sum(1 for c in nb["cells"] if c["cell_type"] == "code")
    if bad:
        print(f"\n{bad} broken cell(s)")
        return 1
    print(f"OK — {n_cells} cells ({n_code} code) all compile")
    return 0


if __name__ == "__main__":
    sys.exit(main())
