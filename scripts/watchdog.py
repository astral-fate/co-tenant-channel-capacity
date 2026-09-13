"""Supervise a long run so a rate limit or an exhausted quota costs minutes, not hours.

    python scripts/watchdog.py -- --model "groq:qwen/qwen3.8-27b" --stages calibrate,matrix,analyse

Everything after `--` is passed straight to `run_local.py`.

What this is for
----------------
`providers._retry` already handles a single call well: it honours the server's Retry-After, backs
off, and caps the wait. What it cannot see is the shape of the whole run, and that is where the
time goes.

The failure this exists to catch is not a crash. Groq's free tier meters tokens per day. Once that
is spent every call 429s, `_retry` spends its eight attempts over roughly ten minutes, gives up,
and the episode is written as `api_error`. The next episode does the same. Nothing crashes and
nothing is corrupted -- `api_error` episodes are correctly not counted as complete -- but a
40-episode matrix will spend six or seven hours producing no data at all, and the first anyone
knows of it is when they come back to an empty result.

So the watchdog watches two things `_retry` cannot:

  progress    no new output for `--stall-seconds` means the run is wedged. Kill it and start
              again; resume is append-only and tested, so a restart costs one partial episode.

  yield       `api_error` episodes appearing without clean episodes between them means the
              provider is refusing everything. Retrying harder cannot help. Stop, or move to the
              next model in `--fallback`.

Why restarting is safe
----------------------
`runner/test_resume.py` proves the properties this depends on: progress is rebuilt from an
append-only log, a half-written trailing line is skipped, a corrupt or missing `state.json` costs
nothing, and no `(generation, agent)` pair is ever run twice. The watchdog therefore treats
"kill and re-invoke" as a cheap operation, which is what makes a short stall timeout affordable.

State
-----
Every decision is appended to `logs/watchdog.json` as it happens, so the supervisor's own history
survives its own death and a later run can see why an earlier one gave up.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Substrings that mean the provider is refusing on a budget rather than wobbling. A per-minute
#: rate limit is transient and `_retry` should absorb it; these are not, and waiting inside one
#: episode never clears them.
QUOTA_MARKERS = (
    "tokens per day", "tpd", "requests per day", "rpd",
    "quota exceeded", "insufficient_quota", "insufficient credits",
    "daily limit", "billing", "payment required", "402",
    "credit balance", "out of credits",
)

#: Transient markers, recorded but never acted on -- `_retry` owns these.
RATE_MARKERS = ("429", "rate limit", "rate_limit", "too many requests")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Journal:
    """Append-only event log. Mirrors the run's own discipline: the file is the source of truth."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []
        if self.path.exists():
            try:
                self.events = json.loads(self.path.read_text(encoding="utf-8")).get("events", [])
            except (json.JSONDecodeError, OSError):
                self.events = []          # a corrupt journal costs history, never the run

    def add(self, kind: str, **fields) -> None:
        ev = {"at": now(), "kind": kind, **fields}
        self.events.append(ev)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"events": self.events}, indent=2), encoding="utf-8")
        tmp.replace(self.path)            # atomic, so a kill mid-write cannot truncate it
        print(f"[watchdog] {kind}: " +
              " ".join(f"{k}={v}" for k, v in fields.items()), flush=True)


def count_episodes(results_root: Path) -> tuple[int, int]:
    """(clean, api_error) episode counts across every episodes.jsonl under `results_root`.

    Read from the logs rather than from stdout, because the logs are what the run itself treats as
    authoritative and they survive a kill.
    """
    clean = errored = 0
    for f in results_root.rglob("episodes.jsonl"):
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue              # partial trailing line; the run skips it too
                if d.get("api_error"):
                    errored += 1
                else:
                    clean += 1
        except OSError:
            continue
    return clean, errored


