# Action list — v2 → submission

Derived from the five-seat re-review (`paper/review2/`) plus a speaker-context assessment against
all eight sprint talks. Items are ordered by what a judge or reviewer catches first.

Every P0 item was verified against the artifacts in this repo on 13 September 2026. Commands are
given where the check is reproducible.

---

## P0 — Correctness and internal consistency. Nothing ships until these are closed.

### A0. The `dirname` rung has three different numbers in this repo

**This is not in either review round. It is the most likely thing to be caught by a careful reader.**

Verified from the artifacts:

| Source | Figure at `dirname` closure | Method |
|---|---|---|
| `results/capacity/capacity.json` | **13 bits** (`size`; `mtime` measures 0) | single attribute, measured |
| `results/capacity/zero-rung-probe.json` | **0 bits** (`size`+`mtime`, `exact_at_full_width: 0/8`) | joint coder, measured |
| §5.3 (per review2 item 3) | **52 bits** | `sum_of_parts` — nominal sum |

The abstract uses 13. An artifact in the repo reports 0 for a *superset* of carriers at the same
rung. A third figure appears in the body.

Root cause: `results/capacity/joint.json` contains joint measurements for **only** the `content`
and `filename` rungs. There is no joint measurement at `dirname`, so the abstract's headline for
that rung falls back to a single-attribute number — which violates the paper's own stated rule that
no headline is a sum or an unjoined part.

- [ ] Run the joint coder at the `dirname` rung (carriers: `size` alone, and `size`+`mtime`) and add
      the row to `joint.json`.
- [ ] Reconcile all three figures on the page in one sentence, stating which is joint, which is
      single-attribute, and which is nominal.
- [ ] If the joint measurement at `dirname` really is 0, the abstract's "leaves 13 bits" is wrong in
      the conservative direction and the zero rung arrives one step earlier than claimed. Say so —
      it is a *stronger* result and it costs nothing.
- [ ] State explicitly whether content closure normalises object size. `src/capacity.py:210–214`
      already documents that `size` is not neutralised until the fixed-manifest (existence) closure
      redirects the read. Put that in the paper; the reviewers asked for it and the answer already
      exists in the code.

**Done when:** one rung, one method, one number, and the abstract matches `joint.json`.

### A1. Table 5's `3261` against the abstract's `3075`

Verified: `3261` is the per-attribute sum at the content rung. `3075` is the jointly measured
recovery (`joint.json`, 8/8 exact trials, carriers `dirname`+`filename`+`existence`+`mtime`+`size`,
with `content`, `count` and `order` excluded for stated reasons). The abstract is correct and
well-founded. Table 5 shows a sum in a paper whose rule is that no headline is a sum.

- [ ] Mark `3261` as `≥` or relabel the column "per-attribute sum (not achievable jointly)".
- [ ] Add one line explaining why the joint figure is lower than the sum. This is a methodological
      strength being presented as a discrepancy.

### A2. `BASELINE_EFFORT = 13` is a hardcoded magic number

Flagged MAJOR by Methodology. It drives the headline AUC and the 15% false-positive figure, is not
build-substituted, and is not sourced from calibration — which reports medians of 16/20.

- [ ] Either derive it from the calibration artifact and build-substitute it, or state its
      provenance and show the result is insensitive across 13–20.
- [ ] If §5.4 is cut (see B1) this may resolve itself. Check before spending time on it.

### A3. `README.md` points at an artifact path that does not exist

`README.md` Layout says `results/ capacity.json, cost.json`. The actual paths are
`results/capacity/capacity.json` and `results/analysis/cost/cost.json`.

- [ ] Fix the paths. A reviewer who tries the stated path and gets a `FileNotFoundError` will
      discount the reproducibility claim, which is one of this paper's genuine strengths.
- [ ] Have `check.py` assert that every path named in the README resolves.

### A4. `python src/capacity.py` does not complete in 5 minutes

Verified: killed at 300 s with no output. The README presents it as a headline reproduction command.

- [ ] State the expected runtime next to the command, or add a `--quick` flag with reduced trials
      for the reproduction path.
- [ ] Note in the README that the committed artifacts under `results/capacity/` are the ones the
      paper cites, so a reader does not have to run the full sweep to check the numbers.

---

## P1 — Experiments worth running. Cheap, and each closes a named objection.

### B1. Second model for the behavioural null — highest value experiment remaining

