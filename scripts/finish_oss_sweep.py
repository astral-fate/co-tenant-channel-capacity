"""Finish the gpt-oss-120b calibration sweep: rate-limit-first, resumable, self-diagnosing.

    python scripts/finish_oss_sweep.py            # run it
    python scripts/finish_oss_sweep.py --report   # print the table and stop
    python scripts/finish_oss_sweep.py --only 16  # one budget

Why this exists rather than one `calibrate.py` invocation
---------------------------------------------------------
Groq meters **tokens per minute**, not requests. One episode at budget 16 costs ~41k
tokens against a ~8k/min ceiling, so an episode needs ~5 minutes of quota however it is
issued. Pacing cannot make that cheaper -- it can only stop us slamming into the limit
and then waiting out a backoff as long as the cooldown itself.

Three things follow, and each is implemented below:

* **Pace is computed, not guessed** -- measured tokens-per-call divided into the TPM
  ceiling. Running faster than that manufactures the 429s we then wait on.
* **Budgets run in order of reporting value, not numeric order.** The sweep is worth
  something the moment the crossing budget has a usable n; the budgets above it only
  confirm the climb. An interruption should cost the least useful data.
* **A stalled run is diagnosed, not waited on.** A provider limit and a dead process
  look identical from outside -- both are silence. This supervisor tells them apart by
  probing the API, and picks the response that matches the cause.

`calibrate.py` resumes by default: completed episodes are skipped, and episodes that
ended in an API error are re-run rather than counted. So killing and restarting this is
always safe, which is what lets the supervisor act decisively when it sees a stall.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "results" / "behavioural" / "calibration" / "oss-120b"
MODEL = "oss-120b"
TARGET_N = 3
AGENTS = 3
MAX_TURNS = 40

#: Groq free-tier ceiling, tokens/minute. The binding limit for this model -- requests
#: per minute never came close.
TPM = 8000
SAFETY = 1.4

#: Budgets ordered by what each adds to the report. 16 is the crossing budget and the
#: only one that can show a window, so it runs first; 20 and 24 only confirm the climb
#: above it and are the first thing an interruption should cost.
PRIORITY = [16, 8, 12, 20, 24]

#: How many times a single budget may be restarted before we give up on it and move on.
MAX_RESTARTS = 3

#: The stall timer is a backstop for a genuinely hung process, NOT a performance check.
#: A dead or exited child is detected instantly and for free by `proc.poll()`; the only
#: thing this timeout can add is catching a process that is alive but wedged.
#:
#: It must therefore sit far above the slowest *healthy* turn, because killing a healthy
#: episode is not a neutral act: the tokens it already spent are gone, the restart spends
#: more re-running the same turns, and on a token-metered provider that deepens the very
#: backoff that made the turn look slow. Two earlier versions got this wrong -- 300 s and
#: then 440 s -- while observed turns under a depleted bucket ran 244-378 s. Both killed
#: working episodes and each restart made the next turn slower. Eight restarts, zero
#: episodes gained.
#:
#: So: generous by default, and overridable for a provider that is genuinely wedged.
STALL_MINUTES = int(os.environ.get("SWEEP_STALL_MINUTES", "25"))


def stall_seconds(pace: int) -> int:
    return STALL_MINUTES * 60


# --------------------------------------------------------------------- artifacts

def episodes(budget: int) -> tuple[list[dict], list[dict]]:
    """(clean, errored) for a budget. An API-error episode never enters a rate."""
    d = OUTDIR / f"b{budget}"
    rows: list[dict] = []
    if d.exists():
        for f in d.rglob("episodes.jsonl"):
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return [r for r in rows if not r.get("api_error")], [r for r in rows if r.get("api_error")]


def measured_tokens_per_call() -> int:
    tok = calls = 0
    for b in set(PRIORITY + [4]):
        clean, _ = episodes(b)
        for e in clean:
            u = e.get("usage_total", {})
            tok += u.get("in", 0) + u.get("out", 0)
            calls += len(e.get("turns", []))
    return max(1, tok // max(1, calls))


def report() -> list[int]:
    print(f"\n{'budget':>7}  {'clean':>7}  {'errored':>7}  verdict")
    window = []
    for b in sorted(set(PRIORITY + [4])):
        clean, err = episodes(b)
        if not clean and not err:
            print(f"{b:>7}  {'-':>7}  {'-':>7}  not run")
            continue
        k, n = sum(1 for e in clean if e.get("success")), len(clean)
        if n == 0:
            verdict = "no clean episode"
        elif 0 < k < n:
            verdict, _ = "IN WINDOW", window.append(b)
        elif k == 0:
            verdict = "floor"
        else:
            verdict = "ceiling"
        print(f"{b:>7}  {k:>3}/{n:<3}  {len(err):>7}  {verdict}")
    print()
    print(f"gate window at budget(s): {window}" if window
          else "no budget yet shows solo success strictly inside (0, 1)")
    return window


# --------------------------------------------------------------------- diagnosis

def probe_provider() -> tuple[str, str]:
    """Ask the provider directly what is wrong. Returns (verdict, detail).

    A stalled run gives no information by itself: a rate limit, a revoked key and a dead
    network all present as silence. The listing endpoint costs no tokens, so it can be
    called freely to separate 'the provider is refusing us' from 'the provider is fine
    and the problem is here'.
    """
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return "no-key", "GROQ_API_KEY is not set in this environment"
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}",
                 # Without a real User-Agent the edge proxy answers 403 with Cloudflare
                 # error 1010 -- a browser-signature ban, not an auth failure. Read
                 # naively that looks exactly like a revoked key, and this supervisor
                 # would abort a perfectly healthy run on it.
                 "User-Agent": "covert-channel-sweep/1.0 (+python-urllib)",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return "healthy", f"models endpoint returned {r.status}"
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        if e.code == 429:
            return "rate-limited", f"429 from the provider: {body}"
        # Cloudflare's own codes are edge decisions about the *client*, not statements
        # about the key. Treating them as auth failures is how a working run gets killed.
        if "error code: 10" in body.lower() or "cloudflare" in body.lower():
            return "edge-block", f"{e.code} from the edge proxy, not the API: {body}"
        if e.code in (401, 403):
            return "auth", f"{e.code} -- key rejected: {body}"
        return "http-error", f"{e.code}: {body}"
    except Exception as e:
        return "network", f"{type(e).__name__}: {e}"


def classify_tail(lines: list[str]) -> str | None:
    """What the run's own recent output says, if anything."""
    blob = "\n".join(lines[-40:]).lower()
    if "429" in blob or "rate limit" in blob or "rate_limit" in blob:
        return "the run's own output shows 429s"
    if "tool_use_failed" in blob or "invalid tool call" in blob:
        return "the model is emitting unparseable tool calls"
    if "connection" in blob or "timeout" in blob:
        return "connection or timeout errors"
    return None


