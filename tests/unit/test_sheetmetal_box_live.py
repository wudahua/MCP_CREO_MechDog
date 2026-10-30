"""DEV-051 T05 / FEAT-014 + BUG-047: four-wall contrast fixtures (2026-10-30).

The 2026-10-29 round six left the four-wall box at 2/4: f_px and f_nx built as
real 90-degree bends, then the third wall f_ny failed inside regeneration
(feature status 6, no geometry items), the health check failed the whole job and
the model rolled back. Corner interference is one candidate, not a cause: no
contrast experiment has run yet.

This module is the offline half of the T05 box driver. It freezes:

* the three mandated contrast groups on the confirmed 185x232x1 base wall with
  h80/R2.54/Y0.5 flanges -- full-length third wall, the same wall trimmed 20 mm
  short of both chain ends, and the submission-order gradient that gives f_ny
  0, 1 and 2 material corners across three fresh models;
* the ``end_trim_mm`` contract the trimmed group needs: an absolute model-unit
  length, both depth sides blind with that offset, omitted meaning the
  unchanged full-edge tree. Whether Creo measures the blind offset as a setback
  from each chain end or a wall length from the section is not decidable
  offline, so a free-wall probe classifies the semantics from the measured
  volume before the trimmed third wall is trusted;
* the per-stage record a live run must fill for a failing wall: accepted
  submission, terminal failure, the feature status/geometry items from the
  native log's UNHEALTHY_FEATURES dump, the health-check message and the
  restored revision/volume;
* the decision table that maps observations to conclusions. Corner interference
  is "supported" only when the trim contrast and the order gradient agree; every
  other outcome stays "undetermined" with the reason recorded.

Nothing here builds geometry. The volume oracles are the independent bent-wall
increment model already validated against the measured 2026-10-29 walls.
"""

from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations
from tests.unit import test_sheetmetal_flange as fx
from tests.unit import test_sheetmetal_relief as relief

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE = REPO_ROOT / "native" / "advanced.cpp"
SCHEMA = REPO_ROOT / "src" / "creo_mechdog" / "schema.py"
SERVER = REPO_ROOT / "server.py"

# The mandated trim for the third-wall contrast: 20 mm short of both chain ends.
TRIM_MM = 20.0

# DEV-051 live rule, same as the T11 driver: a job that is not terminal after
# 180 s is a hang; the driver records the scene and stops without resubmitting.
HANG_BUDGET_SECONDS = 180.0

# Label -> plate side, from the T05 fixture sequence.
LABEL_SIDES = {label: side for side, label in fx.FLANGE_SEQUENCE}

# Round-six facts the contrast starts from (2026-10-29 22:27 report).
ROUND_SIX = {
    "date": "2026-10-29",
    "report": "build/sheetmetal_relief/20261029T222754_44e6ab6a/report.json",
    "third_wall": "f_ny",
    "observed": (
        "feature created with status=6 and geometry_items=[]; health check failed the "
        "job ('Regeneration produced a failed, suppressed or incomplete feature'); the "
        "model rolled back to revision 3 and the pre-wall volume"
    ),
    "third_edge_span_mm": 177.92,
    "corner_interference_status": "candidate_only_no_contrast_run",
}


# --- contrast groups -------------------------------------------------------


def wall_material_corners(previous_sides: list[str], side: str) -> int:
    """Bend ends of this wall that run into an already-built wall's bend."""
    return fx.shared_corners(previous_sides, side)


