#!/usr/bin/env python3
"""Validate a deterministic summary-quality Markdown report."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_HEADINGS = [
    r"^##\s+1\.?\s*Input Data\s*$",
    r"^##\s+2\.?\s*Funnel Outcomes\s*$",
    r"^##\s+3\.?\s*Results\s*$",
    r"^##\s+4\.?\s*Conclusion\s*$",
]


def lexical_units(text: str) -> int:
    without_code = re.sub(r"```.*?```", "", text, flags=re.S)
    ascii_words = re.findall(r"[A-Za-z0-9]+(?:[._%+\-/][A-Za-z0-9]+)*", without_code)
    return len(ascii_words)


def validate_report(report: Path, max_words: int = 800) -> int:
    text = report.read_text(encoding="utf-8")
    errors = []
    for pattern in REQUIRED_HEADINGS:
        if not re.search(pattern, text, flags=re.M):
            errors.append(f"missing heading matching: {pattern}")
    image_targets = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    if len(image_targets) < 2:
        errors.append("report must embed at least two charts")
    for target in image_targets:
        if "://" not in target and not (report.parent / target).exists():
            errors.append(f"missing local image: {target}")
    units = lexical_units(text)
    if units > max_words:
        errors.append(f"report has {units} lexical units; maximum is {max_words}")
    if errors:
        raise ValueError("\n".join(errors))
    return units


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--max-words", type=int, default=800)
    args = parser.parse_args()
    try:
        units = validate_report(args.report, args.max_words)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"valid report: {args.report} ({units}/{args.max_words} lexical units)")


if __name__ == "__main__":
    main()
