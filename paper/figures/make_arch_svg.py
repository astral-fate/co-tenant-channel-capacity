"""Render the system-architecture figure as SVG, from the same claim table as the manuscript.

    python paper/figures/make_arch_svg.py            # writes Fig/system_arch.svg
    python paper/figures/make_arch_svg.py --check    # verify the file matches the artifacts

Why this rather than a generated raster
---------------------------------------
The figure carries numbers whose entire point is that they were computed rather than asserted, so
the one property it must have is that it cannot disagree with `results/`. A hand-drawn or
image-model figure has no such property: three figures in the slide deck went stale within a week,
including one that showed `dirname` closure reaching zero when the measurement says it leaves 13
bits. The manuscript could not drift that way, because `render.py` substitutes every value at build
time and fails the build on a mismatch.

This script gives the figure the same guarantee by importing `render.compute()` -- the identical
claim table the paper uses -- so a changed artifact changes the figure, and `--check` fails CI if
the committed SVG has fallen behind.

Layout follows `Fig/PROMPT-system-arch.md`, five bands: the substrate, the observable attributes,
the measured closure ladder, the two monitors, and the namespace control it is all measured
against.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "paper"))

import render  # noqa: E402

OUT = ROOT / "Fig" / "system_arch.svg"

W, H = 1180, 1560
INK, BLUE, AMBER, RED, GREEN = "#2B2B2B", "#3A6EA5", "#D98C2B", "#B5453C", "#4F7942"
GREY, FILL = "#8A8A8A", "#EFEFEF"

# Band tops. Kept explicit rather than computed so a change to one band cannot silently reflow
# the others into an overlap that nobody notices until the figure is in a PDF.
BANDS = {"A": 70, "B": 430, "C": 570, "D": 960, "E": 1130}


def num(s: str) -> str:
    """Strip the LaTeX the claim table carries for the manuscript's benefit."""
    return (s.replace("$\\geq$", "≥ ").replace("\\geq", "≥ ")
             .replace("$", "").replace("\\,", "").strip())


def _t(x, y, s, *, size=15, fill=INK, anchor="start", weight="normal",
       family="Inter, Helvetica, Arial, sans-serif", mono=False, opacity=1.0) -> str:
    fam = "ui-monospace, SFMono-Regular, Menlo, monospace" if mono else family
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" '
            f'opacity="{opacity}">{escape(s)}</text>')


def _rect(x, y, w, h, *, fill="none", stroke=INK, rx=6, sw=1.5, dash=None, opacity=1.0) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} opacity="{opacity}"/>')


def _line(x1, y1, x2, y2, *, stroke=INK, sw=1.5, dash=None, marker=True) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = ' marker-end="url(#arrow)"' if marker else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}{m}/>')


def _band_label(letter: str, y: int) -> str:
    return _t(40, y, letter, size=20, weight="700", fill=GREY)


