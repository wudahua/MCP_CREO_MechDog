"""FEAT-035 T12 offline contract report; live Toolkit execution is refused."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.unit import test_native_countersink as fixture  # noqa: E402


def provenance() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(("tests/unit/test_native_countersink.py", "tools/test_native_countersink.py"))
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live:
        print("T12 offline driver refuses live Toolkit/Creo connection", file=sys.stderr)
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromModule(fixture)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {
        "task": "DEV-051 T12 / FEAT-035",
        "mode": "offline",
        "native_acceptance": "not_run",
        "unit": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
        },
        "oracle_mm3": {
            "counterbore": fixture.oracle_removed(
                6, 12, {"counterbore": {"diameter": 10, "depth": 2}}
            ),
            "countersink": fixture.oracle_removed(
                6, 12, {"countersink": {"diameter": 10, "angle": 90}}
            ),
            "assumption": "flat drill bottom and complete solid intersection; native tip and actual material removal unverified",
        },
        "sdk": "Creo 12.4 ProHole.h custom-hole CBORE/CSINK elements; runtime element acceptance unverified",
        "pending_live": [
            "single native hole feature and element-tree readback",
            "cylinder/frustum geometry",
            "dimension ID edits",
            "revision and rollback",
            "save/reload",
        ],
        "provenance": provenance(),
    }
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    output = args.output or ROOT / "build" / "native_countersink" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    output.with_suffix(".sha256").write_text(digest + "  report.json\n", encoding="ascii")
    print(json.dumps({"report": str(output), "sha256": digest, "passed": result.wasSuccessful()}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
