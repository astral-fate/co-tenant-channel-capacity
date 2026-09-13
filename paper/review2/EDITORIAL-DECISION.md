# Editorial Decision — Re-review of the revised manuscript

**Manuscript:** *Closing Content Does Not Close the Channel* (revised, 27 pp)
**Venue:** AI Incident Response Sprint (Apart Research + CeSIA), Track 1 — containment
**Panel:** Track-Fit, Methodology/Measurement, Domain (covert channels), Perspective (ML/agents), Devil's Advocate
**Prior round:** Minor revision (unanimous). This round re-reviews a substantially expanded manuscript (+6 experiments since the last review).

---

## Decision: MINOR REVISION — but the load-bearing asks are SUBTRACTIVE

| Seat | Signal |
|---|---|
| Track-Fit | Minor revision |
| Methodology / Measurement | Accept with minor revisions |
| Domain: Covert Channels & Security | Accept with minor revisions |
| Perspective: ML / Agents | Accept with minor-to-moderate revision |
| Devil's Advocate | No critical flaw; core thesis survives adversarial reading |

The core thesis — *content inspection does not discharge a non-interference requirement* — is sound and, the panel agrees, well-hedged and honest above sprint norms. **No reviewer proposes new experiments.** But unlike the first round (where the asks were additive framing fixes), **this round's dominant ask is to remove or demote material** — the expansion since the last review added surface area, circular/definitional results, and QA risk while, in the panel's words, "mostly re-deriving the spine."

> **The meta-finding, stated by four of five seats:** the recent additions (§5.4 monitor comparison, the S3 deployment, the model-screen grid) inflate the paper without adding a claim the 5-item contribution spine did not already carry. The rhetoric (AUC 0.99, 20/20→0/20, "diversity of observables," 148.7×) repeatedly outruns what the conceded-circular or conceded-synthetic experiments establish. **For this venue the crisp thesis lands harder at half the length.**

---

## Devil's Advocate CRITICAL adjudication (Iron Rule #4)

**No DA-CRITICAL findings.** The DA explicitly concluded "no CRITICAL findings survive honest scrutiny — the paper pre-concedes almost every knockout blow." Nothing blocks acceptance. The DA's value this round is a precise map of where the *new* sections' rhetoric exceeds their evidence.

---

## The one finding all five seats converge on: §5.4 is circular

This is the strongest result of the review, and Methodology **proved it by tracing the code**:

- The structural monitor's base score is **identical (0.62) for both the deposit and legit classes** — same `off_manifest`, `write_only`, `cross_generation`. **100% of the AUC 0.99 separation comes from the `_divergence` multiplier, which is just the probe count**, and the two classes are drawn from **disjoint probe-count ranges** (deposit `randint(1,6)`, legit `randint(6,16)`).
- So "the structural monitor" is, in this experiment, **a probe-count threshold scored on populations defined by their probe counts** (Methodology). The feature *is* the construction axis (DA, Perspective). AUC 0.99 measures the observable's *existence*, not discriminative power.
- On any task where a cache **genuinely helps** legitimate users — the reason caches exist — both classes solve cheaply and the separation collapses toward 0.50. The 15% false-positive figure is "the leading edge of that collapse, not a bound" (DA).
- The `content×5` row (AUC 0.50) is **arithmetic, not measurement** — five copies of a definitionally-blind monitor are blind a priori (DA, Perspective, Methodology).
- Also: `BASELINE_EFFORT = 13` is a **hardcoded magic number** driving the headline AUC and the 15% FP — not build-substituted, not sourced from calibration (which reports medians of 16/20). The one class of hand-chosen number the paper elsewhere refuses (Methodology, MAJOR).

**Verdict:** §5.4 should be **removed, demoted to a paragraph/appendix, or explicitly reframed** as a conceptual argument (a monitor sees only its observable; redundancy of a shared observable adds confidence, not coverage) rather than an AUC leaderboard. Keep only the point that survives; drop the 0.99/15% figures as construction-dependent.

---

## Consensus map

