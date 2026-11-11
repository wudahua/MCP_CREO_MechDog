"""FEAT-065/M4 driver: surface_loft boundary tangency (``boundary_conditions``).

Default mode is offline: it checks the published contract without any Creo
session - schema admission of ``tangent`` at an edge first/last section, the
refusals decided before a job (curvature, normal, a non-free guide boundary,
tangent on a sketch or curve section), the empty field gate, the capability /
tool / reference text, the native source route (measured TAN_COND_TYPE 2 plus
PRO_E_BNBLN_STRETCH -1/+1, kernel-default connect chain) and the pure judges
the live cases use.

``--live --confirm-session-usable`` drives the public MCP tools against the
local Creo session. It must only be run after the user has confirmed the live
run for that session (AGENTS.md). The geometry is the FEAT-065 T2b scene: two
vertical surface strips (y = 0 and y = 20, 40 mm long, 10 mm high), bridged by
a two-section surface_loft whose sections are the strips' top edges, with no
guides. The edges come from ``creo_measure_surface_group``
``group.open_edge_records``, picked by their endpoints. To measure a seam the
strip is JOINed with the bridge (``quilt_merge``, target = strip, tool =
bridge) and ``creo_measure_surface_curvature`` reads the normal angle across
the shared edge of the two member faces ``[0, 1]``. A chained merge of the
second strip is not published, so every seam is measured on its own model.

(1) free baseline: both section boundaries ``free`` (a no-op) - the bridge is
    the 800 +- 0.5 mm2 plane at z = 10, and seam A is about 90 deg.
(2) tangent at both ends: saved and reloaded, area above 900 mm2 (T2b measured
    982.5888), bounding box z max above 14 mm, both boundary records written
    (TAN_COND_TYPE 2, stretch -1 / +1, kernel-default chain), and seams A and
    B each ``g1_max_angle_deg < 0.5`` with ``within_g1 = true``.
(3) the same as (2) with strip A's sketch line drawn backwards (edge direction
    and face normal flipped); the area must match (2).
(4) negative: ``curvature`` is refused before a job exists.

The merge receipt is read from the tool response first (compact
``creo_get_job``, then ``detail="full", section="operations_result"``); only
if neither carries ``result_quilt_id`` does the driver read
``jobs/<job_id>/job.json``. The source used is recorded per seam
(``merge_receipt_source``) and summarised in the report.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft_continuity.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft_continuity.py --live --confirm-session-usable
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
TOOLS = Path(__file__).resolve().parent
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import test_surface_loft_inputs as inputs  # noqa: E402
import test_surface_loft_multisection as harness  # noqa: E402

JOBS_ROOT = ROOT / "jobs"

FREE_AREA_MM2 = inputs.BRIDGE_AREA_MM2
AREA_TOLERANCE_MM2 = inputs.AREA_TOLERANCE_MM2
BBOX_TOLERANCE_MM = inputs.BBOX_TOLERANCE_MM
#: The free bridge meets each strip at a right angle.
FREE_SEAM_ANGLE_DEG = 90.0
FREE_SEAM_TOLERANCE_DEG = 1.0
#: Acceptance bounds for the tangent arch (T2b measured 982.5888 mm2, z 15.12).
TANGENT_MIN_AREA_MM2 = 900.0
TANGENT_MIN_ZMAX_MM = 14.0
T2B_TANGENT_AREA_MM2 = 982.5888
#: creo_measure_surface_curvature's own within_g1 marker threshold.
G1_LIMIT_DEG = 0.5
CURVATURE_SAMPLES = 8

STRIPS = [
    {"kind": "quilt_feature", "label": "strip_a"},
    {"kind": "quilt_feature", "label": "strip_b"},
]
TANGENT_BOTH = [
    {"boundary": "first_section", "condition": "tangent"},
    {"boundary": "last_section", "condition": "tangent"},
]
FREE_BOTH = [
    {"boundary": "first_section", "condition": "free"},
    {"boundary": "last_section", "condition": "free"},
]
CURVATURE_FIRST = [{"boundary": "first_section", "condition": "curvature"}]
#: What native/surface_loft.cpp writes for a tangent boundary (T2b mapping).
EXPECTED_WRITTEN = {
    "first_section": {"tnc_index": 0, "tan_cond_type": 2, "stretch": -1.0},
    "last_section": {"tnc_index": 1, "tan_cond_type": 2, "stretch": 1.0},
}
SEAM_STRIPS = {"a": "strip_a", "b": "strip_b"}


# ----------------------------------------------------------------------------
# Plans
# ----------------------------------------------------------------------------


def strips_plan(reverse_a: bool = False) -> list[dict]:
    """Two vertical surface strips; ``reverse_a`` draws strip A's line backwards."""
    plan = [op for op in inputs.bridge_build_plan() if op["label"] not in ("guide_l", "guide_r")]
    if reverse_a:
        plan[0] = inputs.line_sketch("strip_a_line", 0.0, [inputs.STRIP_LENGTH_MM, 0.0], [0.0, 0.0])
    return plan


