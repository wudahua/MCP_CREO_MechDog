"""FEAT-067: a plan can assert the model's millimetre bounding box.

The 2026-11-12 bulb feedback proposed the box from the source drawing
(X 6409.4736..7809.4736, Y 0..181.325, Z -660..-460 mm) as a machine-checkable
acceptance gate. The measured side is the per-body outline the inspection already
records; nothing here builds geometry.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from creo_mechdog.schema import Assertions

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "generic.cpp"


def bulb_box(**overrides):
    box = {
        "min": [6409.4736, 0.0, -660.0],
        "max": [7809.4736, 181.325, -460.0],
        "tolerance_mm": 0.001,
    }
    box.update(overrides)
    return box


class BboxAssertionSchema(unittest.TestCase):
    def test_accepts_the_bulb_box(self):
        assertions = Assertions.model_validate({"bbox_mm": bulb_box()})
        payload = assertions.model_dump(exclude_none=True)
        self.assertEqual(payload["bbox_mm"]["min"], [6409.4736, 0.0, -660.0])
        self.assertEqual(payload["bbox_mm"]["max"], [7809.4736, 181.325, -460.0])
        self.assertEqual(payload["bbox_mm"]["tolerance_mm"], 0.001)

    def test_default_tolerance_is_one_thousandth_of_a_millimetre(self):
        box = bulb_box()
        box.pop("tolerance_mm")
        self.assertEqual(Assertions.model_validate({"bbox_mm": box}).bbox_mm.tolerance_mm, 1e-3)

    def test_rejects_a_box_that_is_not_three_coordinates(self):
        for box in (bulb_box(min=[0.0, 0.0]), bulb_box(max=[1.0, 2.0, 3.0, 4.0])):
            with self.subTest(box=box), self.assertRaises(ValueError):
                Assertions.model_validate({"bbox_mm": box})

    def test_rejects_non_finite_and_boolean_coordinates(self):
        for bad in (float("nan"), float("inf"), True, "1.0"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Assertions.model_validate({"bbox_mm": bulb_box(min=[bad, 0.0, 0.0])})

    def test_rejects_a_reversed_axis(self):
        with self.assertRaises(ValueError):
            Assertions.model_validate({"bbox_mm": bulb_box(min=[6409.4736, 200.0, -660.0])})

    def test_rejects_a_non_positive_tolerance(self):
        for tolerance in (0.0, -1.0):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                Assertions.model_validate({"bbox_mm": bulb_box(tolerance_mm=tolerance)})

    def test_absent_box_keeps_the_key_out_of_the_native_request(self):
        self.assertNotIn("bbox_mm", Assertions.model_validate({}).model_dump(exclude_none=True))


class NativeBboxContract(unittest.TestCase):
    def setUp(self):
        self.source = NATIVE.read_text(encoding="utf-8", errors="replace")

    def test_the_measured_box_uses_the_recorded_body_outline(self):
        self.assertIn("static J measured_bbox_mm(const J &state)", self.source)
        self.assertIn('state["bodies"]', self.source)
        self.assertIn("length_scale_to_mm(board, inspect_length_units(board))", self.source)

    def test_an_unknown_unit_fails_instead_of_comparing_native_units(self):
        self.assertIn("cannot be converted to millimetres", self.source)
        self.assertIn("Bounding box assertion failed", self.source)
        self.assertIn("tolerance ", self.source)

    def test_the_gate_is_checked_before_the_comparison_and_never_after_save_only(self):
        gate = self.source.index('a.contains("bbox_mm")')
        save = self.source.index('generic_stage("save_and_reload")')
        self.assertLess(gate, save)


if __name__ == "__main__":
    unittest.main()
