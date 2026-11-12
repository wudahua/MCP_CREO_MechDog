"""FEAT-066 driver: exact NURBS ``b_spline`` sketch entity.

Default mode is offline: it checks the published contract (clamped knots,
control points, weights, coordinates refusal) and computes the arc length the
live loft must reproduce.

``--live --confirm-session-usable`` submits one ``b_spline`` sketch to the local
Creo session and verifies:

* the sketch job succeeds, is saved and reloaded;
* ``geometry_deviation`` measures the stored control points
  (``measurement=control_points``) with zero deviation, proving that degree,
  knots and control points survived the kernel round-trip;
* two identical 5-point cubic sections 20 mm apart rule a loft whose measured
  area equals ``20 mm * arc length`` computed independently from the same
  degree/knots/control points;
* the loft is one open quilt with ``section_count=2`` and no solid.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_b_spline.py
  .venv\\Scripts\\python.exe tools\\test_b_spline.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import bisect
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

DEGREE = 3
CONTROL_POINTS = [[0.0, 0.0], [10.0, 8.0], [30.0, 9.0], [45.0, 2.0], [50.0, 0.0]]
KNOTS = [0.0, 0.0, 0.0, 0.0, 0.595088181, 1.0, 1.0, 1.0, 1.0]
WEIGHTS = [1.0, 1.0, 1.0, 1.0, 1.0]
GAP_MM = 20.0
AREA_TOLERANCE_FRACTION = 0.01
DEVIATION_TOLERANCE_MM = 1e-6


def _de_boor(u: float) -> tuple[float, float]:
    n = len(CONTROL_POINTS) - 1
    span = n if u >= KNOTS[n + 1] else max(DEGREE, bisect.bisect_right(KNOTS, u) - 1)
    points = [
        [
            CONTROL_POINTS[span - DEGREE + j][0] * WEIGHTS[span - DEGREE + j],
            CONTROL_POINTS[span - DEGREE + j][1] * WEIGHTS[span - DEGREE + j],
            WEIGHTS[span - DEGREE + j],
        ]
        for j in range(DEGREE + 1)
    ]
    for r in range(1, DEGREE + 1):
        for j in range(DEGREE, r - 1, -1):
            i = span - DEGREE + j
            denominator = KNOTS[i + DEGREE + 1 - r] - KNOTS[i]
            alpha = 0.0 if denominator == 0 else (u - KNOTS[i]) / denominator
            points[j] = [(1.0 - alpha) * points[j - 1][k] + alpha * points[j][k] for k in range(3)]
    weight = points[DEGREE][2]
    return points[DEGREE][0] / weight, points[DEGREE][1] / weight


def arc_length_mm(samples: int = 800) -> float:
    start, end = KNOTS[DEGREE], KNOTS[len(CONTROL_POINTS)]
    previous = _de_boor(start)
    total = 0.0
    for index in range(1, samples + 1):
        current = _de_boor(start + (end - start) * index / samples)
        total += math.dist(previous, current)
        previous = current
    return total


EXPECTED_AREA_MM2 = GAP_MM * arc_length_mm()


def entity(name: str) -> dict[str, Any]:
    return {
        "type": "b_spline",
        "name": name,
        "degree": DEGREE,
        "control_points": CONTROL_POINTS,
        "knots": KNOTS,
        "weights": WEIGHTS,
    }


def sketch_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "sketch",
            "label": "nurbs_profile",
            "plane": "XY",
            "entities": [entity("nurbs_profile")],
        }
    ]


def loft_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "sketch",
            "label": "nurbs_a",
            "plane": "XY",
            "entities": [entity("nurbs_a")],
        },
        {
            "op": "sketch",
            "label": "nurbs_b",
            "plane": "XY",
            "offset": GAP_MM,
            "entities": [entity("nurbs_b")],
        },
        {
            "op": "surface_loft",
            "label": "nurbs_loft",
            "sections": ["nurbs_a", "nurbs_b"],
        },
    ]


def case_offline() -> dict:
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    try:
        validated = validate_operations(sketch_plan())
        stored = validated[0]["entities"][0]
        check("schema_accepts_b_spline", True)
        check("knots_preserved", stored.get("knots") == KNOTS, stored.get("knots"))
        check("degree_preserved", stored.get("degree") == DEGREE, stored.get("degree"))
    except ValueError as error:
        check("schema_accepts_b_spline", False, {"error": str(error)})
        return {"mode": "offline", "passed": False, "checks": checks}

    bad_knots = dict(entity("bad"), knots=[0, 0, 0, 0, 1, 1, 1, 1])
    for name, payload in (
        ("wrong_knot_count", bad_knots),
        ("unclamped_knots", dict(entity("bad"), knots=[0, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 0.9, 1.0])),
        ("weight_count", dict(entity("bad"), weights=[1, 1, 1])),
        ("closed_field", dict(entity("bad"), closed=True)),
    ):
        try:
            validate_operations([{"op": "sketch", "label": "bad", "entities": [payload]}])
            check(f"schema_rejects_{name}", False, {"reason": "accepted"})
        except ValueError:
            check(f"schema_rejects_{name}", True)

    try:
        validate_operations(
            [
                {
                    "op": "sketch",
                    "label": "bad",
                    "dimensioning": "coordinates",
                    "entities": [entity("bad")],
                }
            ]
        )
        check("coordinates_rejects_b_spline", False, {"reason": "accepted"})
    except ValueError:
        check("coordinates_rejects_b_spline", True)

    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "checks": checks,
        "expected_ruled_area_mm2": EXPECTED_AREA_MM2,
        "arc_length_mm": arc_length_mm(),
    }


def _deviation_entries(state: dict) -> list[dict]:
    for operation in (state.get("result") or {}).get("operations") or []:
        deviation = operation.get("geometry_deviation")
        if isinstance(deviation, dict):
            stages = deviation.get("stages") or {}
            entries: list[dict] = []
            for stage in stages.values():
                if isinstance(stage, dict):
                    entries.extend(stage.get("sample") or [])
            return entries
    return []


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    def remember(state: dict) -> None:
        jobs.append(
            {
                "job_id": state.get("job_id"),
                "status": state.get("status"),
                "model_id": state.get("model_id"),
                "revision": state.get("revision"),
                "message": str(state.get("message"))[:300],
            }
        )

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await harness.wait_ready(client)
        check("session_ready", bool(started.get("connected")), {"state": started.get("state")})
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_b_spline": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        capabilities = await harness.call_tool(client, "creo_capabilities", {})
        entities = capabilities.get("entities") or []
        check("b_spline_advertised", "b_spline" in entities, {"entities": entities})

        build = await harness.submit(client, sketch_plan())
        remember(build)
        check(
            "sketch_job_succeeded",
            build.get("status") == "succeeded",
            {"status": build.get("status"), "message": str(build.get("message"))[:400]},
        )
        if build.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_b_spline": "failed",
                "checks": checks,
                "jobs": jobs,
                "failure": harness.operation_of(build, "sketch") or build.get("message"),
            }

        check("saved_file_reloaded_and_verified", harness.saved_verified(build))
        entries = _deviation_entries(build)
        bspline_entries = [
            entry for entry in entries if entry.get("measurement") == "control_points"
        ]
        check(
            "deviation_measured_control_points",
            bool(bspline_entries),
            {"entries": entries[:4]},
        )
        deviations = [
            entry.get("deviation_mm")
            for entry in bspline_entries
            if isinstance(entry.get("deviation_mm"), (int, float))
        ]
        check(
            "control_points_round_trip_exactly",
            bool(deviations) and max(deviations) <= DEVIATION_TOLERANCE_MM,
            {"max_deviation_mm": max(deviations) if deviations else None},
        )

        loft = await harness.submit(client, loft_plan())
        remember(loft)
        check(
            "loft_job_succeeded",
            loft.get("status") == "succeeded",
            {"status": loft.get("status"), "message": str(loft.get("message"))[:400]},
        )
        if loft.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_b_spline": "loft_failed",
                "checks": checks,
                "jobs": jobs,
                "failure": harness.operation_of(loft, "surface_loft") or loft.get("message"),
            }

        surface = harness.operation_of(loft, "surface_loft")
        area = surface.get("surface_area_mm2")
        check("saved_file_reloaded_and_verified_loft", harness.saved_verified(loft))
        check(
            "section_count_is_two", surface.get("section_count") == 2, surface.get("section_count")
        )
        check(
            "one_open_quilt",
            surface.get("quilt_count") == 1 and surface.get("quilt_closed_native") == "open",
            {
                "quilt_count": surface.get("quilt_count"),
                "quilt_closed_native": surface.get("quilt_closed_native"),
            },
        )
        check("no_solid_created", surface.get("has_solid") is False, surface.get("has_solid"))
        tolerance = EXPECTED_AREA_MM2 * AREA_TOLERANCE_FRACTION
        check(
            "loft_area_matches_nurbs_arc_length",
            isinstance(area, (int, float)) and abs(area - EXPECTED_AREA_MM2) <= tolerance,
            {
                "surface_area_mm2": area,
                "expected_mm2": EXPECTED_AREA_MM2,
                "tolerance_mm2": tolerance,
            },
        )

        model_id = loft["model_id"]
        quilts = await harness.model_section(client, model_id, "quilts")
        reloaded_area = (quilts[0] if quilts else {}).get("area_mm2")
        check(
            "area_stable_after_reload",
            isinstance(reloaded_area, (int, float))
            and isinstance(area, (int, float))
            and abs(reloaded_area - area) <= tolerance,
            {"area_mm2": reloaded_area, "first_read_mm2": area},
        )

    return {
        "mode": "live",
        "passed": all(item["ok"] for item in checks),
        "native_b_spline": "verified" if all(item["ok"] for item in checks) else "failed",
        "checks": checks,
        "jobs": jobs,
        "expected_ruled_area_mm2": EXPECTED_AREA_MM2,
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
    output = args.output or ROOT / "build" / "b_spline" / f"{stamp}.json"
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
