"""BUG-049 / N03: near-tolerance endpoint fixtures and projection locks.

Fixtures come from the driver (tools/test_profile_endpoint_diagnostics.py);
the original 0.8.5 attachments (gear10.json, gear10_snapped.json,
mc_rings10.json, mc_prep.py) are missing per the N00 mapping, so these are
fixed line/arc substitutes, not a replay of the reported case.

The gap constants are experimental sampling points around the 1e-6 mm
diagnostic clustering value and the externally reported 7.72e-7 mm case.
They are NOT admission thresholds and are never claimed to be the kernel
welding tolerance: input closure uses 1e-4 mm (auto/autodim) or 1e-9 mm
(coordinates), and the native summary clusters endpoints at 1e-6 mm only for
its own report.
"""

from __future__ import annotations

import math
import unittest

from creo_mechdog import operation_results
from creo_mechdog.profile_diagnostics import analyze_profile, validate_solid_profile
from tools import test_profile_endpoint_diagnostics as driver

GAP_SAMPLES_MM = driver.GAP_SAMPLES_MM
OPEN_CHAIN_GAP_MM = driver.OPEN_CHAIN_GAP_MM
SQUARE_AREA_MM2 = driver.SQUARE_SIDE_MM**2
RING_AREA_MM2 = math.pi * driver.RING_RADIUS_MM**2
STADIUM_AREA_MM2 = driver.closed_form_area("stadium")
SAMPLE_LIMIT = driver.SAMPLE_LIMIT

gapped_square = driver.gapped_square
ring_entities = driver.ring_entities
gapped_stadium = driver.gapped_stadium
independent_endpoint_gap = driver.independent_endpoint_gap


def sketch_result(native_section=None) -> dict:
    record = {"op": "sketch", "index": 0, "label": "s1", "succeeded": True}
    result = {"success": True, "operations": [record]}
    if native_section is not None:
        result["operations"][0]["native_section"] = native_section
    return result


def annotated_profile(entities: list[dict], native_section=None) -> dict:
    result = operation_results.annotate_native_result(
        sketch_result(native_section),
        readonly=False,
        inputs=[{"op": "sketch", "label": "s1", "entities": entities}],
    )
    return result["operations"][0]["profile"]