# --------------------------------------------------------------------- supervised run

def run_once(budget: int, pace: int) -> tuple[str, list[str]]:
    """Run calibrate.py for one budget under a stall watchdog.

    The child writes straight to a log file rather than through a pipe. Piping it cost us
    the progress output entirely -- the supervisor then had only episode-completion as a
    liveness signal, and since it was killing episodes before they could complete, that
    signal never fired. Watching a file's growth has no buffering semantics to get wrong.

    Returns (outcome, tail) where outcome is 'done' | 'stalled' | 'failed'.
    """
    env = dict(os.environ)
    env["ARS_PACE_SECONDS"] = str(pace)
    env["PYTHONUNBUFFERED"] = "1"
    log = OUTDIR / f"b{budget}-run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-u", str(ROOT / "runner" / "calibrate.py"),
           "--models", MODEL, "--budgets", str(budget), "--seeds", "0",
           "--generations", "1", "--agents", str(AGENTS),
           "--max-turns", str(MAX_TURNS), "--outdir", str(OUTDIR)]

    limit = stall_seconds(pace)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n===== {time.strftime('%H:%M:%S')} budget {budget} pace {pace}s =====\n")
        fh.flush()
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=fh,
                                stderr=subprocess.STDOUT, text=True)

        last_progress = time.time()
        last_size = log.stat().st_size
        n_before = len(episodes(budget)[0])
        last_shown = ""

        while True:
            time.sleep(10)

            if proc.poll() is not None:
                return ("done" if proc.returncode == 0 else "failed"), tail_of(log)

            size = log.stat().st_size
            n_now = len(episodes(budget)[0])
            if size > last_size or n_now > n_before:
                last_size, n_before = size, n_now
                last_progress = time.time()
                line = (tail_of(log)[-1:] or [""])[0].strip()
                if line and line != last_shown:
                    print(f"   {line}", flush=True)
                    last_shown = line
                continue

            idle = time.time() - last_progress
            if idle > limit:
                print(f"\n  !! log has not grown and no episode landed for "
                      f"{idle/60:.1f} min (limit {limit/60:.1f}) — diagnosing", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return "stalled", tail_of(log)


def tail_of(log: Path, n: int = 40) -> list[str]:
    try:
        return log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def run_budget(budget: int, pace: int) -> int:
    """Run one budget to TARGET_N clean episodes, restarting through stalls."""
    restarts = 0
    while True:
        clean, _ = episodes(budget)
        if len(clean) >= TARGET_N:
            print(f"  b{budget}: {len(clean)}/{TARGET_N} clean — done")
            return pace

        print(f"\n=== budget {budget} — {len(clean)}/{TARGET_N} clean, "
              f"pace {pace}s/call, attempt {restarts + 1} ===")
        t0 = time.time()
        outcome, tail = run_once(budget, pace)
        gained = len(episodes(budget)[0]) - len(clean)
        print(f"  b{budget}: +{gained} clean in {time.time() - t0:.0f}s → {outcome}")

        if outcome == "done":
            if len(episodes(budget)[0]) >= TARGET_N:
                return pace
            # exited cleanly but short of target: calibrate.py ran its allotment
            if gained == 0:
                print(f"  b{budget}: no progress and a clean exit — moving on")
                return pace
            continue

        # --- something went wrong: find out what, then choose a response -------------
        verdict, detail = probe_provider()
        said = classify_tail(tail)
        print(f"  diagnosis: provider={verdict} ({detail})")
        if said:
            print(f"             run output: {said}")

        if verdict == "auth":
            print("  ABORT: the key is rejected. Retrying cannot fix that.")
            return pace
        if verdict == "edge-block":
            # The edge proxy refused the *probe*, so the probe told us nothing about the
            # run. Fall through to a plain restart rather than acting on a non-diagnosis.
            print("  the probe itself was edge-blocked — it says nothing about the run; "
                  "treating this as an unexplained stall")
        if verdict == "no-key":
            print("  ABORT: GROQ_API_KEY is not set in this process.")
            return pace

        restarts += 1
        if restarts > MAX_RESTARTS:
            print(f"  b{budget}: {MAX_RESTARTS} restarts without finishing — moving on "
                  f"so the remaining budgets still get a turn")
            return pace

        if verdict == "rate-limited" or (said and "429" in said):
            pace = min(120, int(pace * 1.8) + 1)
            wait = 90
            print(f"  provider is rate-limiting: slowing to {pace}s/call and "
                  f"waiting {wait}s for the bucket to refill")
            time.sleep(wait)
        elif verdict in ("network", "http-error"):
            print("  provider unreachable: waiting 60s and retrying at the same pace")
            time.sleep(60)
        else:
            # Provider says it is healthy, so the stall was local -- a very long
            # generation, or a wedged request. Restarting costs one episode at most.
            print("  provider is healthy, so the stall was local — restarting the budget")
            time.sleep(5)


def main() -> int:
    ap = argparse.ArgumentParser(description="Finish the oss-120b sweep, supervised.")
    ap.add_argument("--report", action="store_true", help="print the table and stop")
    ap.add_argument("--pace", type=int, default=0, help="seconds between calls (0 = compute)")
    ap.add_argument("--only", default="", help="comma-separated budgets, overriding priority")
    a = ap.parse_args()

    if a.report:
        report()
        return 0

    tpc = measured_tokens_per_call()
    pace = a.pace or max(1, round(SAFETY * 60 * tpc / TPM))
    print(f"measured {tpc:,} tokens/call over the episodes already on disk")
    print(f"ceiling {TPM:,} tokens/min → pacing at {pace}s/call "
          f"(~{60 // pace} calls/min, ~{60 // pace * tpc:,} tokens/min)")
    print(f"stall watchdog: {stall_seconds(pace) // 60} min with no log growth and no new episode")

    order = [int(x) for x in a.only.split(",") if x.strip()] or PRIORITY
    print(f"budget order (by reporting value): {order}")

    for b in order:
        try:
            pace = run_budget(b, pace)
        except KeyboardInterrupt:
            print("\ninterrupted — everything written is kept; re-run to continue")
            report()
            return 130
        report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
