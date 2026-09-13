"""Measure the residual with ONE encoder carrying ONE payload, not by summing separate cells.

    python src/joint.py

Writes `results/capacity/joint.json`.

Why this exists
---------------
`capacity.py` measures each attribute in isolation and the report sums those cells into a
per-rung total. A reviewer put the objection precisely: the paper defines its method against
"summing declared field widths" and then reports totals that are sums of separately measured
widths. The per-attribute cells meet the paper's criterion. The totals never did, because no
encoder was ever asked to carry the total.

The objection also came with a concrete counterexample, and it is correct: `_code_existence`
writes one file per set bit into `build/`, so the number of entries in `build/` is a
deterministic function of the existence pattern. The bits credited to `count` are therefore
already spent by `existence`, and adding them double-counts.

So this module encodes a single payload across several attributes at once, in one substrate
state, and has a receiver recover the whole thing under the same zero-error criterion. What it
reports is a genuinely joint achievable rate.

What the joint coder deliberately does NOT use
----------------------------------------------
* `count` --- determined by `existence`, as above. Including it would double-count.
* `order`  --- measured at 0 bits even fully open, because `list_dir` sorts alphabetically.
* `content` --- so the figure that matters here is the residual AFTER content closure, which is
  the paper's actual claim.

The remaining carriers are laid out so they cannot interfere: the payload is split into disjoint
fields, each written into a different observable of the same small directory tree.
"""
from __future__ import annotations

import json
import math
import os
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from srm import ClosurePolicy  # noqa: E402
from substrate import Substrate, SubstrateError  # noqa: E402

NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

#: Zero-error criterion, matching capacity.py: a width is credited only if every trial recovers
#: the payload exactly.
TRIALS = 8

#: Epoch offset the mtime field is measured against, matching capacity.py.
MTIME_BASE = 1_000_000_000


def _measured_widths(rung: str) -> dict[str, int]:
    """Carrier widths taken from `results/capacity/capacity.json`, not hardcoded.

    WHY THIS IS DERIVED AND NOT A CONSTANT
    --------------------------------------
    These widths were once literals -- dirname 64, filename 64, existence 32, size 13, mtime 20,
    summing to 193 -- chosen to sit inside what `capacity.py` had measured per attribute at the
    time. Then the per-attribute search ceilings were raised, the single-attribute measurements
    grew by more than an order of magnitude, and these literals did not move. The joint figure
    stayed at 193 while the per-attribute sum went to 3814, and a sentence in the paper that had
    been arithmetically true -- that the gap between them is exactly the `count` row -- silently
    became false by a factor of 28.

    A reviewer found it by subtracting two numbers in the paper's own tables.

    The manuscript is protected against a stale number by build-time substitution, but a stale
    *relationship between* numbers is prose, and prose is not substituted. The structural fix is
    to stop the two measurements from being able to disagree: the joint coder now asks
    `capacity.py` what each carrier holds and uses that, so raising a ceiling moves both figures
    or neither.

    Widths are read AT THE RUNG BEING MEASURED, and a carrier the rung has closed is dropped.

    Reading content-rung widths at every rung was a real defect and it produced a textbook
    instance of the confound this project is about. The joint coder was handed a 602-bit filename
    field at the FILENAME rung -- where names are canonicalised -- so the decode could never
    succeed and the search reported 0 bits at every width. That zero would have entered the paper
    as "the channel is closed at this rung" when its actual cause was an encoder asking for a
    carrier that no longer exists. `dirname` alone measures 1318 bits at that same rung, which is
    what made the zero obviously wrong on inspection.
    """
    path = ROOT / "results" / "capacity" / "capacity.json"
    if not path.exists():
        raise SystemExit("results/capacity/capacity.json missing -- run: python src/capacity.py --json "
                         "results/capacity/capacity.json")
    cap = json.loads(path.read_text(encoding="utf-8"))
    at_rung = {m["attribute"]: int(m["bits_achieved"])
               for m in cap["measurements"] if m["rung"] == rung}
    carriers = ("dirname", "filename", "existence", "size", "mtime")
    missing = set(carriers) - at_rung.keys()
    if missing:
        raise SystemExit(f"capacity.json lacks {rung}-rung rows for {sorted(missing)}")
    # A carrier measured at zero for this rung is closed. Including it would make the joint coder
    # depend on something the rung removed, and report the resulting failure as channel closure.
    return {c: at_rung[c] for c in carriers if at_rung[c] > 0}


