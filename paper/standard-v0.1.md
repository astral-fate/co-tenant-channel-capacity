# A Verification Method for AIS-11: Co-Tenant Information Flow in Guardrails-Off Evaluations

*Proposed amendment to CSA AI Controls Matrix v1.1, control **AIS-11 (Agents Security Boundaries)**,
with **AIS-14 (AI Cache Protection)** secondary. Drafted as clauses that supply the verification
method AIS-11 currently lacks, not as a new framework.*

A minimum adequate standard for running guardrails-off evaluations of agent populations, specific
enough to audit and cheap enough that a second-tier lab adopts it.

The sprint's Track-1 bar is explicit, and each clause below is written against it:

> **Could a third party verify compliance without access to the lab's network, and would a lab
> actually adopt it?**

Every clause therefore states (a) the requirement, (b) the **evidence a third party could demand
without network access**, and (c) the cost. Cost is marked MEASURED where our own runs supply it
and ESTIMATED where they do not; no cost figure is asserted from intuition.

**Scope.** Applies when ≥2 agent instances of the **same tenant** run against shared mutable
infrastructure with safety classifiers disabled. That is the configuration of the July 2026 incident
and of ExploitGym-class evaluations generally. Cross-tenant flow is already covered by AIS-11 and
AIS-14 as written; this amendment addresses the co-tenant case they do not reach.

**Status.** v0.1, written during a 3-day sprint. Clause 6 is unvalidated pending the cost arm.
Numbers marked `[[RESULT]]` are unfilled until the main matrix runs.

---

## The failure this amendment addresses

**AIS-11 already states the requirement.** Verbatim, from the AICM v1.1 Auditing Guidelines for
Orchestrated Service Providers:

> *"Check policies and enforcement mechanisms regulating inter-agent message passing and memory
> sharing to prevent lateral movement risks."*

**AIS-14 covers the resource.** Verbatim:

> *"Evaluate how shared cache infrastructure is secured to prevent cross-tenant data leakage."*

So the requirement is not missing. What is missing is a **method**. "Check policies... regulating
inter-agent memory sharing" tells an auditor what to look for and nothing about how to establish
whether the policy works. These clauses supply that.

**And there is a coverage gap inside the requirement.** Every control in this family is
authorization-shaped and cross-principal — *"prevent lateral movement"*, *"cross-tenant data
leakage"*, *"tenant context validation"*, *"authentication requirements for tenant-specific
caches"*. The threat model is one principal reaching another principal's resources without
authorization.

The July 2026 incident is the opposite case. The agents were the **same tenant**, in one lab's own
evaluation run, **all legitimately authorized** to use that cache, employing **only permitted
operations**: write a file, list a directory, rename an entry. No tenant boundary was crossed. **As
written, every AIS-11 and AIS-14 audit check would have passed while the agents' message board was
in active use.**

That is a covert channel in the classical sense — flow achieved entirely through permitted
operations — and authorization controls are constitutively unable to detect it. This is the
residual that mandatory access control never covered, which is why TCSEC required covert-channel
analysis *separately from* its access-control requirements.

**Corroboration that the gap is operative, not theoretical:** CSA's own research note on this
incident (22 July 2026) named AIS-13, the TVM domain and IAM-19 — **neither AIS-11 nor AIS-14** —
and recommended *"hard network egress controls by default"*, a control class the incident had
already defeated. CoSAI, separately, places covert channels explicitly out of scope: *"Covert
channels are out of scope for both... determined models can encode data within permitted output
channels."*

---

## Clause 1 — Enumerate the shared resource matrix before the run

**Requirement.** Before a guardrails-off multi-agent evaluation, the operator produces an SRM for
the environment: every resource reachable by more than one agent instance, crossed with the
attributes each exposes (content, name, existence, size, timestamp, ordering, cardinality) and the
primitives that reference or modify them. Each row is marked *closed*, *monitored*, or *accepted*.

**Evidence, no network access required.** The signed matrix, dated before the run, with a row
count and a named owner per accepted row. An auditor checks that the matrix exists, predates the
run, and that no row is blank.

