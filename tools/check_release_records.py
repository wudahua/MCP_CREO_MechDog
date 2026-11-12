"""Check that a release's POSTCHECK and record are current before packaging.

DEV-083: 0.22.0 and 0.23.0 were tagged while their records still said
"待回填", and the distributed source ZIP kept that state. ``tools/package.py``
now runs the same gate on the archive it just wrote; this script exposes it for
a standalone pre-check.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from creo_mechdog.release_integrity import validate_release_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version, for example 0.23.1")
    parser.add_argument(
        "--source-zip",
        type=Path,
        help="Also check the in-package records of this source archive",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Source tree to check; defaults to this checkout",
    )
    args = parser.parse_args(argv)
    problems = validate_release_records(args.version, args.source_zip, args.root)
    if problems:
        print(f"{args.version}: release records are not current", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"{args.version}: POSTCHECK, release record and per-ID states are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
