"""FEAT-034/T02 offline contract tests for the explicit arc direction field.

The expected volumes below come from an oracle written in this file: the swept
segment volume is computed from the direction declared in the test input only.
No production normalization or analysis helper is called to produce an expected
value, so a production regression cannot silently redefine the expectation.
"""

from __future__ import annotations

import math
import unittest

from pydantic import ValidationError

from creo_mechdog import operation_results
from creo_mechdog.profile_checks import closed_profile
from creo_mechdog.profile_diagnostics import analyze_profile, validate_solid_profile
from creo_mechdog.schema import Arc, SketchGeometryOp, SketchOp

RADIUS_MM = 10.0
DEPTH_MM = 5.0
VOLUME_90_MM3 = 125.0 * math.pi - 250.0
VOLUME_270_MM3 = 375.0 * math.pi + 250.0


# --- independent oracle ----------------------------------------------------


def oracle_sweep_deg(start_deg: float, end_deg: float, direction: int) -> float:
    """Swept degrees of the declared direction; independent of production code."""
    if direction > 0:
        return (end_deg - start_deg) % 360.0
    return (start_deg - end_deg) % 360.0


def oracle_segment_volume_mm3(
    start_deg: float,
    end_deg: float,
    direction: int,
    radius: float = RADIUS_MM,
    depth: float = DEPTH_MM,
) -> float:
    """Circular segment (arc + chord) prism volume from the declared direction."""
    theta = math.radians(oracle_sweep_deg(start_deg, end_deg, direction))
    return depth * 0.5 * radius * radius * (theta - math.sin(theta))


def on_circle(angle_deg: float) -> list[float]:
    angle = math.radians(angle_deg)
    return [RADIUS_MM * math.cos(angle), RADIUS_MM * math.sin(angle)]


def arc_entity(
    *,
    start_deg: float = 0.0,
    end_deg: float = 90.0,
    direction: int | None = None,
    name: str = "arc_a",
) -> dict:
    entity = {
        "type": "arc",
        "name": name,
        "center": [0.0, 0.0],
        "radius": RADIUS_MM,
        "start_angle": start_deg,
        "end_angle": end_deg,
    }
    if direction is not None:
        entity["dir"] = direction
    return entity


def arc_with_chord(
    start_deg: float = 0.0, end_deg: float = 90.0, direction: int | None = None
) -> list[dict]:
    chord = {
        "type": "line",
        "name": "chord",
        "start": on_circle(end_deg),
        "end": on_circle(start_deg),
    }
    return [arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction), chord]


def segment_volume_from_analysis(entities: list[dict]) -> float:
    """Oracle consumer: only reads the analyzer's area, never its normalization."""
    report = analyze_profile(entities)
    return abs(report["material_area_mm2"]) * DEPTH_MM


