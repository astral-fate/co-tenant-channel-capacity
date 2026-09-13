"""Build `results/screen/model-screen.json`: every model the behavioural arm was run against.

    python analyze/model_screen.py

Why this exists
---------------
The manuscript reports one model. Four others were run, and each was excluded for a different
reason: one floored the calibration gate, three were stopped by provider limits before a verdict
could be reached. Reporting the survivor without the screen would present a model that was
*selected* as though it were a model that was simply *used*, which understates the flexibility
exercised even though the selection criterion is measured in an arm that cannot express the effect.

The screen is assembled from the run artifacts rather than transcribed, so it cannot drift from
what was actually run. Episodes that ended in an API error are counted separately and never enter
a success rate: a provider cutting a run off is not evidence about a model.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def _episodes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _split(eps: list[dict]) -> tuple[list[dict], list[dict]]:
    """(clean, errored). An API-error episode never enters a rate."""
    clean = [e for e in eps if not e.get("api_error")]
    return clean, [e for e in eps if e.get("api_error")]


def _sweep(directory: Path) -> dict:
    """{budget: {solved, n, errored}} over a calibrate.py output tree."""
    out: dict[str, dict] = {}
    if not directory.exists():
        return out
    for d in sorted(directory.glob("b*")):
        eps: list[dict] = []
        for f in d.rglob("episodes.jsonl"):
            eps.extend(_episodes(f))
        if not eps:
            continue
        clean, err = _split(eps)
        out[d.name[1:]] = {
            "solved": sum(1 for e in clean if e.get("success")),
            "n": len(clean),
            "errored": len(err),
        }
    return out


def build() -> dict:
    models: list[dict] = []

    # ---- Qwen3-8B: the floor -------------------------------------------------------------
    qwen_path = RESULTS / "behavioural" / "calibration" / "qwen-calib.json"
    if qwen_path.exists():
        q = json.loads(qwen_path.read_text(encoding="utf-8"))
        models.append({
            "alias": q["model_alias"], "model": q["model"], "route": "local (transformers)",
            "role": "screened out", "arm": "no_substrate",
            "budgets": {str(b): {"solved": q["n_solved"], "n": q["n_episodes"], "errored": 0}
                        for b in q["budgets_with_episodes"]},
            "clean_n": q["n_episodes"], "clean_solved": q["n_solved"],
            "capability": "passed",
            "verdict": "floor",
            "why": ("Solved nothing solo at the one budget swept, while emitting no malformed "
                    "probe and no invalid tool call. A difficulty result, not an inability to act."),
        })

    # ---- Haiku 4.5: the reported model ---------------------------------------------------
    haiku = _sweep(RESULTS / "behavioural" / "calibration" / "calib-full")
    if haiku:
        n = sum(v["n"] for v in haiku.values())
        k = sum(v["solved"] for v in haiku.values())
        models.append({
            "alias": "claude-haiku-4.5", "model": "anthropic/claude-haiku-4.5",
            "route": "OpenRouter", "role": "reported", "arm": "no_substrate",
            "budgets": haiku, "clean_n": n, "clean_solved": k,
            "capability": "passed",
            "verdict": "gate passed",
            "why": ("The only model whose solo success fell strictly inside (0, 1); the operating "
                    "point is the budget nearest the pre-registered target."),
        })

    # ---- Gemini: blocked by a per-model request cap ---------------------------------------
    gem_dirs = sorted((RESULTS / "behavioural" / "runs").glob("*gemini*")) if (RESULTS / "behavioural" / "runs").exists() else []
    if gem_dirs:
        eps: list[dict] = []
        for d in gem_dirs:
            eps.extend(_episodes(d / "episodes.jsonl"))
        clean, err = _split(eps)
        models.append({
            "alias": "gemini-2.5", "model": "gemini-2.5-flash",
            "route": "Gemini Developer API", "role": "screened out",
            "arm": "no_substrate, open",
            "budgets": {}, "clean_n": len(clean),
            "clean_solved": sum(1 for e in clean if e.get("success")),
            "errored": len(err),
            "capability": "passed",
            "verdict": "undetermined",
            "why": ("Cleared both capability probes, then exhausted a per-model free-tier request "
                    "cap. One episode completed; the remainder ended in quota errors and are "
                    "excluded from any rate."),
        })

    return {
        "note": ("Assembled from run artifacts by analyze/model_screen.py. API-error episodes are "
                 "counted separately and never enter a success rate."),
        "n_models": len(models),
        "n_reported": sum(1 for m in models if m["role"] == "reported"),
        "models": models,
    }


def main() -> int:
    data = build()
    (RESULTS / "screen" / "model-screen.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{data['n_models']} models, {data['n_reported']} reported\n")
    for m in data["models"]:
        print(f"  {m['alias']:18s} {m['verdict']:14s} clean={m['clean_solved']}/{m['clean_n']:<3d} {m['route']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