class NearToleranceFixtureTests(unittest.TestCase):
    """The gap samples close under 1e-4 input closure and never under 1e-9."""

    def test_exact_square_closes_at_both_input_tolerances(self):
        for tolerance in (1e-4, 1e-9):
            report = analyze_profile(gapped_square(0.0), tolerance)
            self.assertEqual(report["closed_contour_count"], 1)
            self.assertEqual(report["categories"]["near_tolerance"]["count"], 0)
            self.assertAlmostEqual(report["material_area_mm2"], SQUARE_AREA_MM2, places=9)

    def test_gap_samples_close_under_default_and_flag_near_tolerance(self):
        for gap in GAP_SAMPLES_MM:
            with self.subTest(gap=gap):
                report = analyze_profile(gapped_square(gap))
                self.assertEqual(report["closed_contour_count"], 1)
                near = report["categories"]["near_tolerance"]
                self.assertEqual(near["count"], 1)
                item = near["items"][0]
                self.assertAlmostEqual(item["gap_mm"], gap, delta=gap * 1e-3)
                self.assertEqual(item["tolerance_mm"], 1e-4)
                contour = report["contours"][0]
                self.assertAlmostEqual(contour["max_join_gap_mm"], gap, delta=gap * 1e-3)

    def test_gap_samples_open_under_exact_tolerance(self):
        for gap in GAP_SAMPLES_MM:
            with self.subTest(gap=gap):
                report = analyze_profile(gapped_square(gap), 1e-9)
                self.assertEqual(report["closed_contour_count"], 0)
                self.assertEqual(report["open_contour_count"], 1)

    def test_gap_samples_admitted_for_auto_rejected_for_coordinates(self):
        for gap in GAP_SAMPLES_MM:
            entities = gapped_square(gap)
            validate_solid_profile(entities, "auto")
            with self.subTest(gap=gap):
                with self.assertRaisesRegex(ValueError, "near_tolerance"):
                    validate_solid_profile(entities, "coordinates")

    def test_open_chain_rejected_even_for_auto(self):
        report = analyze_profile(gapped_square(OPEN_CHAIN_GAP_MM))
        self.assertEqual(report["closed_contour_count"], 0)
        self.assertEqual(report["open_contour_count"], 1)
        self.assertEqual(report["categories"]["open"]["count"], 1)
        with self.assertRaisesRegex(ValueError, "open"):
            validate_solid_profile(gapped_square(OPEN_CHAIN_GAP_MM), "auto")

    def test_designed_gap_matches_independent_endpoint_distance(self):
        for gap in GAP_SAMPLES_MM:
            with self.subTest(gap=gap):
                measured = independent_endpoint_gap(gapped_square(gap))
                self.assertAlmostEqual(measured, gap, delta=gap * 1e-6)

    def test_ring_gap_uses_derived_angular_shortfall(self):
        for gap in GAP_SAMPLES_MM:
            with self.subTest(gap=gap):
                entities = ring_entities(gap)
                measured = independent_endpoint_gap(entities)
                # chord = 2 r sin(delta/2) with delta = gap/r radians; the
                # degrees round-trip allows a 1e-7 relative slack.
                expected = 2 * driver.RING_RADIUS_MM * math.sin(gap / driver.RING_RADIUS_MM / 2)
                self.assertAlmostEqual(measured, expected, delta=expected * 1e-7)
                report = analyze_profile(entities)
                self.assertEqual(report["closed_contour_count"], 1)
                self.assertEqual(report["categories"]["near_tolerance"]["count"], 1)

    def test_line_arc_mixture_closes_with_exact_area(self):
        for gap in (0.0, GAP_SAMPLES_MM[-1]):
            with self.subTest(gap=gap):
                report = analyze_profile(gapped_stadium(gap))
                self.assertEqual(report["closed_contour_count"], 1)
                # The clustered walk omits the closing chord's line integral;
                # for a chord at y=r the correction is 0.5*r*gap (3e-6 mm^2 at
                # the largest sample, negligible against the area oracle).
                expected = STADIUM_AREA_MM2 - 0.5 * driver.STADIUM_RADIUS_MM * gap
                self.assertAlmostEqual(report["material_area_mm2"], expected, delta=1e-9)
                if gap:
                    self.assertEqual(report["categories"]["near_tolerance"]["count"], 1)


class ProjectionObservabilityTests(unittest.TestCase):
    """The public profile projection keeps bounded gap info and totals."""

    def test_profile_summary_is_labelled_input(self):
        profile = annotated_profile(gapped_square(0.0))
        self.assertEqual(profile["source"], "input")

    def test_missing_native_section_is_not_filled(self):
        result = operation_results.annotate_native_result(
            sketch_result(),
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": gapped_square(0.0)}],
        )
        record = result["operations"][0]
        self.assertNotIn("native_section", record)
        self.assertEqual(record["profile"]["source"], "input")

    def test_unavailable_native_section_stays_unavailable(self):
        result = operation_results.annotate_native_result(
            sketch_result({"available": False, "query_code": -4}),
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": gapped_square(0.0)}],
        )
        record = result["operations"][0]
        self.assertEqual(record["native_section"]["available"], False)
        self.assertEqual(record["native_section"]["query_code"], -4)

    def test_projection_exposes_max_endpoint_gap(self):
        profile = annotated_profile(gapped_square(GAP_SAMPLES_MM[-1]))
        self.assertAlmostEqual(
            profile["max_endpoint_gap_mm"], GAP_SAMPLES_MM[-1], delta=GAP_SAMPLES_MM[-1] * 1e-3
        )

    def test_projection_keeps_bounded_near_tolerance_pairs(self):
        profile = annotated_profile(gapped_square(0.77e-6))
        pairs = profile["near_tolerance_pairs"]
        self.assertEqual(pairs["total"], 1)
        self.assertFalse(pairs["truncated"])
        self.assertEqual(len(pairs["sample"]), 1)
        self.assertAlmostEqual(pairs["sample"][0]["gap_mm"], 0.77e-6, delta=0.77e-9)
        self.assertIn("sq_l0", pairs["sample"][0]["entities"])
        self.assertIn("sq_l3", pairs["sample"][0]["entities"])

    def test_projection_truncates_samples_but_keeps_totals(self):
        entities: list[dict] = []
        for index in range(25):
            entities.extend(gapped_square(0.5e-6, origin=(index * 15.0, 0.0)))
        profile = annotated_profile(entities)
        self.assertEqual(profile["closed_contour_count"], 25)
        pairs = profile["near_tolerance_pairs"]
        self.assertEqual(pairs["total"], 25)
        self.assertTrue(pairs["truncated"])
        self.assertEqual(len(pairs["sample"]), SAMPLE_LIMIT)

    def test_exact_square_reports_zero_gap(self):
        profile = annotated_profile(gapped_square(0.0))
        self.assertEqual(profile["max_endpoint_gap_mm"], 0.0)
        self.assertEqual(profile["near_tolerance_pairs"]["total"], 0)