class ArcDirectionContractTests(unittest.TestCase):
    """The single dir field: strict integers, finite angles, sane sweeps."""

    def test_default_direction_is_counterclockwise(self):
        arc = Arc.model_validate(arc_entity())
        self.assertEqual(arc.dir, 1)
        self.assertEqual(arc.model_dump()["dir"], 1)

    def test_explicit_directions_accepted(self):
        for direction in (1, -1):
            arc = Arc.model_validate(arc_entity(direction=direction))
            self.assertEqual(arc.dir, direction)

    def test_non_integer_direction_rejected(self):
        for bad in (True, False, 1.0, -1.0, "1", None, 0, 2, -2, [1], {"dir": 1}):
            with self.subTest(dir=bad):
                entity = arc_entity()
                entity["dir"] = bad
                with self.assertRaisesRegex(ValidationError, "strict integer"):
                    Arc.model_validate(entity)

    def test_angles_must_be_finite(self):
        for bad in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(angle=bad):
                with self.assertRaises(ValidationError):
                    Arc.model_validate(arc_entity(start_deg=bad))
                with self.assertRaises(ValidationError):
                    Arc.model_validate(arc_entity(end_deg=bad))

    def test_zero_sweep_and_full_circle_rejected(self):
        cases = ((0.0, 0.0, None), (0.0, 360.0, None), (90.0, 450.0, None), (0.0, 360.0, -1))
        for start_deg, end_deg, direction in cases:
            with self.subTest(start=start_deg, end=end_deg, dir=direction):
                with self.assertRaisesRegex(ValidationError, "circle"):
                    Arc.model_validate(
                        arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)
                    )

    def test_large_arc_and_zero_crossing_allowed(self):
        for start_deg, end_deg, direction in (
            (0.0, 180.0, 1),
            (0.0, 270.0, 1),
            (350.0, 10.0, 1),
            (10.0, 350.0, -1),
            (0.0, 180.0, -1),
        ):
            with self.subTest(start=start_deg, end=end_deg, dir=direction):
                arc = Arc.model_validate(
                    arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)
                )
                self.assertEqual(arc.dir, direction)

    def test_sketch_and_update_entries_share_the_contract(self):
        entities = [arc_entity(direction=-1)]
        SketchOp(op="sketch", label="s1", entities=entities)
        SketchGeometryOp(op="update_sketch_geometry", sketch="s1", entities=entities)
        with self.assertRaisesRegex(ValidationError, "strict integer"):
            SketchOp(op="sketch", label="s1", entities=[arc_entity(direction=1.0)])
        with self.assertRaisesRegex(ValidationError, "strict integer"):
            SketchGeometryOp(
                op="update_sketch_geometry", sketch="s1", entities=[arc_entity(direction="1")]
            )


class ArcLegacyRegressionOracleTests(unittest.TestCase):
    """The reported R10 arc + chord volumes and their explicit-direction twins."""

    def test_legacy_zero_to_ninety(self):
        entities = arc_with_chord(0.0, 90.0)
        self.assertNotIn("dir", entities[0])
        volume = segment_volume_from_analysis(entities)
        self.assertAlmostEqual(volume, oracle_segment_volume_mm3(0.0, 90.0, 1), places=9)
        self.assertAlmostEqual(volume, VOLUME_90_MM3, places=9)
        validate_solid_profile(entities, "coordinates")

    def test_legacy_ninety_to_zero(self):
        entities = arc_with_chord(90.0, 0.0)
        self.assertNotIn("dir", entities[0])
        volume = segment_volume_from_analysis(entities)
        self.assertAlmostEqual(volume, oracle_segment_volume_mm3(90.0, 0.0, 1), places=9)
        self.assertAlmostEqual(volume, VOLUME_270_MM3, places=9)

    def test_clockwise_ninety_to_zero_is_the_small_segment(self):
        entities = arc_with_chord(90.0, 0.0, direction=-1)
        volume = segment_volume_from_analysis(entities)
        self.assertAlmostEqual(volume, oracle_segment_volume_mm3(90.0, 0.0, -1), places=9)
        self.assertAlmostEqual(volume, VOLUME_90_MM3, places=9)

    def test_clockwise_zero_to_ninety_is_the_large_segment(self):
        entities = arc_with_chord(0.0, 90.0, direction=-1)
        volume = segment_volume_from_analysis(entities)
        self.assertAlmostEqual(volume, oracle_segment_volume_mm3(0.0, 90.0, -1), places=9)
        self.assertAlmostEqual(volume, VOLUME_270_MM3, places=9)

    def test_two_segments_partition_the_circle(self):
        self.assertAlmostEqual(VOLUME_90_MM3 + VOLUME_270_MM3, DEPTH_MM * math.pi * RADIUS_MM**2)

    def test_legacy_input_still_passes_closed_profile(self):
        for entities in (arc_with_chord(0.0, 90.0), arc_with_chord(90.0, 0.0)):
            result = closed_profile(entities)
            self.assertEqual(result["closed_contour_count"], 1)


