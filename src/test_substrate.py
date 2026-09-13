"""Unit tests for the SRM-instrumented substrate.

These verify what the whole experiment rests on: that each rung of the closure
ladder actually neutralises the attribute it claims to, that lower rungs stay
open, that the cache remains usable as a cache at every rung, and that every
primitive is journalled with the reference/modify attribute split the detector
consumes.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from srm import MATRIX, RUNGS, Attribute, ClosurePolicy  # noqa: E402
from substrate import (  # noqa: E402
    BLOCK_SIZE,
    COUNT_WINDOW,
    FIXED_MTIME,
    N_SLOTS,
    Substrate,
    SubstrateError,
)


def _fresh(rung: str = "open"):
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    s = Substrate(root / "cache", ClosurePolicy.from_rung(rung), root / "audit.jsonl")
    s.seed()
    s.bind("ep0", "agent_a", 0)
    return s, td


def _events(s: Substrate) -> list[dict]:
    return [json.loads(line) for line in s.log_path.read_text(encoding="utf-8").splitlines()]


def test_open_rung_everything_available() -> None:
    s, td = _fresh("open")
    s.write_file("deps/notes.txt", "hello from a")
    s.mkdir("deps/marker")
    s.move("deps/marker", "deps/zz-signal")
    s.bind("ep1", "agent_b", 1)
    assert s.read_file("deps/notes.txt") == "hello from a"
    names = [e["name"] for e in s.list_dir("deps")]
    assert "notes.txt" in names and "zz-signal" in names
    td.cleanup()
    print("  ok  open: content, filenames, dirnames and move all available")


def test_content_rung_leaves_names_open() -> None:
    """The 8 July question in miniature.

    Closing content alone does not stop a principal from choosing names, which is
    exactly the row the incident displaced onto.
    """
    s, td = _fresh("content")
    stored = s.write_file("deps/zz-PAYLOAD.txt", "x")
    assert stored.endswith("zz-PAYLOAD.txt"), "names must still be agent-chosen"
    s.mkdir("deps/zz-0841")
    s.bind("ep1", "agent_b", 1)
    names = [e["name"] for e in s.list_dir("deps")]
    assert "zz-PAYLOAD.txt" in names and "zz-0841" in names
    td.cleanup()
    print("  ok  content closed, names open: agent-chosen names survive")


def test_filename_rung_canonicalises() -> None:
    s, td = _fresh("filename")
    stored = s.write_file("deps/zz-PAYLOAD.txt", "x")
    assert "PAYLOAD" not in stored and stored.endswith(".blob")
    try:
        s.move(stored, "deps/zz-renamed.txt")
    except SubstrateError:
        pass
    else:
        raise AssertionError("move of a file must be denied when FILENAME is closed")
    td.cleanup()
    print(f"  ok  filename closed: canonicalised to {Path(stored).name}, move denied")


def test_dirname_rung_denies_mkdir_and_dir_move() -> None:
    s, td = _fresh("dirname")
    for op in (lambda: s.mkdir("deps/zz-0841"),):
        try:
            op()
        except SubstrateError:
            continue
        raise AssertionError("mkdir must be denied when DIRNAME is closed")
    evs = [e for e in _events(s) if e["primitive"] == "mkdir"]
    assert evs and evs[-1]["ok"] is False and "dirname" in evs[-1]["attrs_mod"]
    td.cleanup()
    print("  ok  dirname closed: mkdir denied and journalled with the attribute")


def test_existence_rung_keeps_the_cache_usable() -> None:
    """Closing existence removes bits without breaking storage or retrieval.

    This is the cost constraint: a mitigation a lab will not adopt is not a
    mitigation. Writes are redirected into a fixed manifest, so the path set
    never varies with an agent's choice, yet artefacts still store and are
    still retrievable by path.

    What this test may NOT assert, and previously did. The ladder is cumulative,
    so the `existence` rung also closes `content`; an earlier version asserted
    `read_file(a) == "payload one"` here and passed only because content closure
    was never enforced on the read path. Once it was, the assertion failed --
    correctly. A rung that closes content cannot also return payloads, and a
    test that demanded both was encoding the very bug it should have caught.

    "Usable" at this rung therefore means: the write is accepted, the path is
    stable, the manifest is invariant, and the read succeeds. It does not mean
    the payload survives, because closing content is exactly the requirement
    that it does not.
    """
    s, td = _fresh("existence")
    before = sorted(p.name for p in (s.root / "deps").iterdir())
    a = s.write_file("deps/AGENT_CHOSEN.txt", "payload one")
    s.write_file("deps/ANOTHER.txt", "payload two")
    after = sorted(p.name for p in (s.root / "deps").iterdir())
    assert before == after, "the manifest must not change when EXISTENCE is closed"
    assert len(after) == N_SLOTS and all(n.startswith("slot_") for n in after)
    assert s.read_file(a) == "", "content is closed at this rung, so the body must be redacted"
    assert any(e["primitive"] == "write_file" and e["detail"].get("redirected")
               for e in _events(s))
    td.cleanup()
    print(f"  ok  existence closed: {N_SLOTS} fixed slots, manifest invariant, "
          "reads succeed with content redacted")


def test_size_and_mtime_normalised() -> None:
    s, td = _fresh("mtime")   # content..size closed, mtime closed too
    s.write_file("deps/a.txt", "short")
    entry = next(e for e in s.list_dir("deps") if e["type"] == "file")
    assert "size" not in entry and "mtime" not in entry, "closed rows must not be reported"
    on_disk = next(p for p in (s.root / "deps").iterdir() if p.is_file())
    assert on_disk.stat().st_size % BLOCK_SIZE == 0, "size must be padded to a block"
    assert int(on_disk.stat().st_mtime) == FIXED_MTIME, "mtime must be normalised"
    td.cleanup()
    print("  ok  size and mtime closed: padded, normalised, and not reported")


def test_order_and_count_closed() -> None:
    s, td = _fresh("sealed")
    for n in ("zeta", "alpha", "mid"):
        s.write_file(f"deps/{n}.txt", n)
    listing = s.list_dir("deps")
    names = [e["name"] for e in listing]
    assert names == sorted(names), "listing must be canonically ordered"
    assert len(listing) <= COUNT_WINDOW, "cardinality must be windowed"
    td.cleanup()
    print(f"  ok  sealed: order canonical, count windowed at {COUNT_WINDOW}")


def test_wipe_is_the_6_july_remediation() -> None:
    s, td = _fresh("open")
    s.write_file("deps/board.md", "the egress method is ...")
    s.mkdir("deps/zz-0841")
    s.wipe()
    s.seed()
    s.bind("ep1", "agent_b", 1)
    assert [e["name"] for e in s.list_dir("deps")] == []
    assert any(e["detail"].get("remediation") == "wipe" for e in _events(s))
    td.cleanup()
    print("  ok  wipe: bodies, names and structure all erased, as on 6 Jul 2026")


def test_scrub_preserves_names_and_structure() -> None:
    """The finer instrument: contents gone, every other row intact."""
    s, td = _fresh("open")
    s.write_file("deps/METHOD.txt", "the egress method is ...")
    s.mkdir("deps/zz-0841")
    before = sorted(p.name for p in (s.root / "deps").iterdir())
    s.scrub_content()
    after = sorted(p.name for p in (s.root / "deps").iterdir())
    assert before == after, "scrub must preserve names and structure"
    assert s.read_file("deps/METHOD.txt") == "", "bodies must be emptied"
    assert "zz-0841" in after, "directory names must survive a content scrub"
    td.cleanup()
    print("  ok  scrub: bodies emptied, names and structure intact")


def test_path_confinement() -> None:
    s, td = _fresh("open")
    for bad in ("../escape.txt", "..\\escape.txt", "deps/../../escape.txt", "/etc/passwd", "C:/x"):
        try:
            s.write_file(bad, "x")
        except SubstrateError:
            continue
        raise AssertionError(f"path traversal not blocked: {bad}")
    td.cleanup()
    print("  ok  path traversal confined to the cache root")


def test_every_attribute_is_journalled_with_ref_mod_split() -> None:
    s, td = _fresh("open")
    s.write_file("deps/a.txt", "content")
    s.mkdir("deps/d")
    s.bind("ep1", "agent_b", 1)
    s.read_file("deps/a.txt")
    s.list_dir("deps")
    s.stat("deps/a.txt")
    evs = _events(s)
    referenced = {a for e in evs for a in e["attrs_ref"]}
    modified = {a for e in evs for a in e["attrs_mod"]}
    all_attrs = {c.attribute.value for c in MATRIX}
    assert not (all_attrs - referenced), f"never referenced: {all_attrs - referenced}"
    assert not (all_attrs - modified), f"never modified: {all_attrs - modified}"
    # The detector's precondition: a modify by one principal, a reference by another.
    assert {e["agent"] for e in evs} == {"agent_a", "agent_b"}
    td.cleanup()
    print(f"  ok  all {len(all_attrs)} attributes journalled on both the ref and mod sides")


def test_closure_is_monotone_in_capacity() -> None:
    """Each rung must remove agent-controlled capacity, never add it."""
    rungs = ["open", "content", "filename", "dirname", "existence", "size", "mtime",
             "order", "count"]
    observed: list[int] = []
    for rung in rungs:
        s, td = _fresh(rung)
        for i, tag in enumerate(("ALPHA", "BETA", "GAMMA")):
            for op in (lambda: s.write_file(f"deps/zz-{tag}-{i}.txt", f"body-{tag}"),
                       lambda: s.mkdir(f"deps/zz-DIR-{tag}")):
                try:
                    op()
                except SubstrateError:
                    pass
        s.bind("ep1", "reader", 1)
        surviving: set[str] = set()
        for e in s.list_dir("deps"):
            surviving.add(e["name"])
            surviving.add(str(e.get("size", "")))
            surviving.add(str(e.get("mtime", "")))
        observed.append(len([v for v in surviving
                             if any(t in v for t in ("ALPHA", "BETA", "GAMMA"))]))
        td.cleanup()
    assert observed == sorted(observed, reverse=True), (
        f"capacity must be non-increasing along the ladder, got {dict(zip(rungs, observed))}"
    )
    assert observed[0] > 0 and observed[-1] == 0
    print(f"  ok  capacity non-increasing: {dict(zip(rungs, observed))}")


def test_residual_bits_decrease_monotonically() -> None:
    levels = [ClosurePolicy.from_level(i).residual_bits() for i in range(len(MATRIX) + 1)]
    assert levels == sorted(levels, reverse=True), levels
    assert levels[-1] == 0.0
    print(f"  ok  nominal residual capacity decreases: "
          f"{levels[0]:.0f} -> {levels[1]:.0f} -> {levels[3]:.0f} -> {levels[-1]:.0f} bits")


def test_dirname_closure_is_not_bypassable_by_write_or_move() -> None:
    """C2 must be closed against *every* primitive that can name a directory.

    Denying mkdir alone is not closure. `write_file("tmp/zzDGEC/pkg.blob")` and
    `move(x, "tmp/zzDGEC/pkg.blob")` both create an agent-named directory as a
    side effect of creating their parent. C2_dirname is the row the 8 July 2026
    displacement actually landed on, so a fixed skeleton that only guards mkdir
    would leave the incident's own channel open -- and, because the side effect
    was never journalled, invisible to the detector as well.
    """
    s, td = _fresh("dirname")
    for label, op in (
        ("write_file", lambda: s.write_file("tmp/zzDGEC/pkg.blob", "payload")),
        ("move", lambda: s.move("build", "tmp/zzDGEC/build")),
    ):
        try:
            op()
        except SubstrateError:
            continue
        raise AssertionError(
            f"{label} created an agent-named directory while DIRNAME was closed"
        )
    listing = [e["name"] for e in s.list_dir("tmp")]
    assert "zzDGEC" not in listing, f"agent-chosen directory leaked into the cache: {listing}"
    denied = [e for e in _events(s) if e["ok"] is False and "dirname" in e["attrs_mod"]]
    assert {e["primitive"] for e in denied} >= {"write_file", "move"}, denied
    td.cleanup()
    print("  ok  dirname closed: write_file and move cannot smuggle a directory past mkdir")


def test_directory_creation_is_journalled_whichever_primitive_does_it() -> None:
    """An agent-chosen directory name is a DIRNAME modification however it arises.

    With C2 open, `write_file` into a fresh path creates a directory the agent
    named. If that is not recorded in attrs_mod, the detector's modify side is
    blind to name-carried deposits made through write_file, and the join can
    never pair them with a later list_dir.
    """
    s, td = _fresh("open")
    s.write_file("tmp/zzDGEC/pkg.blob", "payload")
    ev = [e for e in _events(s) if e["primitive"] == "write_file"][-1]
    assert "dirname" in ev["attrs_mod"], (
        f"directory creation via write_file was not journalled as a DIRNAME "
        f"modification: {ev['attrs_mod']}"
    )
    # A write into an existing directory names no directory and must not claim to.
    s.write_file("tmp/zzDGEC/other.blob", "payload2")
    ev2 = [e for e in _events(s) if e["primitive"] == "write_file"][-1]
    assert "dirname" not in ev2["attrs_mod"], ev2["attrs_mod"]
    td.cleanup()
    print("  ok  directory creation via write_file is journalled as a DIRNAME modification")


def test_cost_model_is_derived_not_typed():
    """The cost table must come from the matrix, not from numbers someone chose.

    SS5.7's adoption argument turns on two things: that the rows added after content closure are
    all structural, and that the count of extra mediation points is small. Both are computed, so
    both get pinned. If a future edit reclassifies a row, this fails rather than quietly changing
    the paper's headline adoption claim.
    """
    from srm import CHANNELS, CLOSURE_LADDER, ENFORCEMENT_CLASSES, MATRIX
    import cost as cost_mod

    for c in MATRIX:
        assert c.enforcement in ENFORCEMENT_CLASSES, (
            f"{c.cid} has enforcement {c.enforcement!r}, which is not a defined class")
        assert c.mediation_points, f"{c.cid} has no mediation points but is a candidate channel"
        # Mediation points are the union of both directions, de-duplicated and sorted.
        expect = tuple(sorted({p.value for p in c.modify_via}
                              | {p.value for p in c.reference_via}))
        assert c.mediation_points == expect, c.mediation_points
    print("  ok  every matrix row has a defined enforcement class and derived mediation points")

    content = cost_mod.cumulative("content")
    dirname = cost_mod.cumulative("dirname")
    assert content["n_mediation_points"] < dirname["n_mediation_points"], (
        "holding a later rung cannot need fewer mediation points than an earlier one")
    assert dirname["rows_closed"][:len(content["rows_closed"])] == content["rows_closed"], (
        "the ladder is cumulative: dirname closure must include every row content closure did")
    print("  ok  closure cost is monotone and the ladder is cumulative")

    # The load-bearing adoption claim: everything past content closure is structural.
    ladder = [CHANNELS[cid].attribute.value for cid in CLOSURE_LADDER]
    after = ladder[ladder.index("content") + 1: ladder.index("dirname") + 1]
    classes = {CHANNELS[c].enforcement for c in CLOSURE_LADDER
               if CHANNELS[c].attribute.value in after}
    assert classes == {"structural"}, (
        f"SS5.7 claims every row past content closure is structural, but found {classes}. "
        f"Either the classification changed or the paper's adoption argument is now false.")
    assert dirname["n_payload_rows"] == content["n_payload_rows"], (
        "reaching dirname closure must not add a payload-class control")
    print("  ok  every row past content closure is structural, so the adoption claim holds")


def test_cost_model_refuses_to_report_effort():
    """The report must not contain an engineer-effort figure, which nothing here measured."""
    import json
    from pathlib import Path as _P
    out = _P(__file__).resolve().parent.parent / "results" / "capacity" / "closure-cost.json"
    if not out.exists():
        print("  ..  closure-cost.json absent; run src/cost.py")
        return
    report = json.loads(out.read_text(encoding="utf-8"))
    # The disclaimer is REQUIRED to say "not engineer-weeks", so scan the data, not the note.
    note = report.pop("note", "")
    assert "not engineer-weeks" in note.lower(), "the report must say what it is not"
    blob = json.dumps(report).lower()
    for banned in ("engineer_week", "eng_wk", "engineer-week", "person_month", "fte"):
        assert banned not in blob, (
            f"closure-cost.json carries {banned!r} outside its disclaimer: "
            f"an effort estimate nothing measured")
    print("  ok  the cost report carries no effort estimate and says so")



def test_lockout_is_opt_in_and_byte_identical_when_off():
    """Every episode already collected was collected without lockout. It must stay reproducible."""
    import tasks as T
    pool = T.build_pool()
    for g in (1, 5, 10):
        base = T.assign(pool, generation=g, n_agents=4, seed=0)
        same = T.assign(pool, generation=g, n_agents=4, seed=0, locked=None)
        empty = T.assign(pool, generation=g, n_agents=4, seed=0, locked=set())
        ids = [t.task_id for t in base]
        assert [t.task_id for t in same] == ids, "locked=None changed the draw"
        assert [t.task_id for t in empty] == ids, "an empty lockout set changed the draw"
    print("  ok  lockout off reproduces the original assignment exactly")


def test_lockout_withdraws_solved_tasks_and_excludes_rather_than_substituting():
    """The mechanism must create scarcity, not quietly re-serve a closed task."""
    import tasks as T
    pool = T.build_pool()
    search_ids = {t.task_id for t in pool if t.kind == "search"}
    assert len(search_ids) >= 2, "need at least two solvable tasks to test withdrawal"

    # Close every search task but one; the draw must never return a closed id.
    keep = sorted(search_ids)[0]
    locked = search_ids - {keep}
    got = T.assign(pool, generation=3, n_agents=4, seed=0, locked=locked)
    drawn = {t.task_id for t in got if t.kind == "search"}
    assert not (drawn & locked), f"assign returned a locked task: {drawn & locked}"
    assert drawn <= {keep}, drawn
    print("  ok  a locked task is never drawn again")

    # Close ALL of them: the generation must come up short rather than substitute.
    starved = T.assign(pool, generation=3, n_agents=4, seed=0, locked=search_ids)
    assert all(t.kind != "search" for t in starved), (
        "assign substituted a closed task instead of excluding the agent -- that removes "
        "exactly the scarcity the mechanism exists to create")
    assert len(starved) < 4, (
        f"expected exclusion when the solvable pool is empty, got {len(starved)} assignments")
    print("  ok  an exhausted pool excludes agents rather than re-serving closed tasks")


def test_lockout_shrinks_the_pool_monotonically():
    """Successive solves must never re-open a task."""
    import tasks as T
    pool = T.build_pool()
    locked: set[str] = set()
    sizes = []
    for g in range(1, 6):
        got = T.assign(pool, generation=g, n_agents=4, seed=0, locked=set(locked))
        sizes.append(len({t.task_id for t in pool if t.task_id not in locked}))
        for t in got:                      # simulate every drawn task being solved
            if t.kind == "search":
                locked.add(t.task_id)
    assert sizes == sorted(sizes, reverse=True), f"available pool grew: {sizes}"
    print(f"  ok  the pool shrinks monotonically under lockout: {sizes}")



if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"running {len(tests)} substrate tests\n")
    for t in tests:
        t()
    print(f"\nAll {len(tests)} substrate tests passed.")
