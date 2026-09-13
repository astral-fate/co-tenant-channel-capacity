"""Discover a real shared store's limits instead of declaring them.

    python real/probe_limits.py /cache

Writes `results/real-substrate/real-limits.json`.

Why this exists
---------------
The synthetic substrate declares `MAX_FILE_BYTES = 8192` and `MAX_ENTRIES = 256`, and every
capacity figure downstream is bounded by those two constants. Two reviewers made the same
objection independently: deriving a search ceiling from a constant we chose does not remove the
circularity, it relabels it. The `content` row terminating at 8192 bits measures our declaration,
not a cache.

The defect is not that the constants are wrong. It is that they are *ours*. On a real store the
same quantities exist and are decided by the filesystem, the kernel and the registry -- so they
can be measured rather than asserted, and nobody can accuse the measurement of having been tuned.

This module measures them. It does the same thing to the substrate that `capacity.py` does to a
channel: binary-searches for the largest value that works, under a criterion that fails closed.

What it discovers
-----------------
* `name_max`      -- longest single path component the store accepts
* `max_file_bytes`-- largest body a single write survives
* `max_entries`   -- most entries one directory holds
* `mtime_ns`      -- whether sub-second timestamps survive a round trip, and at what resolution
* `case_sensitive`-- whether two names differing only in case can coexist
* `preserves_order` -- whether a listing returns creation order or sorted order

The last two are not in the synthetic model at all, and both bear on capacity: a case-insensitive
store halves the name alphabet, and a store that preserves creation order makes `order` a live
carrier where the synthetic substrate measured it at zero.

Honest scope
------------
This measures the mounted filesystem as seen through ordinary file operations. It does NOT
measure a package registry's own API limits, which are usually stricter. Tier 2 does that.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _try(fn) -> bool:
    """Run a probe, treating any refusal by the OS or the store as a failure, never a crash."""
    try:
        fn()
        return True
    except (OSError, ValueError):
        return False


def probe_name_max(base: Path, hi: int = 4096) -> int:
    """Longest single component the store accepts, by binary search."""
    lo, best = 1, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        p = base / ("n" * mid)
        if _try(lambda: (p.write_text("x", encoding="utf-8"), p.unlink())):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def probe_max_file_bytes(base: Path, hi: int = 64 * 1024 * 1024) -> int:
    """Largest single body a write survives. Capped at 64 MiB so a probe cannot fill a disk."""
    p = base / "sizeprobe.bin"
    lo, best = 1, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if _try(lambda: p.write_bytes(b"x" * mid)) and p.exists() and p.stat().st_size == mid:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if p.exists():
        p.unlink()
    return best


def probe_max_entries(base: Path, hi: int = 200_000) -> int:
    """Most entries one directory holds. Stops at `hi` and reports censoring rather than lying."""
    d = base / "entryprobe"
    d.mkdir(exist_ok=True)
    made = 0
    try:
        for i in range(hi):
            (d / f"e{i:07d}").write_text("x", encoding="utf-8")
            made += 1
    except OSError:
        pass
    finally:
        for f in d.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        d.rmdir()
    return made


def probe_mtime_resolution(base: Path) -> dict:
    """Does a sub-second timestamp survive a round trip, and at what granularity?"""
    p = base / "mtimeprobe"
    p.write_text("x", encoding="utf-8")
    want_ns = 1_000_000_000 * 1_000_000 + 123_456_789
    os.utime(p, ns=(want_ns, want_ns))
    got = p.stat().st_mtime_ns
    p.unlink()
    return {
        "requested_ns": want_ns,
        "observed_ns": got,
        "exact": got == want_ns,
        "resolution_ns": abs(got - want_ns) or 1,
    }


def probe_case_sensitivity(base: Path) -> bool:
    a, b = base / "CaseProbe", base / "caseprobe"
    try:
        a.write_text("A", encoding="utf-8")
        b.write_text("B", encoding="utf-8")
        distinct = a.exists() and b.exists() and a.read_text(encoding="utf-8") == "A"
    except OSError:
        distinct = False
    finally:
        for p in (a, b):
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
    return distinct


def probe_order_preserved(base: Path, n: int = 24) -> bool:
    """Does a listing return creation order, or sorted order?

    `order` measures 0 bits in the synthetic substrate because its listing sorts. If a real store
    returns creation order, `order` becomes a live carrier worth log2(n!) bits, and the synthetic
    model understates the channel rather than overstating it.
    """
    d = base / "orderprobe"
    d.mkdir(exist_ok=True)
    names = [f"z{i:03d}" for i in range(n)][::-1]      # created in reverse-sorted order
    for nm in names:
        (d / nm).write_text("x", encoding="utf-8")
        time.sleep(0.001)
    listed = [p.name for p in d.iterdir()]
    for p in d.iterdir():
        p.unlink()
    d.rmdir()
    return listed == names and listed != sorted(listed)


def main(argv: list[str]) -> int:
    target = Path(argv[0]) if argv else Path("/cache")
    if not target.is_dir():
        print(f"FAIL: {target} is not a directory. Mount the shared volume there first.")
        return 1

    base = target / "_probe"
    base.mkdir(parents=True, exist_ok=True)

    print(f"Probing {target} -- discovering limits rather than declaring them")
    print("=" * 78)

    name_max = probe_name_max(base)
    print(f"  name_max         {name_max:>12,} bytes")
    max_bytes = probe_max_file_bytes(base)
    print(f"  max_file_bytes   {max_bytes:>12,} bytes")
    max_entries = probe_max_entries(base)
    print(f"  max_entries      {max_entries:>12,} per directory")
    mt = probe_mtime_resolution(base)
    print(f"  mtime exact      {str(mt['exact']):>12}   resolution {mt['resolution_ns']:,} ns")
    case = probe_case_sensitivity(base)
    print(f"  case_sensitive   {str(case):>12}")
    order = probe_order_preserved(base)
    print(f"  order_preserved  {str(order):>12}")

    for p in sorted(base.iterdir(), reverse=True):
        try:
            p.unlink()
        except OSError:
            pass
    base.rmdir()

    report = {
        "target": str(target),
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "name_max": name_max,
        "max_file_bytes": max_bytes,
        "max_entries": max_entries,
        "max_entries_censored": max_entries >= 200_000,
        "mtime": mt,
        "case_sensitive": case,
        "order_preserved": order,
        "note": ("Measured against a real mount through ordinary file operations. Registry-level "
                 "API limits are stricter and are not measured here."),
    }
    blob = json.dumps(report, indent=2)
    # Written into the SHARED VOLUME first. A container started with --rm is deleted on exit and
    # takes /work with it, so an artifact written only inside the image is unreproducible the
    # moment the run ends -- which happened, and cost a full re-measurement. The named volume
    # outlives the container, so this is the copy that survives.
    (target / "real-limits.json").write_text(blob, encoding="utf-8")
    out = ROOT / "results" / "real-substrate" / "real-limits.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(blob, encoding="utf-8")
    except OSError:
        pass                                    # read-only image layer; the volume copy stands
    print(f"\nwritten to {target / 'real-limits.json'} (survives the container)")

    print("\nAgainst the synthetic substrate's declared constants:")
    print(f"  MAX_FILE_BYTES  declared      8,192   measured {max_bytes:>12,}")
    print(f"  MAX_ENTRIES     declared        256   measured {max_entries:>12,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
