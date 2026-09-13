"""
Run orchestration: conditions, generations, remediation.

A *run* is one (condition, model, seed) triple carried across G generations. Within a generation,
N agents are launched independently against tasks drawn from the shared pool. Between generations
the condition's remediation is applied, if it has one.

Generations exist because inheritance is the thing being measured: an agent in generation g can
only benefit from a discovery made in generation < g, and only if the substrate carried it. The
generation, not the episode, is the unit of independence in the analysis.

Condition -> substrate mapping. The closure ladder is cumulative (closing `dirname` also closes
`content` and `filename`), which is why the conditions are named for their rung:

  no_substrate   cache absent                       baseline task difficulty
  open           rung=open                          the 12 May - 6 Jul channel
  wipe           rung=open, wipe between gens       the 6 Jul remediation
  scrub          rung=open, scrub between gens      bodies emptied, names/structure intact
  content        rung=content                       contents unavailable, names still agent-chosen
  dirname        rung=dirname                       agent-chosen string capacity goes to zero
  existence      rung=existence                     writes redirected into 16 fixed slots
  legit          rung=open, solvable tasks only      FALSE-POSITIVE BASELINE for the detector
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

import srm                      # noqa: E402
import tasks as tasklib         # noqa: E402
from substrate import Substrate  # noqa: E402
from agent import Episode, Workspace, run_episode  # noqa: E402
import providers                # noqa: E402


@dataclass(frozen=True)
class Condition:
    name: str
    rung: str | None          # None => no substrate at all
    wipe: bool = False
    scrub: bool = False
    solvable_only: bool = False   # `legit`: never hand an agent a blocked task
    low_salience: bool = False    # `open_lowsalience`: cache present, usefulness not advertised

    @property
    def has_cache(self) -> bool:
        return self.rung is not None


CONDITIONS: dict[str, Condition] = {
    "no_substrate": Condition("no_substrate", None),
    "open":         Condition("open", "open"),
    "wipe":         Condition("wipe", "open", wipe=True),
    "scrub":        Condition("scrub", "open", scrub=True),
    "content":      Condition("content", "content"),
    "dirname":      Condition("dirname", "dirname"),
    "existence":    Condition("existence", "existence"),
    "legit":        Condition("legit", "open", solvable_only=True),
    # The salience control. Identical substrate, tools and persistence to `open`; the only
    # difference is that the system prompt no longer volunteers that the cache is shared and
    # persists. This is the answer to the strongest objection to the experiment -- that the
    # environment was built to reward deposits, so a deposit proves nothing. A deposit here is
    # unprompted in the strong sense.
    "open_lowsalience": Condition("open_lowsalience", "open", low_salience=True),
}


def _completed_from_log(ep_log: Path) -> set[str]:
    """Rebuild the completed-episode set from the append-only episode log.

    An episode counts as done only if it finished without an API error: the pre-registration
    re-runs API-error episodes rather than counting them, and a zero-turn 429 failure must never
    enter a success rate. Malformed trailing lines (a kill mid-write) are skipped rather than
    fatal, since the next run simply redoes that one episode.
    """
    done: set[str] = set()
    if not ep_log.exists():
        return done
    for line in ep_log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ep = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not ep.get("api_error"):
            done.add(ep.get("agent", ""))
    done.discard("")
    return done


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A state file truncated by a hard kill must not abort the run. The append-only episode
        # log is the source of truth; the worst case is repeating a little work.
        return {}


def _save_state(path: Path, done: set[str], remediated: set[int],
                locked: set[str] | None = None) -> None:
    """Atomic write: temp file then replace, so a kill mid-write cannot corrupt the state."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(
        {"completed": sorted(done), "remediated": sorted(remediated),
         "locked": sorted(locked or set()), "updated": time.time()},
        indent=2), encoding="utf-8")
    tmp.replace(path)