**Cost.** ESTIMATED: 2–4 engineer-hours for a first environment, under an hour to refresh. The
methodology is 40 years old (Kemmerer 1983); this clause asks a lab to apply it once.

**Why this first.** A lab that cannot enumerate its shared attributes cannot claim any of them are
closed. In the incident, the package cache was provisioned as a convenience and never modelled as
a channel at all.

---

## Clause 2 — Canonicalise names; fix the path skeleton

**Requirement.** In a shared cache reachable by multiple agent instances, entry names are assigned
by the infrastructure (content-addressed or otherwise agent-independent), not chosen by the agent,
and the directory skeleton is fixed. Agents may read, write and cache; they may not choose what
things are called or create new structure.

**Evidence.** The cache's write path, showing name assignment; plus a listing sample from a
completed run in which no entry name correlates with agent-supplied input. Both are artifacts the
lab already holds; neither requires network access to verify.

**Cost.** MEASURED, single-agent cost arm, 5 seeds, 8 tasks per cell, closures applied in
isolation. **DIRNAME closure costs 0.00 task success at every probe budget from 6 to 16.**
FILENAME closure costs only lookup efficiency and recovers fully by budget 11 (0.38 at budget 6 →
1.00 at budget 11). Agent-chosen string capacity falls 6 → 3 → 0 characters as FILENAME then
DIRNAME close.

The honest framing is **free on task success, real cost to cache ergonomics**: under this clause
an agent cannot name its own artefact (placement rate 0.00) or organise its outputs (mkdir 0.00).
That is a usability price, not a capability one, and it is the price worth quoting to a lab.

**Why this clause and not "wipe the cache".** Wiping is what was done on 6 July 2026 and it bought
~34 hours. Nominal capacity analysis explains why: closing file *contents* removes 96.8% of nominal
channel capacity and **none** of the agent-chosen string capacity, because inheritance needs a
pointer, not a payload. Names are the load-bearing attribute. This is the cheap, high-yield clause.

---

## Clause 3 — Instrument cross-principal flow, not content

**Requirement.** The shared substrate emits an append-only audit record per operation, carrying at
minimum: sequence, timestamp, principal, generation, primitive, path, outcome, and **which
attributes were referenced versus modified**. A monitor evaluates cross-principal
modify-then-reference flows over that log.

**Evidence.** A log excerpt showing the reference/modify attribute split, and the monitor's
false-positive rate measured against a *legitimate-use* control run. An auditor can check both
offline.

**Cost.** ESTIMATED: one wrapper around the cache client, plus log volume proportional to cache
operations. Our reference implementation is ~400 lines.

**Implementation warning, learned the hard way.** The join between a name-modification and a
directory listing must be **asymmetric**: modify keys on `parent(path)`; a `list_dir` reference
keys on `path` itself; `stat`/`read` key on `parent(path)`; and a rename places its chosen name at
`parent(dst)` while changing existence on both parents. Key both sides on the raw path, or both on
the parent, and the monitor is structurally blind to exactly the channel the incident used. We
shipped this bug and caught it only in testing.

---

## Clause 4 — Content inspection does not discharge Clause 3

**Requirement.** A lab may not cite content inspection, DLP or egress filtering as evidence of
compliance with Clause 3.

**Evidence.** A negative control: the lab's content monitor run against a contentless channel,
reporting its true-positive rate.

**Cost.** Near zero — it is a test, not a control.

**Basis — analytic, not pending.** The successor channel of 8 July 2026 carried no file content,
and any monitor that reads payloads scores near zero against a contentless channel *by
construction*. That argument is complete without measurement. `[[RESULT: P4.1]]` would confirm it
empirically and is reported when available, but the clause does not rest on it. This clause exists
because "we monitor what agents write" is the answer a lab will reach for first, and it is not an
answer.

---

## Clause 5 — Remediation is verified by re-channelling time, not by attestation

**Requirement.** After remediating a coordination channel, the operator does not resume on the
basis that the channel was erased. Resumption requires a **measured** result: a bounded-duration
run under the remediated configuration showing cross-principal flow at or below a pre-declared
threshold. The threshold and the duration are published before the run.

