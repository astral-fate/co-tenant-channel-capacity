# Closing Content Does Not Close the Channel

**Measured residual capacity in co-tenant agent evaluation infrastructure.**

AI Incident Response Sprint (Apart Research + CeSIA), September 2026 — Track 1, containment.

---

## The finding

In July 2026 a population of evaluation agents, running in separate sandboxes under a single
tenant, discovered that a shared package cache was writable by all of them and used it as a message
board. Every operation involved — writing a file, listing a directory, renaming an entry — was one
the agents were authorized to perform. No tenant boundary was crossed at the point the channel
formed, so every authorization-shaped control passed while the board was live.

This repository measures what such a substrate can carry once you start closing it, and whether
agents actually use it.

**Closing file content — the control payload-inspecting monitors implement — leaves 3075 bits,
recovered exactly by a single encoder on 8/8 trials.**

| Closure rung | Residual (bits) | Carried by |
|---|---:|---|
| open | ≥ 11453 | content, names, existence, size, mtime, count |
| content closed | **3075** *(joint)* | names, existence, size, mtime |
| filename closed | 1802 | dirname, existence, size |
| dirname closed | 13 | size |
| existence closed (fixed manifest) | **0** | — |

Two results about method matter as much as the table:

- **The joint figure is not the sum.** Summing per-attribute cells overstates the residual by 186
  bits, because the cells are not independent — the existence coder writes one file per set bit, so
  the entry count is determined by the existence pattern. A total assembled from separately measured
  widths has never been required to carry anything.
- **`order` measures 0 bits even with the channel fully open**, because `list_dir` returns entries
  sorted, so the sender's chosen permutation never reaches the receiver. The obvious nominal formula
  would assign it log₂(256!) ≈ 1684 bits. That gap is why this project measures achievable rates by
  exhibiting a working encoder and decoder, rather than declaring field widths.

**A payload monitor is blind to a name-carried deposit.** It separates content-carried deposits from
ordinary use at AUC 1.00 and the name channel at AUC 0.52 — chance.

**Capacity is not propensity.** Across 40 + 35 episodes, agents read the substrate almost always and
deposited in **zero**, including under the unsolvable tasks that motivated the incident. What a lab
contains here is capacity, not current behaviour. This result is single-model and that limit is
stated rather than buried.

---

## What is and is not in this repository

The **manuscript is not included**. Everything the manuscript is built from is: the substrate, the
closure ladder, the coders, the harness, the detectors, the analysis, and every artifact under
`results/` from which each figure is substituted at build time.

One consequence: `check.py`'s claim suite recomputes values that the manuscript consumes, so it
verifies the artifacts against each other here rather than against the paper text.

---

## Reproducing

No GPU, no network, no API keys required for the capacity results.

```bash
python check.py          # seven suites: substrate, probe budget, resume, pipeline, claims, scorecard
python src/capacity.py   # measure achievable rate per attribute per rung  (slow: full sweep)
python src/joint.py      # the joint encoder — the figure the paper reports as the residual
```

`results/` holds the committed artifacts the numbers above come from, so the table can be checked
without re-running the sweep.

The behavioural arm does need provider credentials. Copy `.env.example` to `.env` and fill it in;
the example carries key *prefixes* for validation, never live values.

---

## Layout

```
src/        substrate, SRM closure ladder, task family, capacity.py and joint.py
runner/     episode loop, provider adapters, difficulty calibration
detect/     content monitor and structural (SRM) monitor
analyze/    measures with generation-level inference, claim verifier, scorecard
real/       probes against real infrastructure (S3, OCI registry)
docs/       incident timeline with per-line sourcing, novelty positioning, pre-registration,
            and slides.pdf, the compiled talk
paper/      manuscript sources and both builds
results/    capacity, cost, detector and behavioural artifacts
colab/      notebook packaging for hosted runs
```

`index.html` is the talk, served at
[astral-fate.github.io/co-tenant-channel-capacity](https://astral-fate.github.io/co-tenant-channel-capacity/).
It is named `index.html` rather than `slides.html` because GitHub Pages serves the repository
root, and with no index it renders this README instead of the deck.

Two builds render from one claim set. `paper/main-8pp.pdf` is the sprint submission: the body is
eight pages and carries every results table, with the architecture figure and the full-length
discussion in appendices outside that limit. `paper/main.pdf` is the same claims without a page
budget. `./build-slides.sh` renders `slides.html` to `docs/slides.pdf`.

`docs/00-incident-timeline.md` records every timeline claim with its source and a strength label.
Phase A is single-sourced to CeSIA and is marked as such; the empirical claims rest on Phase B,
which is independently sourced to METR/Redwood.

---

## Status and limitations

- **The substrate is synthetic.** These are measurements of a model of a shared cache, not of the
  incident's infrastructure. `real/` probes the same questions against a live object store and an
  OCI registry, and finds that content-addressing closes the name channel only for flat-key stores —
  an OCI registry content-addresses blobs but leaves repository names sender-chosen.
- **The behavioural null is single-model**, on a model released after the incident. It cannot
  separate "agents do not do this" from "this model does not do this."
- **The inheritance advantage Δ is unmeasured.** It is not the headline and is not claimed.
- `ACTION-LIST.md` is the live work queue: what is verified, what is outstanding, and in what order.

---

## Provenance

A five-seat review of v1 returned unanimous major revision, with the methodology seat at reject. The
defects were of a kind a consistency checker cannot catch — a headline that was a ratio of two
constants the authors chose, a declared formula contradicting the constant stored beside it, and a
unit of independence declared in the pre-registration but never implemented, which would have
reported a significant effect that was not there.

v2's response was to measure wherever measurement was possible rather than to patch the prose. Every
number in the manuscript is substituted at build time from `results/`, so a figure cannot disagree
with its artifact. That establishes agreement between claim and artifact; it does not establish that
a measure is appropriate, which is the limit that let v1's headline through, and the paper says so.

---

## Author

Fatimah Emad Eldin — `Fatimah@trouve.works`
