"""Tier 3: run one real agent in a container, against a real shared volume.

    python real/agent.py sender   /cache
    python real/agent.py receiver /cache

This is the behavioural arm on real infrastructure. It reuses the episode loop from
`runner/agent.py` unchanged -- the same tools, the same task, the same substrate primitives -- and
changes only where the substrate lives: a real mount under `/cache`, shared by two containers with
separate PID and mount namespaces, instead of a per-process temp directory.

Two roles, run in sequence:
  sender    generation g. Solves its task, may or may not write to /cache, then exits.
  receiver  generation g+1. Sees whatever the sender left in /cache; never sees its transcript.

What this establishes, and what it does not
-------------------------------------------
It establishes that the capacity ladder's substrate is real -- the agents drive an actual shared
filesystem, not a model of one. It does NOT re-measure the ladder (capacity.py does that
deterministically and needs no agent), and it does not, by itself, constitute the pre-registered
behavioural matrix. The matrix needs the pre-registered generation/agent structure and a model
that clears the calibration gate. The gate finding for the model available here is recorded in
`results/tier3-run.json` alongside whatever this produces, so the run is never mistaken for more
than it is.

Model
-----
Reads `MODEL_ALIAS` from the environment (default `kimi`). Kimi K3's latency (~70-130 s/call) and
non-deterministic sampling under a fixed seed are documented in the provider registry; a full arm
on this model is tens of hours of wall clock and is not attempted from one invocation. This runs a
single episode and writes its record, so cost is one episode, not forty.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "runner"))

from srm import ClosurePolicy                       # noqa: E402
from substrate import Substrate                     # noqa: E402
import tasks as tasklib                             # noqa: E402
import providers                                    # noqa: E402
from agent import Workspace, run_episode            # noqa: E402


def _load_env() -> None:
    """Load .env into the process without printing anything, so a container has the key."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: agent.py <sender|receiver> <cache-mount>")
        return 2
    role, mount = argv[0], Path(argv[1])
    mount.mkdir(parents=True, exist_ok=True)

    _load_env()
    alias = os.environ.get("MODEL_ALIAS", "kimi")
    generation = 1 if role == "sender" else 2

    # The substrate points at the REAL shared mount, open rung. This is the whole difference from
    # the synthetic run: `root` is a bind into a named Docker volume shared with the other role.
    log = mount / f"substrate-{role}.jsonl"
    substrate = Substrate(mount / "cache", ClosurePolicy.from_rung("open"), log)

    pool = tasklib.build_pool()
    task = pool[0]                                   # one fixed task; this is a smoke run, not the matrix
    ws = Workspace(mount / f"work-{role}")

    print(f"[tier3] role={role} generation={generation} model={alias} mount={mount}")
    print(f"[tier3] task={task.task_id} kind={task.kind}")
    t0 = time.time()

    try:
        provider = providers.build(alias)
    except Exception as e:                           # noqa: BLE001
        print(f"[tier3] provider build failed: {e}")
        return 1

    try:
        ep = run_episode(
            provider=provider, task=task, workspace=ws, substrate=substrate,
            condition="open", generation=generation, agent_name=f"g{generation}a0",
            model_alias=alias, seed=0, max_turns=18,
            on_event=lambda s: print(f"    + {time.time()-t0:5.0f}s {s}", flush=True),
        )
    except Exception as e:                           # noqa: BLE001
        print(f"[tier3] episode raised: {type(e).__name__}: {e}")
        return 1

    record = {
        "role": role, "model": alias, "mount": str(mount),
        "task": task.task_id, "kind": task.kind,
        "success": ep.success, "turns": len(ep.turns),
        "api_error": ep.api_error, "wall_seconds": round(time.time() - t0, 1),
        "usage": ep.usage_total,
        "note": ("Single real-infrastructure episode. Not the pre-registered behavioural matrix. "
                 "The model's calibration-gate status governs whether a full arm is meaningful."),
    }
    (mount / f"tier3-{role}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"\n[tier3] {role} done in {record['wall_seconds']}s  "
          f"success={ep.success}  turns={len(ep.turns)}  api_error={ep.api_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
