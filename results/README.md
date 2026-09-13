# `results/` — every artifact the manuscript is built from

No number in the paper is typed. `paper/render.py` recomputes each one from the files
below at build time and substitutes it into `main.tex.tmpl`; an unknown placeholder
fails the build. So this tree *is* the evidence — if a file here changes, the paper
changes with it.

```
results/
├── capacity/                  Arm 1 — how much CAN flow. No model, no network.
│   ├── capacity.json            the ladder: 8 attributes x 6 rungs, 8 trials each
│   ├── joint.json               ONE encoder across all open carriers (the headline)
│   ├── closure-cost.json        mediation points per rung
│   ├── payloads.json            external payload anchors (IPv4, AWS key, UUID, PAT, Ed25519)
│   ├── capacity-table.txt       human-readable rendering of capacity.json
│   └── *-prefix/-preraise.json  earlier ceilings, kept so the raise is auditable
│
├── behavioural/               Arm 2 — will agents DO it. Needs a model.
│   ├── runs-full/               the pre-registered matrix (open vs wipe, 40 episodes)
│   ├── runs-blocked/            the follow-up with unsolvable tasks reachable (35 episodes)
│   ├── runs/                    exploratory single-model runs
│   └── calibration/             the gate: solo success must be strictly inside (0,1)
│       ├── calib-full/            Haiku 4.5 — 6 budgets, 31 episodes, the reported sweep
│       ├── calib-smoke/           fast sanity sweep
│       ├── kimi/                  Kimi K3 — control attempted, provider rate-limited
│       ├── oss-120b/              gpt-oss-120b — floors at 4/8, window at 16, truncated
│       └── qwen-calib.json        Qwen3-8B — the floor, extracted from ars-results.zip
│
├── real-substrate/            Tiers 1-3: measured on infrastructure we did not configure
│   ├── real-limits.json         real mount: 67,108,864-byte bodies, 1 ns timestamps
│   ├── real-store-registry.json real OCI registry: closes filename only, sits at no rung
│   └── tier3-episodes.txt       sender/receiver in separate containers
│
├── screen/                    Which models were run, and why each was excluded
│   ├── model-screen.json        built by analyze/model_screen.py; feeds Table 5
│   └── kimi-open.json           Kimi's substrate-present episodes
│
└── analysis/                  Derived, not measured
    ├── reanalysis.json          re-analysis at the correct unit (generations, not episodes)
    ├── scorecard.md             pre-registered predictions vs outcomes
    ├── cost/                    closure-cost intermediates
    └── fixtures/                synthetic fixtures for the detector tests
```

## Two rules this tree enforces

**An API-error episode is never a data point.** Every consumer here splits episodes on
`api_error` before computing a rate. A run cut short by a rate limit says nothing about
a model, and counting it as a failure biases the success rate downward — which is how an
exhausted quota becomes a spurious null.

**A per-attribute sum is not a residual.** `capacity.json` holds cells measured one
attribute at a time; their sum is an upper bound that double-counts dependent attributes
and inherits any censoring. `joint.json` holds the residual: one encoder, all open
carriers, recovered exactly on every trial. `render.py` fails the build if the manuscript
ever calls the first the second.

## Regenerating

```bash
make capacity   # re-measure the ladder      (no model, no network)
make joint      # re-measure the joint coder (no model, no network)
make screen     # rebuild the model screen from whatever runs exist
make paper      # recompute every claim and rebuild the PDF
```
