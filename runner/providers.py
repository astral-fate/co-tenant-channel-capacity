"""
Model adapters.

One narrow interface over Anthropic / OpenAI / Google so the episode loop is provider-agnostic
and the paper can make a cross-family generalisation claim. Each adapter takes a system prompt,
a message history and a tool schema in a single canonical form, and returns either tool calls or
a final text answer.

Keys are read from the environment (ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY) or from
a local `.env` file that is never committed. No key is ever written to a transcript or a log.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


# --------------------------------------------------------------------------- key handling

def load_env(path: str | Path = ".env") -> None:
    """Load KEY=VALUE lines from a local .env into os.environ, without overwriting real env vars."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if not v:
            continue
        os.environ.setdefault(k, v)
        # Accept the aliases people actually write in a .env, and route each key by its own
        # prefix rather than its label -- labels are unreliable (a key named NVIDIA may hold an
        # `hf_` Hugging Face token).
        if v.startswith("AIza"):
            os.environ.setdefault("GOOGLE_API_KEY", v)
        elif v.startswith("gsk_"):
            os.environ.setdefault("GROQ_API_KEY", v)
        elif v.startswith("nvapi-"):
            os.environ.setdefault("NVIDIA_API_KEY", v)
        elif v.startswith("hf_"):
            os.environ.setdefault("HF_TOKEN", v)
        elif v.startswith("sk-or-"):
            os.environ.setdefault("OPENROUTER_API_KEY", v)
        elif v.startswith("sk-ant-"):
            os.environ.setdefault("ANTHROPIC_API_KEY", v)
        elif v.startswith("sk-"):
            os.environ.setdefault("OPENAI_API_KEY", v)


# --------------------------------------------------------------------------- canonical types

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Step:
    """One model turn: either tool calls, or a final answer, or both empty (a stall)."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    #: The model's reasoning trace, where the provider exposes one separately (Qwen3 "thinking").
    #:
    #: RECORDED but never REPLAYED. These are different decisions and both are deliberate: feeding
    #: a model its own reasoning back as dialogue degrades the following turn, so
    #: `append_assistant` drops it -- but discarding it from the RECORD would lose the only
    #: evidence for a pre-registered measure. "Plan versus encoding" asks whether a deposit made
    #: after a closure was planned or merely re-encoded, and that question is answerable only from
    #: what the agent was reasoning at the time. Transcript inspection is also what diagnosed every
    #: model failure in this project; summary statistics diagnosed none of them.
    reasoning: str = ""


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]


Role = Literal["user", "assistant", "tool"]


class Provider:
    """Common interface. `family` is what the paper groups by."""

    family: str = "unknown"
    model: str = "unknown"

    def step(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Step:
        raise NotImplementedError

    # Each provider stores history in its own shape; the loop appends through these hooks so it
    # never has to know the shape.
    def append_assistant(self, messages: list[dict[str, Any]], step: Step) -> None:
        raise NotImplementedError

    def append_tool_results(self, messages: list[dict[str, Any]],
                            results: list[tuple[ToolCall, str, bool]]) -> None:
        raise NotImplementedError


def _retry_after_seconds(exc: Exception) -> float | None:
    """Extract a server-specified wait from a 429, if it gave one.

    Free tiers commonly ask for tens of seconds. Guessing shorter than the server asked for just
    burns the next attempt and truncates the episode, which is how a rate limit silently turns
    into a missing data point rather than a delayed one.
    """
    import re

    m = re.search(r"retry[- _]?after[\"']?\s*[:=]\s*[\"']?([0-9.]+)", str(exc), re.I)
    if m:
        return float(m.group(1))
    # Compound forms are the common case on Groq -- "try again in 4m54.192s" -- and a regex that
    # stops at the first unit reads that as 240s, under-waiting by nearly a minute and earning a
    # second 429 immediately. Sum every unit present instead.
    m = re.search(r"try again in ([0-9hms.\s]+)", str(exc), re.I)
    if m:
        span = m.group(1)
        total = 0.0
        found = False
        for value, unit in re.findall(r"([0-9.]+)\s*([hms])", span, re.I):
            total += float(value) * {"h": 3600.0, "m": 60.0, "s": 1.0}[unit.lower()]
            found = True
        if found:
            return total
    return None


#: Minimum seconds between successive API calls, per process. Free tiers meter requests per
#: minute, and an 18-turn episode issues 18 requests back to back -- which trips the limit even
#: when the daily quota is untouched. Pacing turns a run that dies at turn 1 into one that simply
#: takes longer. Overridable with ARS_PACE_SECONDS.
_PACE = float(os.environ.get("ARS_PACE_SECONDS", "4.0"))
_last_call: list[float] = [0.0]


def _pace() -> None:
    gap = time.time() - _last_call[0]
    if gap < _PACE:
        time.sleep(_PACE - gap)
    _last_call[0] = time.time()


#: Substrings that mean "nothing is listening", as distinct from "the connection wobbled".
#:
#: The difference matters because the two want opposite policies. A dropped or timed-out
#: connection may well succeed on the next attempt, so it earns the full backoff ladder. A
#: *refused* connection means the server is not running, and no amount of waiting inside one
#: episode will change that -- the right move is to fail fast so the episode is recorded as a
#: retryable `api_error` and the next pass picks it up once the server is back.
#:
#: This was measured, not theorised: with a local Ollama server stopped, "connection" matched the
#: generic transient list and every call burned eight attempts with a 2**i ladder -- about 127
#: seconds per call, turning a should-be-instant failure into a half-hour hang.
_UNREACHABLE = (
    "unreachable", "refused", "10061", "connectionrefused", "connection refused",
    "failed to establish a new connection", "no connection could be made",
)

#: Fragments of a tool-call tag that survive the provider's own parsing and land in `content`.
#: Qwen emits `<tool_call>...</tool_call>`; OpenRouter strips the call itself into `tool_calls`
#: but leaves the tail of the opening tag behind, so the text field reads "ool_call>". Harmless to
#: the run and actively misleading in a transcript, since it looks like the model said it.
_TAG_DEBRIS = ("<tool_call>", "</tool_call>", "ool_call>", "<tool_response>", "</tool_response>")


def _clean_text(text: str) -> str:
    for frag in _TAG_DEBRIS:
        text = text.replace(frag, "")
    return text.strip()


def _extract_reasoning(message: Any) -> str:
    """Pull the model's thinking out of whichever field this provider put it in.

    Reasoning models expose their chain of thought separately from `content`, and every provider
    names it differently: OpenRouter uses `reasoning` plus a structured `reasoning_details`,
    Hugging Face's router uses `reasoning_content`, and others omit it. Reading none of them --
    which this adapter did until now -- silently discarded every chain of thought in the study.

    That is not a cosmetic loss. `Step.reasoning` exists because the pre-registered "plan versus
    encoding" measure asks whether a deposit made after a closure was planned or merely re-encoded,
    and that is answerable only from what the agent was reasoning at the time. Transcript
    inspection also diagnosed every model failure in this project; summary statistics diagnosed
    none of them.
    """
    for attr in ("reasoning", "reasoning_content"):
        val = getattr(message, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    # Structured form: a list of {type, text} parts.
    details = getattr(message, "reasoning_details", None)
    if isinstance(details, list):
        parts = [d.get("text", "") for d in details
                 if isinstance(d, dict) and isinstance(d.get("text"), str)]
        joined = "\n".join(p for p in parts if p.strip())
        if joined.strip():
            return joined
    # Some SDK versions expose unknown fields only through the raw dump.
    dump = getattr(message, "model_extra", None) or {}
    for attr in ("reasoning", "reasoning_content"):
        val = dump.get(attr)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _retry(fn, *, attempts: int = 8, base: float = 2.0, cap: float = 120.0):
    """Backoff over transient API failures. Deterministic errors are re-raised immediately.

    Rate limits are treated as first-class rather than as generic transients: the server's own
    Retry-After is honoured when present, and the ceiling is high enough that a free-tier limit
    delays an episode instead of destroying it. This matters because a truncated episode is not a
    neutral loss -- it silently biases the success rate downward and would have corrupted the
    calibration curve.
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            _pace()
            return fn()
        except Exception as exc:  # noqa: BLE001 - provider SDKs raise heterogeneous types
            msg = str(exc).lower()
            rate_limited = "429" in msg or "rate limit" in msg or "rate_limit" in msg
            unreachable = any(t in msg for t in _UNREACHABLE)

            # Some 429s are deterministic refusals wearing a throttle's status code. Groq rejects
            # a request whose *requested* output exceeds the per-minute ceiling -- "Request too
            # large ... Limit 1000, Requested 2048" -- before running it. The parameters are
            # unchanged on retry, so every attempt fails identically; waiting the full ladder
            # spends minutes per episode to arrive at the same error. Re-raise at once so the
            # episode is recorded and the cause is visible, instead of being buried in backoff.
            if any(t in msg for t in ("request too large", "reduce max_tokens",
                                      "expected output tokens exceed")):
                raise

            # A spent DAILY budget is likewise not something to wait out here. Two reasons to
            # re-raise at once rather than climb the ladder:
            #
            #   * A provider with spare credentials can only rotate to them once the exception
            #     escapes this function -- rotation wraps `step`, and `step` calls `_retry`. Backing
            #     off first means a caller with three healthy keys sits idle for ten minutes before
            #     touching any of them. That inversion was live in this project and is what this
            #     branch fixes.
            #   * A provider WITHOUT spare credentials gains nothing either: the Retry-After on a
            #     daily limit is minutes to hours, the ladder cannot outlast it, and the episode is
            #     better recorded as a retryable `api_error` for a later pass than held open.
            #
            # Per-MINUTE limits are excluded deliberately -- those do clear inside an episode, and
            # `_retry` is exactly the right place to absorb them.
            if any(t in msg for t in ("tokens per day", "(tpd)", "requests per day", "(rpd)",
                                      "quota exceeded", "insufficient_quota", "daily limit",
                                      "out of credits", "payment required")):
                raise
            transient = rate_limited or unreachable or any(
                t in msg for t in ("overload", "timeout", "connection", "529", "503", "500", "502"))

            # A server that is not listening gets a few quick tries -- enough to ride out a
            # restart or a model swap -- and then gives up, rather than spending the full ladder
            # waiting for something that is not coming back on its own.
            budget = min(attempts, 3) if unreachable else attempts
            ceiling = 5.0 if unreachable else cap

            if not transient or i >= budget - 1:
                raise
            last = exc
            wait = _retry_after_seconds(exc) if rate_limited else None
            if wait is None:
                wait = min(ceiling, base ** i)
            time.sleep(min(ceiling, wait + 0.5))
    if last:
        raise last


