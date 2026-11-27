"""CLI for checking local links and anchors in active non-frozen Markdown docs.

Exit 0 when all discovered active documents have valid local file targets and
``#anchor`` fragments; exit 1 with a JSON report otherwise::

    python tools/check_doc_links.py
    python tools/check_doc_links.py --root <path/to/repo>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from creo_mechdog.doc_links import check_doc_links
except ModuleNotFoundError:  # unpacked source distribution without an editable install
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from creo_mechdog.doc_links import check_doc_links

DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    report = check_doc_links(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
