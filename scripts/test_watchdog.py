"""End-to-end tests for the run supervisor: prove it restarts, stops, and outlives its child.

    python scripts/test_watchdog.py

No network, no keys, no API calls. Every case runs the real `watchdog.py` as a subprocess against
a stub child, so what is exercised is the actual restart loop rather than a re-implementation of it.

Why this file exists
--------------------
The supervisor shipped three fixes before its core loop had ever been run against a controllable
process, and in that time it twice died silently and once killed itself with its own signal
handler. Each was caught by staring at a frozen log an hour later. An untested supervisor is worth
close to nothing, because the thing it is supposed to notice is exactly the thing you will not be
watching for.

Every case here corresponds to something that actually happened during this project:

  restart-on-stall    a child stopped producing output and nothing restarted it; the run sat
                      dead for 72 minutes.
  survives-child      the supervisor died together with its child, so there was no restart and
                      no record of why.
  clean-exit          a finished child must end the supervisor with 0, not trigger a restart loop.
  quota-give-up       an exhausted provider must stop the run rather than grind out api_errors.
  restart-budget      a permanently broken child must not be restarted forever.
  journal-survives    every outcome must be on disk afterwards, because the supervisor's own
                      history is the only evidence available after it exits.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WATCHDOG = HERE / "watchdog.py"

PASS, FAIL = [], []


def check(label: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(label)
    print(f"  {'ok ' if cond else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))


# --------------------------------------------------------------------------- stub children

STUBS = {
    # Prints, then hangs forever without producing output: the stall case.
    "stall": "import sys,time\nprint('working', flush=True)\ntime.sleep(9999)\n",
    # Prints and exits cleanly straight away.
    "clean": "import sys\nprint('all done', flush=True)\nraise SystemExit(0)\n",
    # Emits a day-quota marker, then keeps quiet.
    "quota": ("import time\n"
              "print('Rate limit reached ... on tokens per day (TPD): Limit 200000', flush=True)\n"
              "time.sleep(9999)\n"),
    # Dies immediately, every time: the restart-budget case.
    "crash": "raise SystemExit(3)\n",
}


def write_stub(d: Path, name: str) -> Path:
    p = d / f"stub_{name}.py"
    p.write_text(STUBS[name], encoding="utf-8")
    return p


def run_watchdog(tmp: Path, stub: str, *, stall: int = 3, poll: int = 1,
                 restarts: int = 2, quota_errors: int = 1,
                 timeout: int = 90) -> tuple[int, str, list[dict]]:
    journal = tmp / "wd.json"
    results = tmp / "results"
    results.mkdir(exist_ok=True)
    cmd = [sys.executable, "-u", str(WATCHDOG),
           "--child", str(write_stub(tmp, stub)),
           "--stall-seconds", str(stall), "--poll", str(poll),
           "--heartbeat", "2", "--max-restarts", str(restarts),
           "--quota-errors", str(quota_errors),
           "--journal", str(journal), "--results", str(results),
           "--"]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, cwd=str(ROOT))
        rc, out = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as e:
        rc, out = -999, (e.stdout or b"").decode(errors="replace")
    events = []
    if journal.exists():
        try:
            events = json.loads(journal.read_text(encoding="utf-8")).get("events", [])
        except json.JSONDecodeError:
            pass
    return rc, out, events, time.time() - t0        # type: ignore[return-value]


def kinds(events: list[dict]) -> list[str]:
    return [e["kind"] for e in events]


# --------------------------------------------------------------------------- cases

def case_stall_restarts() -> None:
    print("\nrestart-on-stall")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rc, out, ev, secs = run_watchdog(tmp, "stall", stall=3, restarts=2, timeout=120)
        k = kinds(ev)
        check("a stalled child is detected", "child-ended" in k)
        stalled = [e for e in ev if e["kind"] == "child-ended" and e.get("reason") == "stalled"]
        check("the reason recorded is 'stalled'", bool(stalled),
              f"reasons={[e.get('reason') for e in ev if e['kind']=='child-ended']}")
        check("it restarts rather than giving up at once", k.count("launched") >= 2,
              f"launches={k.count('launched')}")
        check("it stops after the restart budget", "give-up" in k and rc == 4,
              f"rc={rc}")
        check("the supervisor outlived every child", "supervisor-exiting" in k)
        check("it finished in reasonable time", secs < 120, f"{secs:.0f}s")


def case_clean_exit() -> None:
    print("\nclean-exit")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rc, out, ev, secs = run_watchdog(tmp, "clean", stall=30, timeout=60)
        k = kinds(ev)
        check("a finished child ends the supervisor with 0", rc == 0, f"rc={rc}")
        check("it is recorded as done", "done" in k)
        check("it does NOT restart a healthy child", k.count("launched") == 1,
              f"launches={k.count('launched')}")


def case_quota_gives_up() -> None:
    print("\nquota-give-up")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rc, out, ev, secs = run_watchdog(tmp, "quota", stall=60, timeout=60)
        k = kinds(ev)
        check("a day-quota marker is seen", "quota-marker" in k)
        check("the run stops rather than grinding", rc == 3, f"rc={rc}")
        check("give-up explains itself for the next session",
              any(e["kind"] == "give-up" and "resume" in str(e.get("why", "")) for e in ev))
        check("it does not restart into the same wall", k.count("launched") == 1,
              f"launches={k.count('launched')}")


def case_restart_budget() -> None:
    print("\nrestart-budget")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rc, out, ev, secs = run_watchdog(tmp, "crash", stall=30, restarts=2, timeout=90)
        k = kinds(ev)
        check("a permanently broken child is retried", k.count("launched") >= 2,
              f"launches={k.count('launched')}")
        check("but not forever", k.count("launched") <= 4, f"launches={k.count('launched')}")
        check("it exits non-zero", rc != 0, f"rc={rc}")


def case_journal_survives() -> None:
    print("\njournal-survives")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rc, out, ev, secs = run_watchdog(tmp, "clean", stall=30, timeout=60)
        j = tmp / "wd.json"
        check("the journal is valid JSON on disk afterwards", j.exists())
        reread = json.loads(j.read_text(encoding="utf-8"))
        check("it holds the full event history", len(reread.get("events", [])) >= 3,
              f"{len(reread.get('events', []))} events")
        check("every event is timestamped and typed",
              all("at" in e and "kind" in e for e in reread["events"]))
        check("no temp file is left behind", not (tmp / "wd.tmp").exists())


def main() -> int:
    print("watchdog end-to-end")
    case_clean_exit()
    case_stall_restarts()
    case_quota_gives_up()
    case_restart_budget()
    case_journal_survives()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for f in FAIL:
        print(f"  FAILED: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
