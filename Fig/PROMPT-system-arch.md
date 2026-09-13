# Nano Banana prompt — system architecture figure

Target: `Fig/system_arch.png` (repository README and arXiv manuscript).

**Every number below was read from the live artifacts on 14 September 2026.** Re-check before
shipping:

```bash
python paper/render.py --list        # all claim values
```

> ⚠ The current `Fig/system_arch.jpg` is a byte-identical copy of `paper/figures/methodology.jpg`
> — it is the methodology figure, not an architecture figure. This prompt replaces it.

**Changed since the 13 September version of this prompt:** Band E is new, carrying the per-agent
namespace result. The ladder in Band C also gains a rung — `dirname` closure leaves **13** bits,
not zero; only the fixed manifest reaches zero. The earlier prompt had that wrong, and so did the
slide deck until it was corrected.

---

## Read before generating

Image models render text unreliably, and this figure carries numbers whose entire point is that
they were computed rather than asserted. If the model garbles one digit you ship a fabricated
number inside a project whose discipline is that no number is hand-entered.

**Recommended workflow:** generate with the numeric labels *omitted* — boxes, arrows, bands and
category names only — then set every number yourself in Inkscape, Figma or SVG. The layout is the
part worth generating; the numbers are the part you cannot afford to have invented. A variant
prompt for this is at the foot of the file.

If you generate *with* numbers, check every one against §Verification before use.

---

## House style (include verbatim at the top of the prompt)

> Flat vector style on a white background. Technical diagram, not an infographic. Restrained
> palette: charcoal `#2B2B2B` for text and strokes, muted slate blue `#3A6EA5` for actors and data
> flow, warm amber `#D98C2B` for the highlighted result, soft red `#B5453C` for closed or blocked
> states, muted green `#4F7942` for a control that holds, light grey `#EFEFEF` for panel fills.
> Thin 1.5pt strokes. Generous white space. No gradients, no drop shadows, no 3D, no glossy
> effects, no photographic elements, no decorative background. Clean geometric sans-serif labels
> (Inter or Helvetica). Every label horizontal and legible at small print size. Do not add a title,
> a legend, an outer border, page numbers, or any text other than the labels specified.

---

## The prompt

> [paste house style here]
>
> A tall portrait system-architecture diagram, roughly 3:4, in five horizontal bands stacked top to
> bottom, separated by thin light-grey rules. A small bold letter (A, B, C, D, E) at the top-left of
> each band.
>
> **Band A — "One tenant, many agents".**
> On the left, three rounded-square agent icons stacked vertically in slate-blue outline, each with
> a small head-and-shoulders glyph, labelled **"Agent 1"**, **"Agent 2"**, **"Agent n"**. A thin
> dashed grey rectangle encloses all three, labelled at its top edge **"separate sandboxes, one
> tenant"**.
> In the centre, a tall light-grey rounded rectangle labelled **"shared package cache"** with a
> small database-cylinder icon at its top.
> A solid slate-blue arrow from Agent 1 into the cache labelled **"write"**. A solid slate-blue
> arrow from the cache out to Agent n labelled **"read"**, with three small monospace tags beside
> it: `list_dir`, `stat`, `read_file`.
> On the right, a slate-blue shield icon labelled **"authorization control"**, joined to the cache
> by a thin line, with a green check glyph and the small caption **"every check passes"**.
> Caption centred under the band: **"every operation is one the agents are authorized to perform"**.
>
> **Band B — "Eight observable attributes".**
> One horizontal row of eight evenly spaced pill-shaped chips in light grey, each with a tiny icon
> at its left. Left to right, labelled exactly: **content**, **filename**, **dirname**,
> **existence**, **size**, **mtime**, **order**, **count**.
> The **content** chip alone is outlined in soft red with a small magnifying-glass icon and the tiny
> label **"what a payload monitor reads"**.
> A thin bracket spanning all eight, labelled **"a sender can vary, a receiver can observe"**.
>
> **Band C — "Measured residual after closure" (the highlighted band).**
> Five horizontal bars descending left to right in a staircase, each bar's LENGTH proportional to
> its residual on a log scale, a padlock icon at the left end and a bold value at the right end.
> Bar 1, longest, slate blue, open padlock: **"open"** / **"≥ 11,453 bits"**.
> Bar 2, amber with a thin amber halo: **"content closed"** / **"3,075 bits"**.
> Bar 3, amber, shorter: **"+ filename closed"** / **"1,802 bits"**.
> Bar 4, amber, very short: **"+ dirname closed"** / **"13 bits"**.
> Bar 5, a flat line with a closed red padlock: **"+ fixed manifest"** / **"0 bits"**.
> A horizontal dashed charcoal reference line across the band, positioned low between bars 4 and 5,
> labelled **"20.7 bits = the passcode a successor needs"**.
> An amber callout beside bar 2 reading **"the control a payload monitor implements"**.
> To the right of the staircase, a boxed figure in amber reading **"3,075 bits"** with the smaller
> caption beneath **"one encoder, one payload, 8/8 exact"**.
>
> **Band D — "Two monitors, one blind" (slim).**
> Two horizontal gauge bars side by side, each running 0.50 to 1.00, with a small tick at 0.50
> labelled **"chance"**.
> Left gauge, slate blue, needle at the far right: above **"content-carried deposit"**, below
> **"AUC 1.00"**.
> Right gauge, soft red, needle sitting almost exactly on the chance tick: above **"name-carried
> deposit"**, below **"AUC 0.52"**.
> Short bold caption at the right end: **"content inspection does not discharge a non-interference
> requirement"**.
>
> **Band E — "The control this is measured against" (new).**
> Split into two halves by a thin vertical rule.
> LEFT half, headed **"namespacing closes the channel"**: two small agent icons each inside its own
> muted-green rounded box labelled **"agent A namespace"** and **"agent B namespace"**, with a grey
> arrow drawn between them struck through by a green X. Three small stacked labels beneath:
> **"0 of 1,153 artefacts visible"**, **"0 of 320 escapes resolved"**, **"1 mediation point,
> structural"**.
> RIGHT half, headed **"and costs cache reuse"**: a small two-series bar chart, four paired bars,
> x-axis labelled **"2 agents"**, **"8"**, **"16"**, **"16 × 40"**. In each pair the left bar is
> slate blue (**"shared"**) and the right bar amber (**"per-agent"**). Above each pair a small
> multiplier label: **"1.11×"**, **"1.93×"**, **"3.30×"**, **"6.40×"**.
> Caption under the right half: **"the multiplier rises with the overlap that justifies a cache"**.