class ArcAnalyzerDirectionTests(unittest.TestCase):
    """The analyzer consumes dir: sweeps, zero crossing and 180/270 degrees."""

    def test_reported_sweeps(self):
        for start_deg, end_deg, direction, expected in (
            (0.0, 180.0, 1, 180.0),
            (0.0, 270.0, 1, 270.0),
            (350.0, 10.0, 1, 20.0),
            (10.0, 350.0, 1, 340.0),
            (0.0, 90.0, -1, 270.0),
            (90.0, 0.0, -1, 90.0),
            (350.0, 10.0, -1, 340.0),
        ):
            with self.subTest(start=start_deg, end=end_deg, dir=direction):
                report = analyze_profile(
                    [arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)]
                )
                echo = report["arc_geometry"][0]
                self.assertAlmostEqual(echo["sweep_deg"], expected, places=9)
                self.assertAlmostEqual(
                    oracle_sweep_deg(start_deg, end_deg, direction), expected, places=9
                )

    def test_volume_for_one_eighty_and_two_seventy(self):
        half = segment_volume_from_analysis(arc_with_chord(0.0, 180.0, 1))
        self.assertAlmostEqual(half, DEPTH_MM * 0.5 * RADIUS_MM**2 * math.pi, places=9)
        for start_deg, end_deg, direction in ((0.0, 270.0, 1), (0.0, 90.0, -1)):
            volume = segment_volume_from_analysis(arc_with_chord(start_deg, end_deg, direction))
            self.assertAlmostEqual(
                volume, oracle_segment_volume_mm3(start_deg, end_deg, direction), places=9
            )

    def test_reversed_representation_is_the_same_geometry(self):
        direct = analyze_profile(arc_with_chord(0.0, 90.0, 1))
        reversed_input = analyze_profile(arc_with_chord(90.0, 0.0, -1))
        self.assertAlmostEqual(
            direct["material_area_mm2"], reversed_input["material_area_mm2"], places=9
        )
        first, second = direct["arc_geometry"][0], reversed_input["arc_geometry"][0]
        self.assertEqual(first["dir"], -second["dir"])
        self.assertAlmostEqual(first["sweep_deg"], second["sweep_deg"], places=9)
        for left, right in zip(first["start_uv"], second["end_uv"]):
            self.assertAlmostEqual(left, right, places=9)
        for left, right in zip(first["end_uv"], second["start_uv"]):
            self.assertAlmostEqual(left, right, places=9)

    def test_input_echo_is_labelled_not_measured(self):
        echo = analyze_profile([arc_entity(start_deg=0.0, end_deg=90.0, direction=-1)])[
            "arc_geometry"
        ][0]
        self.assertEqual(echo["source"], "input")
        self.assertIsNone(echo["query_code"])
        self.assertEqual(echo["frame"], "sketch_local")
        self.assertEqual(echo["dir"], -1)
        self.assertAlmostEqual(echo["start_uv"][0], RADIUS_MM, places=9)
        self.assertAlmostEqual(echo["start_tangent_uv"][1], -1.0, places=9)
        self.assertAlmostEqual(echo["end_tangent_uv"][0], 1.0, places=9)

    def test_analyzer_rejects_the_same_illegal_values(self):
        with self.assertRaisesRegex(ValueError, "strict integer"):
            analyze_profile([arc_entity(direction=1.0)])
        with self.assertRaisesRegex(ValueError, "circle"):
            analyze_profile([arc_entity(start_deg=0.0, end_deg=360.0)])