def contrast_groups() -> dict:
    """The three mandated contrasts, each on a fresh model.

    ``order`` is the submission order; every wall is its own job and its edge is
    re-selected from a fresh inspection. ``material_corners`` is derived from the
    order, not asserted: f_ny sees 0 corners first, 1 after f_px and 2 after
    f_px+f_nx, which is the corner gradient the round-six failure sits at the
    top of. The trimmed group repeats the full-length order with the third wall
    trimmed ``TRIM_MM`` short of both chain ends.
    """
    groups = {
        "full_length": {
            "order": ["f_px", "f_nx", "f_ny"],
            "trim_third": False,
            "why": (
                "reproduce the round-six shape: two parallel walls, then the "
                "perpendicular full-edge wall with two material corners"
            ),
            "expected": "observation_only",
        },
        "trimmed_20": {
            "order": ["f_px", "f_nx", "f_ny"],
            "trim_third": True,
            "why": (
                "same walls, but the third wall stops 20 mm short of both chain ends; "
                "if the trim removes the failure, the corner contact is load-bearing"
            ),
            "expected": "observation_only",
            "gated_on": "trim_semantics == setback_from_ends",
        },
        "order_ny_first": {
            "order": ["f_ny", "f_px", "f_nx"],
            "trim_third": False,
            "why": (
                "f_ny as the first wall has zero material corners; success here would "
                "localise the failure to the corner context, not the -y edge"
            ),
            "expected": "observation_only",
        },
        "order_ny_second": {
            "order": ["f_px", "f_ny"],
            "trim_third": False,
            "why": (
                "f_ny as the second wall has exactly one material corner; it separates "
                "'any existing neighbour breaks f_ny' from 'both corners are needed'"
            ),
            "expected": "observation_only",
        },
    }
    for name, group in groups.items():
        previous: list[str] = []
        rows = []
        for label in group["order"]:
            side = LABEL_SIDES[label]
            trimmed = group["trim_third"] and label == group["order"][-1]
            rows.append(
                {
                    "label": label,
                    "side": side,
                    "material_corners": wall_material_corners(previous, side),
                    "end_trim_mm": TRIM_MM if trimmed else None,
                }
            )
            previous.append(side)
        group["walls"] = rows
        group["f_ny_material_corners"] = next(
            row["material_corners"] for row in rows if row["label"] == "f_ny"
        )
    return groups


def offline_plan_rows(group: str) -> list[dict]:
    """Per-wall oracle rows for one group over the full fixture spans.

    Live walls of later positions run on shortened chains, so the live driver
    recomputes every expectation from the measured span; these rows fix the
    offline expectations (full spans, no relief) and the trim arithmetic.
    """
    inspection = fx.box_inspection()
    rows = []
    for wall in contrast_groups()[group]["walls"]:
        span = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, wall["side"], face="top")[
            "geometry"
        ]["span_mm"]
        if wall["end_trim_mm"] is not None:
            # Setback interpretation only; the live probe must confirm it first.
            expected = relief.bent_wall_increment_mm3(span - 2 * TRIM_MM)
        else:
            expected = relief.bent_wall_increment_mm3(span)
        rows.append(
            {
                **wall,
                "fixture_span_mm": span,
                "effective_span_mm": span - 2 * TRIM_MM
                if wall["end_trim_mm"] is not None
                else span,
                "expected_added_mm3": expected,
            }
        )
    return rows


def group_plans_validate() -> dict:
    """Every group's base plan and every per-wall request pass admission."""
    from tests.unit import test_sheetmetal_relief as r

    results = {}
    for name in contrast_groups():
        rows = offline_plan_rows(name)
        first = rows[0]
        base = [fx.wall_sketch(), fx.wall_base_op()]
        first_flange = fx.flange_op(first["side"], first["label"], _reference(first["side"]))
        if first["end_trim_mm"] is not None:
            first_flange["end_trim_mm"] = first["end_trim_mm"]
        dumped = validate_operations(base + [first_flange])
        per_wall = []
        for row in rows[1:]:
            operation = fx.flange_op(row["side"], row["label"], _reference(row["side"]))
            if row["end_trim_mm"] is not None:
                operation["end_trim_mm"] = row["end_trim_mm"]
            per_wall.append(validate_operations([operation])[0])
        results[name] = {
            "base_plan_operations": len(dumped),
            "first_flange_relief": r.expected_native_sides(dumped[-1].get("relief")),
            "walls": [
                {
                    "label": row["label"],
                    "end_trim_mm": wall.get("end_trim_mm"),
                    "relief": r.expected_native_sides(wall.get("relief")),
                }
                for row, wall in zip(rows[1:], per_wall)
            ],
        }
    return results


