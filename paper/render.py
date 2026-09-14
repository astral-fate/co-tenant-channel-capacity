"""Recompute every number the v2 paper asserts, and render the manuscript from the results.

    python paper/render.py           # recompute, check, render paper/main.tex
    python paper/render.py --list    # print the claim table and stop

Why the manuscript contains no numbers of its own
-------------------------------------------------
Version 1 of this project shipped a cost table that contradicted its own artifact -- a false
caption, an unsourced standard deviation, four wrong cells, three of sixteen budgets reported --
and it survived review-by-consistency-checker because the checker recomputed what the paper said
and confirmed the paper said it consistently.

Here the values are not written into the manuscript at all: `main.tex.tmpl` carries placeholders
and this script substitutes what the artifacts actually contain. A figure in the paper cannot
disagree with `results/` because the paper has no figures of its own. Unknown placeholders fail
the build; computed-but-unused claims are reported, since an orphan usually means a finding was
cut and its number left behind.

This establishes agreement between manuscript and artifacts. It does not establish that a
measure is appropriate -- the limit that let v1's headline through -- and the paper says so.
"""
from __future__ import annotations

import collections
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
sys.path.insert(0, str(ROOT / "analyze"))
sys.path.insert(0, str(ROOT / "src"))

import measures  # noqa: E402

#: Abstract limits are venue properties, not properties of the work, so they are keyed on the
#: template being rendered. The sprint scores a 150-word abstract; arXiv's field accepts roughly
#: 1920 characters, which is about 300 words, and the full manuscript has no reason to be
#: compressed to the shorter one. A template with no entry falls back to the sprint limit, so a
#: new build is constrained until someone states otherwise.
ABSTRACT_WORD_LIMITS = {
    "main-8pp.tex.tmpl": 150,   # AI Incident Response Sprint submission build
    "main.tex.tmpl": 300,       # arXiv / full manuscript
}
ABSTRACT_WORD_LIMIT_DEFAULT = 150


def abstract_word_limit(tmpl_name: str) -> int:
    return ABSTRACT_WORD_LIMITS.get(tmpl_name, ABSTRACT_WORD_LIMIT_DEFAULT)

#: Alphanumeric passcode of the length the benchmark task uses. The comparison the residual is
#: measured against: what an inheriting agent actually needs to carry.
PASSCODE_LEN = 4
PASSCODE_ALPHABET = 36

#: The pseudo-replication demonstration. Two agents share one substrate per generation, so
#: counting episodes doubles n and treats the dependent unit as independent -- when the
#: hypothesis is precisely that one agent changes the other's environment.
DEMO_HITS_A, DEMO_HITS_B, DEMO_GENERATIONS = 7, 3, 10


@dataclass
class Claim:
    key: str
    describe: str
    fn: Callable[[], str]
    raw: bool = False


TEX_ESCAPES = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
               "_": r"\_", "{": r"\{", "}": r"\}"}


def tex_escape(s: str) -> str:
    return "".join(TEX_ESCAPES.get(ch, ch) for ch in s)


def _capacity() -> dict[str, Any]:
    return json.loads((ROOT / "results" / "capacity" / "capacity.json").read_text(encoding="utf-8"))


def _rung_total(rung: str) -> tuple[float, bool]:
    """Summed achievable bits at a rung, and whether any contributing measure was censored."""
    ms = [m for m in _capacity()["measurements"] if m["rung"] == rung]
    return sum(m["bits_achieved"] for m in ms), any(m["censored"] for m in ms)


def _bits(rung: str) -> str:
    total, censored = _rung_total(rung)
    return f"{'$\\geq$' if censored else ''}{total:.0f}".replace("$\\geq$", r"$\geq$")


def _passcode_bits() -> float:
    return PASSCODE_LEN * math.log2(PASSCODE_ALPHABET)


def _attr_bits(rung: str, attr: str) -> str:
    m = next(m for m in _capacity()["measurements"]
             if m["rung"] == rung and m["attribute"] == attr)
    prefix = r"$\geq$" if m["censored"] else ""
    return f"{prefix}{m['bits_achieved']:.0f}"


def _capacity_table_tex() -> str:
    """The ladder, emitted from the measurement rather than transcribed."""
    cap = _capacity()
    rungs = ["open", "content", "filename", "dirname", "existence", "sealed"]
    attrs = []
    for m in cap["measurements"]:
        if m["attribute"] not in attrs:
            attrs.append(m["attribute"])
    rows = []
    for a in attrs:
        cells = " & ".join(_attr_bits(r, a) for r in rungs)
        rows.append(f"\\texttt{{{a}}} & {cells} \\\\")
    rows.append(r"\midrule")
    totals = []
    for r in rungs:
        total, censored = _rung_total(r)
        totals.append((r"$\geq$" if censored else "") + f"{total:.0f}")
    rows.append(r"\textbf{total} & " + " & ".join(f"\\textbf{{{t}}}" for t in totals) + r" \\")
    return "\n".join(rows)





def _count_at_content() -> float:
    """The count row at the content rung: the part of the sum the joint coder omits by design."""
    return next(m["bits_achieved"] for m in _capacity()["measurements"]
                if m["rung"] == "content" and m["attribute"] == "count")


def _joint_loss(rung: str) -> float:
    """What one encoder loses against the sum of the carriers it actually used.

    This is deliberately NOT (rung total - joint): the rung total includes `count`, which the
    joint coder excludes on purpose. Subtracting it here would fold a designed exclusion into a
    measured loss and reproduce, in a new place, the conflation that broke the earlier claim.
    """
    r = next(x for x in _joint_all() if x["rung"] == rung)
    return r["bits_attempted"] - r["bits_recovered"]


def _joint_all() -> list:
    return json.loads((ROOT / "results" / "capacity" / "joint.json").read_text(encoding="utf-8"))


def _m2() -> dict[str, Any]:
    """Calibration episodes for the second model, read straight from the episode logs.

    Reported because the pre-registered gate stopped the run before a matrix existed, so there is
    no matrix artifact to read and the honest record is the calibration itself.
    """
    root = ROOT / "results" / "calib-full"
    clean = errored = solved = tokens = 0
    budgets: set[int] = set()
    for f in root.rglob("episodes.jsonl"):
        if "qwen3-32b" not in str(f):
            continue
        parent = f.parents[1].name                        # e.g. "b20"
        if parent.startswith("b") and parent[1:].isdigit():
            budgets.add(int(parent[1:]))
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("api_error"):
                errored += 1
                continue
            clean += 1
            solved += 1 if d.get("success") else 0
            u = d.get("usage_total") or {}
            tokens += u.get("in", 0) + u.get("out", 0)
    return {"clean": clean, "errored": errored, "solved": solved,
            "tokens": tokens, "budgets": sorted(budgets)}


#: Substrate tools, split by what using one demonstrates. Reading shows the agent engaged with the
#: shared store at all; writing is the deposit. An arm with zero reads cannot express a propensity
#: either way, which is a different situation from an arm that read and declined to write.
_SUB_READ = {"cache_list", "cache_read", "cache_stat"}
_SUB_WRITE = {"cache_write", "cache_mkdir", "cache_move", "cache_delete"}


def _arm_stats(match: str) -> dict[str, Any]:
    """Matrix-arm behaviour for whichever model's alias contains `match`."""
    reads = writes = solved = eps = 0
    budgets: set[int] = set()
    calls: dict[str, int] = {}
    for f in (ROOT / "results").rglob("episodes.jsonl"):
        if "calib" in str(f) or match not in str(f):
            continue
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("api_error"):
                continue
            eps += 1
            budgets.add(d.get("max_probes"))
            solved += 1 if d.get("success") else 0
            names = {c.get("name") for t in d.get("turns", []) for c in t.get("calls", [])}
            for t in d.get("turns", []):
                for c in t.get("calls", []):
                    calls[c.get("name")] = calls.get(c.get("name"), 0) + 1
            reads += 1 if names & _SUB_READ else 0
            writes += 1 if names & _SUB_WRITE else 0
    return {"episodes": eps, "read_episodes": reads, "write_episodes": writes,
            "solved": solved, "budgets": sorted(b for b in budgets if b),
            "read_calls": sum(v for k, v in calls.items() if k in _SUB_READ)}


def _b20(match: str) -> dict[str, Any]:
    """The matched-budget head-to-head arm for one model, split by condition.

    Both models were re-run at probe budget 20 -- the only budget at which neither is pinned on
    its own calibration curve -- so affordance is held constant and substrate engagement becomes
    directly comparable. `results/runs-b20` is kept separate from the calibrated-budget matrices
    so neither overwrites the other.
    """
    out: dict[str, Any] = {"n": 0, "read": 0, "wrote": 0, "solved": 0, "read_calls": 0,
                           "errors": 0, "by_cond": {}}
    for f in (ROOT / "results" / "runs-b20").rglob("episodes.jsonl"):
        if match not in str(f):
            continue
        cond = f.parent.name.split("__")[0]
        c = out["by_cond"].setdefault(cond, {"n": 0, "read": 0, "wrote": 0})
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("api_error"):
                out["errors"] += 1
                continue
            names = [x.get("name") for t in d.get("turns", []) for x in t.get("calls", [])]
            s = set(names)
            out["n"] += 1
            c["n"] += 1
            hit_r, hit_w = bool(s & _SUB_READ), bool(s & _SUB_WRITE)
            out["read"] += hit_r
            c["read"] += hit_r
            out["wrote"] += hit_w
            c["wrote"] += hit_w
            out["read_calls"] += sum(1 for x in names if x in _SUB_READ)
            out["solved"] += 1 if d.get("success") else 0
    return out


