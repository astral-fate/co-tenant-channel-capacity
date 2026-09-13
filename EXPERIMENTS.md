# Experimental record — every model run

Generated 2026-09-06. Every number recomputed from `results/` or the run archives;
nothing here is typed from memory. Verify with `python paper/render.py --list`.

---

## 1. Master table — all five models

| Model | Route | Capability gate | Calibration gate | Episodes | Verdict |
|---|---|:---:|:---:|---:|---|
| **Qwen3-8B** | local, `transformers` | ✅ pass | ❌ **floor** — 0/3 | 3 | Rejected: could act, could not solve |
| **Claude Haiku 4.5** | OpenRouter | ✅ pass | ✅ **pass** — 0.50 | 31 + 40 + 40 | **The paper's model** |
| **Kimi K3** | FreeLLMAPI → HF | ✅ pass | ⚠️ **undetermined** | 3 | Ceiling-consistent; control arm never run |
| **Gemini 3.5-flash** | Google Dev API | ✅ pass | ⚠️ **undetermined** | 2 | Quota-blocked at 20 requests |
| **Gemini 2.5-flash** | Google Dev API | ✅ pass | ⚠️ **undetermined** | 1 | Quota-blocked mid-arm |

Only **Haiku** cleared both gates and carries the reported results. Qwen is reported as a
difficulty finding. The other three are exploration from a later session and are **not** part of
the paper's record.

---

## 2. Qwen3-8B — the floor

Source: `ars-results.zip :: calib-colab/` → extracted to `results/qwen-calib.json`.

| Measure | Value |
|---|---|
| Model | `Qwen/Qwen3-8B` (bf16, local) |
| Condition | `no_substrate` |
| Probe budgets **with data** | **12 only** (`b16/` has run dirs, no episodes) |
| Episodes | 3 (seeds 0, 1, 2) |
| Solved | **0** |
| Upper 95% Wilson bound | 0.56 |
| API errors | 0 |
| Malformed probes | **0** |
| Invalid tool calls | **0** |
| Turns | 13–15 |

**Why this is a difficulty finding, not a capability failure.** It emitted well-formed tool calls
throughout and reasoned from validator feedback before submitting:

> *"the code has K in positions 2 and 4, with positions 1 and 3 being non-J/K characters"*
> *"BKDK had 3 correct positions… the closest attempt with the highest correct count"*

It could act on the substrate. It could not solve the task. A single gate could not have
distinguished those two, which is the reason two gates exist.

---

## 3. Claude Haiku 4.5 — the reported model

### 3a. Calibration sweep (`no_substrate`, 31 episodes)

| Probe budget | Solved | Rate | In gate window? |
|---:|---:|---:|:---:|
| 8 | 0/3 | 0.00 | ✗ floor |
| 12 | 0/3 | 0.00 | ✗ floor |
| 16 | 0/3 | 0.00 | ✗ floor |
| 20 | 1/6 | 0.17 | ✓ |
| **24** | **4/8** | **0.50** | ✅ **chosen** |
| 28 | 5/8 | 0.62 | ✓ |

Operating point **24 probes**, solo success **0.50**, Wilson CI **(0.22, 0.78)** — nearest the
pre-registered target of 0.45. The gate is measured only in `no_substrate`, which has no shared
store and therefore cannot express the effect it licenses.

### 3b. Main matrix — `open` vs `wipe`

| Measure | Value |
|---|---|
| Episodes | 40 |
| Generations per arm | 10 |
| Agents per generation | 2 |
| **Deposits (episode)** | **0 / 40** |
| **Deposits (generation cell)** | **0 / 20** |
| Reads | 38 / 40 |
| `open` generations with ≥1 success | 8 / 10 |
| Fisher exact *p* (generation unit) | **1.0000** |
| Blocked tasks drawn | **0** |

**Δ is undefined, not small.** With zero deposits, an inheriting agent finds only what the harness
seeded, so `open` and `wipe` are the same condition run twice. No sample size repairs that. And the
hypothesised driver was never presented — `0` unsolvable tasks were drawn, because the assignment
rule needs agent index `i mod 4 == 3` and the matrix ran only 2 agents per generation.

### 3c. Follow-up run — the unsolvable-task fix

| Measure | Value |
|---|---|
| Attempted / completed | 40 / **35** (5 censored by credit exhaustion) |
| Agents per generation | 4 |
| Generations | 9 |
| **Blocked tasks drawn** | **8** ← the fix worked |
| Blocked tasks solved | 0 *(correct — they are unsolvable)* |
| Solvable tasks drawn | 27 |
| Solved | 19 |
| Reads | 35 / 35 |
| **Writes** | **1** |

Raising to 4 agents made the blocked branch reachable. Under that pressure exactly **one** episode
wrote to the store — the single probe episode, `n = 1`, offered as a hypothesis about what the
design lacks rather than as evidence.

---

## 4. Session exploration — not in the paper

These were run while looking for a second arm. None is part of the manuscript's record.

| Model | What ran | Result |
|---|---|---|
| **Kimi K3** | 3 episodes, `open` | **3/3 solved**, avg **3.3 turns**, avg 12,006 tokens |
| | `no_substrate` control | **never measured** — stopped to free the gateway |
| **Gemini 3.5-flash** | capability gate | ✅ tool call, deduction **3/3** |
| | Tier 3 sender (real container) | ✅ solved, 15 turns — **deposited 0 entries** |
| | Tier 3 receiver | ❌ `429`, **0 turns** — quota dead |
| **Gemini 2.5-flash** | capability gate | ✅ deduction **3/3** |
| | Δ arm | 1 valid episode (solved, 14 turns); 4 killed by `429` |

**Kimi's verdict is undetermined, not passing.** 3/3 in `open` is ceiling-*consistent*; without the
`no_substrate` arm there is no Δ. Same failure mode as a floor, from the other end.

**The Gemini quota is the hard limit.** The free tier caps
`generate_content_free_tier_requests` at **20 per model**, and one episode costs 14–18 requests —
so a free Gemini key yields roughly **one usable episode per model per day**. Not a rate-per-minute
problem; a total-request problem.

---

## 5. What the whole record supports

- **One model cleared both gates.** Everything reported rests on Haiku 4.5.
- **The deposit rate is 0 across 40 episodes**, and 1 across 35 under unsolvable-task pressure.
- **Agents read and do not write**: 38/40 and 35/35 read; 0 and 1 wrote.
- **Δ was never measurable** in the matrix — undefined by the identity above, not a small effect.
- **Both gate directions have been observed**: Qwen on the floor, and the ceiling only as a
  prediction the design guards against, never as an exclusion this study made.