def _reference(side: str) -> dict:
    return fx.select_wall_edge(fx.box_inspection(), fx.PLATE_BOUNDS, side, face="top")


# --- trim semantics probe ---------------------------------------------------


def trim_probe_plan() -> tuple:
    """One free first wall carrying the trim: the semantics probe.

    f_px on +x has both bend ends at free plate corners, so nothing else can
    confound the measured increment; the probe answers what the blind offset
    means before any trimmed third wall is submitted.
    """
    reference = _reference("+x")
    operations = [
        fx.wall_sketch(),
        fx.wall_base_op(),
        {**fx.flange_op("+x", "f_px", reference), "end_trim_mm": TRIM_MM},
    ]
    return validate_operations(operations), reference


def trim_interpretations(span_mm: float) -> dict:
    """Candidate measured increments for one trimmed wall over ``span_mm``.

    All four candidates use the bent-increment model validated against the
    2026-10-29 walls; they differ only in the effective chain length each
    interpretation implies.
    """
    return {
        "setback_from_ends": relief.bent_wall_increment_mm3(span_mm - 2 * TRIM_MM),
        "length_from_section": relief.bent_wall_increment_mm3(TRIM_MM),
        "length_both_sides": relief.bent_wall_increment_mm3(2 * TRIM_MM),
        "trim_ignored": relief.bent_wall_increment_mm3(span_mm),
    }


def classify_trim_semantics(
    measured_increment_mm3: float | None, span_mm: float, tolerance_mm3: float = 0.2
) -> dict:
    """Name the interpretation the measured increment matches, or unresolved."""
    candidates = trim_interpretations(span_mm)
    if measured_increment_mm3 is None:
        return {"semantics": "unresolved", "reason": "no measured increment"}
    matched = [
        name
        for name, expected in candidates.items()
        if abs(measured_increment_mm3 - expected) <= max(tolerance_mm3, abs(expected) * 1e-3)
    ]
    if len(matched) == 1:
        return {"semantics": matched[0], "candidates": candidates}
    if not matched:
        return {"semantics": "unresolved", "candidates": candidates}
    return {"semantics": "ambiguous", "matched": matched, "candidates": candidates}


# --- per-stage record for a failing wall ------------------------------------


def extract_unhealthy_feature(log_text: str | None, label: str) -> dict | None:
    """The named feature's status/geometry items from UNHEALTHY_FEATURES.

    The health check dumps the whole feature list into native.log before it
    fails the job, so the failing wall's status=6 and empty geometry come from
    that dump, not from inference. None means the log was unavailable or the
    line was absent; a missing feature name is recorded as such.
    """
    if not log_text:
        return None
    match = re.search(r"UNHEALTHY_FEATURES=(\[.*\])", log_text)
    if not match:
        return {"line_found": False}
    try:
        features = json.loads(match.group(1))
    except ValueError:
        return {"line_found": True, "parse_error": True}
    for feature in features:
        if feature.get("name") == label:
            return {
                "line_found": True,
                "status": feature.get("status"),
                "geometry_item_count": len(feature.get("geometry_items") or []),
                "incomplete": feature.get("incomplete"),
            }
    return {"line_found": True, "feature_not_in_dump": True}


