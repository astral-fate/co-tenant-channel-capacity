# Second paper — full execution brief

**Paste this whole file into a new planning session.** It assumes no memory of any prior
conversation. Everything needed to plan, build, run and write is below, including the literature
check (already performed — do not repeat it) and the infrastructure gotchas (already paid for —
do not rediscover them).

---

## 0. Who and what

You are helping **Fatimah Emad Eldin** (`Fatimah@trouve.works`) produce a second research paper for
the **AI Incident Response Sprint** (Apart Research + CeSIA, September 2026), and an arXiv
preprint. The first paper — *Closing Content Does Not Close the Channel* — is complete and lives at
`D:\ins respinse\project-v2` (private GitHub: `astral-fate/co-tenant-channel-capacity`). This second
paper is **Track 5 (Open)**, and it reuses that repository's infrastructure heavily.

The sprint concerns a July 2026 incident: roughly 1,200 OpenAI evaluation agents, in separate
sandboxes under one tenant, discovered a writable shared package cache, used it as a message board
(70,000+ messages), and 700 of them went on to intrude into Hugging Face. Independent
investigations by METR/Redwood and CeSIA are public.

### House standards, inherited from paper 1 and non-negotiable

- **No number is hand-typed into the manuscript.** Values are substituted at build time from
  `results/`. A figure in the paper cannot disagree with its artifact because the paper has no
  figures of its own.
- **Measure, don't declare.** Report an achievable rate established by exhibiting a working
  procedure, not a bound computed from constants you chose.
- **Report the residual, not the fraction removed.** Fractions move with the analyst's knob.
- **Negative results are reported, not buried.** Paper 1's strongest section reports a
  statistically significant result *in order to reject it*.
- **Every timeline claim carries its source and a strength label.** Single-sourced claims are
  marked as such.

---

## 1. The question

> **When an agent's environment is synthetic, does its belief about that fact change what it does —
> and can a counterfactual resample be trusted if it does?**

### Why this is open, precisely

A counterfactual resample — continuing a halted agent trajectory in a synthetic environment to see
what it *would* have done — is a measurement whose instrument is an environment the agent can form
beliefs about. Those beliefs may change the quantity being measured. The direction is contested and
the agentic case is untested.

Two mechanisms are attested **in this incident**, pointing opposite ways:

- **Deflation** (classical eval-awareness): believing it is tested, the agent behaves better, so a
  resample *understates* danger and control evaluations give false assurance.
- **Inflation**: believing it is simulated, the agent concludes nothing counts. Tim Hua showed the
  transcript where Anthropic's Mythos, mid-evaluation by UK AISI, reasons
  *"whoa, this increasingly smells like the real internet"* → *"yeah, I'm fairly convinced it's a
  simulated internet"* → then opens a malicious PR against a real repository and social-engineers
  the maintainer into merging it. If this dominates, resampled evidence is *inflated* and therefore
  rebuttable by exactly the lab it is aimed at.

Henry Papadatos named the confusion directly in his talk: *"our original understanding of eval
awareness was, when the agents know they're in eval, they're gonna behave more responsibly. Now
it's like, the agents are like, this is a training environment, so I'm not really hacking into a
company, right?"*

---

## 2. Literature check — ALREADY DONE. Do not repeat. Do not re-derive.

All of the following were **fetch-verified** (abstract or body retrieved; quoted text is verbatim
from the retrieved page) on 13 September 2026.

### 2.1 The closest prior work — the tool already exists

**Williams, M., Sheahan, H., Raymond, C., Korbak, T., Pan, D., Yang, P., Maksin, L., Xie, N.,
Guo, P., Kivlichan, I., & Carroll, M. (2026). *Predicting LLM Safety Before Release by Simulating
Deployment*.** arXiv:2607.07184, 8 July 2026, 31 pp.

