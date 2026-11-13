"""FEAT-067: a plan can assert the part's total surface area in square millimetres.

The 2026-11-12 bulb feedback asked for the same machine-checkable treatment the
bounding box got (13.2). The measured side walks every face of the solid once and
scales twice; nothing here builds or approximates geometry.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from creo_mechdog.schema import Assertions

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "generic.cpp"


class SurfaceAreaAssertionSchema(unittest.TestCase):
    def test_accepts_an_area_and_defaults_the_tolerance(self):
        assertions = Assertions.model_validate({"surface_area_mm2": 440.0})
        payload = assertions.model_dump(exclude_none=True)
        self.assertEqual(payload["surface_area_mm2"], 440.0)
        self.assertEqual(payload["surface_area_tolerance_mm2"], 0.01)

    def test_accepts_an_explicit_tolerance(self):
        assertions = Assertions.model_validate(
            {"surface_area_mm2": 1540.0, "surface_area_tolerance_mm2": 0.5}
        )
        self.assertEqual(assertions.surface_area_tolerance_mm2, 0.5)

    def test_accepts_a_measured_zero(self):
        self.assertEqual(Assertions.model_validate({"surface_area_mm2": 0}).surface_area_mm2, 0.0)

    def test_rejects_non_finite_boolean_and_textual_areas(self):
        for bad in (float("nan"), float("inf"), True, "440.0"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Assertions.model_validate({"surface_area_mm2": bad})

    def test_rejects_a_negative_area(self):
        with self.assertRaises(ValueError):
            Assertions.model_validate({"surface_area_mm2": -1.0})

    def test_rejects_a_non_positive_or_non_finite_tolerance(self):
        for tolerance in (0.0, -0.01, float("inf"), True):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                Assertions.model_validate(
                    {"surface_area_mm2": 440.0, "surface_area_tolerance_mm2": tolerance}
                )

    def test_absent_area_keeps_the_key_out_of_the_native_request(self):
        payload = Assertions.model_validate({}).model_dump(exclude_none=True)
        self.assertNotIn("surface_area_mm2", payload)


class NativeSurfaceAreaContract(unittest.TestCase):
    def setUp(self):
        self.source = NATIVE.read_text(encoding="utf-8", errors="replace")

    def test_the_measured_area_walks_every_face_of_the_solid(self):
        self.assertIn("static J measured_surface_area_mm2(const J &state)", self.source)
        self.assertIn("ProSolidSurfaceVisit((ProSolid)board", self.source)
        self.assertIn("surface_area_native(surface)", self.source)

    def test_the_area_is_scaled_twice_and_never_assumed(self):
        self.assertIn("area.value * scale.scale * scale.scale", self.source)
        self.assertIn("cannot be converted to millimetres", self.source)
        self.assertIn("Surface area assertion failed", self.source)

    def test_a_failed_face_fails_the_whole_sum(self):
        self.assertIn("surface_area_eval_failed", self.source)
        self.assertIn("solid_surface_visit_failed", self.source)

    def test_an_assembly_is_refused_instead_of_measured(self):
        self.assertIn("the surface area assertion measures a part, not a ", self.source)

    def test_the_gate_is_checked_before_the_comparison_and_never_after_save_only(self):
        gate = self.source.index('a.contains("surface_area_mm2")')
        save = self.source.index('generic_stage("save_and_reload")')
        self.assertLess(gate, save)

    def test_the_tolerance_is_absolute_square_millimetres(self):
        self.assertIn('a.value("surface_area_tolerance_mm2", 0.01)', self.source)
        self.assertIn("mm2 tolerance ", self.source)


if __name__ == "__main__":
    unittest.main()
