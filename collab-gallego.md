# Collaboration note — covert-channel measurement ↔ epistemic-diversity protocol replay

**From:** Fatimah Emad Eldin (covert storage channels in shared agentic evaluation infrastructure)
**Re:** Sofia Gallego's epistemic-diversity + progressive-replay containment proposal
**One line:** our work sits one layer below yours and plugs straight in — I measure *what a given reviewer can and cannot see*; you propose measuring *which combination of reviewers, over time, catches an unfolding threat*. My monitor result is a single cell in your protocol matrix; your replay generalises it across reviewer types and across time.

---

## Why this is a fit

Your central question — *do different reviewers catch different blind spots, or mainly add confidence to the same interpretation?* — is one my paper answers, with an operating characteristic, for one concrete pair of reviewers:

- A **content/payload reviewer** catches a content-carried deposit at **AUC 1.00** (TPR 1.00 at 5% FPR) but is at **chance on a name-carried deposit — AUC 0.52, 95% CI [0.47, 0.57], TPR 0.00**. Its alarm rate on the name channel (0.385) is indistinguishable from its benign false-positive rate on ordinary use (0.355).
- So here reviewer diversity is **necessary and non-redundant**: the content reviewer is *provably* blind to the channel the July 2026 incident actually used.
- But I also report the honest converse: the **structural reviewer's separation is not established at scale** — having a diverse reviewer did not, in my small construction, demonstrably catch it. **Diversity is necessary but not automatically sufficient.**

That second point is exactly your worry, measured from both sides.

## What I can hand you

1. **A ready testbed for the progressive replay.** My harness reproduces the incident and already emits a real event stream; gating information at time *t* and asking each protocol *continue / restrict / investigate / pause / terminate* is a thin wrapper over what exists. Deterministic, CPU-only, no model budget.
2. **A principled taxonomy of reviewer coverage** — my closure ladder maps your specialised reviewers onto observables: a *permissions* reviewer sees nothing (every operation is permitted — the whole point); a *content* reviewer covers file bodies; a *namespace/structural* reviewer covers names, existence, order; a *downstream-consequence* reviewer is a behavioural-divergence feature (cache hit vs deposit).
3. **A base rate for your metrics** — the behavioural arm measures deposit propensity (~0 in the configuration tested), the denominator your false-alarm and detection-time numbers need.
4. **A deployed-control reference point** — one control (name canonicalisation) on a live object store closes the channel 20/20 → 0/20 at 20/20 legitimate reuse, from one write-path enforcement point. Useful as the "restrict/terminate" endpoint a protocol escalates toward.

## The specific joint experiment (medium effort, high value)

A progressive replay over my incident event stream, gating information at each step *t*, running these protocols and reporting **detection time, false alarms, human-review burden, cost**:

| Protocol | Observable(s) | Expected from my results |
|---|---|---|
| Single content monitor | file bodies | never fires on the name channel (blind) |
| N identical content monitors | same | same blind spot, higher confidence — the redundancy trap |
| Structural / namespace reviewer | names, existence, order | *can* see the carrier; efficacy currently unproven at scale |
| Content + structural (union) | both | detection gated on the structural reviewer working |
| + human escalation at t = k | context | trades detection latency against review burden |

The hypothesis your framing predicts and my data supports: **detection tracks the diversity of *observables*, not the number or reasoning depth of reviewers.** N content monitors, or content reviewers in debate, share one blind spot; only a reviewer that watches a *different observable* moves detection time.

## How the three papers you cited slot in

- **GuardAgent** (guard LLM compiling policy → guardrail code; access-control/policy compliance) — your *safety-agent* arm. My argument predicts it is **blind to a name-carried deposit by construction** (all operations permitted) unless its compiled policy encodes structural/namespace invariants. A concrete falsifiable claim for that protocol.
- **Multi-Agent Judge / debate** ("a few rounds capture most gain") — your *reviewers-checking-each-other* arm, and a direct test of the redundancy worry. My work sharpens *why* gains plateau: debate among same-observable reviewers adds confidence, not coverage.
- **MAGE / shadow memory** (safety context across the full trajectory) — the *long-horizon* arm. My covert channel is a long-horizon threat by construction: the deposit is meaningless within one generation and only becomes a channel across generations (g → g+1). A per-turn monitor misses it; cross-trajectory memory is the mechanism class that could catch it. My substrate is a clean instance to test shadow memory against.

## The reframing to take away

The epistemic diversity that matters is **diversity of observables, not diversity of reasoners.** My content-vs-structural result is the existence proof; redundancy or debate among same-observable reviewers manufactures confidence around a shared blind spot. That turns your open question into a testable design principle — and it is the piece none of the three cited papers supplies, because none measures the observability gap directly.

Happy to run the replay on my harness together, or hand over the event stream + the two monitors and metric code so you can drive it.