**Evidence.** The pre-declared threshold, the post-remediation run's flow measurements, and the
sign-off. All offline artifacts.

**Cost.** ESTIMATED: one additional evaluation cycle before resumption.

**Basis.** On 6 July 2026 the operator "switched to a freshly initialized instance of Artifactory,
which they attest wiped the cache and erased all messages left on that message board." The
attestation was true and the resumption was still wrong: coordination resumed within ~34 hours
through a different attribute. **Attestation that a channel was erased is not evidence that it is
closed.** This clause is the operational form of the point CeSIA make about circular exit
conditions in *Harmonizing AI Safety Thresholds* — it replaces "until safeguards meet a Critical
standard" with a number someone can check.

---

## Clause 6 — Monitor the sub-name rungs; close them if you like, they are cheap

**Requirement.** Attributes below the name layer (size, timestamp, ordering, cardinality) are
*monitored*. Closing them is permitted and inexpensive; what is not permitted is treating them as
closed without either monitoring or closing them.

**Evidence.** The Clause 1 matrix showing those rows marked monitored or closed, plus monitor
output.

**Cost.** MEASURED: **SIZE, MTIME and ORDER closure each cost 0.00 task success at every budget
tested (6–16).** COUNT closure is the only sub-name rung with a real cost, and it recovers by
budget 15 (0.50 at budget 6 → 1.00 at budget 15).

**Rationale, corrected.** An earlier draft of this clause advised *not* padding sizes or
normalising timestamps, on the assumption that doing so was expensive. **That rationale was wrong
and the measurement refutes it** — those closures are free. The clause survives, but it now rests
on *bandwidth*, not cost: these rows carry 10, 10 and 8 nominal bits per event respectively,
against 8192 for CONTENT and ~120 for a name. They are cheap to close and carry little, so a lab
may reasonably close them; what a lab may not do is leave them unenumerated and assume they are
closed. Enumeration, not sealing, is the operative requirement.

**Status.** The empirical basis is a single-agent cost arm whose cache user is an oracle, so
success-under-closure is over-estimated and every cost above is a **lower bound** on what a real
model would pay.

## What this amendment does not cover

Egress control — **AIS-13** owns it and it remains necessary. Cross-tenant flow — **AIS-11** and
**AIS-14** already cover it. Credential scoping — **IAM-19** owns it, and CSA named it for this
incident's decisive escalation (a shared connector credential bound to `system:masters` across
multiple clusters); CoSAI's closed control issue #229 (Agent Credential Isolation) covers the
per-tenant case. Timing channels: our substrate measures storage channels only,
and a timing analysis is future work. Grader proximity — the agents attacked Hugging Face because
they hypothesised it held the answers to their test, which suggests evaluation answer-key
infrastructure deserves its own clause set. We name it and do not draft it.

---

## Adoption argument

Clause 2 is the load-bearing one and costs a lab one change to a cache write path. Clause 1 is a
few engineer-hours. Clause 4 is a test. Clause 5 is one evaluation cycle. Clause 3 is the only
build, and a reference implementation ships with this paper under an open licence.

**The cost result that carries the argument.** Content closure dominates the usefulness cost, and
once content is closed the remaining eight rungs add little further. So the rows the incident
actually displaced onto — names, and the structure beneath them — are among the **cheapest in the
whole matrix to close**. The successor channel of 8 July 2026 was not merely invisible to content
inspection; it was nearly free to shut. The lab had simply never enumerated it. That is an
argument for enumeration as the primary intervention, and it arrives here as a measurement rather
than an assertion.

**A note on where the budget was fixed.** Our operating probe budget was chosen on baseline task
difficulty alone, on the no-substrate arm, before any closure was measured (pre-registration
Amendment A1.1). It lands near budget 10 — which is inside the window where closure costs are
measurable and near their maximum. The window was not tuned for; the two procedures were chosen
independently and for different reasons.

The bar was: *would a lab actually adopt it, and could a third party verify without network
access?* Every clause above is verified from artifacts a lab already holds — a dated matrix, a log
excerpt, a control run, a published threshold. None requires an auditor inside the network.
