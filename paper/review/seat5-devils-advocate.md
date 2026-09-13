## Devil's Advocate Report

**Reviewed:** D:\ins respinse\project-v2\paper\main.tex (1719 lines, read in full).
**Venue:** AI Incident Response Sprint (Apart Research + CeSIA), Track 1 — a 3-day sprint output.
**Note:** This is a peer-review challenge of the argument, not a code audit. Arithmetic that could be checked (3261, 11453, 3075 = 3261 − 186, the p=0.031 sign test, the Wilson bounds) is internally consistent.

---

### Strongest counter-argument

The paper's headline is a precise number about a channel its own agents never used, measured against a monitor its own text says nobody purely deploys, on a substrate its own real-world section shows the number does not survive. Three concessions, each honest in isolation, are jointly fatal to the *headline* (not the thesis). (1) The 3075-bit residual and the "148.7x passcode" are both computed from author-chosen constants (`MAX_FILE_BYTES=8192`, `MAX_ENTRIES=256`) and the study's own passcode; Sec. Real then reports the real body limit is 8192x larger, real directories hold 200,000 entries, and real timestamps add ~30 bits — so the specific figure transfers to nothing, as Sec. 2.2 and L3 concede. (2) Sec. Payloads shows 5/5 real credentials fit and "the table does not discriminate," which means the operationally relevant claim is merely "residual > a credential" — true at 300 bits or 30,000. The precision of 3075 and 148.7 is therefore theatre around a claim that is qualitative and, being analytic (Sec. Blind), was true a priori. (3) The behavioural arm — the paper's only empirical test of whether the channel matters — is a *null*: 0/75 deposits. Operational relevance is imported wholesale from the July incident and one external study (Paglieri). So a reader is asked to accept a falsely-precise synthetic capacity for a channel the authors could not induce their own agents to use, against a pure-payload monitor the paper admits real DLP is not. The thesis "content inspection is insufficient" survives all of this — because it is a theorem. But the *paper*, as sold by its abstract and title, oversells a circular number as a finding.

---

### Issue list

