"""Run the whole pipeline locally, with logs, a manifest, and resume.

    python run_local.py --smoke          # end-to-end proof on ~5 episodes, a few cents
    python run_local.py                  # the real run
    python run_local.py --force gate     # re-run one stage that resume would have skipped

Five stages, in dependency order:

    check       seven suites; no network, no keys, no GPU
    gate        can the model emit a tool call and do the task's inference at all
    calibrate   find the probe budget where solo success is strictly between 0 and 1
    matrix      the conditions that define Delta
    analyse     recompute every claim and score every registered prediction

Why this exists rather than a shell script
------------------------------------------
Three properties that a chain of `&&` does not give:

* **Every stage's output is both streamed and saved.** A child process's stdout is echoed live
  and written to `logs/<stage>.log`. Capturing it would withhold everything until exit, which on
  a multi-hour stage is indistinguishable from a hang; not capturing it loses the record.
* **A manifest records what actually ran.** `logs/manifest.json` holds each stage's exit code,
  wall-clock, and the artifacts it produced. Re-running reads it, so a completed stage is skipped
  rather than repeated -- and a stage that *failed* is retried rather than silently skipped.
* **Resume is checked against artifacts, not against the manifest alone.** A manifest can be
  written and the artifacts deleted; the episode logs are the ground truth, exactly as inside
  `run.py`, where `done` is rebuilt from the append-only log rather than trusted from state.

The smoke mode runs the identical code path at minimum size. It is not a mock: it makes real API
calls, writes real episodes and runs the real analysis, so a failure it does not catch is a
failure the full run would not have hit either.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
RESULTS = ROOT / "results"
MANIFEST = LOGS / "manifest.json"

sys.path.insert(0, str(ROOT / "runner"))

#: Default inference route. OpenRouter reaches the Anthropic family through one key; `build()`
#: accepts the `family:model` form directly, and `_safe_alias()` turns the ':' and '/' into
#: path-safe characters for the run directory name.
DEFAULT_MODEL = "openrouter:anthropic/claude-haiku-4.5"

#: Swept UPWARD, corrected by measurement: Claude Haiku floored at 6 (0/1). The task returns
#: only "N of 4 positions correct" -- no colour-presence hint -- so it is much harder than the
#: Mastermind comparison suggested.
PROBE_BUDGETS = [8, 12, 16, 20, 24, 28]

#: The pre-registered target solo-success rate. `calibrate.py` chooses the budget whose measured
#: rate is CLOSEST to this among those strictly inside (0, 1). Measured curve for
#: claude-haiku-4.5: 8:0.00  12:0.00  16:0.00  20:0.17  24:0.50  28:0.62 -- so 24 is selected.
CALIB_TARGET = 0.45
CALIB_SEEDS = "0,1,2"

CONDITIONS = "open,wipe"
GENERATIONS = 10
AGENTS = 2
MAX_TURNS = 30

#: Smoke: the same path at the smallest size that still exercises every stage.
SMOKE = {
    "gate_samples": 1,
    "min_passes": 1,
    "budgets": [6],
    "seeds": "0",
    "conditions": "open",
    "generations": 2,     # two, so a second generation actually inherits a substrate
    "agents": 1,
    "max_turns": 12,
}


@dataclass
class StageResult:
    name: str
    status: str = "pending"        # ok | failed | skipped
    exit_code: int | None = None
    seconds: float = 0.0
    started: str = ""
    log: str = ""
    note: str = ""
    artifacts: list[str] = field(default_factory=list)


def tee(cmd: list[str], log_path: Path, cwd: Path = ROOT) -> int:
    """Run a child process, echoing every line to stdout and appending it to `log_path`."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n{'=' * 78}\n$ {' '.join(cmd)}\n"
                 f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n{'=' * 78}\n")
        fh.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1,
                                encoding="utf-8", errors="replace")
        for line in proc.stdout:
            stamped = f"[{time.time() - t0:6.0f}s] {line}"
            print(stamped, end="", flush=True)
            fh.write(stamped)
            fh.flush()
        proc.wait()
        fh.write(f"--- exit {proc.returncode} after {time.time() - t0:.0f}s ---\n")
    return proc.returncode


def load_manifest() -> dict[str, dict]:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # A truncated manifest must not abort the run; the artifacts are the ground truth.
            print("  manifest unreadable -- treating every stage as pending")
    return {}


