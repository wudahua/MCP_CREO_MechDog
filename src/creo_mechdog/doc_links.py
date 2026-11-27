"""Check local file links and heading anchors across active non-frozen Markdown docs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

ROOT_ACTIVE_FILES = ("README.md", "AGENTS.md")
FROZEN_DOCS_DIRS = frozenset({"archive", "validation", "release-notes"})

_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_HTML_ANCHOR_RE = re.compile(
    r"""<a\b[^>]*\b(?:id|name)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def discover_active_markdown(root: Path) -> list[Path]:
    """Discover active, non-frozen Markdown files under ``root`` dynamically."""
    base = Path(root).resolve()
    files: list[Path] = []
    for name in ROOT_ACTIVE_FILES:
        candidate = base / name
        if candidate.is_file():
            files.append(candidate)
    docs_dir = base / "docs"
    if docs_dir.is_dir():
        for path in sorted(docs_dir.rglob("*.md")):
            if not path.is_file():
                continue
            rel = path.relative_to(base)
            if len(rel.parts) >= 2 and rel.parts[1] in FROZEN_DOCS_DIRS:
                continue
            files.append(path)
    return files


def slugify_heading(heading: str) -> str:
    """Convert a Markdown ATX heading to its GitHub-style fragment slug."""
    text = heading.strip()
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def extract_anchors(text: str) -> set[str]:
    """Extract heading slugs and explicit HTML ``id``/``name`` anchors."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    in_fence = False
    fence_char = ""
    for line in text.splitlines():
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_char = marker
            elif marker == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue
        for anchor_id in _HTML_ANCHOR_RE.findall(line):
            anchors.add(anchor_id)
            anchors.add(anchor_id.lower())
        heading = _HEADING_RE.match(line)
        if heading:
            slug = slugify_heading(heading.group(1))
            if slug:
                seen = counts.get(slug, 0)
                counts[slug] = seen + 1
                anchors.add(slug if seen == 0 else f"{slug}-{seen}")
    return anchors


def _parse_target(raw_destination: str) -> str:
    value = raw_destination.strip()
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1].strip()
    return value.split()[0]


def check_doc_links(root: Path) -> dict[str, Any]:
    """Verify local file links and Markdown ``#anchor`` targets in active docs."""
    base = Path(root).resolve()
    files = discover_active_markdown(base)
    anchor_cache: dict[Path, set[str]] = {}
    broken_files: list[dict[str, Any]] = []
    broken_anchors: list[dict[str, Any]] = []
    links_checked = 0

    for source in files:
        source_rel = source.relative_to(base).as_posix()
        text = source.read_text(encoding="utf-8-sig")
        in_fence = False
        fence_char = ""
        for lineno, line in enumerate(text.splitlines(), 1):
            fence = _FENCE_RE.match(line)
            if fence:
                marker = fence.group(1)[0]
                if not in_fence:
                    in_fence = True
                    fence_char = marker
                elif marker == fence_char:
                    in_fence = False
                continue
            if in_fence:
                continue
            cleaned = _INLINE_CODE_RE.sub("", line)
            for match in _LINK_RE.finditer(cleaned):
                raw = _parse_target(match.group(1))
                if not raw or _SCHEME_RE.match(raw) or raw.startswith("//"):
                    continue
                links_checked += 1
                path_part, _, fragment = raw.partition("#")
                path_part = unquote(path_part)
                fragment = unquote(fragment)
                if path_part == "":
                    target = source
                else:
                    target = (source.parent / path_part).resolve()
                    try:
                        target.relative_to(base)
                    except ValueError:
                        broken_files.append(
                            {
                                "source": source_rel,
                                "line": lineno,
                                "link": raw,
                                "reason": "escapes_root",
                            }
                        )
                        continue
                    if not target.exists():
                        broken_files.append(
                            {
                                "source": source_rel,
                                "line": lineno,
                                "link": raw,
                                "reason": "missing_file",
                            }
                        )
                        continue
                if fragment and target.is_file() and target.suffix.lower() == ".md":
                    if target not in anchor_cache:
                        anchor_cache[target] = extract_anchors(
                            target.read_text(encoding="utf-8-sig")
                        )
                    anchors = anchor_cache[target]
                    if fragment not in anchors and fragment.lower() not in anchors:
                        broken_anchors.append(
                            {
                                "source": source_rel,
                                "line": lineno,
                                "link": raw,
                                "anchor": fragment,
                                "target": target.relative_to(base).as_posix(),
                                "reason": "missing_anchor",
                            }
                        )

    return {
        "root": str(base),
        "files_scanned": len(files),
        "links_checked": links_checked,
        "broken_files": broken_files,
        "broken_anchors": broken_anchors,
        "consistent": not broken_files and not broken_anchors,
    }