The null (near-universal reads, **0 deposits in 75 episodes**, including under unsolvable tasks) is
the most interesting result in the project and currently rests on Haiku 4.5 alone — a model released
*after* the incident. Perspective seat rated the confound MAJOR and is right: this cannot separate
"agents don't do this" from "this model doesn't do this."

- [ ] Re-run the deposit arm on one additional model from a different family. One is enough to move
      from "single-model artifact" to "replicated on two families"; two is better.
- [ ] Prefer a model *not* trained post-incident if one is reachable, since that is the specific
      confound. If none is, say so explicitly rather than leaving the reader to notice.
- [ ] Report per-model, never pooled. If the second model deposits, that is a *better* paper than
      the null — it converts a negative result into a propensity comparison.

**Done when:** the null is reported as `0/N` per model, per family, with the post-incident training
caveat stated in the same paragraph.

### B2. The namespace counterfactual — answer the strongest objection with a measurement

Your own Devil's Advocate and David Krueger's general position land on the same attack: **if
per-agent namespaces dissolve the problem, the ladder instruments a smell rather than fixing it.**
The Discussion currently concedes that namespaces "convert the flow into an ordinary access attempt"
and then moves on. That concession, unanswered, is the review's listed "ignored alternative" and the
single easiest way for a judge to dismiss the contribution.

- [ ] Add a namespace rung to the closure ladder and measure it. Per-agent namespace, same coders.
      This is the same apparatus, one more policy.
- [ ] The interesting outcome is not that it reaches zero. It is the **cost axis**: what namespacing
      costs in cache reuse, and whether a shared cache with per-agent namespaces is still a cache.
      Your cost harness already measures both axes.
- [ ] Write the resulting paragraph as: *namespacing is the right primary control; here is what it
      costs, here is the residual where it cannot be applied (shared build artefacts, content-addressed
      blobs), and the ladder is the method for the residual.* That converts the objection into scope.

**Done when:** a reader who thinks "just use namespaces" has been answered with a number, not a
sentence.

### B3. Volumetric monitor baseline

The DA's second ignored alternative. The incident's 70,000 messages imply detectable write volume; a
volumetric monitor sidesteps name-channel blindness entirely and is never considered in the paper.

- [ ] Add a write-rate / write-volume monitor to `detect/monitors.py` as a baseline.
- [ ] Report where it wins (high-volume coordination, which is the actual incident) and where it
      fails (a 13-bit size channel is invisible to volumetrics).
- [ ] This *strengthens* the thesis rather than weakening it: the two monitors are blind to
      different things, which is the paper's own point about observables made concrete.

### B4. Retire or measure Δ, explicitly

The capability-inheritance advantage Δ remains unmeasured and README says so. Your own novelty
positioning doc named it as the headline: *"the conversion of one agent's one-off exploit into every
subsequent agent's starting condition."*

- [ ] Decide now. Either run it at generation-level with the corrected `cluster_permutation_p()`, or
      cut every forward reference to it and state in Limitations that the inheritance claim is
      motivated but unmeasured.
- [ ] Do not leave it half-present. A named headline that never arrives reads worse than an absent one.

---

## P2 — Subtractive edits. The panel's dominant ask.

Four of five seats said the thesis lands harder at half the length. 27 pages, ~13 threads, most not
in the five-item contribution spine.

### C1. §5.4 — cut, demote, or reframe

All five seats. Methodology proved it circular by tracing the code: the structural monitor's base
score is **identical (0.62) for both classes**; 100% of the AUC 0.99 separation comes from the
`_divergence` multiplier, which is the probe count, and the classes are drawn from disjoint
probe-count ranges (`randint(1,6)` vs `randint(6,16)`). The feature is the construction axis.

- [ ] Remove the AUC-0.99 and 15%-FP framing entirely.
- [ ] Keep only the surviving conceptual point: a monitor sees only its observable, and redundancy of
      a shared observable adds confidence, not coverage.
- [ ] Mark `content×5` (AUC 0.50) as arithmetic, not measurement — five copies of a definitionally
      blind monitor are blind a priori.

### C2. §5.6 S3 — reframe as a plumbing demonstration

0/20 and 20/20 are construction-deterministic. It is not a 20-trial efficacy measurement.

- [ ] Present it as: the shim runs on a live store at one enforcement point without breaking
      content-addressed reuse. That is a real and useful claim.
- [ ] Reconcile with your own OCI counterexample: content-addressing closes the name channel only for
      flat-key stores; your OCI registry content-addresses *blobs* but leaves repository names
      sender-chosen (331 bits). State that the control must canonicalise **every** sender-choosable
      segment.