def save_manifest(man: dict[str, dict]) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(man, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(MANIFEST)          # atomic: a kill mid-write cannot leave a half-file


def episodes_under(path: Path) -> int:
    n = 0
    for f in path.rglob("episodes.jsonl"):
        n += sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
    return n


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="minimum-size end-to-end run")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--force", nargs="*", default=[],
                    help="stage names to re-run even if already complete ('all' for every stage)")
    ap.add_argument("--stages", default="check,gate,calibrate,matrix,analyse")
    a = ap.parse_args(argv)

    cfg = SMOKE if a.smoke else {
        "gate_samples": 3, "min_passes": 2, "budgets": PROBE_BUDGETS, "seeds": CALIB_SEEDS,
        "conditions": CONDITIONS, "generations": GENERATIONS, "agents": AGENTS,
        "max_turns": MAX_TURNS,
    }
    tag = "smoke" if a.smoke else "full"
    LOGS.mkdir(parents=True, exist_ok=True)
    calib_dir = RESULTS / f"calib-{tag}"
    runs_dir = RESULTS / f"runs-{tag}"

    import providers                                            # noqa: PLC0415
    providers.load_env(ROOT / ".env")
    have = providers.available()
    fam = a.model.split(":", 1)[0] if ":" in a.model else None
    print(f"model: {a.model}")
    print(f"aliases with a key present: {len(have)}")
    if fam == "openrouter" and "or-glm" not in have:
        print("  OPENROUTER_API_KEY is not set. Put it in .env as OPENROUTER_API_KEY=...")
        return 2

    man = load_manifest()
    force = set(a.force)
    wanted = [s.strip() for s in a.stages.split(",") if s.strip()]
    print(f"mode: {tag} | stages: {', '.join(wanted)}")
    print(f"logs: {LOGS}\n")

    def done(name: str) -> bool:
        return name not in force and "all" not in force and \
            man.get(name, {}).get("status") == "ok"

    order: list[StageResult] = []

    # ---- check ---------------------------------------------------------------------------
    if "check" in wanted:
        r = StageResult("check", log=str(LOGS / "check.log"))
        if done("check"):
            r.status, r.note = "skipped", "already ok in manifest"
        else:
            t0 = time.time()
            r.started = time.strftime("%Y-%m-%dT%H:%M:%S")
            r.exit_code = tee([sys.executable, "check.py"], Path(r.log))
            r.seconds = round(time.time() - t0, 1)
            r.status = "ok" if r.exit_code == 0 else "failed"
        order.append(r)
        man[r.name] = asdict(r)
        save_manifest(man)
        if r.status == "failed":
            print("\ncheck failed -- the tree is inconsistent; nothing downstream is trustworthy")
            return 1

    # ---- gate ----------------------------------------------------------------------------
    if "gate" in wanted:
        r = StageResult("gate", log=str(LOGS / "gate.log"))
        if done("gate"):
            r.status, r.note = "skipped", "already ok in manifest"
        else:
            t0 = time.time()
            r.started = time.strftime("%Y-%m-%dT%H:%M:%S")
            # min_passes tracks samples in smoke mode; a gate that cannot be satisfied would
            # report a configuration error as a capability failure.
            r.exit_code = tee([sys.executable, "-u", "colab/gate.py", "--model", a.model,
                               "--samples", str(cfg["gate_samples"]),
                               "--min-passes", str(cfg["min_passes"])], Path(r.log))
            r.seconds = round(time.time() - t0, 1)
            r.status = "ok" if r.exit_code == 0 else "failed"
        order.append(r)
        man[r.name] = asdict(r)
        save_manifest(man)
        if r.status == "failed":
            print("\ngate failed -- a model that cannot do the task makes a null Delta meaningless")
            return 1

    # ---- calibrate -----------------------------------------------------------------------
    max_probes = man.get("calibrate", {}).get("note", "")
    max_probes = int(max_probes.split("=")[-1]) if max_probes.startswith("max_probes=") else None

    if "calibrate" in wanted:
        r = StageResult("calibrate", log=str(LOGS / "calibrate.log"))
        if done("calibrate") and max_probes:
            r.status, r.note = "skipped", f"max_probes={max_probes}"
        else:
            t0 = time.time()
            r.started = time.strftime("%Y-%m-%dT%H:%M:%S")
            # Sweep every budget, then choose. Stopping at the first budget strictly inside
            # (0, 1) is NOT the pre-registered rule and gives a different answer: 20 is first in
            # range at 0.17, while 24 at 0.50 is nearest the 0.45 target. Selecting 20 would run
            # the whole matrix at an operating point the preregistration did not pick.
            rates: dict[int, float] = {}
            for budget in cfg["budgets"]:
                out = calib_dir / f"b{budget}"
                if episodes_under(out) < len(cfg["seeds"].split(",")):
                    rc = tee([sys.executable, "-u", "runner/calibrate.py",
                              "--models", a.model, "--budgets", str(budget),
                              "--seeds", cfg["seeds"], "--generations", "1", "--agents", "1",
                              "--max-turns", str(cfg["max_turns"]),
                              "--outdir", str(calib_dir)], Path(r.log))
                    if rc != 0:
                        r.exit_code = rc
                        break
                rate = solo_rate(out)
                if rate is not None:
                    rates[budget] = rate
                print(f"budget {budget}: solo success {rate}")

            usable = {b: v for b, v in rates.items() if 0.0 < v < 1.0}
            chosen = min(usable, key=lambda b: abs(usable[b] - CALIB_TARGET)) if usable else None
            print("calibration curve: "
                  + ", ".join(f"{b}:{v:.2f}" for b, v in sorted(rates.items())))
            if chosen is not None:
                print(f"GATE PASSED at probe budget {chosen} "
                      f"(solo success {usable[chosen]:.2f}, target {CALIB_TARGET})")
            r.seconds = round(time.time() - t0, 1)
            r.artifacts = [str(calib_dir)]
            if chosen is None:
                r.status, r.note = "failed", "no budget gave solo success strictly between 0 and 1"
                order.append(r)
                man[r.name] = asdict(r)
                save_manifest(man)
                print("\nCALIBRATION GATE NOT PASSED. Not running the matrix: with the baseline "
                      "arm pinned, Delta is zero by construction.\nThis is the pre-registered "
                      "stop and a reportable result, not a failure to work around.")
                return 1
            max_probes = chosen
            r.status, r.note, r.exit_code = "ok", f"max_probes={chosen}", 0
        order.append(r)
        man[r.name] = asdict(r)
        save_manifest(man)

    # ---- matrix --------------------------------------------------------------------------
    if "matrix" in wanted:
        r = StageResult("matrix", log=str(LOGS / "matrix.log"))
        if max_probes is None:
            r.status, r.note = "failed", "no max_probes; run the calibrate stage first"
            order.append(r)
            man[r.name] = asdict(r)
            save_manifest(man)
            return 1
        t0 = time.time()
        r.started = time.strftime("%Y-%m-%dT%H:%M:%S")
        before = episodes_under(runs_dir)
        r.exit_code = tee([sys.executable, "-u", "runner/run.py",
                           "--conditions", cfg["conditions"], "--models", a.model,
                           "--seeds", "0", "--generations", str(cfg["generations"]),
                           "--agents", str(cfg["agents"]), "--max-probes", str(max_probes),
                           "--max-turns", str(cfg["max_turns"]), "--outdir", str(runs_dir)],
                          Path(r.log))
        r.seconds = round(time.time() - t0, 1)
        after = episodes_under(runs_dir)
        r.note = f"{after} episode(s) on disk (+{after - before} this run)"
        r.artifacts = [str(runs_dir)]
        r.status = "ok" if r.exit_code == 0 else "failed"
        order.append(r)
        man[r.name] = asdict(r)
        save_manifest(man)

    # ---- analyse -------------------------------------------------------------------------
    if "analyse" in wanted:
        r = StageResult("analyse", log=str(LOGS / "analyse.log"))
        t0 = time.time()
        r.started = time.strftime("%Y-%m-%dT%H:%M:%S")
        # cost.py is deterministic and needs no model call, but it reads capacity.json, so it
        # runs here rather than at check time -- the cost table must never be stale relative to
        # the residual it sits beside.
        rc0 = tee([sys.executable, "src/cost.py"], Path(r.log))
        rc1 = tee([sys.executable, "analyze/verify.py"], Path(r.log))
        rc2 = tee([sys.executable, "analyze/scorecard.py"], Path(r.log))
        r.seconds = round(time.time() - t0, 1)
        r.exit_code = rc0 or rc1 or rc2
        r.status = "ok" if r.exit_code == 0 else "failed"
        order.append(r)
        man[r.name] = asdict(r)
        save_manifest(man)

    # ---- summary -------------------------------------------------------------------------
    print(f"\n{'=' * 78}\nsummary ({tag})\n{'=' * 78}")
    width = max((len(s.name) for s in order), default=8)
    for s in order:
        mark = {"ok": "ok  ", "failed": "FAIL", "skipped": "--  "}.get(s.status, "?   ")
        extra = f"  {s.note}" if s.note else ""
        print(f"  {mark} {s.name:<{width}}  {s.seconds:>7.1f}s{extra}")
    print(f"\nmanifest: {MANIFEST}")
    print(f"episodes: calib={episodes_under(calib_dir)}  matrix={episodes_under(runs_dir)}")

    failed = [s.name for s in order if s.status == "failed"]
    if failed:
        print(f"\n{len(failed)} stage(s) failed: {', '.join(failed)}")
        return 1
    if a.smoke:
        print("\nSmoke run passed end to end. The full run uses the identical code path:")
        print("  python run_local.py")
    return 0


def solo_rate(outdir: Path) -> float | None:
    """Solo success in the baseline arm, excluding api-error episodes.

    An episode that died on an API error is not a data point -- counting it as a failure is how
    an exhausted rate limit becomes a spurious null.
    """
    eps = []
    for f in outdir.rglob("episodes.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                eps.append(json.loads(line))
    clean = [e for e in eps if not e.get("api_error")]
    if not clean:
        return None
    return sum(1 for e in clean if e.get("success")) / len(clean)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
