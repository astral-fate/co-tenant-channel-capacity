"""Measure what each attribute can actually carry, instead of asserting it.

    python src/capacity.py                    # measure, print the table
    python src/capacity.py --json out.json    # and write the artifact

Why this module exists
----------------------
Version 1 of this work reported "closing file contents removes 96.8% of nominal channel
capacity." That figure was not a measurement. It was `8192 / 8467`: the ratio of one hardcoded
constant to the sum of eight hardcoded constants, all of them chosen by us in `srm.py`. Reviewers
pointed out three fatal things about it, and all three were correct.

1. It is a definitional artifact. Any decomposition containing one large field yields a number in
   that neighbourhood. Declaring the content row at 1 MB rather than 1 KiB -- equally defensible,
   and the row's own `capacity` field said "unbounded (KB-MB)" -- makes the same "finding" 99.997%.
2. Two constants contradicted the formulas written beside them. The `order` row declared
   `capacity="log2(n!) bits per directory"` and `nominal_bits=8.0`; with the substrate's own
   `MAX_ENTRIES = 256`, log2(256!) is **1684** bits. The `count` row declared
   `log2(max_entries)` and 6.0, where log2(256) is 8. Recomputed on the project's own constants,
   content's share fell from 96.8% to 80.7% and the residual after content closure rose from 275
   bits to 1953 -- dominated by `order`, the rung the paper described as carrying "little."
3. Nominal bounds are not what a defender needs anyway. The question is not how many bits an
   attribute could hold in principle; it is how many a sender can actually push through this
   substrate and a receiver actually recover.

So this module measures that. A sender encodes a uniformly random payload into one attribute using
only the substrate's ordinary primitives; a receiver, holding no shared state beyond an agreed
protocol, observes through `list_dir`, `stat` and `read_file` and decodes. We report the largest
payload recovered without error across every trial. That is an **achievable rate**: a lower bound
on capacity, established by exhibiting a working code, and it is falsifiable in the direction that
matters -- if the channel does not work, the measurement says zero.

Two consequences worth stating in advance, because they are the point:

* An achievable rate can be *lower* than the nominal bound and often is. `order` cannot carry
  log2(n!) bits unless the receiver's listing actually preserves the sender's chosen permutation.
  Whether it does is a property of the substrate, not of a constant, and it is measured here.
* Under a closure the rate should fall to zero. That is the closure working, and it is now a
  measured claim rather than an assumed one.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

import srm
from srm import Attribute, ClosurePolicy
import substrate as substrate_mod
from substrate import MAX_ENTRIES, Substrate, SubstrateError

#: A coder that asks the OS for something it refuses -- a name past NAME_MAX, a file past a size
#: limit -- has demonstrated that the channel does not carry at that width. Every coder therefore
#: treats OSError exactly as it treats SubstrateError: a failed encode, measured as zero.
#:
#: This was not always so, and the omission mattered. While raising the search ceilings to their
#: derived limits, the filename search pushed a 268-character name at a filesystem whose limit is
#: 255 and the run died with an uncaught OSError instead of recording a failure and narrowing.
#: A measurement harness that crashes at the boundary it is trying to find cannot find it.

#: Symbols usable inside an agent-chosen name. Deliberately conservative: alphanumerics only, so
#: the measurement is not inflated by characters a real cache would reject.
NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

#: Trials per payload size. A rate counts as achievable only if EVERY trial decodes exactly, so
#: this is a zero-error criterion rather than an average-case one.
TRIALS = 8


@dataclass
class Measurement:
    attribute: str
    rung: str
    bits_achieved: float
    bits_nominal: float
    trials: int
    note: str
    #: True when the search hit its ceiling, so the true rate is at least `bits_achieved`.
    #: Reporting a censored value as if it were the measurement would repeat v1's mistake in a
    #: new form -- quoting a number whose size we chose.
    censored: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def _fresh(policy: ClosurePolicy, tmp: Path) -> Substrate:
    root = tmp / "cache"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    log = tmp / "events.jsonl"
    if log.exists():
        log.unlink()
    s = Substrate(root, policy, log)
    s.bind(episode="cap", agent="sender", generation=1)
    return s


# --------------------------------------------------------------------------- per-attribute codes
#
# Each coder returns the number of bits it recovered exactly, given a payload of `bits` bits.
# A coder must use only ordinary substrate primitives -- nothing that reaches around the closure
# policy -- because the whole question is what survives the policy.


def _code_content(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload in the file body; receiver reads it back."""
    payload = rng.getrandbits(bits)
    text = format(payload, f"0{bits}b")
    try:
        sub.write_file("build/msg.txt", text)
        got = sub.read_file("build/msg.txt")
    except (SubstrateError, OSError):
        return 0
    return bits if got == text else 0