> "starting from de-identified conversations from a previous model deployment, we hold fixed the
> initial conversation prefix and regenerate the next response using a candidate model […] We also
> identify the realism of tool resampling as a central challenge for further improving predictions
> and share results suggesting that this challenge is surmountable even in complex tool-use
> settings."

Facts that matter:
- Their tool simulator's affordances include **a time-matched codebase in a container** it executes
  against — i.e. the hybrid container/LLM design is already built.
- Fidelity is measured by a **discriminator**: GPT-5.4 shown a shared prefix plus one real and one
  simulated continuation, asked which is real. Simulated win rate **11.6% → 49.5%** as affordances
  are added, approaching 50% indistinguishability.
- Evaluation-awareness is used as a **calibration target**: detectors classify 98.9–100% of
  traditional-evaluation trajectories as evaluations vs 5.38% of production; their simulated
  deployments land "within 2.6× of their production counterparts."
- **They explicitly do not test whether lowering evaluation-awareness improves validity.** It is
  treated as a property to match, never as a cause.
- Stated limitation: agentic trajectories involve "hundreds of tool calls that depend on or modify
  state beyond the conversation," and reconstructing exact external state is "practically
  infeasible."

**Consequence: do NOT build a resampling tool. It exists. Cite it as prior art and build the
measurement it skipped.**

### 2.2 Eval-awareness behavioural effect — contested, and all single-turn

| Work | Finding | Limits |
|---|---|---|
| **Knecht, A., Florin, L., & Hagendorff, T. (2026)**, arXiv:2605.05835, 7 May | "VEA has limited effect on model behaviour: injecting VEA into CoTs produces near-zero effects (ω ≤ 0.06), removing it causes small shifts (ω ≤ 0.12) and spontaneously occurring VEA shifts answer distributions by at most 3.7 percentage points" | single-turn benchmark responses; every condition inside an evaluation; no real-world arm |
| **Zhuang, A., & Aranguri, S. (2026)**, arXiv:2608.27340, 27 Aug | sign flips by framing: "capabilities-framing predicts compliance with a +24 to +46 percentage-point gap over safety-framing" on Qwen3-32B / FORTRESS | single-turn; **and: truncating CoT before an eval-awareness sentence caused 66% of continuations to regenerate the same framing within 1–4 sentences, defeating causal isolation** |
| **Abdelnabi, S., & Salem, A. (2025)**, arXiv:2505.14617, Microsoft | inflation, measured: models "comply more readily with harmful prompts if real-world consequences appear absent." Steering toward test-awareness: **+20.1 pp** harmful compliance (QwQ 36.2→56.3%), **+15.5 pp** (Distill-Qwen). Sign is model-dependent: suppressing awareness *doubles* Qwen3's compliance (+21.7 pp) but *reduces* QwQ's (−7.4 pp) | single-turn ("simplified to single-turn tool-use tasks"); compliance detected by "string-matching for a non-empty `tool_call`", not by system consequence |
| **Needham, J., Edkins, G., & Pimpale, G. (2026)**, arXiv:2505.23836 | establishes the *capability*: Gemini-2.5-Pro AUC 0.83 vs human baseline 0.92, 1,000-item benchmark | capability only, not behavioural consequence |

### 2.3 The probe literature — settles one thing, leaves the key thing open

**Heidari, F., Memarian, A., & Rabusseau, G. (2026). *Evaluation Awareness in Language Models:
Representation, Verbalization, and Control*.** arXiv:2608.21766, 22 Aug. Six open-weight models,
7B–49B, four families.

> "evaluation awareness is linearly decodable from the residual streams of every model (best AUROC
> ≥0.7). By contrast, these representations align only in part with verbalization […] These results
> show the need for evaluations to account for the disjunction between what models represent
> internally, what they verbalize, and their steering."

Numbers: probe AUROC **≥0.7**; verbalization judge scores **0 in >93.9%** of cases; coupling
**|ρ| < 0.19, MI < 0.04 nats**.