#: One provider instance per alias, reused across episodes within a process.
#:
#: `providers.build()` was called once per episode. For a hosted API that is free -- the object is
#: a thin HTTP client. For `TransformersProvider` it re-runs `from_pretrained`, which reloads ~16
#: GB of weights onto the GPU: about 17 s of wall-clock per episode (roughly 40 minutes across a
#: 140-episode matrix) and a fresh 16 GB allocation each time, relying on the garbage collector to
#: release the previous copy before the next one is placed. That is a slow way to run out of VRAM.
#:
#: Caching is sound only because the constructor takes no per-episode state: `build(alias)`
#: receives nothing about the task, the secret or the seed, and `step()` is a pure function of the
#: messages it is handed. Mock providers are exempt -- they are seeded per episode by design and
#: MUST NOT be shared, or every episode would replay the first one's scripted behaviour.
_PROVIDER_CACHE: dict[str, Any] = {}


def _make_provider(alias: str, *, mock_policy: str | None, secret: str, seed: int,
                   task_id: str = "art-000"):
    if alias == "mock":
        from mock import MockProvider
        return MockProvider(policy=mock_policy or "solo", secret=secret, seed=seed,
                            task_id=task_id)
    if alias not in _PROVIDER_CACHE:
        _PROVIDER_CACHE[alias] = providers.build(alias)
    return _PROVIDER_CACHE[alias]


def _safe_alias(alias: str) -> str:
    """Make a model alias safe to use as a directory name.

    Run directories are named `<condition>__<model>__s<seed>`, and the model alias went in
    verbatim. That breaks on the `family:model` form: `ollama:qwen3:4b` produced
    `open__ollama:qwen3:4b__s0`, and a colon is illegal in a Windows filename, so `mkdir` raised
    WinError 123 and the run died before writing a single episode -- no episodes, no state file,
    nothing to resume from. Ollama model names always contain a colon, so this was not an edge
    case for the local backend.

    Only characters that are illegal or ambiguous in a path are replaced, so the registry aliases
    already in use (`qwen-local`, `or-glm`, `mock`) map to themselves and existing run directories
    keep their names.
    """
    out = []
    for ch in alias:
        out.append(ch if (ch.isalnum() or ch in "-_.") else "_")
    return "".join(out)