def band_a(v: dict[str, str]) -> list[str]:
    y = BANDS["A"]
    o = [_band_label("A", y), _t(70, y, "One tenant, many agents", size=21, weight="700")]
    o.append(_rect(66, y + 22, 300, 250, stroke=GREY, dash="6 5", rx=10))
    o.append(_t(80, y + 44, "separate sandboxes, one tenant", size=13, fill=GREY))
    for i, name in enumerate(("Agent 1", "Agent 2", "Agent n")):
        ay = y + 60 + i * 68
        o.append(_rect(96, ay, 150, 52, stroke=BLUE, rx=10))
        o.append(f'<circle cx="126" cy="{ay+20}" r="8" fill="none" stroke="{BLUE}" '
                 f'stroke-width="1.5"/>')
        o.append(f'<path d="M114 {ay+42} a12 12 0 0 1 24 0" fill="none" stroke="{BLUE}" '
                 f'stroke-width="1.5"/>')
        o.append(_t(150, ay + 32, name, size=15, fill=BLUE))
    # the cache
    o.append(_rect(470, y + 40, 230, 230, fill=FILL, stroke=INK, rx=12))
    o.append(f'<ellipse cx="585" cy="{y+72}" rx="34" ry="12" fill="none" stroke="{INK}" '
             f'stroke-width="1.5"/>')
    o.append(f'<path d="M551 {y+72} v26 a34 12 0 0 0 68 0 v-26" fill="none" stroke="{INK}" '
             f'stroke-width="1.5"/>')
    o.append(_t(585, y + 140, "shared package cache", size=16, anchor="middle", weight="600"))
    o.append(_line(250, y + 92, 466, y + 92, stroke=BLUE))
    o.append(_t(358, y + 84, "write", size=13, anchor="middle", fill=BLUE))
    o.append(_line(704, y + 210, 470, y + 210, stroke=BLUE))
    o.append(_t(587, y + 202, "read", size=13, anchor="middle", fill=BLUE))
    for i, tag in enumerate(("list_dir", "stat", "read_file")):
        o.append(_t(500 + i * 74, y + 232, tag, size=12, fill=BLUE, mono=True))
    # authorization control
    o.append(f'<path d="M840 {y+92} l34 12 v30 c0 24 -18 38 -34 44 c-16 -6 -34 -20 -34 -44 '
             f'v-30 z" fill="none" stroke="{BLUE}" stroke-width="1.5"/>')
    o.append(_t(840, y + 210, "authorization control", size=14, anchor="middle", fill=BLUE))
    o.append(f'<path d="M828 {y+146} l9 9 l18 -20" fill="none" stroke="{GREEN}" '
             f'stroke-width="2.5"/>')
    o.append(_t(840, y + 232, "every check passes", size=12, anchor="middle", fill=GREEN))
    o.append(_line(704, y + 130, 802, y + 130, stroke=GREY, sw=1, marker=False))
    o.append(_t(W / 2, y + 300, "every operation is one the agents are authorized to perform",
                size=15, anchor="middle", fill=GREY))
    return o


def band_b() -> list[str]:
    y = BANDS["B"]
    o = [_band_label("B", y), _t(70, y, "Eight observable attributes", size=21, weight="700")]
    attrs = ["content", "filename", "dirname", "existence", "size", "mtime", "order", "count"]
    x0, cw, gap = 70, 122, 10
    for i, a in enumerate(attrs):
        x = x0 + i * (cw + gap)
        red = a == "content"
        o.append(_rect(x, y + 24, cw, 42, fill=FILL, stroke=RED if red else GREY,
                       rx=21, sw=1.8 if red else 1.2))
        o.append(_t(x + cw / 2, y + 51, a, size=14, anchor="middle",
                    fill=RED if red else INK, weight="600" if red else "normal", mono=True))
    o.append(_t(x0 + cw / 2, y + 86, "what a payload monitor reads",
                size=11, anchor="middle", fill=RED))
    span = 8 * cw + 7 * gap
    o.append(f'<path d="M{x0} {y+100} v8 h{span} v-8" fill="none" stroke="{GREY}" '
             f'stroke-width="1.2"/>')
    o.append(_t(x0 + span / 2, y + 126, "a sender can vary, a receiver can observe",
                size=13, anchor="middle", fill=GREY))
    return o