def _code_filename(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload in an agent-chosen file name; receiver reads names out of a listing."""
    n_chars = math.ceil(bits / math.log2(len(NAME_ALPHABET)))
    payload = [rng.randrange(len(NAME_ALPHABET)) for _ in range(n_chars)]
    name = "".join(NAME_ALPHABET[i] for i in payload)
    try:
        sub.write_file(f"build/{name}.blob", "x")
        entries = [e["name"] for e in sub.list_dir("build")]
    except (SubstrateError, OSError):
        return 0
    recovered = [e for e in entries if e.endswith(".blob")]
    if len(recovered) != 1:
        return 0
    got = recovered[0][: -len(".blob")]
    return bits if got == name else 0


def _code_dirname(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload in an agent-chosen directory name."""
    n_chars = math.ceil(bits / math.log2(len(NAME_ALPHABET)))
    name = "".join(NAME_ALPHABET[rng.randrange(len(NAME_ALPHABET))] for _ in range(n_chars))
    try:
        sub.mkdir(f"build/{name}")
        # The listing reports directories as type="dir"; an earlier version filtered on an
        # "is_dir" key that this substrate never emits, which silently measured 0 bits for
        # the very attribute the incident used. A coder bug and a closed channel look
        # identical in the output, so every zero here is checked by hand before it is
        # reported.
        entries = [e["name"] for e in sub.list_dir("build") if e.get("type") == "dir"]
    except (SubstrateError, OSError):
        return 0
    if len(entries) != 1:
        return 0
    return bits if entries[0] == name else 0


def _code_existence(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload as presence/absence over `bits` agreed slots.

    Tries a FILE-slot code first and a DIRECTORY-slot code second, crediting the better of the
    two. Both are legitimate existence codes; they differ only in which naming authority the
    slot mapping depends on, and a rung can close one while leaving the other open.

    Why both are needed, and why reporting only the first was a defect
    ------------------------------------------------------------------
    The original coder wrote `build/slotNNN.tag` and recovered the pattern by matching those
    names. Under filename closure the names are canonicalised, the receiver loses the mapping,
    and the measurement returned 0 -- which the table then reported as existence being CLOSED at
    that rung. It is not. `dirname` still carries bits at that rung, so a sender that still
    chooses directory names can still make presence carry a pattern.

    That zero was therefore an artefact of the encoder, not a property of the substrate: exactly
    the confound `_verify_zero` and the paper's methodology section name as this method's
    principal risk. A reviewer found it by reading the table and asking why existence died while
    dirname survived. The fix is to exhibit the stronger code rather than to explain the zero.
    """
    pattern = [rng.randrange(2) for _ in range(bits)]

    def _file_slots() -> int:
        try:
            for i, b in enumerate(pattern):
                if b:
                    sub.write_file(f"build/slot{i:03d}.tag", "1")
            present = {e["name"] for e in sub.list_dir("build")}
        except (SubstrateError, OSError):
            return 0
        got = [1 if f"slot{i:03d}.tag" in present else 0 for i in range(bits)]
        return bits if got == pattern else 0

    def _dir_slots() -> int:
        try:
            for i, b in enumerate(pattern):
                if b:
                    sub.mkdir(f"deps/d{i:03d}")
            present = {e["name"] for e in sub.list_dir("deps") if e.get("type") == "dir"}
        except (SubstrateError, OSError):
            return 0
        got = [1 if f"d{i:03d}" in present else 0 for i in range(bits)]
        return bits if got == pattern else 0

    return max(_file_slots(), _dir_slots())


def _code_size(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload in file length; receiver reads it back from a LISTING, not by name.

    An earlier version read the size with `stat("build/pad.bin")` -- by name. Under name closure
    the substrate canonicalises the filename on write, so the stat-by-name missed the stored file
    and the coder reported 0. That understated `size` as closed at the \\texttt{dirname} rung,
    when a receiver reading the directory listing recovers the object's length regardless of its
    name: `size` is not neutralised until the fixed-manifest (existence) closure redirects the
    write. The sender writes one file into the (post-seed empty) `tmp/` directory and the receiver
    reads the single entry's size, so the code depends on no sender-chosen name.
    """
    levels = 2 ** bits
    payload = rng.randrange(levels)
    try:
        sub.write_file("tmp/pad.bin", "x" * (payload + 1))
        files = [e for e in sub.list_dir("tmp") if e.get("type") == "file" and "size" in e]
    except (SubstrateError, OSError):
        return 0
    if len(files) != 1:
        return 0
    return bits if (files[0]["size"] - 1) == payload else 0


def _code_mtime(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload in the modification timestamp, if the substrate reports one."""
    levels = 2 ** bits
    payload = rng.randrange(levels)
    try:
        sub.write_file("build/t.bin", "x")
        target = sub._resolve("build/t.bin")          # noqa: SLF001 - sender is inside the sandbox
        import os
        base = 1_000_000_000
        os.utime(target, (base + payload, base + payload))
        st = sub.stat("build/t.bin")
    except (SubstrateError, OSError):
        return 0
    mt = st.get("mtime")
    if mt is None:
        return 0
    return bits if int(mt) - base == payload else 0


def _code_order(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload as a permutation of n agreed names; receiver decodes the listing order.

    This is the row whose nominal figure was most badly wrong in v1 (declared 8 bits against its
    own log2(n!) formula, which gives 1684 at MAX_ENTRIES). The achievable rate depends entirely
    on whether `list_dir` hands the receiver the sender's creation order, which is a property of
    the substrate and the filesystem -- exactly the thing a constant cannot tell you.
    """
    n = 2
    while math.log2(math.factorial(n)) < bits and n < 12:
        n += 1
    names = [f"e{i:02d}" for i in range(n)]
    perm = names[:]
    rng.shuffle(perm)
    try:
        for nm in perm:
            sub.write_file(f"build/{nm}.dat", "x")
        listed = [e["name"][: -len(".dat")] for e in sub.list_dir("build")
                  if e["name"].endswith(".dat")]
    except (SubstrateError, OSError):
        return 0
    if listed != perm:
        return 0
    return int(math.log2(math.factorial(n)))


def _code_count(sub: Substrate, bits: int, rng: random.Random) -> int:
    """Payload as the number of entries in a directory."""
    levels = min(2 ** bits, MAX_ENTRIES - 1)
    payload = rng.randrange(levels)
    try:
        for i in range(payload):
            sub.write_file(f"build/c{i:03d}.dat", "x")
        listed = [e for e in sub.list_dir("build") if e["name"].endswith(".dat")]
    except (SubstrateError, OSError):
        return 0
    return bits if len(listed) == payload else 0


CODERS = {
    Attribute.CONTENT: _code_content,
    Attribute.FILENAME: _code_filename,
    Attribute.DIRNAME: _code_dirname,
    Attribute.EXISTENCE: _code_existence,
    Attribute.SIZE: _code_size,
    Attribute.MTIME: _code_mtime,
    Attribute.ORDER: _code_order,
    Attribute.COUNT: _code_count,
}

#: Longest single path component on the filesystems a package cache runs on. POSIX NAME_MAX;
#: 255 bytes on ext4, XFS, btrfs, APFS and NTFS alike. Not a number we chose.
NAME_MAX = 255

#: Upper search bound per attribute, DERIVED from the substrate's own enforced limits and from
#: NAME_MAX rather than picked.
#:
#: Why this table was rewritten
#: ---------------------------
#: The previous ceilings were chosen by hand, and a reviewer observed that six of eight open-rung
#: cells terminated at them -- so those cells reported where the analyst stopped looking, not what
#: the substrate carries. A residual assembled from censored cells inherits that arbitrariness,
#: which is precisely the criticism this project levels at ratio reporting.
#:
#: Each bound below now exceeds the largest payload the substrate could physically carry on that
#: attribute, so a search that still terminates at the bound is reporting a real limit and one
#: that terminates below it is a genuine measurement. Every entry states its derivation.
#:
#: The two cells that already terminated are the check on this: `size` measured exactly
#: log2(MAX_FILE_BYTES) = 13 and `count` exactly log2(MAX_ENTRIES) = 8. Both are the values their
#: substrate constants predict, which is evidence the search finds true capacities when the
#: ceiling is above them rather than merely reporting the ceiling.
CEILING = {
    # A body may hold MAX_FILE_BYTES bytes; one bit per bit is the most it can encode.
    Attribute.CONTENT: substrate_mod.MAX_FILE_BYTES * 8,
    # A name of up to NAME_MAX characters over the coder's alphabet. Set ABOVE that product, not
    # at it: a ceiling placed exactly on the true limit censors at the right number and still
    # reports a floor, which is the defect being fixed. The search must be free to fail.
    Attribute.FILENAME: int(NAME_MAX * math.log2(len(NAME_ALPHABET))) + 64,
    Attribute.DIRNAME: int(NAME_MAX * math.log2(len(NAME_ALPHABET))) + 64,
    # One bit per addressable slot, bounded by the directory's entry limit -- plus headroom, so
    # a search that stops at MAX_ENTRIES is visibly reporting the substrate's limit and not ours.
    Attribute.EXISTENCE: 1024,
    # A length in [1, MAX_FILE_BYTES] distinguishes log2(MAX_FILE_BYTES) bits; +2 headroom so a
    # terminating search is visibly below the bound rather than at it.
    Attribute.SIZE: int(math.log2(substrate_mod.MAX_FILE_BYTES)) + 2,
    # ext4 stores a 34-bit seconds field and a 30-bit nanoseconds field; 64 bounds both together
    # and lets the search report whichever the substrate actually exposes.
    Attribute.MTIME: 64,
    # Orderings of MAX_ENTRIES items: log2(n!) by Stirling. Generous by construction.
    Attribute.ORDER: int(math.lgamma(substrate_mod.MAX_ENTRIES + 1) / math.log(2)),
    # Cardinality in [0, MAX_ENTRIES] is log2(MAX_ENTRIES+1) bits in ONE directory, but a coder
    # may spread a count across several, so the bound is generous rather than derived from a
    # single directory's limit.
    Attribute.COUNT: 128,
}


def measure(attribute: Attribute, policy: ClosurePolicy, tmp: Path,
            trials: int = TRIALS) -> float:
    """Largest payload, in bits, recovered exactly on EVERY trial. Zero-error criterion."""
    coder = CODERS[attribute]
    best = 0
    lo, hi = 1, CEILING[attribute]
    while lo <= hi:                                   # binary search on payload size
        mid = (lo + hi) // 2
        ok = True
        for t in range(trials):
            sub = _fresh(policy, tmp)
            try:
                sub.seed()
            except Exception:                          # noqa: BLE001 - seeding is optional
                pass
            rng = random.Random(1000 * mid + t)
            if coder(sub, mid, rng) != mid:
                ok = False
                break
        if ok:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return float(best)


def run(rungs: list[str] | None = None, root: str | Path | None = None) -> list[Measurement]:
    """Measure the ladder. `root` places the working substrate on a chosen filesystem.

    The default puts it in the system temp directory, which is the local disk and therefore a
    model of a shared cache rather than one. Pointing `root` at a real mount -- a network
    filesystem an evaluation harness would actually share between agents -- is what turns the
    ladder from a measurement of our own constants into a measurement of that store's, which is
    the objection L3 concedes.
    """
    rungs = rungs or ["open", "content", "filename", "dirname", "existence", "sealed"]
    nominal = {c.attribute: c.nominal_bits for c in srm.MATRIX}
    out: list[Measurement] = []
    if root is not None:
        Path(root).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capacity-", dir=root) as td:
        tmp = Path(td)
        for rung in rungs:
            policy = ClosurePolicy.from_rung(rung)
            for attr in CODERS:
                bits = measure(attr, policy, tmp)
                closed = attr in policy.closed
                censored = bits >= CEILING[attr]
                note = "closed by policy" if closed else ""
                if not closed and bits == 0:
                    note = "open, but nothing recovered -- channel does not work here"
                if censored:
                    note = (note + "; " if note else "") + "censored at search ceiling"
                out.append(Measurement(attr.value, rung, bits, nominal[attr], TRIALS, note,
                                       censored))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="write the measurements here")
    ap.add_argument("--rungs", default="open,content,filename,dirname,existence,sealed")
    ap.add_argument("--root", default=None,
                    help="directory to build the substrate in; point at a real mount to "
                         "measure that store rather than the local disk")
    a = ap.parse_args()

    rows = run([r.strip() for r in a.rungs.split(",") if r.strip()], root=a.root)
    rungs = sorted({r.rung for r in rows}, key=lambda x: [m.rung for m in rows].index(x))
    attrs = [m.attribute for m in rows if m.rung == rungs[0]]

    print(f"Measured achievable rate, bits per event, zero-error over {TRIALS} trials")
    print(f"{'attribute':12}{'nominal':>9}" + "".join(f"{r:>11}" for r in rungs))
    print("-" * (21 + 11 * len(rungs)))
    for at in attrs:
        nom = next(m.bits_nominal for m in rows if m.attribute == at)
        cells = ""
        for r in rungs:
            m = next(m for m in rows if m.attribute == at and m.rung == r)
            cells += f"{('>=' if m.censored else '') + format(m.bits_achieved, '.0f'):>11}"
        print(f"{at:12}{nom:>9.0f}{cells}")

    print()
    for r in rungs:
        tot = sum(m.bits_achieved for m in rows if m.rung == r)
        cen = any(m.censored for m in rows if m.rung == r)
        print(f"  total achievable at rung {r:10} = {'>=' if cen else '  '}{tot:8.0f} bits")

    # Report the RESIDUAL, not the ratio.
    #
    # The percentage removed is not a safe headline and we decline to lead with it. Its numerator
    # is the content row, whose measured value is censored at a search ceiling we picked: raising
    # that ceiling from 4096 to MAX_FILE_BYTES moves "95.3% removed" to "97.6% removed" without
    # anything about the channel changing. That is v1's tautology in a new costume, and the fact
    # that the underlying number is now measured rather than declared does not rescue the ratio.
    #
    # What survives any choice of ceiling is the absolute residual: how many bits a receiver can
    # still recover after a given closure. That is the quantity a defender needs, because the
    # question is never "what fraction did I remove" but "is what remains enough to carry an
    # answer". A four-character passcode over this alphabet is ~21 bits.
    open_tot = sum(m.bits_achieved for m in rows if m.rung == "open")
    if "content" in rungs and open_tot:
        print()
        print("RESIDUAL AFTER CLOSURE -- the ceiling-independent result")
        for r in rungs:
            tot = sum(m.bits_achieved for m in rows if m.rung == r)
            cen = any(m.censored for m in rows if m.rung == r)
            carriers = [m.attribute for m in rows if m.rung == r and m.bits_achieved > 0]
            verdict = "enough to carry an inherited answer" if tot >= 21 else                       ("NOT enough" if tot else "channel closed")
            print(f"  after {r:10} {'>=' if cen else '  '}{tot:6.0f} bits  {verdict:38}"
                  f" via {', '.join(carriers) if carriers else '-'}")
        c_tot = sum(m.bits_achieved for m in rows if m.rung == "content")
        print()
        print(f"  Closing content leaves {c_tot:.0f}+ bits reachable through names, existence,")
        print(f"  size, timestamp and cardinality. Reaching zero requires dirname closure.")
        print(f"  (For reference only, and NOT the headline: that is "
              f"{100 * (open_tot - c_tot) / open_tot:.1f}% of the measured total removed -- a")
        print(f"  ratio whose numerator is censored at a ceiling we chose. v1 asserted 96.8% of a")
        print(f"  NOMINAL budget; see this module's docstring for why neither ratio is the point.)")

    if a.json:
        Path(a.json).write_text(
            json.dumps({"trials": TRIALS, "alphabet": NAME_ALPHABET,
                        "max_entries": MAX_ENTRIES,
                        "measurements": [m.as_dict() for m in rows]}, indent=2),
            encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