# --------------------------------------------------------------------------- Anthropic

class AnthropicProvider(Provider):
    family = "anthropic"

    def __init__(self, model: str = "claude-sonnet-5", max_tokens: int = 2048):
        import anthropic  # imported lazily so a missing SDK only breaks its own family

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model
        self.max_tokens = max_tokens

    def step(self, system, messages, tools):
        payload = [{"name": t.name, "description": t.description, "input_schema": t.schema}
                   for t in tools]
        resp = _retry(lambda: self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            messages=messages, tools=payload,
        ))
        text, calls = "", []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return Step(text=text, tool_calls=calls, stop_reason=resp.stop_reason or "",
                    usage={"in": resp.usage.input_tokens, "out": resp.usage.output_tokens})

    def append_assistant(self, messages, step):
        content: list[dict[str, Any]] = []
        if step.text:
            content.append({"type": "text", "text": step.text})
        for c in step.tool_calls:
            content.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
        if content:
            messages.append({"role": "assistant", "content": content})

    def append_tool_results(self, messages, results):
        blocks = [{"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": not ok}
                  for c, out, ok in results]
        messages.append({"role": "user", "content": blocks})


# --------------------------------------------------------------------------- OpenAI

class OpenAIProvider(Provider):
    family = "openai"

    #: Spelling of the output-budget parameter for this endpoint. See `step()`.
    token_param = "max_completion_tokens"

    def __init__(self, model: str = "gpt-5.1", max_tokens: int = 2048):
        from openai import OpenAI

        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=key)
        self.model = model
        self.max_tokens = max_tokens

    def step(self, system, messages, tools):
        payload = [{"type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.schema}}
                   for t in tools]
        # OpenAI renamed this parameter; most OpenAI-compatible endpoints did not follow, and the
        # Hugging Face router rejects the new spelling outright with a bare 400. The name is
        # therefore a property of the endpoint, not of this class.
        resp = _retry(lambda: self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}] + messages,
            tools=payload, **{self.token_param: self.max_tokens},
        ))
        choice = resp.choices[0]
        calls = []
        for tc in (choice.message.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__malformed__": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        u = resp.usage
        return Step(text=_clean_text(choice.message.content or ""), tool_calls=calls,
                    reasoning=_extract_reasoning(choice.message),
                    stop_reason=choice.finish_reason or "",
                    usage={"in": getattr(u, "prompt_tokens", 0), "out": getattr(u, "completion_tokens", 0)})

    def append_assistant(self, messages, step):
        msg: dict[str, Any] = {"role": "assistant", "content": step.text or None}
        if step.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in step.tool_calls
            ]
        messages.append(msg)

    def append_tool_results(self, messages, results):
        for c, out, _ok in results:
            messages.append({"role": "tool", "tool_call_id": c.id, "content": out})