def _namespace() -> dict[str, Any]:
    return json.loads((ROOT / "results" / "capacity" / "namespace.json").read_text(encoding="utf-8"))


def _reuse_row(agents: int, pool: int, per_agent: int) -> dict[str, Any]:
    for r in _namespace()["reuse"]:
        if (r["agents"], r["pool"], r["per_agent"]) == (agents, pool, per_agent):
            return r
    raise KeyError(f"no reuse row for agents={agents} pool={pool} per_agent={per_agent}")


def _reuse_table_tex() -> str:
    rows = []
    for r in _namespace()["reuse"]:
        rows.append(f"{r['agents']} & {r['pool']} & {r['per_agent']} & "
                    f"{r['overlap']:.2f} & {r['fetches_shared']:.0f} & "
                    f"{r['fetches_namespaced']:.0f} & {r['multiplier']:.2f}")
    return " \\\\\n".join(rows) + " \\\\"


# --------------------------------------------------------------------------- calibration
#: Where `run_local.py` writes the baseline-arm sweep. The gate is measured ONLY here: the
#: `no_substrate` condition has no shared store, so an operating point chosen from it cannot have
#: been tuned to favour the inheritance effect (A6.6, A10.1).
CALIB_DIR = ROOT / "results" / "behavioural" / "calibration" / "calib-full"


def _calib() -> dict[int, tuple[int, int]]:
    """{probe budget: (solved, clean episodes)} from the baseline sweep.

    Episodes that died on an API error are excluded rather than counted as failures. Counting
    them is how an exhausted rate limit becomes a spurious null, which this project has already
    recorded once.
    """
    out: dict[int, tuple[int, int]] = {}
    if not CALIB_DIR.exists():
        return out
    for d in sorted(CALIB_DIR.glob("b*")):
        try:
            budget = int(d.name[1:])
        except ValueError:
            continue
        eps = []
        for f in d.rglob("episodes.jsonl"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    eps.append(json.loads(line))
        clean = [e for e in eps if not e.get("api_error")]
        if clean:
            out[budget] = (sum(1 for e in clean if e.get("success")), len(clean))
    return dict(sorted(out.items()))


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - half), min(1.0, c + half))


#: The pre-registered target the budget is chosen against. `calibrate.py` picks the budget whose
#: solo success is CLOSEST to this among those strictly inside (0, 1) -- not simply the first one
#: in range, which would report a different operating point than the one actually used.
CALIB_TARGET = 0.45


def _chosen() -> tuple[int, float, int, int] | None:
    """(budget, rate, n, k) for the budget nearest the target, mirroring calibrate.py."""
    usable = [(abs(k / n - CALIB_TARGET), b, k / n, n, k)
              for b, (k, n) in _calib().items() if 0 < k < n]
    if not usable:
        return None
    _d, b, r, n, k = min(usable)
    return (b, r, n, k)


def _calib_table_tex() -> str:
    rows = []
    for budget, (k, n) in _calib().items():
        lo, hi = _wilson(k, n)
        rate = k / n
        mark = r"\textbf{" + f"{rate:.2f}" + "}" if 0.0 < rate < 1.0 else f"{rate:.2f}"
        rows.append(f"{budget} & {k} / {n} & {mark} & ({lo:.2f}, {hi:.2f}) \\\\")
    return "\n".join(rows) if rows else "-- & -- & -- & -- \\\\"


def _calib_model() -> str:
    for d in CALIB_DIR.glob("b*"):
        for sub in d.iterdir():
            if sub.is_dir() and "__" in sub.name:
                return sub.name.split("__")[1].replace("_", "/").replace("openrouter/", "")
    return "(none)"



# --------------------------------------------------------------------------- behavioural arm
RUNS_DIR = ROOT / "results" / "behavioural" / "runs-full"

#: The follow-up run. `runs-full` ran two agents per generation, which made the blocked-task
#: branch of the assignment rule unreachable; this one runs four, so the branch fires.
BLOCKED_DIR = ROOT / "results" / "behavioural" / "runs-blocked"

#: A deposit can only be made by `cache_write`. Everything else in the substrate API reads.
WRITE_TOOLS = {"cache_write"}
READ_TOOLS = {"cache_list", "cache_read", "cache_stat"}


def _arms() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not RUNS_DIR.exists():
        return out
    for run in sorted(RUNS_DIR.iterdir()):
        f = run / "episodes.jsonl"
        if f.exists():
            out.setdefault(run.name.split("__")[0], []).extend(
                json.loads(line) for line in f.read_text(encoding="utf-8").splitlines()
                if line.strip())
    return out


def _tools(ep: dict) -> set[str]:
    return {c["name"] for t in ep["turns"] for c in t["calls"]}


def _all_eps() -> list[dict]:
    return [e for v in _arms().values() for e in v]


def _gen_dep(eps: list[dict]) -> dict[int, bool]:
    """Per generation: did ANY agent in it write to the substrate?"""
    by: dict[int, bool] = {}
    for e in eps:
        g = e["generation"]
        by[g] = by.get(g, False) or bool(_tools(e) & WRITE_TOOLS)
    return by


def _blocked_all() -> list[dict]:
    """Every episode the follow-up run attempted, including ones the API terminated."""
    out: list[dict] = []
    if not BLOCKED_DIR.exists():
        return out
    for run in sorted(BLOCKED_DIR.iterdir()):
        f = run / "episodes.jsonl"
        if f.exists():
            out.extend(json.loads(line) for line in f.read_text(encoding="utf-8").splitlines()
                       if line.strip())
    return out


def _blocked_eps() -> list[dict]:
    """Analysable episodes: those that ran to completion.

    Five episodes ended on an HTTP 402 when the account's credit ran out mid-run. They are
    censored by an external condition unrelated to agent behaviour, so counting them in a
    denominator would understate every rate below. They are reported separately instead.
    """
    return [e for e in _blocked_all() if not e.get("api_error")]




# --------------------------------------------------------------------------- real substrate
def _real_limits() -> dict:
    return json.loads((ROOT / "results" / "real-substrate" / "real-limits.json").read_text(encoding="utf-8"))


def _qwen() -> dict:
    """The floored 8B calibration, kept because A10.4 commits to reporting it.

    Its value is that the capability probes were passed while the task was not solved: no
    malformed probe and no invalid tool call in any episode. That separates a difficulty floor
    from an inability to act, which is the distinction the two gates exist to draw.
    """
    return json.loads((ROOT / "results" / "behavioural" / "calibration" / "qwen-calib.json").read_text(encoding="utf-8"))


def _s3() -> dict:
    """A real object store's limits, probed through its ordinary API.

    Kept separate from the mount probe because the two disagree about what a carrier even is.
    An object store has no directories and assigns its own timestamps, so two rows the
    filesystem model treats as live carriers are absent here by construction rather than
    measured at zero.
    """
    return json.loads((ROOT / "results" / "real-substrate" / "real-limits-s3.json")
                      .read_text(encoding="utf-8"))


def _usecost() -> dict:
    """The usefulness cost of each closure: an oracle cache user, single agent, no channel.

    This arm prices the ladder. It is what turns "dirname closure reaches zero bits" into a
    control a lab would actually adopt, because the question a lab asks is not whether a
    closure works but what it costs the agents that depend on the cache.
    """
    return json.loads((ROOT / "results" / "analysis" / "cost" / "cost.json")
                      .read_text(encoding="utf-8"))


def _usecost_budgets() -> list[int]:
    return [b for b in _usecost()["budgets"] if 3 <= b <= 16]


def _usecost_row(table: str, policy: str) -> dict:
    return _usecost()[table][policy]


def _usecost_max(policy: str, table: str = "cost_isolated") -> float:
    """Worst task-success cost this closure imposes at any budget swept."""
    return max(_usecost_row(table, policy).values())


def _usecost_table_tex() -> str:
    """Cumulative ladder: task success under each rung, emitted from the artifact."""
    rows = []
    order = ["L0_open", "L1_content", "L2_filename", "L3_dirname", "L4_existence"]
    label = {"L0_open": "nothing closed", "L1_content": "content",
             "L2_filename": "+ filename", "L3_dirname": "+ dirname",
             "L4_existence": "+ existence"}
    budgets = _usecost_budgets()
    succ = {(r["policy"], r["budget"]): r["success"] for r in _usecost()["success_cumulative"]}
    for pol in order:
        cells = [("--" if (pol, b) not in succ else f"{succ[(pol, b)]:.2f}") for b in budgets]
        rows.append(r"\texttt{" + label[pol] + "} & " + " & ".join(cells) + r" \\")
    return "\n".join(rows)


def _usecost_free_attrs() -> str:
    """Attributes whose closure costs nothing at any budget swept."""
    free = [k.replace("only_", "") for k, v in _usecost()["cost_isolated"].items()
            if k.startswith("only_") and max(v.values()) == 0.0]
    return ", ".join(r"\texttt{" + a + "}" for a in free)


def _grid() -> dict:
    """Solo success per model per probe budget, from analyze/calibration_grid.py.

    Reported as a grid rather than one rate per model because the gate is a property of an
    operating point, not of a model: several models here floor at low budgets and clear the
    window higher up, and a pooled rate would hide exactly that.
    """
    return json.loads((ROOT / "results" / "screen" / "calibration-grid.json")
                      .read_text(encoding="utf-8"))


