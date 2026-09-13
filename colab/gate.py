"""Capability gates for a local model, run as a subprocess.

    python colab/gate.py --model qwen8-hf [--samples 3]

Exits 0 only if the model can do the two things an episode requires: emit a tool call, and perform
the eliminate-letters inference the search task is built on.

Run as a SEPARATE PROCESS on purpose. An 8B in 4-bit is ~5.5 GiB, and if the notebook kernel held
one copy while `run.py` loaded another, a 16 GiB card would be carrying 11 GiB of duplicated
weights plus two KV caches. One process, one copy, released on exit.

Why the deduction is sampled more than once: a 4B model passed this exact probe on its first
attempt, was declared usable on that basis, and then failed the same probe twice. One pass is not
evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "src"))

from providers import ToolSpec, build  # noqa: E402

VALIDATE = ToolSpec(
    name="validate",
    description="Test a candidate code.",
    schema={"type": "object", "properties": {"candidate": {"type": "string"}},
            "required": ["candidate"]},
)

# A 3-character code with all ten letters accounted for, so the answer is uniquely determined.
# An earlier 4-character version of this probe gave 0-hit data for A, B, H, J and K but said
# nothing about E or F, leaving the fourth character genuinely ambiguous -- and a correct answer
# that resolved the ambiguity differently was nearly recorded as a model regression.
DEDUCTION = (
    "A 3-character code uses letters from A B C D E F G H J K. You have learned: "
    "CCC gives 1 of 3 positions correct; DDD gives 1 of 3; GGG gives 1 of 3; and "
    "AAA, BBB, EEE, FFF, HHH, JJJ and KKK each give 0 of 3. "
    "Which letters does the code contain? Answer with just the letters."
)
#: The symbol set the task uses; kept beside the probe it scores.
ALPHABET = "ABCDEFGHJK"

EXPECTED = ["C", "D", "G"]


def user_msg(provider, text: str):
    """One user turn in the shape the provider's SDK expects.

    Gemini's SDK validates `contents` against its own union type and rejects the OpenAI
    `{"role", "content"}` dict, so the google family needs a real `types.Content`. `agent.py`
    already branches this way; the gate must too, or a Google model fails the gate on a message
    format error and is wrongly recorded as incapable.
    """
    if provider.family == "google":
        from google.genai import types
        return [types.Content(role="user", parts=[types.Part(text=text)])]
    if provider.family == "bedrock":
        # Converse takes content as a list of typed blocks. A bare string is rejected, so a
        # Bedrock model would fail the gate on the message shape and be recorded as incapable
        # -- the same way a Google model did before this branch existed.
        return [{"role": "user", "content": [{"text": text}]}]
    return [{"role": "user", "content": text}]


def answer_letters(text: str | None) -> list[str]:
    """Letters the model gives as its ANSWER, not every letter it mentions while reasoning.

    The original extraction scanned the whole response for characters in the alphabet. That works
    only for a model whose visible text is the answer alone -- Qwen3 emits its reasoning inside
    `<think>` tags, which the provider strips into `step.reasoning`, leaving a bare "C D G".

    Any model that reasons in plain text fails it. Claude's response restates the evidence
    ("AAA, BBB, EEE, FFF, HHH, JJJ, KKK give 0 of 3"), so all ten letters appear and the check
    returns the whole alphabet. That is a false negative about the scorer, not a finding about the
    model, and it would have rejected essentially every API model as incapable.

    The answer is taken from the last non-empty line instead. Single-character tokens are
    preferred, so prose like "C, D, and G" yields C/D/G and not the A and D inside "and"; if the
    line has none -- an answer written "CDG" -- every alphabet character on that line is used.
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return []
    last = lines[-1].upper()
    tokens = [t for t in re.split(r"[^A-Z]+", last) if t]
    singles = [t for t in tokens if len(t) == 1 and t in ALPHABET]
    if singles:
        return sorted(set(singles))
    return sorted({c for c in last if c in ALPHABET})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen8-hf", help="registry alias")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--min-passes", type=int, default=2)
    a = ap.parse_args()

    # min_passes > samples cannot be satisfied by any model, so the gate would report a
    # capability failure that is really a configuration error -- exactly the confusion this file
    # exists to prevent. Clamp, and say so, rather than failing a model for arithmetic.
    if a.min_passes > a.samples:
        print(f"NOTE: --min-passes {a.min_passes} exceeds --samples {a.samples}; clamping to "
              f"{a.samples}. With one sample this checks the plumbing, not the model: a 4B "
              f"passed this probe once and then failed it twice.", flush=True)
        a.min_passes = a.samples

    # A raw ModuleNotFoundError here is a confusing way to learn you are on the wrong machine.
    import providers as _p  # noqa: PLC0415
    cls = _p.REGISTRY.get(a.model, (None, None))[0]
    if cls is _p.TransformersProvider and not _p._torch_available():
        print(f"cannot run {a.model!r}: torch with CUDA is not importable here.", flush=True)
        print("This alias loads the model in-process and needs torch -- it is meant for Colab "
              "or any host with working GPU torch.", flush=True)
        print("On a host without it, use an Ollama alias (qwen8-q3, qwen8-local) or a hosted "
              "one (qwen-space, or-glm, claude-haiku).", flush=True)
        return 3

    print(f"loading {a.model} ...", flush=True)
    t0 = time.time()
    provider = build(a.model)
    print(f"loaded in {time.time() - t0:.0f}s  (family={provider.family}, "
          f"model={provider.model})", flush=True)

    # ---- gate 1: tool calling ------------------------------------------------------------
    t0 = time.time()
    step = provider.step(
        "You are an agent. Use the tools provided.",
        user_msg(provider, "Call validate with the candidate ABCD."),
        [VALIDATE],
    )
    secs = time.time() - t0
    names = [c.name for c in step.tool_calls]
    print(f"\ngate 1 tool calling: {secs:.1f}s  calls={names}  "
          f"args={[c.arguments for c in step.tool_calls]}", flush=True)
    if not step.tool_calls:
        print(f"GATE 1 FAILED: no tool call. text={step.text[:200]!r}", flush=True)
        return 1
    print("GATE 1 PASSED", flush=True)

    # ---- gate 2: the inference the task is built on --------------------------------------
    passes = 0
    total_s = 0.0
    total_t = 0
    truncated = 0
    for i in range(a.samples):
        t0 = time.time()
        step = provider.step(
            "You are a careful reasoner. Answer concisely.",
            user_msg(provider, DEDUCTION),
            [],
        )
        secs = time.time() - t0
        total_s += secs
        total_t += step.usage.get("out", 0)
        letters = answer_letters(step.text)
        ok = letters == EXPECTED
        passes += ok
        # Reasoning present but no answer means the think budget cut the thought short.
        if not (step.text or "").strip() and step.reasoning:
            truncated += 1
        tps = step.usage.get("out", 0) / max(secs, 1e-9)
        print(f"  sample {i + 1}/{a.samples}: {secs:5.1f}s {step.usage.get('out', 0):5d} tok "
              f"= {tps:5.1f} tok/s  reasoning={len(step.reasoning)} chars", flush=True)
        print(f"    answer={(step.text or '')[:110]!r}", flush=True)
        print(f"    letters={letters} -> {'PASS' if ok else 'FAIL'}", flush=True)

    mean_tps = total_t / max(total_s, 1e-9)
    print(f"\ngate 2 deduction: {passes}/{a.samples} passed", flush=True)
    print(f"throughput: {mean_tps:.1f} tok/s, {total_t / a.samples:.0f} tok/deduction", flush=True)
    if truncated:
        print(f"NOTE: {truncated}/{a.samples} hit the think budget. Raise ARS_THINK_BUDGET; a "
              f"truncated thought costs a recovery generation and yields a probe chosen without "
              f"completed reasoning.", flush=True)
    # 12 turns at the mean cost is an upper bound -- early turns are much cheaper.
    print(f"projected episode cost: ~{12 * (total_t / a.samples) / max(mean_tps, 1e-9) / 60:.0f} "
          f"min (upper bound)", flush=True)

    if passes < a.min_passes:
        print(f"\nGATE 2 FAILED: {passes}/{a.samples} < {a.min_passes}. This model cannot "
              f"reliably perform the task's core inference. Report that rather than spending "
              f"hours measuring a floor -- a zero here would be caused by the model, not by the "
              f"substrate.", flush=True)
        return 2

    print("\nGATE 2 PASSED -- safe to calibrate", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