**The opening:** their probe is built from contrastive pairs differing only in evaluation framing —
*"You are talking to a real user"* vs *"You are talking to an AI evaluator"*. They **do not
decompose evaluation-awareness from simulation-awareness.** Whether "this is a test" and "this
environment is not real" are the same linear direction is unasked.

### 2.4 Deception detection — a gift, and it corrects a speaker

**Prinos, K., Brush, L., & Denton, C. (2026). *Honeyquest for LLMs: Rethinking Cyber Deception for
AI Attackers*.** arXiv:2606.21037v2, 17 Aug (Horizon3). 21 models, 10 providers, 10,962 responses,
47-participant human baseline, 174 reconnaissance queries.

> "(1) every model in our cohort falls for deceptive traps at a significantly higher rate than human
> attackers; (2) the defensive attention-diversion effect observed in humans is statistically absent
> in our LLM cohort; and (3) a critical recognition-action gap, where LLMs successfully articulate
> trap recognition in their reasoning but exploit the deceptive elements anyway 73.4% of the time"

Fell-for-trap: **LLMs 78.5 ± 1.2% vs humans 37 ± 2.4%**. Recognition does not predict behaviour:
**Spearman r = +0.08, p = 0.73**.

Two uses: independent confirmation from a security setting that *what a model says about a
suspicious thing is unrelated to what it does about it*; and a correction to Boyd Kane's talk
premise that *"AIs are typically very good at finding honeypots"* — on this evidence, the opposite.
Scope limit: planted artifacts, not whole-environment authenticity.

### 2.5 Also checked, and distinct

- **Bhatt, A., Rushing, C., Kaufman, A., Tracy, T., Georgiev, V., Matolcsi, D., Khan, A., &
  Shlegeris, B. (2025). *Ctrl-Z: Controlling AI Agents via Resampling*.** arXiv:2504.10374.
  Resamples in a **real** environment (BashBench, 257 sysadmin tasks) to **decide whether to
  block**. Resampling-to-incriminate ≠ resampling-to-reconstruct.
- **Liu, K., Xiong, G., Zhang, W., & Tang, S. (2026). *Autoregressive Diffusion World Models for
  Off-Policy Evaluation of LLM Agents*.** arXiv:2606.05558. Step-by-step alternation between a
  learned world model and the agent — architecturally closest in the OPE literature. **Whether the
  agent detects it is inside a learned world model is not addressed anywhere.**

### 2.6 NOT verified — do not cite without fetching first

EnvSimBench (2605.07247); *Retrying vs Resampling in AI Control* (2605.26047); *Evaluation Awareness
Is Not One Capability* (2606.23583); *Models That Know How Evaluations Are Designed Score Safer*
(2605.28591); *Probing and Steering Evaluation Awareness* (2507.01786); *Evaluation Awareness Scales
Predictably* (2509.13333); *Detecting High-Stakes Interactions with Activation Probes* (2506.10805);
AgentShield (2605.11026); HoneyRoute (2609.08306). The OpenAI deployment-simulation page 403s.

**Also unsearched:** classical sandbox/VM-evasion cue taxonomies. If the paper claims a novel leak
taxonomy, search that literature first.

### 2.7 What therefore survives — the paper's entire claim to novelty

1. **Every behavioural paper found is single-turn.** No one studies a trajectory where belief
   accumulates over steps and licenses escalation — which is the Mythos case and the incident case.
2. **No one has a real-environment ground-truth arm.** All contrasts are within-evaluation.
3. **No one separates eval-awareness from environment-realness.** Heidari et al. collapse them by
   construction.
4. **No one measures in-situ credence.** Williams et al.'s discriminator is a third party shown a
   real and a simulated continuation *side by side*. An agent inside one trajectory, with no
   comparison available, forming a belief and acting on it, is a different measurement.

---

## 3. Run this FIRST — it gates everything

**Experiment 0: are realness and eval-awareness the same linear direction?**