def bridge_loft(edge_a: int, edge_b: int, conditions: list[dict] | None = None) -> dict:
    operation: dict[str, Any] = {
        "op": "surface_loft",
        "label": "bridge",
        "sections": [inputs.edge_ref(edge_a), inputs.edge_ref(edge_b)],
    }
    if conditions is not None:
        operation["boundary_conditions"] = [dict(item) for item in conditions]
    return operation


def seam_merge(strip: str) -> dict:
    return {
        "op": "quilt_merge",
        "label": "join_seam",
        "target": {"kind": "quilt_feature", "label": strip},
        "tool": {"kind": "quilt_feature", "label": "bridge"},
    }


# ----------------------------------------------------------------------------
# Pure readers and judges (shared by the offline self-check and the live run)
# ----------------------------------------------------------------------------


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _near(value: Any, expected: float, tolerance: float) -> bool:
    number = _number(value)
    return number is not None and abs(number - expected) <= tolerance


def _int(value: Any) -> bool:
    return type(value) is int


def bbox_z(bbox: Any, corner: int) -> float | None:
    """z of the lower (0) or upper (1) corner of an inspect_model bbox_mm."""
    if not isinstance(bbox, list) or len(bbox) != 2:
        return None
    point = bbox[corner]
    if not isinstance(point, list) or len(point) != 3:
        return None
    return _number(point[2])


