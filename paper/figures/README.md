# Figure assets

`stale/methodology-SUPERSEDED.jpg` is the previous methodology figure. **It is not built into
the paper and must not be.** Its panel labels were rendered when the measurement read
`open >= 4297`, `content >= 201`, `filename >= 64` and `9.7x`. Every one of those has since
moved: the search ceilings were derived from substrate constants rather than chosen, an encoder
defect in the existence row was fixed, and the joint residual is now searched rather than
assumed.

A reviewer caught the mismatch and was right to: the paper claims every value is substituted from
`results/` at build time, and a raster figure with numbers baked into it is the one place that
claim cannot hold. An image cannot be re-rendered by `render.py`.

To restore the figure, regenerate it from `PROMPT-methodology.md` -- whose numbers are refreshed
from the current artifacts -- and save it as `figures/methodology.png`. Until then the manuscript
builds with a visible placeholder saying the asset is absent, which is the honest state.

**Preferred**: generate the diagram with NO numeric labels and add the numbers in a vector editor,
or emit the figure from `results/` as TikZ. Either keeps the build-substitution guarantee intact.