def run_condition(
    *,
    condition: Condition,
    model_alias: str,
    seed: int,
    generations: int,
    agents_per_gen: int,
    outdir: Path,
    pool_size: int = 4,
    resume: bool = True,
    mock_policies: list[str] | None = None,
    max_turns: int = 18,
    max_probes: int = 0,
    lockout: bool = False,
    verbose: bool = True,
) -> list[Episode]:
    """Execute one (condition, model, seed) run. Returns every episode in order."""

    run_id = f"{condition.name}__{_safe_alias(model_alias)}__s{seed}"
    base = outdir / run_id
    base.mkdir(parents=True, exist_ok=True)
    sub_log = base / "substrate.jsonl"
    ep_log = base / "episodes.jsonl"
    state_path = base / "state.json"

    # ---- resume --------------------------------------------------------------------------
    # Logs are append-only and are NEVER truncated. A run killed by a rate limit, a network drop
    # or a Ctrl-C loses at most the episode in flight; everything already written stays on disk
    # and is skipped next time. `state.json` also records which generation boundaries have had
    # their remediation applied, because replaying a wipe or a scrub on resume would destroy
    # substrate state that earlier episodes legitimately created.
    state = _load_state(state_path)
    remediated: set[int] = {int(g) for g in state.get("remediated", [])}

    # `done` is rebuilt from the EPISODE LOG, not from state.json. The log is append-only and is
    # the only artifact that cannot disagree with reality; state.json is a convenience that a
    # hard kill can truncate mid-write. Trusting the state file alone is not merely lossy -- a
    # corrupted one silently re-runs completed episodes and appends DUPLICATES, which inflates n
    # and biases every rate in the analysis. Verified by a corrupt-state test.
    done: set[str] = _completed_from_log(ep_log)
    done |= set(state.get("completed", []))
    # First-to-solve lockout must survive a resume, or a restarted run re-opens closed tasks
    # and the scarcity it exists to create silently disappears.
    locked: set[str] = set(state.get("locked", []))

    if not resume:
        for f in (sub_log, ep_log, state_path):
            if f.exists():
                f.unlink()
        done, remediated, locked = set(), set(), set()
    elif done:
        print(f"  resuming {run_id}: {len(done)} episode(s) already on disk, skipping them")

    pool = tasklib.build_pool()
    if condition.solvable_only:
        pool = [t for t in pool if t.kind == "search"]

    # Restrict the pool so that a task an early agent solved is very likely to be drawn again
    # later. This is a deliberate design parameter, not a convenience: inheritance can only be
    # measured if a later agent faces a task an earlier agent already solved, and with 3 agents
    # over 5 generations drawn from 12 tasks that coincidence is rare. Narrowing the pool raises
    # the repeat rate without biasing any comparison, because every condition -- `open` and its
    # matched `wipe` control alike -- draws from the identical restricted pool with the same seed.
    if pool_size and pool_size < len(pool):
        searches = [t for t in pool if t.kind == "search"][:pool_size]
        blocked = [t for t in pool if t.kind == "blocked"][:max(1, pool_size // 3)]
        pool = searches + ([] if condition.solvable_only else blocked)

    substrate = None
    if condition.has_cache:
        policy = srm.ClosurePolicy.from_rung(condition.rung)
        substrate = Substrate(base / "cache", policy, sub_log)
        substrate.seed()

    episodes: list[Episode] = []

    for g in range(1, generations + 1):
        if g > 1 and substrate is not None and g not in remediated:
            if condition.wipe:
                substrate.wipe()
                substrate.seed()
                remediated.add(g)
            elif condition.scrub:
                substrate.scrub_content()
                remediated.add(g)
            _save_state(state_path, done, remediated, locked)

        assigned = tasklib.assign(pool, generation=g, n_agents=agents_per_gen, seed=seed,
                                  locked=locked if lockout else None)
        if lockout and len(assigned) < agents_per_gen:
            # The shortfall is the finding, not an error: agents excluded because the pool
            # closed under them. Reported so the denominator stays honest.
            print(f"  [lockout] generation {g}: {agents_per_gen - len(assigned)} agent(s) "
                  f"excluded, {len(locked)} task(s) closed")

        for i, task in enumerate(assigned):
            agent_name = f"g{g}a{i}"
            if agent_name in done:
                continue
            policy_name = None
            if mock_policies:
                policy_name = mock_policies[(g - 1) * agents_per_gen + i] \
                    if len(mock_policies) > (g - 1) * agents_per_gen + i else mock_policies[-1]

            provider = _make_provider(model_alias, mock_policy=policy_name,
                                      secret=task.secret, seed=seed * 1000 + g * 10 + i,
                                      task_id=task.task_id)

            ws = Workspace(base / "work" / agent_name)

            # Per-TURN progress, not just per-episode. On a local 8B an episode can run twenty
            # minutes, so a per-episode line leaves the operator staring at nothing for the whole
            # of it. `run_episode` already emitted these events; nothing had ever passed a
            # handler in, so they went nowhere.
            ep_t0 = time.time()

            def _turn_event(msg: str, _t0: float = ep_t0) -> None:
                print(f"    +{time.time() - _t0:5.0f}s {msg}", flush=True)

            ep = run_episode(
                provider=provider, task=task, workspace=ws, substrate=substrate,
                condition=condition.name, generation=g, agent_name=agent_name,
                model_alias=model_alias, seed=seed, max_turns=max_turns, max_probes=max_probes,
                low_salience=condition.low_salience,
                on_event=_turn_event if verbose else None,
            )
            episodes.append(ep)
            # Append and fsync per episode: durable on disk before the next API call is issued,
            # so a rate limit or a kill never costs more than the episode in flight.
            with ep_log.open("a", encoding="utf-8") as fh:
                fh.write(ep.to_json() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            # Only a genuinely completed episode counts as done. An episode killed by an API
            # error is NOT a data point: the pre-registration says such episodes are re-run, not
            # counted, and marking one complete would both skip it on resume and let a
            # zero-turn failure enter a success rate as a zero. That is exactly how an exhausted
            # rate limit turns into a spurious null.
            if not ep.api_error:
                done.add(agent_name)
                # First-to-solve lockout: a solved task is permanently withdrawn, so later
                # agents face a shrinking pool rather than a repeat of the same distribution.
                if lockout and ep.success:
                    locked.add(task.task_id)
                _save_state(state_path, done, remediated, locked)

            if verbose:
                flag = "OK " if ep.success else ("ERR" if ep.api_error else "-- ")
                print(f"  [{flag}] {run_id} {agent_name} {task.task_id}({task.kind}) "
                      f"turns={len(ep.turns)} validates={ep.n_validate} "
                      f"tok={ep.usage_total['in']}/{ep.usage_total['out']} "
                      f"{ep.finished - ep.started:.0f}s"
                      + (f" err={ep.api_error[:60]}" if ep.api_error else ""),
                      flush=True)

    return episodes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the channel-genesis experiment.")
    ap.add_argument("--conditions", default="open",
                    help="comma-separated: " + ",".join(CONDITIONS))
    ap.add_argument("--models", default="mock", help="comma-separated model aliases, or 'mock'")
    ap.add_argument("--seeds", default="0,1,2",
                    help="comma-separated integer seeds; >=3 per pre-registration Amendment A2.1")
    ap.add_argument("--generations", type=int, default=5)
    ap.add_argument("--agents", type=int, default=3)
    ap.add_argument("--max-turns", type=int, default=18)
    ap.add_argument("--max-probes", type=int, default=0,
                    help="Oracle calls allowed per episode; 0 = unlimited. This, not "
                         "--max-turns, is the difficulty lever: a model that batches "
                         "parallel tool calls gets unbounded probes from a turn limit.")
    ap.add_argument("--pool-size", type=int, default=4,
                    help="number of distinct search tasks in the draw; smaller => more repeats "
                         "across generations => inheritance is measurable. Applied identically "
                         "to every condition.")
    ap.add_argument("--outdir", default=str(HERE.parent / "results" / "behavioural" / "runs"))
    ap.add_argument("--mock-policies", default="",
                    help="comma-separated policy per episode for the mock provider")
    ap.add_argument("--lockout", action="store_true",
                    help="first-to-solve lockout: a solved task is permanently withdrawn from "
                         "the pool, so later agents face scarcity rather than the same "
                         "distribution. Off by default; every episode collected so far was "
                         "collected without it and stays reproducible.")
    ap.add_argument("--no-resume", action="store_true",
                    help="delete existing logs and restart this run from scratch "
                         "(default: resume, skipping episodes already on disk)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and estimated episode count, then exit")
    a = ap.parse_args(argv)

    providers.load_env(HERE.parent / ".env")

    conds = [CONDITIONS[c.strip()] for c in a.conditions.split(",") if c.strip()]
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    pol = [p.strip() for p in a.mock_policies.split(",") if p.strip()] or None

    total = len(conds) * len(models) * len(seeds) * a.generations * a.agents
    print(f"plan: {len(conds)} conditions x {len(models)} models x {len(seeds)} seeds "
          f"x {a.generations} gens x {a.agents} agents = {total} episodes")

    if models != ["mock"]:
        have = providers.available()
        missing = [m for m in models if m not in have and ":" not in m]
        if missing:
            print(f"ERROR: no API key for {missing}. Available: {have or '(none)'}", file=sys.stderr)
            print("Put keys in project/.env as ANTHROPIC_API_KEY=... etc.", file=sys.stderr)
            return 2

    if a.dry_run:
        return 0

    outdir = Path(a.outdir)
    t0 = time.time()
    n = 0
    for c in conds:
        for m in models:
            for s in seeds:
                eps = run_condition(
                    condition=c, model_alias=m, seed=s, generations=a.generations,
                    agents_per_gen=a.agents, outdir=outdir, pool_size=a.pool_size,
                    resume=not a.no_resume, mock_policies=pol, max_turns=a.max_turns,
                    max_probes=a.max_probes, lockout=a.lockout,
                )
                n += len(eps)
    print(f"done: {n} episodes in {time.time() - t0:.1f}s -> {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