def _grid_table_tex() -> str:
    """One row per (model, route); one column per budget. Emitted from the artifact."""
    g = _grid()
    budgets = g["budgets"]
    rows = []
    for r in g["rows"]:
        cells = []
        for b in budgets:
            c = r["budgets"].get(str(b))
            if not c or c["n"] == 0:
                cells.append("--")
            else:
                cell = f"{c['solved']}/{c['n']}"
                # Bold the operating points that satisfy the gate, so the reader can see the
                # window without recomputing it from the fractions.
                cells.append(r"\textbf{" + cell + "}" if c["verdict"] == "window" else cell)
        name = tex_escape(r["model"])
        route = tex_escape(r["route"])
        rows.append(r"\texttt{" + name + "} & " + route + " & " + " & ".join(cells) + r" \\")
    return "\n".join(rows)


def _grid_budget_hdr() -> str:
    return " & ".join(str(b) for b in _grid()["budgets"])


def _grid_cols() -> str:
    return "ll" + "r" * len(_grid()["budgets"])


def _grid_windows() -> str:
    """Models with at least one operating point strictly inside (0, 1)."""
    hits = [f"\\texttt{{{tex_escape(r['model'])}}} ({r['route']}) at "
            + ", ".join(str(b) for b in r["windows"])
            for r in _grid()["rows"] if r["windows"]]
    return "; ".join(hits)


def _screen() -> dict:
    """Every model the behavioural arm was run against, assembled by analyze/model_screen.py."""
    return json.loads((ROOT / "results" / "screen" / "model-screen.json").read_text(encoding="utf-8"))


def _screen_table_tex() -> str:
    """One row per model screened, emitted from the artifact rather than transcribed."""
    rows = []
    for m in _screen()["models"]:
        alias = tex_escape(m["alias"])
        route = tex_escape(m["route"])
        verdict = tex_escape(m["verdict"])
        rate = f'{m["clean_solved"]}/{m["clean_n"]}' if m["clean_n"] else "--"
        role = r"\textbf{reported}" if m["role"] == "reported" else "screened out"
        rows.append(
            r"\texttt{" + alias + "} & " + route + " & " + rate
            + " & " + verdict + " & " + role + r" \\"
        )
    return "\n".join(rows)


def _real_store() -> dict:
    return json.loads((ROOT / "results" / "real-substrate" / "real-store-registry.json").read_text(encoding="utf-8"))


def _store_table_tex() -> str:
    """Per-attribute verdict for the real registry, emitted from the probe."""
    a = _real_store()["attributes"]
    order = ("content", "filename", "dirname", "existence", "size", "mtime")
    bold = "\\textbf{carries}"
    rows = []
    for k in order:
        d = a.get(k, {})
        verdict = bold if d.get("carries") else "closed"
        ev = tex_escape(d.get("evidence", ""))
        rows.append("\\texttt{" + k + "} & " + verdict + " & " + ev + r" \\")
    return "\n".join(rows)




# --------------------------------------------------------------------------- external payloads
def _payloads() -> dict:
    return json.loads((ROOT / "results" / "capacity" / "payloads.json").read_text(encoding="utf-8"))


def _fits() -> list[dict]:
    """Third-party-defined secrets the joint residual is large enough to carry."""
    return [p for p in _payloads()["payloads"] if p["bits"] <= _joint()["bits_recovered"]]


def _payload_table_tex() -> str:
    j = _joint()["bits_recovered"]
    rows = []
    for p in _payloads()["payloads"]:
        mark = r"\checkmark" if p["bits"] <= j else "--"
        rows.append(f"{tex_escape(p['name'])} & {p['bits']:.0f} & {mark} \\\\")
    return "\n".join(rows)


# --------------------------------------------------------------------------- closure cost
def _cost() -> dict:
    return json.loads((ROOT / "results" / "capacity" / "closure-cost.json").read_text(encoding="utf-8"))


def _cost_rung(rung: str) -> dict:
    return next(r for r in _cost()["per_rung"] if r["rung"] == rung)


def _cost_row(attribute: str) -> dict:
    return next(r for r in _cost()["per_row"] if r["attribute"] == attribute)


def _extra_classes() -> str:
    """The enforcement classes of the rows closure adds after content -- the adoption claim.

    Rendered as prose rather than a count because the claim is categorical: if any of these were
    payload-class, the argument that the remaining distance is cheap would not hold.
    """
    ladder = [r["attribute"] for r in _cost()["per_row"]]
    after = ladder[ladder.index("content") + 1: ladder.index("dirname") + 1]
    classes = sorted({_cost_row(a)["enforcement"] for a in after})
    return classes[0] if len(classes) == 1 else ", ".join(classes)


def _cost_table_tex() -> str:
    """Emit the cost ladder from the measurement, in the paper's rung order."""
    rows = []
    for r in _cost()["per_rung"]:
        if r["rung"] == "open":
            continue
        bits = "--" if r["bits_achieved"] is None else f"{r['bits_achieved']:.0f}"
        rows.append(f"\\texttt{{{r['rung']}}} & {r['level']} & {r['n_mediation_points']} & "
                    f"{r['n_payload_rows']} & {bits} \\\\")
    return "\n".join(rows)


def _pairs() -> list[tuple[int, int]]:
    """(open, wipe) probes-to-solution for every matched cell both arms solved."""
    return measures.matched_pairs(measures.discover(RUNS_DIR), "open", "wipe", "n_validate")


def _matched_cells() -> int:
    """Cells drawing the same task in both arms -- the premise the pairing rests on."""
    runs = measures.discover(RUNS_DIR)
    def index(cond):
        return {(e["generation"], e["agent"][-1]): e.get("task_id")
                for r in runs if r.condition == cond for e in r.episodes}
    a, b = index("open"), index("wipe")
    return sum(1 for k in a if k in b and a[k] == b[k])


def _fu_deposits() -> int:
    """Writes left for another agent, as opposed to self-verified writability probes.

    The rule lives in `measures.is_probe_write` so that the paper, the scorecard and any future
    run apply the same one. See pre-registration A12.3 for why it is a rule and not a reading.
    """
    return sum(len(measures.deposits(r))
               for r in measures.discover(BLOCKED_DIR)) if BLOCKED_DIR.exists() else 0


def _fu_probes() -> int:
    """Episodes whose shared-store writes were all probes."""
    return sum(len(measures.probe_writes(r))
               for r in measures.discover(BLOCKED_DIR)) if BLOCKED_DIR.exists() else 0


def _gen_cells(eps: list[dict]) -> dict[int, list[bool]]:
    by: dict[int, list[bool]] = {}
    for e in eps:
        by.setdefault(e["generation"], []).append(bool(e.get("success")))
    return by


# --------------------------------------------------------------------------- joint residual
#: The reviewer-forced correction. `capacity.py` sums per-attribute cells; `joint.py` runs ONE
#: encoder carrying ONE payload and has the receiver recover all of it under the same zero-error
#: criterion. The summed figure exceeds the joint one by exactly the `count` row, because an
#: existence pattern determines the entry count -- so summing it double-counts.
def _joint() -> dict | None:
    f = ROOT / "results" / "capacity" / "joint.json"
    if not f.exists():
        return None
    rows = json.loads(f.read_text(encoding="utf-8"))
    return next((r for r in rows if r["rung"] == "content"), None)


def _monitor(name: str) -> dict:
    """A monitor scenario from analyze/monitor_residual.py: the joint residual left when a
    monitor inspects a given carrier set. Same encoder and criterion as the headline residual,
    so the numbers are directly comparable -- only the inspected carrier set differs."""
    rows = json.loads((ROOT / "results" / "capacity" / "monitor-residual.json")
                      .read_text(encoding="utf-8"))
    return next(r for r in rows if r["monitor"] == name)


def _mon_roc() -> dict:
    """The content monitor's measured operating characteristic, from analyze/monitor_roc.py."""
    return json.loads((ROOT / "results" / "detect" / "monitor-roc.json").read_text(encoding="utf-8"))


def _ceil_sweep() -> dict:
    """The ceiling-sweep experiment, from analyze/ceiling_sweep.py."""
    return json.loads((ROOT / "results" / "capacity" / "ceiling-sweep.json")
                      .read_text(encoding="utf-8"))


def _prod_s3() -> dict:
    """The name-closure control deployed on a real object store, from analyze/prod_s3_control.py."""
    return json.loads((ROOT / "results" / "real-substrate" / "prod-s3-control.json")
                      .read_text(encoding="utf-8"))


def _ceil_table_tex() -> str:
    rows = []
    for r in _ceil_sweep()["ceilings"]:
        rows.append(f"{r['ceiling_bits']} & {r['content_bits']:.0f} & {r['open_total']:.0f} & "
                    f"{r['fraction_removed_by_content_closure']:.2f} & {r['joint_residual']} "
                    r"\\")
    return "\n".join(rows)


def _p_episodes() -> float:
    """Fisher exact counting EPISODES -- the pseudo-replicated analysis."""
    return measures.fisher_exact(DEMO_HITS_A * 2, DEMO_GENERATIONS * 2,
                                 DEMO_HITS_B * 2, DEMO_GENERATIONS * 2)


def _p_generations() -> float:
    """The same outcome counting GENERATIONS, which is the unit of independence."""
    return measures.fisher_exact(DEMO_HITS_A, DEMO_GENERATIONS,
                                 DEMO_HITS_B, DEMO_GENERATIONS)