def third_wall_stage_record(
    label: str,
    job_id: str | None,
    terminal: dict | None,
    log_text: str | None,
    revision_before: int | None,
    volume_before_mm3: float | None,
    snapshot_after: dict,
) -> dict:
    """The five mandated stages for one failing wall, each recorded not inferred.

    submission -> terminal failure -> feature status/geometry (native log dump)
    -> health-check message -> rollback (revision and volume restored).
    """
    failure = {}
    if terminal is not None:
        from tools.sheetmetal_live import failure_text

        failure = failure_text(terminal)
    message = failure.get("message") or (terminal or {}).get("message") or ""
    revision_after = snapshot_after.get("revision")
    inspection = snapshot_after.get("inspection") if isinstance(snapshot_after, dict) else {}
    volume_after = inspection.get("volume_mm3") if isinstance(inspection, dict) else None
    rollback_known = revision_before is not None and revision_after is not None
    volume_known = volume_before_mm3 is not None and volume_after is not None
    return {
        "stage_submission": {"submitted": job_id is not None, "job_id": job_id},
        "stage_terminal": {
            "status": (terminal or {}).get("status"),
            "toolkit_code": failure.get("toolkit_code"),
            "failed_stage": failure.get("failed_stage"),
            "failed_toolkit_call": failure.get("failed_toolkit_call"),
        },
        "stage_feature_state": extract_unhealthy_feature(log_text, label),
        "stage_health_check": {
            "message": message,
            "regeneration_failed_message": "failed, suppressed or incomplete" in message,
        },
        "stage_rollback": {
            "revision_before": revision_before,
            "revision_after": revision_after,
            "volume_before_mm3": volume_before_mm3,
            "volume_after_mm3": volume_after,
            "revision_restored": bool(rollback_known and revision_after == revision_before),
            "volume_restored": bool(volume_known and volume_after == volume_before_mm3),
            "rolled_back": bool(
                rollback_known
                and revision_after == revision_before
                and (
                    not volume_known
                    or math.isclose(volume_after, volume_before_mm3, rel_tol=0, abs_tol=0.01)
                )
            ),
        },
        "native_log_available": log_text is not None,
    }


def failed_wall_verdict(stage: dict, label: str) -> dict:
    """Judge one failing wall against the round-six shape.

    The round-six shape is: status=6, empty geometry, the regeneration health
    message and a restored revision/volume. Anything else is recorded as a
    different failure shape, which would itself be new evidence.
    """
    feature = stage["stage_feature_state"]
    health = stage["stage_health_check"]
    rollback = stage["stage_rollback"]
    checks = {
        "terminal_failed": stage["stage_terminal"]["status"] == "failed",
        "feature_status_6": bool(feature) and feature.get("status") == 6,
        "geometry_empty": bool(feature) and feature.get("geometry_item_count") == 0,
        "health_message": bool(health["regeneration_failed_message"]),
        "rolled_back": bool(rollback["rolled_back"]),
    }
    round_six_shape = all(checks.values())
    return {
        "label": label,
        "checks": checks,
        "matches_round_six_shape": round_six_shape,
        "note": (
            "a failing wall that does not match the round-six shape is a new "
            "observation, not a reproduction; record it as such"
        ),
    }


# --- corner decision table ---------------------------------------------------

# Observations the live run feeds in; every value is an outcome name, never a
# pre-written conclusion.
OBSERVATION_OUTCOMES = ("third_failed", "third_succeeded", "not_executed")