class ArcCenterRadiusEchoTests(unittest.TestCase):
    """Arc center and radius are echoed on both sides for two-stage comparison."""

    def test_input_echo_reports_center_and_radius(self):
        echo = analyze_profile(ring_entities(0.0))["arc_geometry"][0]
        self.assertEqual(echo["center_uv"], [0.0, 0.0])
        self.assertEqual(echo["radius_mm"], driver.RING_RADIUS_MM)

    def test_projection_passes_measured_center_through(self):
        measured = [
            {
                "name": "ring_a0",
                "source": "native",
                "query_code": 0,
                "frame": "sketch_local",
                "start_uv": [driver.RING_RADIUS_MM, 0.0],
                "end_uv": [0.0, driver.RING_RADIUS_MM],
                "start_tangent_uv": [0.0, 1.0],
                "end_tangent_uv": [-1.0, 0.0],
                "dir": 1,
                "sweep_deg": 90.0,
                "center_uv": [1e-12, -2e-12],
                "radius_mm": driver.RING_RADIUS_MM + 3e-13,
            }
        ]
        result = operation_results.annotate_native_result(
            sketch_result(),
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": ring_entities(0.0)}],
        )
        result["operations"][0]["arc_geometry"] = measured
        result = operation_results.annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": ring_entities(0.0)}],
        )
        echo = result["operations"][0]["arc_geometry"][0]
        self.assertEqual(echo["source"], "native")
        self.assertAlmostEqual(echo["center_uv"][0], 1e-12, places=15)
        self.assertAlmostEqual(echo["radius_mm"], driver.RING_RADIUS_MM, places=12)

    def test_legacy_measured_record_without_center_stays_native(self):
        # A pre-existing worker record without the new fields keeps source
        # native; the missing fields stay null instead of degrading the entry.
        measured = [
            {
                "name": "ring_a0",
                "source": "native",
                "query_code": 0,
                "frame": "sketch_local",
                "start_uv": [driver.RING_RADIUS_MM, 0.0],
                "end_uv": [0.0, driver.RING_RADIUS_MM],
                "start_tangent_uv": [0.0, 1.0],
                "end_tangent_uv": [-1.0, 0.0],
                "dir": 1,
                "sweep_deg": 90.0,
            }
        ]
        result = operation_results.annotate_native_result(
            sketch_result(),
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": ring_entities(0.0)}],
        )
        result["operations"][0]["arc_geometry"] = measured
        result = operation_results.annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "sketch", "label": "s1", "entities": ring_entities(0.0)}],
        )
        echo = result["operations"][0]["arc_geometry"][0]
        self.assertEqual(echo["source"], "native")
        self.assertIsNone(echo["center_uv"])
        self.assertIsNone(echo["radius_mm"])


class DriverOfflineContractTests(unittest.TestCase):
    """The driver's own offline matrix stays self-consistent."""

    def test_every_gap_case_is_admitted_and_the_open_chain_is_not(self):
        from creo_mechdog.schema import validate_operations

        validate_operations(driver.plate_operations())
        for case in driver.build_cases("unittest"):
            validate_operations(driver.cut_operations(case))
        with self.assertRaises(ValueError):
            validate_operations(driver.open_chain_operations())

    def test_case_names_are_valid_model_names(self):
        for case in driver.build_cases("abcd1234"):
            name = case["model_name"]
            self.assertLessEqual(len(name), 31)
            self.assertTrue(name[0].isalnum())
            self.assertTrue(all(c.islower() or c.isdigit() or c == "_" for c in name))


if __name__ == "__main__":
    unittest.main()