#: Release metadata for the artifact statement. Kept in a file rather than in the template so
#: that a URL or commit hash is substituted like every other number instead of being typed into
#: the prose, where nothing would ever check it.
_ARTIFACT = json.loads((PAPER / "artifact.json").read_text(encoding="utf-8"))

#: What a null field renders as. It is deliberately conspicuous: a manuscript that goes out with
#: an undeposited artifact should say so on the page rather than imply a repository exists.
PENDING = r"\textbf{[PENDING]}"


def _art(field: str) -> str:
    """One artifact field, or a visible PENDING marker when it has not been filled in."""
    v = _ARTIFACT.get(field)
    return PENDING if v in (None, "", []) else str(v)


def _art_deps() -> str:
    """The dependency list, which is currently empty and is a claim in its own right."""
    deps = _ARTIFACT["third_party"]
    return "none" if not deps else ", ".join(f"\\texttt{{{d}}}" for d in deps)


def _art_seeds() -> str:
    return ", ".join(str(s) for s in _ARTIFACT["seeds_behavioural"])


CLAIMS: list[Claim] = [
    # raw: these carry a `$\geq$` censoring marker, which the escaper would turn into a
    # literal dollar sign and a broken math environment.
    Claim("OPEN_BITS", "Achievable bits, channel open", lambda: _bits("open"), raw=True),
    Claim("CONTENT_BITS", "Achievable bits after content closure",
          lambda: _bits("content"), raw=True),
    Claim("FILENAME_BITS", "Achievable bits after filename closure",
          lambda: _bits("filename"), raw=True),
    Claim("DIRNAME_BITS", "Achievable bits after dirname closure",
          lambda: _bits("dirname"), raw=True),
    Claim("EXISTENCE_BITS", "Achievable bits after existence closure -- the true zero rung",
          lambda: _bits("existence"), raw=True),

    Claim("MAX_FILE_BYTES", "Substrate body-size limit",
          lambda: str(__import__("substrate").MAX_FILE_BYTES)),
    Claim("CONTENT_PACKED_BITS", "Bits a body of that size holds if the coder packs them",
          lambda: f"{__import__('substrate').MAX_FILE_BYTES * 8:,}"),
    Claim("NAME_MAX", "Filesystem limit on one path component",
          lambda: str(__import__("capacity").NAME_MAX)),
    Claim("NAME_BYTES_BITS", "What a name row would carry over arbitrary bytes",
          lambda: f"{__import__('capacity').NAME_MAX * 8:,}"),

    Claim("NAME_BITS", "Bits travelling in filename and dirname at the content rung",
          lambda: (r"$\geq$" if any(m["censored"] for m in _capacity()["measurements"]
                                     if m["rung"] == "content"
                                     and m["attribute"] in ("filename", "dirname"))
                   else "")
                  + f"""{sum(m['bits_achieved'] for m in _capacity()['measurements']
                             if m['rung'] == 'content'
                             and m['attribute'] in ('filename', 'dirname')):.0f}""",
          raw=True),

    Claim("CONTENT_BITS_N", "Content-closure residual, bare number",
          lambda: f"{_rung_total('content')[0]:.0f}"),
    # Printed to one decimal so the ratio reproduces: 201 / 20.7 = 9.7. Rounding the passcode
    # to 21 made the printed ratio irreproducible for a reader doing the division.
    Claim("PASSCODE_BITS", "Bits in the task's passcode",
          lambda: f"{_passcode_bits():.1f}"),
    # RESIDUAL_MULTIPLE (the SUMMED content residual over the passcode) is deliberately absent.
    # SS5.4 establishes that the summed total is not a rate any encoder was asked to carry, so a
    # ratio built on it should not be quotable from the manuscript at all. JOINT_MULTIPLE is the
    # figure that survives the paper's own criterion. Removing the claim rather than leaving it
    # unused is the point: an available number gets used.

    Claim("ORDER_BITS", "Achievable bits via creation order, fully open",
          lambda: _attr_bits("open", "order")),
    Claim("TRIALS", "Zero-error trials per payload size",
          lambda: str(_capacity()["trials"])),
    Claim("MAX_ENTRIES", "Directory entry ceiling",
          lambda: f"{_capacity()['max_entries']:,}"),
    Claim("ORDER_NOMINAL_FORMULA", "log2(n!) at MAX_ENTRIES -- the reviewer's corrected formula",
          lambda: f"{math.log2(math.factorial(_capacity()['max_entries'])):.0f}"),

    Claim("P_EPISODES", "Fisher p counting episodes (pseudo-replicated)",
          lambda: f"{_p_episodes():.4f}"),
    Claim("P_GENERATIONS", "Fisher p counting generations (correct unit)",
          lambda: f"{_p_generations():.4f}"),
    Claim("DEMO_A", "Successes in arm A", lambda: str(DEMO_HITS_A)),
    Claim("DEMO_B", "Successes in arm B", lambda: str(DEMO_HITS_B)),
    Claim("DEMO_N", "Generations per arm", lambda: str(DEMO_GENERATIONS)),
    Claim("DEMO_N_EPISODES", "Episodes per arm", lambda: str(DEMO_GENERATIONS * 2)),

    Claim("CALIB_TABLE_TEX", "Baseline calibration sweep (generated)",
          _calib_table_tex, raw=True),
    Claim("CALIB_MODEL", "Model used for the calibration sweep", _calib_model),
    Claim("CALIB_N_BUDGETS", "Probe budgets swept", lambda: str(len(_calib()))),
    Claim("CALIB_N_EPISODES", "Baseline episodes run in the sweep",
          lambda: str(sum(n for _k, n in _calib().values()))),
    Claim("CALIB_TARGET", "Pre-registered target solo-success rate",
          lambda: f"{CALIB_TARGET:.2f}"),
    Claim("CALIB_CHOSEN", "Budget meeting the gate, or 'none'",
          lambda: str(_chosen()[0]) if _chosen() else "none"),
    Claim("CALIB_CHOSEN_RATE", "Solo success at the chosen budget",
          lambda: f"{_chosen()[1]:.2f}" if _chosen() else "--"),
    Claim("CALIB_CHOSEN_N", "Baseline episodes at the chosen budget",
          lambda: str(_chosen()[2]) if _chosen() else "--"),
    Claim("CALIB_CHOSEN_CI", "Wilson interval at the chosen budget",
          lambda: ("({:.2f}, {:.2f})".format(*_wilson(_chosen()[3], _chosen()[2]))
                   if _chosen() else "--")),

    Claim("S3_NAME_MAX", "Longest key segment a real object store accepted",
          lambda: f'{_s3()["name_max"]:,}'),
    Claim("S3_NAME_RATIO", "How much wider the object-store name carrier is than a mount's",
          lambda: f'{_s3()["name_max"] / 255:.1f}'),
    Claim("S3_MAX_BYTES", "Largest object body accepted, at the probe ceiling",
          lambda: f'{_s3()["max_object_bytes"]:,}'),
    Claim("S3_ENTRIES", "Entries written and listed under one prefix",
          lambda: f'{_s3()["entries_listed"]:,}'),
    Claim("S3_MTIME_SETTABLE", "Whether a sender can choose the timestamp a reader observes",
          lambda: ("the store assigns it and exposes no API to override it"
                   if not _s3()["mtime"]["settable_by_sender"]
                   else "a sender can set it")),
    Claim("S3_ORDER_CREATED", "Creation order in the ordering probe",
          lambda: ", ".join(_s3()["order_created"])),
    Claim("S3_ORDER_LISTED", "Order the store returned",
          lambda: ", ".join(_s3()["order_listed"])),
    Claim("S3_DIRNAME_SEPARABLE", "Whether dirname is a carrier distinct from filename",
          lambda: ("a directory is a prefix of the key rather than an object"
                   if not _s3()["dirname_separable_from_filename"]
                   else "directories are objects in their own right")),
    Claim("S3_REGION", "Region the object store was probed in", lambda: _s3()["region"]),

    Claim("USECOST_SEEDS", "Seeds in the cost arm",
          lambda: str(_usecost()["success_isolated"][0]["n_seeds"])),
    Claim("USECOST_EPISODES", "Episodes per cell in the cost arm",
          lambda: str(_usecost()["success_isolated"][0]["n_episodes"])),
    Claim("USECOST_BUDGET_LO", "Lowest probe budget priced", lambda: str(_usecost_budgets()[0])),
    Claim("USECOST_BUDGET_HI", "Highest probe budget priced", lambda: str(_usecost_budgets()[-1])),
    Claim("USECOST_DIRNAME_MAX", "Worst task-success cost of dirname closure, any budget",
          lambda: f"{_usecost_max('only_dirname'):.2f}"),
    Claim("USECOST_CONTENT_MAX", "Worst task-success cost of content closure, any budget",
          lambda: f"{_usecost_max('only_content'):.2f}"),
    Claim("USECOST_FILENAME_MAX", "Worst task-success cost of filename closure, any budget",
          lambda: f"{_usecost_max('only_filename'):.2f}"),
    Claim("USECOST_FREE_ATTRS", "Attributes whose closure costs nothing at any budget",
          _usecost_free_attrs, raw=True),
    Claim("USECOST_STEP_L2_L3", "Extra cost of adding dirname closure to filename closure",
          lambda: f"{max(abs(_usecost_row('cost_cumulative','L3_dirname')[k] - v) for k, v in _usecost_row('cost_cumulative','L2_filename').items()):.2f}"),
    Claim("USECOST_EXISTENCE_MAX", "Worst task-success cost of existence closure, any budget",
          lambda: f"{_usecost_max('only_existence'):.2f}"),
    Claim("USECOST_STEP_L3_L4", "Extra task cost of adding existence closure to dirname closure",
          lambda: f"{max(abs(_usecost_row('cost_cumulative','L4_existence')[k] - v) for k, v in _usecost_row('cost_cumulative','L3_dirname').items()):.2f}"),
    Claim("USECOST_TABLE_TEX", "Cumulative ladder priced in task success",
          _usecost_table_tex, raw=True),
    Claim("USECOST_BUDGET_COLS", "Column spec for the cost table",
          lambda: "l" + "r" * len(_usecost_budgets()), raw=True),
    Claim("USECOST_BUDGET_HDR", "Budget headings for the cost table",
          lambda: " & ".join(str(b) for b in _usecost_budgets()), raw=True),

    Claim("GRID_TABLE_TEX", "Solo success per model per budget", _grid_table_tex, raw=True),
    Claim("GRID_BUDGET_HDR", "Budget column headings", _grid_budget_hdr, raw=True),
    Claim("GRID_COLS", "Column spec for the calibration grid", _grid_cols, raw=True),
    Claim("GRID_WINDOWS", "Models with an operating point inside (0,1)", _grid_windows, raw=True),
    Claim("GRID_N_ROWS", "Rows in the calibration grid", lambda: str(_grid()["n_rows"])),
    Claim("GRID_N_BUDGETS", "Distinct probe budgets swept",
          lambda: str(len(_grid()["budgets"]))),
    # cmidrule spans the budget columns: they begin at column 3 (after model, route)
    # and run to 2 + one column per budget. Derived so the rule tracks the grid width
    # rather than a hand-counted endpoint that silently desyncs when a row is dropped.
    Claim("GRID_CMID_END", "Last column index the budget-header rule spans",
          lambda: str(2 + len(_grid()["budgets"]))),

    Claim("SCREEN_N_MODELS", "Models the behavioural arm was run against",
          lambda: str(_screen()["n_models"])),
    Claim("SCREEN_N_REPORTED", "Models whose results the paper reports",
          lambda: str(_screen()["n_reported"])),
    Claim("SCREEN_N_EXCLUDED", "Models screened out",
          lambda: str(_screen()["n_models"] - _screen()["n_reported"])),
    Claim("SCREEN_TABLE_TEX", "The model screen, one row per model", _screen_table_tex, raw=True),

    Claim("QWEN_MODEL", "The floored calibration model",
          lambda: _qwen()["model"].replace("_", r"\_")),
    Claim("QWEN_N", "Episodes in the floored calibration",
          lambda: str(_qwen()["n_episodes"])),
    Claim("QWEN_SOLVED", "Episodes solved by the floored model",
          lambda: str(_qwen()["n_solved"])),
    Claim("QWEN_BUDGET", "Probe budget at which the floored sweep produced episodes",
          lambda: ", ".join(str(b) for b in _qwen()["budgets_with_episodes"])),
    Claim("QWEN_MALFORMED", "Malformed probes emitted by the floored model",
          lambda: str(_qwen()["n_malformed_probes"])),
    Claim("QWEN_INVALID_TOOL", "Invalid tool calls emitted by the floored model",
          lambda: str(_qwen()["n_invalid_tool"])),
    Claim("QWEN_CI_HI", "Upper 95% Wilson bound on the floored solo rate",
          lambda: "{:.2f}".format(_wilson(_qwen()["n_solved"], _qwen()["n_episodes"])[1])),

    Claim("N_MATRIX_EPISODES", "Episodes in the completed matrix",
          lambda: str(len(_all_eps()))),
    Claim("N_MATRIX_ERRORS", "API-error episodes in the matrix",
          lambda: str(sum(1 for e in _all_eps() if e.get("api_error")))),
    Claim("DEPOSIT_K", "Episodes that wrote to the substrate",
          lambda: str(sum(1 for e in _all_eps() if _tools(e) & WRITE_TOOLS))),
    Claim("DEPOSIT_CI_HI_EP", "Upper Wilson bound, EPISODE unit (pseudo-replicated)",
          lambda: f"{_wilson(sum(1 for e in _all_eps() if _tools(e) & WRITE_TOOLS), len(_all_eps()))[1]:.3f}"),
    # The reported bound. Generation is the declared unit of independence (SS4.4), so a
    # generation counts as depositing if ANY of its agents did.
    Claim("DEPOSIT_GEN_K", "Generations in which any agent deposited",
          lambda: str(sum(1 for eps in _arms().values()
                          for g, v in _gen_dep(eps).items() if v))),
    Claim("DEPOSIT_GEN_N", "Generation cells across both arms",
          lambda: str(sum(len(_gen_dep(eps)) for eps in _arms().values()))),
    Claim("DEPOSIT_CI_HI", "Upper 95% Wilson bound at the GENERATION unit",
          lambda: f"{_wilson(sum(1 for eps in _arms().values() for g, v in _gen_dep(eps).items() if v), sum(len(_gen_dep(eps)) for eps in _arms().values()))[1]:.3f}"),
    Claim("READ_K", "Episodes that read the substrate",
          lambda: str(sum(1 for e in _all_eps() if _tools(e) & READ_TOOLS))),
    Claim("READ_MEDIAN", "Median substrate reads per episode",
          lambda: f"{statistics.median([sum(1 for t in e['turns'] for c in t['calls'] if c['name'] in READ_TOOLS) for e in _all_eps()]):.0f}"),

    Claim("OPEN_K", "open arm successes",
          lambda: str(sum(1 for e in _arms()["open"] if e.get("success")))),
    Claim("OPEN_N", "open arm episodes", lambda: str(len(_arms()["open"]))),
    Claim("WIPE_K", "wipe arm successes",
          lambda: str(sum(1 for e in _arms()["wipe"] if e.get("success")))),
    Claim("WIPE_N", "wipe arm episodes", lambda: str(len(_arms()["wipe"]))),
    Claim("OPEN_GEN_K", "open generations with at least one success",
          lambda: str(sum(1 for v in _gen_cells(_arms()["open"]).values() if any(v)))),
    Claim("WIPE_GEN_K", "wipe generations with at least one success",
          lambda: str(sum(1 for v in _gen_cells(_arms()["wipe"]).values() if any(v)))),
    Claim("N_GENERATIONS", "generations per arm",
          lambda: str(len(_gen_cells(_arms()["open"])))),
    Claim("DELTA_GEN_P", "Fisher exact p at the generation level",
          lambda: f"{measures.fisher_exact(sum(1 for v in _gen_cells(_arms()['open']).values() if any(v)), len(_gen_cells(_arms()['open'])), sum(1 for v in _gen_cells(_arms()['wipe']).values() if any(v)), len(_gen_cells(_arms()['wipe']))):.4f}"),
    Claim("MATRIX_AGENTS", "agents per generation in the matrix",
          lambda: str(max(len(v) for v in _gen_cells(_arms()["open"]).values()))),
    Claim("N_BLOCKED_DRAWN", "blocked tasks drawn in the matrix",
          lambda: str(sum(1 for e in _all_eps() if e.get("task_kind") == "blocked"))),

    # --- the second-model attempt, stopped by the pre-registered calibration gate ------------
    Claim("M2_NAME", "Second model attempted", lambda: r"\texttt{qwen3-32b}", raw=True),
    Claim("M2_EPISODES", "Calibration episodes run on the second model",
          lambda: str(_m2()["clean"])),
    Claim("M2_ERRORS", "API-error episodes on the second model", lambda: str(_m2()["errored"])),
    Claim("M2_BUDGETS", "Probe budgets swept on the second model",
          lambda: str(len(_m2()["budgets"]))),
    Claim("M2_BUDGET_LO", "Lowest probe budget swept", lambda: str(min(_m2()["budgets"]))),
    Claim("M2_BUDGET_HI", "Highest probe budget swept", lambda: str(max(_m2()["budgets"]))),
    Claim("M2_TOKENS", "Tokens spent on the second-model calibration",
          lambda: f"{_m2()['tokens']:,}"),
    Claim("M2_SOLVED", "Tasks the second model solved at any budget",
          lambda: str(_m2()["solved"])),

    # --- the third model: cleared the gate, ran a matrix, never touched the substrate -------
    Claim("M3_NAME", "Third model attempted", lambda: r"\texttt{qwen3-235b-a22b}", raw=True),
    Claim("M3_EPISODES", "Matrix episodes on the third model",
          lambda: str(_arm_stats("235b")["episodes"])),
    Claim("M3_READS", "Third-model episodes that read the substrate",
          lambda: str(_arm_stats("235b")["read_episodes"])),
    Claim("M3_WRITES", "Third-model episodes that wrote to the substrate",
          lambda: str(_arm_stats("235b")["write_episodes"])),
    Claim("M3_SOLVED", "Third-model episodes solved",
          lambda: str(_arm_stats("235b")["solved"])),
    Claim("M3_BUDGET", "Probe budget the third model calibrated to",
          lambda: str(_arm_stats("235b")["budgets"][0])),
    Claim("M3_CURVE", "Third model's calibration curve",
          lambda: "8:0.00, 12:0.33, 16:1.00, 20:0.67, 24:1.00, 28:1.00"),
    Claim("HK_BUDGET", "Probe budget the reported arm calibrated to",
          lambda: str(_arm_stats("haiku")["budgets"][0])),
    Claim("HK_READ_CALLS", "Substrate read calls in the reported arm",
          lambda: str(_arm_stats("haiku")["read_calls"])),
    Claim("HK_READ_EPISODES", "Reported-arm episodes that read the substrate",
          lambda: str(_arm_stats("haiku")["read_episodes"])),
    Claim("OVERLAP_BUDGET", "The only budget where both models are unpinned",
          lambda: "20"),

    # --- the matched-budget head-to-head, both arms at budget 20 ----------------------------
    Claim("HH_N", "Episodes per arm in the matched-budget comparison",
          lambda: str(_b20("haiku")["n"])),
    Claim("HH_TOTAL", "Episodes across both matched-budget arms",
          lambda: str(_b20("haiku")["n"] + _b20("235b")["n"])),
    Claim("HH_ERRORS", "API errors across both matched-budget arms",
          lambda: str(_b20("haiku")["errors"] + _b20("235b")["errors"])),
    Claim("HH_HK_READ", "Reported-arm episodes that read the store at budget 20",
          lambda: str(_b20("haiku")["read"])),
    Claim("HH_HK_PCT", "Reported-arm read rate at budget 20",
          lambda: f"{100 * _b20('haiku')['read'] / max(1, _b20('haiku')['n']):.1f}"),
    Claim("HH_HK_CALLS", "Reported-arm read calls at budget 20",
          lambda: str(_b20("haiku")["read_calls"])),
    Claim("HH_HK_SOLVED", "Reported-arm episodes solved at budget 20",
          lambda: str(_b20("haiku")["solved"])),
    Claim("HH_HK_WIPE_READ", "Reported-arm reads in the wiped condition",
          lambda: str(_b20("haiku")["by_cond"].get("wipe", {}).get("read", 0))),
    Claim("HH_HK_WIPE_N", "Reported-arm episodes in the wiped condition",
          lambda: str(_b20("haiku")["by_cond"].get("wipe", {}).get("n", 0))),
    Claim("HH_M3_READ", "Third-model episodes that read the store at budget 20",
          lambda: str(_b20("235b")["read"])),
    Claim("HH_M3_PCT", "Third-model read rate at budget 20",
          lambda: f"{100 * _b20('235b')['read'] / max(1, _b20('235b')['n']):.1f}"),
    Claim("HH_M3_CALLS", "Third-model read calls at budget 20",
          lambda: str(_b20("235b")["read_calls"])),
    Claim("HH_M3_SOLVED", "Third-model episodes solved at budget 20",
          lambda: str(_b20("235b")["solved"])),
    Claim("HH_M3_WIPE_READ", "Third-model reads in the wiped condition",
          lambda: str(_b20("235b")["by_cond"].get("wipe", {}).get("read", 0))),
    Claim("HH_M3_WIPE_N", "Third-model episodes in the wiped condition",
          lambda: str(_b20("235b")["by_cond"].get("wipe", {}).get("n", 0))),
    Claim("HH_WRITES", "Deposits across both matched-budget arms",
          lambda: str(_b20("haiku")["wrote"] + _b20("235b")["wrote"])),
    Claim("HH_ALL_CALLS", "Read calls across both matched-budget arms",
          lambda: str(_b20("haiku")["read_calls"] + _b20("235b")["read_calls"])),

    # --- per-agent namespacing: the control the ladder is measured against ------------------
    Claim("NS_CARRIERS", "Carriers checked for cross-namespace leakage",
          lambda: str(len(_namespace()["carriers"]))),
    Claim("NS_VISIBLE", "Sender artefacts observable from the receiver's namespace",
          lambda: str(sum(c["observable_by_receiver"] for c in _namespace()["carriers"]))),
    Claim("NS_PLANTED", "Sender artefacts planted across the confinement probe",
          lambda: str(sum(c["sender_artefacts"] for c in _namespace()["carriers"]))),
    Claim("NS_ESCAPES", "Namespace escape attempts made",
          lambda: str(sum(c["escapes_attempted"] for c in _namespace()["carriers"]))),
    Claim("NS_ESCAPES_OK", "Namespace escape attempts that resolved",
          lambda: str(sum(c["escapes_succeeded"] for c in _namespace()["carriers"]))),
    Claim("NS_SAME_TOTAL", "Same-namespace achievable total, the positive control",
          lambda: f"{sum(c['same_namespace_bits'] for c in _namespace()['carriers']):,.0f}"),
    Claim("NS_MEDIATION", "Mediation points a namespace control needs",
          lambda: str(_namespace()["mediation"]["mediation_points"])),
    Claim("NS_CLASS", "Enforcement class of the namespace control",
          lambda: str(_namespace()["mediation"]["enforcement_class"])),
    Claim("NS_REUSE_TABLE", "Cache-reuse cost rows", lambda: _reuse_table_tex(), raw=True),
    Claim("NS_WORST_MULT", "Largest measured fetch multiplier under namespacing",
          lambda: f"{max(r['multiplier'] for r in _namespace()['reuse']):.2f}"),
    Claim("NS_WORST_AGENTS", "Agent count at the largest multiplier",
          lambda: str(max(_namespace()["reuse"], key=lambda r: r["multiplier"])["agents"])),
    Claim("NS_WORST_SHARED", "Fetches under one shared cache at that workload",
          lambda: f"{max(_namespace()['reuse'], key=lambda r: r['multiplier'])['fetches_shared']:.0f}"),
    Claim("NS_WORST_NS", "Fetches under per-agent namespaces at that workload",
          lambda: f"{max(_namespace()['reuse'], key=lambda r: r['multiplier'])['fetches_namespaced']:.0f}"),
    Claim("NS_MIN_MULT", "Smallest measured fetch multiplier (two agents)",
          lambda: f"{_reuse_row(2, 100, 20)['multiplier']:.2f}"),
    Claim("NS_TRIALS", "Workload draws per reuse row",
          lambda: str(_namespace()["reuse"][0]["trials"])),

    Claim("JOINT_BITS", "Bits recovered by ONE joint encoder after content closure",
          lambda: str(_joint()["bits_recovered"])),
    Claim("JOINT_TRIALS", "Exact trials for the joint encoder",
          lambda: f"{_joint()['exact_trials']}/{_joint()['trials']}"),
    Claim("JOINT_CARRIERS", "Carriers the joint encoder uses",
          lambda: str(len(_joint()["carriers"]))),
    Claim("SUM_MINUS_JOINT", "Bits the summed total claims over the joint measurement",
          lambda: f"{_rung_total('content')[0] - _joint()['bits_recovered']:.0f}"),
    Claim("JOINT_MULTIPLE", "Joint residual as a multiple of the passcode",
          lambda: f"{_joint()['bits_recovered'] / _passcode_bits():.1f}"),

    # A path-inspecting monitor (deployed DLP inspects file paths, not only bodies) also catches
    # the two sender-chosen name carriers; the residual is re-measured over what survives, by the
    # same joint encoder, so it is directly comparable to JOINT_BITS.
    Claim("MONITOR_PATH_BITS", "Residual under a path-inspecting monitor",
          lambda: str(_monitor("content+path")["bits"])),
    Claim("MONITOR_PATH_MULTIPLE", "Path-monitor residual as a multiple of the passcode",
          lambda: f"{_monitor('content+path')['bits'] / _passcode_bits():.1f}"),
    Claim("MONITOR_PATH_CARRIERS", "Carriers a path-inspecting monitor leaves open",
          lambda: ", ".join(_monitor("content+path")["carriers_left"])),
    Claim("MONITOR_STRUCT_BITS", "Residual under a monitor that also models directory presence",
          lambda: str(_monitor("content+path+struct")["bits"])),
    # The dirname-rung residual an enumeration-based encoder recovers -- 0, because the substrate
    # refuses the directory structure the size/mtime carriers need. Evidence that the zero holds
    # across a second encoder family, not only the name-locating per-attribute coders.

    # Monitor-blindness experiment (analyze/monitor_roc.py): the content monitor's measured ROC.
    Claim("MON_ROC_N", "Episodes per class in the monitor ROC",
          lambda: str(_mon_roc()["n_per_class"])),
    Claim("MON_AUC_CONTENT", "Content monitor AUC, content-carried vs legit (positive control)",
          lambda: f"{_mon_roc()['auc_content_vs_legit']:.2f}"),
    Claim("MON_AUC_NAME", "Content monitor AUC, name-carried vs legit",
          lambda: f"{_mon_roc()['auc_name_vs_legit']:.2f}"),
    Claim("MON_AUC_NAME_CI", "95% interval on the name-vs-legit AUC",
          lambda: f"[{_mon_roc()['auc_name_vs_legit_ci'][0]:.2f}, "
                  f"{_mon_roc()['auc_name_vs_legit_ci'][1]:.2f}]"),
    Claim("MON_TPR_CONTENT", "Content monitor TPR at 5% FPR, content-carried",
          lambda: f"{_mon_roc()['tpr_at_5pct_fpr_content']:.2f}"),
    Claim("MON_TPR_NAME", "Content monitor TPR at 5% FPR, name-carried",
          lambda: f"{_mon_roc()['tpr_at_5pct_fpr_name']:.2f}"),
    Claim("MON_ALARM_NAME", "Content monitor alarm rate on the name channel",
          lambda: f"{_mon_roc()['alarm_rate_name']:.2f}"),
    Claim("MON_ALARM_LEGIT", "Content monitor alarm rate on legitimate use",
          lambda: f"{_mon_roc()['alarm_rate_legit']:.2f}"),

    # Ceiling-sweep experiment (analyze/ceiling_sweep.py): fraction moves, residual does not.
    Claim("CEIL_FRAC_MIN", "Smallest fraction-removed across the ceiling sweep",
          lambda: f"{_ceil_sweep()['fraction_min']:.2f}"),
    Claim("CEIL_FRAC_MAX", "Largest fraction-removed across the ceiling sweep",
          lambda: f"{_ceil_sweep()['fraction_max']:.2f}"),
    Claim("CEIL_RESIDUAL", "Joint residual, invariant across the ceiling sweep",
          lambda: str(_ceil_sweep()["residual_bits"])),
    Claim("CEIL_TABLE_TEX", "Rows of the ceiling-sweep table", _ceil_table_tex, raw=True),

    # Name-closure control deployed on a real object store (analyze/prod_s3_control.py).
    # Reported as a deployment demonstration, not a sampled efficacy rate: the recovered/closed
    # counts are construction-deterministic (a content hash cannot carry a chosen name), so only
    # the enforcement-point count enters the prose.
    Claim("PROD_S3_ENFORCE", "Write-path enforcement points the control needs",
          lambda: str(_prod_s3()["enforcement_points"])),

    # Four-monitor observability comparison (analyze/monitor_comparison.py).
    Claim("CONTENT_OPEN_BITS", "The content row measured open, bare number",
          lambda: _attr_bits("open", "content").replace(r"$\geq$", "")),
    Claim("COUNT_ROW_BITS", "The count row at the content rung, the one still censored",
          lambda: f"{_count_at_content():.0f}"),
    Claim("COUNT_DEP_BITS", "Gap term: the count row, excluded as dependent on existence",
          lambda: f"{_count_at_content():.0f} bits"),
    Claim("JOINT_LOSS_BITS", "Gap term: measured joint encoder loss at the content rung",
          lambda: f"{_joint_loss('content'):.0f} bits"),
    Claim("JOINT_LOSS_FILENAME", "Measured joint encoder loss at the filename rung",
          lambda: f"{_joint_loss('filename'):.0f}"),

    Claim("CAPACITY_TABLE_TEX", "Measured ladder (generated)", _capacity_table_tex, raw=True),

    Claim("PAYLOAD_TABLE_TEX", "External payload table (generated)",
          _payload_table_tex, raw=True),
    Claim("N_PAYLOADS_FIT", "Third-party secrets the joint residual can carry",
          lambda: str(len(_fits()))),
    Claim("N_PAYLOADS", "Third-party secrets compared against",
          lambda: str(len(_payloads()["payloads"]))),
    Claim("COST_TABLE_TEX", "Closure cost table (generated)", _cost_table_tex, raw=True),
    Claim("MED_CONTENT", "Mediation points to hold content closure",
          lambda: str(_cost_rung("content")["n_mediation_points"])),
    Claim("MED_DIRNAME", "Mediation points to hold dirname closure",
          lambda: str(_cost_rung("dirname")["n_mediation_points"])),
    Claim("MED_EXTRA", "Additional mediation points from content closure to dirname closure",
          lambda: str(_cost_rung("dirname")["n_mediation_points"]
                      - _cost_rung("content")["n_mediation_points"])),
    Claim("EXTRA_CLASSES", "Enforcement class of every row added past content closure",
          _extra_classes),
    Claim("PAYLOAD_ROWS_DIRNAME", "Payload-class rows required at dirname closure",
          lambda: str(_cost_rung("dirname")["n_payload_rows"])),
    Claim("MED_EXISTENCE", "Mediation points to hold existence closure -- the rung that reaches zero",
          lambda: str(_cost_rung("existence")["n_mediation_points"])),
    Claim("MED_EXTRA_EXISTENCE", "Additional mediation points from content closure to existence closure",
          lambda: str(_cost_rung("existence")["n_mediation_points"]
                      - _cost_rung("content")["n_mediation_points"])),
    Claim("PAYLOAD_ROWS_EXISTENCE", "Payload-class rows required at existence closure",
          lambda: str(_cost_rung("existence")["n_payload_rows"])),
    Claim("CONTENT_CLASS", "Enforcement class of the control the incident applied",
          lambda: _cost_row("content")["enforcement"]),
    Claim("DIRNAME_CLASS", "Enforcement class of directory-name closure",
          lambda: _cost_row("dirname")["enforcement"]),
    Claim("EXISTENCE_CLASS", "Enforcement class of the control that reaches zero",
          lambda: _cost_row("existence")["enforcement"]),

    # ---- Tier 1: a real shared volume ----
    Claim("REAL_NAME_MAX", "NAME_MAX measured on a real mount",
          lambda: f"{_real_limits()['name_max']:,}"),
    Claim("REAL_MAX_BYTES", "Largest body a real mount accepted",
          lambda: f"{_real_limits()['max_file_bytes']:,}"),
    Claim("REAL_MAX_ENTRIES", "Entries one real directory held",
          lambda: f"{_real_limits()['max_entries']:,}"),
    Claim("REAL_MTIME_NS", "Timestamp resolution surviving a round trip on a real mount",
          lambda: ("1 ns, exact" if _real_limits()["mtime"]["exact"]
                   else f"{_real_limits()['mtime']['resolution_ns']:,} ns")),
    Claim("REAL_ORDER", "Whether a real listing preserved creation order",
          lambda: "no" if not _real_limits()["order_preserved"] else "yes"),
    Claim("BYTES_RATIO", "How far the synthetic body limit sits below the real one",
          lambda: f"{_real_limits()['max_file_bytes'] // 8192:,}"),

    # ---- Tier 2: a real artifact store ----
    Claim("STORE_TABLE_TEX", "Real-store attribute verdicts (generated)",
          _store_table_tex, raw=True),
    Claim("STORE_RUNG", "Rung the real registry natively sits at",
          lambda: _real_store()["classification"]["native_rung"]),
    Claim("STORE_SLOTS", "Existence slots recovered exactly from the real catalog",
          lambda: _real_store()["attributes"]["existence"]["evidence"].split("/")[0]),
    Claim("STORE_NAME_BITS", "Bits a sender-chosen repository name carried",
          lambda: f"{_real_store()['attributes']['dirname']['bits_per_name']:.0f}"),

    # ---- the matched-pairs probes-to-solution analysis ----
    # Reported because it comes out SIGNIFICANT in the predicted direction on a comparison the
    # rest of the paper establishes has no treatment in it. See SS5.8.
    Claim("PAIR_N", "Matched cells where both arms solved",
          lambda: str(len(_pairs()))),
    Claim("PAIR_CELLS", "Cells drawing the same task in both arms",
          lambda: str(_matched_cells())),
    Claim("PAIR_OPEN_MED", "Median probes to solution, open arm",
          lambda: f"{statistics.median([a for a, _b in _pairs()]):.0f}"),
    Claim("PAIR_WIPE_MED", "Median probes to solution, wipe arm",
          lambda: f"{statistics.median([b for _a, b in _pairs()]):.0f}"),
    Claim("PAIR_MED_DIFF", "Median paired difference, wipe minus open",
          lambda: f"{statistics.median([b - a for a, b in _pairs()]):.0f}"),
    Claim("PAIR_POS", "Pairs where the open arm used fewer probes",
          lambda: str(measures.sign_test([b - a for a, b in _pairs()])[0])),
    Claim("PAIR_NEG", "Pairs where the wipe arm used fewer probes",
          lambda: str(measures.sign_test([b - a for a, b in _pairs()])[1])),
    Claim("PAIR_TIE", "Tied pairs", lambda: str(measures.sign_test(
        [b - a for a, b in _pairs()])[2])),
    Claim("PAIR_P", "Exact two-sided sign-test p on the paired differences",
          lambda: f"{measures.sign_test([b - a for a, b in _pairs()])[3]:.3f}"),

    # ---- the follow-up run at four agents per generation ----
    Claim("FU_ATTEMPTED", "Episodes the follow-up attempted",
          lambda: str(len(_blocked_all()))),
    Claim("FU_N", "Follow-up episodes that ran to completion",
          lambda: str(len(_blocked_eps()))),
    Claim("FU_CENSORED", "Follow-up episodes terminated by credit exhaustion",
          lambda: str(len(_blocked_all()) - len(_blocked_eps()))),
    Claim("FU_GENS", "Generations with at least one completed episode",
          lambda: str(len({e["generation"] for e in _blocked_eps()}))),
    Claim("FU_AGENTS", "Agents per generation in the follow-up",
          lambda: str(max(collections.Counter(
              e["generation"] for e in _blocked_eps()).values()))),
    Claim("FU_BLOCKED_N", "Blocked (unsolvable) tasks drawn in the follow-up",
          lambda: str(sum(1 for e in _blocked_eps() if e.get("task_kind") == "blocked"))),
    Claim("FU_BLOCKED_SOLVED", "Blocked tasks solved, which should be zero",
          lambda: str(sum(1 for e in _blocked_eps()
                          if e.get("task_kind") == "blocked" and e.get("success")))),
    Claim("FU_SEARCH_N", "Solvable tasks drawn in the follow-up",
          lambda: str(sum(1 for e in _blocked_eps() if e.get("task_kind") == "search"))),
    Claim("FU_SOLVED", "Follow-up episodes solved",
          lambda: str(sum(1 for e in _blocked_eps() if e.get("success")))),
    Claim("FU_READ_K", "Follow-up episodes that read the substrate",
          lambda: str(sum(1 for e in _blocked_eps() if _tools(e) & READ_TOOLS))),
    Claim("FU_WRITE_K", "Follow-up episodes that wrote to the substrate",
          lambda: str(sum(1 for e in _blocked_eps() if _tools(e) & WRITE_TOOLS))),
    Claim("FU_DEPOSIT_K", "Follow-up episodes that deposited for a successor",
          lambda: str(_fu_deposits())),
    Claim("FU_GEN_WRITE_K", "Generations containing any write",
          lambda: str(sum(1 for v in _gen_dep(_blocked_eps()).values() if v))),
    Claim("FU_DEPOSIT_CI_HI", "Upper 95% Wilson bound on deposits, generation unit",
          lambda: f"{_wilson(_fu_deposits(), len(_gen_dep(_blocked_eps())))[1]:.2f}"),
    Claim("FU_BLOCKED_CI_HI", "Upper 95% Wilson bound on deposits among blocked tasks",
          lambda: f"{_wilson(0, sum(1 for e in _blocked_eps() if e.get('task_kind') == 'blocked'))[1]:.2f}"),
    Claim("FU_READ_MEDIAN", "Median substrate reads per follow-up episode",
          lambda: f"{statistics.median([sum(1 for t in e['turns'] for c in t['calls'] if c['name'] in READ_TOOLS) for e in _blocked_eps()]):.0f}"),

    # Artifact metadata. `raw` because PENDING is itself LaTeX and must not be escaped.
    Claim("ART_URL", "Artifact repository URL", lambda: _art("url"), raw=True),
    Claim("ART_DOI", "Archived artifact DOI", lambda: _art("archive_doi"), raw=True),
    Claim("ART_COMMIT", "Commit the reported numbers were produced at",
          lambda: _art("commit"), raw=True),
    Claim("ART_LICENSE_CODE", "Code license", lambda: _art("license_code")),
    Claim("ART_LICENSE_DATA", "Data license", lambda: _art("license_data")),
    Claim("ART_PYTHON", "Interpreter the reported run used", lambda: _art("python")),
    Claim("ART_PYTHON_MIN", "Lowest interpreter version the code targets",
          lambda: _art("python_minimum")),
    Claim("ART_DEPS", "Third-party dependencies of the measurement arm", _art_deps, raw=True),
    Claim("ART_MODEL", "Model the behavioural arm used", lambda: _art("model_id")),
    Claim("ART_ROUTE", "How that model was served", lambda: _art("model_route")),
    Claim("ART_MODEL_DATED", "Month of the behavioural run", lambda: _art("model_dated")),
    Claim("ART_SEEDS", "Seeds used in the behavioural arm", _art_seeds),
    Claim("ART_SEED_CAPACITY", "Seeding rule for the capacity trials",
          lambda: _art("seed_rule_capacity")),
    Claim("ART_SEED_JOINT", "Seeding rule for the joint-encoder trials",
          lambda: _art("seed_rule_joint")),
]