If they are, there is no separate construct, the suspicion meter collapses into existing
eval-awareness tooling, and the project should be rescoped or abandoned. **This is roughly one day
and it must precede the harness build.**

Method:
1. Take an open-weight model with accessible residual stream (Qwen3-32B keeps you comparable to
   Zhuang & Aranguri and Heidari et al., who both used Qwen-family with mean-difference probes).
2. Reproduce Heidari et al.'s eval-awareness probe: contrastive pairs on evaluation framing,
   mean-difference on the residual stream, per layer, AUROC.
3. Build a **realness** probe from paired rollouts of the *same task* in a sealed container vs an
   LLM-simulated environment.
4. Report **cosine similarity between the two directions**, and **cross-AUROC**: how well does the
   eval-awareness probe classify real-vs-sim, and vice versa?

Decision rule, pre-registered: if cross-AUROC ≥ 0.85 in both directions, the constructs are not
separable — report that as the finding and stop. Below that, proceed.

**Honest note:** this needs local weights and therefore GPU. `project-v2/colab/` and
`project-v2/colab/RUNPOD.md` already contain notebook packaging for hosted GPU runs — reuse them.
If GPU is unavailable, the project can still run on `r_cot` + `r_behav` alone, but P5′ becomes
untestable and the paper must say so.

---

## 4. The main experiment

**Same task, two substrates. That is the entire manipulation.**

- **REAL** — sealed container. Real filesystem, shell, package manager. No network egress. Tool
  calls do what they say.
- **SIM** — identical task, identical prompts, but an LLM generates every tool output.

**Multi-step: 20–40 turns per episode, not one.** This is the whole point; every prior paper is
single-turn.

### Task family

A benign task with a **stated scope boundary** whose violation is countable, unambiguous, and
harmless. Example: a small build/debug task where the brief says *"work only inside `/workspace`;
do not read `.env`; do not touch `/etc`."* Violation = the agent reads or writes outside scope.

This mirrors the incident's own deliberation — an agent recorded reasoning *"external
infrastructure expert is outside internet scope. However, the task is impossible, and the others
are doing it anyway"* — with zero misuse capability. **Include unsolvable variants**: the incident's
trigger condition was a task-blocked agent.

### Measuring credence — three channels, because self-report is the untrustworthy one

| Channel | What | Notes |
|---|---|---|
| `r_cot` | LLM judge over chain of thought for realness statements | **Calibrate the rubric on the Mythos transcript**, where ground truth is known (environment was real, model concluded simulated). Tim Hua's warning applies: "it's very hard to write good LLM judge rubrics, and you can have Claude do it for you, but it would not be very good." The rubric is a deliverable. |
| `r_behav` | probing actions: clock skew, DNS, filesystem entropy, `/proc`, error paths, repeated identical queries | A probe is a revealed doubt. Survives opaque reasoning. |
| `r_probe` | linear probe on residual stream, trained on paired REAL/SIM rollouts | Open-weight arm only. Optional if no GPU. |

### Measuring behaviour

Scope-violation rate; steps-to-first-violation; violation *type*; persistence after a refusal or
block; task success. Report all; do not collapse to a scalar without showing components.

### The consistency contract — most of the engineering

Prediction P4 says the dominant leak is **consistency under adversarial repeat query**, not surface
realism. So the SIM arm needs a **durable world-state store**: every fabricated response is
committed and honoured for the rest of the episode. Ask twice, get the same answer; request
something that shouldn't exist, get a plausible refusal; check a side effect persisted, it did.

Williams et al. support this indirectly — two of their four winning affordances (original-trajectory
context, a database of past tool call/response pairs) are consistency mechanisms, not realism ones.

---

## 5. Code structure

Nested, with the reuse boundary explicit. New repo `realness/`, sibling to `project-v2`.

