"""FEAT-065/M3 driver: surface_loft sections/guides beyond MCP sketches.

Default mode is offline: it checks the published contract without any Creo
session - schema admission of curve/edge references and of one convergence
point at the first or last section, the refusals that can be decided before a
job (a point in the middle or in the guides, two points, repeated references),
the capability/reference text that marks every new form "Creo 12.4 live
acceptance pending", and the native source route.

``--live --confirm-session-usable`` drives the public MCP tools against the
local Creo session. It must only be run after the user has confirmed the live
run for that session (AGENTS.md). The cases are:

(a) four-sided bridge: two surface-extruded strips (walls at y = 0 and y = 20,
    40 mm long, 10 mm high) are bridged by a loft whose two sections are the
    strips' top edges and whose guides are two sketch lines at z = 10. The
    expected quilt is the flat 40 x 20 rectangle (800.0 mm2). The section
    edges come from ``creo_measure_surface_group`` on {strip_a, strip_b}: its
    ``group.open_edge_records`` (FEAT-065 T1b) list every open boundary edge
    with its id and endpoints, and the driver picks the one edge per strip
    whose endpoints are the two guide ends (order-insensitive, 0.01 mm). One
    loft is submitted; nothing is probed. ``--bridge-edges A B`` still names
    the two edges by hand. The group {strip_a, strip_b, bridge} is then
    measured again (seam gap, joined and open edges; the two section edges
    must no longer be open). A solid block cannot replace the strips:
    surface_loft refuses any model that holds solid material (``has_solid``).
(b) projected curve: a line projected onto a 40 x 20 fill (``project_curve``,
    z = 0, y = 10) is the first section; a sketch line at z = 20, y = 30 is the
    second. Ruled area 40 x 20*sqrt(2) = 1131.3708 mm2.
(c) bulbous-bow simplification: three YZ ellipse sections along X (x = 0, 20,
    40) as a smooth blend without a point (c0, the arbitrary orthogonal plane
    case), then the same sections converging to a single-point datum_points
    tip at x = 60 (c, the experimental point holder).
(d) negatives: a nonexistent edge id fails the job with
    SURFACE_LOFT_INPUT_REJECTED and a failed_loft_input block; a point in a
    middle section is refused before a job exists.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft_inputs.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft_inputs.py --live --confirm-session-usable
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

PRO_CURVE_TYPE = 62
AREA_TOLERANCE_MM2 = 0.5
BBOX_TOLERANCE_MM = 0.5
#: An id far above anything a small test model allocates.
MISSING_EDGE_ID = 2147480000

# (a) four-sided bridge
STRIP_LENGTH_MM = 40.0
STRIP_HEIGHT_MM = 10.0
STRIP_GAP_MM = 20.0
BRIDGE_AREA_MM2 = STRIP_LENGTH_MM * STRIP_GAP_MM
#: The strip top edges end exactly on the guide ends; each strip has one.
BRIDGE_SECTION_ENDPOINTS = {
    "strip_a": ((0.0, 0.0, STRIP_HEIGHT_MM), (STRIP_LENGTH_MM, 0.0, STRIP_HEIGHT_MM)),
    "strip_b": (
        (0.0, STRIP_GAP_MM, STRIP_HEIGHT_MM),
        (STRIP_LENGTH_MM, STRIP_GAP_MM, STRIP_HEIGHT_MM),
    ),
}
ENDPOINT_TOLERANCE_MM = 0.01

# (b) projected curve section
PROJECT_WIDTH_MM = 40.0
PROJECT_HEIGHT_MM = 20.0
PROJECT_LINE_Y_MM = 10.0
PROJECT_SOURCE_Z_MM = 10.0
TOP_SECTION_Z_MM = 20.0
TOP_SECTION_Y_MM = 30.0
PROJECTED_AREA_MM2 = PROJECT_WIDTH_MM * math.hypot(
    TOP_SECTION_Z_MM, TOP_SECTION_Y_MM - PROJECT_LINE_Y_MM
)

# (c) bulbous-bow simplification: (x position, half-width y, half-height z)
BULB_SECTIONS = ((0.0, 12.0, 8.0), (20.0, 10.0, 7.0), (40.0, 6.0, 4.0))
BULB_TIP_X_MM = 60.0


def line_sketch(label: str, offset: float, start: list, end: list, plane: str = "XY") -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "offset": offset,
        "entities": [{"type": "line", "name": "l", "start": start, "end": end}],
    }


def edge_ref(identifier: int) -> dict:
    return {"kind": "edge", "id": identifier}


def _point_matches(point: Any, expected: tuple, tolerance: float) -> bool:
    if not isinstance(point, list) or len(point) != len(expected):
        return False
    for value, target in zip(point, expected):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not abs(float(value) - target) <= tolerance:
            return False
    return True


def edges_with_endpoints(
    records: Any, ends: tuple, tolerance: float = ENDPOINT_TOLERANCE_MM
) -> list[dict]:
    """Open edge records whose two endpoints are ``ends``, in either order."""
    found: list[dict] = []
    for record in records if isinstance(records, list) else []:
        points = record.get("endpoints_mm") if isinstance(record, dict) else None
        if not isinstance(points, list) or len(points) != 2:
            continue
        first, second = points
        if (
            _point_matches(first, ends[0], tolerance) and _point_matches(second, ends[1], tolerance)
        ) or (
            _point_matches(first, ends[1], tolerance) and _point_matches(second, ends[0], tolerance)
        ):
            found.append(record)
    return found


def pick_bridge_edges(group: Any) -> tuple[list[int] | None, dict]:
    """(a) the one open edge per strip whose endpoints are the two guide ends.

    Reads ``group.open_edge_records`` of a ``creo_measure_surface_group``
    receipt and returns ``[strip_a_edge_id, strip_b_edge_id]``, or ``None`` with
    the reason. A missing list, no match or more than one match per strip, a
    match without an id and two matches on the same quilt are refusals: the
    driver never guesses an edge or falls back to probing.
    """
    group = group if isinstance(group, dict) else {}
    records = group.get("open_edge_records")
    detail: dict[str, Any] = {
        "open_edge_records_total": group.get("open_edge_records_total"),
        "open_edge_records_truncated": group.get("open_edge_records_truncated"),
    }
    if not isinstance(records, list):
        detail["reason"] = "open_edge_records_missing"
        return None, detail
    chosen: dict[str, dict] = {}
    for strip, ends in BRIDGE_SECTION_ENDPOINTS.items():
        matches = edges_with_endpoints(records, ends)
        detail[strip] = matches
        if len(matches) != 1:
            state = "ambiguous" if matches else "missing"
            if not matches and group.get("open_edge_records_truncated") is True:
                state = "missing_from_a_truncated_list"
            detail["reason"] = f"{strip}_top_edge_{state}"
            return None, detail
        chosen[strip] = matches[0]
    ids = [chosen[strip].get("edge_id") for strip in BRIDGE_SECTION_ENDPOINTS]
    quilts = [chosen[strip].get("quilt_id") for strip in BRIDGE_SECTION_ENDPOINTS]
    if not all(type(value) is int and value >= 0 for value in ids):
        detail["reason"] = "top_edge_id_unavailable"
        return None, detail
    if not all(type(value) is int for value in quilts) or quilts[0] == quilts[1]:
        detail["reason"] = "top_edges_not_on_two_quilts"
        return None, detail
    return ids, detail


def synthetic_strip_group(**overrides: Any) -> dict:
    """An offline stand-in for the {strip_a, strip_b} measurement receipt.

    Four open edges per strip in a shuffled visit order; the strip_b top edge
    runs backwards so the picker must match endpoints in either order.
    """
    h, length, gap = STRIP_HEIGHT_MM, STRIP_LENGTH_MM, STRIP_GAP_MM
    edges = [
        (101, 21, [[0.0, 0.0, 0.0], [length, 0.0, 0.0]]),
        (102, 21, [[length, 0.0, 0.0], [length, 0.0, h]]),
        (103, 21, [[0.0, 0.0, h], [length, 0.0, h]]),
        (104, 21, [[0.0, 0.0, h], [0.0, 0.0, 0.0]]),
        (201, 22, [[0.0, gap, 0.0], [0.0, gap, h]]),
        (202, 22, [[length, gap, h], [0.0, gap, h]]),
        (203, 22, [[0.0, gap, 0.0], [length, gap, 0.0]]),
        (204, 22, [[length, gap, 0.0], [length, gap, h]]),
    ]
    records = [
        {
            "edge_id": edge_id,
            "surface_id": quilt + 10,
            "quilt_id": quilt,
            "length_mm": math.dist(*ends),
            "endpoints_mm": ends,
        }
        for edge_id, quilt, ends in edges
    ]
    group = {
        "quilt_ids": [21, 22],
        "open_edges": len(records),
        "open_edges_status": {"available": True, "scale_to_mm_known": True, "unit_name": "mm"},
        "open_edge_records": records,
        "open_edge_records_total": len(records),
        "open_edge_records_truncated": False,
        "open_edge_records_status": {
            "available": True,
            "reason": None,
            "query_code": 0,
            "scale_to_mm_known": True,
            "unit_name": "mm",
            "limit": 32,
        },
        "state": "open",
    }
    group.update(overrides)
    return group


# ----------------------------------------------------------------------------
# Plans
# ----------------------------------------------------------------------------


def bridge_build_plan() -> list[dict]:
    """(a) two vertical surface strips and two guide lines on the z = 10 plane."""
    return [
        line_sketch("strip_a_line", 0.0, [0.0, 0.0], [STRIP_LENGTH_MM, 0.0]),
        {
            "op": "extrude",
            "label": "strip_a",
            "sketch": "strip_a_line",
            "depth": STRIP_HEIGHT_MM,
            "mode": "surface",
        },
        line_sketch("strip_b_line", 0.0, [0.0, STRIP_GAP_MM], [STRIP_LENGTH_MM, STRIP_GAP_MM]),
        {
            "op": "extrude",
            "label": "strip_b",
            "sketch": "strip_b_line",
            "depth": STRIP_HEIGHT_MM,
            "mode": "surface",
        },
        line_sketch("guide_l", STRIP_HEIGHT_MM, [0.0, 0.0], [0.0, STRIP_GAP_MM]),
        line_sketch(
            "guide_r", STRIP_HEIGHT_MM, [STRIP_LENGTH_MM, 0.0], [STRIP_LENGTH_MM, STRIP_GAP_MM]
        ),
    ]


def bridge_loft(edge_a: int, edge_b: int) -> dict:
    return {
        "op": "surface_loft",
        "label": "bridge",
        "sections": [edge_ref(edge_a), edge_ref(edge_b)],
        "guides": ["guide_l", "guide_r"],
    }


def projection_build_plan() -> list[dict]:
    """(b) a 40 x 20 fill at z = 0, the source line at z = 10 and the top section."""
    return [
        {
            "op": "sketch",
            "label": "proj_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect",
                    "min": [0.0, 0.0],
                    "max": [PROJECT_WIDTH_MM, PROJECT_HEIGHT_MM],
                }
            ],
        },
        {"op": "surface_fill", "label": "proj_target", "sketch": "proj_profile"},
        line_sketch(
            "proj_src",
            PROJECT_SOURCE_Z_MM,
            [0.0, PROJECT_LINE_Y_MM],
            [PROJECT_WIDTH_MM, PROJECT_LINE_Y_MM],
        ),
        {
            "op": "datum_plane",
            "label": "proj_dir",
            "reference": {"kind": "datum_plane", "axis": "z", "offset": 0.0},
            "offset": PROJECT_SOURCE_Z_MM + 20.0,
        },
        line_sketch(
            "sec_top",
            TOP_SECTION_Z_MM,
            [0.0, TOP_SECTION_Y_MM],
            [PROJECT_WIDTH_MM, TOP_SECTION_Y_MM],
        ),
    ]


def projection_operation(source_curve_id: int) -> dict:
    # Same direction convention as tools/test_surface_chain.py: the direction
    # plane sits above the source and "negative" projects down onto z = 0.
    return {
        "op": "project_curve",
        "label": "proj_curve",
        "target": {"kind": "quilt_feature", "label": "proj_target"},
        "source": {"kind": "curve", "id": source_curve_id},
        "direction_ref": {"kind": "datum_feature", "label": "proj_dir"},
        "side": "negative",
    }


def projection_loft(curve_id: int) -> dict:
    return {
        "op": "surface_loft",
        "label": "proj_loft",
        "sections": [{"kind": "curve", "id": curve_id}, "sec_top"],
    }


def bulb_plan(with_tip: bool) -> list[dict]:
    """(c) YZ ellipses along X; with_tip adds one convergence point at x = 60."""
    plan: list[dict] = []
    labels: list[Any] = []
    for index, (x, half_y, half_z) in enumerate(BULB_SECTIONS):
        label = f"bulb_{index}"
        plan.append(
            {
                "op": "sketch",
                "label": label,
                "plane": "YZ",
                "offset": x,
                "entities": [
                    {
                        "type": "ellipse",
                        "name": "e",
                        "center": [0.0, 0.0],
                        "x_radius": half_y,
                        "y_radius": half_z,
                    }
                ],
            }
        )
        labels.append(label)
    if with_tip:
        plan.append(
            {
                "op": "datum_points",
                "label": "bow_tip",
                "points": [{"name": "tip", "position": [BULB_TIP_X_MM, 0.0, 0.0]}],
            }
        )
        labels.append({"kind": "datum_point_feature", "label": "bow_tip"})
    plan.append(
        {
            "op": "surface_loft",
            "label": "bulb",
            "sections": labels,
            "interpolation": "smooth",
        }
    )
    return plan


def missing_edge_plan() -> list[dict]:
    """(d1) a valid sketch section next to an edge id that cannot exist."""
    return [
        line_sketch("sec_a", 0.0, [0.0, 0.0], [40.0, 0.0]),
        {
            "op": "surface_loft",
            "label": "bad_loft",
            "sections": [edge_ref(MISSING_EDGE_ID), "sec_a"],
        },
    ]


def middle_point_plan() -> list[dict]:
    """(d2) a point between two sections: refused before a job exists."""
    return [
        line_sketch("sec_a", 0.0, [0.0, 0.0], [40.0, 0.0]),
        line_sketch("sec_b", 20.0, [0.0, 0.0], [40.0, 0.0]),
        {
            "op": "datum_points",
            "label": "mid_tip",
            "points": [{"name": "tip", "position": [20.0, 0.0, 10.0]}],
        },
        {
            "op": "surface_loft",
            "label": "bad_loft",
            "sections": ["sec_a", {"kind": "datum_point_feature", "label": "mid_tip"}, "sec_b"],
            "interpolation": "smooth",
        },
    ]


# ----------------------------------------------------------------------------
# Offline contract
# ----------------------------------------------------------------------------


def case_offline() -> dict:
    from creo_mechdog import capabilities
    from creo_mechdog.references import reference_capabilities
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append(
            {"check": name, "ok": bool(ok), **({"detail": detail} if detail is not None else {})}
        )

    def accepts(name: str, plan: list[dict]) -> list[dict] | None:
        try:
            validated = validate_operations(plan)
        except ValueError as error:
            check(f"schema_accepts_{name}", False, {"error": str(error)[:300]})
            return None
        check(f"schema_accepts_{name}", True)
        return validated

    def refuses(name: str, plan: list[dict], phrase: str) -> None:
        try:
            validate_operations(plan)
        except ValueError as error:
            check(f"schema_refuses_{name}", phrase in str(error), {"error": str(error)[:300]})
            return
        check(f"schema_refuses_{name}", False, {"reason": "accepted"})

    validated = accepts(
        "edge_sections_with_sketch_guides", [*bridge_build_plan(), bridge_loft(11, 12)]
    )
    if validated:
        check(
            "edge_references_kept_verbatim",
            validated[-1]["sections"] == [edge_ref(11), edge_ref(12)],
            validated[-1]["sections"],
        )
    accepts("projected_curve_section", [*projection_build_plan(), projection_loft(41)])
    validated = accepts("yz_ellipses_along_x", bulb_plan(with_tip=False))
    if validated:
        planes = [op.get("plane") for op in validated if op["op"] == "sketch"]
        check("bulb_sections_are_yz", planes == ["YZ"] * len(BULB_SECTIONS), planes)
    validated = accepts("yz_ellipses_with_end_point", bulb_plan(with_tip=True))
    if validated:
        check(
            "point_is_the_last_section",
            validated[-1]["sections"][-1] == {"kind": "datum_point_feature", "label": "bow_tip"},
        )
    accepts("missing_edge_plan_is_admitted_for_native_rejection", missing_edge_plan())

    refuses("middle_point", middle_point_plan(), "sections[1] is a point")
    plan = [*bridge_build_plan(), bridge_loft(11, 12)]
    plan[-1]["guides"] = ["guide_l", {"kind": "point", "id": 5}]
    refuses("point_guide", plan, "guides[1] is a point")
    plan = [*bridge_build_plan(), bridge_loft(11, 12)]
    plan[-1]["sections"] = [{"kind": "point", "id": 5}, {"kind": "point", "id": 6}]
    refuses("two_points", plan, "one convergence point")
    refuses("repeated_edge", [*bridge_build_plan(), bridge_loft(11, 11)], "repeats sections[0]")
    plan = [*bridge_build_plan(), bridge_loft(11, 12)]
    plan[-1]["sections"][0] = {"kind": "edge", "label": "top_a"}
    refuses("edge_label", plan, "takes an id, not a label")
    plan = [*bridge_build_plan(), bridge_loft(11, 12)]
    plan[-1]["sections"][0] = {"kind": "quilt_feature", "label": "strip_a"}
    refuses("quilt_as_section", plan, "pass one of its edges")
    plan = [*bridge_build_plan(), bridge_loft(11, 12)]
    plan[-1]["guides"] = [edge_ref(11), "guide_r"]
    refuses("edge_as_section_and_guide", plan, "cannot be both a section and a guide")
    plan = bulb_plan(with_tip=True)
    plan[-2]["points"].append({"name": "tip2", "position": [61.0, 0.0, 0.0]})
    refuses("multi_point_tip", plan, "single-point datum_points feature")

    family = capabilities.families()["surface_loft"]
    limits = family["limits"]
    for name, phrase in (
        ("live_status", "not live-verified on Creo 12.4"),
        ("curve_form", "{kind:'curve',id:N}"),
        ("edge_form", "{kind:'edge',id:N}"),
        ("point_position", "first or last section only"),
        ("receipt_marker", "unverified_input_forms"),
    ):
        check(f"capability_limits_name_{name}", phrase in limits)
    check("capability_scope_marks_live_pending", "live acceptance pending" in family["scope"])
    check("capability_prefix_unchanged", limits.startswith("2-32 sections and, optionally, 2-8"))
    entry = reference_capabilities()["by_tool"].get("creo_surface_loft") or {}
    check("references_publish_the_loft_shapes", "not live-verified" in entry.get("live_status", ""))

    server = (ROOT / "server.py").read_text(encoding="utf-8")
    check(
        "tool_signature_accepts_reference_objects",
        "sections: Annotated[list[str | int | dict[str, Any]]" in server
        and "guides: Annotated[list[str | int | dict[str, Any]]" in server,
    )
    native = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")
    code = "\n".join(line for line in native.splitlines() if not line.lstrip().startswith("//"))
    check(
        "native_point_holder_uses_the_documented_instruction",
        "PRO_CURVCOLL_ADD_POINT_INSTR" in code,
    )
    check("native_rejects_inputs_with_a_structured_block", "failed_loft_input" in code)
    check("native_reports_unverified_forms", "unverified_input_forms" in code)

    # (a) edge discovery: creo_measure_surface_group publishes the open edges
    # (FEAT-065 T1b) and the driver picks the section edges by their endpoints.
    picked, detail = pick_bridge_edges(synthetic_strip_group())
    check("open_edge_picker_finds_both_top_edges", picked == [103, 202], detail)
    group = synthetic_strip_group()
    group["open_edge_records"] = [*group["open_edge_records"], dict(group["open_edge_records"][2])]
    picked, detail = pick_bridge_edges(group)
    check(
        "open_edge_picker_refuses_an_ambiguous_match",
        picked is None and detail.get("reason") == "strip_a_top_edge_ambiguous",
        detail.get("reason"),
    )
    group = synthetic_strip_group(open_edge_records_truncated=True)
    group["open_edge_records"] = group["open_edge_records"][:4]
    picked, detail = pick_bridge_edges(group)
    check(
        "open_edge_picker_names_a_truncated_list",
        picked is None and detail.get("reason") == "strip_b_top_edge_missing_from_a_truncated_list",
        detail.get("reason"),
    )
    picked, detail = pick_bridge_edges(synthetic_strip_group(open_edge_records=None))
    check(
        "open_edge_picker_refuses_a_missing_list",
        picked is None and detail.get("reason") == "open_edge_records_missing",
        detail.get("reason"),
    )
    from creo_mechdog.operation_results import normalize_surface_group

    unknown_units = synthetic_strip_group()
    unknown_units["open_edge_records_status"] = {
        **unknown_units["open_edge_records_status"],
        "scale_to_mm_known": False,
        "mm_values_reason": "unit_scale_unknown",
    }
    cleaned = normalize_surface_group(unknown_units) or {}
    records = cleaned.get("open_edge_records") or []
    check(
        "unknown_unit_scale_keeps_ids_and_nulls_mm_values",
        len(records) == 8
        and all(isinstance(record["edge_id"], int) for record in records)
        and all(
            record["endpoints_mm"] is None and record["length_mm"] is None for record in records
        )
        and pick_bridge_edges(cleaned)[0] is None,
        records[:2],
    )
    tool = server[server.index("async def creo_measure_surface_group(") :]
    tool = tool[: tool.index('"""', tool.index('"""') + 3)]
    check(
        "measure_tool_documents_the_open_edge_records",
        "group.open_edge_records" in tool and "live acceptance pending" in tool,
    )
    group_native = (ROOT / "native" / "surface_group.cpp").read_text(encoding="utf-8")
    group_code = "\n".join(
        line for line in group_native.splitlines() if not line.lstrip().startswith("//")
    )
    check(
        "native_measurement_publishes_open_edge_records",
        all(
            phrase in group_code
            for phrase in (
                'group["open_edge_records"]',
                'group["open_edge_records_total"]',
                'group["open_edge_records_truncated"]',
                "SURFACE_GROUP_OPEN_EDGE_RECORD_LIMIT",
                "ProEdgeXyzdataEval(edge, (double)end",
            )
        ),
    )

    return {"mode": "offline", "passed": all(item["ok"] for item in checks), "checks": checks}


# ----------------------------------------------------------------------------
# Live cases (only after the user's per-session confirmation)
# ----------------------------------------------------------------------------


class Recorder:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []
        self.observations: dict[str, Any] = {}

    def check(self, name: str, ok: bool, detail: Any = None) -> bool:
        self.checks.append(
            {"check": name, "ok": bool(ok), **({"detail": detail} if detail is not None else {})}
        )
        return bool(ok)

    def remember(self, case: str, state: dict) -> None:
        self.jobs.append(
            {
                "case": case,
                "job_id": state.get("job_id"),
                "status": state.get("status"),
                "model_id": state.get("model_id"),
                "revision": state.get("revision"),
                "message": str(state.get("message"))[:300],
            }
        )


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, expected: float, tolerance: float) -> bool:
    number = _number(value)
    return number is not None and abs(number - expected) <= tolerance


async def feature_id_of(client, model_id: str, label: str) -> int | None:
    for feature in await harness.model_section(client, model_id, "features"):
        if str(feature.get("name", "")).lower() == label:
            return feature.get("id")
    return None


async def geometry_ids(client, model_id: str, feature_id: int | None, item_type: int) -> list[int]:
    if feature_id is None:
        return []
    items = await harness.model_section(client, model_id, "feature_geometry")
    return [
        item["id"]
        for item in items
        if item.get("feature_id") == feature_id and item.get("type") == item_type
    ]


async def quilt_record(client, model_id: str, quilt_id: Any) -> dict:
    for quilt in await harness.model_section(client, model_id, "quilts"):
        if quilt.get("quilt_id") == quilt_id:
            return quilt
    return {}


async def case_a_edge_bridge(client, rec: Recorder, bridge_edges: list[int] | None) -> None:
    build = await harness.submit(client, bridge_build_plan())
    rec.remember("a_build", build)
    if not rec.check(
        "a_strips_built",
        build.get("status") == "succeeded",
        {"status": build.get("status"), "message": str(build.get("message"))[:300]},
    ):
        return
    model_id, revision = build["model_id"], build.get("revision")
    strips = [
        {"kind": "quilt_feature", "label": "strip_a"},
        {"kind": "quilt_feature", "label": "strip_b"},
    ]

    if bridge_edges:
        edge_a, edge_b = bridge_edges
        rec.observations["a_edge_source"] = "--bridge-edges"
    else:
        # FEAT-065 T1b: the open boundary edges of both strips, ids plus
        # endpoints, from one read-only measurement; no candidate is probed.
        measured, is_error = await measure_group(client, model_id, strips)
        group = measured.get("group") or {}
        records = group.get("open_edge_records")
        summary = {
            "job_id": measured.get("job_id"),
            "is_error": is_error,
            "open_edges": group.get("open_edges"),
            "open_edge_records_total": group.get("open_edge_records_total"),
            "open_edge_records_truncated": group.get("open_edge_records_truncated"),
            "open_edge_records_status": group.get("open_edge_records_status"),
        }
        rec.observations["a_strip_open_edges"] = {**summary, "open_edge_records": records}
        if not rec.check(
            "a_strip_open_edge_records_published",
            not is_error
            and isinstance(records, list)
            and isinstance(group.get("open_edges"), int)
            and group.get("open_edge_records_total") == group.get("open_edges")
            and len(records) == group.get("open_edges")
            and group.get("open_edge_records_truncated") is False,
            summary,
        ):
            return
        rec.check(
            "a_two_separate_strips_have_eight_open_edges",
            group.get("open_edges") == 8,
            summary,
        )
        rec.check(
            "a_measurement_kept_the_revision",
            measured.get("revision") == revision,
            {"measured": measured.get("revision"), "build": revision},
        )
        picked, detail = pick_bridge_edges(group)
        if not rec.check("a_top_edges_found_by_endpoints", picked is not None, detail):
            return
        edge_a, edge_b = picked
        rec.check(
            "a_top_edges_are_strip_long",
            all(
                _near(match[0].get("length_mm"), STRIP_LENGTH_MM, ENDPOINT_TOLERANCE_MM)
                for match in (detail["strip_a"], detail["strip_b"])
            ),
            {strip: detail[strip] for strip in BRIDGE_SECTION_ENDPOINTS},
        )
        rec.observations["a_edge_source"] = "creo_measure_surface_group open_edge_records"
    rec.observations["a_section_edges"] = [edge_a, edge_b]

    bridged = await harness.submit(client, [bridge_loft(edge_a, edge_b)], model_id, revision)
    rec.remember("a_bridge", bridged)
    loft = harness.operation_of(bridged, "surface_loft")
    if not rec.check(
        "a_bridge_succeeded",
        bridged.get("status") == "succeeded",
        {
            "status": bridged.get("status"),
            "message": str(bridged.get("message"))[:400],
            "failed_loft_input": loft.get("failed_loft_input"),
        },
    ):
        return
    rec.check("a_saved_file_reloaded_and_verified", harness.saved_verified(bridged))
    rec.check(
        "a_sources_are_edges",
        loft.get("section_source_kinds") == ["edge", "edge"]
        and loft.get("guide_source_kinds") == ["sketch", "sketch"]
        and "edge" in (loft.get("unverified_input_forms") or []),
        {
            "section_source_kinds": loft.get("section_source_kinds"),
            "section_geometry_ids": loft.get("section_geometry_ids"),
            "unverified_input_forms": loft.get("unverified_input_forms"),
        },
    )
    rec.check(
        "a_bridge_is_the_flat_rectangle",
        _near(loft.get("surface_area_mm2"), BRIDGE_AREA_MM2, AREA_TOLERANCE_MM2),
        {"surface_area_mm2": loft.get("surface_area_mm2"), "expected": BRIDGE_AREA_MM2},
    )
    rec.check(
        "a_one_open_quilt_no_solid",
        loft.get("quilt_count") == 1
        and loft.get("quilt_closed_native") == "open"
        and loft.get("has_solid") is False,
        {
            "quilt_count": loft.get("quilt_count"),
            "closure": loft.get("quilt_closed_native"),
            "has_solid": loft.get("has_solid"),
        },
    )
    sources = loft.get("section_sources") or []
    rec.observations["a_section_sources"] = sources
    rec.check(
        "a_edge_sources_name_their_faces",
        len(sources) == 2
        and all(isinstance(item.get("adjacent_surface_ids"), list) for item in sources),
        sources,
    )
    box = (await quilt_record(client, bridged["model_id"], loft.get("quilt_id"))).get("bbox_mm")
    rec.check(
        "a_bridge_lies_on_the_strip_tops",
        isinstance(box, list)
        and _near(box[0][2], STRIP_HEIGHT_MM, BBOX_TOLERANCE_MM)
        and _near(box[1][2], STRIP_HEIGHT_MM, BBOX_TOLERANCE_MM),
        {"bbox_mm": box},
    )
    measured, is_error = await measure_group(
        client,
        bridged["model_id"],
        [*strips, {"kind": "quilt_feature", "label": "bridge"}],
    )
    group = measured.get("group") or {}
    rec.observations["a_group"] = {
        key: group.get(key)
        for key in (
            "state",
            "state_reason",
            "boundary_edges",
            "joined_edges",
            "open_edges",
            "gap_max_mm",
            "boundary_closed",
            "open_edge_records_total",
            "open_edge_records_truncated",
        )
    }
    rec.check(
        "a_group_measured",
        not is_error and group.get("open_edges") is not None,
        rec.observations["a_group"],
    )
    gap = _number(group.get("gap_max_mm"))
    rec.check(
        "a_bridge_seams_join_the_strips",
        (group.get("joined_edges") or 0) >= 2 and (gap is None or gap <= 0.01),
        rec.observations["a_group"],
    )
    rec.check(
        "a_group_is_open", group.get("boundary_closed") is False, group.get("boundary_closed")
    )
    still_open = [
        record.get("edge_id")
        for record in group.get("open_edge_records") or []
        if isinstance(record, dict) and record.get("edge_id") in (edge_a, edge_b)
    ]
    rec.check(
        "a_section_edges_no_longer_open",
        isinstance(group.get("open_edge_records"), list)
        and group.get("open_edge_records_truncated") is False
        and not still_open,
        {"section_edges": [edge_a, edge_b], "still_open": still_open},
    )


async def measure_group(client, model_id: str, references: list[dict]) -> tuple[dict, bool]:
    result = await client.call_tool(
        "creo_measure_surface_group", {"model_id": model_id, "references": references}
    )
    payload: dict = result.structured_content or {}
    if not payload:
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {"raw": text[:600]}
                break
    return payload, bool(getattr(result, "isError", False))


async def case_b_projected_curve(client, rec: Recorder) -> None:
    build = await harness.submit(client, projection_build_plan())
    rec.remember("b_build", build)
    if not rec.check(
        "b_projection_scene_built",
        build.get("status") == "succeeded",
        {"status": build.get("status"), "message": str(build.get("message"))[:300]},
    ):
        return
    model_id = build["model_id"]
    source = await geometry_ids(
        client, model_id, await feature_id_of(client, model_id, "proj_src"), PRO_CURVE_TYPE
    )
    if not rec.check("b_source_curve_found", bool(source), {"curve_ids": source}):
        return
    projected = await harness.submit(
        client, [projection_operation(source[0])], model_id, build.get("revision")
    )
    rec.remember("b_project", projected)
    curve_id = harness.operation_of(projected, "project_curve").get("curve_id")
    if not rec.check(
        "b_projection_succeeded",
        projected.get("status") == "succeeded" and isinstance(curve_id, int),
        {"status": projected.get("status"), "curve_id": curve_id},
    ):
        return
    lofted = await harness.submit(
        client, [projection_loft(curve_id)], model_id, projected.get("revision")
    )
    rec.remember("b_loft", lofted)
    if not rec.check(
        "b_loft_succeeded",
        lofted.get("status") == "succeeded",
        {"status": lofted.get("status"), "message": str(lofted.get("message"))[:400]},
    ):
        rec.observations["b_failure"] = harness.operation_of(lofted, "surface_loft")
        return
    loft = harness.operation_of(lofted, "surface_loft")
    rec.check("b_saved_file_reloaded_and_verified", harness.saved_verified(lofted))
    rec.check(
        "b_sources_are_curve_then_sketch",
        loft.get("section_source_kinds") == ["curve", "sketch"]
        and (loft.get("section_geometry_ids") or [[None]])[0] == [curve_id]
        and loft.get("unverified_input_forms") == ["curve"],
        {
            "section_source_kinds": loft.get("section_source_kinds"),
            "section_geometry_ids": loft.get("section_geometry_ids"),
            "unverified_input_forms": loft.get("unverified_input_forms"),
        },
    )
    rec.check(
        "b_ruled_area_matches",
        _near(loft.get("surface_area_mm2"), PROJECTED_AREA_MM2, AREA_TOLERANCE_MM2),
        {"surface_area_mm2": loft.get("surface_area_mm2"), "expected": PROJECTED_AREA_MM2},
    )
    rec.check(
        "b_one_open_quilt_no_solid",
        loft.get("quilt_count") == 1
        and loft.get("quilt_closed_native") == "open"
        and loft.get("has_solid") is False,
    )


async def case_c_bulb_convergence(client, rec: Recorder) -> None:
    max_half_y = max(half_y for _, half_y, _ in BULB_SECTIONS)
    for name, with_tip, x_end in (("c0", False, BULB_SECTIONS[-1][0]), ("c", True, BULB_TIP_X_MM)):
        state = await harness.submit(client, bulb_plan(with_tip))
        rec.remember(f"{name}_bulb", state)
        loft = harness.operation_of(state, "surface_loft")
        if not rec.check(
            f"{name}_bulb_succeeded",
            state.get("status") == "succeeded",
            {
                "status": state.get("status"),
                "message": str(state.get("message"))[:400],
                "failed_loft_input": loft.get("failed_loft_input"),
                "convergence_point": loft.get("convergence_point"),
            },
        ):
            rec.observations[f"{name}_failure"] = loft or state.get("message")
            continue
        rec.check(f"{name}_saved_file_reloaded_and_verified", harness.saved_verified(state))
        expected_kinds = ["sketch"] * len(BULB_SECTIONS) + (["point"] if with_tip else [])
        rec.check(
            f"{name}_section_sources",
            loft.get("section_source_kinds") == expected_kinds
            and loft.get("section_count") == len(expected_kinds),
            {
                "section_source_kinds": loft.get("section_source_kinds"),
                "section_count": loft.get("section_count"),
            },
        )
        rec.check(
            f"{name}_one_open_quilt_no_solid",
            loft.get("quilt_count") == 1
            and loft.get("quilt_closed_native") == "open"
            and loft.get("has_solid") is False,
        )
        if with_tip:
            point = loft.get("convergence_point") or {}
            rec.check(
                "c_convergence_point_reported",
                point.get("position") == "end"
                and point.get("live_verified") is False
                and loft.get("unverified_input_forms") == ["point"],
                {"convergence_point": point, "unverified": loft.get("unverified_input_forms")},
            )
        box = (await quilt_record(client, state["model_id"], loft.get("quilt_id"))).get("bbox_mm")
        rec.observations[f"{name}_bbox_mm"] = box
        # Which sketch axis of the YZ plane carries x_radius is not asserted:
        # the widest half-extent may land on Y or on Z.
        widest = (
            max(_number(box[1][1]) or 0.0, _number(box[1][2]) or 0.0)
            if isinstance(box, list)
            else None
        )
        rec.check(
            f"{name}_spans_the_sections_along_x",
            isinstance(box, list)
            and _near(box[0][0], BULB_SECTIONS[0][0], BBOX_TOLERANCE_MM)
            and _near(box[1][0], x_end, BBOX_TOLERANCE_MM)
            and widest is not None
            and widest >= max_half_y - BBOX_TOLERANCE_MM,
            {"bbox_mm": box, "x_end_mm": x_end, "max_half_extent_mm": max_half_y},
        )
        rec.observations[f"{name}_surface_area_mm2"] = loft.get("surface_area_mm2")


async def case_d_negative(client, rec: Recorder) -> None:
    missing = await harness.submit(client, missing_edge_plan())
    rec.remember("d_missing_edge", missing)
    loft = harness.operation_of(missing, "surface_loft")
    failure = loft.get("failed_loft_input") or {}
    rec.check(
        "d_missing_edge_fails_with_a_structured_rejection",
        missing.get("status") == "failed"
        and "SURFACE_LOFT_INPUT_REJECTED" in str(missing.get("message"))
        and failure.get("reason") == "edge_not_found"
        and failure.get("slot") == "sections[0]",
        {"status": missing.get("status"), "failed_loft_input": failure},
    )
    refused = await harness.call_tool(
        client, "creo_execute_plan", {"operations": middle_point_plan()}
    )
    rec.check(
        "d_middle_point_refused_before_a_job",
        not refused.get("job_id") and "sections[1] is a point" in json.dumps(refused),
        {"response": str(refused)[:300]},
    )


async def case_live(bridge_edges: list[int] | None) -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    rec = Recorder()
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await harness.wait_ready(client)
        if not rec.check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        ):
            return {
                "mode": "live",
                "passed": False,
                "note": "the session never reported connected; no geometry was submitted",
                "checks": rec.checks,
                "jobs": rec.jobs,
            }
        capabilities = await harness.call_tool(client, "creo_capabilities", {})
        if not rec.check(
            "surface_loft_published", "surface_loft" in (capabilities.get("operations") or [])
        ):
            return {
                "mode": "live",
                "passed": False,
                "note": "surface_loft is refused before any job; no geometry was submitted",
                "checks": rec.checks,
                "jobs": rec.jobs,
            }
        await case_a_edge_bridge(client, rec, bridge_edges)
        await case_b_projected_curve(client, rec)
        await case_c_bulb_convergence(client, rec)
        await case_d_negative(client, rec)

    passed = all(item["ok"] for item in rec.checks)
    return {
        "mode": "live",
        "passed": passed,
        "surface_loft_inputs": "verified" if passed else "failed",
        "checks": rec.checks,
        "observations": rec.observations,
        "jobs": rec.jobs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument(
        "--bridge-edges",
        type=int,
        nargs=2,
        metavar=("STRIP_A_TOP", "STRIP_B_TOP"),
        help=(
            "case (a): use these strip top-edge ids instead of picking them from "
            "creo_measure_surface_group open_edge_records"
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.live and not args.confirm_session_usable:
        parser.error("--live requires --confirm-session-usable")

    report = case_offline()
    if args.live:
        report["live"] = asyncio.run(case_live(args.bridge_edges))
        report["passed"] = bool(report["passed"] and report["live"]["passed"])

    stamp = time.strftime("%Y%m%d-%H%M%S")
    output = args.output or ROOT / "build" / "surface_loft_inputs" / f"{stamp}.json"
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