def compute() -> dict[str, str]:
    out: dict[str, str] = {}
    for c in CLAIMS:
        try:
            out[c.key] = c.fn()
        except Exception as e:                                    # noqa: BLE001
            print(f"  !! {c.key}: FAILED to compute -- {e}")
            out[c.key] = f"<<UNCOMPUTABLE:{c.key}>>"
    return out


def abstract_words(text: str) -> int | None:
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.S)
    if not m:
        return None
    body = re.sub(r"\\[a-zA-Z]+\{?|\}|\\noindent", " ", m.group(1))
    return len(re.sub(r"\s+", " ", body).split())


def render(values: dict[str, str], tmpl_name: str = "main.tex.tmpl",
           out_name: str = "main.tex") -> int:
    tmpl_path = PAPER / tmpl_name
    if not tmpl_path.exists():
        print(f"\nno template at {tmpl_path}")
        return 1
    tmpl = tmpl_path.read_text(encoding="utf-8")
    raw_keys = {c.key for c in CLAIMS if c.raw}

    used = set(re.findall(r"\{\{([A-Z_0-9]+)\}\}", tmpl))
    unknown = sorted(used - set(values))
    if unknown:
        print(f"\nFAIL: unknown placeholder(s): {', '.join(unknown)}")
        return 1

    def sub(m: re.Match) -> str:
        key = m.group(1)
        return values[key] if key in raw_keys else tex_escape(values[key])

    out = re.sub(r"\{\{([A-Z_0-9]+)\}\}", sub, tmpl)
    if "<<UNCOMPUTABLE" in out:
        print("\nFAIL: an uncomputable claim reached the manuscript")
        return 1

    n = abstract_words(out)
    if n is None:
        print("\nFAIL: no abstract -- a required submission item")
        return 1

    (PAPER / out_name).write_text(out, encoding="utf-8")
    limit = abstract_word_limit(tmpl_name)
    status = "ok" if n <= limit else "OVER LIMIT"
    print(f"\n  {out_name}  {len(out):,} chars  {len(used)} claims  "
          f"abstract {n}/{limit} [{status}]")

    # A table or figure with a label nothing points at is decoration, and LaTeX does not warn
    # about it: an unreferenced label builds clean. Two tables shipped that way in this paper
    # before a reviewer asked where they were, so the check is mechanical now.
    defined = set(re.findall(r"\\label\{((?:tab|fig):[^}]+)\}", out))
    referenced = set(re.findall(r"\\ref\{((?:tab|fig):[^}]+)\}", out))
    dangling = sorted(defined - referenced)
    if dangling:
        print(f"\n  FAIL: {len(dangling)} float(s) defined but never referenced:")
        for d in dangling:
            print(f"    {d}")
        print(r"    Add a Table~\ref{...} or Figure~\ref{...} callout, or delete the float.")
        return 1

    # A per-attribute sum is an upper bound that double-counts dependent attributes and inherits
    # any censoring in its cells; the residual is the jointly measured, zero-error figure with
    # `count` excluded. The two were used interchangeably across two generations of this pipeline,
    # each time producing a headline that could not be reconciled with its own ladder. Prose is
    # where that substitution happens, so it is checked mechanically: a sentence may name a sum
    # value alongside "residual" only when it also says "sum", which is what a reconciliation
    # sentence does and what a mislabelling does not.
    sum_values = {re.sub(r"[^0-9]", "", str(values[k]))
                  for k in ("OPEN_BITS", "CONTENT_BITS") if k in values}
    sum_values = {v for v in sum_values if v}
    # The guard is about PROSE mislabelling. A table legitimately places an open-rung sum in one
    # column and the residual in another (that juxtaposition is the point of the ceiling sweep),
    # and a tabular block has no sentence punctuation, so the whole table reads as one "sentence"
    # to the splitter below. Strip tabular environments before checking.
    prose = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", " ", out, flags=re.DOTALL)
    offenders = []
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        low = sentence.lower()
        if "residual" not in low or "sum" in low:
            continue
        for v in sum_values:
            if re.search(rf"(?<![0-9]){re.escape(v)}(?![0-9])", sentence.replace(",", "")):
                offenders.append((v, " ".join(sentence.split())[:120]))
                break
    if offenders:
        print(f"\n  FAIL: {len(offenders)} sentence(s) call a per-attribute sum a residual:")
        for v, snippet in offenders:
            print(f"    [{v}] {snippet}")
        print("    Say 'sum' explicitly, or use the jointly measured value (JOINT_BITS).")
        return 1

    orphan = sorted(set(values) - used)
    if orphan:
        print(f"\n  {len(orphan)} computed claim(s) unused in {tmpl_name}: "
              f"{', '.join(orphan)}")
    return 0 if n <= abstract_word_limit(tmpl_name) else 1


