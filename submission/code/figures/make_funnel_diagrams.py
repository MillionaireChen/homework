#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit the submission diagrams as editable draw.io files.

One layout spec per diagram -> one `.drawio` (mxGraph XML) file. The `.svg`
files the report embeds are rendered *from* these `.drawio` files by
`render_drawio_svg.py`, so the draw.io file is the single source of truth:
edit it in draw.io, re-run the renderer, and the figure in the report changes.

    python3 make_funnel_diagrams.py --outdir ../../figures
    python3 render_drawio_svg.py ../../figures/*.drawio

Diagrams:
  funnel_pipeline   the funnel: what runs, what exits, how many survive
  plugin_anatomy    what the plugin is made of
  two_plugins       the same design built twice, then cross-validated

Counts come from the two committed 250-pair runs; none is illustrative.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path

BLUE, ORANGE, GREEN, RED, PURPLE, GREY, TEAL = (
    "#4A76D4", "#D98C3F", "#4C9A5E", "#C0392B", "#7B61A8", "#5A6C7D", "#2E8B8B")
BLUE_BG, ORANGE_BG, GREEN_BG, RED_BG, PURPLE_BG, GREY_BG, TEAL_BG = (
    "#E8F0FE", "#FDF0E6", "#E9F6EC", "#FBE3E3", "#F0EDF7", "#EEF1F4", "#E4F2F2")
INK = "#1A2233"


class Scene:
    """Minimal node/edge scene, emitted as mxGraph XML."""

    def __init__(self, name: str, w: int, h: int):
        self.name, self.w, self.h = name, w, h
        self.cells: list[str] = []
        self._n = 0

    def _id(self) -> str:
        self._n += 1
        return f"n{self._n}"

    def node(self, x, y, w, h, label="", *, fill="#FFFFFF", stroke=INK, font=14,
             bold=False, italic=False, align="center", valign="middle",
             rounded=True, dashed=False, color=INK, pad=10):
        style = [f"rounded={1 if rounded else 0}", "whiteSpace=wrap", "html=1",
                 f"fillColor={fill}", f"strokeColor={stroke}", f"fontColor={color}",
                 f"fontSize={font}", f"align={align}", f"verticalAlign={valign}",
                 f"spacingLeft={pad}", f"spacingRight={pad}"]
        if rounded:
            style.append("arcSize=10")
        if bold:
            style.append("fontStyle=1")
        elif italic:
            style.append("fontStyle=2")
        if dashed:
            style.append("dashed=1;dashPattern=6 4")
        nid = self._id()
        value = html.escape(label, quote=True).replace("\n", "&lt;br&gt;")
        self.cells.append(
            f'<mxCell id="{nid}" value="{value}" style="{";".join(style)};" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return nid

    def text(self, x, y, w, h, label, *, font=13, bold=False, italic=False,
             align="left", color=INK, valign="middle"):
        return self.node(x, y, w, h, label, fill="none", stroke="none", font=font,
                         bold=bold, italic=italic, align=align, color=color,
                         valign=valign, rounded=False, pad=0)

    def edge(self, pts, *, color=INK, dashed=False, label="", width=2.0,
             arrow=True, font=12):
        style = ["edgeStyle=none", "rounded=0", f"strokeColor={color}",
                 f"strokeWidth={width}", "html=1", f"fontSize={font}",
                 f"fontColor={color}", "labelBackgroundColor=#FFFFFF",
                 f"endArrow={'blockThin' if arrow else 'none'}", "endFill=1"]
        if dashed:
            style.append("dashed=1;dashPattern=6 4")
        nid = self._id()
        way = "".join(f'<mxPoint x="{x}" y="{y}" as="{k}"/>'
                      for (x, y), k in zip([pts[0], pts[-1]], ("sourcePoint", "targetPoint")))
        mids = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
        arr = f'<Array as="points">{mids}</Array>' if mids else ""
        self.cells.append(
            f'<mxCell id="{nid}" value="{html.escape(label, quote=True)}" style="{";".join(style)};" '
            f'edge="1" parent="1"><mxGeometry relative="1" as="geometry">{way}{arr}</mxGeometry></mxCell>')
        return nid

    def xml(self) -> str:
        return (f'<mxfile host="make_funnel_diagrams.py" type="device">'
                f'<diagram name="{html.escape(self.name)}" id="{html.escape(self.name)}">'
                f'<mxGraphModel dx="{self.w}" dy="{self.h}" grid="0" gridSize="10" guides="1" '
                f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                f'pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">'
                f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{"".join(self.cells)}</root>'
                f'</mxGraphModel></diagram></mxfile>')


# --------------------------------------------------------------------------- #
def diagram_funnel_pipeline() -> Scene:
    """The main flow. Band width is proportional to the pairs still alive."""
    s = Scene("funnel_pipeline", 1140, 920)
    cx, bh, gap = 760, 86, 28
    top, wide, narrow = 104, 600, 320

    def w_of(n):
        return narrow + (wide - narrow) * n / 250

    s.text(0, 26, 1140, 32, "The funnel", font=27, bold=True, align="center")
    s.text(0, 62, 1140, 22, "250 pairs in, 165 scored. Every exit confirmed by an independent reviewer.",
           font=14, color=GREY, align="center")

    bands = [
        (250, "250 pairs\n50 articles x 5 candidates", "#FFFFFF", INK, None),
        (250, "1 · PHYSICAL GATES\ncopy · over 3 sentences · truncation",
         BLUE_BG, BLUE, ("51 terminal", "verbatim copy 50 · truncation 1")),
        (199, "2 · RELEVANCE (embedding, required)\nown article only · never terminal",
         TEAL_BG, TEAL, None),
        (199, "3 · GROUNDING GATE\noff-topic · reversal · fabrication",
         ORANGE_BG, ORANGE, ("29 terminal", "off-topic 16 · reversal 13")),
        (170, "4 · SCORING + REVIEW\nfaithfulness · coverage · coherence · conciseness",
         GREEN_BG, GREEN, ("5 terminal", "fabrication 1 · truncation 4")),
        (165, "165 scored 0-100\nlabel + rank within article", PURPLE_BG, PURPLE, None),
    ]

    geo = []
    y = top
    for n, label, fill, stroke, _ in bands:
        w = w_of(n)
        s.node(cx - w / 2, y, w, bh, label, fill=fill, stroke=stroke, font=15,
               bold=(stroke in (INK, PURPLE)))
        geo.append((y, w))
        y += bh + gap
    for side in (-1, 1):                                   # funnel walls
        pts = []
        for (y0, w) in geo:
            pts += [(cx + side * w / 2, y0), (cx + side * w / 2, y0 + bh)]
        s.edge(pts, color=GREY, width=1.2, arrow=False, dashed=True)
    for i in range(len(geo) - 1):                          # flow
        s.edge([(cx, geo[i][0] + bh), (cx, geo[i + 1][0])], color=GREY, width=2.2)

    for (_, _, _, _, exit_), (y0, w) in zip(bands, geo):   # side exits
        if not exit_:
            continue
        head, detail = exit_
        ex_w = 320
        x = cx - w / 2 - 56 - ex_w
        s.node(x, y0 + 4, ex_w, bh - 8, f"{head}\n{detail}", fill=RED_BG, stroke=RED, font=14)
        s.edge([(cx - w / 2, y0 + bh / 2), (x + ex_w, y0 + bh / 2)], color=RED, width=2.0)

    ty = geo[-1][0] + bh + 42
    s.node(70, ty, 1000, 60, "validate  →  rank within article  →  charts  →  report",
           fill=GREY_BG, stroke=GREY, font=16, bold=True)
    s.text(0, ty + 72, 1140, 22,
           "Scripts propose, agents judge, the reviewer confirms. 80 of 250 pairs never reach the scorer.",
           font=13, italic=True, color=GREY, align="center")
    return s


# --------------------------------------------------------------------------- #
def diagram_plugin_anatomy() -> Scene:
    """What the plugin is made of."""
    s = Scene("plugin_anatomy", 1180, 600)
    s.text(0, 26, 1180, 32, "The evaluator ships as a plugin", font=27, bold=True, align="center")
    s.text(0, 62, 1180, 22, "One install, one command. The plugin runs its own scripts and spawns its own agents.",
           font=14, color=GREY, align="center")

    s.node(400, 106, 380, 60, "/evaluate-summaries", fill=BLUE_BG, stroke=BLUE, font=18, bold=True)
    s.node(350, 200, 480, 68, "skill: evaluate-summary-quality",
           fill=ORANGE_BG, stroke=ORANGE, font=16)
    s.edge([(590, 166), (590, 200)], color=BLUE)

    s.node(90, 316, 470, 190, "", fill=GREEN_BG, stroke=GREEN)
    s.text(116, 330, 420, 26, "scripts — deterministic", font=16, bold=True, color=GREEN)
    for i, t in enumerate(["hard_gate.py", "embedding_gate.py", "validate_result.py",
                           "rank_results.py"]):
        s.text(116, 370 + i * 32, 420, 24, t, font=14)

    s.node(620, 316, 470, 190, "", fill=ORANGE_BG, stroke=ORANGE)
    s.text(646, 330, 420, 26, "agents — one job each", font=16, bold=True, color=ORANGE)
    for i, t in enumerate(["grounding-gate", "scorer", "reviewer", "reporter"]):
        s.text(646, 370 + i * 32, 420, 24, t, font=14)

    s.edge([(500, 268), (325, 316)], color=GREEN)
    s.edge([(680, 268), (855, 316)], color=ORANGE)
    s.text(0, 528, 1180, 24,
           "Each agent runs in a fresh context: the reviewer never inherits the scorer's reasoning.",
           font=13, italic=True, color=GREY, align="center")
    return s


# --------------------------------------------------------------------------- #
def diagram_two_plugins() -> Scene:
    """The same design built twice, then cross-validated."""
    s = Scene("two_plugins", 1180, 620)
    s.text(0, 26, 1180, 32, "One design, two plugins", font=27, bold=True, align="center")
    s.text(0, 62, 1180, 22, "Built for two hosts, run over all 250 pairs, neither seeing the other's output.",
           font=14, color=GREY, align="center")

    s.node(440, 106, 300, 54, "one design", fill="#FFFFFF", stroke=INK, font=17, bold=True)
    s.node(120, 204, 400, 104, "PLUGIN A — Claude Code\n85 terminal · 165 scored",
           fill=BLUE_BG, stroke=BLUE, font=16)
    s.node(660, 204, 400, 104, "PLUGIN B — Codex\n82 terminal · 168 scored",
           fill=ORANGE_BG, stroke=ORANGE, font=16)
    s.edge([(520, 160), (320, 204)], color=BLUE)
    s.edge([(660, 160), (860, 204)], color=ORANGE)

    s.node(120, 352, 940, 132, "", fill=GREEN_BG, stroke=GREEN)
    s.text(146, 366, 900, 26, "cross-validation", font=16, bold=True, color=GREEN)
    stats = [("90.0%", "same routing"), ("100%", "same category when both stop"),
             ("0.897", "score correlation"), ("7.25", "mean difference of 100")]
    for i, (v, t) in enumerate(stats):
        x = 150 + i * 228
        s.node(x, 400, 208, 70, t, fill="#FFFFFF", stroke=GREEN, font=12, valign="bottom")
        s.text(x, 406, 208, 30, v, font=20, bold=True, align="center")
    s.text(0, 508, 1180, 48,
           "The 25 disagreements do not overlap: A stops 14 factual reversals B cannot see,\n"
           "B stops 11 truncations A scores as a penalty instead.",
           font=13, color=INK, align="center")
    return s


DIAGRAMS = {
    "funnel_pipeline": diagram_funnel_pipeline,
    "plugin_anatomy": diagram_plugin_anatomy,
    "two_plugins": diagram_two_plugins,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--only", nargs="*", choices=sorted(DIAGRAMS))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    for name in (args.only or sorted(DIAGRAMS)):
        scene = DIAGRAMS[name]()
        path = args.outdir / f"{name}.drawio"
        path.write_text(scene.xml(), encoding="utf-8")
        print(f"wrote {path}  ({len(scene.cells)} cells, {scene.w}x{scene.h})")


if __name__ == "__main__":
    main()