@dataclass
class JointResult:
    rung: str
    bits_attempted: int
    bits_recovered: int
    trials: int
    exact_trials: int
    carriers: list[str]
    excluded: dict[str, str]
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _encode(sub: Substrate, payload: int, widths: dict[str, int]) -> None:
    """Write one payload across every carrier, into one directory tree."""
    bits = payload
    take = {}
    for name, w in widths.items():
        take[name] = bits & ((1 << w) - 1)
        bits >>= w

    # A carrier absent from `widths` is one this rung has closed. The structure it occupies is
    # still written, using a fixed protocol constant, so the tree the receiver walks has the same
    # shape at every rung and a decode failure means a lost field rather than a lost path.
    def field(name: str) -> int:
        return take.get(name, 0)

    # dirname: a directory whose name is the field, in a fixed parent
    if "dirname" in widths:
        n = math.ceil(widths["dirname"] / math.log2(len(NAME_ALPHABET)))
        dname = _to_name(field("dirname"), n)
    else:
        dname = "fixed"
    sub.mkdir(f"build/{dname}")

    # filename: one file whose stem is the field, inside that directory
    if "filename" in widths:
        n = math.ceil(widths["filename"] / math.log2(len(NAME_ALPHABET)))
        fname = _to_name(field("filename"), n)
    else:
        fname = "fixed"
    # size: the body length carries its own field; content itself is never read back
    body = "x" * (1 + field("size"))
    sub.write_file(f"build/{dname}/{fname}.blob", body)

    # existence: presence or absence of protocol-named slots in a separate directory.
    #
    # Slots are DIRECTORIES, not files, and this matters. File-slot names are filenames, so
    # filename closure canonicalises them and the receiver loses the slot mapping -- the joint
    # coder then decoded existence as zero and every payload mismatched, at a rung where
    # capacity.py measures existence at 1024 bits. It measures that because its own existence
    # coder falls back to directory slots for exactly this reason. The two coders have to agree
    # about what an existence code is, or the joint figure is measuring a weaker code than the
    # per-attribute figure it is compared against.
    sub.mkdir("deps/slots")
    for i in range(widths.get("existence", 0)):
        if (field("existence") >> i) & 1:
            sub.mkdir(f"deps/slots/d{i:03d}")

    # mtime: the timestamp of a dedicated marker file. The substrate exposes no setter, so the
    # sender touches the file directly -- it is inside its own sandbox, exactly as capacity.py's
    # single-attribute mtime coder does.
    #
    # Written ONLY when mtime is a live carrier at this rung. Writing it unconditionally was a
    # defect with a misleading symptom: under filename closure the substrate canonicalises
    # "marker.stamp" to a content-derived name, so `_resolve` on the literal path raised
    # FileNotFoundError, `measure()` recorded a failed encode, and the search reported 0 bits at
    # every width -- for a rung where `dirname` alone carries 1318. A carrier the rung has closed
    # must not be touched by the encoder at all, or its absence is misread as the channel's.
    if "mtime" in widths:
        sub.write_file("deps/marker.stamp", "m")
        target = sub._resolve("deps/marker.stamp")        # noqa: SLF001
        os.utime(target, (MTIME_BASE + field("mtime"), MTIME_BASE + field("mtime")))


