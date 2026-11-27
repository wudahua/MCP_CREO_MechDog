"""DEV-077: check the declared BACKLOG ID counts against the ledger itself.

The declaration in ``docs/BACKLOG.md`` used to be maintained by hand and went
stale when an ID moved to the completion archive. This module only parses text;
it never edits the ledger, so it can run in a source distribution without Git.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

PREFIXES = ("BUG", "FEAT", "DEV")

_ID_ROW = re.compile(r"^\|\s*\[?(BUG|FEAT|DEV)-(\d+)\]?", re.MULTILINE)
_DECLARED = re.compile(
    r"当前唯一 ID \*\*(\d+)\*\*（BUG \*\*(\d+)\*\*、FEAT \*\*(\d+)\*\*、DEV \*\*(\d+)\*\*）"
)
_COUNTS_SECTION = re.compile(r"^##\s*使用与计数\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
_CATEGORY_ROW = re.compile(r"^\|\s*([^|\n]+?)\s*\|\s*(\d+)\s*\|\s*$", re.MULTILINE)
_SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _parse_sections(text: str) -> tuple[str, dict[str, int], list[str]]:
    """Return ``(preamble, section_id_counts, duplicate_headings)`` split by ``## ``."""
    matches = list(_SECTION_HEADING.finditer(text))
    if not matches:
        return text, {}, []
    preamble = text[: matches[0].start()]
    counts: dict[str, int] = {}
    duplicates: list[str] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        row_count = len(_ID_ROW.findall(body))
        if heading in counts:
            duplicates.append(heading)
            counts[heading] += row_count
        else:
            counts[heading] = row_count
    return preamble, counts, duplicates


def summarize(text: str) -> dict[str, Any]:
    """Compare the declared counts, ID rows, category table and status sections."""
    rows = _ID_ROW.findall(text)
    per_prefix = Counter(prefix for prefix, _ in rows)
    actual = {prefix: per_prefix[prefix] for prefix in PREFIXES}
    identifiers = [f"{prefix}-{number}" for prefix, number in rows]
    duplicates = sorted(name for name, count in Counter(identifiers).items() if count > 1)
    section = _COUNTS_SECTION.search(text)

    declared_categories: dict[str, int] | None = None
    duplicate_category_rows: list[str] = []
    category_total: int | None = None
    if section is not None:
        declared_categories = {}
        for match in _CATEGORY_ROW.finditer(section.group(1)):
            category = match.group(1).strip()
            value = int(match.group(2))
            if category in declared_categories:
                duplicate_category_rows.append(category)
            declared_categories[category] = value
        category_total = sum(declared_categories.values())

    declared_match = _DECLARED.search(text)
    declared = (
        {
            "total": int(declared_match.group(1)),
            "BUG": int(declared_match.group(2)),
            "FEAT": int(declared_match.group(3)),
            "DEV": int(declared_match.group(4)),
        }
        if declared_match is not None
        else None
    )

    preamble, section_counts, duplicate_headings = _parse_sections(text)
    actual_categories: dict[str, int] = {}
    category_mismatches: list[dict[str, Any]] = []

    problems: list[str] = []
    if declared is None:
        problems.append("declared_line_missing")
    else:
        if declared["total"] != len(identifiers):
            problems.append("declared_total")
        for prefix in PREFIXES:
            if declared[prefix] != actual[prefix]:
                problems.append(f"declared_{prefix}")
    if category_total is None:
        problems.append("category_table_missing")
    elif category_total != len(identifiers):
        problems.append("category_total")
    if duplicate_category_rows:
        problems.append("duplicate_category_rows")
    if duplicate_headings:
        problems.append("duplicate_status_headings")
    if _ID_ROW.findall(preamble):
        problems.append("unsectioned_id_rows")
    if declared_categories is not None:
        for category, expected_count in declared_categories.items():
            if category not in section_counts:
                category_mismatches.append(
                    {
                        "category": category,
                        "declared": expected_count,
                        "actual": None,
                        "reason": "missing_section",
                    }
                )
                problems.append(f"category_missing:{category}")
            else:
                actual_count = section_counts[category]
                actual_categories[category] = actual_count
                if actual_count != expected_count:
                    category_mismatches.append(
                        {
                            "category": category,
                            "declared": expected_count,
                            "actual": actual_count,
                            "reason": "count_mismatch",
                        }
                    )
                    problems.append(f"category_mismatch:{category}")
        for category, count in section_counts.items():
            if category not in declared_categories and count > 0:
                actual_categories[category] = count
                category_mismatches.append(
                    {
                        "category": category,
                        "declared": None,
                        "actual": count,
                        "reason": "undeclared_section",
                    }
                )
                problems.append(f"category_undeclared:{category}")
    if duplicates:
        problems.append("duplicate_ids")

    return {
        "declared": declared,
        "actual": actual,
        "actual_total": len(identifiers),
        "category_total": category_total,
        "declared_categories": declared_categories,
        "actual_categories": actual_categories,
        "category_mismatches": category_mismatches,
        "duplicates": duplicates,
        "problems": problems,
        "consistent": not problems,
    }