class Supervised:
    """One child run, with a reader thread so a stall is measured from real output."""

    def __init__(self, cmd: list[str], log_path: Path, tail: int = 40):
        self.cmd = cmd
        self.log_path = log_path
        self.last_output = time.time()
        self.tail: deque[str] = deque(maxlen=tail)
        self.proc: subprocess.Popen | None = None
        self._fh = None

    def start(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.log_path.open("a", encoding="utf-8")
        self.proc = subprocess.Popen(
            self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=str(ROOT),
        )
        self.last_output = time.time()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            self.last_output = time.time()
            self.tail.append(line.rstrip("\n"))
            if self._fh:
                self._fh.write(line)
                self._fh.flush()
        if self._fh:
            self._fh.close()

    def idle_seconds(self) -> float:
        return time.time() - self.last_output

    def scan(self, markers: tuple[str, ...]) -> str | None:
        for line in list(self.tail):
            low = line.lower()
            for m in markers:
                if m in low:
                    return line.strip()[:200]
        return None

    def stop(self) -> None:
        if not self.proc or self.proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)  # best effort
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=20)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Supervise run_local.py; restart on stall, stop or fail over on quota.")
    ap.add_argument("--stall-seconds", type=int, default=600,
                    help="no output for this long means wedged (default 600)")
    ap.add_argument("--max-restarts", type=int, default=6)
    ap.add_argument("--quota-errors", type=int, default=3,
                    help="consecutive api_error episodes with no clean episode between them "
                         "before the provider is judged exhausted (default 3)")
    ap.add_argument("--fallback", default="",
                    help="comma-separated models to try, in order, when one is exhausted")
    ap.add_argument("--poll", type=int, default=15)
    ap.add_argument("--journal", default=str(ROOT / "logs" / "watchdog.json"))
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("rest", nargs=argparse.REMAINDER,
                    help="-- followed by the run_local.py arguments")
    a = ap.parse_args(argv)

    passthrough = [x for x in a.rest if x != "--"]
    if not passthrough:
        print("nothing to run: put the run_local.py arguments after --", file=sys.stderr)
        return 2

    journal = Journal(Path(a.journal))
    results = Path(a.results)
    models = [m for m in a.fallback.split(",") if m.strip()]

    def cmd_for(model_override: str | None) -> list[str]:
        args = list(passthrough)
        if model_override:
            if "--model" in args:
                args[args.index("--model") + 1] = model_override
            else:
                args += ["--model", model_override]
        return [sys.executable, "-u", str(ROOT / "run_local.py"), *args]

    current_model: str | None = None
    restarts = 0
    base_clean, base_err = count_episodes(results)
    journal.add("start", stall_seconds=a.stall_seconds, clean=base_clean, api_error=base_err,
                fallbacks=len(models))

    while True:
        child = Supervised(cmd_for(current_model), ROOT / "logs" / "watchdog-child.log")
        child.start()
        journal.add("launched", pid=child.proc.pid if child.proc else None,
                    model=current_model or "(as given)", restarts=restarts)

        last_clean, last_err = count_episodes(results)
        streak = 0
        reason = None

        while True:
            time.sleep(a.poll)
            rc = child.proc.poll() if child.proc else None

            if rc is not None:
                reason = "exited-clean" if rc == 0 else f"exited-{rc}"
                break

            clean, err = count_episodes(results)
            if clean > last_clean:
                streak = 0                      # real progress clears the streak
            if err > last_err:
                streak += err - last_err
            last_clean, last_err = clean, err

            if streak >= a.quota_errors:
                reason = "quota-exhausted"
                break

            hit = child.scan(QUOTA_MARKERS)
            if hit:
                journal.add("quota-marker", line=hit)
                reason = "quota-exhausted"
                break

            if child.idle_seconds() > a.stall_seconds:
                reason = "stalled"
                break

        child.stop()
        clean, err = count_episodes(results)
        journal.add("child-ended", reason=reason, clean=clean, api_error=err,
                    gained=clean - base_clean)

        if reason == "exited-clean":
            journal.add("done", clean=clean, api_error=err)
            return 0

        if reason == "quota-exhausted":
            if models:
                current_model = models.pop(0)
                journal.add("failover", to=current_model, remaining=len(models))
                continue
            journal.add("give-up",
                        why="provider refusing and no fallback left; resume with the same "
                            "command once the quota resets -- nothing measured is lost",
                        clean=clean, api_error=err)
            return 3

        restarts += 1
        if restarts > a.max_restarts:
            journal.add("give-up", why="restart budget spent", restarts=restarts,
                        clean=clean, api_error=err)
            return 4
        journal.add("restarting", after=reason, restarts=restarts)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
