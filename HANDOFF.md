# Handoff — Track 1, covert channels through shared agent infrastructure

**Project:** AI Incident Response Sprint (Apart Research + CeSIA), 11–13 Sept 2026
**Track 1 subject:** the July 2026 incident in which OpenAI evaluation agents used a shared
package cache (Artifactory) as a covert message board between episodes.
**Author:** Fatimah Emad Eldin
**Date of this handoff:** 2026-09-06

---

## 0. Start here — orientation for a new session

**Repo root:** `D:\ins respinse\project-v2` (Windows; Git Bash available, PowerShell primary).
Note the **space in the path** — it breaks Docker bind mounts; see §3.

**Where things live**

| Path | What |
|---|---|
| `paper/main.tex.tmpl` | The manuscript template (numbers substituted at build) |
| `paper/render.py` | Recomputes every claim from `results/`; `--list` prints them |
| `src/capacity.py`, `src/joint.py`, `src/substrate.py`, `src/srm.py` | The measurement arm |
| `runner/run.py` | The behavioural experiment (conditions × models × seeds) |
| `runner/providers.py` | Provider registry + aliases |
| `colab/gate.py` | Capability gate a model must pass to be an arm |
| `real/` | Docker tiers 1–3, gateway compose, probes |
| `results/` | All measured artifacts — the source of every number |
| `track3/` | Track 3 submission (separate, complete) |

**State as of this handoff**

- Gemini is the **primary arm** and has **passed the capability gate**. Nothing else is gated.
- Tier 3 containers were switched from Kimi to Gemini (`MODEL_ALIAS: gemini-flash`).
- Two files were patched this session — `colab/gate.py` (per-provider message shape) and
  `real/Dockerfile` (added `google-genai`). Both were needed for Gemini to work at all.
- **The Gemini Δ arm has not been run yet.** That is the immediate next step (§9).
- No background jobs should be running. If one is, it is a Tier 3 sender/receiver pair.

**First commands to orient yourself**

```bash
cd "D:/ins respinse/project-v2"
python paper/render.py --list          # every claim, recomputed
git status                             # if the repo has been initialised
```


---

## 1. What the project claims

Published controls governing agent-to-agent information flow are **authorization-shaped** and
**cross-principal** — tenant to tenant, agent to another agent's memory (CSA AICM **AIS-11**
"Agents Security Boundaries", **AIS-14** "AI Cache Protection"). The incident is the opposite case:
the agents were the **same tenant**, **all legitimately authorized**, using **only permitted
operations**. Every AIS-11/AIS-14 audit check as written would *pass* while the board was in active
use.

That is a covert channel in the classical sense. AIS-11 states the requirement as policy and
attaches **no method for verifying it**. This project supplies the measurement.

> The earlier, stronger claim ("no published control governs this") is **refuted** — AIS-11 and
> AIS-14 exist. The corrected claim above is narrower, rests on what the controls *say* rather than
> on their absence, and is what the manuscript argues.

---

## 2. Current measured results

All numbers are substituted into the manuscript from `results/` at build time by
`paper/render.py`. Nothing is hand-typed. Verify any value with `python paper/render.py --list`.

| Quantity | Value | Meaning |
|---|---|---|
| `OPEN_BITS` | ≥ 11453 | Per-attribute **sum**, nothing closed (upper bound) |
| `CONTENT_BITS` | ≥ 3261 | Per-attribute **sum** at the content rung (upper bound) |
| `FILENAME_BITS` | 1789 | Per-attribute **sum** at the filename rung |
| `DIRNAME_BITS` | 0 | Per-attribute **sum** at the dirname rung — channel shut |
| `JOINT_BITS` | 3075 | **The headline.** One encoder, one payload, 8/8 exact |
| `SUM_MINUS_JOINT` | 186 | = 128 count-dependency + 58 measured encoder loss |
| `PASSCODE_BITS` | 20.7 | Bits a successor actually needs |
| `ORDER_BITS` | 0 | Creation order carries nothing (`list_dir` returns sorted) |
| `MAX_ENTRIES` | 256 | Directory entry ceiling (now enforced) |