def corner_decision(
    observations: dict,
    trim_semantics: str | None = None,
) -> dict:
    """Map the contrast observations to a conclusion, without guessing.

    Corner interference becomes "supported" only when all three hold: the
    full-length third wall fails at two corners, a lower-corner position of the
    same wall succeeds, and the trimmed third wall succeeds while the full one
    fails with the setback semantics confirmed. Everything else stays
    undetermined with the blocking reason recorded.
    """
    full = observations.get("full_length")
    trimmed = observations.get("trimmed_20")
    first = observations.get("order_ny_first")
    second = observations.get("order_ny_second")
    incomplete = [
        name
        for name, value in (
            ("full_length", full),
            ("order_ny_first", first),
            ("order_ny_second", second),
        )
        if value not in ("third_failed", "third_succeeded")
    ]
    if incomplete:
        return {
            "conclusion": "undetermined_incomplete",
            "reasons": [f"{name} has no usable outcome" for name in incomplete],
            "corner_interference": "not_determined",
        }
    if full == "third_succeeded":
        return {
            "conclusion": "not_reproduced",
            "reasons": ["the full-length third wall built on this run"],
            "corner_interference": "not_determined",
        }
    if first == "third_failed":
        return {
            "conclusion": "third_wall_fails_without_corners",
            "reasons": [
                "f_ny failed as the first wall with zero material corners; the failure "
                "does not need corner contact and the corner hypothesis is refuted for "
                "this geometry"
            ],
            "corner_interference": "refuted",
        }
    if second == "third_failed":
        return {
            "conclusion": "single_corner_trigger",
            "reasons": [
                "f_ny built with zero corners but failed with one; corner contact with "
                "a single neighbour is already fatal"
            ],
            "corner_interference": "partially_supported_pending_trim",
        }
    # full failed at 2 corners, and f_ny succeeded at 0 and 1. Only now does the
    # trimmed outcome carry weight; a skipped or unexecuted trim keeps the cause
    # open on purpose.
    if trimmed == "third_succeeded":
        if trim_semantics == "setback_from_ends":
            return {
                "conclusion": "corner_interference_supported",
                "reasons": [
                    "the same wall fails at full length and builds when trimmed 20 mm "
                    "short of both chain ends (setback semantics confirmed by the "
                    "free-wall probe); corner contact is the load-bearing difference"
                ],
                "corner_interference": "supported_by_trim_and_order_contrast",
            }
        return {
            "conclusion": "trim_builds_but_semantics_unconfirmed",
            "reasons": [
                "the trimmed wall built, but the free-wall probe did not confirm the "
                "setback interpretation, so the trimmed wall may not be short of the "
                "corners at all"
            ],
            "corner_interference": "not_determined",
        }
    if trimmed == "third_failed":
        return {
            "conclusion": "trimmed_wall_also_fails",
            "reasons": [
                "the trimmed third wall failed too; removing the corner contact did not "
                "remove the failure, so corner interference is refuted for this trim "
                "and the remaining candidates are reference, parameter or health-check "
                "behaviour"
            ],
            "corner_interference": "refuted_by_trim_contrast",
        }
    return {
        "conclusion": "corner_count_dependent_pending_trim",
        "reasons": [
            "f_ny fails with two material corners and builds with fewer; this is "
            "consistent with corner interference but the mandated trim contrast has "
            "not run, so the cause stays undetermined"
        ],
        "corner_interference": "not_determined",
    }


# --- static source guards ----------------------------------------------------


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.find("\nstatic ", start + len(signature))
    return source[start : end if end > 0 else len(source)]


def native_source() -> dict:
    advanced = REPO_ROOT / "native" / "advanced.cpp"
    source = advanced.read_text(encoding="utf-8", errors="replace")
    flange = _function_body(source, "static void generic_sheetmetal_flange")
    checks = {
        # Default tree unchanged: the stock TO_END both-sides write survives.
        "default_to_end_both_sides": flange.count("PRO_WALL_LEN_TYPE_TO_END") == 2,
        # Trim branch: blind type plus offset on both sides, opt-in only.
        "trim_branch_blind_offset": "PRO_WALL_LEN_TYPE_BLIND" in flange
        and "PRO_E_SMT_FLANGE_DEPTH_OFFSET" in flange,
        "trim_branch_gated_on_request": 'op.contains("end_trim_mm")' in flange,
        "trim_must_be_positive": "end_trim_mm must be a number greater than 0" in flange,
        "trim_logged": "FLANGE_END_TRIM" in flange,
        "trim_echo_recorded": 'extra["depth_trim"]' in flange,
        # Scope discipline: the trim is the only new element write.
        "no_corner_relief": "PRO_E_SMT_CORNER_RELIEF" not in flange,
        "no_miter_cuts": "PRO_E_SMT_MTR_CUTS" not in flange,
        "no_edge_rip": "PRO_E_SMT_EDGE_RIP" not in flange,
        "no_to_ref_depth": "PRO_WALL_LEN_TYPE_TO_REF" not in flange,
        "no_blind_sym_depth": "PRO_WALL_LEN_TYPE_BLIND_SYM" not in flange,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "statement": (
            "end_trim_mm switches both flange depth sides from TO_END to blind with the "
            "requested offset and touches nothing else; the stock tree is unchanged for "
            "calls without the field"
        ),
        "live_uncertainty": (
            "ProSmtFlangeWall.h documents DEPTH_OFFSET only as a double; whether it is a "
            "setback from each chain end or a length from the section is classified by "
            "the free-wall probe from the measured volume"
        ),
    }