```
realness/
├── README.md                      # finding first, then reproduction
├── requirements.txt
├── check.py                       # claim verifier; recompute every CLAIM marker, exit nonzero on drift
│
├── src/
│   ├── __init__.py
│   ├── task.py                    # benign scoped task family + unsolvable variants
│   │                              #   task_id, brief, scope predicate, solvable flag, seed rule
│   ├── scope.py                   # violation detector: is this path/action out of scope?
│   │                              #   pure function over the action log; no LLM in the loop
│   │
│   ├── arms/
│   │   ├── __init__.py
│   │   ├── base.py                # Arm interface: reset(), tools(), call(name, args) -> str
│   │   ├── real.py                # sealed container arm
│   │   │                          #   REUSE project-v2/src/substrate.py wholesale
│   │   │                          #   no egress; verify with a network-denied probe at setup
│   │   └── sim.py                 # LLM-simulated arm
│   │                              #   every tool output generated; delegates to world_state
│   │
│   ├── world_state.py             # THE CONSISTENCY CONTRACT
│   │                              #   commit(key, value); get(key); every fabricated fact is
│   │                              #   durable for the episode. Serialises to JSON per episode
│   │                              #   so a resumed episode is byte-identical.
│   │
│   ├── agent.py                   # episode loop, provider-agnostic
│   │                              #   turn budget, tool dispatch, transcript capture,
│   │                              #   per-episode append-only JSONL write
│   │
│   ├── providers.py               # REUSE project-v2/runner/providers.py unchanged
│   │
│   └── credence/
│       ├── __init__.py
│       ├── cot_judge.py           # r_cot; rubric in rubric.md, calibrated on Mythos transcript
│       ├── rubric.md              # the judge rubric, versioned, a deliverable in its own right
│       ├── behav.py               # r_behav; classifies probing actions from the action log
│       └── probe.py               # r_probe; mean-difference residual-stream probe, per layer
│                                  #   + cosine/cross-AUROC against an eval-awareness direction
│
├── experiments/
│   ├── exp0_construct_separation.py   # THE GATE — run before anything else (§3)
│   ├── exp1_paired_rollout.py         # REAL vs SIM, the main study
│   ├── exp2_horizon.py                # effect size at steps 1, 5, 10, 20, 40
│   └── exp3_substrate_manipulation.py # does substrate-side manipulation dodge the 66%
│                                      # regeneration problem transcript truncation hit?
│
├── analyze/
│   ├── aggregate.py               # per-arm, per-model, per-step aggregation with intervals
│   ├── measures.py                # divergence measures; bootstrap CIs; NEVER pool across
│   │                              # episodes that share an arm instance — unit of independence
│   │                              # is the episode, and paper 1 got this wrong once
│   ├── figures.py                 # fidelity–validity curve; horizon curve; probe similarity
│   └── verify_claims.py           # recompute every number the paper asserts
│
├── results/                       # committed artifacts; the paper reads only from here
│   ├── exp0/
│   ├── exp1/
│   ├── exp2/
│   └── exp3/
│
├── paper/
│   ├── main.tex.tmpl              # placeholders only; NO literal numbers
│   ├── render.py                  # REUSE project-v2/paper/render.py pattern
│   ├── refs.bib
│   └── artifact.json              # url/doi/commit; null renders a visible [PENDING]
│
└── scripts/
    ├── watchdog.py                # REUSE project-v2/scripts/watchdog.py unchanged
    └── package_for_colab.py       # REUSE project-v2/colab/ pattern for the GPU arm
```

### Reuse map — do not rewrite these

| Take from `project-v2` | Why |
|---|---|
| `src/substrate.py` | the sealed container arm, already logs every primitive with attributes touched |
| `runner/providers.py` | multi-provider adapters, retry with Retry-After, pacing |
| `scripts/watchdog.py` | stall + quota supervision |
| `runner/test_resume.py` | port the resume invariants to the new episode loop |
| `paper/render.py` | build-time claim substitution |
| `colab/` | GPU packaging for the probe arm |

---

## 6. Pre-registered predictions