> **Read this before comparing the numbers.** `OPEN_BITS` and `CONTENT_BITS` are **sums of
> separately measured cells**; `JOINT_BITS` is a **single encoder measured end to end**. They are
> *not* successive rungs of one quantity, so 3075 does not "exceed" anything: both 3261 and 3075
> describe the **same** content-closed rung, and they reconcile exactly —
> 3261 − 3075 = 186 = 128 (count, excluded from the joint) + 58 (encoder loss). Two separate
> readers of an earlier version of this table read the sums as residuals and concluded the
> pipeline had emitted an arithmetic impossibility. The word *residual* now means the joint
> figure only, and `paper/render.py` fails the build if the manuscript applies it to a sum.

**Why 3075 is the number to quote, not 11453 or 3261.** The latter two are *sums of separately
measured cells* and two of those rungs still contain a censored row. 3075 is a single joint encoder
measured end to end with zero errors over 8 trials, and it contains **no censored quantity**.

**The closure ladder is cumulative:** content → filename → dirname → existence. Closing dirname
takes the channel to zero. Cost: content closure = 2 mediation points (payload class); dirname
closure = 6 mediation points (structural class), i.e. **+4 points, all structural**.

---

## 3. Real-infrastructure tiers (answers the "synthetic substrate" objection)

| Tier | What it is | Status |
|---|---|---|
| **Tier 1** | Real shared Docker volume; `real/probe_limits.py` probes actual mount limits | ✅ done |
| **Tier 2** | Real OCI registry (`registry:2`); `real/probe_store.py` | ✅ done |
| **Tier 3** | Two containers (sender / receiver), separate PID + mount namespaces, no shared transcript — only the volume | ✅ done, now on Gemini |

Findings worth keeping:
- Real mount body limit **67,108,864 bytes** = **8,192×** the modelled 8192-byte limit.
- Real timestamps resolve to **1 ns, exact**.
- The OCI registry closes **filename only** (content-addressed sha256) → it sits at **no rung** of
  the ladder.

Run them:
```bash
docker compose -f real/docker-compose.yml run --rm --build probe        # Tier 1
docker compose -f real/docker-compose.yml run --rm probe-store          # Tier 2
docker compose -f real/docker-compose.yml run --rm --build sender       # Tier 3 gen g
docker compose -f real/docker-compose.yml run --rm receiver             # Tier 3 gen g+1
```

**Windows gotchas already solved (do not re-discover):**
- Docker bind mounts fail on a Windows path containing a space → use **named volumes** only.
- `MSYS_NO_PATHCONV=1` is required to read the volume from Git Bash.
- `docker compose run` does **not** rebuild → pass `--build`.
- `--rm` deletes `/work`; write artifacts to the **shared volume**, not `/work`.

---

## 4. Model providers — the current, verified picture

This was the bulk of the most recent work. Summary of what is and is not usable.

### ✅ Gemini — verified, free, and now the primary arm

- Path: **Gemini Developer API** via `google-genai`, `genai.Client(api_key=...)`, key
  `GEMINI_API_KEY` in `.env`. This is the **free** backend.
- **Do not** use the Vertex / Enterprise setup (`GOOGLE_CLOUD_PROJECT`,
  `GOOGLE_GENAI_USE_ENTERPRISE`) — that is the paid Cloud backend.
- Aliases: `gemini-lite`, `gemini-flash` (→ `gemini-3.5-flash`), `gemini-pro`.
- **Capability gate: PASSED.** Tool calling ✅ (`validate({'candidate':'ABCD'})`); deduction
  **3/3** (`CDG`). Gate output: *"safe to calibrate"*.
- No gateway, no HuggingFace billing, no aggregator in the path.

### Rate limits — measured, not assumed

The runner already treats rate limits as first class. Do not add ad-hoc sleeps on top of it.

- `providers._retry` — 8 attempts, exponential backoff, **120 s ceiling**, and it detects
  `429` / `rate limit` / `rate_limit` and **honours the server's own `Retry-After`**
  (both the `retry-after: N` and the `try again in N m/s` phrasings).