def job_json_operation(jobs_root: Path, job_id: str, op: str) -> dict:
    """The raw operation record from ``jobs/<job_id>/job.json`` (fallback only)."""
    try:
        manifest = json.loads((jobs_root / job_id / "job.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for item in (manifest.get("result") or {}).get("operations") or []:
        if isinstance(item, dict) and item.get("op") == op:
            return item
    return {}


async def merge_receipt(
    client, state: dict, jobs_root: Path = JOBS_ROOT
) -> tuple[dict, str | None]:
    """The quilt_merge record that carries ``result_quilt_id``, and where it came from.

    Tool responses first: the compact poll, then the paged full view of the
    operation results. ``jobs/<job_id>/job.json`` is the last resort. ``None``
    as the source means no record named the result quilt.
    """
    compact = harness.operation_of(state, "quilt_merge")
    if _int(compact.get("result_quilt_id")):
        return compact, "creo_get_job compact"
    job_id = state.get("job_id")
    if not job_id:
        return compact, None
    page = await harness.call_tool(
        client,
        "creo_get_job",
        {"job_id": job_id, "detail": "full", "section": "operations_result", "limit": 50},
    )
    for record in (page.get("data") or {}).get("operations_result") or []:
        if (
            isinstance(record, dict)
            and record.get("op") == "quilt_merge"
            and _int(record.get("result_quilt_id"))
        ):
            return record, "creo_get_job full operations_result"
    record = job_json_operation(jobs_root, job_id, "quilt_merge")
    if _int(record.get("result_quilt_id")):
        return record, "jobs/<job_id>/job.json"
    return compact, None


def seam_reading(payload: Any) -> dict:
    """The G1 block of one creo_measure_surface_curvature response."""
    payload = payload if isinstance(payload, dict) else {}
    reading = {
        key: payload.get(key)
        for key in (
            "job_id",
            "revision",
            "quilt_id",
            "g1_max_angle_deg",
            "within_g1",
            "g1_threshold_deg",
            "g1_status",
        )
    }
    if reading["g1_max_angle_deg"] is None and reading["within_g1"] is None:
        reading["raw"] = json.dumps(payload, ensure_ascii=False)[:600]
    return reading


def judge_seam(reading: dict, *, tangent: bool) -> tuple[bool, dict]:
    angle = _number(reading.get("g1_max_angle_deg"))
    within = reading.get("within_g1")
    if tangent:
        ok = angle is not None and angle < G1_LIMIT_DEG and within is True
        expected = f"g1_max_angle_deg < {G1_LIMIT_DEG} and within_g1 = true"
    else:
        ok = (
            angle is not None
            and abs(angle - FREE_SEAM_ANGLE_DEG) <= FREE_SEAM_TOLERANCE_DEG
            and within is False
        )
        expected = f"g1_max_angle_deg {FREE_SEAM_ANGLE_DEG} +- {FREE_SEAM_TOLERANCE_DEG}"
    return ok, {"g1_max_angle_deg": angle, "within_g1": within, "expected": expected}


def conditions_written(records: Any, edges: list[int] | None) -> tuple[bool, Any]:
    """Both tangent records say what the native executor wrote, and where."""
    if not isinstance(records, list) or len(records) != 2:
        return False, records
    for index, (record, boundary) in enumerate(zip(records, EXPECTED_WRITTEN)):
        expected = EXPECTED_WRITTEN[boundary]
        if not isinstance(record, dict):
            return False, records
        if (
            record.get("boundary") != boundary
            or record.get("condition") != "tangent"
            or record.get("status") != "written"
            or record.get("connect_chain") != "kernel_default"
            or record.get("tnc_index") != expected["tnc_index"]
            or record.get("tan_cond_type") != expected["tan_cond_type"]
            or not _near(record.get("stretch"), expected["stretch"], 1e-9)
            or not _int(record.get("surface_id"))
            or (edges is not None and record.get("edge_id") != edges[index])
        ):
            return False, records
    return True, records


def conditions_untouched(records: Any) -> tuple[bool, Any]:
    """Explicit ``free`` boundaries are echoed and leave the kernel default."""
    if not isinstance(records, list) or len(records) != 2:
        return False, records
    ok = all(
        isinstance(record, dict)
        and record.get("condition") == "free"
        and record.get("status") == "kernel_default"
        and "tan_cond_type" not in record
        and "stretch" not in record
        for record in records
    )
    return ok, records


def judge_bridge(loft: dict, bbox: Any, edges: list[int] | None, *, tangent: bool) -> list:
    """(name, ok, detail) for one bridge loft receipt plus its quilt bounding box."""
    area = loft.get("surface_area_mm2")
    z_min, z_max = bbox_z(bbox, 0), bbox_z(bbox, 1)
    sources_ok = loft.get("section_source_kinds") == ["edge", "edge"]
    checks: list[tuple[str, bool, Any]] = [
        (
            "sections_are_the_two_top_edges",
            sources_ok
            and (edges is None or loft.get("section_geometry_ids") == [[edges[0]], [edges[1]]]),
            {
                "section_source_kinds": loft.get("section_source_kinds"),
                "section_geometry_ids": loft.get("section_geometry_ids"),
                "picked_edges": edges,
            },
        ),
        (
            "one_open_quilt_no_solid",
            loft.get("quilt_count") == 1
            and loft.get("quilt_closed_native") == "open"
            and loft.get("has_solid") is False,
            {
                "quilt_count": loft.get("quilt_count"),
                "closure": loft.get("quilt_closed_native"),
                "has_solid": loft.get("has_solid"),
            },
        ),
    ]
    if tangent:
        ok, detail = conditions_written(loft.get("boundary_conditions"), edges)
        checks += [
            ("boundary_conditions_written", ok, detail),
            (
                "area_above_900",
                (_number(area) or 0.0) > TANGENT_MIN_AREA_MM2,
                {"surface_area_mm2": area, "t2b_measured_mm2": T2B_TANGENT_AREA_MM2},
            ),
            (
                "arch_rises_above_z14",
                z_max is not None and z_max > TANGENT_MIN_ZMAX_MM,
                {"bbox_mm": bbox, "z_max_mm": z_max},
            ),
        ]
    else:
        ok, detail = conditions_untouched(loft.get("boundary_conditions"))
        checks += [
            ("free_conditions_write_nothing", ok, detail),
            (
                "area_is_the_800_plane",
                _near(area, FREE_AREA_MM2, AREA_TOLERANCE_MM2),
                {"surface_area_mm2": area, "expected": FREE_AREA_MM2},
            ),
            (
                "bridge_stays_on_the_strip_tops",
                _near(z_max, inputs.STRIP_HEIGHT_MM, BBOX_TOLERANCE_MM)
                and _near(z_min, inputs.STRIP_HEIGHT_MM, BBOX_TOLERANCE_MM),
                {"bbox_mm": bbox},
            ),
        ]
    return checks


# ----------------------------------------------------------------------------
# Offline contract
# ----------------------------------------------------------------------------


def _flat(text: str) -> str:
    return " ".join(text.split())


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


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
            capabilities.require_available(validated)
        except ValueError as error:
            check(f"accepts_{name}", False, {"error": str(error)[:300]})
            return None
        check(f"accepts_{name}", True)
        return validated

    def refuses(name: str, plan: list[dict], phrase: str) -> None:
        try:
            capabilities.require_available(validate_operations(plan))
        except ValueError as error:
            check(f"refuses_{name}", phrase in str(error), {"error": str(error)[:300]})
            return
        check(f"refuses_{name}", False, {"reason": "accepted"})

    # Admission: the published shape and the measured refusals.
    validated = accepts(
        "tangent_at_both_edge_sections", [*strips_plan(), bridge_loft(11, 12, TANGENT_BOTH)]
    )
    if validated:
        check(
            "tangent_conditions_kept_verbatim",
            validated[-1].get("boundary_conditions") == TANGENT_BOTH,
            validated[-1].get("boundary_conditions"),
        )
    accepts(
        "tangent_with_reversed_strip_a", [*strips_plan(True), bridge_loft(11, 12, TANGENT_BOTH)]
    )
    accepts("explicit_free_at_both_sections", [*strips_plan(), bridge_loft(11, 12, FREE_BOTH)])
    accepts(
        "free_on_sketch_sections_and_guides",
        [
            *inputs.bridge_build_plan(),
            {
                "op": "surface_loft",
                "label": "sketch_bridge",
                "sections": ["strip_a_line", "strip_b_line"],
                "guides": ["guide_l", "guide_r"],
                "boundary_conditions": [
                    {"boundary": name, "condition": "free"}
                    for name in ("first_section", "last_section", "first_guide", "last_guide")
                ],
            },
        ],
    )
    refuses(
        "curvature",
        [*strips_plan(), bridge_loft(11, 12, CURVATURE_FIRST)],
        "condition 'curvature' is not available",
    )
    refuses(
        "normal",
        [
            *strips_plan(),
            bridge_loft(11, 12, [{"boundary": "last_section", "condition": "normal"}]),
        ],
        "condition 'normal' is not available",
    )
    guided = bridge_loft(11, 12, [{"boundary": "first_guide", "condition": "tangent"}])
    guided["guides"] = ["guide_l", "guide_r"]
    refuses(
        "tangent_on_a_guide",
        [*inputs.bridge_build_plan(), guided],
        "guide boundaries were not measured",
    )
    sketch = bridge_loft(11, 12, TANGENT_BOTH)
    sketch["sections"] = ["strip_a_line", "strip_b_line"]
    refuses(
        "tangent_on_sketch_sections", [*strips_plan(), sketch], "needs sections[0] to be an edge"
    )
    curve = bridge_loft(11, 12, TANGENT_BOTH[1:])
    curve["sections"] = [inputs.edge_ref(11), {"kind": "curve", "id": 12}]
    refuses(
        "tangent_on_a_curve_section", [*strips_plan(), curve], "needs sections[1] to be an edge"
    )

    # The field gate is empty; its mechanism is kept.
    family = capabilities.families()["surface_loft"]
    check(
        "field_gate_is_empty",
        capabilities.UNAVAILABLE_FIELDS == {} and family.get("unavailable_fields") == {},
        {"UNAVAILABLE_FIELDS": capabilities.UNAVAILABLE_FIELDS},
    )

    # Public text.
    limits = _flat(family["limits"])
    for name, phrase in (
        ("tangent_scope", "'tangent' is published at first_section/last_section only"),
        ("single_adjacent_face", "single adjacent face"),
        ("fixed_direction", "continuing the neighbouring face"),
        ("measured_area", "982.5888 mm2"),
        ("measured_seam", "G1 0.0 deg at both seams"),
        ("curvature_reason", "kept a 90 deg seam"),
        ("guide_reason", "guide boundaries were not measured"),
    ):
        check(f"capability_limits_name_{name}", phrase in limits)
    check(
        "capability_text_has_no_gate_or_pending_marker",
        "UNAVAILABLE_FIELDS" not in limits
        and "live acceptance pending" not in limits
        and "not live-verified" not in limits,
    )
    check("capability_prefix_unchanged", family["limits"].startswith("2-32 sections and"))
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    tool = server[server.index("async def creo_surface_loft(") :]
    tool = _flat(tool[: tool.index('"""', tool.index('"""') + 3)])
    check(
        "tool_description_publishes_tangent",
        "Only condition='tangent' is published" in tool
        and "boundary_conditions=[{boundary:'first_section', condition:'tangent'}" in tool
        and "NOT AVAILABLE" not in tool,
    )
    entry = reference_capabilities()["by_tool"].get("creo_surface_loft") or {}
    example = entry.get("boundary_conditions")
    check("references_publish_the_tangent_example", example == TANGENT_BOTH, example)
    if example == TANGENT_BOTH:
        accepts(
            "reference_tangent_example",
            [
                {
                    "op": "surface_loft",
                    "label": "ref_bridge",
                    "sections": entry.get("tangent_sections"),
                    "boundary_conditions": example,
                }
            ],
        )

    # Native route: measured tables, refusal before the tree, kernel chain kept.
    native = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")
    code = _code(native)
    flat = _flat(code)
    loft_body = code[code.index("static void generic_surface_loft(const J &op)") :]
    check(
        "native_tables_are_the_measured_values",
        'SURFACE_LOFT_TAN_COND_TYPE_VALUES = {{"tangent", 2}};' in flat
        and 'SURFACE_LOFT_TNC_BOUNDARY_INDEX = {{"first_section", 0}, {"last_section", 1}};' in flat
        and 'SURFACE_LOFT_TANGENT_STRETCH = {{"first_section", -1.0}, {"last_section", 1.0}};'
        in flat,
    )
    check(
        "native_refuses_unmeasured_conditions_before_the_tree",
        'refuse("not_available"' in code
        and loft_body.index("surface_loft_conditions(op, section_inputs, guide_inputs, details)")
        < loft_body.index("node(nullptr, PRO_E_FEATURE_TREE)"),
    )
    check(
        "native_writes_stretch_and_keeps_the_kernel_chain",
        "CK(ProElementDoubleSet(stretch_element, stretch));" in code
        and 'record["connect_chain"] = "kernel_default";' in code
        and "PRO_E_BNBLN_CONNECT_SURF_CHAIN" not in code
        and "surf_chain_method" not in code,
    )

    # Self-checks of the live judges and readers (no Creo).
    good_arch = {
        "surface_area_mm2": 982.5887974169791,
        "section_source_kinds": ["edge", "edge"],
        "section_geometry_ids": [[53], [85]],
        "quilt_count": 1,
        "quilt_closed_native": "open",
        "has_solid": False,
        "boundary_conditions": [
            {
                "index": 0,
                "boundary": "first_section",
                "condition": "tangent",
                "edge_id": 53,
                "surface_id": 55,
                "status": "written",
                "tnc_index": 0,
                "tan_cond_type": 2,
                "stretch": -1.0,
                "connect_chain": "kernel_default",
            },
            {
                "index": 1,
                "boundary": "last_section",
                "condition": "tangent",
                "edge_id": 85,
                "surface_id": 87,
                "status": "written",
                "tnc_index": 1,
                "tan_cond_type": 2,
                "stretch": 1.0,
                "connect_chain": "kernel_default",
            },
        ],
    }
    arch_box = [[-0.12, -0.12, 9.88], [40.12, 20.12, 15.120004800192012]]
    judged = judge_bridge(good_arch, arch_box, [53, 85], tangent=True)
    check("judge_accepts_the_t2b_arch", all(ok for _, ok, _ in judged), judged)
    flat_plane = {**good_arch, "surface_area_mm2": 800.0}
    judged = judge_bridge(
        flat_plane, [[0.0, 0.0, 10.0], [40.0, 20.0, 10.0]], [53, 85], tangent=True
    )
    check(
        "judge_refuses_a_tangent_request_that_stayed_flat",
        {name for name, ok, _ in judged if not ok} == {"area_above_900", "arch_rises_above_z14"},
        [name for name, ok, _ in judged if not ok],
    )
    wrong_sign = json.loads(json.dumps(good_arch))
    wrong_sign["boundary_conditions"][0]["stretch"] = 1.0
    check(
        "judge_refuses_a_wrong_stretch_sign",
        not conditions_written(wrong_sign["boundary_conditions"], [53, 85])[0],
    )
    free_plane = {
        **good_arch,
        "surface_area_mm2": 799.9999999999999,
        "boundary_conditions": [
            {
                "index": 0,
                "boundary": "first_section",
                "condition": "free",
                "status": "kernel_default",
            },
            {
                "index": 1,
                "boundary": "last_section",
                "condition": "free",
                "status": "kernel_default",
            },
        ],
    }
    judged = judge_bridge(
        free_plane, [[-0.12, -0.12, 9.88], [40.12, 20.12, 10.12]], [53, 85], tangent=False
    )
    check("judge_accepts_the_free_plane", all(ok for _, ok, _ in judged), judged)
    check(
        "judge_seam_g1", judge_seam({"g1_max_angle_deg": 0.0, "within_g1": True}, tangent=True)[0]
    )
    check(
        "judge_seam_refuses_the_folded_bridge",
        not judge_seam({"g1_max_angle_deg": 180.0, "within_g1": False}, tangent=True)[0],
    )
    check(
        "judge_seam_free",
        judge_seam({"g1_max_angle_deg": 90.0, "within_g1": False}, tangent=False)[0],
    )
    reading = seam_reading(
        {"g1_max_angle_deg": 0.0, "within_g1": True, "g1_status": {"available": True}}
    )
    check(
        "seam_reader_reads_top_level_g1",
        reading["g1_max_angle_deg"] == 0.0 and "raw" not in reading,
    )
    check("seam_reader_keeps_an_unreadable_payload", "raw" in seam_reading({"raw": "Error"}))

    return {"mode": "offline", "passed": all(item["ok"] for item in checks), "checks": checks}


# ----------------------------------------------------------------------------
# Live cases (only after the user's per-session confirmation)
# ----------------------------------------------------------------------------


async def bridge_scene(
    client,
    rec: inputs.Recorder,
    case: str,
    conditions: list[dict] | None,
    *,
    reverse_a: bool = False,
) -> dict | None:
    """Strips -> open-edge pick -> bridge loft. Returns the scene or None."""
    build = await harness.submit(client, strips_plan(reverse_a))
    rec.remember(f"{case}_build", build)
    if not rec.check(
        f"{case}_strips_built",
        build.get("status") == "succeeded",
        {"status": build.get("status"), "message": str(build.get("message"))[:300]},
    ):
        return None
    model_id, revision = build["model_id"], build.get("revision")
    measured, is_error = await inputs.measure_group(client, model_id, STRIPS)
    picked, detail = inputs.pick_bridge_edges(measured.get("group") or {})
    if not rec.check(
        f"{case}_top_edges_found_by_endpoints",
        not is_error and picked is not None,
        {"is_error": is_error, "job_id": measured.get("job_id"), **detail},
    ):
        return None
    lofted = await harness.submit(
        client, [bridge_loft(picked[0], picked[1], conditions)], model_id, revision
    )
    rec.remember(f"{case}_loft", lofted)
    loft = harness.operation_of(lofted, "surface_loft")
    if not rec.check(
        f"{case}_loft_succeeded",
        lofted.get("status") == "succeeded",
        {
            "status": lofted.get("status"),
            "message": str(lofted.get("message"))[:400],
            "failed_boundary_condition": loft.get("failed_boundary_condition"),
            "failed_loft_input": loft.get("failed_loft_input"),
        },
    ):
        rec.observations[f"{case}_failure"] = loft or lofted.get("message")
        return None
    rec.check(f"{case}_saved_file_reloaded_and_verified", harness.saved_verified(lofted))
    box = (await inputs.quilt_record(client, lofted["model_id"], loft.get("quilt_id"))).get(
        "bbox_mm"
    )
    area = _number(loft.get("surface_area_mm2"))
    rec.observations[f"{case}_bridge"] = {
        "model_id": lofted.get("model_id"),
        "section_edges": picked,
        "surface_area_mm2": loft.get("surface_area_mm2"),
        "area_delta_from_t2b_mm2": None if area is None else area - T2B_TANGENT_AREA_MM2,
        "bbox_mm": box,
        "boundary_conditions": loft.get("boundary_conditions"),
        "tan_cond_tree": loft.get("tan_cond_tree"),
    }
    for name, ok, detail in judge_bridge(loft, box, picked, tangent=conditions == TANGENT_BOTH):
        rec.check(f"{case}_{name}", ok, detail)
    return {
        "model_id": lofted["model_id"],
        "revision": lofted.get("revision"),
        "edges": picked,
        "area": area,
    }


async def seam(
    client,
    rec: inputs.Recorder,
    case: str,
    scene: dict,
    side: str,
    *,
    tangent: bool,
    jobs_root: Path = JOBS_ROOT,
) -> None:
    """JOIN one strip with the bridge and judge the normal angle across the seam."""
    strip = SEAM_STRIPS[side]
    merged = await harness.submit(client, [seam_merge(strip)], scene["model_id"], scene["revision"])
    rec.remember(f"{case}_merge_{strip}", merged)
    receipt, source = await merge_receipt(client, merged, jobs_root)
    quilt_id = receipt.get("result_quilt_id")
    observed: dict[str, Any] = {
        "strip": strip,
        "merge_job_id": merged.get("job_id"),
        "merge_receipt_source": source,
        "result_quilt_id": quilt_id,
        "merged_surface_ids": receipt.get("merged_surface_ids"),
    }
    rec.observations[f"{case}_seam_{side}"] = observed
    if not rec.check(
        f"{case}_seam_{side}_merged",
        merged.get("status") == "succeeded" and _int(quilt_id),
        {
            "status": merged.get("status"),
            "message": str(merged.get("message"))[:300],
            "merge_receipt_source": source,
            "result_quilt_id": quilt_id,
        },
    ):
        return
    measured = await harness.call_tool(
        client,
        "creo_measure_surface_curvature",
        {
            "model_id": scene["model_id"],
            "target": {"kind": "quilt", "id": quilt_id},
            "faces": [0, 1],
            "samples_per_direction": CURVATURE_SAMPLES,
        },
    )
    reading = seam_reading(measured)
    observed["curvature"] = reading
    ok, detail = judge_seam(reading, tangent=tangent)
    name = "g1_within_0_5_deg" if tangent else "about_90_deg"
    rec.check(f"{case}_seam_{side}_{name}", ok, detail)


async def case_negative(client, rec: inputs.Recorder) -> None:
    refused = await harness.call_tool(
        client,
        "creo_execute_plan",
        {"operations": [*strips_plan(), bridge_loft(11, 12, CURVATURE_FIRST)]},
    )
    rec.check(
        "negative_curvature_refused_before_a_job",
        not refused.get("job_id")
        and "condition 'curvature' is not available" in json.dumps(refused, ensure_ascii=False),
        {"response": str(refused)[:400]},
    )


async def run_live_cases(client, rec: inputs.Recorder, jobs_root: Path = JOBS_ROOT) -> None:
    """(1)-(4) against a ready client; split out so a fake client can drive it."""
    # (1) free baseline: explicit free at both ends is a no-op.
    scene = await bridge_scene(client, rec, "free", FREE_BOTH)
    if scene:
        await seam(client, rec, "free", scene, "a", tangent=False, jobs_root=jobs_root)
    # (2) tangent at both ends; (3) the same with strip A drawn backwards. A
    # chained merge is not published, so each seam gets its own model.
    areas: dict[str, list[float]] = {}
    for case, reverse_a in (("tangent", False), ("tangent_reversed", True)):
        for side in ("a", "b"):
            name = f"{case}_seam_{side}_scene"
            scene = await bridge_scene(client, rec, name, TANGENT_BOTH, reverse_a=reverse_a)
            if not scene:
                continue
            if scene["area"] is not None:
                areas.setdefault(case, []).append(scene["area"])
            await seam(client, rec, case, scene, side, tangent=True, jobs_root=jobs_root)
    forward, reverse = areas.get("tangent") or [], areas.get("tangent_reversed") or []
    rec.check(
        "tangent_reversed_matches_tangent_area",
        bool(forward)
        and bool(reverse)
        and max(forward + reverse) - min(forward + reverse) <= AREA_TOLERANCE_MM2,
        {"tangent": forward, "tangent_reversed": reverse},
    )
    # (4) negative.
    await case_negative(client, rec)
    sources = sorted(
        {
            str(value.get("merge_receipt_source"))
            for key, value in rec.observations.items()
            if key.endswith(("_seam_a", "_seam_b")) and isinstance(value, dict)
        }
    )
    rec.observations["merge_receipt_sources"] = sources


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    rec = inputs.Recorder()
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
        await run_live_cases(client, rec)

    passed = all(item["ok"] for item in rec.checks)
    return {
        "mode": "live",
        "passed": passed,
        "surface_loft_continuity": "verified" if passed else "failed",
        "merge_receipt_sources": rec.observations.get("merge_receipt_sources"),
        "checks": rec.checks,
        "observations": rec.observations,
        "jobs": rec.jobs,
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
    output = args.output or ROOT / "build" / "surface_loft_continuity" / f"{stamp}.json"
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