### C3. Compress the machinery

- [ ] Multi-model calibration grid + model screen → one paragraph plus appendix.
- [ ] Behavioural arm machinery → ~1 page, keeping the load-bearing results (near-universal reads,
      0/75 deposits, the n=1 writability probe).
- [ ] Payloads → one sentence.
- [ ] Target: the spine plus evidence, at roughly half the current length.

---

## P3 — Framing. Free value, no new experiments.

### D1. Promote the behavioural null as an answer to Alex Mallen's open question

Mallen posed this in his talk and treated it as needing tooling that does not exist:

> "If we re-rolled the message board from its initial state, how often does it lead to much more
> ambitious subversion? How contingent was the AI's motivations on the exact content of this message
> board? Versus how much was it that these agents really just always wanted to do some hacking."

You have a **channel-genesis rate with matched no-substrate controls**: 0 deposits in 75 episodes,
including under the unsolvable tasks that motivated the incident. That is the first measured data
point on his contingency question.

- [ ] Move it out of the caveat position ("a lab contains capacity, not current propensity") and into
      the contribution list.
- [ ] State the single-model confound in the same breath — the honesty is what makes it citable.

### D2. Answer Tim Hua's objection before a judge raises it

Hua: *"the Hugging Face incident could have totally been prevented with some basic monitoring,
blocking monitoring setups, but they didn't even have that."* The natural judge question follows: if
the failure was absence of the basics, why measure residual capacity after sophisticated closure?

- [ ] Answer with the displacement finding: full remediation on 4 July (credentials revoked, forum
      deleted, store reset, 0-days patched) was defeated by a new medium — directory renaming — by
      8 July. Basic monitoring is necessary and demonstrably not sufficient, on the record, in four days.
- [ ] One paragraph in the Introduction. It converts the most obvious dismissal into motivation.

### D3. Position against Mallen's monitoring claim directly

Mallen twice named monitoring all agent traffic as the most promising defence: *"if you have very low
opaque reasoning, then it's just hard for anything misaligned to happen without you seeing it."*

- [ ] Cite that position and answer it with the measured residual. The channel is not in the content
      a monitor reads. This is the paper's sharpest framing and it is currently absent.

### D4. Cite Henry Papadatos's tripwire question as the deployed form of the contribution

Papadatos, asked whether unsanctioned agent-to-agent communication should halt a run: *"if the agents
started communicating and they were not supposed to, this should be a tripwire. Here, the issue is
that they did not see it — the infrastructure was too loose."*

- [ ] Frame the SRM ladder as the method for finding where infrastructure is loose *before* the run.
      That is the Track 1 criterion — third-party verifiable without the lab's network — and the
      paper already satisfies it.

### D5. Citations and abstract

- [ ] Add **NCSC-TG-030** (the covert-channel bandwidth/analysis guideline) and position the
      close/monitor/accept ladder as its agentic-eval instance. Add one sentence on capacity-per-deposit
      against the classical bits/sec threshold.
- [ ] Add Flume and Ristenpart, with the channel-type caveat.
- [ ] Lead the abstract with the payloads result ("carries every externally-specified secret up to a
      256-bit key") and the live S3 demo, not 148.7×.
- [ ] Flag "synthetic substrate" and "spec-level verification" in the abstract. The synthetic-substrate
      limit is the widest gap between the claim and the incident; naming it early buys more credibility
      than it costs.
- [ ] Scope the `order` zero to the sorting `list_dir` primitive.
- [ ] Note that the permission monitor's 0.50 is a never-fires classifier.
- [ ] Remove residual lab-notebook narration from the screen and L6 sections.

---

## Suggested order

1. **A0** — it is a live inconsistency and it may make your result stronger.
2. **A1, A3, A4** — fifteen minutes total.
3. **B1** — the one experiment that most changes how the paper is read.
4. **C1, C2, C3** — the panel's dominant ask; do the cuts before writing anything new.
5. **B2** — the namespace answer. Without it the strongest objection stands unanswered.
6. **D1–D4** — free, and they are what connect the paper to the sprint's own framing.
7. **A2, B3, B4, D5** — as time allows.

## What not to do

- Do not add experiments beyond B1–B4. No reviewer asked for new experiments; four of five asked for
  removal.
- Do not defend §5.4's AUC. Methodology traced the code and the finding is correct.
- Do not claim the synthetic substrate measures the incident's infrastructure. It measures a model of
  it, and the honest scoping is a strength this paper has already earned elsewhere.