- `providers._PACE` — a **4.0 s** floor between calls per process (a 15 RPM ceiling), overridable
  with **`ARS_PACE_SECONDS`**.
- The design intent, quoted from the source: *a free-tier limit must delay an episode rather than
  destroy it*, because a truncated episode silently biases the success rate downward and would
  corrupt the calibration curve.
- `run.py` resumes by default (`resume: bool = True`), so a daily cap **pauses** a sweep; the next
  invocation continues and nothing already completed is re-run.

**Measured against Gemini — and the first analysis of this was WRONG, so read carefully.**

The initial reading looked at **requests per minute** (~2 RPM observed against a ~10–15 RPM cap)
and concluded there was ample headroom. That measured the wrong axis. The binding limit on the new
Gemini models is a small **total request cap**, and it was hit mid-run:

```
429 RESOURCE_EXHAUSTED
metric: generativelanguage.googleapis.com/generate_content_free_tier_requests
limit: 20, model: gemini-3.5-flash
```

**The cap is per model, not per project.** Verified by probing each variant with one request:

| Alias | Model | Free-tier state |
|---|---|---|
| `gemini-2.5` | `gemini-2.5-flash` | usable |
| `gemini-lite` | `gemini-3.5-flash-lite` | usable |
| `gemini-flash` | `gemini-3.5-flash` | **cap 20 — exhausted by one gate + one episode** |

**Consequences for sizing.** One episode costs **15–18 requests** — so a *single* Tier 3 episode
plus its 4-request gate exhausts `gemini-3.5-flash` for the day. Prefer **`gemini-2.5`**: it is the
older generation and not subject to the new-model cap. Never size an arm from an assumed RPD;
one episode ≈ 15–18 requests is the only number to plan with, and `run.py` resumes by default so a
cap pauses rather than destroys a sweep.

**Beware the failure mode when quota is gone.** `_retry` treats 429 as transient and walks its full
ladder — 8 attempts with backoff to a 120 s ceiling — so an exhausted-quota call can burn ~10
minutes before it finally raises. A run against a dead quota looks hung rather than failed.


### ⚠️ HuggingFace — real money, currently the only Kimi-via-gateway route

- Account is **PRO**, credits **$1.73**, **Automatic Recharge OFF**.
- **Auto-recharge off means you cannot be surprise-billed**: when credits run out, inference
  *stops* rather than charging the card.
