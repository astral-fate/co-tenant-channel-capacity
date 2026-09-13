# Nano Banana prompt — methodology figure (Track 1)

Target file: `paper/figures/methodology.png`
Refreshed **2026-09-06** against the live artifacts. Verify with `python paper/render.py --list`.

---

## Read this first — the previous figure was withdrawn for exactly this reason

The last version of this figure shipped with `>= 4297`, `>= 201`, `>= 64` and `9.7x` rendered into
the image. Every one of those numbers has since moved: the search ceilings were derived from
substrate constants rather than chosen by hand, an encoder defect in the existence row was fixed,
and the joint residual is now *searched* rather than assumed. A reviewer found the figure
contradicting its own caption, and was right to — the paper claims every value is substituted from
`results/` at build time, and a raster image is the one place that guarantee cannot hold.

It now sits in `figures/stale/methodology-SUPERSEDED.jpg` and is not built.

**Therefore, strongly preferred: ask for the diagram with NO numeric labels at all** — boxes,
arrows, staircase shape, category names — and add every number afterwards in Inkscape, Figma or a
vector editor. The layout is the hard part. The numbers are the part you cannot afford to have
invented, and an image model garbles digits routinely.

If you do let the model render the numbers, check every one against the table at the bottom before
the figure goes near the paper. A wrong digit here is worse than a missing figure.

---

## House style

> Flat vector style on a white background. A technical diagram, not an infographic. Restrained
> palette: charcoal `#2B2B2B` for text and strokes, muted slate blue `#3A6EA5` for actors and data
> flow, warm amber `#D98C2B` for the highlighted result, soft red `#B5453C` for closed or blocked
> states, light grey `#EFEFEF` for panel fills. Thin 1.5pt strokes. Generous white space. No
> gradients, no drop shadows, no 3D, no glossy effects, no photographic elements, no decorative
> background. Clean geometric sans-serif labels (Inter or Helvetica). Every label horizontal and
> legible at small print size. Do not add a title, a legend, an outer border, page numbers, or any
> text other than the labels specified.

---

## The prompt

> [paste house style]
>
> A wide landscape methodology diagram, roughly 16:9, in four horizontal bands stacked top to
> bottom, separated by thin light-grey rules, with a small bold letter (A, B, C, D) at the
> top-left of each band.
>
> **Band A — "The substrate and the two agents".**
> On the left, two rounded-square agent icons stacked vertically in slate blue outline, each with
> a small head-and-shoulders glyph. Top labelled **"Agent, generation g"**, bottom labelled
> **"Agent, generation g+1"**. Between them a horizontal dashed grey line labelled
> **"episode boundary"**. A faint grey arrow drawn directly between the two agents, struck through
> with a red X, labelled **"transcript NOT inherited"**.
> In the centre, a tall light-grey rounded rectangle labelled **"shared package cache"** with a
> small database-cylinder icon at its top.
> A solid slate-blue arrow from the top agent into the cache labelled **"write"**; a solid
> slate-blue arrow from the cache to the bottom agent labelled **"read"**, with three small
> monospace tags beside it: `list_dir`, `stat`, `read_file`.
> Caption under the band: **"every operation is permitted"**.
>
> **Band B — "Eight observable attributes"**.
> A single horizontal row of eight small light-grey pill chips, evenly spaced, each with a tiny
> icon at its left, labelled exactly: **content**, **filename**, **dirname**, **existence**,
> **size**, **mtime**, **order**, **count**.
> A thin bracket spanning all eight labelled **"a sender can vary, a receiver can observe"**.
> The **order** chip is greyed out and slightly transparent with a small footnote marker.
> The **count** chip carries a small superscript dagger.
>
> **Band C — "The measured ladder" (the tallest band, and the point of the figure)**.
> Four horizontal bars descending left-to-right in a staircase, each bar's LENGTH proportional to
> the residual, a padlock icon at its left end and a bold value at its right end:
> Bar 1, longest, slate blue, open padlock: **"open"** / **"≥ 11453 bits"**.
> Bar 2, amber, about 28% of bar 1: **"content closed"** / **"≥ 3261 bits"**.
> Bar 3, amber, about 16% of bar 1: **"+ filename closed"** / **"1789 bits"**.
> Bar 4, a flat line with a closed red padlock: **"+ dirname closed"** / **"0 bits"**.
> A horizontal dashed charcoal reference line very low, just above bar 4, labelled
> **"20.7 bits = the passcode a successor needs"**.
> A small amber callout beside bar 2 reading **"the control a payload monitor implements"**.
> To the right of the staircase, set apart in a boxed amber panel, the figure's headline:
> large text **"3075 bits"**, and beneath it in smaller text
> **"one encoder, one payload, 8/8 exact"**, and beneath that in smaller grey text
> **"the sum overstates by 186 = 128 count + 58 loss"**.
>
> **Band D — "Cost, and the real store" (slim, split left and right by a thin vertical rule)**.
> LEFT HALF: a two-row mini-table. Row 1 labelled **"content closed"** with a chip
> **"2 mediation points"** and a red-tinted chip **"payload class"**. Row 2 labelled
> **"dirname closed"** with a chip **"6 mediation points"** and a blue-tinted chip
> **"structural class"**. An arrow spanning the two rows labelled **"+4 points, all structural"**.
> RIGHT HALF: three short stacked rows headed **"probed on real infrastructure"**:
> **"real mount body limit: 67,108,864 bytes (8,192x the model)"**,
> **"real timestamps: 1 ns, exact"**,
> **"OCI registry: closes filename only → sits at no rung"**.

