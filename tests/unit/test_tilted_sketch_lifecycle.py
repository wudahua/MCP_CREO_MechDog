"""Offline geometry, matrix, and no-live gates for DEV-051 T06."""

import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import test_tilted_sketch_lifecycle as lifecycle


class TiltedSketchLifecycleTests(unittest.TestCase):
    def test_polygon_has_thirty_closed_independent_lines_and_area(self):
        entities = lifecycle.polygon_entities()
        self.assertEqual(len(entities), 30)
        self.assertEqual(len({item["name"] for item in entities}), 30)
        for index, entity in enumerate(entities):
            self.assertEqual(entity["end"], entities[(index + 1) % 30]["start"])
        shoelace = (
            abs(
                sum(
                    item["start"][0] * item["end"][1] - item["end"][0] * item["start"][1]
                    for item in entities
                )
            )
            / 2
        )
        self.assertAlmostEqual(shoelace, lifecycle.independent_area_mm2(), places=10)
        self.assertLess(lifecycle.independent_area_mm2(), math.pi * 25)

    def test_case_matrix_is_independent_and_valid(self):
        cases = lifecycle.build_cases("abc12345")
        lifecycle.validate_cases(cases)
        self.assertEqual(len(cases), 32)
        self.assertEqual(len({case["model_name"] for case in cases}), 32)
        for case in cases:
            self.assertTrue(case["new_part_required"])
            self.assertTrue(case["second_reference_must_be_verified_live"])
            self.assertTrue(case["failed_then_same_face_rectangle"]["conditional"])
            kinds = [op["label"] for op in case["ordered_sketch_submissions"]]
            if case["case"].endswith("polygon_then_rectangle"):
                self.assertEqual(kinds, ["polygon", "rectangle"])
            if case["case"].endswith("rectangle_then_polygon"):
                self.assertEqual(kinds, ["rectangle", "polygon"])

    def test_live_gate_refuses_before_creating_report(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "test_tilted_sketch_lifecycle.py"), "--live"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses --live", result.stderr)


if __name__ == "__main__":
    unittest.main()
