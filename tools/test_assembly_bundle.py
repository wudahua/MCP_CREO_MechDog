"""FEAT-031 T13 offline fixture report; live Creo execution is refused."""

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
from tests.unit import test_assembly_bundle as fixture  # noqa: E402


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
    names.update(("tests/unit/test_assembly_bundle.py", "tools/test_assembly_bundle.py"))
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
        print("T13 offline driver refuses live Toolkit/Creo connection", file=sys.stderr)
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromModule(fixture)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {
        "task": "DEV-051 T13 / FEAT-031",
        "mode": "offline",
        "native_acceptance": "not_run",
        "unit": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
        },
        "contract": {
            "root": "owned model output",
            "manifest": "native_bundle/manifest.json",
            "max_files": 128,
            "max_bytes": 536870912,
            "manifest_bytes": 32768,
        },
        "pending_live": [
            "single and nested assembly opening in a fresh directory",
            "native reference resolution",
            "source snapshots and hashes",
            "revision and save/reload",
        ],
        "provenance": provenance(),
    }
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    output = args.output or ROOT / "build" / "assembly_bundle" / run_id / "report.json"
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