---

## Verification

Check every rendered label against this before shipping. Source of truth is
`python paper/render.py --list`.

| Label in figure | Must equal | Claim key |
|---|---|---|
| `≥ 11,453 bits` | ≥11453 | `OPEN_BITS` |
| `3,075 bits` (bar 2 and the boxed figure) | 3075 | `JOINT_BITS` |
| `1,802 bits` | 1802 | `FILENAME_BITS` |
| `13 bits` | 13 | `DIRNAME_BITS` |
| `0 bits` | 0 | `EXISTENCE_BITS` |
| `8/8 exact` | 8/8 | `JOINT_TRIALS` |
| `20.7 bits` | 20.7 | `PASSCODE_BITS` |
| `AUC 1.00` | 1.00 | `MON_AUC_CONTENT` |
| `AUC 0.52` | 0.52 | `MON_AUC_NAME` |
| `0 of 1,153 artefacts visible` | 0 / 1153 | `NS_VISIBLE` / `NS_PLANTED` |
| `0 of 320 escapes resolved` | 0 / 320 | `NS_ESCAPES_OK` / `NS_ESCAPES` |
| `1 mediation point` | 1 | `NS_MEDIATION` |
| `1.11×` … `6.40×` | 1.11 … 6.40 | `NS_MIN_MULT` … `NS_WORST_MULT` |
| the eight attribute names | the eight rows of `srm.MATRIX` | `src/srm.py` |

**Four labels that must not be mis-set:**

- Bar 4 is **13, not 0**. The joint coder reports 0 at the `dirname` rung, but that is a limitation
  of an encoder addressing carriers by sender-chosen name — see the `note` field on the dirname row
  of `results/capacity/joint.json` and the `_code_size` docstring in `src/capacity.py`. `size` is
  not neutralised until the fixed-manifest closure. **The previous version of this prompt had this
  wrong.**
- Bar 5, not bar 4, is the zero.
- Bar 2 is the **joint** figure (3,075), never the per-attribute sum (3,261). The paper's rule is
  that no headline is a sum.
- Band E's left half must read as the control **working**. Namespacing wins on capacity and the
  figure should say so; the cost is the right half, not a hedge on the left.

---

## Variant: layout only, numbers added by hand (recommended)

Use the prompt above with two changes:

1. Append to the house style: *"Render no numeric values anywhere. Where a number would appear,
   leave an empty rounded placeholder box of the appropriate width."*
2. Delete every bold value from Bands C, D and E, keeping the bar lengths, staircase, gauges, chart
   shape and all category labels.

Then set the values from §Verification in a vector editor. This is the only route that cannot ship
an invented number.

---

## A note on the alternative

For a repository figure, a diagram rendered from source — Mermaid, TikZ, or hand-authored SVG — is
reproducible, diffable, and cannot hallucinate a digit. It would also regenerate when the artifacts
change, which matters here: three figures in the slide deck went stale within a week, including one
that showed `dirname` closure reaching zero. The paper cannot drift that way because `render.py`
substitutes every number at build time and fails the build on a mismatch. A generated raster is the
better choice only if the visual polish is worth losing that property.
