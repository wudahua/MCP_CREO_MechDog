"""FEAT-065 sub-item driver: surface_loft sections on arbitrary orthogonal planes.

Offline mode validates the YZ/XZ plans. Live mode (``--live
--confirm-session-usable``) lofts two R20 circles on each plane and checks the
ruled area equals ``circumference * gap``. A circle keeps the section closed and
satisfies the native "one curve, or two curves forming one closed profile" rule;
a rectangle sketch is four non-composite lines and is refused.

* YZ@X=0 / YZ@X=50 -> 2*pi*20 mm * 50 mm = 6283.185 mm^2
* XZ@Y=0 / XZ@Y=40 -> 2*pi*20 mm * 40 mm = 5026.548 mm^2

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft_planes.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft_planes.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, str(entry))

import test_surface_loft_multisection as harness  # noqa: E402

SECTION_RADIUS_MM = 20.0
CIRCUMFERENCE_MM = 2 * math.pi * SECTION_RADIUS_MM
AREA_TOLERANCE_FRACTION = 0.01

CASES = (
    {"plane": "YZ", "first": 0.0, "second": 50.0, "gap": 50.0, "expected": CIRCUMFERENCE_MM * 50.0},
    {"plane": "XZ", "first": 0.0, "second": 40.0, "gap": 40.0, "expected": CIRCUMFERENCE_MM * 40.0},
)


def circle(name: str) -> dict[str, Any]:
    return {
        "type": "circle",
        "name": name,
        "center": [0.0, 0.0],
        "radius": SECTION_RADIUS_MM,
    }


def plan(case: dict[str, Any]) -> list[dict[str, Any]]:
    plane = case["plane"]
    return [
        {
            "op": "sketch",
            "label": "section_a",
            "plane": plane,
            "offset": case["first"],
            "entities": [circle("section_a")],
        },
        {
            "op": "sketch",
            "label": "section_b",
            "plane": plane,
            "offset": case["second"],
            "entities": [circle("section_b")],
        },
        {
            "op": "surface_loft",
            "label": "loft",
            "sections": ["section_a", "section_b"],
        },
    ]


def case_offline() -> dict:
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []
    for case in CASES:
        try:
            validate_operations(plan(case))
            ok, error = True, None
        except ValueError as exc:
            ok, error = False, str(exc)
        checks.append(
            {
                "check": f"schema_accepts_{case['plane']}_sections",
                "ok": ok,
                **({"error": error} if error else {}),
            }
        )
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "checks": checks,
        "cases": CASES,
    }


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        ready = await harness.wait_ready(client)
        check("session_ready", bool(ready.get("connected")), {"state": ready.get("state")})
        if not ready.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "note": "no connected session; nothing submitted",
                "checks": checks,
                "jobs": jobs,
            }

        for case in CASES:
            plane = case["plane"]
            state = await harness.submit(client, plan(case))
            jobs.append(
                {
                    "plane": plane,
                    "job_id": state.get("job_id"),
                    "status": state.get("status"),
                    "model_id": state.get("model_id"),
                    "revision": state.get("revision"),
                    "message": str(state.get("message"))[:300],
                }
            )
            check(
                f"{plane}_loft_succeeded",
                state.get("status") == "succeeded",
                {"status": state.get("status"), "message": str(state.get("message"))[:500]},
            )
            if state.get("status") != "succeeded":
                continue
            surface = harness.operation_of(state, "surface_loft")
            area = surface.get("surface_area_mm2")
            tolerance = case["expected"] * AREA_TOLERANCE_FRACTION
            check(
                f"{plane}_area_matches_perimeter",
                isinstance(area, (int, float)) and abs(area - case["expected"]) <= tolerance,
                {
                    "surface_area_mm2": area,
                    "expected_mm2": case["expected"],
                    "tolerance_mm2": tolerance,
                },
            )
            check(
                f"{plane}_one_open_quilt",
                surface.get("quilt_count") == 1 and surface.get("quilt_closed_native") == "open",
                {
                    "quilt_count": surface.get("quilt_count"),
                    "quilt_closed_native": surface.get("quilt_closed_native"),
                },
            )
            check(
                f"{plane}_no_solid",
                surface.get("has_solid") is False,
                surface.get("has_solid"),
            )
            check(f"{plane}_saved_reloaded", harness.saved_verified(state))

    return {
        "mode": "live",
        "passed": all(item["ok"] for item in checks),
        "checks": checks,
        "jobs": jobs,
        "cases": CASES,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        parser.error("--live requires --confirm-session-usable")

    report = case_offline()
    if args.live:
        report["live"] = asyncio.run(case_live())
        report["passed"] = bool(report["passed"] and report["live"]["passed"])

    stamp = time.strftime("%Y%m%d-%H%M%S")
    output = args.output or ROOT / "build" / "surface_loft_planes" / f"{stamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for section, items in (
        ("offline", report["checks"]),
        ("live", (report.get("live") or {}).get("checks") or []),
    ):
        for item in items:
            print(f"  {'PASS' if item['ok'] else 'FAIL'} {item['check']}")
    print(f"passed={report['passed']}")
    print(f"report={output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