class ArcFrameTests(unittest.TestCase):
    """Rotated and flipped local frames keep the declared geometry consistent."""

    def test_rotated_frame_keeps_sweep_and_area(self):
        turn = 37.0
        rotated = arc_with_chord(0.0, 90.0, 1)
        for entity in rotated:
            if entity["type"] == "arc":
                entity["center"] = [3.0, -2.0]
                entity["start_angle"] = 0.0 + turn
                entity["end_angle"] = 90.0 + turn
            else:
                start, end = on_circle(90.0 + turn), on_circle(0.0 + turn)
                entity["start"] = [3.0 + start[0], -2.0 + start[1]]
                entity["end"] = [3.0 + end[0], -2.0 + end[1]]
        volume = segment_volume_from_analysis(rotated)
        self.assertAlmostEqual(volume, VOLUME_90_MM3, places=6)
        echo = analyze_profile(rotated)["arc_geometry"][0]
        self.assertAlmostEqual(echo["sweep_deg"], 90.0, places=9)

    def test_flipped_frame_reverses_the_direction(self):
        # Mirroring the sketch-local frame maps a CCW arc onto a CW arc of the
        # mirrored coordinates; dir flips with the frame handedness.
        mirrored = arc_with_chord(0.0, 90.0, 1)
        for entity in mirrored:
            if entity["type"] == "arc":
                entity["start_angle"] = -0.0
                entity["end_angle"] = -90.0
                entity["dir"] = -1
            else:
                entity["start"] = on_circle(-90.0)
                entity["end"] = on_circle(-0.0)
        echo = analyze_profile(mirrored)["arc_geometry"][0]
        self.assertEqual(echo["dir"], -1)
        self.assertAlmostEqual(echo["sweep_deg"], 90.0, places=9)
        volume = segment_volume_from_analysis(mirrored)
        self.assertAlmostEqual(volume, VOLUME_90_MM3, places=6)
        self.assertAlmostEqual(volume, oracle_segment_volume_mm3(0.0, -90.0, -1), places=6)


class ArcEditAndDownstreamTests(unittest.TestCase):
    """Geometry updates and downstream volume expectations on the same entries."""

    def test_update_entry_consume_direction(self):
        update = SketchGeometryOp(
            op="update_sketch_geometry",
            sketch="rev_sk",
            entities=arc_with_chord(0.0, 90.0, -1),
            dimensioning="autodim",
        )
        self.assertEqual(update.entities[0].dir, -1)
        volume = segment_volume_from_analysis([entity.model_dump() for entity in update.entities])
        self.assertAlmostEqual(volume, VOLUME_270_MM3, places=9)

    def test_illegal_edit_rejected_before_any_geometry(self):
        with self.assertRaisesRegex(ValidationError, "strict integer"):
            SketchGeometryOp(
                op="update_sketch_geometry",
                sketch="rev_sk",
                entities=[arc_entity(direction=0)],
            )
        with self.assertRaisesRegex(ValidationError, "circle"):
            SketchGeometryOp(
                op="update_sketch_geometry",
                sketch="rev_sk",
                entities=[arc_entity(start_deg=45.0, end_deg=405.0)],
            )

    def test_direction_edit_switches_the_segment(self):
        before = segment_volume_from_analysis(arc_with_chord(0.0, 90.0, 1))
        after = segment_volume_from_analysis(arc_with_chord(0.0, 90.0, -1))
        self.assertAlmostEqual(before, VOLUME_90_MM3, places=9)
        self.assertAlmostEqual(after, VOLUME_270_MM3, places=9)
        self.assertAlmostEqual(before + after, DEPTH_MM * math.pi * RADIUS_MM**2, places=9)