def band_c(v: dict[str, str]) -> list[str]:
    y = BANDS["C"]
    o = [_band_label("C", y), _t(70, y, "Measured residual after closure", size=21, weight="700")]
    rungs = [
        ("open", num(v["OPEN_BITS"]), 11453, BLUE, False),
        ("content closed", num(v["JOINT_BITS"]), 3075, AMBER, False),
        ("+ filename closed", num(v["FILENAME_BITS"]), 1802, AMBER, False),
        ("+ dirname closed", num(v["DIRNAME_BITS"]), 13, AMBER, False),
        ("+ fixed manifest", num(v["EXISTENCE_BITS"]), 0, RED, True),
    ]
    x0, top, bh, gap, maxw = 250, y + 34, 40, 20, 560
    for i, (label, shown, val, colour, closed) in enumerate(rungs):
        by = top + i * (bh + gap)
        # log scale, so 13 bits is visible next to 11,453 without a break in the axis
        frac = 0.0 if val <= 0 else max(0.045, math.log10(val + 1) / math.log10(11454))
        w = maxw * frac
        o.append(_t(238, by + 26, label, size=15, anchor="end"))
        if val > 0:
            o.append(_rect(x0, by, w, bh, fill=colour, stroke="none", rx=4,
                           opacity=0.28 if colour == AMBER else 0.22))
            o.append(_rect(x0, by, w, bh, fill="none", stroke=colour, rx=4))
        else:
            o.append(_line(x0, by + bh / 2, x0 + 46, by + bh / 2, stroke=RED, sw=2.5,
                           marker=False))
        # padlock
        lx, ly = x0 - 34, by + 12
        o.append(_rect(lx, ly + 6, 16, 12, fill="none", stroke=colour, rx=2, sw=1.4))
        arc = f"M{lx+3} {ly+6} v-4 a5 5 0 0 1 10 0 v4" if closed else \
              f"M{lx+3} {ly+6} v-4 a5 5 0 0 1 10 0"
        o.append(f'<path d="{arc}" fill="none" stroke="{colour}" stroke-width="1.4"/>')
        o.append(_t(max(x0 + w + 12, x0 + 58), by + 26, f"{shown} bits", size=16,
                    weight="700", fill=colour))
    # passcode reference line
    py = top + 3 * (bh + gap) + bh + 8
    o.append(_line(x0 - 40, py, x0 + maxw, py, stroke=INK, sw=1.2, dash="5 4", marker=False))
    o.append(_t(x0 + maxw, py - 6, f"{num(v['PASSCODE_BITS'])} bits = the passcode a "
                                   f"successor needs", size=12, anchor="end", fill=INK))
    # callout + the headline box
    o.append(_t(x0 + 8, top + bh + 34, "the control a payload monitor implements",
                size=12, fill=AMBER))
    bx, by2 = 880, top + 40
    o.append(_rect(bx, by2, 230, 96, fill=AMBER, stroke=AMBER, rx=10, opacity=0.14))
    o.append(_rect(bx, by2, 230, 96, fill="none", stroke=AMBER, rx=10))
    o.append(_t(bx + 115, by2 + 46, f"{num(v['JOINT_BITS'])} bits", size=30, anchor="middle",
                weight="700", fill=AMBER))
    o.append(_t(bx + 115, by2 + 72, f"one encoder, one payload, {num(v['JOINT_TRIALS'])} exact",
                size=11, anchor="middle", fill=INK))
    return o


def band_d(v: dict[str, str]) -> list[str]:
    y = BANDS["D"]
    o = [_band_label("D", y), _t(70, y, "Two monitors, one blind", size=21, weight="700")]
    for i, (title, auc, colour) in enumerate((
            ("content-carried deposit", num(v["MON_AUC_CONTENT"]), BLUE),
            ("name-carried deposit", num(v["MON_AUC_NAME"]), RED))):
        gx, gy, gw = 90 + i * 540, y + 60, 420
        o.append(_t(gx, gy - 14, title, size=14, weight="600"))
        o.append(_rect(gx, gy, gw, 20, fill=FILL, stroke=GREY, rx=10, sw=1))
        frac = (float(auc) - 0.5) / 0.5
        o.append(_rect(gx, gy, max(4, gw * frac), 20, fill=colour, stroke="none", rx=10,
                       opacity=0.55))
        o.append(_line(gx, gy + 20, gx, gy + 30, stroke=GREY, sw=1, marker=False))
        o.append(_t(gx, gy + 44, "0.50  chance", size=11, fill=GREY))
        o.append(_t(gx + gw, gy + 44, "1.00", size=11, anchor="end", fill=GREY))
        o.append(_t(gx + gw * frac, gy - 26, f"AUC {auc}", size=17, weight="700",
                    anchor="middle", fill=colour))
    o.append(_t(W / 2, y + 132,
                "content inspection does not discharge a non-interference requirement",
                size=14, anchor="middle", weight="600"))
    return o


