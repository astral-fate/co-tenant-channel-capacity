# Editorial Decision — Multi-Perspective Review

**Manuscript:** *Closing Content Does Not Close the Channel* (covert storage channels in shared agentic evaluation infrastructure)
**Venue calibration:** AI Incident Response Sprint (Apart Research + CeSIA), Track 1 — containment/contamination
**Panel:** 5 seats (Track-Fit, Methodology/Measurement, Domain: Covert Channels & Security, Perspective: ML/Agents, Devil's Advocate)

---

## Decision: MINOR REVISION (unanimous)

All five seats independently recommended **Minor revision**. Every reviewer judged the work unusually rigorous and honest for a 3-day sprint, and the central thesis — *content inspection does not discharge a non-interference requirement* — is sound (the Devil's Advocate notes it is essentially **analytic**, hence robust). No reviewer found a results-invalidating error. Every MAJOR item is a **framing, scope, or consistency** fix, or one cheap additional run — none require re-doing the core measurement.

> **Caveat on the decision:** the *number* of substantive MAJOR items is high for a "Minor." At a stricter security venue (USENIX/S&P), the IFC/DIFC engagement (Domain seat) and the n=3 grid consistency (Methodology seat) would likely escalate to **Major**. For this sprint venue, Minor is correct — but treat the Priority-1 and Priority-2 items below as **required**, not optional.

---

## Devil's Advocate CRITICAL adjudication (Iron Rule #4)

**No DA-CRITICAL findings.** The Devil's Advocate explicitly concluded the paper "has no CRITICAL flaw that survives its own concessions." All DA issues are MAJOR-level overselling/framing problems that the manuscript body already half-concedes. Nothing blocks acceptance; the DA's value here is a precise map of where the abstract/title claim more than the body defends.

---

## Consensus map (where seats agree)

| Theme | Seats | Severity |
|---|---|---|
| **Abstract/title oversell the synthetic headline & undersell the adoptable control** | Track-Fit, Methodology, DA | MAJOR |
| **Behavioural null vs. adoption case unreconciled; no consolidated "what a lab should do"** | Track-Fit, Perspective, DA | MAJOR |
| **"Zero-error over 8 trials" overstates what 8 samples license** | Methodology, Domain | MAJOR/MINOR |
| **Central thesis is sound; honesty/disclosure is exemplary** | all 5 | (strength) |
| **Reproducibility discipline above venue norms** | Methodology, DA | (strength) |

## Distinctive findings (single-seat, high value)

- **n=3 grid overreach** (Methodology): the paper disowns n=3 as "noise" for Haiku, then leans on n=3 Bedrock cells to claim "two open-weight families pass the gate." `gpt-oss-120b` is non-monotone (0.667/0.667/0.333) — the same signature flagged as noise elsewhere. **Internal inconsistency.**
- **IFC/DIFC literature not engaged** (Domain): the "no published control" claim is over-broad — Decentralized Information Flow Control *is* the published control class for flow through permitted operations, and per-agent namespaces are a coarse instance of it. Scope the claim + cite Myers–Liskov (SOSP'97), Zeldovich HiStar (OSDI'06), Krohn Flume (SOSP'07).
- **Measured-zero ≠ proven non-interference** (Domain): add a *structural* argument for the zero rung (once names are closed, no sender-choosable attribute remains), don't rest "reaches zero" on one encoder over 8 trials.
- **Capability gate ≠ deposit capability** (Perspective): the gate proves the model can do the *task*, not that it can conceive/encode/write a covert deposit — so "could but wouldn't" rests on an n=1 probe. Add an instructed-deposit positive control and/or run the deposit matrix on a 2nd gate-passing model.
- **Alignment confound for the null** (DA): a safety-tuned model may *decline* covert coordination — an alternative to "no reason to send" that the paper never considers.
- **Realistic path-inspecting monitor residual absent** (DA): real DLP inspects paths; the decision-relevant number is the residual under path inspection (~existence+size+mtime, still > a key), never computed. The reported 3075 assumes a pure-payload monitor the paper admits nobody deploys.

---

## Revision Roadmap (prioritized)

### Priority 1 — Highest leverage, cheap, do first
1. **Reframe the abstract (and reconsider the title).** (a) Surface the adoptable control: directory-name closure reaches zero residual at zero measured task cost and is externally verifiable without the lab's network. (b) Flag the residual as synthetic where it first appears ("on a synthetic model of such a cache"). (c) State the two-arm structure in one line. *[Track-Fit MAJOR, DA MAJOR, Methodology]*
2. **Add an explicit lab-facing recommendation + reconcile the null up front.** One paragraph (end of Intro or top of Discussion): capacity is a substrate property independent of current propensity; propensity is config-dependent and demonstrated at scale elsewhere (Paglieri); therefore close structurally now because it is cheap. Prevents "0/75 deposits" being misread as "no problem." *[Track-Fit MAJOR, Perspective, DA]*

### Priority 2 — Defensibility (framing/consistency)
3. **Fix "zero-error over 8 trials."** Reframe as an empirical lower bound on zero-error capacity (C₀ ≤ C_Shannon); "8 seeded payloads round-tripped through a deterministic map," not a zero-error guarantee. State the false-credit probability or raise the trial count. *[Methodology MAJOR, Domain MINOR]*
4. **Resolve the n=3 grid inconsistency.** Either extend the Bedrock sweeps to the ~8-seed depth used for Haiku, or downgrade "two families pass the gate" to "suggestive at n=3, the same regime §4.14 flags as noise-dominated." Do not treat n=3 as noise for the reported model and a pass for the others. *[Methodology MAJOR]*
5. **Commit to the "verification method for AIS-11" framing throughout** and engage IFC/DIFC. Remove the "constitutively blind"/"never covered" oscillation; scope novelty to *agentic evaluation infrastructure*; add a short IFC paragraph (namespaces as the pragmatic DIFC subset). *[Domain MAJOR]*
6. **Add a structural argument for the zero rung.** Once file and directory names are both closed, no sender-choosable attribute remains → provably zero, paralleling the §5.3 structural argument for content. Distinguish "measured 0" from "non-interference." *[Domain MAJOR]*

### Priority 3 — Strengthening (one cheap run + honest caveats)
7. **Compute the residual under a realistic path-inspecting monitor** (the number a lab faces) alongside the pure-payload 3075. *[DA MAJOR]*
8. **Separate monitor (read-only, ~0 cost) from closure/redaction (costly)** in the cost-inversion narrative. *[DA MAJOR]*
9. **Address CAN'T-vs-WON'T:** add an instructed-deposit positive control and/or run the deposit matrix on ≥1 more gate-passing model (gpt-oss-120b, kimi-k2.5). Flag single-model deposit scope in the abstract. *[Perspective MAJOR]*
10. **Name the alignment/safety-training confound** as an alternative explanation for the null. *[DA MAJOR]*
11. **Flag task-family dependence of the "free" dirname-closure result** (names are task-irrelevant here; a semantic-name cache may pay a functional cost). *[DA MAJOR]*
12. **Disentangle motive from benefit** in the null: state whether successors face related/same tasks; if not, fold "shared objective" into the "reason to send." *[Perspective MAJOR]*

### Priority 4 — Polish, citations, minor
- Missing canonical citations: **NCSC-TG-030** (absolute-bandwidth/residual reporting is classical practice, not a novel correction), **Ristenpart et al. CCS'09** (co-residency), the IFC papers above. *[Domain]*
- Define/distinguish **"co-tenant"** from cloud co-residency at first use. *[Domain]*
- **Scope out timing channels** explicitly in §3. *[Domain]*
- Add a literal **shared-resource matrix** (Kemmerer). *[Domain]*
- State the **existence-depends-on-names** dependency where Table 1 is discussed. *[Domain]*
- Recast **Contribution 5** (negative control) as a methodological safeguard, not a headline contribution. *[Track-Fit]*
- Soften the **n=1 probe** over-weighting ("discovery is reachable" from one observation). *[Perspective]*
- State the **build trust boundary**: the build verifies consistency with `results/` JSON, not correctness from raw transcripts; the raster figure is not build-verified. *[Methodology]*
- Consider compressing calibration/screen tables to keep the capacity+control spine foregrounded. *[Track-Fit]*

---

## Reviewer recommendation signals
| Seat | Signal |
|---|---|
| Track-Fit | Minor revision |
| Methodology / Measurement | Minor revision |
| Domain: Covert Channels & Security | Minor revision (IFC item → Major at a stricter venue) |
| Perspective: ML / Agents | Minor revision |
| Devil's Advocate | No critical flaw; framing/overselling only |

Full per-seat reports: `seat1-trackfit.md`, `seat2-methodology.md`, `seat3-domain.md`, `seat4-perspective.md`, `seat5-devils-advocate.md`.
