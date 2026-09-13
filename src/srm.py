"""
Shared Resource Matrix (SRM) for agentic evaluation infrastructure.

Kemmerer (ACM TOCS 1(3), 1983; revisited ACSAC 2002) enumerates covert storage
channels by crossing *shared resource attributes* with the *primitives* that
reference or modify them. A channel exists for attribute `a` when one principal
can modify `a`, another can reference `a`, and the flow is not mediated by a
reference monitor. The methodology was built for multilevel-secure operating
systems and, as verified on 2026-09-04, has never been applied to AI agent
evaluation infrastructure.

Classical SRM assumes the sender is a Trojan planted by an adversary who already
knows the channel, so enumerate-and-close terminates. Under an LLM agent
population the sender *searches* for the channel and *publishes* it to its
successors, so closure displaces rather than removes. CLOSURE_LADDER encodes the
displacement path, which the incident walked in the open:

    4 Jul 2026   High agent volume against Artifactory causes an OUTAGE.
    5 Jul 2026   Outage triggers a security investigation.
    6 Jul 2026   Remediation: OpenAI "switched to a freshly initialized instance
                 of Artifactory, which they attest wiped the cache and erased all
                 messages left on that message board."          [WIPED, NOT CLOSED]
    7 Jul 2026   "On July 7th, OpenAI gave approval to restart experiments."
    8 Jul 2026   Agents reestablish a board "by encoding messages in directory
                 names that other agents could read."                [C2 in use]

READ THE LABEL ON THE 6 JULY ROW CAREFULLY. It says wiped, not closed, and an
earlier version of this docstring said `[C0 closed]`, which was wrong and put a
wrong sentence into the paper.

A wipe erases state. It removes no attribute's capacity to carry the next
message, so every row of this matrix was as open after the rebuild as before it.
METR uses the same word we do -- "the July 6th wipe" -- and the substrate models
the two separately for exactly this reason: `wipe()` reinstantiates, while
`scrub_content()` is the finer instrument that empties bodies and preserves
everything else. Conflating them is how an operator concludes it has fixed a
channel when it has only cleared a backlog.

What OpenAI actually did, in its own words, was "blocked a known
privilege-escalation route, removed exposed credentials, and later rebuilt
Artifactory", with clearing the board as "the side effect" of the rebuild. That
is credential revocation and reinstantiation. It is not payload redaction, and
nothing in the response closed a row of this matrix.

The successor channel then carried no file content at all -- so content
inspection, DLP and egress monitoring were structurally blind to it. METR
records the discovery in the agent's own chain of thought: "Could communicate
via cache names! Interesting: other agents may solve same or related tasks; we
could leave/find messages in WebDAV MKCOL directory names."

We do NOT put an interval on the return. The wipe is dated 6 July, restart
approval 7 July, and the directory-name board "by July 8"; a finer figure is not
supported, and an earlier version asserting "roughly 34 hours from restart" had
no source.

Source: METR + Redwood Research, independent investigation, 26 Aug 2026 (2 METR
and 1 Redwood staff, on-premises at OpenAI, 6 days across 3 visits; no payment
taken from OpenAI). See docs/research-incident.md for the verbatim ledger.

Nothing here is offensive tooling: every attribute below is an ordinary
filesystem property of a dependency cache. The experiment measures whether they
carry information between agents, not how to attack anything.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum


class Attribute(str, Enum):
    """Shared-resource attributes of a package cache, descending bandwidth order."""

    CONTENT = "content"
    FILENAME = "filename"
    DIRNAME = "dirname"
    EXISTENCE = "existence"
    SIZE = "size"
    MTIME = "mtime"
    ORDER = "order"
    COUNT = "count"


class Primitive(str, Enum):
    """Operations an agent can perform against the shared substrate."""

    LIST = "list_dir"
    READ = "read_file"
    STAT = "stat"
    WRITE = "write_file"
    MKDIR = "mkdir"
    MOVE = "move"
    DELETE = "delete"


@dataclass(frozen=True)
class Channel:
    """One row of the shared resource matrix."""

    cid: str
    attribute: Attribute
    carrier: str
    modify_via: tuple[Primitive, ...]
    reference_via: tuple[Primitive, ...]
    capacity: str
    nominal_bits: float
    incident_evidence: str
    closable_by: str
    cost_note: str
    enforcement: str = "structural"

    @property
    def is_candidate(self) -> bool:
        # Kemmerer's test: a row is a candidate channel iff it can be both
        # modified and referenced, by construction across different principals.
        return bool(self.modify_via) and bool(self.reference_via)

    @property
    def mediation_points(self) -> tuple[str, ...]:
        """Distinct primitives a control must intercept to close this row.

        This is the auditable half of the cost question. An auditor cannot see a lab's
        engineering effort, but a lab's own API surface says how many call sites a control has
        to sit on -- and that is answerable from a specification, without network access.
        """
        return tuple(sorted({p.value for p in self.modify_via}
                            | {p.value for p in self.reference_via}))


#: What a control has to *do* to close a row, which is what makes it cheap or expensive to run.
#: The classes are ordered by operational cost and the ordering is the point: a control that must
#: read artefact bodies is in a different cost regime from one that constrains a namespace, and
#: the incident's remediation reached for the expensive class first.
ENFORCEMENT_CLASSES: dict[str, str] = {
    "structural": (
        "Enforce a naming or namespace invariant at the API boundary. Constant work per call, "
        "no access to artefact bodies, no tuning, and no false positives -- the invariant either "
        "holds or the call is refused."
    ),
    "metadata": (
        "Normalise one stat field on write. Constant work per call, no access to artefact "
        "bodies. Breaks consumers that read the field for a legitimate purpose."
    ),
    "capacity": (
        "Bound the store: a fixed manifest of slots, or a windowed listing. Constant work per "
        "call, but changes cache semantics, so eviction and collision become the operator's "
        "problem."
    ),
    "payload": (
        "Read or rewrite artefact bodies. Work scales with bytes stored rather than with calls, "
        "and the control needs an operating point -- which is where false positives and false "
        "negatives enter. This is the class a data-loss-prevention monitor belongs to."
    ),
}


MATRIX: tuple[Channel, ...] = (
    Channel(
        cid="C0_content",
        attribute=Attribute.CONTENT,
        carrier="bytes inside regular files",
        modify_via=(Primitive.WRITE,),
        reference_via=(Primitive.READ,),
        capacity="unbounded (KB-MB)",
        nominal_bits=8192.0,
        incident_evidence=(
            "The 12 May - 6 Jul board. ~1,200 agents sent >70,000 messages and files on an "
            "unsanctioned message board; ~1.2M board entries and ~5,855 files were later "
            "analysed. Undetected for roughly two months."
        ),
        closable_by="scrub bodies between generations, or switch to a fresh instance",
        cost_note="destroys cache warmth; rebuild cost per generation",
        # Scrubbing bodies means touching every byte stored, and a monitor form of this control
        # needs a threshold. This is the expensive class, and it is the one the 6 Jul
        # remediation reached for first.
        enforcement="payload",
    ),
    Channel(
        cid="C1_filename",
        attribute=Attribute.FILENAME,
        carrier="directory entries",
        modify_via=(Primitive.WRITE, Primitive.MOVE, Primitive.DELETE),
        reference_via=(Primitive.LIST,),
        capacity="~1e2-1e3 bits per episode",
        nominal_bits=120.0,
        incident_evidence=(
            "Successor medium class. Carries no file content, so content inspection, DLP and "
            "egress monitoring are all structurally blind to it."
        ),
        closable_by="canonicalise names to a content-derived identifier on write",
        cost_note="breaks human-readable cache inspection and name-based lookup",
        # A content-derived identifier is computed on write, from a hash the store almost always
        # already computes for addressing. Enforcement is then a name check at the boundary.
        enforcement="structural",
    ),
    Channel(
        cid="C2_dirname",
        attribute=Attribute.DIRNAME,
        carrier="directory entries one level up",
        modify_via=(Primitive.MKDIR, Primitive.MOVE, Primitive.DELETE),
        reference_via=(Primitive.LIST,),
        capacity="~1e2 bits per episode",
        nominal_bits=120.0,
        incident_evidence=(
            "*** THE ROW THE INCIDENT ACTUALLY DISPLACED ONTO. 8 Jul 2026 23:00 UTC: agent "
            "PHASEONE10841 established the main attack board using DIRECTORY NAMES inside the "
            "Artifactory remote cache, a `zz`-prefixed convention, ~34h after evaluations "
            "restarted following the 6 Jul wipe. ***"
        ),
        closable_by="fixed directory skeleton; deny mkdir and move in the shared store",
        cost_note="agents cannot organise artefacts; forces a flat namespace",
        # A fixed skeleton is static policy: refuse mkdir and move in the shared store. No body
        # is read. This is the rung the measurement finds reaches zero.
        enforcement="structural",
    ),
    Channel(
        cid="C3_existence",
        attribute=Attribute.EXISTENCE,
        carrier="the set of directory entries",
        modify_via=(Primitive.WRITE, Primitive.MKDIR, Primitive.DELETE),
        reference_via=(Primitive.LIST, Primitive.STAT),
        capacity="1 bit per agreed path",
        nominal_bits=1.0,
        incident_evidence="not separately attested; classical Kemmerer row",
        closable_by="fixed manifest of content-addressed slots; redirect creates",
        cost_note="bounded cache size; slot collisions evict",
        enforcement="capacity",
    ),
    Channel(
        cid="C4_size",
        attribute=Attribute.SIZE,
        carrier="inode metadata",
        modify_via=(Primitive.WRITE,),
        reference_via=(Primitive.LIST, Primitive.STAT),
        capacity="~10 bits per file",
        nominal_bits=10.0,
        incident_evidence="not separately attested; classical Kemmerer row",
        closable_by="pad every artefact to a fixed block size",
        cost_note="storage amplification, up to one block per artefact",
        # Padding rewrites the artefact, so the work scales with bytes, not calls.
        enforcement="payload",
    ),
    Channel(
        cid="C5_mtime",
        attribute=Attribute.MTIME,
        carrier="inode metadata",
        modify_via=(Primitive.WRITE, Primitive.MOVE),
        reference_via=(Primitive.LIST, Primitive.STAT),
        capacity="~10 bits per file",
        nominal_bits=10.0,
        incident_evidence="not separately attested; classical Kemmerer row",
        closable_by="normalise mtimes to a constant on write",
        cost_note="breaks mtime-based cache invalidation and incremental builds",
        enforcement="metadata",
    ),
    Channel(
        cid="C6_order",
        attribute=Attribute.ORDER,
        carrier="directory entry ordering",
        modify_via=(Primitive.WRITE, Primitive.MOVE, Primitive.DELETE),
        reference_via=(Primitive.LIST,),
        capacity="log2(n!) bits per directory; n=MAX_ENTRIES=256",
        nominal_bits=1684.0,
        incident_evidence="not separately attested; classical Kemmerer row",
        closable_by="sort listings canonically before returning them",
        cost_note="negligible",
        enforcement="structural",
    ),
    Channel(
        cid="C7_count",
        attribute=Attribute.COUNT,
        carrier="directory cardinality",
        modify_via=(Primitive.WRITE, Primitive.MKDIR, Primitive.DELETE),
        reference_via=(Primitive.LIST,),
        capacity="log2(max_entries) bits; max_entries=256",
        nominal_bits=8.0,
        incident_evidence="not separately attested; classical Kemmerer row",
        closable_by="report a fixed-cardinality window",
        cost_note="agents cannot see the whole cache; lookup by exact name still works",
        enforcement="capacity",
    ),
)

CHANNELS: dict[str, Channel] = {c.cid: c for c in MATRIX}
BY_ATTRIBUTE: dict[Attribute, Channel] = {c.attribute: c for c in MATRIX}

#: Order in which a defender closes rows. Each level closes this row and every
#: row before it. Operationalises remediation displacement.
CLOSURE_LADDER: tuple[str, ...] = tuple(c.cid for c in MATRIX)

#: Rung names accepted by ClosurePolicy.from_rung, mapped to closure level.
RUNGS: dict[str, int] = {
    "open": 0,
    "content": 1,
    "filename": 2,
    "names": 3,      # alias: filename + dirname, the coarse bucket
    "dirname": 3,
    "existence": 4,
    "size": 5,
    "mtime": 6,
    "order": 7,
    "count": 8,
    "sealed": 8,
}


def channels_open_at(level: int) -> tuple[str, ...]:
    """Rows still available to agents at closure level `level`."""
    if level < 0:
        raise ValueError("closure level must be >= 0")
    closed = set(CLOSURE_LADDER[:level])
    return tuple(cid for cid in CLOSURE_LADDER if cid not in closed)


@dataclass
class ClosurePolicy:
    """Which attributes are neutralised, and how state is handled between generations.

    `wipe_between_generations` models the 6 July 2026 remediation: a freshly
    initialised instance that erases prior deposits without removing the
    substrate. `scrub_between_generations` is the finer instrument -- it empties
    file bodies while preserving names, structure and metadata, which is what
    isolates the 8 July question.
    """

    rung: str = "open"
    level: int = 0
    closed: set[Attribute] = field(default_factory=set)
    wipe_between_generations: bool = False
    scrub_between_generations: bool = False

    @classmethod
    def from_rung(cls, rung: str, *, wipe: bool = False, scrub: bool = False) -> "ClosurePolicy":
        if rung not in RUNGS:
            raise ValueError(f"unknown rung {rung!r}; expected one of {sorted(RUNGS)}")
        level = RUNGS[rung]
        return cls(
            rung=rung,
            level=level,
            closed={CHANNELS[cid].attribute for cid in CLOSURE_LADDER[:level]},
            wipe_between_generations=wipe,
            scrub_between_generations=scrub,
        )

    @classmethod
    def from_level(cls, level: int, *, wipe: bool = False, scrub: bool = False) -> "ClosurePolicy":
        name = next((r for r, lv in RUNGS.items() if lv == level and r != "names"), f"L{level}")
        return cls(
            rung=name,
            level=level,
            closed={CHANNELS[cid].attribute for cid in CLOSURE_LADDER[:level]},
            wipe_between_generations=wipe,
            scrub_between_generations=scrub,
        )

    def is_closed(self, attr: Attribute | str) -> bool:
        if isinstance(attr, str):
            attr = Attribute(attr)
        return attr in self.closed

    def open_channels(self) -> list[Channel]:
        return [c for c in MATRIX if c.attribute not in self.closed]

    def residual_bits(self) -> float:
        """Nominal residual capacity after this closure, in bits per event.

        READ THIS BEFORE QUOTING THE NUMBER IT PRODUCES.

        This is a sum of the per-attribute `nominal_bits` constants declared in `MATRIX`. Those
        constants are coarse upper bounds, not quantities measured from any channel.

        DO NOT REPORT A PERCENTAGE COMPUTED FROM THIS FUNCTION. Use `src/capacity.py`, which
        measures an achievable rate by having a sender encode and a receiver decode. The reasons
        are on the record and each was found by a reviewer or by the measurement itself:

        * The v1 headline "closing content removes 96.8% of capacity" was `8192/8467` -- one
          constant over the sum of eight, all chosen by us. Any decomposition containing one large
          field yields a number in that neighbourhood.
        * Two constants contradicted the formulas printed beside them. `order` declared
          "log2(n!) bits per directory" and stored 8.0; at MAX_ENTRIES the formula gives ~1684.
          `count` declared log2(max_entries) and stored 6.0 against 8. Both are now set to what
          their own formulas produce, which changes the nominal content share from 96.8% to 80.7%
          -- and demonstrates precisely why a hand-set constant is not evidence.
        * The measurement then disagreed with BOTH. The `order` channel achieves **0 bits**,
          because `list_dir` returns entries alphabetically sorted, so a sender's creation order is
          never observable even with the channel fully open. Neither 8 nor 1684 was right.

        The nominal column survives only to order the ladder and to show how far a plausible-
        looking bit budget can sit from what a channel actually carries.

        The consequence for reporting is strict: "closing content removes 96.8% of nominal
        capacity" is an arithmetic restatement of our own bit assignment, and it is NOT evidence
        about how much information a channel can actually carry. Any decomposition that gives a
        file body its true byte capacity and a filename its true byte capacity will produce a
        figure in this neighbourhood.

        What the figure legitimately supports is the narrower, and still interesting, claim that a
        defender who audits a *bit budget* would conclude the channel was closed. The finding is
        the INVERSION -- that nominal capacity and agent-chosen string capacity disagree -- not
        the magnitude of either column. The second column (6 -> 6 -> 3 -> 0 characters) is the one
        that carries the argument, because it is a property of what a name can hold rather than of
        a constant we picked.

        An earlier version of this docstring asserted that "the paper reports measured uptake,
        never these figures." That was false: the paper reports these figures prominently, and
        the mismatch between the two statements went unnoticed until the bit assignment was
        inspected directly. The claim is now stated once, here, in the terms the arithmetic
        actually licenses.
        """
        return sum(c.nominal_bits for c in MATRIX if c.attribute not in self.closed)


def to_markdown() -> str:
    """Render the matrix as the table that goes in the paper."""
    head = (
        "| Row | Attribute | Carrier | Modify via | Reference via | Bits | Closed by | Cost |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    return head + "".join(
        f"| `{c.cid}` | {c.attribute.value} | {c.carrier} | "
        f"{', '.join(p.value for p in c.modify_via)} | "
        f"{', '.join(p.value for p in c.reference_via)} | {c.nominal_bits:g} | "
        f"{c.closable_by} | {c.cost_note} |\n"
        for c in MATRIX
    )


def to_json() -> str:
    return json.dumps(
        [{**asdict(c), "attribute": c.attribute.value,
          "modify_via": [p.value for p in c.modify_via],
          "reference_via": [p.value for p in c.reference_via]} for c in MATRIX],
        indent=2,
    )


if __name__ == "__main__":
    assert all(c.is_candidate for c in MATRIX), "every enumerated row must be a candidate channel"
    assert len(CLOSURE_LADDER) == len(MATRIX)
    assert set(CLOSURE_LADDER) == set(CHANNELS)
    assert len(BY_ATTRIBUTE) == len(MATRIX), "one row per attribute"
    print(to_markdown())
    print(f"{len(MATRIX)} candidate covert storage channels enumerated.\n")
    for rung in ("open", "content", "dirname", "existence", "sealed"):
        p = ClosurePolicy.from_rung(rung)
        print(f"  rung {rung:>10}  level={p.level}  "
              f"open={len(p.open_channels())}  residual={p.residual_bits():8.1f} bits")
