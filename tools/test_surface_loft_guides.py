"""FEAT-065/M2 driver: surface_loft with a guided second direction (2DIR).

Default mode is offline: it checks the published contract (guides admitted in
pairs, a single guide refused, duplicates and section reuse refused, capability
text and the native 2DIR route) without any Creo session.

``--live --confirm-session-usable`` submits one guided boundary blend to the
local Creo session and verifies:

* straight guides lying in the section plane reproduce the plain ruled blend
  (800.0 mm2, x = 0..40): adding a second direction does not change a surface
  it already describes;
* semicircular guides (radius 14.1421 mm, endpoints on both sections) build ONE
  open quilt whose measurements differ from that baseline: measured
  2026-11-11 on Creo 12.4.0.0 the area is 600.0 mm2 and the bounding box
  reaches x = 44.24 mm instead of stopping at 40 mm. This pair of numbers is
  the evidence that the second direction acted; the exact shape has not been
  inspected in the GUI, so the report records the numbers, not an
  interpretation of the surface;
* the receipt reports guide_count = 2 with two guide curve ids;
* both results are saved, reloaded and verified, and no solid is created;
* a one-guide request is refused before a job exists.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft_guides.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft_guides.py --live --confirm-session-usable
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
        sys.path.insert(0, entry)

import test_surface_loft_multisection as harness  # noqa: E402

SECTION_LENGTH_MM = 40.0
SECTION_GAP_MM = 20.0
#: Semicircular guide: centre 10 mm off the section edge, 90 degrees of sweep, so
#: the mid-height bulge is r - 10 = 4.1421 mm past the section endpoint.
GUIDE_RADIUS_MM = math.sqrt(200.0)
GUIDE_BULGE_MM = GUIDE_RADIUS_MM - 10.0
#: A plain two-section ruled surface spans exactly 0..40 mm; the guided one
#: reaches 40 + bulge. 0.5 mm is far outside the 0.12 mm inspection padding.
GUIDE_BBOX_TOLERANCE_MM = 0.5
AREA_TOLERANCE_MM2 = 5.0
#: The plain two-section ruled surface through these sections.
PLAIN_AREA_MM2 = 800.0
#: Measured 2026-11-11 (Creo 12.4.0.0, job cd495d1c...) for the curved guides.
CURVED_GUIDE_AREA_MM2 = 600.0
CURVED_GUIDE_MAX_X_MM = 44.24
#: Three coplanar 40 mm sections 20 mm apart with straight guides: the only
#: surface through all of them is the 40 x 40 rectangle.
THREE_SECTION_AREA_MM2 = 1600.0


def sketch(label: str, plane: str, offset: float, name: str, start, end) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "offset": offset,
        "entities": [{"type": "line", "name": name, "start": start, "end": end}],
    }


def guide_sketch(label: str, centre_x: float) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XZ",
        "offset": 0.0,
        "entities": [
            {
                "type": "arc",
                "name": "guide",
                "center": [centre_x, SECTION_GAP_MM / 2.0],
                "radius": GUIDE_RADIUS_MM,
                "start_angle": 315.0,
                "end_angle": 45.0,
                "dir": 1,
            }
        ],
    }


def guided_plan() -> list[dict]:
    return [
        sketch("sec_a", "XY", 0.0, "a", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("sec_b", "XY", SECTION_GAP_MM, "b", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        guide_sketch("guide_left", 0.0),
        # The right guide is the same arc shifted by one section length: centre
        # 10 mm left of x = 40, so its 90 degree sweep still ends on the section.
        guide_sketch("guide_right", SECTION_LENGTH_MM - 10.0),
        {
            "op": "surface_loft",
            "label": "guided_loft",
            "sections": ["sec_a", "sec_b"],
            "guides": ["guide_left", "guide_right"],
        },
    ]


def straight_guided_plan() -> list[dict]:
    """Same sections with two straight guides in the section plane.

    These guides lie exactly in the surface the two sections already describe,
    so the guided result must equal the plain ruled blend.
    """
    return [
        sketch("sec_a", "XY", 0.0, "a", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("sec_b", "XY", SECTION_GAP_MM, "b", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("guide_left", "XZ", 0.0, "g", [0.0, 0.0], [0.0, SECTION_GAP_MM]),
        sketch(
            "guide_right",
            "XZ",
            0.0,
            "g",
            [SECTION_LENGTH_MM, 0.0],
            [SECTION_LENGTH_MM, SECTION_GAP_MM],
        ),
        {
            "op": "surface_loft",
            "label": "guided_loft",
            "sections": ["sec_a", "sec_b"],
            "guides": ["guide_left", "guide_right"],
        },
    ]


def single_guide_plan() -> list[dict]:
    plan = guided_plan()
    plan[-1]["guides"] = ["guide_left"]
    return plan


def three_section_guided_plan() -> list[dict]:
    """Three smooth sections with two straight guides that span all of them.

    Every curve lies in the y = 0 plane, so the guided blend can only be the
    40 x 40 mm rectangle: 1600.0 mm2. Measured 2026-11-11 on Creo 12.4.0.0.
    """
    return [
        sketch("sec_a", "XY", 0.0, "a", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("sec_b", "XY", SECTION_GAP_MM, "b", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("sec_c", "XY", 2 * SECTION_GAP_MM, "c", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("guide_left", "XZ", 0.0, "g", [0.0, 0.0], [0.0, 2 * SECTION_GAP_MM]),
        sketch(
            "guide_right",
            "XZ",
            0.0,
            "g",
            [SECTION_LENGTH_MM, 0.0],
            [SECTION_LENGTH_MM, 2 * SECTION_GAP_MM],
        ),
        {
            "op": "surface_loft",
            "label": "guided_loft",
            "sections": ["sec_a", "sec_b", "sec_c"],
            "interpolation": "smooth",
            "guides": ["guide_left", "guide_right"],
        },
    ]


def case_offline() -> dict:
    from creo_mechdog import capabilities
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    try:
        validated = validate_operations(guided_plan())
        check("schema_accepts_two_guides", validated[-1]["guides"] == ["guide_left", "guide_right"])
        check("schema_keeps_the_sections", validated[-1]["sections"] == ["sec_a", "sec_b"])
    except ValueError as error:
        check("schema_accepts_two_guides", False, {"error": str(error)})
        return {"mode": "offline", "passed": False, "checks": checks}

    try:
        validated = validate_operations(three_section_guided_plan())
        check(
            "schema_accepts_guides_with_three_sections",
            validated[-1]["guides"] == ["guide_left", "guide_right"]
            and validated[-1]["interpolation"] == "smooth",
            {"sections": len(validated[-1]["sections"])},
        )
    except ValueError as error:
        check("schema_accepts_guides_with_three_sections", False, {"error": str(error)})

    example = ROOT / "examples" / "surface_loft_guides.json"
    try:
        plan = json.loads(example.read_text(encoding="utf-8"))
        validated = validate_operations(plan["operations"])
        loft = validated[-1]
        check(
            "example_plan_is_valid",
            loft["op"] == "surface_loft" and len(loft["guides"]) == 2,
            {"file": example.name, "guides": loft.get("guides")},
        )
    except (OSError, ValueError, KeyError) as error:
        check("example_plan_is_valid", False, {"error": str(error)[:200]})

    for name, guides in (
        ("single_guide", ["guide_left"]),
        ("duplicate_guides", ["guide_left", "guide_left"]),
        ("guide_reuses_a_section", ["sec_a", "guide_right"]),
    ):
        plan = guided_plan()
        plan[-1]["guides"] = guides
        try:
            validate_operations(plan)
            check(f"schema_rejects_{name}", False, {"reason": "accepted"})
        except ValueError as error:
            check(f"schema_rejects_{name}", True, {"error": str(error)[:160]})

    limits = capabilities.families()["surface_loft"]["limits"]
    check("capability_names_the_guide_range", "2-8 guides" in limits, limits[:200])
    check(
        "capability_states_without_guide_does_not_regenerate",
        "does not regenerate" in limits or "never regenerates" in limits,
    )

    native = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")
    code = "\n".join(line for line in native.splitlines() if not line.lstrip().startswith("//"))
    check("native_builds_the_second_direction", "PRO_E_BNBLN_2DIR" in code)
    check("native_refuses_a_single_guide", "need at least two guide" in code)

    server = (ROOT / "server.py").read_text(encoding="utf-8")
    # FEAT-065/M3 widened the element type to accept curve/edge references.
    check(
        "tool_exposes_the_guides_argument",
        "guides: Annotated[list[str | int | dict[str, Any]]" in server,
    )

    return {"mode": "offline", "passed": all(item["ok"] for item in checks), "checks": checks}


def quilt_bbox(quilts: list) -> list | None:
    """The inspected quilt bounding box, padded by the inspector's own margin."""
    for quilt in quilts:
        box = quilt.get("bbox_mm")
        if isinstance(box, list) and len(box) == 2:
            return box
    return None


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
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "guided_loft": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        capabilities = await harness.call_tool(client, "creo_capabilities", {})
        published = "surface_loft" in (capabilities.get("operations") or [])
        check("surface_loft_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "guided_loft": "gated",
                "note": "surface_loft is refused before any job; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        # 1) A one-guide request never reaches the kernel.
        refused = await harness.call_tool(
            client, "creo_execute_plan", {"operations": single_guide_plan()}
        )
        check(
            "single_guide_refused_before_a_job",
            not refused.get("job_id"),
            {"message": str(refused.get("message") or refused)[:300]},
        )

        # 2) Straight guides reproduce the plain ruled blend.
        straight = await harness.submit(client, straight_guided_plan())
        remember(straight)
        check(
            "straight_guided_job_succeeded",
            straight.get("status") == "succeeded",
            {"status": straight.get("status"), "message": str(straight.get("message"))[:400]},
        )
        straight_loft = harness.operation_of(straight, "surface_loft")
        straight_area = straight_loft.get("surface_area_mm2")
        check(
            "straight_guides_reproduce_the_plain_blend",
            isinstance(straight_area, (int, float)) and abs(straight_area - PLAIN_AREA_MM2) <= 0.5,
            {"surface_area_mm2": straight_area, "plain_area_mm2": PLAIN_AREA_MM2},
        )
        check(
            "straight_guided_receipt_counts",
            straight_loft.get("guide_count") == 2 and straight_loft.get("quilt_count") == 1,
            {
                "guide_count": straight_loft.get("guide_count"),
                "quilt_count": straight_loft.get("quilt_count"),
            },
        )
        straight_box = quilt_bbox(
            await harness.model_section(client, straight["model_id"], "quilts")
        )
        check(
            "straight_guides_stay_inside_the_sections",
            straight_box is not None
            and abs(straight_box[1][0] - SECTION_LENGTH_MM) <= GUIDE_BBOX_TOLERANCE_MM,
            {"bbox_mm": straight_box, "section_end_mm": SECTION_LENGTH_MM},
        )

        # 3) Curved guides build a measurably different surface.
        guided = await harness.submit(client, guided_plan())
        remember(guided)
        check(
            "guided_job_succeeded",
            guided.get("status") == "succeeded",
            {"status": guided.get("status"), "message": str(guided.get("message"))[:400]},
        )
        if guided.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "guided_loft": "failed",
                "checks": checks,
                "jobs": jobs,
                "failure": harness.operation_of(guided, "surface_loft") or guided.get("message"),
            }

        model_id = guided["model_id"]
        loft = harness.operation_of(guided, "surface_loft")
        check("saved_file_reloaded_and_verified", harness.saved_verified(guided))
        check("guide_count_is_two", loft.get("guide_count") == 2, loft.get("guide_count"))
        check(
            "two_guide_curve_ids",
            isinstance(loft.get("guide_curve_ids"), list)
            and len(loft.get("guide_curve_ids") or []) == 2,
            loft.get("guide_curve_ids"),
        )
        check("exactly_one_quilt_item", loft.get("quilt_count") == 1, loft.get("quilt_count"))
        check(
            "quilt_is_open",
            loft.get("quilt_closed_native") == "open",
            loft.get("quilt_closed_native"),
        )
        check("no_solid_created", loft.get("has_solid") is False, loft.get("has_solid"))
        area = loft.get("surface_area_mm2")
        check(
            "curved_guides_change_the_measured_area",
            isinstance(area, (int, float)) and abs(area - PLAIN_AREA_MM2) > AREA_TOLERANCE_MM2,
            {
                "surface_area_mm2": area,
                "plain_area_mm2": PLAIN_AREA_MM2,
                "measured_2026_11_11": CURVED_GUIDE_AREA_MM2,
                "note": "the shape itself was not inspected, only the measurements",
            },
        )

        quilts = await harness.model_section(client, model_id, "quilts")
        box = quilt_bbox(quilts)
        expected_max_x = SECTION_LENGTH_MM + GUIDE_BULGE_MM
        check(
            "quilt_follows_the_guides",
            box is not None and box[1][0] >= expected_max_x - GUIDE_BBOX_TOLERANCE_MM,
            {
                "bbox_mm": box,
                "expected_max_x_mm": expected_max_x,
                "plain_ruled_max_x_mm": SECTION_LENGTH_MM,
                "measured_2026_11_11_max_x_mm": CURVED_GUIDE_MAX_X_MM,
                "guide_bulge_mm": GUIDE_BULGE_MM,
            },
        )

        reloaded_area = (quilts[0] if quilts else {}).get("area_mm2")
        check(
            "area_stable_after_reload",
            isinstance(reloaded_area, (int, float))
            and isinstance(area, (int, float))
            and abs(reloaded_area - area) <= AREA_TOLERANCE_MM2,
            {"area_mm2": reloaded_area, "first_read_mm2": area},
        )

        # 4) Guides also work beside three smooth sections.
        three = await harness.submit(client, three_section_guided_plan())
        remember(three)
        check(
            "three_section_guided_job_succeeded",
            three.get("status") == "succeeded",
            {"status": three.get("status"), "message": str(three.get("message"))[:400]},
        )
        if three.get("status") == "succeeded":
            three_loft = harness.operation_of(three, "surface_loft")
            three_area = three_loft.get("surface_area_mm2")
            check(
                "three_section_guided_receipt",
                three_loft.get("section_count") == 3
                and three_loft.get("guide_count") == 2
                and three_loft.get("quilt_count") == 1
                and three_loft.get("quilt_closed_native") == "open"
                and three_loft.get("has_solid") is False,
                {
                    "section_count": three_loft.get("section_count"),
                    "guide_count": three_loft.get("guide_count"),
                    "quilt_count": three_loft.get("quilt_count"),
                    "closure": three_loft.get("quilt_closed_native"),
                },
            )
            check(
                "three_section_guided_area",
                isinstance(three_area, (int, float))
                and abs(three_area - THREE_SECTION_AREA_MM2) <= AREA_TOLERANCE_MM2,
                {"surface_area_mm2": three_area, "expected_mm2": THREE_SECTION_AREA_MM2},
            )
            check("three_section_saved_reloaded_and_verified", harness.saved_verified(three))
            three_box = quilt_bbox(await harness.model_section(client, three["model_id"], "quilts"))
            check(
                "three_section_guided_bbox",
                three_box is not None
                and abs(three_box[1][0] - SECTION_LENGTH_MM) <= GUIDE_BBOX_TOLERANCE_MM
                and abs(three_box[1][2] - 2 * SECTION_GAP_MM) <= GUIDE_BBOX_TOLERANCE_MM,
                {"bbox_mm": three_box},
            )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "guided_loft": "verified" if passed else "failed",
        "checks": checks,
        "jobs": jobs,
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
    output = args.output or ROOT / "build" / "surface_loft_guides" / f"{stamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for section, items in (
        ("offline", report["checks"]),
        ("live", (report.get("live") or {}).get("checks") or []),
    ):
        if not items:
            continue
        print(f"[{section}]")
        for item in items:
            print(f"  {'PASS' if item['ok'] else 'FAIL'} {item['check']}")
    print(f"passed={report['passed']}")
    print(f"report={output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
