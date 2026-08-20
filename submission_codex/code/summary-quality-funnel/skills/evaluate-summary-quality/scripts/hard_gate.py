#!/usr/bin/env python3
"""Create high-precision draft hard-gate decisions for summary evaluation."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional


TERMINALS = set("。！？!?")
OPEN_TO_CLOSE = {
    "「": "」", "『": "』", "（": "）", "(": ")",
    "【": "】", "[": "]", "〈": "〉", "《": "》",
}
CLOSE_TO_OPEN = {value: key for key, value in OPEN_TO_CLOSE.items()}
PARTICLE_ENDING = re.compile(r"(?:が|を|に|へ|と|から|ので|ため|そして|しかし|また)$")
TERMINAL_RANK = {
    "EMPTY_OUTPUT": 0,
    "VERBATIM_SOURCE_COPY": 1,
    "OBVIOUS_TRUNCATION": 2,
    "OVER_SENTENCE_LIMIT": 3,
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def structural_metrics(text: str) -> Dict[str, Any]:
    stack: List[str] = []
    sentence_count = 0
    segment_has_text = False
    for char in text.strip():
        if char in OPEN_TO_CLOSE:
            stack.append(char)
            segment_has_text = True
        elif char in CLOSE_TO_OPEN:
            if stack and stack[-1] == CLOSE_TO_OPEN[char]:
                stack.pop()
            segment_has_text = True
        elif char in TERMINALS and not stack:
            if segment_has_text:
                sentence_count += 1
                segment_has_text = False
        elif not char.isspace():
            segment_has_text = True
    if segment_has_text:
        sentence_count += 1
    if text.strip() and sentence_count == 0:
        sentence_count = 1

    stripped = text.rstrip()
    final_char = stripped[-1:] if stripped else ""
    missing_terminal_punctuation = bool(stripped and final_char not in TERMINALS)
    hard_truncation = bool(final_char in "、,，：:" or stack)
    suspected_truncation = bool(
        hard_truncation
        or missing_terminal_punctuation
        or PARTICLE_ENDING.search(normalize(stripped))
    )
    return {
        "sentence_count": sentence_count,
        "unclosed_delimiters": stack,
        "final_character": final_char,
        "missing_terminal_punctuation": missing_terminal_punctuation,
        "hard_truncation": hard_truncation,
        "suspected_truncation": suspected_truncation,
    }


def shingle_coverage(candidate: str, source: str, width: int = 12) -> float:
    if not candidate:
        return 0.0
    if len(candidate) < width:
        return float(candidate in source)
    shingles = [candidate[i : i + width] for i in range(len(candidate) - width + 1)]
    return sum(item in source for item in shingles) / len(shingles)


def copy_metrics(article: str, summary: str) -> Dict[str, Any]:
    source = normalize(article)
    candidate = normalize(summary)
    if not candidate:
        return {
            "normalized_chars": 0,
            "full_containment": False,
            "longest_exact_chars": 0,
            "longest_exact_ratio": 0.0,
            "shingle12_coverage": 0.0,
            "hard_copy": False,
        }
    blocks = difflib.SequenceMatcher(
        None, candidate, source, autojunk=False
    ).get_matching_blocks()
    longest = max((block.size for block in blocks), default=0)
    ratio = longest / len(candidate)
    coverage = shingle_coverage(candidate, source)
    contained = len(candidate) >= 30 and candidate in source
    hard_copy = contained or (
        longest >= 60 and ratio >= 0.90 and coverage >= 0.95
    )
    return {
        "normalized_chars": len(candidate),
        "full_containment": contained,
        "longest_exact_chars": longest,
        "longest_exact_ratio": round(ratio, 4),
        "shingle12_coverage": round(coverage, 4),
        "hard_copy": hard_copy,
    }


def draft_terminal(
    result: Dict[str, Any], category: str, stage: str, evidence: Dict[str, Any]
) -> Dict[str, Any]:
    result.update({
        "status": "PENDING_REVIEW",
        "eligible_for_soft_scoring": False,
        "draft_score": 0,
        "draft_terminal_result": category,
        "terminal_rank": TERMINAL_RANK[category],
        "hard_fail": True,
    })
    result["evaluation_trace"].append({
        "stage": stage,
        "result": "DRAFT_TERMINAL_RESULT",
        "evidence": evidence,
    })
    return result


def evaluate(record: Dict[str, Any]) -> Dict[str, Any]:
    article = str(record.get("article", ""))
    summary = str(record.get("summary", ""))
    # Preserve pipeline inputs but explicitly remove dataset-only reference fields.
    result = {key: value for key, value in record.items() if key != "reference_summary"}
    result.update({
        "status": "PENDING",
        "eligible_for_soft_scoring": None,
        "draft_score": None,
        "draft_terminal_result": None,
        "terminal_rank": None,
        "hard_fail": False,
        "evaluation_trace": [],
    })

    if not normalize(summary):
        return draft_terminal(
            result, "EMPTY_OUTPUT", "empty_check", {"normalized_chars": 0}
        )

    copy = copy_metrics(article, summary)
    if copy["hard_copy"]:
        return draft_terminal(
            result, "VERBATIM_SOURCE_COPY", "source_copy_check", copy
        )
    result["evaluation_trace"].append({
        "stage": "source_copy_check", "result": "PASS", "evidence": copy
    })

    shape = structural_metrics(summary)
    sentence_evidence = {
        "sentence_count": shape["sentence_count"], "maximum_allowed": 3
    }
    if shape["sentence_count"] > 3:
        return draft_terminal(
            result,
            "OVER_SENTENCE_LIMIT",
            "sentence_count",
            sentence_evidence,
        )
    result["evaluation_trace"].append({
        "stage": "sentence_count", "result": "PASS", "evidence": sentence_evidence
    })

    # Propose only on evidence a string test can prove. A missing sentence-final
    # character is recorded in the trace and left to the Reviewer, which reads the text.
    if shape["hard_truncation"]:
        return draft_terminal(
            result, "OBVIOUS_TRUNCATION", "truncation_check", shape
        )
    result["evaluation_trace"].append({
        "stage": "truncation_check", "result": "PASS", "evidence": shape,
    })
    result.update({"status": "READY_FOR_RELEVANCE"})
    return result


def read_records(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value if isinstance(value, list) else [value]


def write_records(
    records: List[Dict[str, Any]], path: Optional[Path], jsonl: bool
) -> None:
    if jsonl:
        text = "\n".join(json.dumps(item, ensure_ascii=False) for item in records)
    else:
        value: Any = records[0] if len(records) == 1 else records
        text = json.dumps(value, ensure_ascii=False, indent=2)
    if path:
        path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True,
        help="JSON/JSONL with article and summary fields",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--jsonl", action="store_true", help="write one compact object per line"
    )
    args = parser.parse_args()
    records = [evaluate(record) for record in read_records(args.input)]
    write_records(
        records, args.output, args.jsonl or args.input.suffix.lower() == ".jsonl"
    )


if __name__ == "__main__":
    main()