class GroqProvider(OpenAIProvider):
    """Groq serves open-weight models over an OpenAI-compatible API.

    Two reasons this matters here beyond availability. It supplies model families that are not
    Anthropic or Google -- gpt-oss and Qwen -- so the cross-family generalisation claim rests on
    genuinely different training lineages. And it runs *open-weight* models, which is the class
    Hugging Face's responders fell back to when hosted frontier models refused their forensic
    work. Measuring channel genesis on the models a defender can actually self-host is closer to
    the incident than measuring it only on hosted frontier models.
    """

    family = "groq"

    #: Substrings meaning "this key's budget is spent", as distinct from "slow down". A per-minute
    #: rate limit is transient and `_retry` absorbs it; these do not clear by waiting inside an
    #: episode, and the only useful response is a different key. Keep this list narrow: treating a
    #: transient 429 as exhaustion would burn every spare key in the first minute of a run.
    QUOTA_MARKERS = (
        "tokens per day", "tpd", "requests per day", "rpd",
        "quota exceeded", "insufficient_quota", "daily limit",
        "billing", "payment required", "out of credits",
    )

    #: Groq's free tier enforces an OUTPUT-tokens-per-minute ceiling *per request*: ask for more
    #: than this and the call is rejected before it runs, with a 429 that no amount of waiting and
    #: no other key will clear. Measured 13 Sep 2026 on `qwen/qwen3.8-27b`: "Request too large ...
    #: on output tokens per minute (OTPM): Limit 1000, Requested 2048". The default here is
    #: therefore below that ceiling rather than at the generic 2048, because the failure it causes
    #: is deterministic and looks exactly like throttling. Observed completions in this project run
    #: 27-265 tokens, so the cap costs nothing. Raise it only with a paid tier.
    FREE_TIER_OTPM = 1000

    def __init__(self, model: str = "openai/gpt-oss-20b",
                 max_tokens: int = FREE_TIER_OTPM):
        keys = self._collect_keys()
        if not keys:
            raise RuntimeError("no Groq key set (GROQ_API_KEYS, GROQ_API_KEY, GROQ_API_KEY_2, ...)")
        self._keys = keys
        self._key_index = 0
        #: Wall-clock time at which each key becomes eligible again. Groq's daily limit is a
        #: ROLLING window -- "Used 199082/200000, try again in 4m54s" means this key recovers in
        #: minutes, not that it is finished for the day. The first version of this rotation treated
        #: a quota error as permanent and advanced one way, so a seven-key chain was consumed in
        #: under a minute and the run then had nothing left while every key was about to recover.
        #: Parking with an expiry turns the chain into a pool.
        self._available_at = [0.0] * len(keys)
        self.model = model
        self.max_tokens = max_tokens
        self._connect()

    @staticmethod
    def _collect_keys() -> list[str]:
        """Keys in priority order, de-duplicated.

        `GROQ_API_KEYS` (comma-separated) wins if set; otherwise the numbered forms are read in
        order. Numbered variables rather than repeated `GROQ_API_KEY=` lines because `load_env`
        routes by key PREFIX and uses `setdefault`, so a second `gsk_` line would be silently
        dropped -- a failure that looks like the fallback simply never firing.
        """
        joined = os.environ.get("GROQ_API_KEYS", "")
        raw = [k.strip() for k in joined.split(",")] if joined else []
        if not raw:
            raw = [os.environ.get("GROQ_API_KEY", "")]
            i = 2
            while os.environ.get(f"GROQ_API_KEY_{i}"):
                raw.append(os.environ[f"GROQ_API_KEY_{i}"])
                i += 1
        seen, out = set(), []
        for k in raw:
            if k and k not in seen:
                seen.add(k)
                out.append(k)
        return out

    def _connect(self) -> None:
        from openai import OpenAI
        self.client = OpenAI(api_key=self._keys[self._key_index],
                             base_url="https://api.groq.com/openai/v1")

    #: Longest we will wait for a parked key to recover rather than failing the episode. Beyond
    #: this the limit is behaving like a real daily exhaustion and the episode is better recorded
    #: as a retryable `api_error` for a later pass.
    MAX_PARK_WAIT = 420.0

    def _park(self, exc: Exception) -> None:
        """Mark the current key unavailable until the server says it has recovered."""
        wait = _retry_after_seconds(exc)
        if wait is None:
            wait = 300.0                        # no hint given; assume a five-minute window
        self._available_at[self._key_index] = time.time() + wait
        print(f"[groq] key {self._key_index + 1}/{len(self._keys)} "
              f"(...{self._keys[self._key_index][-4:]}) parked for {wait:.0f}s", flush=True)

    def _advance_key(self) -> bool:
        """Rotate to a key that is available now, waiting briefly if none is.

        Round-robin over a pool rather than a one-way walk down a list: a key parked after a
        rolling-window limit comes back into service once its retry-after has elapsed. Identified
        in logs by position and last four characters only; a key never reaches a log or a
        transcript in this project.
        """
        n = len(self._keys)
        now_t = time.time()
        for step in range(1, n + 1):             # try every other key, in order, from here
            cand = (self._key_index + step) % n
            if self._available_at[cand] <= now_t:
                self._key_index = cand
                self._connect()
                print(f"[groq] rotating to key {cand + 1}/{n} "
                      f"(...{self._keys[cand][-4:]})", flush=True)
                return True

        # Everything is parked. Wait for the soonest, if that is sooner than giving up.
        soonest = min(self._available_at)
        delay = soonest - now_t
        if delay <= self.MAX_PARK_WAIT:
            cand = self._available_at.index(soonest)
            print(f"[groq] all {n} keys parked; waiting {delay:.0f}s for key {cand + 1}",
                  flush=True)
            time.sleep(max(0.0, delay) + 1.0)
            self._key_index = cand
            self._connect()
            return True
        print(f"[groq] all {n} keys parked, soonest in {delay:.0f}s -- giving up on this episode",
              flush=True)
        return False

    def _is_quota(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(m in msg for m in self.QUOTA_MARKERS)

    def step(self, system, messages, tools):
        """Delegate to the OpenAI-compatible step, rotating keys on exhaustion.

        Rotation sits here rather than inside `_retry` because the two handle different failures.
        `_retry` waits out a transient fault on one key; this swaps the key when waiting cannot
        help. A run therefore continues across a spent daily budget without restarting, and the
        rotation is announced so the record shows which key produced which episodes.
        """
        while True:
            try:
                return super().step(system, messages, tools)
            except Exception as exc:  # noqa: BLE001 - provider SDKs raise heterogeneous types
                if self._is_quota(exc):
                    self._park(exc)              # this key, until the server says otherwise
                    if self._advance_key():
                        continue
                raise


class NvidiaProvider(OpenAIProvider):
    """NVIDIA NIM, also an OpenAI-compatible endpoint.

    Adds Llama and further Qwen checkpoints, both open-weight, widening the lineage coverage.
    Keys are `nvapi-...`; a token beginning `hf_` is a Hugging Face token, not a NIM key.
    """

    family = "nvidia"

    def __init__(self, model: str = "meta/llama-3.3-70b-instruct", max_tokens: int = 2048):
        from openai import OpenAI

        key = os.environ.get("NVIDIA_API_KEY")
        if not key:
            raise RuntimeError("NVIDIA_API_KEY is not set (NIM keys begin 'nvapi-')")
        self.client = OpenAI(api_key=key, base_url="https://integrate.api.nvidia.com/v1")
        self.model = model
        self.max_tokens = max_tokens


class GatewayProvider(OpenAIProvider):
    """A self-hosted FreeLLMAPI gateway: one OpenAI-compatible endpoint fronting several free
    providers, with automatic failover when one rate-limits. Reads FREELLM_BASE and FREELLM_KEY.

    Why this exists: a single free provider returns HTTP 429 on the first call and its reasoning
    models run at 70-130 s/turn, either of which makes a behavioural arm infeasible. Behind the
    gateway, kimi-k3 answered in ~5 s over the HuggingFace-router path and the router moves off a
    rate-limited provider automatically. The determinism caveat is unchanged -- these are sampled
    models -- so the pre-registration's non-deterministic-arm handling still applies.
    """

    family = "gateway"

    def __init__(self, model: str = "auto", max_tokens: int = 8192):
        from openai import OpenAI
        base = os.environ.get("FREELLM_BASE", "http://localhost:3001/v1")
        key = os.environ.get("FREELLM_KEY")
        if not key:
            raise RuntimeError("FREELLM_KEY is not set (the gateway's freellmapi-... unified key)")
        self.client = OpenAI(api_key=key, base_url=base)
        self.model = model
        self.max_tokens = max_tokens


class HFRouterProvider(OpenAIProvider):
    """Hugging Face's inference router, OpenAI-compatible, serving open-weight checkpoints.

    Registered as its own family rather than reached through `GatewayProvider` because the paper
    groups results by `family`, and a Qwen checkpoint served over the HF router is a Qwen result,
    not a "gateway" result. Labelling it by the transport would silently weaken the cross-family
    claim it exists to support.

    It also carries the same argument as the Groq adapter, and carries it further: these are the
    weights a defender can host. Hugging Face's own responders fell back to a self-hosted
    open-weight model when hosted frontier models refused their forensic work, so measuring
    channel genesis here is measuring it on the class of model that was actually available during
    the incident.

    KNOWN LIMITATION, measured 13 Sep 2026 and the reason this route is not used for the
    behavioural arm: `Qwen/Qwen3-32B` over this router does **not** emit native tool calls. Given a
    tool schema it returns prose containing a ```tool_code fence -- the call written out as text --
    and `tool_calls` comes back empty. The same checkpoint over OpenRouter emits proper tool calls
    and passes the gate. So the deficiency is in the serving path, not the weights, and an
    agentic episode cannot be driven through here. Fine for single-turn generation; check
    `tool_calls` before trusting it for anything else.
    """

    family = "huggingface"
    token_param = "max_tokens"

    def __init__(self, model: str = "Qwen/Qwen3-32B", max_tokens: int = 4096):
        from openai import OpenAI

        key = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        if not key:
            raise RuntimeError("HF_TOKEN is not set (a Hugging Face token, 'hf_...')")
        self.client = OpenAI(api_key=key, base_url="https://router.huggingface.co/v1")
        self.model = model
        self.max_tokens = max_tokens


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter: one OpenAI-compatible endpoint fronting ~425 models across every major lab.

    This is what makes the cross-family claim real rather than aspirational. It reaches Anthropic
    and OpenAI proprietary models, so the paper can finally test the *family that produced the
    incident* -- the one gap the study otherwise could not close, and which was previously listed
    as a stated limitation.
    """

    family = "openrouter"

    def __init__(self, model: str = "openai/gpt-4o-mini", max_tokens: int = 2048,
                 # The SDK default is 600 s with two retries, so one wedged request can stall an
                 # episode loop for half an hour with nothing on stdout. A reasoning model needs
                 # real headroom per turn -- 16k characters of thinking is normal for Qwen3-32B --
                 # but not thirty minutes of it. Set explicitly so a hang fails fast enough to be
                 # seen and resumed rather than silently eating a run.
                 timeout: float = 180.0, max_retries: int = 2):
        from openai import OpenAI

        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self.client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1",
                             timeout=timeout, max_retries=max_retries)
        self.model = model
        self.max_tokens = max_tokens


class HFSpaceProvider(Provider):
    """Talks to our own ZeroGPU Gradio Space.

    Why this exists: every hosted free tier we tried metered us out mid-experiment -- OpenRouter
    by daily cap, Groq by tokens-per-minute, Gemini per-minute, HF's router by monthly credits.
    Each one turned episodes into HTTP 429s, and a truncated episode is not a neutral loss: counted
    as a failure it biases success downward, which already produced one false null in this project.
    Running the model on the user's own ZeroGPU allocation removes the metering entirely.

    The Space exposes one function taking {system, messages, tools} and returning
    {text, tool_calls, usage}. Message history is kept in OpenAI shape because Qwen's chat
    template understands `role: "tool"`, so the episode loop needs no special-casing.
    """

    family = "hfspace"

    def __init__(self, model: str = "Qwen/Qwen3-8B",
                 space: str = "FatimahEmadEldin/covert-channel-agent-runner",
                 # This is the ANSWER budget only. The Space applies its own thinking budget
                 # before it, forces the thought closed if that budget runs out, and strips the
                 # <think> block before parsing -- so reasoning tokens never re-enter the
                 # dialogue and are not counted here. A tool call plus a short note fits well
                 # inside 256; the earlier 1536 was the whole per-turn budget and the model spent
                 # essentially all of it thinking.
                 max_tokens: int = 256):
        from gradio_client import Client

        tok = os.environ.get("HF_TOKEN")
        if not tok:
            raise RuntimeError("HF_TOKEN is not set")
        self.client = Client(space, token=tok, verbose=False)
        self.model = model
        self.space = space
        self.max_tokens = max_tokens

    def step(self, system, messages, tools):
        payload = json.dumps({
            "system": system,
            "messages": messages,
            "tools": [{"name": t.name, "description": t.description, "parameters": t.schema}
                      for t in tools],
            "max_tokens": self.max_tokens,
        })
        raw = _retry(lambda: self.client.predict(payload, api_name="/generate"))
        d = json.loads(raw)
        if d.get("error"):
            # Surfaced as an exception so the episode loop's existing error handling applies,
            # rather than silently becoming an empty turn.
            raise RuntimeError(f"space error: {d['error']}")
        calls = [ToolCall(id=f"c{i}", name=c["name"], arguments=c.get("arguments") or {})
                 for i, c in enumerate(d.get("tool_calls") or [])]
        u = d.get("usage") or {}
        return Step(text=d.get("text") or "", tool_calls=calls,
                    # The Space currently reports only `reasoning_chars`; it is read here so that
                    # a Space returning the trace itself needs no client change.
                    reasoning=str(d.get("reasoning") or ""),
                    usage={"in": int(u.get("in", 0)), "out": int(u.get("out", 0))})

    def append_assistant(self, messages, step):
        msg: dict[str, Any] = {"role": "assistant", "content": step.text or ""}
        if step.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in step.tool_calls
            ]
        messages.append(msg)

    def append_tool_results(self, messages, results):
        for c, out, _ok in results:
            messages.append({"role": "tool", "tool_call_id": c.id,
                             "name": c.name, "content": out})


# --------------------------------------------------------------------------- Ollama (local GPU)

class OllamaProvider(Provider):
    """Local quantized inference through Ollama's native chat API.

    Why local, and why Ollama specifically. The ZeroGPU Space worked but metered: a daily
    GPU-second allowance against a matrix measured in GPU-hours, plus queueing behind other
    tenants. A local GPU has neither. This machine runs Python 3.14, well ahead of prebuilt
    `torch` and `llama-cpp-python` wheels, so an in-process runtime is not an option -- Ollama is
    a standalone binary and does not care which Python is installed.

    Thinking is bounded here for the same reason it is bounded on the Space: unbounded, Qwen3 spent
    an entire generation budget reasoning and emitted no answer, which reaches the episode loop as
    an empty turn indistinguishable from a broken adapter. `num_predict` caps the generation. If
    that cap lands mid-thought -- reasoning present, but no content and no tool call -- the turn is
    retried once with thinking off, which is the local equivalent of forcing the thought closed. A
    truncated thought that yields an action is worth more than a turn that yields nothing.

    Uses stdlib `urllib` rather than an SDK: it is one JSON POST, and there is nothing to break on
    a Python version this new.
    """

    family = "ollama"

    def __init__(self, model: str = "qwen3:4b",
                 host: str | None = None,
                 think: bool = True,
                 num_predict: int = 3072,
                 num_ctx: int | None = None,
                 max_tokens: int | None = None):
        self.model = model
        self.host = (host or os.environ.get("OLLAMA_HOST")
                     or "http://localhost:11434").rstrip("/")
        self.think = think
        # Generation is bounded, but generously, and the bound exists to stop a runaway rather
        # than to ration tokens. The history is worth recording because both extremes were tried.
        #
        # A SMALL cap is actively harmful. At 1024 and even 2048 tokens this model's reasoning was
        # cut off mid-thought, and a truncated thought does not fail cleanly -- the reasoning leaks
        # into `content` with no tool call attached, which the episode loop reads as a stall.
        # Episodes spent three of twelve probes and gave up for that reason alone.
        #
        # NO cap is worse. With `num_predict=-1`, llama-server applies *context shifting*: once
        # generation passes the context window it discards the oldest tokens and continues, so
        # there is no wall to stop it. Measured: a single turn generated **15,551 tokens**, nearly
        # twice the 8192 context, and was still going. Worse than slow -- context shifting evicts
        # the EARLIEST tokens first, which is the task statement, so the model literally loses the
        # question. That is the origin of the meta-commentary seen in transcripts ("the query
        # appears to involve a logic puzzle, likely similar to Mastermind") on turns where it had
        # forgotten what it was asked. Throughput also decayed from 25 to 13.5 tok/s as the cache
        # filled.
        #
        # So the rule is: prompt + generation must fit inside num_ctx, so context shifting never
        # engages at all. 3072 is a little above the ~2600 tokens the hardest one-shot deduction
        # actually needs, and leaves ample headroom for the prompt inside the 8192 window.
        #
        # 6144 was tried first and was too generous: the model ruminated to 6121 of 6144 tokens on
        # a single turn -- it expands to fill whatever ceiling it is given, so the ceiling should
        # sit near the measured requirement rather than far above it. The requirement is real,
        # though: with thinking disabled entirely this model answers the same deduction in 20
        # tokens and gets it wrong 3 times out of 3, parroting the whole alphabet back. So the
        # tokens are not waste, they are the cost of a correct answer -- there is simply no need
        # for twice as many.
        # ARS_NUM_PREDICT lets a caller (the Colab notebook, say) set this without editing
        # source. A hardcoded value here silently overrode the notebook's own setting.
        self.num_predict = int(max_tokens or os.environ.get("ARS_NUM_PREDICT")
                               or num_predict)
        # Context has to hold the prompt PLUS the whole generation, and on a 6 GiB card its KV
        # cache competes directly with model layers for residency. The arithmetic decides it:
        # 8192 cells cost 1152 MiB of KV, which on top of a 4.1 GiB model exceeds the 5.0 GiB
        # available and pushes layers onto the CPU -- and CPU-resident layers cost far more than
        # a shorter context does. 4096 cells cost 576 MiB, keeps the model fully resident, and
        # 4096 proved too small in practice and the failure was not graceful. This model's
        # thinking grows as an episode progresses -- measured up to ~7000 tokens on a single turn,
        # against the ~800 a one-shot deduction costs -- and once a thought exceeds the remaining
        # context the generation is truncated before the tool call, which the episode loop sees as
        # a stall. 8192 cells with a q8_0 cache cost ~612 MiB, roughly 300 MiB more than 4096, and
        # buy room for the long turns. Raise with ARS_NUM_CTX if VRAM allows; watch the offload
        # split when doing so, because KV competes with layers for residency.
        self.num_ctx = int(num_ctx or os.environ.get("ARS_NUM_CTX") or 8192)

    def _post(self, path: str, payload: dict, timeout: float = 900.0) -> dict:
        import urllib.error  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415

        req = urllib.request.Request(
            f"{self.host}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"ollama HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"ollama unreachable at {self.host}: {exc.reason}. Is `ollama serve` running?"
            ) from exc

    def _tools(self, tools) -> list[dict]:
        return [{"type": "function",
                 "function": {"name": t.name, "description": t.description,
                              "parameters": t.schema}}
                for t in tools]

    def _chat(self, system, messages, tools, *, think: bool) -> dict:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = {
            "model": self.model,
            "messages": msgs,
            "tools": self._tools(tools),
            "stream": False,
            "think": think,
            "options": {"num_predict": self.num_predict, "num_ctx": self.num_ctx,
                        "temperature": 0.7, "top_p": 0.9},
        }
        return self._post("/api/chat", payload)

    def step(self, system, messages, tools):
        d = _retry(lambda: self._chat(system, messages, tools, think=self.think))
        msg = d.get("message") or {}
        text = (msg.get("content") or "").strip()
        raw_calls = msg.get("tool_calls") or []
        reasoning = msg.get("thinking") or ""

        # Forced closure, triggered by the ABSENCE OF A TOOL CALL rather than by empty output.
        #
        # This condition used to require empty text, and that missed the failure that actually
        # occurs. With `num_predict=-1` generation runs until the context is full, so a thought
        # longer than the remaining context is cut off mid-stream -- and what comes back is not
        # empty, it is the reasoning itself leaking into `content` with no tool call attached.
        # Measured: thinking grew 1854 -> 3785 -> 6682 -> 28569 characters across one episode, the
        # last three turns produced prose instead of calls, and the episode stalled having spent 3
        # of its 12 probes.
        #
        # In this harness every useful action is a tool call, so a call-less turn is worthless
        # whatever text accompanies it. Retrying once with thinking disabled converts a wasted turn
        # into an action. Note this is not a token cap: the first attempt still gets the full
        # context to think in.
        if not raw_calls and (reasoning or text):
            d = _retry(lambda: self._chat(system, messages, tools, think=False))
            msg = d.get("message") or {}
            text = (msg.get("content") or "").strip()
            raw_calls = msg.get("tool_calls") or []

        calls = []
        for i, c in enumerate(raw_calls):
            fn = c.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=f"c{i}", name=fn.get("name", ""),
                                  arguments=args if isinstance(args, dict) else {}))

        # `reasoning` here is whatever the FINAL call produced: on a forced-closure retry the
        # second call's thinking is what led to the action actually taken.
        return Step(text=text, tool_calls=calls,
                    reasoning=(msg.get("thinking") or reasoning or ""),
                    usage={"in": int(d.get("prompt_eval_count") or 0),
                           "out": int(d.get("eval_count") or 0)})

    def append_assistant(self, messages, step):
        # Thinking is deliberately NOT replayed. Feeding a model its own reasoning trace back as
        # dialogue degrades the following turn, and Qwen's own guidance is to drop it between
        # turns. The consequence is that the model re-derives from tool results each turn.
        msg: dict[str, Any] = {"role": "assistant", "content": step.text or ""}
        if step.tool_calls:
            msg["tool_calls"] = [
                {"function": {"name": c.name, "arguments": c.arguments}}
                for c in step.tool_calls
            ]
        messages.append(msg)

    def append_tool_results(self, messages, results):
        for c, out, _ok in results:
            messages.append({"role": "tool", "name": c.name, "content": out})


# --------------------------------------------------------------------------- transformers (local)

class TransformersProvider(Provider):
    """In-process inference with `transformers`, for hosts that already have torch.

    Preferred over `OllamaProvider` wherever torch is available, because it removes an entire
    class of failure rather than merely working around it: no 1.4 GB binary to fetch from a URL
    that may have moved, no background server or port to bind, no orphaned `llama-server`
    children silently holding GPU memory, and no guessing at a layer split decided from whatever
    VRAM happened to be free. Device placement is explicit here.

    Ollama remains the right choice on a host with no usable torch -- a Python version ahead of
    the available wheels, for instance, which is exactly the situation on the Windows machine this
    project was developed on and the reason the Ollama adapter exists at all.

    Thinking is handled the same way as on the hosted Space, and for the same measured reasons.
    Phase one is capped at `think_budget`; if it exhausts that budget the closing tag is appended
    and the model is given `answer_budget` more tokens to act. Both bounds are load-bearing: with
    no bound at all this model ran a single turn to 15,551 tokens, and with too small a bound the
    thought is truncated mid-stream and leaks into the message body with no tool call attached,
    which the episode loop reads as a stall.
    """

    family = "transformers"

    #: Weights of an 8B in bf16 are ~16 GiB. Below this much VRAM the model is quantised; at or
    #: above it, it is not. The threshold leaves headroom for the KV cache at `num_ctx`.
    BF16_VRAM_FLOOR_GIB = 24.0

    @staticmethod
    def autoconfig(torch: Any) -> dict[str, Any]:
        """Choose quantisation, dtype and attention kernel from the visible device.

        The defaults are hardware-dependent because the right answer inverts between cards:

        * On a **T4** (16 GiB, Turing, no bf16) 4-bit NF4 is mandatory -- fp16 weights alone are
          ~16 GiB and will not load -- and float16 is the only option.
        * On an **A100** (40/80 GiB, Ampere) 4-bit is not merely unnecessary, it is *slower*:
          every matmul pays a dequantisation cost that buys nothing once the weights already fit.
          bf16 also removes the fp16 overflow risk, and SDPA gives fused attention kernels that
          Turing cannot use.

        Loading 4-bit on an A100 is therefore a silent performance bug rather than a safe
        default, which is why this is detected rather than hard-coded. Every element is
        overridable by environment variable for a host that disagrees.
        """
        env = os.environ.get
        if not torch.cuda.is_available():
            return {"load_in_4bit": False, "dtype": "float32", "attn": "eager",
                    "device": "cpu", "vram_gib": 0.0}

        props = torch.cuda.get_device_properties(0)
        gib = props.total_memory / 1024 ** 3
        bf16 = torch.cuda.is_bf16_supported()

        cfg = {
            "load_in_4bit": gib < TransformersProvider.BF16_VRAM_FLOOR_GIB,
            "dtype": "bfloat16" if bf16 else "float16",
            # SDPA is built into torch, so it costs no install; flash-attn would need a ~10-minute
            # source build for a marginal further gain.
            "attn": "sdpa" if props.major >= 8 else "eager",
            "device": props.name,
            "vram_gib": round(gib, 1),
        }
        if env("ARS_LOAD_4BIT") is not None:
            cfg["load_in_4bit"] = env("ARS_LOAD_4BIT") not in ("0", "false", "False", "")
        if env("ARS_DTYPE"):
            cfg["dtype"] = env("ARS_DTYPE")
        if env("ARS_ATTN"):
            cfg["attn"] = env("ARS_ATTN")

        # TF32 costs nothing on Ampere and speeds up the fp32 paths that remain.
        if props.major >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        return cfg

    def __init__(self, model: str = "Qwen/Qwen3-8B",
                 load_in_4bit: bool | None = None,
                 think_budget: int | None = None,
                 max_tokens: int | None = None,
                 dtype: str | None = None,
                 attn_implementation: str | None = None):
        import torch  # noqa: PLC0415 - imported lazily so a host without torch is unaffected
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

        self.model = model
        self._torch = torch

        auto = self.autoconfig(torch)
        load_in_4bit = auto["load_in_4bit"] if load_in_4bit is None else load_in_4bit
        dtype = dtype or auto["dtype"]
        attn = attn_implementation or auto["attn"]
        self.hardware = {**auto, "load_in_4bit": load_in_4bit, "dtype": dtype, "attn": attn}

        self._dtype = getattr(torch, dtype)
        self.think_budget = int(think_budget or os.environ.get("ARS_THINK_BUDGET") or 6144)
        self.answer_budget = int(max_tokens or os.environ.get("ARS_ANSWER_BUDGET") or 512)

        kw: dict[str, Any] = {"dtype": self._dtype, "device_map": "auto",
                              "attn_implementation": attn}
        if load_in_4bit:
            # 4-bit NF4 puts an 8B inside ~5.5 GiB, which leaves a 16 GiB card ample room for the
            # KV cache. Without it, fp16 weights alone are ~16 GiB and will not fit.
            from transformers import BitsAndBytesConfig  # noqa: PLC0415

            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=self._dtype,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )

        print(f"[transformers] {model} on {auto['device']} ({auto['vram_gib']} GiB): "
              f"4bit={load_in_4bit} dtype={dtype} attn={attn}")

        self.tokenizer = AutoTokenizer.from_pretrained(model)
        try:
            self.net = AutoModelForCausalLM.from_pretrained(model, **kw)
        except (ValueError, ImportError) as e:
            # An unsupported attention kernel must not take the run down; fall back and say so,
            # because silently degrading to eager would look like a mysteriously slow A100.
            if "attn_implementation" not in kw or attn == "eager":
                raise
            print(f"[transformers] attn={attn} rejected ({e}); falling back to eager")
            kw["attn_implementation"] = "eager"
            self.hardware["attn"] = "eager"
            self.net = AutoModelForCausalLM.from_pretrained(model, **kw)
        self.net.eval()

    # -- thinking-trace handling, mirroring the Space ------------------------------------------
    _THINK = re.compile(r"<think>.*?</think>", re.S)
    _THINK_OPEN = re.compile(r"<think>.*$", re.S)
    _CLOSE_THINK = "\n</think>\n\n"
    _TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)

    def _split_thinking(self, text: str) -> tuple[str, str]:
        reasoning = " ".join(m.group(0) for m in self._THINK.finditer(text))
        body = self._THINK.sub("", text)
        if "<think>" in body:                       # truncated mid-thought
            reasoning += " " + self._THINK_OPEN.search(body).group(0)
            body = self._THINK_OPEN.sub("", body)
        return body.strip(), reasoning.strip()

    def _parse_tool_calls(self, text: str) -> tuple[str, list[ToolCall]]:
        """A malformed call is dropped, never guessed at: inventing arguments here would put
        fabricated agent behaviour into the transcripts, which is worse than a lost turn."""
        calls: list[ToolCall] = []
        for i, m in enumerate(self._TOOL_CALL.finditer(text)):
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            name = obj.get("name")
            if not name:
                continue
            args = obj.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=f"c{i}", name=name,
                                  arguments=args if isinstance(args, dict) else {}))
        return self._TOOL_CALL.sub("", text).strip(), calls

    def _tools(self, tools) -> list[dict]:
        return [{"type": "function",
                 "function": {"name": t.name, "description": t.description,
                              "parameters": t.schema}}
                for t in tools]

    def step(self, system, messages, tools):
        torch = self._torch
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        prompt = self.tokenizer.apply_chat_template(
            msgs, tools=self._tools(tools), add_generation_prompt=True, tokenize=False,
            enable_thinking=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.net.device)
        n_in = int(inputs["input_ids"].shape[-1])

        with torch.no_grad():
            out = self.net.generate(
                **inputs, max_new_tokens=self.think_budget, do_sample=True,
                temperature=0.7, top_p=0.9, pad_token_id=self.tokenizer.eos_token_id,
            )
        gen = out[0][n_in:]
        raw = self.tokenizer.decode(gen, skip_special_tokens=True)
        n_out = int(gen.shape[-1])

        # Forced closure on TRUNCATION, not on empty output. The failure that actually occurs is a
        # thought cut off mid-stream, which leaves plenty of text -- the reasoning itself -- with
        # no tool call attached.
        if n_out >= self.think_budget:
            suffix = "" if "</think>" in raw else self._CLOSE_THINK
            extra = ([] if not suffix else
                     [self.tokenizer(suffix, return_tensors="pt",
                                     add_special_tokens=False)["input_ids"][0].to(self.net.device)])
            closed = torch.cat([out[0], *extra]).unsqueeze(0)
            with torch.no_grad():
                out2 = self.net.generate(
                    input_ids=closed, attention_mask=torch.ones_like(closed),
                    max_new_tokens=self.answer_budget, do_sample=True, temperature=0.7,
                    top_p=0.9, pad_token_id=self.tokenizer.eos_token_id,
                )
            tail = out2[0][closed.shape[-1]:]
            n_out += int(tail.shape[-1])
            raw = raw + suffix + self.tokenizer.decode(tail, skip_special_tokens=True)

        body, reasoning = self._split_thinking(raw)
        text, calls = self._parse_tool_calls(body)
        return Step(text=text, tool_calls=calls, reasoning=reasoning,
                    usage={"in": n_in, "out": n_out})

    def append_assistant(self, messages, step):
        # Reasoning is recorded in the episode but never replayed: feeding a model its own trace
        # back as dialogue degrades the following turn, and Qwen's guidance is to drop it.
        msg: dict[str, Any] = {"role": "assistant", "content": step.text or ""}
        if step.tool_calls:
            msg["tool_calls"] = [
                {"type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in step.tool_calls
            ]
        messages.append(msg)

    def append_tool_results(self, messages, results):
        for c, out, _ok in results:
            messages.append({"role": "tool", "name": c.name, "content": out})


# --------------------------------------------------------------------------- Google

class GoogleProvider(Provider):
    family = "google"

    def __init__(self, model: str = "gemini-3-pro", max_tokens: int = 2048):
        from google import genai

        key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        self.client = genai.Client(api_key=key)
        self.model = model
        self.max_tokens = max_tokens
        #: The raw parts of the last response. Gemini 3.x attaches a `thought_signature` to
        #: functionCall parts and REQUIRES it to be present when that call is echoed back in the
        #: history; rebuilding the parts from name+args drops it and the next request fails with
        #: 400 "Function call is missing a thought_signature". So we replay the originals.
        self._last_parts: list[Any] | None = None

    def step(self, system, messages, tools):
        from google.genai import types

        decls = [types.FunctionDeclaration(name=t.name, description=t.description, parameters=t.schema)
                 for t in tools]
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=decls)],
            max_output_tokens=self.max_tokens,
        )
        resp = _retry(lambda: self.client.models.generate_content(
            model=self.model, contents=messages, config=cfg))

        text, calls = "", []
        cand = resp.candidates[0] if resp.candidates else None
        self._last_parts = list(cand.content.parts) if cand and cand.content and cand.content.parts else None
        for part in (cand.content.parts if cand and cand.content else []):
            if getattr(part, "text", None):
                text += part.text
            fc = getattr(part, "function_call", None)
            if fc:
                calls.append(ToolCall(id=fc.name, name=fc.name, arguments=dict(fc.args or {})))
        um = getattr(resp, "usage_metadata", None)
        return Step(text=text, tool_calls=calls,
                    stop_reason=str(getattr(cand, "finish_reason", "")) if cand else "",
                    usage={"in": getattr(um, "prompt_token_count", 0) or 0,
                           "out": getattr(um, "candidates_token_count", 0) or 0})

    def append_assistant(self, messages, step):
        from google.genai import types

        # Replay the model's ORIGINAL parts rather than reconstructing them. Gemini 3.x signs
        # functionCall parts with a `thought_signature` and rejects a history in which that
        # signature is absent, so a rebuilt part fails even when name and args are identical.
        parts = list(self._last_parts) if self._last_parts else []
        if not parts:
            if step.text:
                parts.append(types.Part(text=step.text))
            for c in step.tool_calls:
                parts.append(types.Part(
                    function_call=types.FunctionCall(name=c.name, args=c.arguments)))
        # Gemini also requires alternating user/model turns; a turn with no parts at all would
        # leave two consecutive user turns once the loop appends its nudge.
        if not parts:
            parts.append(types.Part(text="(no output)"))
        messages.append(types.Content(role="model", parts=parts))

    def append_tool_results(self, messages, results):
        from google.genai import types

        parts = [types.Part(function_response=types.FunctionResponse(
            name=c.name, response={"output": out, "error": not ok}))
            for c, out, ok in results]
        messages.append(types.Content(role="user", parts=parts))


# --------------------------------------------------------------------------- registry

# --------------------------------------------------------------------------- Bedrock

class BedrockProvider(Provider):
    """Amazon Bedrock through the Converse API.

    Added because every other provider in this study is metered against a shared free tier and
    three of them throttled during the behavioural run: a per-model request cap, a cooldown that
    matched the retry ladder's own ceiling, and a tokens-per-minute limit that turned a five
    minute episode into fifty. Bedrock bills per token against an account, so the arm is bounded
    by budget rather than by someone else's quota -- which makes an episode's wall-clock a
    property of the model instead of a property of the hour it was run in.

    Two Bedrock-specific details are load-bearing:

    * **Inference profiles.** Several Nova models refuse a raw model id with "on-demand
      throughput isn't supported" and require a regional profile instead -- `eu.amazon.nova-pro`
      rather than `amazon.nova-pro`. The prefix is derived from the region, because getting it
      wrong presents as a ValidationException that reads like a malformed request rather than a
      routing problem.
    * **Converse, not InvokeModel.** Converse gives one tool-calling shape across vendors, so the
      episode loop does not need a per-model adapter for what is meant to be a cross-family
      comparison.
    """

    family = "bedrock"

    #: Regions map to inference-profile prefixes. A model invoked without the prefix where one is
    #: required fails with a message about throughput, not about naming.
    _PREFIX = {"us": "us.", "eu": "eu.", "ap": "apac."}

    def __init__(self, model: str = "amazon.nova-lite-v1:0", max_tokens: int = 2048,
                 region: str | None = None):
        import boto3

        self.region = region or os.environ.get("AWS_REGION") or "us-east-1"
        self.client = boto3.client("bedrock-runtime", region_name=self.region)
        self.model = model
        self.max_tokens = max_tokens

    def _alternates(self, model: str) -> list[str]:
        """Model ids to try, in order.

        Whether a model needs a regional inference profile is a per-model fact, not a
        per-region one: Nova refuses the bare id with "on-demand throughput isn't supported",
        while `openai.gpt-oss-120b` has no regional profile at all and rejects the prefixed
        form as an invalid identifier. Prefixing unconditionally breaks the second group;
        never prefixing breaks the first. So both are offered and the API decides, once.
        """
        if model.startswith(("us.", "eu.", "apac.", "global.")):
            return [model]
        prefix = self._PREFIX.get(self.region.split("-")[0], "")
        return [model, prefix + model, "global." + model] if prefix else [model]

    def _resolve(self, kw: dict[str, Any]):
        """Call converse, settling on whichever id form this model accepts."""
        last: Exception | None = None
        for candidate in self._alternates(self.model):
            try:
                resp = self.client.converse(**{**kw, "modelId": candidate})
                self.model = candidate          # remember, so later turns cost one call
                return resp
            except Exception as e:
                msg = str(e)
                if "ValidationException" not in type(e).__name__ and "identifier" not in msg:
                    raise                        # a real failure, not a naming one
                last = e
        raise last if last else RuntimeError("no model id form accepted")

    def step(self, system, messages, tools):
        kw: dict[str, Any] = {
            "modelId": self.model,
            "messages": messages,
            "inferenceConfig": {"maxTokens": self.max_tokens},
        }
        if system:
            kw["system"] = [{"text": system}]
        if tools:
            kw["toolConfig"] = {"tools": [
                {"toolSpec": {"name": t.name, "description": t.description,
                              "inputSchema": {"json": t.schema}}}
                for t in tools]}

        resp = _retry(lambda: self._resolve(kw))

        blocks = resp["output"]["message"]["content"]
        text = "".join(b["text"] for b in blocks if "text" in b)
        calls = [ToolCall(id=b["toolUse"]["toolUseId"],
                          name=b["toolUse"]["name"],
                          arguments=b["toolUse"].get("input") or {})
                 for b in blocks if "toolUse" in b]
        u = resp.get("usage", {})
        return Step(text=text, tool_calls=calls,
                    stop_reason=str(resp.get("stopReason", "")),
                    usage={"in": u.get("inputTokens", 0), "out": u.get("outputTokens", 0)})

    def append_assistant(self, messages, step):
        content: list[dict[str, Any]] = []
        if step.text:
            content.append({"text": step.text})
        for c in step.tool_calls:
            content.append({"toolUse": {"toolUseId": c.id, "name": c.name, "input": c.arguments}})
        if content:
            messages.append({"role": "assistant", "content": content})

    def append_tool_results(self, messages, results):
        # Converse requires tool results to come back as a user turn, each block keyed to the
        # toolUseId it answers. A mismatched id is rejected outright rather than ignored.
        blocks = [{"toolResult": {"toolUseId": c.id,
                                  "content": [{"text": out}],
                                  "status": "success" if ok else "error"}}
                  for c, out, ok in results]
        messages.append({"role": "user", "content": blocks})


#: Capability tiers within each family, so the paper can report a capability-scaling result
#: alongside the cross-family generalisation result.
REGISTRY: dict[str, tuple[type[Provider], str]] = {
    # Google -- hosted frontier, two capability tiers
    "gemini-lite":  (GoogleProvider, "gemini-3.5-flash-lite"),
    "gemini-flash": (GoogleProvider, "gemini-3.5-flash"),
    "gemini-pro":   (GoogleProvider, "gemini-3.1-pro-preview"),
    "gemini-2.5":   (GoogleProvider, "gemini-2.5-flash"),
    # gpt-oss via Groq -- open-weight, two capability tiers
    "oss-20b":      (GroqProvider, "openai/gpt-oss-20b"),
    "oss-120b":     (GroqProvider, "openai/gpt-oss-120b"),
    # Qwen via Groq -- a third training lineage
    "qwen-27b":     (GroqProvider, "qwen/qwen3.6-27b"),
    "qwen38-27b":   (GroqProvider, "qwen/qwen3.8-27b"),
    # NVIDIA NIM -- open-weight, further lineages. Needs an `nvapi-` key.
    # Model ids verified against the live NIM catalogue, not guessed.
    "nemotron-70b": (NvidiaProvider, "nvidia/llama-3.1-nemotron-70b-instruct"),
    "mistral-lg":   (NvidiaProvider, "mistralai/mistral-large-2-instruct"),
    "deepseek":     (NvidiaProvider, "deepseek-ai/deepseek-v4-pro-0813"),
    "mixtral":      (NvidiaProvider, "mistralai/mixtral-8x22b-v0.1"),
    # Kimi K3 (Moonshot) via NIM. A reasoning model: it emits a `reasoning_content` field and
    # spends output budget there before any `content` appears, so a small max_tokens returns an
    # empty answer that looks like a refusal. Measured latency is 70-130 s per call at low effort,
    # and `seed` does NOT make it deterministic (verified: three seeded calls diverged). Both facts
    # are recorded because they bound what a behavioural run with this model can claim. `kimi-k2.6`
    # is in the catalogue but 404s for our account, so only k3 is usable.
    "kimi":         (NvidiaProvider, "moonshotai/kimi-k3"),
    # Through the self-hosted gateway: failover + far lower latency than the direct NIM path.
    # Bedrock -- billed per token against an account rather than a shared free tier, so the
    # arm is bounded by budget instead of by another tenant's quota.
    "nova-micro":   (BedrockProvider, "amazon.nova-micro-v1:0"),
    "nova-lite":    (BedrockProvider, "amazon.nova-lite-v1:0"),
    "nova-pro":     (BedrockProvider, "amazon.nova-pro-v1:0"),
    "nova-2-lite":  (BedrockProvider, "amazon.nova-2-lite-v1:0"),
    "gw-kimi":      (GatewayProvider, "kimi-k3"),
    "gw-auto":      (GatewayProvider, "auto"),
    # OpenRouter -- reaches every family through one endpoint, including the proprietary
    # models this study otherwise could not test. Model ids are verified live before use.
    # Free tier. Tool-calling support verified live before registration -- several free models
    # accept the tools parameter and silently never emit a call, which would look like an agent
    # that declined to act rather than a model that cannot.
    #
    # `or-glm` is GLM-5.2, the open-weight model Hugging Face's own incident responders fell back
    # to when hosted frontier models refused their forensic work. Measuring channel genesis on the
    # exact model a defender reached for under refusal is as close to the incident as this study
    # can get without proprietary access.
    "or-glm":       (OpenRouterProvider, "z-ai/glm-5.2:free"),
    "or-nemotron":  (OpenRouterProvider, "nvidia/nemotron-3-super-120b-a12b:free"),
    "or-lightning": (OpenRouterProvider, "nvidia/nemotron-3.5-lightning:free"),
    # Our own ZeroGPU Space -- no rate limit, no daily cap, no per-minute token ceiling.
    "qwen-space": (HFSpaceProvider, "Qwen/Qwen3-8B"),
    # Local quantized inference on this machine's GPU: no quota, no queue.
    "qwen-local":  (OllamaProvider, "qwen3:4b"),
    "qwen8-local": (OllamaProvider, "qwen3:8b"),
    # The one that actually fits. Qwen3-8B at Q4_K_M is 5.23 GiB against 5.0 GiB free, so Ollama
    # offloaded only 24 of 37 layers and GPU utilisation sat at ~35% waiting on the CPU-resident
    # remainder -- a single deduction had not finished after six minutes. Q3_K_M is 4.1 GiB and
    # goes fully resident with room for the KV cache. Worth the quantization loss because the 4B,
    # which does fit at Q4, cannot perform the task's core inference at any token budget.
    "qwen8-q3":    (OllamaProvider, "hf.co/unsloth/Qwen3-8B-GGUF:Q3_K_M"),
    # In-process, straight from Hugging Face. Preferred anywhere torch works.
    "qwen8-hf":    (TransformersProvider, "Qwen/Qwen3-8B"),
    "qwen4-hf":    (TransformersProvider, "Qwen/Qwen3-4B"),
    # Present only if the corresponding key is supplied
    "claude-haiku": (AnthropicProvider, "claude-haiku-4-5-20251001"),
    "claude-sonnet": (AnthropicProvider, "claude-sonnet-5"),
    "gpt":          (OpenAIProvider, "gpt-5.1"),
}


def build(alias: str, **kw: Any) -> Provider:
    """Instantiate a provider by registry alias, or by explicit `family:model`."""
    if alias in REGISTRY:
        cls, model = REGISTRY[alias]
        # Reasoning models spend output budget on `reasoning_content` before emitting any
        # `content` or tool call. At the default 2048 a turn truncates mid-reasoning and the
        # agent looks like it declined to act. Kimi K3 needs a much larger ceiling; the value is
        # set here rather than in the class so ordinary models keep the tighter default.
        if "kimi" in model.lower() and "max_tokens" not in kw:
            kw["max_tokens"] = 8192
        return cls(model=model, **kw)
    if ":" in alias:
        fam, model = alias.split(":", 1)
        cls = {"anthropic": AnthropicProvider, "openai": OpenAIProvider,
               "google": GoogleProvider, "groq": GroqProvider,
               "nvidia": NvidiaProvider, "openrouter": OpenRouterProvider,
               "gateway": GatewayProvider, "hf": HFRouterProvider,
               "huggingface": HFRouterProvider,
               "hfspace": HFSpaceProvider, "ollama": OllamaProvider,
               "transformers": TransformersProvider,
               "bedrock": BedrockProvider}.get(fam)
        if cls:
            return cls(model=model, **kw)
    raise ValueError(f"unknown model alias {alias!r}; known: {sorted(REGISTRY)}")


def _torch_available() -> bool:
    """True if torch can be imported with a usable CUDA device.

    A live check rather than a declared capability: on the Windows host this project was built on,
    Python is ahead of the available torch wheels and the import simply fails, which is the entire
    reason the Ollama adapter exists.
    """
    try:
        import torch  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - a broken install is as disqualifying as a missing one
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def _ollama_up(host: str | None = None) -> bool:
    """True if an Ollama server answers. Availability is a live check, not an env var."""
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    base = (host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def available() -> list[str]:
    """Registry aliases whose family has a key present. Used to skip families cleanly."""
    have = {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "google": bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")),
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "nvidia": bool(os.environ.get("NVIDIA_API_KEY")),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        "hfspace": bool(os.environ.get("HF_TOKEN")),
        # Ollama needs no key; it needs a reachable server, so this is a live probe.
        "ollama": _ollama_up(),
        # transformers needs torch present, not a key or a server.
        "transformers": _torch_available(),
        # The self-hosted gateway needs its unified key; the server being reachable is checked
        # when a call is actually made, not here.
        "gateway": bool(os.environ.get("FREELLM_KEY")),
        # Bedrock authenticates through the standard AWS chain, so a key in the environment
        # is only one of several valid ways to be credentialled.
        "bedrock": bool(os.environ.get("AWS_ACCESS_KEY_ID")
                        or os.environ.get("AWS_PROFILE")),
    }
    fam_of = {AnthropicProvider: "anthropic", OpenAIProvider: "openai",
              GoogleProvider: "google", GroqProvider: "groq", NvidiaProvider: "nvidia",
              OpenRouterProvider: "openrouter", HFSpaceProvider: "hfspace",
              OllamaProvider: "ollama", TransformersProvider: "transformers",
              GatewayProvider: "gateway", BedrockProvider: "bedrock"}
    # GroqProvider subclasses OpenAIProvider, so test the most specific class first.
    def fam(cls):
        for c in (BedrockProvider, GatewayProvider, GroqProvider, NvidiaProvider, OpenRouterProvider,
                  HFSpaceProvider, OllamaProvider, TransformersProvider,
                  AnthropicProvider, GoogleProvider, OpenAIProvider):
            if cls is c:
                return fam_of[c]
        return fam_of[cls]
    return [a for a, (cls, _) in REGISTRY.items() if have[fam(cls)]]
