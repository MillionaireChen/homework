#!/usr/bin/env python3
"""Validate a concise Markdown report produced by the Report Agent."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_HEADINGS = [
    r"^##\s+1[.、]?\s*输入",
    r"^##\s+2[.、]?\s*(漏斗|流程)",
    r"^##\s+3[.、]?\s*统计",
    r"^##\s+4[.、]?\s*结论",
]


def lexical_units(text: str) -> int:
    without_code = re.sub(r"```.*?```", "", text, flags=re.S)
    cjk = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", without_code)
    ascii_words = re.findall(r"[A-Za-z0-9]+(?:[._%+\-/][A-Za-z0-9]+)*", without_code)
    return len(cjk) + len(ascii_words)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--max-words", type=int, default=800)
    args = parser.parse_args()
    text = args.report.read_text(encoding="utf-8")
    errors = []
    for pattern in REQUIRED_HEADINGS:
        if not re.search(pattern, text, flags=re.M):
            errors.append(f"missing heading matching: {pattern}")
    image_targets = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    if len(image_targets) < 2:
        errors.append("report must embed at least two charts")
    for target in image_targets:
        if "://" not in target and not (args.report.parent / target).exists():
            errors.append(f"missing local image: {target}")
    units = lexical_units(text)
    if units > args.max_words:
        errors.append(f"report has {units} lexical units; maximum is {args.max_words}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"valid report: {args.report} ({units}/{args.max_words} lexical units)")


if __name__ == "__main__":
    main()