class ArcEchoProjectionTests(unittest.TestCase):
    """Results echo measured geometry or unknown; they never echo the request."""

    @staticmethod
    def sketch_result(measured=None) -> dict:
        record = {
            "op": "sketch",
            "index": 0,
            "label": "s1",
            "succeeded": True,
        }
        if measured is not None:
            record["arc_geometry"] = measured
        return {
            "success": True,
            "operations": [record],
        }

    def test_native_echo_is_projected(self):
        measured = [
            {
                "name": "arc_a",
                "source": "native",
                "query_code": 0,
                "frame": "sketch_local",
                "start_uv": [1.0, 2.0],
                "end_uv": [3.0, 4.0],
                "start_tangent_uv": [0.0, -1.0],
                "end_tangent_uv": [1.0, 0.0],
                "dir": -1,
                "sweep_deg": 270.0,
            }
        ]
        result = self.sketch_result(measured)
        annotated = operation_results.annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": arc_with_chord(0.0, 90.0, -1)}],
        )
        echo = annotated["operations"][0]["arc_geometry"]
        self.assertEqual(len(echo), 1)
        self.assertEqual(echo[0]["source"], "native")
        self.assertEqual(echo[0]["start_uv"], [1.0, 2.0])
        self.assertEqual(echo[0]["sweep_deg"], 270.0)

    def test_missing_native_echo_reports_unknown(self):
        entities = arc_with_chord(0.0, 90.0, -1)
        result = self.sketch_result()
        annotated = operation_results.annotate_native_result(
            result, readonly=False, inputs=[{"op": "sketch", "label": "s1", "entities": entities}]
        )
        echo = annotated["operations"][0]["arc_geometry"]
        self.assertEqual(echo[0]["source"], "unknown")
        self.assertIsNone(echo[0]["query_code"])
        for key in operation_results._ARC_MEASURED_FIELDS:
            self.assertIsNone(echo[0][key], key)
        # The requested angles never appear as measured values.
        self.assertNotEqual(echo[0]["start_uv"], on_circle(0.0))

    def test_unknown_query_code_is_preserved(self):
        entities = [arc_entity(start_deg=0.0, end_deg=90.0)]
        result = self.sketch_result([{"name": "arc_a", "source": "unknown", "query_code": 42}])
        annotated = operation_results.annotate_native_result(
            result, readonly=False, inputs=[{"op": "sketch", "label": "s1", "entities": entities}]
        )
        echo = annotated["operations"][0]["arc_geometry"]
        self.assertEqual(echo[0]["source"], "unknown")
        self.assertEqual(echo[0]["query_code"], 42)

    def test_incomplete_native_record_is_downgraded(self):
        entities = [arc_entity(start_deg=0.0, end_deg=90.0)]
        result = self.sketch_result(
            [{"name": "arc_a", "source": "native", "query_code": 0, "start_uv": [1.0, 2.0]}]
        )
        annotated = operation_results.annotate_native_result(
            result, readonly=False, inputs=[{"op": "sketch", "label": "s1", "entities": entities}]
        )
        echo = annotated["operations"][0]["arc_geometry"]
        self.assertEqual(echo[0]["source"], "unknown")

    def test_update_operations_get_the_same_echo(self):
        entities = arc_with_chord(90.0, 0.0, -1)
        result = {
            "success": True,
            "operations": [
                {
                    "op": "update_sketch_geometry",
                    "index": 0,
                    "label": "",
                    "sketch": "rev_sk",
                    "succeeded": True,
                }
            ],
        }
        annotated = operation_results.annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "update_sketch_geometry", "sketch": "rev_sk", "entities": entities}],
        )
        echo = annotated["operations"][0]["arc_geometry"]
        self.assertEqual(echo[0]["source"], "unknown")
        self.assertIsNone(echo[0]["sweep_deg"])

    def test_input_profile_echo_is_separate_from_the_measured_echo(self):
        entities = arc_with_chord(0.0, 90.0, -1)
        result = self.sketch_result()
        annotated = operation_results.annotate_native_result(
            result, readonly=False, inputs=[{"op": "sketch", "label": "s1", "entities": entities}]
        )
        operation = annotated["operations"][0]
        self.assertEqual(operation["profile"]["source"], "input")
        self.assertEqual(operation["profile"]["arc_geometry"][0]["source"], "input")
        self.assertEqual(operation["arc_geometry"][0]["source"], "unknown")


if __name__ == "__main__":
    unittest.main()