def _decode(sub: Substrate, widths: dict[str, int]) -> int | None:
    """Recover the payload using only list_dir and stat."""
    try:
        dirs = [e["name"] for e in sub.list_dir("build") if e.get("type") == "dir"]
        if len(dirs) != 1:
            return None
        dname = dirs[0]

        files = [e for e in sub.list_dir(f"build/{dname}") if e.get("type") != "dir"]
        if len(files) != 1:
            return None
        fname = files[0]["name"]
        if not fname.endswith(".blob"):
            return None
        size = files[0]["size"]

        present = {e["name"] for e in sub.list_dir("deps/slots") if e.get("type") == "dir"}
        # The marker exists only when mtime is a live carrier at this rung.
        if "mtime" in widths:
            stamp = [e for e in sub.list_dir("deps") if e["name"].endswith(".stamp")]
            if not stamp:
                return None
            mtime = stamp[0]["mtime"]
        else:
            mtime = MTIME_BASE
    except SubstrateError:
        return None

    # Decode ONLY the carriers this rung left open. A closed carrier was written as a fixed
    # protocol constant, and the substrate may have rewritten it -- under filename closure the
    # stored name is a content-derived identifier containing characters outside the coder's
    # alphabet, so decoding it raised ValueError and killed the whole measurement. Reading back a
    # field the rung removed is not a decode failure, it is a category error.
    got: dict[str, int] = {}
    try:
        if "dirname" in widths:
            got["dirname"] = _from_name(dname)
        if "filename" in widths:
            got["filename"] = _from_name(fname[: -len(".blob")])
    except ValueError:
        return None
    if "size" in widths:
        got["size"] = size - 1
    if "existence" in widths:
        got["existence"] = sum(1 << i for i in range(widths["existence"])
                               if f"d{i:03d}" in present)
    if "mtime" in widths:
        got["mtime"] = int(mtime) - MTIME_BASE

    out = 0
    for name in reversed(list(widths)):
        out = (out << widths[name]) | (got[name] & ((1 << widths[name]) - 1))
    return out


def _to_name(value: int, n_chars: int) -> str:
    base = len(NAME_ALPHABET)
    out = []
    for _ in range(n_chars):
        out.append(NAME_ALPHABET[value % base])
        value //= base
    return "".join(out)


def _from_name(name: str) -> int:
    base = len(NAME_ALPHABET)
    out = 0
    for ch in reversed(name):
        out = out * base + NAME_ALPHABET.index(ch)
    return out


def measure(rung: str, widths: dict[str, int], trials: int = TRIALS) -> tuple[int, int]:
    """Return (exact_trials, total_bits) for one joint width assignment at one rung."""
    total = sum(widths.values())
    exact = 0
    for t in range(trials):
        rng = random.Random(9000 + t)
        payload = rng.getrandbits(total)
        with tempfile.TemporaryDirectory(prefix="joint-") as td:
            root = Path(td) / "cache"
            log = Path(td) / "events.jsonl"
            sub = Substrate(root, ClosurePolicy.from_rung(rung), log)
            sub.bind(episode="joint", agent="sender", generation=1)
            sub.seed()
            try:
                _encode(sub, payload, widths)
            except (SubstrateError, OSError, FileNotFoundError):
                # A rung that closes a carrier this coder depends on makes encoding impossible.
                # That is a zero for this width assignment, not a crash.
                continue
            sub.bind(episode="joint", agent="receiver", generation=2)
            if _decode(sub, widths) == payload:
                exact += 1
    return exact, total


def _scaled(caps: dict[str, int], total: int) -> dict[str, int]:
    """Allocate `total` bits across carriers in proportion to their measured capacity.

    Every carrier is capped at what `capacity.py` measured for it alone, so the joint coder can
    never ask an attribute for more than that attribute demonstrably holds.
    """
    room = sum(caps.values())
    if total >= room:
        return dict(caps)
    # Every carrier keeps at least one bit. Dropping a carrier entirely would change the SHAPE of
    # the code rather than its width -- the encoder writes a fixed set of observables, and a
    # zero-width field would mean an empty directory name or a zero-length body, which the
    # substrate refuses. Keeping a floor of 1 keeps the code the same code at every width.
    out, spent = {}, 0
    keys = sorted(caps, key=lambda k: -caps[k])
    for i, k in enumerate(keys):
        if i == len(keys) - 1:
            out[k] = max(1, min(caps[k], total - spent))
        else:
            share = max(1, min(caps[k], round(total * caps[k] / room)))
            out[k] = share
            spent += share
    return out


