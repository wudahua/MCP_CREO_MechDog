"""BUG-119 driver: surface_loft on a part that already contains a solid.

Offline mode checks the published plan and the native delta gate. Live mode
(``--live --confirm-session-usable``) builds a 100x60x10 solid first, then lofts
two R20 circular sections 40 mm apart above it. The native section rule accepts
one curve or the two arcs of a closed profile, so a rectangle sketch (four
non-composite lines) is refused; a circle keeps the section closed and gives the
exact lateral area 2*pi*20*40 = 5026.548 mm^2.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft_existing_solid.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft_existing_solid.py --live --confirm-session-usable
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

WIDTH_MM = 100.0
HEIGHT_MM = 60.0
SOLID_DEPTH_MM = 10.0
SECTION_RADIUS_MM = 20.0
FIRST_SECTION_Z = 20.0
SECOND_SECTION_Z = 60.0
GAP_MM = SECOND_SECTION_Z - FIRST_SECTION_Z
PERIMETER_MM = 2 * math.pi * SECTION_RADIUS_MM
EXPECTED_AREA_MM2 = PERIMETER_MM * GAP_MM
AREA_TOLERANCE_FRACTION = 0.01


def rectangle(name: str) -> dict[str, Any]:
    return {
        "type": "rectangle",
        "name": name,
        "min": [-WIDTH_MM / 2, -HEIGHT_MM / 2],
        "max": [WIDTH_MM / 2, HEIGHT_MM / 2],
    }


def circle(name: str) -> dict[str, Any]:
    return {
        "type": "circle",
        "name": name,
        "center": [0.0, 0.0],
        "radius": SECTION_RADIUS_MM,
    }


def plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "sketch",
            "label": "base",
            "plane": "XY",
            "entities": [rectangle("base")],
        },
        {"op": "extrude", "label": "solid", "sketch": "base", "depth": SOLID_DEPTH_MM},
        {
            "op": "sketch",
            "label": "section_a",
            "plane": "XY",
            "offset": FIRST_SECTION_Z,
            "entities": [circle("section_a")],
        },
        {
            "op": "sketch",
            "label": "section_b",
            "plane": "XY",
            "offset": SECOND_SECTION_Z,
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
    try:
        validate_operations(plan())
        checks.append({"check": "schema_accepts_existing_solid_plan", "ok": True})
    except ValueError as error:
        checks.append(
            {"check": "schema_accepts_existing_solid_plan", "ok": False, "error": str(error)}
        )
    source = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")
    checks.append(
        {
            "check": "native_gate_is_a_delta",
            "ok": "created_solid_material" in source
            and 'if (details["has_solid"].get<bool>())' not in source,
        }
    )
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "checks": checks,
        "expected_area_mm2": EXPECTED_AREA_MM2,
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

        state = await harness.submit(client, plan())
        jobs.append(
            {
                "job_id": state.get("job_id"),
                "status": state.get("status"),
                "model_id": state.get("model_id"),
                "revision": state.get("revision"),
                "message": str(state.get("message"))[:300],
            }
        )
        check(
            "existing_solid_loft_succeeded",
            state.get("status") == "succeeded",
            {"status": state.get("status"), "message": str(state.get("message"))[:500]},
        )
        if state.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "checks": checks,
                "jobs": jobs,
                "failure": harness.operation_of(state, "surface_loft") or state.get("message"),
            }

        surface = harness.operation_of(state, "surface_loft")
        check("saved_file_reloaded_and_verified", harness.saved_verified(state))
        check(
            "solid_existed_before_the_loft",
            surface.get("has_solid_before") is True,
            surface.get("has_solid_before"),
        )
        check(
            "loft_did_not_create_solid_material",
            surface.get("created_solid_material") is False,
            {
                "created_solid_material": surface.get("created_solid_material"),
                "has_solid_before": surface.get("has_solid_before"),
                "has_solid_after": surface.get("has_solid_after"),
                "material_bodies_before": surface.get("material_bodies_before"),
                "material_bodies_after": surface.get("material_bodies_after"),
                "volume_mm3_before": surface.get("volume_mm3_before"),
                "volume_mm3_after": surface.get("volume_mm3_after"),
            },
        )
        check(
            "material_body_count_unchanged",
            surface.get("material_bodies_before") == surface.get("material_bodies_after"),
            {
                "before": surface.get("material_bodies_before"),
                "after": surface.get("material_bodies_after"),
            },
        )
        area = surface.get("surface_area_mm2")
        tolerance = EXPECTED_AREA_MM2 * AREA_TOLERANCE_FRACTION
        check(
            "loft_area_matches_circle_circumference",
            isinstance(area, (int, float)) and abs(area - EXPECTED_AREA_MM2) <= tolerance,
            {
                "surface_area_mm2": area,
                "expected_mm2": EXPECTED_AREA_MM2,
                "tolerance_mm2": tolerance,
            },
        )
        check(
            "one_open_quilt",
            surface.get("quilt_count") == 1 and surface.get("quilt_closed_native") == "open",
            {
                "quilt_count": surface.get("quilt_count"),
                "quilt_closed_native": surface.get("quilt_closed_native"),
            },
        )

    return {
        "mode": "live",
        "passed": all(item["ok"] for item in checks),
        "checks": checks,
        "jobs": jobs,
        "expected_area_mm2": EXPECTED_AREA_MM2,
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
    output = args.output or ROOT / "build" / "surface_loft_existing_solid" / f"{stamp}.json"
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
