"""Resume tests: kill a run at the worst moments and prove nothing is lost or double-counted.

    python runner/test_resume.py

Runs against the mock provider, so no GPU, no network and no keys. Every case here corresponds to
something that actually went wrong in this project:

  mid-episode kill      SIGKILL between episodes and mid-write. A partially written final line
                        must not be read as a completed episode, and must not be fatal.
  corrupt state file    `state.json` was trusted once and it replayed six finished episodes,
                        writing eighteen lines with six duplicate (generation, agent) pairs.
                        Progress is now rebuilt from the append-only log; the state file is only
                        ever additive to that.
  deleted state file    losing it must cost nothing, because the log is the source of truth.
  API-error episodes    must NOT count as done -- they are retried. Counting a zero-turn 429 as a
                        failure once produced a false null in this project, so the rule is load
                        bearing rather than tidy.
  no duplicates         the invariant that matters for every rate we report: one episode per
                        (generation, agent) pair.
  provider outage       a dead local inference server must produce retryable api_error records,
                        not a crashed run and not counted failures.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ok  {msg}")
    else:
        print(f"  FAIL {msg}")
        _FAILURES.append(msg)


GENERATIONS = 6
AGENTS = 2
EXPECTED = GENERATIONS * AGENTS


def run(outdir: Path, *, timeout: float | None = None) -> bool:
    """Invoke the runner. Returns True if it completed, False if we killed it on timeout."""
    cmd = [sys.executable, "-u", "run.py", "--conditions", "open", "--models", "mock",
           "--seeds", "0", "--generations", str(GENERATIONS), "--agents", str(AGENTS),
           "--outdir", str(outdir)]
    try:
        subprocess.run(cmd, cwd=HERE, timeout=timeout, capture_output=True)
        return True
    except subprocess.TimeoutExpired:
        return False


def episodes(outdir: Path) -> list[dict]:
    """Every episode under `outdir`, whatever the run directory is called.

    This used to hardcode `open__mock__s0`, which quietly broke the provider-outage case: that run
    lives in `open__ollama_qwen3_4b__s0`, so the lookup found nothing and the test reported "0/0
    episodes recorded as api_error" as a harness failure when the harness was fine. A test that
    looks in the wrong place fails in the same direction as a real bug, which is the worst kind of
    false alarm.
    """
    out = []
    for f in sorted(outdir.glob("*/episodes.jsonl")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue      # a torn final line is expected after a kill
    return out


def pairs(eps: list[dict]) -> Counter:
    return Counter((e["generation"], e["agent"]) for e in eps if not e.get("api_error"))


def main() -> int:
    tmp = tempfile.TemporaryDirectory(prefix="resume-")
    root = Path(tmp.name)

    print("resume")

    # --- baseline: a clean full run, for comparison -------------------------------------------
    clean = root / "clean"
    t0 = time.time()
    run(clean)
    clean_secs = time.time() - t0
    base = episodes(clean)
    check(len(base) == EXPECTED,
          f"a clean run produces exactly {EXPECTED} episodes (got {len(base)})")
    check(all(v == 1 for v in pairs(base).values()),
          "no duplicate (generation, agent) pairs in a clean run")

    # --- interrupted, then resumed -------------------------------------------------------------
    # Kill early enough to land mid-episode, then resume repeatedly until it finishes. The point
    # is not that one resume suffices, it is that repeated interruption never loses or duplicates.
    # The kill is triggered by OBSERVED PROGRESS, not by a clock.
    #
    # Two earlier versions were both wrong. A hard-coded timeout stopped interrupting anything once
    # the mock got fast enough -- the run completed first and the test passed without ever having
    # tested a kill. Deriving the deadline from the measured clean-run duration was better but
    # still a race: when the run finished inside the deadline the check failed, so the suite went
    # flaky, which is worse than no test because it teaches you to ignore a red result.
    #
    # Polling the episode log until some but not all episodes exist, then killing, has no timing
    # assumption in it at all.
    inter = root / "interrupted"
    KILL_AFTER = EXPECTED // 2
    proc = subprocess.Popen(
        [sys.executable, "-u", "run.py", "--conditions", "open", "--models", "mock",
         "--seeds", "0", "--generations", str(GENERATIONS), "--agents", str(AGENTS),
         "--outdir", str(inter)],
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    killed_at = None
    deadline = time.time() + 120
    while time.time() < deadline:
        n = len(episodes(inter))
        if n >= KILL_AFTER and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
            killed_at = n
            break
        if proc.poll() is not None:      # finished before we could interrupt it
            break
        time.sleep(0.02)

    mid = episodes(inter)
    print(f"      (clean run {clean_secs:.1f}s; killed after {killed_at} episodes "
          f"of {EXPECTED}; exit={proc.poll()})")
    check(killed_at is not None and len(mid) < EXPECTED,
          f"the interruption actually interrupted: killed at {killed_at} episodes with "
          f"{len(mid)}/{EXPECTED} on disk")

    for _ in range(6):
        if run(inter, timeout=60):
            break
    after = episodes(inter)
    good = pairs(after)

    check(len(good) == EXPECTED,
          f"resume reaches the full {EXPECTED} clean episodes after interruption "
          f"(got {len(good)})")
    check(all(v == 1 for v in good.values()),
          f"no (generation, agent) pair is run twice across the interruption "
          f"(duplicates: {[k for k, v in good.items() if v > 1]})")
    check(len(after) >= len(mid),
          "work completed before the kill is retained, not discarded")

    # --- a completed run is a no-op --------------------------------------------------------------
    before_n = len(episodes(inter))
    run(inter)
    check(len(episodes(inter)) == before_n,
          f"re-running a finished run adds nothing (stayed at {before_n})")

    # --- the state file is not the source of truth ---------------------------------------------
    corrupt = root / "corrupt"
    shutil.copytree(inter, corrupt)
    state = corrupt / "open__mock__s0" / "state.json"
    state.write_text("{ this is not json", encoding="utf-8")
    run(corrupt)
    check(len(pairs(episodes(corrupt))) == EXPECTED
          and all(v == 1 for v in pairs(episodes(corrupt)).values()),
          "a corrupt state.json neither loses episodes nor replays them")

    deleted = root / "deleted"
    shutil.copytree(inter, deleted)
    (deleted / "open__mock__s0" / "state.json").unlink()
    run(deleted)
    check(len(pairs(episodes(deleted))) == EXPECTED
          and all(v == 1 for v in pairs(episodes(deleted)).values()),
          "a deleted state.json costs nothing; the append-only log is authoritative")

    # --- a torn final line must not be fatal, and must not count as done -----------------------
    torn = root / "torn"
    shutil.copytree(inter, torn)
    log = torn / "open__mock__s0" / "episodes.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write('{"episode_id":"torn","generation":9,"agent":"g9a9","succ')
    run(torn)
    survived = pairs(episodes(torn))
    check(len(survived) == EXPECTED and all(v == 1 for v in survived.values()),
          "a half-written trailing line is skipped, not treated as an episode")

    # --- API-error episodes are retried, never counted -----------------------------------------
    errored = root / "errored"
    shutil.copytree(inter, errored)
    log = errored / "open__mock__s0" / "episodes.jsonl"
    lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    victim = json.loads(lines[-1])
    victim["api_error"] = "RateLimitError: 429"
    victim["success"] = False
    lines[-1] = json.dumps(victim, separators=(",", ":"))
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    st = errored / "open__mock__s0" / "state.json"
    if st.exists():
        s = json.loads(st.read_text(encoding="utf-8"))
        s["completed"] = []
        st.write_text(json.dumps(s), encoding="utf-8")

    run(errored)
    eps_e = episodes(errored)
    retried = pairs(eps_e)
    check(retried.get((victim["generation"], victim["agent"]), 0) >= 1,
          "an API-error episode is re-run rather than left as a failure")
    check(all(v == 1 for v in retried.values()),
          f"the retry does not create a duplicate clean episode "
          f"(duplicates: {[k for k, v in retried.items() if v > 1]})")


    # --- a dead inference server must degrade, not crash ---------------------------------------
    # This is the local-stack case the mock cannot cover. Inference now runs on a local Ollama
    # server, and a local server can be stopped, crash, or be restarted for a model swap while a
    # matrix is grinding. The requirement is that such episodes become `api_error` records -- which
    # are excluded from every rate and retried -- rather than killing the run or, far worse, being
    # counted as failures. Counting a zero-turn provider failure as a failure produced a false null
    # in this project once already.
    #
    # Port 1 is used as a guaranteed-dead endpoint, so this needs no GPU and no model.
    outage = root / "outage"
    env = dict(os.environ, OLLAMA_HOST="http://127.0.0.1:1")
    cmd = [sys.executable, "-u", "run.py", "--conditions", "open",
           "--models", "ollama:qwen3:4b", "--seeds", "0",
           "--generations", "2", "--agents", "1", "--max-probes", "5",
           "--max-turns", "4", "--outdir", str(outage)]
    proc = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, timeout=300)

    out_eps = episodes(outage)
    errored = [e for e in out_eps if e.get("api_error")]
    check(proc.returncode == 0,
          f"a dead inference server does not crash the run (exit {proc.returncode})")
    check(len(errored) == len(out_eps) and len(out_eps) > 0,
          f"every episode against a dead server is recorded as api_error "
          f"({len(errored)}/{len(out_eps)})")
    check(all("ollama unreachable" in (e.get("api_error") or "").lower()
              or "urlerror" in (e.get("api_error") or "").lower()
              or "runtimeerror" in (e.get("api_error") or "").lower() for e in errored),
          "the recorded error names the cause rather than a generic failure")
    check(pairs(out_eps) == Counter(),
          "no api_error episode is counted as a clean episode")

    # And the crucial half: those episodes are NOT marked done, so a later pass redoes them.
    state = outage / "open__ollama_qwen3_4b__s0" / "state.json"
    if not state.exists():
        cands = list(outage.glob("*/state.json"))
        state = cands[0] if cands else None
    if state is not None:
        completed = json.loads(state.read_text(encoding="utf-8")).get("completed", [])
        check(completed == [],
              f"api_error episodes are not marked complete, so they are retried "
              f"(completed={completed})")
    else:
        check(False, "expected a state.json for the outage run")

    tmp.cleanup()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} resume test(s) failed")
        return 1
    print("All resume tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
