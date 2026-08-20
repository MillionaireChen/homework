#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a draw.io (mxGraph) file to SVG.

The `.drawio` files in `figures/` are the editable source of every diagram in
the report; this renderer turns them into the `.svg` files the report embeds.
Edit a diagram in draw.io, re-run this, and the figure updates — no hand-kept
second copy of the layout.

    python3 render_drawio_svg.py ../../figures/*.drawio          # in place, .svg beside
    python3 render_drawio_svg.py in.drawio --output out.svg

Scope: the style vocabulary emitted by `make_funnel_diagrams.py` — rectangles
(square or rounded), edges with waypoints and arrowheads, dashes, fills,
per-cell font size/weight/colour/alignment. draw.io's full shape library is out
of scope on purpose; anything this renderer cannot draw is not used in the
diagrams it is paired with.
"""
from __future__ import annotations

import argparse
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
DEFAULT_STROKE = "#000000"
LINE_HEIGHT = 1.34


def parse_style(style: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (style or "").split(";"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            out[part.strip()] = "1"
    return out


def label_lines(value: str | None) -> list[str]:
    if not value:
        return []
    text = re.sub(r"<br\s*/?>", "\n", value)
    text = re.sub(r"<[^>]+>", "", text)
    return text.split("\n")


def esc(t: str) -> str:
    return html.escape(t, quote=False)


class SvgOut:
    def __init__(self, w: float, h: float):
        self.w, self.h = w, h
        self.body: list[str] = []
        self.markers: set[str] = set()

    def marker(self, color: str) -> str:
        self.markers.add(color)
        return f"arrow-{color.lstrip('#')}"

    def render(self) -> str:
        defs = "".join(
            f'<marker id="arrow-{c.lstrip("#")}" markerWidth="10" markerHeight="10" '
            f'refX="8.5" refY="3" orient="auto" markerUnits="strokeWidth">'
            f'<path d="M0,0 L0,6 L8.5,3 z" fill="{c}"/></marker>' for c in sorted(self.markers))
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w:g}" height="{self.h:g}" '
                f'viewBox="0 0 {self.w:g} {self.h:g}">'
                f'<defs>{defs}</defs>'
                f'<rect width="{self.w:g}" height="{self.h:g}" fill="#FFFFFF"/>'
                f'{"".join(self.body)}</svg>\n')


def draw_vertex(out: SvgOut, cell: ET.Element, st: dict[str, str]) -> None:
    geo = cell.find("mxGeometry")
    if geo is None:
        return
    x, y = float(geo.get("x", 0)), float(geo.get("y", 0))
    w, h = float(geo.get("width", 0)), float(geo.get("height", 0))

    fill = st.get("fillColor", "#FFFFFF")
    stroke = st.get("strokeColor", DEFAULT_STROKE)
    rx = 8 if st.get("rounded") == "1" else 0
    opacity = float(st.get("opacity", 100)) / 100.0
    dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""

    if fill != "none" or stroke != "none":
        f = "none" if fill == "none" else fill
        s = "none" if stroke == "none" else stroke
        out.body.append(
            f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx}" '
            f'fill="{f}" stroke="{s}" stroke-width="1.3" fill-opacity="{opacity:g}"{dash}/>')

    lines = label_lines(cell.get("value"))
    if not lines:
        return
    size = float(st.get("fontSize", 11))
    style_bits = int(st.get("fontStyle", 0) or 0)
    weight = "bold" if style_bits & 1 else "normal"
    italic = ' font-style="italic"' if style_bits & 2 else ""
    color = st.get("fontColor", "#1A2233")
    align = st.get("align", "center")
    valign = st.get("verticalAlign", "middle")
    pad_l = float(st.get("spacingLeft", 0) or 0)
    pad_r = float(st.get("spacingRight", 0) or 0)

    lh = size * LINE_HEIGHT
    block = lh * len(lines)
    if valign == "top":
        first = y + 4 + size * 0.92
    elif valign == "bottom":
        first = y + h - block + size * 0.92 - 4
    else:
        first = y + (h - block) / 2 + size * 0.92

    if align == "left":
        tx, anchor = x + pad_l, "start"
    elif align == "right":
        tx, anchor = x + w - pad_r, "end"
    else:
        tx, anchor = x + w / 2, "middle"

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        out.body.append(
            f'<text x="{tx:g}" y="{first + i * lh:g}" font-family="{FONT}" font-size="{size:g}" '
            f'font-weight="{weight}"{italic} fill="{color}" text-anchor="{anchor}">{esc(line)}</text>')