def contract_source() -> dict:
    schema = SCHEMA.read_text(encoding="utf-8", errors="replace")
    server = SERVER.read_text(encoding="utf-8", errors="replace")
    checks = {
        "schema_field_optional_positive": "end_trim_mm: Annotated[float, Field(gt=0" in schema,
        "schema_rejects_boolean": "end_trim_mm is a length in model units, not a boolean" in schema,
        "server_optional_parameter": "end_trim_mm: Annotated[" in server,
        "server_writes_only_when_present": 'operation["end_trim_mm"] = end_trim_mm' in server,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"contract source guard missing: {missing}"
    return {
        "static_contract_assertions": checks,
        "reason_schema_and_server_touched": (
            "the mandated trimmed contrast must pass validate_operations (shared by the "
            "independent tool and execute_plan), which requires the field on "
            "SheetmetalFlangeOp and the optional parameter on creo_sheetmetal_flange"
        ),
    }


LIVE_REFUSAL = (
    "T05 four-wall live acceptance is a separate integration step on the single shared "
    "dev service (MCP_CREO_MechDog_dev, E:/Projects/MCP_CREO_MechDog). This driver runs "
    "offline checks only: it never instantiates an MCP client, never connects to Creo and "
    "never retries a job. Use --live --confirm-session-usable only inside that assigned "
    "integration step."
)


# --- unit tests --------------------------------------------------------------


class ContrastGroupTest(unittest.TestCase):
    def test_orders_give_f_ny_the_zero_one_two_corner_gradient(self):
        groups = contrast_groups()
        self.assertEqual(groups["order_ny_first"]["f_ny_material_corners"], 0)
        self.assertEqual(groups["order_ny_second"]["f_ny_material_corners"], 1)
        self.assertEqual(groups["full_length"]["f_ny_material_corners"], 2)
        self.assertEqual(groups["trimmed_20"]["f_ny_material_corners"], 2)

    def test_only_the_third_wall_of_the_trimmed_group_carries_the_trim(self):
        for name, group in contrast_groups().items():
            for wall in group["walls"]:
                expected = TRIM_MM if (group["trim_third"] and wall["label"] == "f_ny") else None
                self.assertEqual(wall["end_trim_mm"], expected, (name, wall["label"]))

    def test_offline_rows_reuse_the_confirmed_increment_model(self):
        rows = offline_plan_rows("full_length")
        self.assertAlmostEqual(rows[0]["expected_added_mm3"], 18_025.291234, delta=1e-3)
        self.assertAlmostEqual(rows[2]["expected_added_mm3"], 14_373.615854, delta=1e-3)
        trimmed = offline_plan_rows("trimmed_20")[-1]
        self.assertAlmostEqual(trimmed["effective_span_mm"], 145.0, places=6)
        self.assertAlmostEqual(
            trimmed["expected_added_mm3"],
            relief.bent_wall_increment_mm3(145.0),
            delta=1e-6,
        )

    def test_every_group_plan_and_wall_validates(self):
        results = group_plans_validate()
        self.assertEqual(len(results), 4)
        for name, result in results.items():
            with self.subTest(group=name):
                self.assertEqual(result["base_plan_operations"], 3)
                for wall in result["walls"]:
                    self.assertEqual(wall["relief"], {"side1": "none", "side2": "none"})

    def test_trim_probe_plan_validates_with_the_trim(self):
        operations, reference = trim_probe_plan()
        dumped = validate_operations(operations)
        self.assertEqual(dumped[-1]["end_trim_mm"], TRIM_MM)
        self.assertEqual(dumped[-1]["label"], "f_px")
        self.assertEqual(reference["geometry"]["face"], "top")


class TrimSemanticsTest(unittest.TestCase):
    def test_candidates_are_well_separated_for_both_edge_lengths(self):
        for span in (185.0, 232.0):
            values = sorted(trim_interpretations(span).values())
            for low, high in zip(values, values[1:]):
                self.assertGreater(high - low, 1.0, span)

    def test_probe_classifies_each_interpretation(self):
        span = 232.0
        for name, expected in trim_interpretations(span).items():
            with self.subTest(interpretation=name):
                verdict = classify_trim_semantics(expected, span)
                self.assertEqual(verdict["semantics"], name, verdict)

    def test_unknown_measurement_stays_unresolved(self):
        self.assertEqual(classify_trim_semantics(None, 232.0)["semantics"], "unresolved")
        middle = sum(trim_interpretations(232.0).values()) / 4.0
        self.assertEqual(classify_trim_semantics(middle, 232.0)["semantics"], "unresolved")

    def test_trimmed_third_wall_requires_the_setback_reading(self):
        # The trimmed group is gated on setback_from_ends; any other reading leaves
        # the trimmed wall's clearance from the corners unproven.
        rows = offline_plan_rows("trimmed_20")
        third = rows[-1]
        setback = trim_interpretations(third["fixture_span_mm"])["setback_from_ends"]
        self.assertAlmostEqual(third["expected_added_mm3"], setback, delta=1e-6)


class TrimAdmissionTest(unittest.TestCase):
    def test_trim_is_preserved_and_optional(self):
        operation = fx.flange_op("+x", "f_px", _reference("+x"))
        self.assertNotIn("end_trim_mm", validate_operations([operation])[0])
        operation["end_trim_mm"] = 20.0
        self.assertEqual(validate_operations([operation])[0]["end_trim_mm"], 20.0)

    def test_invalid_trims_are_rejected_before_modelling(self):
        edge = _reference("+x")
        for bad in (0.0, -1.0, True, float("inf"), "1t"):
            with self.subTest(value=bad):
                operation = fx.flange_op("+x", "f_px", edge)
                operation["end_trim_mm"] = bad
                with self.assertRaises(Exception):
                    validate_operations([operation])


class StageRecordTest(unittest.TestCase):
    UNHEALTHY_LINE = (
        'UNHEALTHY_FEATURES=[{"id":9,"type":17,"type_name":"WALL","status":6,'
        '"incomplete":false,"name":"f_ny","dimensions":[],"geometry_items":[],'
        '"parent_ids":[],"child_ids":[]}]'
    )

    def _record(
        self, log_text, terminal_status="failed", revision=(3, 3), volume=(80_040.0, 80_040.0)
    ):
        after = {"revision": revision[1], "inspection": {"volume_mm3": volume[1]}}
        return third_wall_stage_record(
            "f_ny",
            "job-1",
            {
                "status": terminal_status,
                "message": "Regeneration produced a failed, suppressed or incomplete feature",
            },
            log_text,
            revision[0],
            volume[0],
            after,
        )

    def test_round_six_shape_is_recognised(self):
        stage = self._record(self.UNHEALTHY_LINE)
        self.assertTrue(stage["stage_submission"]["submitted"])
        self.assertEqual(stage["stage_terminal"]["status"], "failed")
        self.assertEqual(
            stage["stage_feature_state"],
            {"line_found": True, "status": 6, "geometry_item_count": 0, "incomplete": False},
        )
        self.assertTrue(stage["stage_health_check"]["regeneration_failed_message"])
        self.assertTrue(stage["stage_rollback"]["rolled_back"])
        verdict = failed_wall_verdict(stage, "f_ny")
        self.assertTrue(verdict["matches_round_six_shape"], verdict["checks"])

    def test_deviation_from_the_round_six_shape_is_recorded(self):
        log = self.UNHEALTHY_LINE.replace('"status":6', '"status":1024')
        verdict = failed_wall_verdict(self._record(log), "f_ny")
        self.assertFalse(verdict["matches_round_six_shape"])
        self.assertFalse(verdict["checks"]["feature_status_6"])

    def test_missing_log_leaves_the_feature_state_unknown(self):
        stage = self._record(None)
        self.assertIsNone(stage["stage_feature_state"])
        self.assertFalse(stage["native_log_available"])
        self.assertFalse(failed_wall_verdict(stage, "f_ny")["matches_round_six_shape"])

    def test_absent_line_and_unnamed_feature_are_distinct_outcomes(self):
        self.assertEqual(extract_unhealthy_feature("no dump here", "f_ny"), {"line_found": False})
        other = self.UNHEALTHY_LINE.replace("f_ny", "f_other")
        self.assertEqual(
            extract_unhealthy_feature(other, "f_ny"),
            {"line_found": True, "feature_not_in_dump": True},
        )

    def test_failed_rollback_is_visible(self):
        stage = self._record(self.UNHEALTHY_LINE, revision=(3, 4), volume=(80_040.0, 98_065.0))
        self.assertFalse(stage["stage_rollback"]["revision_restored"])
        self.assertFalse(stage["stage_rollback"]["rolled_back"])
        self.assertFalse(failed_wall_verdict(stage, "f_ny")["matches_round_six_shape"])


class CornerDecisionTest(unittest.TestCase):
    def test_corner_interference_never_stands_without_the_trim_contrast(self):
        decision = corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "skipped_unresolved_semantics",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            }
        )
        self.assertEqual(decision["conclusion"], "corner_count_dependent_pending_trim")
        self.assertEqual(decision["corner_interference"], "not_determined")

    def test_full_contrast_supports_the_corner_cause(self):
        decision = corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="setback_from_ends",
        )
        self.assertEqual(decision["conclusion"], "corner_interference_supported")
        self.assertEqual(decision["corner_interference"], "supported_by_trim_and_order_contrast")

    def test_trim_success_without_setback_semantics_stays_undetermined(self):
        decision = corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="unresolved",
        )
        self.assertEqual(decision["conclusion"], "trim_builds_but_semantics_unconfirmed")
        self.assertEqual(decision["corner_interference"], "not_determined")

    def test_trimmed_wall_failing_refutes_the_corner_cause(self):
        decision = corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_failed",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="setback_from_ends",
        )
        self.assertEqual(decision["conclusion"], "trimmed_wall_also_fails")
        self.assertEqual(decision["corner_interference"], "refuted_by_trim_contrast")

    def test_zero_corner_failure_refutes_the_corner_cause(self):
        decision = corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "not_executed",
                "order_ny_first": "third_failed",
                "order_ny_second": "third_succeeded",
            }
        )
        self.assertEqual(decision["conclusion"], "third_wall_fails_without_corners")
        self.assertEqual(decision["corner_interference"], "refuted")

    def test_unexpected_success_and_incomplete_runs_stay_undetermined(self):
        decision = corner_decision(
            {
                "full_length": "third_succeeded",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            }
        )
        self.assertEqual(decision["conclusion"], "not_reproduced")
        self.assertEqual(decision["corner_interference"], "not_determined")
        partial = corner_decision({"full_length": "third_failed"})
        self.assertEqual(partial["conclusion"], "undetermined_incomplete")


class NativeSourceGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = native_source()
        cls.contract = contract_source()

    def test_native_guards_hold(self):
        for name, present in self.native["static_source_assertions"].items():
            self.assertTrue(present, name)

    def test_contract_guards_hold(self):
        for name, present in self.contract["static_contract_assertions"].items():
            self.assertTrue(present, name)

    def test_live_uncertainty_is_recorded_not_resolved(self):
        self.assertIn("setback", self.native["live_uncertainty"])


class RoundSixEvidenceTest(unittest.TestCase):
    def test_round_six_is_recorded_as_a_candidate_not_a_cause(self):
        self.assertEqual(ROUND_SIX["third_wall"], "f_ny")
        self.assertEqual(ROUND_SIX["corner_interference_status"], "candidate_only_no_contrast_run")

    def test_live_refusal_points_at_the_single_dev_service(self):
        self.assertIn("MCP_CREO_MechDog_dev", LIVE_REFUSAL)
        self.assertIn("--confirm-session-usable", LIVE_REFUSAL)


if __name__ == "__main__":
    unittest.main()
