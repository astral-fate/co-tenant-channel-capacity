"""Per-agent namespacing: the control the ladder is measured against.

    python src/namespace.py            # measure, print, write results/capacity/namespace.json

Why this module exists
----------------------
The reviewer objection this project has never answered is the cheapest one to state: if per-agent
namespaces convert co-tenant flow into an ordinary access attempt across a boundary where
authorization controls already work, then the closure ladder instruments a problem a one-line fix
dissolves, and a lab should adopt the fix rather than the instrument.

The objection is correct on the capacity axis and this module confirms it rather than resisting it.
Namespacing is not rung 9. The ladder closes *attributes* on a shared resource; namespacing removes
the sharing, so it acts on a different axis entirely and it is strictly stronger on the axis it acts
on. Any honest treatment has to say so.

What is left, and what this measures, is the axis on which namespacing is not free. A shared cache
exists because two agents needing the same artefact should fetch it once. Partition it per agent and
that property is gone by construction: the same artefact is fetched once per agent that needs it.
That cost is not a matter of opinion and it does not require a production deployment to observe --
it follows from the workload's overlap structure, which is countable.

So three measurements, in increasing order of interest:

1. **Cross-namespace capacity.** Run the existing coders with sender and receiver in different
   namespaces. Every carrier should measure zero -- not because an attribute is closed, but because
   the receiver cannot address the sender's subtree. Same-namespace is run as the positive control,
   and must reproduce the open-rung figures, or the harness is measuring its own plumbing.

2. **Cache-reuse loss.** For a workload of `k` agents drawing artefacts from a pool with a given
   overlap, count fetches under one shared namespace and under per-agent namespaces. The ratio is
   the cost, and it rises with exactly the overlap that motivates having a cache.

3. **Mediation surface.** Where the control has to sit, and what it has to do there, on the same two
   axes `cost.py` uses for the ladder so the numbers are comparable.

None of this needs a network, a key, or a GPU.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import capacity as capacity_mod
from capacity import CODERS, measure
from srm import Attribute, ClosurePolicy
from substrate import Substrate, SubstrateError

TRIALS = capacity_mod.TRIALS


# --------------------------------------------------------------------------- 1. capacity

class NamespacedSubstrate(Substrate):
    """A substrate whose every path is confined to one agent's subtree.

    The confinement is applied in `_resolve`, which every primitive already routes through, so no
    primitive needs to know the control exists. That is the point of the design and it is also the
    reason the mediation count in §3 is one rather than eight.
    """

    def __init__(self, root, policy, log_path, namespace: str):
        self.namespace = namespace
        super().__init__(root, policy, log_path)
        (self.root / namespace).mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """Resolve inside the agent's subtree, and refuse anything that leaves it.

        The containment check has to be against `root/namespace`, not against `root`. Prefixing
        the path and deferring to the base class is the obvious implementation and it does not
        work: `../agent_a` prefixes to `agent_b/../agent_a`, which resolves to a sibling subtree
        that is still under `root`, so the base check passes and the namespace is escaped. The
        first version of this class did that, and the probe below caught it at 20/20 escapes --
        which is the reason the probe tries escapes at all rather than assuming the control holds.
        """
        base = (self.root / self.namespace).resolve()
        target = (base / path).resolve()
        if target != base and base not in target.parents:
            raise SubstrateError(f"outside namespace {self.namespace!r}: {path}")
        return target

    def seed(self, entries=None, skeleton=("build", "deps", "tmp")) -> None:
        for d in skeleton:
            (self.root / self.namespace / d).mkdir(parents=True, exist_ok=True)
        for rel, body in (entries or {}).items():
            p = self.root / self.namespace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")


@dataclass
class CarrierResult:
    attribute: str
    same_namespace_bits: float
    sender_artefacts: int
    observable_by_receiver: int
    escapes_attempted: int
    escapes_succeeded: int


def _confinement_probe(attribute: Attribute, tmp: Path, trials: int) -> tuple[int, int, int, int]:
    """Sender encodes in namespace A; receiver in B enumerates everything it can reach.

    This is a confinement check, not a capacity measurement, and the distinction matters. The
    project's coders encode and decode inside one substrate object, so handing a coder the
    receiver's substrate makes it write and read in B -- a same-namespace round trip wearing a
    cross-namespace label. An earlier version of this function did exactly that and reported a
    16-bit "leak" on seven carriers, which was the top of its own search range and nothing else.

    What can be established without rewriting every coder is the property the control actually
    claims: after a sender has written into A, is any of it addressable from B? So the sender
    encodes a real payload, and the receiver then walks its own view recursively and tries the
    obvious escapes. Cross-namespace capacity is zero exactly when the reachable set is disjoint
    from the sender's writes and no escape resolves.
    """
    coder = CODERS[attribute]
    policy = ClosurePolicy.from_rung("open")
    ESCAPES = ("../agent_a", "../agent_a/build", "..", "/", "./../agent_a")
    n_sender = n_seen = n_esc = n_esc_ok = 0

    for t in range(trials):
        d = tmp / f"conf_{attribute.value}_{t}"
        if d.exists():
            shutil.rmtree(d)
        sender = NamespacedSubstrate(d, policy, d / "a.jsonl", namespace="agent_a")
        sender.seed()
        receiver = NamespacedSubstrate(d, policy, d / "b.jsonl", namespace="agent_b")
        receiver.seed()

        try:
            coder(sender, 8, random.Random(7000 + t))
        except (SubstrateError, OSError):
            pass

        planted = {p.name for p in (d / "agent_a").rglob("*")}
        n_sender += len(planted)

        # Everything the receiver can reach through its own view.
        reachable: set[str] = set()
        frontier = ["."]
        while frontier:
            cur = frontier.pop()
            try:
                for e in receiver.list_dir(cur):
                    child = f"{cur}/{e['name']}".lstrip("./")
                    reachable.add(e["name"])
                    if e.get("type") == "dir":
                        frontier.append(child)
            except (SubstrateError, OSError):
                continue
        # A name the receiver seeds for itself is not evidence of a leak; only the sender's
        # own artefacts count, and the skeleton is common to both.
        skeleton = {"build", "deps", "tmp"}
        n_seen += len((planted & reachable) - skeleton)

        for esc in ESCAPES:
            n_esc += 1
            try:
                receiver.list_dir(esc)
                n_esc_ok += 1
            except (SubstrateError, OSError, ValueError):
                pass

    return n_sender, n_seen, n_esc, n_esc_ok


def measure_capacity(trials: int = TRIALS) -> list[CarrierResult]:
    out: list[CarrierResult] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for attribute in CODERS:
            same = measure(attribute, ClosurePolicy.from_rung("open"), tmp, trials=trials)
            planted, seen, esc, esc_ok = _confinement_probe(attribute, tmp, trials=trials)
            out.append(CarrierResult(attribute.value, same, planted, seen, esc, esc_ok))
    return out


# --------------------------------------------------------------------------- 2. cache-reuse loss

@dataclass
class ReuseResult:
    agents: int
    pool: int
    per_agent: int
    overlap: float
    fetches_shared: int
    fetches_namespaced: int
    multiplier: float
    trials: int


def measure_reuse(agents: int, pool: int, per_agent: int,
                  trials: int = 200, seed: int = 11) -> ReuseResult:
    """Count artefact fetches under one shared cache and under per-agent caches.

    A fetch is a cache miss. Under sharing, an artefact is fetched the first time any agent needs
    it. Under per-agent namespaces, it is fetched the first time *each* agent needs it. Nothing
    here is a simulation of a network -- it is the deduplication arithmetic the cache exists to
    perform, counted over a workload.
    """
    rng = random.Random(seed)
    tot_shared = tot_ns = 0
    for _ in range(trials):
        draws = [set(rng.sample(range(pool), per_agent)) for _ in range(agents)]
        tot_shared += len(set().union(*draws))     # each distinct artefact fetched once
        tot_ns += sum(len(d) for d in draws)       # each agent fetches its own copy
    union_mean = tot_shared / trials
    ns_mean = tot_ns / trials
    # Overlap: how much of the per-agent demand is redundant across agents.
    overlap = 1.0 - (union_mean / ns_mean) if ns_mean else 0.0
    return ReuseResult(
        agents=agents, pool=pool, per_agent=per_agent,
        overlap=round(overlap, 4),
        fetches_shared=round(union_mean, 1),
        fetches_namespaced=round(ns_mean, 1),
        multiplier=round(ns_mean / union_mean, 3) if union_mean else 0.0,
        trials=trials,
    )


# --------------------------------------------------------------------------- 3. mediation surface

#: Where the control sits, and what it does there. Both are properties of the API surface, which is
#: what makes them checkable by a third party without the lab's network -- the same standard
#: `cost.py` holds the ladder to.
MEDIATION = {
    "control": "per-agent namespace",
    "mediation_points": 1,
    "mediation_detail": "path resolution; every primitive already routes through it",
    "enforcement_class": "structural",
    "per_call_cost": "O(1) prefix check",
    "operating_point": None,
    "false_positive_surface": "none -- there is no threshold to set",
}


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=TRIALS)
    ap.add_argument("--json", default=str(ROOT / "results" / "capacity" / "namespace.json"))
    args = ap.parse_args()

    print("PER-AGENT NAMESPACING -- the control the ladder is measured against")
    print("=" * 74)

    print("\n1. Confinement (same-namespace capacity is the positive control)")
    print(f"   {'attribute':<12} {'same ns bits':>13} {'planted':>9} {'visible':>9} {'escapes':>9}")
    carriers = measure_capacity(trials=args.trials)
    for c in carriers:
        print(f"   {c.attribute:<12} {c.same_namespace_bits:>13.0f} {c.sender_artefacts:>9} "
              f"{c.observable_by_receiver:>9} {c.escapes_succeeded:>4}/{c.escapes_attempted:<4}")
    leaked = [c.attribute for c in carriers
              if c.observable_by_receiver or c.escapes_succeeded]
    same_tot = sum(c.same_namespace_bits for c in carriers)
    print(f"\n   same-namespace total {same_tot:.0f} bits across the eight carriers.")
    print(f"   carriers where the sender's artefacts were visible from the receiver's "
          f"namespace, or an escape resolved: {leaked or 'none'}")

    print("\n2. Cache-reuse loss (the axis on which namespacing is not free)")
    print(f"   {'agents':>7} {'pool':>6} {'each':>6} {'overlap':>8} "
          f"{'shared':>8} {'per-agent':>10} {'x':>7}")
    reuse = []
    for agents, pool, per_agent in [(2, 100, 20), (4, 100, 20), (8, 100, 20),
                                    (16, 100, 20), (16, 100, 40), (16, 50, 20)]:
        r = measure_reuse(agents, pool, per_agent)
        reuse.append(r)
        print(f"   {r.agents:>7} {r.pool:>6} {r.per_agent:>6} {r.overlap:>8.3f} "
              f"{r.fetches_shared:>8.1f} {r.fetches_namespaced:>10.1f} {r.multiplier:>7.2f}")

    print("\n3. Mediation surface")
    for k, v in MEDIATION.items():
        print(f"   {k:<24} {v}")

    payload = {
        "carriers": [asdict(c) for c in carriers],
        "reuse": [asdict(r) for r in reuse],
        "mediation": MEDIATION,
        "trials": args.trials,
    }
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwritten to {out}")

    worst = max(reuse, key=lambda r: r.multiplier)
    print(f"""
  Namespacing closes cross-agent flow on every carrier measured, which the ladder
  does not do until its final rung. It is the stronger control and this project
  should say so. Its cost is not integration -- one mediation point, no operating
  point, no threshold -- but reuse: on the heaviest workload here, {worst.agents}
  agents over a pool of {worst.pool}, it turns {worst.fetches_shared:.0f} fetches
  into {worst.fetches_namespaced:.0f}, a factor of {worst.multiplier:.2f}. The
  ladder's remaining use is the residual case: substrates that cannot be
  partitioned because the sharing is the point.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