---

## Verification table — check every label against this

Run `python paper/render.py --list` and confirm each:

| Label in figure | Claim key | Current value |
|---|---|---|
| `≥ 11453 bits` | `OPEN_BITS` | ≥11453 |
| `≥ 3261 bits` | `CONTENT_BITS` | ≥3261 |
| `1789 bits` | `FILENAME_BITS` | 1789 (uncensored) |
| `0 bits` | `DIRNAME_BITS` | 0 |
| `3075 bits` | `JOINT_BITS` | 3075 |
| `8/8 exact` | `JOINT_TRIALS` | 8/8 |
| `186 = 128 + 58` | `SUM_MINUS_JOINT`, `COUNT_DEP_BITS`, `JOINT_LOSS_BITS` | 186, 128, 58 |
| `20.7 bits` | `PASSCODE_BITS` | 20.7 |
| `2` / `6` / `+4` | `MED_CONTENT` / `MED_DIRNAME` / `MED_EXTRA` | 2 / 6 / 4 |
| `payload` / `structural` | `CONTENT_CLASS` / `DIRNAME_CLASS` | payload / structural |
| `67,108,864 bytes` | `REAL_MAX_BYTES` | 67,108,864 |
| `8,192x` | `BYTES_RATIO` | 8,192 |
| `1 ns, exact` | `REAL_MTIME_NS` | 1 ns, exact |
| eight attribute names | rows of `srm.MATRIX` | content…count |

## The two annotations that must not be dropped

**`order` is greyed deliberately.** It measures **0 bits even fully open**, because `list_dir`
returns entries sorted, so a sender's creation sequence is never observable. This was *confirmed*
on a real mount, not just modelled. It is the figure's cleanest single argument that declared
widths are not capacity — the nominal budget for that row is 1684 bits.

**`count` carries a dagger** because it is the one row still censored at its search ceiling
(≥128), and the joint encoder omits it by construction: an existence pattern determines the entry
count, so including it would double-count. That omission is why the 3075-bit headline contains no
censored quantity, which is the whole of §5.9's argument.

## Do not let the figure claim

- That `≥ 11453` or `≥ 3261` are capacities. They are sums of separately measured cells, and two
  of the rungs still carry a censored row. The **3075** panel is the figure's real number.
- That the ladder was measured on real infrastructure. Band D reports what was *probed* there;
  Bands B and C remain synthetic and the paper says so.

## After generating

```bash
python paper/render.py && cd paper && bash build.sh
```

The placeholder disappears once `figures/methodology.png` exists. **If the figure and the caption
ever disagree, the caption is right** — it is substituted from `results/` at build time and the
image is not.
