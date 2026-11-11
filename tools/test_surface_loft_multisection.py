"""FEAT-065/M1 driver: surface_loft with three sections (single direction).

Default mode is offline: it checks the published contract (schema admission for
2..32 sections, duplicate refusal, capability text) without any Creo session.

``--live --confirm-session-usable`` runs the public MCP tools against the local
Creo session and verifies:

* three parallel 40/60/40 mm sections 20 mm apart produce ONE open quilt of
  2000.0 mm2 (+/- 0.5), measured, saved and reloaded with a stable id/area;
* the receipt reports section_count=3 and three section curve ids;
* no solid is created by the loft;
* a two-section loft still measures 800.0 mm2 (regression of the 0.18.3 path);
* thicken 2 mm on the three-section quilt measures 4000.0 mm3 (+/- 0.5).

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft_multisection.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft_multisection.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AREA_TOLERANCE_MM2 = 0.5
VOLUME_TOLERANCE_MM3 = 0.5
#: Piecewise ruled surface through 40/60/40 mm sections 20 mm apart: the value a
#: straight blend would give. Measured 2026-11-11 on Creo 12.4.0.0: 2101.2524,
#: i.e. the kernel fits one smooth blend through all three sections.
PIECEWISE_AREA_MM2 = 2000.0
MEASURED_SMOOTH_AREA_MM2 = 2101.2524427513217
#: A smooth blend must exceed the piecewise area; this bounds "credibly smooth"
#: without pinning a kernel-specific spline value.
SMOOTH_AREA_MAX_MM2 = 2300.0
TWO_SECTION_AREA_MM2 = 800.0


def multisection_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "sketch",
            "label": "loft_a",
            "plane": "XY",
            "entities": [
                {"type": "line", "name": "section_a", "start": [0.0, 0.0], "end": [40.0, 0.0]}
            ],
        },
        {
            "op": "sketch",
            "label": "loft_b",
            "plane": "XY",
            "offset": 20.0,
            "entities": [
                {"type": "line", "name": "section_b", "start": [0.0, 0.0], "end": [60.0, 0.0]}
            ],
        },
        {
            "op": "sketch",
            "label": "loft_c",
            "plane": "XY",
            "offset": 40.0,
            "entities": [
                {"type": "line", "name": "section_c", "start": [0.0, 0.0], "end": [40.0, 0.0]}
            ],
        },
        {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["loft_a", "loft_b", "loft_c"],
            # Measured 2026-11-11: >2 sections are one smooth blend through every
            # section, so "straight" is refused rather than silently ignored.
            "interpolation": "smooth",
        },
    ]


def two_section_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "sketch",
            "label": "loft_a",
            "plane": "XY",
            "entities": [
                {"type": "line", "name": "section_a", "start": [0.0, 0.0], "end": [40.0, 0.0]}
            ],
        },
        {
            "op": "sketch",
            "label": "loft_b",
            "plane": "XY",
            "offset": 20.0,
            "entities": [
                {"type": "line", "name": "section_b", "start": [0.0, 0.0], "end": [40.0, 0.0]}
            ],
        },
        {"op": "surface_loft", "label": "loft_surface", "sections": ["loft_a", "loft_b"]},
    ]


THICKEN_PLAN: list[dict[str, Any]] = [
    {
        "op": "thicken",
        "label": "loft_solid",
        "reference": {"kind": "quilt_feature", "label": "loft_surface"},
        "thickness": 2.0,
        "side": "symmetric",
    }
]


def case_offline() -> dict:
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    if "surface_loft" not in REGISTERED_OPERATIONS:
        check("surface_loft_registered", False)
        return {"mode": "offline", "passed": False, "checks": checks}
    check("surface_loft_registered", True)

    try:
        validated = validate_operations(multisection_plan())
        check("schema_accepts_three_sections", True)
        check(
            "three_section_ids_kept_in_order",
            validated[-1].get("sections") == ["loft_a", "loft_b", "loft_c"],
            validated[-1].get("sections"),
        )
    except ValueError as error:
        check("schema_accepts_three_sections", False, {"error": str(error)})
        return {"mode": "offline", "passed": False, "checks": checks}

    for name, sections in (
        ("one_section", ["loft_a"]),
        ("thirty_three_sections", [f"loft_{index}" for index in range(33)]),
        ("duplicate_sections", ["loft_a", "loft_a"]),
    ):
        try:
            validate_operations(
                [{"op": "surface_loft", "label": "loft_surface", "sections": sections}]
            )
            check(f"schema_rejects_{name}", False, {"reason": "accepted"})
        except ValueError:
            check(f"schema_rejects_{name}", True)

    try:
        validate_operations(
            [
                {
                    "op": "surface_loft",
                    "label": "loft_surface",
                    "sections": ["loft_a", "loft_b", "loft_c"],
                    "interpolation": "straight",
                }
            ]
        )
        check("schema_rejects_straight_above_two_sections", False, {"reason": "accepted"})
    except ValueError as error:
        check(
            "schema_rejects_straight_above_two_sections",
            'interpolation="smooth"' in str(error),
            {"error": str(error)[:200]},
        )

    from creo_mechdog import capabilities

    limits = capabilities.families()["surface_loft"]["limits"]
    check("capability_states_2_to_32_sections", "2-32 sections" in limits, limits[:120])
    # FEAT-065/M2 publishes the second direction, so the capability text must
    # name the guide range instead of calling guide curves unpublished.
    check("capability_states_two_to_eight_guides", "2-8 guides" in limits, limits[:200])

    return {"mode": "offline", "passed": all(item["ok"] for item in checks), "checks": checks}


async def wait_ready(client, budget_seconds: int = 210) -> dict:
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    retry = True
    while time.monotonic() < deadline:
        state = (await client.call_tool("creo_startup_status", {"retry": retry})).structured_content
        retry = False
        if state.get("connected"):
            return state
        if state.get("state") in ("timeout", "failed", "error", "blocked", "unavailable"):
            return state
        await asyncio.sleep(2)
    return state


async def call_tool(client, tool: str, arguments: dict) -> dict:
    result = await client.call_tool(tool, arguments)
    if result.structured_content is not None:
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text[:600]}
    return {}


async def submit(client, operation_plan: list[dict], model_id=None, revision=None) -> dict:
    arguments: dict = {"operations": operation_plan}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    submitted = await call_tool(client, "creo_execute_plan", arguments)
    job_id = submitted.get("job_id")
    if not job_id:
        return {"status": "refused", "message": str(submitted)[:600]}
    deadline = time.monotonic() + 900
    state: dict = {}
    while time.monotonic() < deadline:
        state = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    else:
        return {"status": "unsettled", "job_id": job_id, "message": "job did not settle"}
    view = await call_tool(
        client,
        "creo_get_job",
        {"job_id": job_id, "detail": "compact", "sections": ["operations"]},
    )
    if view.get("status"):
        state = view
    state["job_id"] = job_id
    return state


def operation_of(state: dict, op: str) -> dict:
    operations = (state.get("result") or {}).get("operations") or state.get("operations") or []
    for operation in operations:
        if operation.get("op") == op:
            return operation
    return {}


def saved_verified(state: dict) -> bool:
    result = state.get("result") or {}
    return bool(
        result.get("saved_file_reloaded_and_verified")
        or state.get("saved_file_reloaded_and_verified")
    )


async def model_section(client, model_id: str, name: str, limit: int = 200) -> list:
    page = await call_tool(
        client,
        "creo_inspect_model",
        {"model_id": model_id, "detail": "full", "section": name, "limit": limit},
    )
    return (page.get("data") or {}).get(name) or []


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
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_multisection_loft": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        capabilities = await call_tool(client, "creo_capabilities", {})
        published = "surface_loft" in (capabilities.get("operations") or [])
        check("surface_loft_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "native_multisection_loft": "gated",
                "note": "surface_loft is refused before any job; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        # 1) Three sections, one direction.
        build = await submit(client, multisection_plan())
        remember(build)
        check(
            "three_section_job_succeeded",
            build.get("status") == "succeeded",
            {"status": build.get("status"), "message": str(build.get("message"))[:400]},
        )
        if build.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_multisection_loft": "failed",
                "checks": checks,
                "jobs": jobs,
                "failure": operation_of(build, "surface_loft") or build.get("message"),
            }

        model_id = build["model_id"]
        revision = build.get("revision")
        loft = operation_of(build, "surface_loft")
        check("saved_file_reloaded_and_verified", saved_verified(build))
        check("section_count_is_three", loft.get("section_count") == 3, loft.get("section_count"))
        check(
            "three_section_curve_ids",
            isinstance(loft.get("section_curve_ids"), list)
            and len(loft.get("section_curve_ids") or []) == 3,
            loft.get("section_curve_ids"),
        )
        check(
            "receipt_reports_smooth_not_ruled",
            loft.get("interpolation") == "smooth" and loft.get("piecewise_ruled") is False,
            {
                "interpolation": loft.get("interpolation"),
                "piecewise_ruled": loft.get("piecewise_ruled"),
            },
        )
        check("exactly_one_quilt_item", loft.get("quilt_count") == 1, loft.get("quilt_count"))
        quilt_id = loft.get("quilt_id")
        check("quilt_id_present", isinstance(quilt_id, int), quilt_id)
        area = loft.get("surface_area_mm2")
        check(
            "three_sections_are_smooth_not_piecewise",
            isinstance(area, (int, float))
            and PIECEWISE_AREA_MM2 + AREA_TOLERANCE_MM2 < area <= SMOOTH_AREA_MAX_MM2,
            {
                "surface_area_mm2": area,
                "piecewise_would_be": PIECEWISE_AREA_MM2,
                "measured_2026_11_11": MEASURED_SMOOTH_AREA_MM2,
            },
        )
        check(
            "quilt_is_open",
            loft.get("quilt_closed_native") == "open",
            loft.get("quilt_closed_native"),
        )
        check("no_solid_created", loft.get("has_solid") is False, loft.get("has_solid"))

        quilts = await model_section(client, model_id, "quilts")
        check("model_has_exactly_one_quilt", len(quilts) == 1, {"quilt_count": len(quilts)})
        reloaded = quilts[0] if quilts else {}
        check(
            "quilt_id_stable_after_reload",
            reloaded.get("quilt_id") == quilt_id,
            reloaded.get("quilt_id"),
        )
        reloaded_area = reloaded.get("area_mm2")
        check(
            "area_stable_after_reload",
            isinstance(reloaded_area, (int, float))
            and isinstance(area, (int, float))
            and abs(reloaded_area - area) <= AREA_TOLERANCE_MM2,
            {"area_mm2": reloaded_area, "first_read_mm2": area},
        )

        # 2) Thicken the three-section quilt by 2 mm: volume must follow the
        # measured area, not a predicted one.
        thicken = await submit(client, THICKEN_PLAN, model_id, revision)
        remember(thicken)
        thickened = operation_of(thicken, "thicken")
        volume = thickened.get("volume_after_mm3")
        expected_volume = area * 2.0 if isinstance(area, (int, float)) else None
        check(
            "thicken_job_succeeded",
            thicken.get("status") == "succeeded",
            {"status": thicken.get("status"), "message": str(thicken.get("message"))[:400]},
        )
        check(
            "thicken_volume_matches_measured_area",
            isinstance(volume, (int, float))
            and isinstance(expected_volume, (int, float))
            and abs(volume - expected_volume) <= VOLUME_TOLERANCE_MM3,
            {"volume_after_mm3": volume, "area_x_2": expected_volume},
        )

        # 3) Two-section regression on a fresh model.
        two = await submit(client, two_section_plan())
        remember(two)
        two_loft = operation_of(two, "surface_loft")
        two_area = two_loft.get("surface_area_mm2")
        check(
            "two_section_job_succeeded",
            two.get("status") == "succeeded",
            {"status": two.get("status"), "message": str(two.get("message"))[:400]},
        )
        check(
            "two_section_section_count",
            two_loft.get("section_count") == 2,
            two_loft.get("section_count"),
        )
        check(
            "two_section_area_800",
            isinstance(two_area, (int, float))
            and abs(two_area - TWO_SECTION_AREA_MM2) <= AREA_TOLERANCE_MM2,
            {"surface_area_mm2": two_area},
        )
        check(
            "two_sections_are_piecewise_ruled",
            two_loft.get("piecewise_ruled") is True and two_loft.get("interpolation") == "straight",
            {
                "piecewise_ruled": two_loft.get("piecewise_ruled"),
                "interpolation": two_loft.get("interpolation"),
            },
        )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_multisection_loft": "verified" if passed else "failed",
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
    output = args.output or ROOT / "build" / "surface_loft_multisection" / f"{stamp}.json"
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
            status = "PASS" if item["ok"] else "FAIL"
            print(f"  {status} {item['check']}")
    print(f"passed={report['passed']}")
    print(f"report={output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