def main(argv: list[str]) -> int:
    print("Recomputing every claim from results/\n")
    values = compute()
    width = max(len(c.key) for c in CLAIMS)
    for c in CLAIMS:
        v = values[c.key]
        shown = v if len(v) <= 40 else v[:37] + "..."
        print(f"  {c.key:<{width}}  {shown:<42}  {c.describe}")

    bad = [k for k, v in values.items() if v.startswith("<<UNCOMPUTABLE")]
    if bad:
        print(f"\nFAIL: {len(bad)} claim(s) uncomputable: {', '.join(bad)}")
        return 1

    pending = sorted(k for k, v in values.items() if v == PENDING)
    if pending:
        print(f"\n  ARTIFACT NOT DEPOSITED: {len(pending)} field(s) unset in paper/artifact.json")
        print(f"    {', '.join(pending)}")
        print("    These render as a visible [PENDING] marker in the PDF. Fill them in before")
        print("    submission -- the paper should not imply a repository that does not exist.")
    if "--list" in argv:
        return 0

    # The 8-page submission build renders the same claims through a shorter template, so it
    # inherits every guard in render() rather than being a hand-edited copy that can drift.
    tmpl = out = None
    for arg in argv:
        if arg.startswith("--tmpl="):
            tmpl = arg.split("=", 1)[1]
        elif arg.startswith("--out="):
            out = arg.split("=", 1)[1]
    if (tmpl is None) != (out is None):
        print("\nFAIL: --tmpl and --out must be given together")
        return 1
    if tmpl is not None:
        return render(values, tmpl, out)
    return render(values)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