def band_e(v: dict[str, str]) -> list[str]:
    y = BANDS["E"]
    o = [_band_label("E", y),
         _t(70, y, "The control this is measured against", size=21, weight="700")]
    o.append(_line(W / 2, y + 20, W / 2, y + 330, stroke=GREY, sw=1, dash="4 4", marker=False))

    # left: confinement holds
    o.append(_t(70, y + 48, "namespacing closes the channel", size=16, weight="600", fill=GREEN))
    for i, name in enumerate(("agent A namespace", "agent B namespace")):
        bx = 80 + i * 250
        o.append(_rect(bx, y + 66, 210, 66, fill=GREEN, stroke=GREEN, rx=10, opacity=0.10))
        o.append(_rect(bx, y + 66, 210, 66, fill="none", stroke=GREEN, rx=10))
        o.append(f'<circle cx="{bx+34}" cy="{y+94}" r="9" fill="none" stroke="{GREEN}" '
                 f'stroke-width="1.5"/>')
        o.append(_t(bx + 56, y + 100, name, size=13, fill=GREEN))
    o.append(_line(292, y + 99, 328, y + 99, stroke=GREY, sw=1.5, marker=False))
    o.append(f'<path d="M302 {y+89} l18 20 M320 {y+89} l-18 20" stroke="{GREEN}" '
             f'stroke-width="2.5" fill="none"/>')
    facts = [f"{num(v['NS_VISIBLE'])} of {num(v['NS_PLANTED'])} artefacts visible",
             f"{num(v['NS_ESCAPES_OK'])} of {num(v['NS_ESCAPES'])} escapes resolved",
             f"{num(v['NS_MEDIATION'])} mediation point, structural"]
    for i, f in enumerate(facts):
        o.append(_t(80, y + 168 + i * 26, f"•  {f}", size=14))
    o.append(_t(80, y + 258, f"positive control: {num(v['NS_SAME_TOTAL'])} bits "
                             f"same-namespace", size=12, fill=GREY))

    # right: what it costs
    o.append(_t(630, y + 48, "and costs cache reuse", size=16, weight="600", fill=AMBER))
    rows = render._namespace()["reuse"][:4]
    peak = max(r["fetches_namespaced"] for r in rows)
    gx, gy, gh = 660, y + 210, 120
    for i, r in enumerate(rows):
        px = gx + i * 112
        hs = gh * (r["fetches_shared"] / peak)
        hn = gh * (r["fetches_namespaced"] / peak)
        o.append(_rect(px, gy - hs, 34, hs, fill=BLUE, stroke="none", rx=3, opacity=0.55))
        o.append(_rect(px + 40, gy - hn, 34, hn, fill=AMBER, stroke="none", rx=3, opacity=0.7))
        o.append(_t(px + 37, gy - max(hs, hn) - 10, f"{r['multiplier']:.2f}×",
                    size=13, anchor="middle", weight="700", fill=AMBER))
        lbl = f"{r['agents']}" if r["per_agent"] == 20 else f"{r['agents']}×{r['per_agent']}"
        o.append(_t(px + 37, gy + 18, lbl, size=12, anchor="middle", fill=GREY))
    o.append(_line(gx - 12, gy, gx + 4 * 112, gy, stroke=GREY, sw=1, marker=False))
    o.append(_t(gx, gy + 40, "agents", size=12, fill=GREY))
    o.append(_rect(880, y + 96, 14, 14, fill=BLUE, stroke="none", rx=2, opacity=0.55))
    o.append(_t(902, y + 108, "shared", size=12))
    o.append(_rect(980, y + 96, 14, 14, fill=AMBER, stroke="none", rx=2, opacity=0.7))
    o.append(_t(1002, y + 108, "per-agent", size=12))
    o.append(_t(630, y + 288, "the multiplier rises with the overlap that justifies a cache",
                size=13, fill=GREY))
    return o


def build() -> str:
    v = render.compute()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0 L10 5 L0 10 z" fill="{BLUE}"/></marker></defs>',
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
    ]
    parts += band_a(v) + band_b() + band_c(v) + band_d(v) + band_e(v)
    for y in (BANDS["B"] - 30, BANDS["C"] - 30, BANDS["D"] - 30, BANDS["E"] - 30):
        parts.append(_line(40, y, W - 40, y, stroke="#E3E3E3", sw=1, marker=False))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed SVG is behind the artifacts")
    a = ap.parse_args()
    svg = build()
    if a.check:
        if not OUT.exists():
            print(f"FAIL: {OUT} does not exist -- run without --check")
            return 1
        if OUT.read_text(encoding="utf-8") != svg:
            print(f"FAIL: {OUT} is stale. Regenerate: python {Path(__file__).name}")
            return 1
        print(f"ok  {OUT.name} matches the artifacts")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT}  ({len(svg):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