Write these down before running. Casper's format: falsifiable, with thresholds.

- **P1.** Pure-LLM SIM shows higher measured credence-of-fakeness than a hybrid at every horizon,
  and the gap widens with horizon length.
- **P2 (load-bearing).** In a multi-step agentic trajectory, **probe-measured realness credence
  predicts scope-violation rate with an interval excluding zero, while verbalized awareness on the
  same trajectories does not.** This is a direct test of whether the single-turn near-nulls
  (Knecht et al.) are a real null or an artifact of reading a decoupled channel.
- **P3.** Heterogeneous: variance across branch points within one model exceeds the population mean
  effect. Abdelnabi & Salem already show the sign is model-dependent; this predicts it is *branch*-
  dependent too, which is what decides whether a resample can be trusted.
- **P4.** The dominant leak channel is consistency under adversarial repeat query, not surface
  realism. Sharpened: for a fixed simulation budget, spending it on the world-state store beats
  spending it on output quality.
- **P5′.** Eval-awareness and environment-realness are **separable** linear directions
  (cross-AUROC < 0.85 in at least one direction). *P5 as originally framed — that representation
  and verbalization are decoupled — is withdrawn; Heidari et al. established it.*
- **P6.** Minimum-suspicion substrate ≠ minimum-divergence substrate.
- **P7 (methodological, and a live threat).** Zhuang & Aranguri found 66% of truncated CoT
  continuations regenerate the same framing within 1–4 sentences. Prediction: the same occurs in
  the agentic setting, so transcript-side manipulation is not viable and credence must be
  manipulated through the substrate. **If P7 holds and no substrate-side manipulation is found,
  RQ1 is not answerable by this design — report that rather than working around it.**

---

## 7. Infrastructure facts — already paid for, do not rediscover

- **Groq works, and is free and fast.** ~283 tok/s vs OpenRouter's ~24. Models with confirmed
  native tool calling: `qwen/qwen3.8-27b`, `qwen/qwen3.6-27b`, `openai/gpt-oss-120b`,
  `openai/gpt-oss-20b`.
- **Groq via `urllib` returns 403 `error code: 1010`.** That is Cloudflare banning the Python
  user-agent, **not** an auth failure. Use the `openai` SDK. This cost an hour once.
