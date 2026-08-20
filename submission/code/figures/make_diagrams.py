#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the three report diagrams as SVG (and PNG via ImageMagick if present).

The .drawio files in figures/ are the editable source of the same diagrams.
These SVGs are what the report embeds, because a markdown image cannot point at
drawio XML.

    python3 make_diagrams.py --outdir ../../figures
"""
from __future__ import annotations

import argparse
import html
import shutil
import subprocess
from pathlib import Path

# Diagrams are English-only: one family, no CJK fallback needed.
# (ImageMagick's rasteriser does not fall back across a font list.)
FONT = "Helvetica Neue"
BLUE, ORANGE, GREEN, RED, PURPLE, GREY = "#4A76D4", "#D98C3F", "#4C9A5E", "#C0392B", "#7B61A8", "#5A6C7D"
BLUE_BG, ORANGE_BG, GREEN_BG, RED_BG, PURPLE_BG, YELLOW_BG = "#E8F0FE", "#FDF0E6", "#E9F6EC", "#FBE3E3", "#F0EDF7", "#FFF8E1"


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def text(x, y, s, size=11, weight="normal", fill="#1A2233", anchor="start", style=""):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {style}>{esc(s)}</text>')


def lines(x, y, rows, size=10, lh=14, fill="#1A2233", weight="normal", anchor="start"):
    return "".join(text(x, y + i * lh, r, size, weight, fill, anchor) for i, r in enumerate(rows))


def box(x, y, w, h, fill="#FFFFFF", stroke="#333333", rx=3, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.3"{d}/>'


def arrow(x1, y1, x2, y2, color="#333333", dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.6" '
            f'marker-end="url(#a-{color[1:]})"{d}/>')


def svg(w, h, body, colors=(BLUE, ORANGE, GREEN, RED, PURPLE, GREY, "#333333")):
    defs = "".join(
        f'<marker id="a-{c[1:]}" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto">'
        f'<path d="M0,0 L0,6 L8,3 z" fill="{c}"/></marker>' for c in colors)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<defs>{defs}</defs><rect width="{w}" height="{h}" fill="#FFFFFF"/>{body}</svg>')


# --------------------------------------------------------------------------- #
T = {
 "en": {
  "arch_title": "Reference-free summary quality funnel",
  "arch_sub": "Input is one (article, candidate summary) pair. No reference summary at any runtime stage. Nothing terminates without an independent reviewer confirming it.",
  "l1": "LAYER 1 — PHYSICAL HARD CONSTRAINTS   deterministic, no model",
  "l2": "LAYER 2 — SEMANTIC HARD CONSTRAINT   agent judgment, still terminal",
  "l3": "LAYER 3 — SOFT SCORING   graded quality, survivors only",
  "l4": "OUTPUT   validation, ranking, reporting",
  "input": ["INPUT", "(article, candidate)", "250 pairs = 50 x 5"],
  "hg": ["hard_gate.py — string tests only", "empty · over 3 sentences · continuous copy", "trailing comma · unclosed delimiter",
         "proposes, never decides"],
  "rev1": ["summary-reviewer", "terminal pass", "re-derives the evidence itself"],
  "term1": ["TERMINAL", "VERBATIM_SOURCE_COPY  tier 1", "OBVIOUS_TRUNCATION  tier 2", "OVER_SENTENCE_LIMIT  tier 3"],
  "note1": "Ordinary entity, number or quotation overlap is not copying. A particle ending is suspicion, not proof. A REJECT sends the candidate onward.",
  "emb": ["embedding_gate.py — optional hint", "qwen3-embedding:0.6b", "candidate vs its OWN article only",
          "no cross-article rank, no margin", "NEVER TERMINAL"],
  "gate2": ["summary-grounding-gate  (agent)", "one question: is the candidate grounded in its article?",
            "OFF_TOPIC · FACTUAL_REVERSAL · FABRICATED_CONTENT",
            "never sees the anchor, the rubric, or another article", "never produces a score"],
  "rev2": ["summary-reviewer — grounding pass", "reproduces both cited spans itself"],
  "term2": ["TERMINAL  tier 0", "OFF_TOPIC", "FACTUAL_REVERSAL", "FABRICATED_CONTENT"],
  "cent": ["THE CENTRALITY BOUNDARY",
           "Terminal only when the defect is CENTRAL: main event negated,",
           "outcome inverted, or the core claim invented.",
           "A wrong peripheral figure, a wrong secondary entity, or one added",
           "unsupported detail stays GROUNDED and costs faithfulness points.",
           "Deletion test: remove the bad sentence — does the summary still stand?"],
  "note2": "Why a separate agent: the most dangerous candidate is fluent, on topic, correct length, not copied — and asserts the opposite of the article. String rules cannot see it, and embedding similarity stays HIGH precisely because the subject matter is right.",
  "anchor": ["anchor pass  (article only)", "main_event + key_facts + anchor_summary",
             "one per article, cached, generated BEFORE candidates", "a coverage aid, never ground truth"],
  "scorer": ["summary-scorer", "atomic claim checks with cited source spans",
             "SUPPORTED · CONTRADICTED · NOT_IN_SOURCE",
             "faithfulness 50 | coverage 30 | coherence 15 | conciseness 5"],
  "rev3": ["summary-reviewer", "soft-score pass", "rechecks every claim,", "arithmetic and label band"],
  "back": ["SEMANTIC BACKSTOP", "A claim-by-claim audit exposes what the gate missed.",
           "The Scorer may PROPOSE a semantic terminal; the Reviewer may ESCALATE.",
           "This run: fired 4 times, all on candidates the gate layer had released, 1 confirmed."],
  "bands": ["EXCELLENT 90-100", "GOOD 75-89", "FINE 65-74", "MIXED 50-64", "POOR 0-49"],
  "note3": "REVISE — one Scorer revision, then reviewed again. Unresolved disagreement is preserved as LOW_CONFIDENCE, never silently averaged.",
  "out": [["validate_result.py", "schema · ranges", "dimension sums · trace"],
          ["rank_results.py", "within-article order:", "terminal tiers, then score"],
          ["make_report_charts.py", "deterministic stats", "and charts"],
          ["summary-reporter", "writes the conclusion only,", "never invents a number"]],
  "approve": "APPROVE", "reject": "REJECT / passed", "grounded": "GROUNDED / REJECT",
  "escalate": "ESCALATE", "hint": "hint",
 },
}


def diagram_architecture(L) -> str:
    b = []
    b.append(text(600, 32, L["arch_title"], 20, "bold", "#1A2233", "middle"))
    b.append(text(600, 54, L["arch_sub"], 10.5, "normal", GREY, "middle"))

    for y, h, lab, col, bg in [(72, 150, L["l1"], BLUE, BLUE_BG), (234, 252, L["l2"], ORANGE, ORANGE_BG),
                               (502, 238, L["l3"], GREEN, GREEN_BG), (752, 106, L["l4"], PURPLE, PURPLE_BG)]:
        b.append(box(30, y, 1140, h, bg, col, 5))
        b.append(text(44, y + 19, lab, 12, "bold", col))

    # layer 1
    b.append(box(48, 96, 148, 62, "#FFFFFF", "#333333"))
    b.append(lines(58, 116, L["input"], 10.5, 15, weight="bold"))
    b.append(box(232, 92, 316, 70, "#FFFFFF", BLUE))
    b.append(lines(244, 110, L["hg"][:3], 9.5, 13.5))
    b.append(text(244, 152, L["hg"][3], 9, "normal", GREY))
    b.append(box(586, 96, 196, 62, YELLOW_BG, "#C8A415"))
    b.append(lines(598, 116, L["rev1"], 9.5, 14))
    b.append(box(822, 92, 326, 70, RED_BG, RED))
    b.append(lines(834, 110, L["term1"], 9.5, 14, fill="#7B241C"))
    b.append(text(48, 208, L["note1"], 9, "normal", GREY))

    # layer 2
    b.append(box(48, 262, 318, 86, "#FFFFFF", GREY, 3, "5,3"))
    b.append(lines(60, 280, L["emb"][:4], 9, 13, fill=GREY))
    b.append(text(60, 338, L["emb"][4], 9.5, "bold", GREY))
    b.append(box(400, 262, 428, 86, "#FFFFFF", ORANGE))
    b.append(lines(412, 280, L["gate2"], 9.5, 13.5))
    b.append(box(862, 262, 286, 58, YELLOW_BG, "#C8A415"))
    b.append(lines(874, 282, L["rev2"], 9.5, 14))
    b.append(box(862, 352, 286, 72, RED_BG, RED))
    b.append(lines(874, 372, L["term2"], 9.5, 14, fill="#7B241C"))
    b.append(box(48, 358, 780, 92, "#FFF3E0", ORANGE, 3, "5,3"))
    b.append(text(60, 376, L["cent"][0], 11, "bold", "#8A4B00"))
    b.append(lines(60, 393, L["cent"][1:], 9, 12.5, fill="#8A4B00"))
    n2 = L["note2"]
    cut = n2.rfind(" ", 0, int(len(n2) * 0.55))
    b.append(text(48, 464, n2[:cut].strip(), 9, "normal", GREY))
    b.append(text(48, 476, n2[cut:].strip(), 9, "normal", GREY))

    # layer 3
    b.append(box(48, 530, 352, 76, "#FFFFFF", GREEN))
    b.append(lines(60, 548, L["anchor"], 9.5, 13.5))
    b.append(box(434, 530, 394, 76, "#FFFFFF", GREEN))
    b.append(lines(446, 548, L["scorer"], 9.5, 13.5))
    b.append(box(862, 530, 286, 76, YELLOW_BG, "#C8A415"))
    b.append(lines(874, 548, L["rev3"], 9.5, 14))
    b.append(box(48, 624, 690, 76, YELLOW_BG, "#C8A415", 3, "5,3"))
    b.append(text(60, 642, L["back"][0], 11, "bold", "#7A5C00"))
    b.append(lines(60, 659, L["back"][1:], 9, 13, fill="#7A5C00"))
    b.append(box(772, 624, 376, 76, GREEN_BG, GREEN))
    b.append(text(784, 648, "  ·  ".join(L["bands"][:3]), 9.5, "normal", "#1F5B2E"))
    b.append(text(784, 668, "  ·  ".join(L["bands"][3:]), 9.5, "normal", "#1F5B2E"))
    b.append(text(48, 722, L["note3"], 9, "normal", GREY))

    # output
    for i, col in enumerate(L["out"]):
        x = 48 + i * 285
        b.append(box(x, 780, 262, 60, "#FFFFFF", PURPLE))
        b.append(lines(x + 12, 799, col, 9.5, 13))

    # edges
    b.append(arrow(196, 127, 228, 127))
    b.append(arrow(548, 127, 582, 127))
    b.append(text(802, 84, L["approve"], 8.5, "normal", RED, "middle"))
    b.append(arrow(782, 127, 818, 127, RED))
    b.append('<path d="M684,158 L684,186 L560,186 L560,258" fill="none" stroke="#333333" stroke-width="1.5" marker-end="url(#a-333333)"/>')
    b.append(text(692, 178, L["reject"], 8.5, "normal", GREY))
    b.append(arrow(366, 300, 396, 300, GREY, "4,3"))
    b.append(text(381, 293, L["hint"], 8, "normal", GREY, "middle"))
    b.append(arrow(828, 296, 858, 296, ORANGE))
    b.append(arrow(1005, 320, 1005, 348, RED))
    b.append(text(1013, 340, L["approve"], 8.5, "normal", RED))
    b.append('<path d="M862,291 L842,291 L842,494 L224,494 L224,526" fill="none" stroke="#333333" stroke-width="1.5" marker-end="url(#a-333333)"/>')
    b.append(text(560, 489, L["grounded"], 8.5, "normal", GREY))
    b.append(arrow(400, 568, 430, 568, GREEN))
    b.append(arrow(828, 568, 858, 568, GREEN))
    b.append(f'<path d="M1148,552 L1176,552 L1176,402 L1152,402" fill="none" stroke="{RED}" stroke-width="1.4" stroke-dasharray="4,3" marker-end="url(#a-C0392B)"/>')
    b.append(text(1170, 478, L["escalate"], 8, "normal", RED, "end"))
    b.append(f'<path d="M1005,606 L1005,738 L179,738 L179,776" fill="none" stroke="{GREEN}" stroke-width="1.5" marker-end="url(#a-4C9A5E)"/>')
    for i in range(3):
        b.append(arrow(48 + i * 285 + 262, 810, 48 + (i + 1) * 285, 810, PURPLE))
    return svg(1200, 872, "".join(b))


def diagram_results() -> str:
    b = []
    b.append(text(600, 32, "Funnel outcomes on the same 250 pairs — two independent implementations", 19, "bold", "#1A2233", "middle"))
    b.append(text(600, 53, "50 articles x 5 candidates. Neither used a reference summary at runtime; neither saw the other's output.", 10.5, "normal", GREY, "middle"))

    def funnel(y0, name, col, bg, stages, exits, band):
        o = [text(48, y0, name, 12, "bold", col)]
        widths = [520, 448, 376, 300]
        for i, (lab, n) in enumerate(stages):
            w = widths[i]; x = 48 + (520 - w) // 2
            o.append(box(x, y0 + 12 + i * 44, w, 38, bg, col, 3))
            o.append(text(x + 14, y0 + 36 + i * 44, lab, 11, "bold" if i in (0, 3) else "normal"))
            o.append(text(x + w - 14, y0 + 36 + i * 44, str(n), 13, "bold", col, "end"))
        for i, rows in enumerate(exits):
            if not rows: continue
            o.append(box(600, y0 + 14 + i * 44, 300, 34, RED_BG, RED, 3))
            o.append(text(612, y0 + 28 + i * 44, rows[0], 9, "bold", "#7B241C"))
            o.append(text(612, y0 + 41 + i * 44, rows[1], 8.5, "normal", "#7B241C"))
            o.append(arrow(568 + (520 - widths[i]) // 2, y0 + 31 + i * 44, 596, y0 + 31 + i * 44, RED))
        o.append(text(930, y0 + 30, band[0], 9.5, "normal", col))
        o.append(text(930, y0 + 46, band[1], 9.5, "normal", col))
        return "".join(o)

    b.append(funnel(88, "IMPLEMENTATION A — Claude plugin  (two hard-constraint layers, grounding-gate agent)", BLUE, BLUE_BG,
        [("INPUT", 250), ("passed string gates", 199), ("passed grounding gate", 170), ("SOFT-SCORED", 165)],
        [None,
         ["- 51 terminal", "50 verbatim copy · 1 truncation"],
         ["- 29 terminal", "16 off-topic · 13 factual reversal"],
         ["- 5 terminal  (reviewer backstop)", "4 truncation stubs · 1 fabricated"]],
        ["scores 35-98, median 79", "EXC 28 · GOOD 66 · FINE 34 · MIXED 25 · POOR 12"]))

    b.append(funnel(300, "IMPLEMENTATION B — Codex plugin  (deterministic gates + relevance review, no grounding-gate agent)", ORANGE, ORANGE_BG,
        [("INPUT", 250), ("passed deterministic gates", 197), ("passed relevance review", 181), ("SOFT-SCORED", 168)],
        [None,
         ["- 66 terminal in total", "50 verbatim copy · 16 truncation"],
         ["- 16 terminal", "16 off-topic  (19 suspects, 3 released)"],
         ["13 hard failures recovered", "downstream by review"]],
        ["scores 32-100, median 85", "EXC 65 · GOOD 49 · MIXED 42 · POOR 12  (no FINE tier)"]))

    b.append(text(48, 520, "CROSS-VALIDATION — the two implementations against each other", 13, "bold", "#1F5B2E"))
    cards = [("ROUTING AGREEMENT", "90.0%", ["225 of 250 routed the same way", "71 both terminal · 154 both scored"]),
             ("TERMINAL CATEGORY", "71 / 71 = 100%", ["where both terminated, both chose", "the same category. Zero mismatches."]),
             ("SCORE AGREEMENT", "Spearman 0.897", ["on the 154 pairs both scored", "mean absolute difference 7.2 of 100"]),
             ("WITHIN-ARTICLE ORDER", "0 inversions / 50", ["no planted bad summary ranked", "above a reference-grade one"])]
    for i, (h, big, rows) in enumerate(cards):
        x = 48 + i * 282
        b.append(box(x, 534, 262, 84, GREEN_BG, GREEN, 4))
        b.append(text(x + 12, 552, h, 9, "bold", "#1F5B2E"))
        b.append(text(x + 12, 574, big, 15, "bold", "#1F5B2E"))
        b.append(lines(x + 12, 592, rows, 8.5, 12, fill="#1F5B2E"))

    b.append(text(48, 648, "ALL 25 DISAGREEMENTS ATTRIBUTE TO ONE RULE DIFFERENCE — and the two sets do not overlap", 12, "bold", "#7B241C"))
    b.append(box(48, 660, 540, 76, "#EEF3FF", BLUE, 4))
    b.append(lines(60, 680, ["14 terminal in A only — 13 factual reversal, 1 fabricated content",
                             "weak label: 14 / 14 are GENERATED candidates",
                             "B has no grounding-gate agent and cannot reach this class. B scored them 60-94."], 9.5, 15))
    b.append(box(608, 660, 544, 76, "#FFF6EC", ORANGE, 4))
    b.append(lines(620, 680, ["11 terminal in B only — all obvious truncation",
                              "weak label: 11 / 11 are REF_TRUNCATED fragments",
                              "A makes truncation a scaled penalty and scored them 39-70 instead of zero."], 9.5, 15))
    b.append(text(48, 758, "Reading: the implementations never disagree about WHICH candidates are defective, only about SEVERITY, and each disagreement set maps onto exactly one documented rule choice.", 10, "normal", GREY))
    return svg(1200, 780, "".join(b))


def diagram_failures() -> str:
    b = []
    b.append(text(600, 32, "What the data contains, and which detector each failure needs", 19, "bold", "#1A2233", "middle"))
    b.append(text(600, 53, "Found by reading all 250 candidates against their articles. Counts are what the corpus holds, established offline by exact comparison.", 10.5, "normal", GREY, "middle"))

    cols = [(48, 356, "CHEAP AND CERTAIN", "a string test proves it", BLUE, BLUE_BG),
            (420, 356, "CHEAP AND DIRECTIONAL", "an embedding hints, never decides", ORANGE, ORANGE_BG),
            (792, 360, "EXPENSIVE AND NECESSARY", "only reading the article decides", RED, RED_BG)]
    for x, w, h1, h2, col, bg in cols:
        b.append(box(x, 72, w, 320, bg, col, 5))
        b.append(text(x + w / 2, 94, h1, 11.5, "bold", col, "middle"))
        b.append(text(x + w / 2, 110, h2, 9.5, "normal", col, "middle"))

    b.append(box(64, 124, 324, 104, "#FFFFFF", BLUE))
    b.append(text(76, 144, "Verbatim copy of the article", 10.5, "bold"))
    b.append(text(76, 161, "51 in corpus", 11, "bold", BLUE))
    b.append(lines(76, 179, ["The candidate is the article's own opening block,",
                             "caption and byline included. One even reproduces",
                             "a typo from the source.",
                             "Detector: normalized containment + shingle coverage"], 8.8, 12.5))
    b.append(box(64, 244, 324, 104, "#FFFFFF", BLUE))
    b.append(text(76, 264, "Truncated fragment", 10.5, "bold"))
    b.append(text(76, 281, "17 in corpus", 11, "bold", BLUE))
    b.append(lines(76, 299, ["A reference summary cut mid-sentence. Two kinds:",
                             "· amputated mid-token — visibly broken",
                             "· noun-final (taigen-dome) — reads as headline register",
                             "Detector: final character + unclosed delimiter"], 8.8, 12.5))
    b.append(text(64, 368, "Over three sentences — 0 here, kept for production traffic.", 8.8, "normal", GREY))

    b.append(box(436, 124, 324, 224, "#FFFFFF", ORANGE))
    b.append(text(448, 144, "Wrong article entirely", 10.5, "bold"))
    b.append(text(448, 161, "16 in corpus", 11, "bold", ORANGE))
    b.append(lines(448, 179, ["Each is another article's reference summary filed",
                              "under this one. No shared actor, place or event.", "",
                              "Embedding separation, measured offline:",
                              "   matched      0.71 - 0.87   mean 0.80",
                              "   mismatched   0.16 - 0.40   mean 0.27",
                              "   gap 0.31, reproduced on two disjoint samples", "",
                              "The embedding NOMINATES, a reviewer confirms:",
                              "19 nominated, 16 confirmed, 3 correctly released."], 8.8, 12.5))
    b.append(text(436, 368, "Similarity cannot grade quality — a copy, a hallucination", 8.8, "normal", "#8A4B00"))
    b.append(text(436, 380, "and a reversal all stay highly similar to their article.", 8.8, "normal", "#8A4B00"))

    b.append(box(808, 124, 328, 104, "#FFFFFF", RED))
    b.append(text(820, 144, "Factual reversal", 10.5, "bold"))
    b.append(lines(820, 162, ["Asserts the opposite of the central event:",
                              "closure announced -> called off · settled -> refused",
                              "Fluent, on topic, right length, not copied.",
                              "Detector: grounding-gate agent + reviewer"], 8.8, 12.5))
    b.append(box(808, 244, 328, 132, "#FFFFFF", RED))
    b.append(text(820, 264, "Fabricated content", 10.5, "bold"))
    b.append(lines(820, 282, ["An invented event, quotation or figure — almost",
                              "always ATTACHED to a correct main event, which",
                              "makes it the hardest category to adjudicate."], 8.8, 12.5))
    b.append(text(820, 328, "Entity and number substitution", 10.5, "bold"))
    b.append(lines(820, 344, ["Mashhad -> Tabriz · 52 -> 72 arrests · Russia -> Iran",
                              "Detector: atomic claim checks with cited spans"], 8.8, 12.5))

    b.append(text(48, 418, "THE LINE THAT DECIDES SEVERITY — centrality, not conspicuousness", 13, "bold", "#7B241C"))
    b.append(box(48, 430, 540, 158, RED_BG, RED, 4))
    b.append(text(60, 450, "CENTRAL DEFECT → terminal, score 0", 10.5, "bold", "#7B241C"))
    b.append(lines(60, 468, ["the main event is negated, the outcome inverted, or the",
                             "invented text DISPLACES what the article says.", "",
                             "Worked example — 41875333_aa36a21a",
                             "Headline: \"the US stresses its resolve\". Body: \"no dictator should",
                             "underestimate US resolve\". The candidate instead quotes \"the US is",
                             "no longer the world\'s policeman\" — absent, and opposite. Terminal.",
                             "A sibling that compressed the real sentence scored 95."], 8.8, 13, fill="#7B241C"))
    b.append(box(608, 430, 544, 158, "#FFF6EC", ORANGE, 4))
    b.append(text(620, 450, "PERIPHERAL DEFECT → stays in scoring, heavy faithfulness penalty", 10.5, "bold", "#8A4B00"))
    b.append(lines(620, 468, ["a wrong secondary entity or figure, or one invented claim",
                              "standing BESIDE a correctly stated central event.", "",
                              "Worked example — 50469832_8a6e1840",
                              "Sentence 1 states the real policy shift correctly. Sentence 2",
                              "invents an emergency UN Security Council session and a",
                              "unanimous condemnation, chained on with \"in response to this\".",
                              "Not terminal: faithfulness 12 of 50, total 50, MIXED."], 8.8, 13, fill="#8A4B00"))
    b.append(text(48, 606, "Deletion test — remove the defective sentence: if the summary still stands, the defect is peripheral.", 10, "bold", GREY))

    b.append(text(48, 638, "WHAT THE RUN SHOWED ABOUT THIS LINE", 12, "bold", "#1F5B2E"))
    b.append(box(48, 650, 1104, 92, GREEN_BG, GREEN, 4))
    b.append(lines(60, 670, ["All 8 FABRICATED_CONTENT proposals from the gate were released at grounding review. The scorer's claim audit then re-proposed 4 of them —",
                             "every one a candidate the gate layer had let go — and 1 was confirmed terminal. Reversal and off-topic behaved oppositely: 13 and 16 proposals, 100% confirmed.",
                             "",
                             "Reading: reversal and off-topic are central by construction. Fabrication usually is not, so the gate-level fabrication rubric is tuned conservatively",
                             "and the claim-level backstop is what actually catches the central cases."], 9, 14, fill="#1F5B2E"))
    return svg(1200, 762, "".join(b))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    L = T["en"]

    for name, fn in [("funnel_architecture", lambda: diagram_architecture(L)),
                     ("funnel_results", diagram_results),
                     ("failure_modes", diagram_failures)]:
        out = args.outdir / f"{name}.svg"
        out.write_text(fn(), encoding="utf-8")
        print("wrote", out)
        if shutil.which("magick"):
            png = out.with_suffix(".png")
            subprocess.run(["magick", "-density", "160", "-background", "white",
                            str(out), str(png)], check=False)
            print("wrote", png)


if __name__ == "__main__":
    main()
