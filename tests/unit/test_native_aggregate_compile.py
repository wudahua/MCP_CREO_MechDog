"""DEV-082: the aggregate TU must compile without the optional Probbl.h.

The 0.19.3 feedback showed the header-gate contract tests passing while
``native/generic.cpp`` still failed with C2065/C3861 on a Creo 10 SDK: the
guarded symbols lived in ``surface_loft.cpp`` while ``surface_boundary_fill.cpp``
referenced them unconditionally. Those tests only inspected ``#include`` lines
and a single isolated TU, so nothing checked cross-file symbol visibility.

Since 2026-11-12 the gate is the boundary-blend element ids
(``MECHDOG_HAS_BNBLN_TREE``), not ``__has_include(<Probbl.h>)``: Creo 10 ships
the ids in ``ProElemId.h`` and only lacks the documentation header.

This module is the static half of the gate. It never compiles: it reads the
handwritten sources, collects the symbols that only exist inside a
``MECHDOG_HAS_BNBLN_TREE`` region, and fails when another file references one
of them outside an equivalent guard. That is exactly the shape of the C2065 /
C3861 failure and it runs in CI without a Toolkit SDK.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native"
DEFINING_FILE = "surface_loft.cpp"
CONSUMER_FILE = "surface_boundary_fill.cpp"
GATE = "MECHDOG_HAS_BNBLN_TREE"

_DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")
# Only file-scope `static` declarations are collected: they are the helpers the
# gate hides. Control statements and member access never match this shape.
_DECLARATION = re.compile(
    r"^\s*static\s+(?:constexpr\s+)?(?:inline\s+)?"
    r"[A-Za-z_][\w:<>,\s\*&]*?\b([A-Za-z_]\w*)\s*(?:\(|=|\[)"
)


def _sources() -> list[Path]:
    return sorted(p for p in NATIVE.glob("*.cpp") if p.name != DEFINING_FILE)


def _strip_comments(text: str) -> str:
    """Blank out // and /* */ comments without moving any line boundary."""
    out: list[str] = []
    in_block = False
    for line in text.splitlines():
        kept: list[str] = []
        index = 0
        while index < len(line):
            if in_block:
                end = line.find("*/", index)
                if end < 0:
                    index = len(line)
                else:
                    in_block = False
                    index = end + 2
                continue
            start = line.find("//", index)
            block = line.find("/*", index)
            if start >= 0 and (block < 0 or start < block):
                kept.append(line[index:start])
                index = len(line)
            elif block >= 0:
                kept.append(line[index:block])
                index = block + 2
                in_block = True
            else:
                kept.append(line[index:])
                index = len(line)
        out.append("".join(kept))
    return "\n".join(out)


def _branch_declarations(text: str, gate: str = GATE) -> tuple[set[str], set[str]]:
    """Split declarations into (gate-defined branch, everything else)."""
    inside: set[str] = set()
    outside: set[str] = set()
    stack: list[bool] = []  # True when the enclosing branch requires the gate
    for line in _strip_comments(text).splitlines():
        directive = _DIRECTIVE.match(line)
        if directive:
            kind, rest = directive.group(1), directive.group(2)
            if kind in ("if", "ifdef", "ifndef"):
                stack.append(gate in rest)
            elif kind == "elif":
                if stack:
                    stack[-1] = gate in rest
            elif kind == "else":
                if stack:
                    stack[-1] = False
            elif kind == "endif":
                if stack:
                    stack.pop()
            continue
        match = _DECLARATION.match(line)
        if not match:
            continue
        if stack and all(stack):
            inside.add(match.group(1))
        else:
            outside.add(match.group(1))
    return inside, outside


def _guarded_symbols(text: str, gate: str = GATE) -> set[str]:
    """Symbols that exist only while the gate macro is defined.

    A symbol declared both inside the gate and in its ``#else``/stub branch is
    available on either build, so it is not a cross-file hazard.
    """
    inside, outside = _branch_declarations(text, gate)
    return inside - outside


def _unguarded_references(path: Path, symbol: str, gate: str = GATE) -> list[int]:
    """Line numbers where ``symbol`` is used outside a gate region."""
    hits: list[int] = []
    stack: list[bool] = []
    text = _strip_comments(path.read_text(encoding="utf-8"))
    for number, line in enumerate(text.splitlines(), start=1):
        directive = _DIRECTIVE.match(line)
        if directive:
            kind, rest = directive.group(1), directive.group(2)
            if kind in ("if", "ifdef", "ifndef"):
                stack.append(gate in rest)
            elif kind == "elif":
                if stack:
                    stack[-1] = gate in rest
            elif kind == "else":
                if stack:
                    stack[-1] = False
            elif kind == "endif":
                if stack:
                    stack.pop()
            continue
        if stack and all(stack):
            continue
        if re.search(rf"(?<![\w]){re.escape(symbol)}(?![\w])", line):
            hits.append(number)
    return hits


def _gate_regions_balanced(text: str, gate: str = GATE) -> bool:
    depth = 0
    for line in text.splitlines():
        directive = _DIRECTIVE.match(line)
        if not directive:
            continue
        kind, rest = directive.group(1), directive.group(2)
        if kind in ("if", "ifdef", "ifndef"):
            if gate in rest:
                depth += 1
        elif kind == "endif" and depth:
            depth -= 1
    return depth == 0


class AggregateCompileContractTests(unittest.TestCase):
    def test_guarded_symbols_are_collected_from_the_defining_tu(self):
        symbols = _guarded_symbols((NATIVE / DEFINING_FILE).read_text(encoding="utf-8"))
        self.assertIn("SURFACE_LOFT_TREE_SAMPLE_LIMIT", symbols)
        self.assertIn("loft_element_json", symbols)

    def test_no_other_tu_references_a_guarded_symbol_without_the_same_gate(self):
        symbols = _guarded_symbols((NATIVE / DEFINING_FILE).read_text(encoding="utf-8"))
        self.assertTrue(symbols)
        problems: list[str] = []
        for path in _sources():
            for symbol in sorted(symbols):
                for line in _unguarded_references(path, symbol):
                    problems.append(f"{path.name}:{line} uses {symbol} outside {GATE}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_boundary_fill_body_is_gated_and_publishes_a_reason_when_missing(self):
        text = (NATIVE / CONSUMER_FILE).read_text(encoding="utf-8")
        self.assertIn(f"#if {GATE}", text)
        self.assertRegex(text, rf"#else\s+//\s*{GATE} == 0")
        self.assertIn("SURFACE_BOUNDARY_FILL_SDK_UNAVAILABLE", text)
        self.assertIn("generic_surface_boundary_fill", text)
        self.assertTrue(_gate_regions_balanced(text))

    def test_every_gate_region_in_the_native_sources_is_balanced(self):
        for path in sorted(NATIVE.glob("*.cpp")):
            with self.subTest(path=path.name):
                self.assertTrue(_gate_regions_balanced(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