def edge_points(cell: ET.Element) -> list[tuple[float, float]] | None:
    geo = cell.find("mxGeometry")
    if geo is None:
        return None
    src = geo.find('mxPoint[@as="sourcePoint"]')
    dst = geo.find('mxPoint[@as="targetPoint"]')
    if src is None or dst is None:
        return None
    pts = [(float(src.get("x", 0)), float(src.get("y", 0)))]
    arr = geo.find('Array[@as="points"]')
    if arr is not None:
        pts += [(float(p.get("x", 0)), float(p.get("y", 0))) for p in arr.findall("mxPoint")]
    pts.append((float(dst.get("x", 0)), float(dst.get("y", 0))))
    return pts


def path_midpoint(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Point half way along the polyline, not the middle waypoint."""
    seg = [((pts[i][0] - pts[i + 1][0]) ** 2 + (pts[i][1] - pts[i + 1][1]) ** 2) ** 0.5
           for i in range(len(pts) - 1)]
    half = sum(seg) / 2
    for i, d in enumerate(seg):
        if half <= d or i == len(seg) - 1:
            f = half / d if d else 0
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f,
                    pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)
        half -= d
    return pts[0]


def draw_edge(out: SvgOut, cell: ET.Element, st: dict[str, str]) -> None:
    pts = edge_points(cell)
    if pts is None:
        return
    color = st.get("strokeColor", DEFAULT_STROKE)
    width = float(st.get("strokeWidth", 1.3))
    dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""
    head = ""
    if st.get("endArrow", "classic") not in ("none", "0"):
        head = f' marker-end="url(#{out.marker(color)})"'
    d = "M " + " L ".join(f"{x:g},{y:g}" for x, y in pts)
    out.body.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}"'
                    f' stroke-linejoin="round"{dash}{head}/>')


def draw_edge_label(out: SvgOut, cell: ET.Element, st: dict[str, str]) -> None:
    pts = edge_points(cell)
    if pts is None:
        return
    color = st.get("strokeColor", DEFAULT_STROKE)
    lines = label_lines(cell.get("value"))
    if lines and any(l.strip() for l in lines):
        mid = path_midpoint(pts)
        size = float(st.get("fontSize", 9.5))
        fc = st.get("fontColor", color)
        text = " ".join(l for l in lines if l.strip())
        # a small white plate keeps the label legible where it crosses a line
        out.body.append(
            f'<rect x="{mid[0] - len(text) * size * 0.29:g}" y="{mid[1] - size * 0.95:g}" '
            f'width="{len(text) * size * 0.58:g}" height="{size * 1.5:g}" fill="#FFFFFF" opacity="0.92"/>')
        out.body.append(
            f'<text x="{mid[0]:g}" y="{mid[1] + size * 0.36:g}" font-family="{FONT}" '
            f'font-size="{size:g}" fill="{fc}" text-anchor="middle">{esc(text)}</text>')


def render(path: Path, output: Path | None = None) -> Path:
    root = ET.parse(path).getroot()
    model = root.find(".//mxGraphModel")
    if model is None:
        raise SystemExit(f"{path}: no mxGraphModel")
    w = float(model.get("pageWidth", 1200))
    h = float(model.get("pageHeight", 800))
    out = SvgOut(w, h)

    cells = model.findall("./root/mxCell")
    for cell in cells:                                   # edges under the boxes
        if cell.get("edge") == "1":
            draw_edge(out, cell, parse_style(cell.get("style")))
    for cell in cells:
        if cell.get("vertex") == "1":
            draw_vertex(out, cell, parse_style(cell.get("style")))
    for cell in cells:                                   # labels on top of both
        if cell.get("edge") == "1":
            draw_edge_label(out, cell, parse_style(cell.get("style")))

    dest = output or path.with_suffix(".svg")
    dest.write_text(out.render(), encoding="utf-8")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, help="only valid with a single input")
    args = ap.parse_args()
    if args.output and len(args.inputs) != 1:
        raise SystemExit("--output takes a single input file")
    for src in args.inputs:
        dest = render(src, args.output)
        print(f"rendered {src.name} -> {dest.name}")


if __name__ == "__main__":
    main()
