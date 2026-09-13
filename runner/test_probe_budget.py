"""Regression tests for the probe budget.

The budget used to be enforced as a turn limit, and that silently failed to control difficulty:
a model issuing parallel `validate` calls got as many probes per turn as it asked for. Measured on
this harness, GLM-5.2 spent 21-23 oracle calls inside a 14-turn budget against a 9-probe optimum
and succeeded in 5 of 5 episodes, while Qwen2.5-7B issued one call per turn, got 12, and succeeded
in 0 of 16. The same declared parameter was two different experiments -- one at the ceiling, one at
the floor -- and the inheritance advantage is unmeasurable at either.

These tests pin the fix. The first is the one that matters: a batching model must not be able to
buy extra probes by packing them into fewer turns.

    python runner/test_probe_budget.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

import tasks  # noqa: E402
from agent import Workspace, run_episode  # noqa: E402
from providers import Provider, Step, ToolCall  # noqa: E402

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ok  {msg}")
    else:
        print(f"  FAIL {msg}")
        _FAILURES.append(msg)


class BatchingProvider(Provider):
    """Issues `per_turn` oracle calls every turn -- the behaviour that defeated the turn limit.

    Candidates are drawn from a fixed wrong-answer generator so the episode cannot succeed by
    luck; these tests are about how many probes the harness *allows*, not about solving the task.
    """

    family = "test"
    model = "batching"

    def __init__(self, per_turn: int = 5, alphabet: str = "ABCDEFGHJK") -> None:
        self.per_turn = per_turn
        self.alphabet = alphabet
        self.n = 0

    def step(self, system, messages, tools) -> Step:
        calls = []
        for _ in range(self.per_turn):
            a = self.alphabet[self.n % len(self.alphabet)]
            b = self.alphabet[(self.n // len(self.alphabet)) % len(self.alphabet)]
            self.n += 1
            calls.append(ToolCall(id=f"t{self.n}", name="validate",
                                  arguments={"candidate": f"{a}{b}{a}{b}"}))
        return Step(text="", tool_calls=calls, usage={"in": 0, "out": 0})

    def append_assistant(self, messages, step):
        messages.append({"role": "assistant", "content": step.text or ""})

    def append_tool_results(self, messages, results):
        for c, out, _ok in results:
            messages.append({"role": "tool", "tool_call_id": c.id, "name": c.name,
                             "content": out})


def _episode(provider, *, max_turns: int, max_probes: int, tmp: Path):
    task = next(t for t in tasks.build_pool() if t.kind == "search")
    return run_episode(
        provider=provider, task=task, workspace=Workspace(tmp), substrate=None,
        condition="no_substrate", generation=1, agent_name="g1a0",
        model_alias="test", seed=0, max_turns=max_turns, max_probes=max_probes,
    )


def main() -> int:
    # Kept out of results/ so a test run can never leave anything that looks like run data.
    tmpdir = tempfile.TemporaryDirectory(prefix="probe-budget-")
    tmp = Path(tmpdir.name)

    print("probe budget")

    # The load-bearing test. 20 turns x 5 calls = 100 probes available if the budget were a turn
    # limit; the budget says 7.
    ep = _episode(BatchingProvider(per_turn=5), max_turns=20, max_probes=7, tmp=tmp)
    check(ep.n_validate == 7,
          f"a batching model cannot exceed its probe budget (spent {ep.n_validate}, allowed 7)")
    check(ep.n_probes_refused > 0,
          f"refusals are recorded so the budget is auditable ({ep.n_probes_refused} refused)")

    # Same budget, one call per turn: the budget must bind identically. This is the equivalence
    # the turn limit did not provide.
    ep_serial = _episode(BatchingProvider(per_turn=1), max_turns=20, max_probes=7, tmp=tmp)
    check(ep_serial.n_validate == 7,
          f"a serial model gets the same budget (spent {ep_serial.n_validate}, allowed 7)")

    # A budget above what the model spends must not bind, or `n_probes_refused` would be
    # meaningless as evidence that difficulty was actually applied.
    ep_loose = _episode(BatchingProvider(per_turn=1), max_turns=4, max_probes=50, tmp=tmp)
    check(ep_loose.n_probes_refused == 0,
          "a budget the model never reaches records no refusals")
    check(ep_loose.n_validate <= 4,
          f"turns still cap total work when probes are plentiful (spent {ep_loose.n_validate})")

    # 0 means unlimited, which is the default and must stay backward-compatible.
    ep_unl = _episode(BatchingProvider(per_turn=5), max_turns=3, max_probes=0, tmp=tmp)
    check(ep_unl.n_validate == 15 and ep_unl.n_probes_refused == 0,
          f"max_probes=0 is unlimited (spent {ep_unl.n_validate}, refused "
          f"{ep_unl.n_probes_refused})")

    # Exhaustion must end the episode promptly. A refused probe still costs a full model turn,
    # so a 30-turn ceiling with a budget of 8 was ~22 turns per episode that could not change the
    # outcome. The grace turns are what keep `submit` reachable.
    ep_grace = _episode(BatchingProvider(per_turn=1), max_turns=40, max_probes=5, tmp=tmp)
    from agent import POST_EXHAUSTION_GRACE
    check(ep_grace.ended_on_budget,
          "an exhausted episode ends on budget rather than running out the turn ceiling")
    check(len(ep_grace.turns) <= 5 + POST_EXHAUSTION_GRACE + 1,
          f"it ends within the grace window (turns={len(ep_grace.turns)}, "
          f"budget 5 + grace {POST_EXHAUSTION_GRACE})")
    check(len(ep_grace.turns) > 5,
          f"but the agent still gets turns after exhaustion to submit "
          f"(turns={len(ep_grace.turns)} > 5)")

    # Repeats and malformed candidates must not consume budget: the 9-probe reference optimum
    # counts DISTINCT guesses, so charging a repeat would make the budget a different quantity
    # from the one difficulty is calibrated against.
    class RepeatProvider(BatchingProvider):
        """Sends the same candidate every time, then one malformed one."""

        def step(self, system, messages, tools):
            self.n += 1
            cand = "JJJJ" if self.n <= 6 else "ZZ"
            return Step(text="", tool_calls=[ToolCall(id=f"r{self.n}", name="validate",
                                                      arguments={"candidate": cand})],
                        usage={"in": 0, "out": 0})

    ep_rep = _episode(RepeatProvider(), max_turns=10, max_probes=4, tmp=tmp)
    check(ep_rep.n_validate == 1,
          f"a repeated candidate is charged exactly once (n_validate={ep_rep.n_validate})")
    check(ep_rep.n_repeat_probes >= 4,
          f"repeats are counted, not silently forgiven (n_repeat_probes={ep_rep.n_repeat_probes})")
    check(ep_rep.n_malformed_probes >= 1,
          f"malformed candidates are counted and not charged "
          f"(n_malformed_probes={ep_rep.n_malformed_probes})")
    check(ep_rep.n_probes_refused == 0,
          "a budget of 4 is never exhausted by repeats alone")

    # The parameters must reach the record, or a result tree cannot be checked for mixed families.
    check(ep.max_probes == 7 and ep.code_len == tasks.CODE_LEN,
          f"episode records its own difficulty parameters (max_probes={ep.max_probes}, "
          f"code_len={ep.code_len})")

    # ---- provider caching --------------------------------------------------------------------
    # Real providers are cached per alias so a 16 GB model is not reloaded once per episode.
    # Mock providers must NOT be cached: they carry the episode's secret and seed, and sharing one
    # would make every episode replay the first one's scripted behaviour -- producing a full,
    # plausible result tree in which every arm is identical. That failure is silent, which is why
    # it is pinned here rather than left to the comment on the cache.
    import run as runner

    m1 = runner._make_provider("mock", mock_policy="solo", secret="AAAA", seed=1,
                               task_id="art-001")
    m2 = runner._make_provider("mock", mock_policy="solo", secret="BBBB", seed=2,
                               task_id="art-002")
    check(m1 is not m2, "mock providers are built fresh per episode, never shared")
    check(getattr(m1, "secret", None) != getattr(m2, "secret", None),
          "each mock provider carries its own episode secret")
    check("mock" not in runner._PROVIDER_CACHE,
          "the mock alias never enters the provider cache")

    tmpdir.cleanup()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} probe-budget test(s) failed")
        return 1
    print("All probe-budget tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