**MAJOR — headline validity — Abstract, title, Sec. Joint, Sec. Payloads.**
Challenge: The 3075-bit / 148.7x headline is synthetic and circular (both quantities from the authors' own harness), and Sec. Real demonstrates it does not transfer to real infrastructure.
Rebuttal condition: The paper already argues residual is a method demonstration, not a quotable production number (Sec. 2.2) — the fix is to report the headline as "at least one credential's worth after content closure" rather than "3075 bits, 148.7x." If the abstract were re-framed qualitatively this issue dissolves.

**MAJOR — operational realism — Sec. Blind, Threats.**
Challenge: The paper concedes "many deployed data-loss-prevention systems do inspect paths," which would catch the filename (1292) and dirname (1318) carriers — the bulk of the residual. Yet it never computes the residual against a realistic path-inspecting monitor: existence+size+mtime ~= 523 bits (still > a 256-bit key). The most decision-relevant number is absent, and the reported 3075 assumes a pure-payload monitor the paper itself says is not what real systems use.
Rebuttal condition: Sec. Blind is explicitly scoped to payload-only monitors. Reporting the ~523-bit residual under path inspection would rebut me — and would strengthen the paper.

**MAJOR — monitor vs. closure conflation — Sec. Cost, Sec. Usecost.**
Challenge: The cost "inversion" narrative ("the ineffective control is the expensive one") conflates a content *monitor* (read-only detection, ~0 task cost, cheap) with content *closure* (redaction, up to 1.00 task-success cost in the usecost table). The control labs actually deploy is a monitor; Sec. Usecost measures redaction. A read-only content monitor is both cheap and ineffective — a simpler, stronger argument — so the "pay the most for the least" punchline overstates the realistic control's cost.
Rebuttal condition: The paper has two cost axes (defender regime + agent task-success). Separating the deployed monitor's ~0 task cost from redaction's task cost in the inversion claim would rebut me.

**MAJOR — borrowed relevance / the null — Sec. Gate, Sec. Followup.**
Challenge: 0/40 then 0/35 deposits. The capacity result's real-world weight rests entirely on the July incident and Paglieri (both external, unrun by the authors). The paper's own agents demonstrate the channel is unused.
Rebuttal condition: The paper frames itself as containment engineering (measure before exploitation), reconciles the incident via scale/conditions, and proposes a falsifiable lockout experiment — this is handled well, not glossed. Residual severity is about framing, not a hidden flaw.

**MAJOR — ignored alternative for the null — Sec. Followup, "Why the deposit never happened."**
Challenge: The paper attributes zero deposits to "a missing reason to send." An equally strong explanation is that a safety-tuned model (claude-haiku-4.5) declines covert coordination for alignment reasons. The probe episode ("established the affordance then had no use for it") is fully consistent with a model that chose not to, not one lacking incentive. If alignment suppresses deposits, the capacity's threat relevance drops.
Rebuttal condition: Paglieri's less-constrained agents did deposit under lockout — but they were differently incentivised/possibly differently aligned, so this does not isolate "incentive" from "alignment." A deposit under lockout with the same model would rebut me; the paper does not yet have it.

**MAJOR — generalisation of "free" — Sec. Usecost, App. Standard clauses 3 and 6.**
Challenge: "Dirname closure costs 0.00 task success" is measured with an oracle cache user (conceded lower bound) on one task family (passcode search) where names are incidentally task-irrelevant. On a cache where names carry semantic lookup value, name closure could break function. The "free" claim — the paper's core actionable recommendation — is the optimistic end of an oracle measurement on a favourable task.
Rebuttal condition: The paper flags the oracle and the budget-14 ceiling. It does not flag task-family dependence of the "free" result; adding that caveat, or measuring on a semantic-name cache, would rebut me.

**MINOR — cumulative-closure phrasing — Abstract, Table 1.**
Challenge: Because closure is cumulative and the dirname rung zeroes existence/size/mtime (entries become unaddressable), "closing directory names" actually means full cross-agent namespace isolation reached after content+filename closure. The abstract compresses three closures + namespace isolation into one phrase, understating the intervention.

**MINOR — "immune" residual overstated — Sec. Ratio.**
Challenge: The joint residual is immune to ceiling-raising but the paper concedes it moves with encoder strength (real names ~= 2040 bits) and substrate (+30-bit timestamps). "Immune" is true only against one of several perturbations.

**MINOR — modest novelty — Sec. 2.**
Challenge: Metadata-as-covert-channel is decades old (the paper's own Lampson/Kemmerer/TCSEC citations); Metere2026 is conceded as method precedent. The genuine contributions are the application domain, the residual-not-fraction convention, and the AIS-11 clauses. Appropriately scoped for a sprint, but the framing occasionally reads bigger than the delta.

---

### Ignored alternative explanations / paths

- Alignment/safety training as the cause of the null — the single most important unconsidered confound.
- Residual against a realistic path-inspecting monitor (~523 bits) — never computed, though it is the number a lab would actually face.
- Read-only content monitor (cheap + ineffective) as the true deployed control, distinct from redaction.
- Whether "dirname closure" on a semantic-name cache is genuinely free, or free only when names are task-irrelevant.

---

### Missing stakeholder perspectives

- The **model developer**: if RLHF already suppresses covert deposits, the containment control defends against a partially-mitigated threat.
- The **cache operator with functional name dependence** (dedup, cross-build reuse): "0.00 task success cost" is not "0.00 functional cost"; the interface-migration cost is acknowledged but never priced.
- The **auditor the clauses are written for**: the paper claims external verifiability, but every MEASURED cost rests on an oracle single-agent arm the auditor cannot reproduce against a real model without the lab's model access.

---

### Observations (non-defects) — do not "fix"

- Disclosure of disconfirming evidence is exceptional and rare: it reports the p=0.031 result *in order to reject it* (Sec. Noeffect), concedes the negative control shows the design manufactures significance from noise (L5b), reports its own null as a null, and lets the real-substrate section overturn two of its own figures. This is the opposite of cherry-picking.
- The residual-vs-fraction argument is *genuinely* sound, not repackaging: the demonstrated movement of the open-rung total (4297 to 11453) with unchanged substrate is a real instability in any fraction, and the joint residual's exclusion of the censored count cell is a legitimate fix.
- Sec. Blind is a valid analytic argument, correctly labelled "an argument, not an experiment."
- The unit-of-independence correction (generation, not episode) is correct and frequently missed in this literature; the worked p=0.0256 vs 0.1789 example is a real service.
- The probe-vs-deposit classification rule is pre-registered before the larger run, which correctly guards against post-hoc fitting.
- Reproducibility discipline (stdlib-only, deterministic seeds, no hand-typed numbers) is above the norm for any venue, let alone a 3-day sprint.
- The "reason to send" hypothesis is **not** an unfalsifiable escape hatch: it names a mechanism (asymmetric lockout), cites an external confirming case, and specifies the next experiment. Treat it as borderline, not as a defect.

---

### Bottom line for the venue

For a 3-day AI Incident Response sprint, this is unusually rigorous and self-aware work whose central claim ("content inspection does not discharge a non-interference requirement") is essentially valid because it is analytic. It has **no CRITICAL flaw** that survives its own concessions. Its real weaknesses are all overselling: a circular, falsely-precise synthetic headline; a missing realistic-monitor residual; a monitor/closure cost conflation; and an unexamined alignment confound for its central null. Every one is a framing or scope problem the body already half-concedes — which is exactly why the abstract and title, which do not concede them, are the part most in need of revision.