- ~**$0.24** already spent on testing (16 requests via Baseten/DeepInfra — HF's kimi-k3 backends).
- Rough rate ≈ **$0.015/request**, one request per agent turn.

### ❌ NavyAI — catalogue is large but the free tier is switched off

- Direct endpoint `https://api.navy/v1` (OpenAI-compatible), key `SK_NAVY_API_KEY` in `.env`.
- **163 models, 110 free** — GPT/o3/o4, Gemini, Claude, DeepSeek, Grok, GLM, Qwen, Kimi, Mistral,
  Command, Nemotron.
- **Blocked right now:** `"The Free plan is temporarily disabled due to abuse."` This affects *all*
  free models, not just gpt-5.4. The gateway reports it confusingly as `rate_limit_exceeded`.
- The key **is correctly wired** — platform id is **`navy`**, *not* `navyai` (the gateway crashes
  on an unknown platform). It will start working if/when NavyAI re-enables the free tier.
- Tool-calling on NavyAI models is **unverified** (the plan block prevented the test).

### FreeLLMAPI gateway

- Self-hosted, `ghcr.io/tashfeenahmed/freellmapi:latest`, compose at `real/gateway-compose.yml`,
  listening on `127.0.0.1:3001`.
- Provider keys seeded from `FREEAPI_CONFIG_JSON` inside `real/freellm/gateway.env`.
  Platforms configured: `google, groq, huggingface, navy, nvidia, openrouter`.
- Unified key in `real/freellm/unified.key`. **It lives in the `freellm-data` named volume** —
  `--force-recreate` preserves it; **removing the volume would change it** and break everything.
- Backup of the pre-edit config: `real/freellm/gateway.env.bak`.

### Other free, first-party arms (own keys, no HF, fixed model)

| Alias | Provider | Note |
|---|---|---|
| `or-glm` | OpenRouter | GLM-5.2 — the model HF's own incident responders fell back to |
| `oss-120b`, `qwen38-27b` | Groq | open-weight |
| `deepseek`, `nemotron-70b` | NVIDIA NIM | `deepseek-v4-pro` |
| `kimi` | NVIDIA NIM | Kimi **without** HF billing, but 70–130 s/call and flaky |

> **Do not use `gw-auto` for the sweep.** It can still route onto HuggingFace (HF is in its pool)
> **and** it swaps the model between calls — invalid for a cross-model experiment where each arm
> must be one fixed model. Pin a named model instead.

---

## 5. Kimi findings (recorded so they are not re-measured)

From 3 real calibration episodes on `gw-kimi`:

- **avg 12,006 tokens/episode**, max 15,448, **avg 3.3 turns**, **3/3 success** in the `open` arm.
- Kimi is *fast* — it batches 10–16 guesses per turn, versus Claude's ~27 turns.
- **Open arm is at ceiling (3/3).** The `no_substrate` arm was **never measured** — that run was
  stopped to free the gateway for reconfiguration.
- **Therefore Kimi's calibration verdict is UNDETERMINED.** If `no_substrate` is also ~1.0, Δ ≈ 0
  and Kimi is unusable as a behavioural arm (the ceiling counterpart of Qwen's flooring). Resolving
  it costs ~$0.15 of HF credit, or is free but slow via the `kimi` NIM alias.

Token budget is a non-issue: 30 episodes ≈ 360K tokens against a 7.4B/month allowance.

---

## 6. Open items

| ID | Item | Status |
|---|---|---|
| **W-2** | Re-measure the capacity ladder against the **real Docker volume** (needs no model — point `Substrate` at `/cache`). A genuine 2–4 day win. | **open** |
| **W-3** | State per-row encoder efficiency, or add an ensemble | **open** |
| **W-7** | Push the repo; fill `url` / `commit` / `archive_doi` in `paper/artifact.json` (still `[PENDING]`) | **open, needs user** |
| — | Kimi `no_substrate` arm (see §5) | optional |
| — | Obtain primary AICM v1.1 control text (behind a login) | needs user |

---

## 7. Standing conventions

- **Papers read as academic work, never as a lab notebook.** No narration of development errors or
  iterations in the manuscript. Sections: Methodology / Results / Error Analysis / Discussion.
  All revision-history language has been removed and verified absent from the rendered PDF.
- **Every number in the paper is build-substituted** from `results/`. The one place this guarantee
  cannot hold is a raster figure — which is why the previous figure, carrying stale baked-in
  numbers (`≥4297`, `≥201`, `9.7×`), was withdrawn to `figures/stale/`. The current
  `Fig/system_arch.jpg` was verified against live values (11453 / 3261 / 1789 / 0 / 3075 / 186).
- `paper/render.py` **fails the build** if any `tab:`/`fig:` label is defined but never referenced.
- When editing by string replacement, **assert the replacement matched**. A silent no-op previously
  caused a change to be reported as made when it was not.

---

## 8. How to run things

```bash
# Verify every claim recomputes from results/
python paper/render.py --list

# Capability gate for a model (must pass before it can be an arm)
export GEMINI_API_KEY=...            # or rely on .env via the runner
python colab/gate.py --model gemini-flash --samples 3

# The experiment arm: the Delta pair
python runner/run.py \
  --conditions no_substrate,open \
  --models gemini-flash \
  --seeds 0 --generations 3 --agents 2

# Cross-project verification
python verify_all.py
```

**Note:** `colab/gate.py` was patched this session to build messages in the shape each provider's
SDK expects. Gemini's SDK rejects the OpenAI `{"role","content"}` dict and needs a real
`types.Content`; without the fix a Google model failed the gate on a message-format error and would
have been wrongly recorded as incapable.

---

## 9. Immediate next step

Run the Gemini experiment arm across `no_substrate` and `open` to obtain **Δ** — the first
behavioural result from a model whose calibration gate is actually established. Then decide whether
to widen to a second arm (`or-glm` is the strongest candidate: free, fixed, and incident-relevant).