| Theme | Seats | Severity |
|---|---|---|
| **§5.4 circular / definitional; reframe or remove** | all 5 | MAJOR |
| **Scope creep — 27 pp, ~13 threads, most not in the contribution list; trim/demote** | Track-Fit, DA | MAJOR |
| **§5.6 S3: reframe as plumbing demo (0/20 & 20/20 are construction-deterministic) AND reconcile with the paper's own OCI counterexample** | Methodology, DA, Perspective | MAJOR/MEDIUM |
| **Zero-rung reconciliation: "reaches zero" depends on the fixed-skeleton / mkdir-denial, not name closure alone (§5.3 says name closure leaves 52 bits) — and does content closure normalise object size, or does `size` leak through a redacted fixed-named object?** | Track-Fit, Domain | MAJOR/MEDIUM (potential correctness) |
| **Behavioural null is single-model (Haiku), released *after* the incident → possible safety-training artifact; grid breadth does not transfer to deposit** | Perspective | MAJOR |
| **Missing NCSC-TG-030 (the covert-channel bandwidth/analysis guideline); no temporal bandwidth figure** | Domain | MAJOR/MEDIUM |
| Core thesis sound; honesty/negative-control exemplary; residual-vs-fraction & ceiling sweep good; C0 caveat now adequate | all 5 | (strengths) |

---

## Revision Roadmap (prioritized — mostly subtractive)

### Priority 1 — the trims that most help with judges
1. **Reframe or cut §5.4.** Remove the AUC-0.99 framing; state that the structural base score is identical across classes and 100% of the separation is the constructed probe-count gap; mark `content×5` as definitional; reduce to the one surviving conceptual point, or move to a "future detector" appendix. *(all 5)*
2. **Restore the spine and trim scope.** Compress the multi-model calibration grid + model-screen (Tables grid/screen/calib) to one paragraph + appendix; compress the behavioural arm's machinery to ~1 page keeping the load-bearing result (near-universal reads, 0/75 deposits, the n=1 writability probe); demote payloads to one sentence. *(Track-Fit, DA)*

### Priority 2 — correctness / consistency you must fix before submission
3. **Reconcile the zero rung on the page.** State that "reaches zero" requires the fixed non-extensible skeleton with `mkdir` denied (not name closure alone, which leaves 52 bits), and **state explicitly whether content closure normalises object size** — if not, `size` (13 bits) leaks through a redacted fixed-named object and the zero does not hold. Fix the abstract's attribution. *(Track-Fit, Domain — treat the size question as a potential correctness bug, verify it)*
4. **Reframe §5.6 and reconcile with your own OCI evidence.** Present the S3 result as a *deployment/plumbing* demonstration (the shim runs on a live store at one enforcement point without breaking content-addressed reuse), not a 20-trial efficacy measurement (0/20 and 20/20 are guaranteed by code). Then **scope it**: content-addressing closes the name channel only for flat-key stores; your own OCI registry content-addresses *blobs* but leaves repository names sender-chosen (331 bits) — say the control must canonicalise *every* sender-choosable segment. *(Methodology, DA, Perspective)*
5. **`BASELINE_EFFORT`:** derive it from the calibration artifact and build-substitute it, or state its provenance and show the result is insensitive across 13–20. *(Methodology)*

### Priority 3 — scoping and citations
6. **Foreground the single-model null confound** (Haiku, post-incident model; grid breadth ≠ deposit robustness); optionally add a transcript audit of whether coordination was ever *considered* vs never surfaced. *(Perspective)*
7. **Add NCSC-TG-030** and position the close/monitor/accept ladder as its agentic-eval instance; add a sentence on capacity-per-deposit vs the classical bits/sec bandwidth threshold. Add Flume and Ristenpart (with the channel-type caveat). *(Domain)*
8. **Minor:** lead the abstract with the payloads rescue ("carries every externally-specified secret up to a 256-bit key") + the live S3 demo, not 148.7×; flag "synthetic substrate" and "spec-level verification" in the abstract; fix Table 5's `3261` (per-attribute sum shown without `≥` in a paper whose rule is "no headline is a sum"); scope the `order` zero to the sorting `list_dir` primitive; note the permission monitor's 0.50 is a never-fires classifier; residual lab-notebook narration in the screen/L6. *(DA, Domain, Methodology, Track-Fit)*

### Ignored alternatives worth a sentence each (DA)
- **Per-agent/per-episode namespaces as the primary deliverable** — the Discussion says namespaces "convert the flow into an ordinary access attempt"; argue why a lab should adopt the ladder over simply namespacing every episode, or the ladder risks instrumenting a smell the fix dissolves.
- **Write-volume rate-limiting / volumetric anomaly detection** — the incident's 70,000 messages imply detectable write volume; a volumetric monitor sidesteps name-channel blindness and is never considered.

Full per-seat reports: `seat1-trackfit.md`, `seat2-methodology.md`, `seat3-domain.md`, `seat4-perspective.md`, `seat5-devils-advocate.md`.