def search(rung: str, caps: dict[str, int], trials: int = TRIALS) -> tuple[int, int, dict]:
    """Largest joint payload recovered exactly on EVERY trial, by binary search on the total.

    The per-attribute table reports what each carrier holds when it is the only thing carrying.
    Summing those is not a rate any encoder was asked for, which is this module's original point;
    but neither is the maximum a joint encoder can reach, because one encoder writing five
    carriers into one substrate state runs into interactions the separate measurements never see.
    So the joint figure is searched for, exactly as the per-attribute figures are, rather than
    assumed to be either the sum or some hand-chosen fraction of it.

    The gap between the sum and this number is therefore a MEASURED quantity. An earlier version
    asserted the gap was "exactly the count row", which was true at one set of ceilings and false
    at the next; nothing now asserts what the gap is, because the search reports it.
    """
    lo, hi, best, best_w = 1, sum(caps.values()), 0, {}
    while lo <= hi:
        mid = (lo + hi) // 2
        w = _scaled(caps, mid)
        exact, total = measure(rung, w, trials)
        if exact == trials and total >= mid - len(caps):
            best, best_w = total, w
            lo = mid + 1
        else:
            hi = mid - 1
    return best, sum(caps.values()), best_w


def main() -> int:
    # Widths are resolved per rung inside the loop, since a rung can close a carrier.
    excluded = {
        "content": "excluded so the figure is the residual AFTER content closure",
        "count": "deterministic function of the existence pattern -- summing it double-counts",
        "order": "measured 0 bits even fully open; list_dir returns entries sorted",
    }

    print("JOINT residual -- one encoder, one payload, one substrate state")
    print("=" * 74)
    print("Carriers available per rung, from results/capacity/capacity.json:")
    for r in ("content", "filename", "dirname"):
        w = _measured_widths(r)
        shown = ", ".join(f"{k}={v}" for k, v in sorted(w.items()))
        print(f"  {r:9} {sum(w.values()):>5} bits across {len(w)}  ({shown})")
    print()
    print("Excluded, and why:")
    for k, v in excluded.items():
        print(f"  {k:11} {v}")
    print()

    results = []
    for rung in ("content", "filename", "dirname"):
        widths = _measured_widths(rung)
        best, attempted, used = search(rung, widths)
        # A zero here is only channel closure if the coder could actually address the object.
        # At the `dirname` rung the substrate canonicalises names on write, and this encoder
        # still addresses its carriers by sender-chosen name -- the identical defect
        # `capacity._code_size` was rewritten to avoid, by reading the object's length out of a
        # directory listing instead. So a dirname zero is a limitation of THIS coder, not a
        # measurement that the channel is shut: `capacity.json` records 13 bits at that rung from
        # a name-independent read, and `size` is not neutralised until the fixed-manifest
        # (existence) closure redirects the write. Recorded rather than dropped, because the
        # gap between the two is itself the reconciliation the paper owes the reader.
        note = ""
        if rung == "dirname" and not best:
            note = ("joint coder inapplicable at this rung: it addresses carriers by "
                    "sender-chosen name, which dirname closure canonicalises. Not channel "
                    "closure -- see capacity.json (13 bits, name-independent listing read) "
                    "and the _code_size docstring. A joint figure here requires a "
                    "listing-addressed encoder.")
        r = JointResult(rung=rung, bits_attempted=attempted,
                        bits_recovered=best, trials=TRIALS,
                        exact_trials=TRIALS if best else 0,
                        carriers=list(used) if used else list(widths), excluded=excluded,
                        note=note)
        results.append(r)
        verdict = f"{best} bits recovered jointly" if best else "FAILED at every width"
        print(f"  rung {rung:9} sum of parts {attempted:>5}  ->  {verdict}")
        if used:
            print(f"    carriers used: " + ", ".join(f"{k}={v}" for k, v in sorted(used.items())))

    out = ROOT / "results" / "capacity" / "joint.json"
    out.write_text(json.dumps([r.as_dict() for r in results], indent=2), encoding="utf-8")
    print(f"\nwritten to {out}")

    got = next((r for r in results if r.rung == "content"), None)
    if got and got.bits_recovered:
        print(f"""
  A single encoder carries {got.bits_recovered} bits through a substrate with content
  closure applied, recovered exactly on {got.exact_trials}/{TRIALS} trials. This is the figure the
  paper's own criterion demands, and it is what should be reported as the residual --
  not the sum of separately measured cells.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