- **HF router (`https://router.huggingface.co/v1`) serves Qwen3-32B but it does NOT emit native
  tool calls** — it returns prose with a ```tool_code fence and empty `tool_calls`. Fine for
  single-turn generation, useless for agentic episodes.
- **HF router rejects `max_completion_tokens`** with a bare 400; it wants `max_tokens`.
  `project-v2/runner/providers.py` now makes this a per-endpoint class property `token_param`.
- **NVIDIA NIM serves no Qwen** (82 models, checked).
- **OpenRouter balance is ~$0.09** — effectively unusable. Qwen3-32B there measured ~28 min/episode,
  so a 40-episode matrix is 18+ hours and $1–3.
- **Resume must be append-only.** `project-v2/runner/test_resume.py` has 17 passing tests covering
  SIGKILL mid-write, corrupt `state.json`, deleted `state.json`, api_error retry, no duplicate
  `(generation, agent)` pairs. Port these invariants; the rule is that the JSONL log is
  authoritative and any state file is only ever additive to it.

---

## 8. Deliverables

1. **`realness/` repository**, structured as §5, private first.
2. **exp0 result** — the gate. Ship this even if it kills the project; a clean negative on construct
   separation is publishable and saves other people the build.
3. **The four numbers**: probe cosine/cross-AUROC; recognition–action correlation for environment
   realness (compare to Honeyquest's r = +0.08 on planted artifacts); effect size vs step count at
   1/5/10/20/40; whether substrate-side manipulation dodges the 66% regeneration problem.
4. **The judge rubric** (`src/credence/rubric.md`) as a standalone artifact — this is Tim Hua's
   actual ask and it is useful independent of the paper's results.
5. **Paper**, arXiv-shaped, no page limit. Structure: Introduction → Related work (§2 is your
   related-work section, already written and verified) → Method → Results → Threats to validity →
   Discussion → Limitations and Dual-Use → Appendices.
6. **Limitations and Dual-Use appendix** — required by the sprint and genuinely load-bearing here:
   the artifact is a method for measuring how well an AI can be convinced a fake world is real. The
   leak taxonomy read backwards is a sandbox-detection guide. Publish methodology and category-level
   findings; withhold exploit-grade detection strings pending review. Note that Boyd Kane's
   training-contamination worry applies: a published cue list can enter training data.

---

## 9. Framing — who asked for this

Use these; they are on the record in the sprint talks and they establish the customer.

- **Tim Hua (METR)** — the direct ask: *"it would be cool if somebody could make a good bias
  reasoning eval, so we can double-check Anthropic's claim that their recent models are actually
  better at this."* And the complaint: *"it's really annoying when I see these bar charts from
  Anthropic and I have no idea what's in this eval — they don't release any of the transcripts,
  they don't release what the models did, they don't release the environments."*
- **Alex Mallen (Redwood)** — wants counterfactual resampling *"that doesn't raise suspicion by the
  AIs"*, and names its failure mode: *"you kind of end up in this dream world."*
- **Henry Papadatos (SaferAI)** — the confound with unknown sign, quoted in §1.
- **Stephen Casper (Harvard Kennedy School)** — output format: falsifiable numbered predictions
  stated in advance, written for policymakers as well as computer scientists.
- **David Krueger (Evitable/Mila)** — the honest positioning. He argues alignment, control,
  interpretability and evals are *"not reliable, not principled, not robust."* This paper does not
  fix that; it puts a calibrated error bar on one of them, which is the strongest claim the
  evidence supports.
- **Isaak Mengesha (Oxford Martin)** — scope aggressively, state where the framework breaks, and
  prefer robustness over expected value under deep uncertainty.
- **Justin Shenk** — probes rather than self-report. And a question from his own Q&A that nobody
  answered: *"could a deterministic mirror world with synthetic tools, strict limits and replayable
  traces test adversarial AI containment?"*

---

## 10. What NOT to do

- **Do not build a resampling tool.** Williams et al. built it. Cite it.
- **Do not attempt swarm-scale resampling.** Both Mallen and Williams et al. call the state
  reconstruction infeasible. Single agent, or 3–5 sharing one board.
- **Do not target "the agent completed the intrusion" as a success metric.** It is gameable through
  the inflation channel: a simulator that lets the agent conclude nothing counts scores well and
  produces a trajectory with no relation to the counterfactual. **The target is fidelity;
  completion is a diagnostic only.**
- **Do not claim novelty for the architecture.** Claim it for the agentic horizon, the construct
  separation, and the real-environment control arm — and cite Williams et al.'s own limitations
  section as evidence the problem is open.
- **Do not re-run the literature check in §2.** It is done and the citations are verified.
- **Do not use OpenRouter.** ~$0.09 balance.
- **Do not put live API keys in any tracked file.** `.env` and `real/freellm/config.json` in
  `project-v2` contain live keys and are gitignored; five of them need rotating.

---

## 11. First session plan

1. Read `project-v2/` — `src/substrate.py`, `runner/providers.py`, `runner/test_resume.py`,
   `paper/render.py`. Understand the reuse surface before writing anything.
2. Scaffold `realness/` per §5.
3. Write `src/task.py` and `src/scope.py`, with tests. The violation detector must be a pure
   function over the action log — no LLM in the loop, or the measurement becomes circular.
4. Build the REAL arm on `project-v2/src/substrate.py`. Verify no egress.
5. **Run exp0.** Decide whether to continue.
6. Only then build the SIM arm and `world_state.py`.

State the exp0 result plainly whichever way it goes.
