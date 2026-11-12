"""FEAT-066: exact NURBS sketch entity contract.

The 0.20.0 / 0.21.0 feedback asked for a 1:1 TXT NURBS entry. ``spline`` only
carries interpolant points, so the kernel fits a different curve. ``b_spline``
maps to Pro2dBSplinedef (degree + clamped knots + control points + weights).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

from creo_mechdog.profile_checks import closed_profile
from creo_mechdog.schema import BSpline, SketchOp

ROOT = Path(__file__).resolve().parents[2]


def curve(**overrides):
    payload = {
        "type": "b_spline",
        "name": "side_guide",
        "degree": 3,
        "control_points": [[0, 0], [10, 8], [30, 9], [45, 2], [50, 0]],
    }
    payload.update(overrides)
    return BSpline(**payload)


class BSplineSchemaTests(unittest.TestCase):
    def test_default_knots_are_clamped_and_uniform(self):
        entity = curve()
        self.assertEqual(entity.knots, [0.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0, 1.0, 1.0])
        self.assertIsNone(entity.weights)
        self.assertEqual(entity.degree, 3)

    def test_explicit_txt_knots_are_preserved(self):
        knots = [0, 0, 0, 0, 0.595088181, 1, 1, 1, 1]
        entity = curve(knots=knots)
        self.assertEqual(entity.knots, [float(value) for value in knots])

    def test_knot_count_must_match_control_points_and_degree(self):
        with self.assertRaisesRegex(ValidationError, "needs 9 knots"):
            curve(knots=[0, 0, 0, 0, 1, 1, 1, 1])

    def test_knots_must_be_clamped(self):
        with self.assertRaisesRegex(ValidationError, "clamped"):
            curve(knots=[0, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 0.9, 1.0])

    def test_knots_must_not_decrease(self):
        with self.assertRaisesRegex(ValidationError, "nondecreasing"):
            curve(knots=[0, 0, 0, 0, 0.6, 0.4, 1, 1, 1])

    def test_weights_need_one_positive_value_per_control_point(self):
        with self.assertRaisesRegex(ValidationError, "one value per control point"):
            curve(weights=[1, 1, 1])
        with self.assertRaisesRegex(ValidationError, "greater than zero"):
            curve(weights=[1, 1, 0, 1, 1])

    def test_degree_must_be_below_the_control_point_count(self):
        with self.assertRaisesRegex(ValidationError, "needs at least"):
            curve(degree=5)

    def test_degree_rejects_bool(self):
        with self.assertRaisesRegex(ValidationError, "integer between 1 and 10"):
            curve(degree=True)

    def test_closed_is_not_a_field(self):
        with self.assertRaises(ValidationError):
            curve(closed=True)

    def test_entity_union_discriminates_b_spline(self):
        op = SketchOp(
            op="sketch",
            label="profile",
            entities=[
                {
                    "type": "b_spline",
                    "name": "arc",
                    "degree": 2,
                    "control_points": [[0, 0], [10, 0], [10, 10]],
                }
            ],
        )
        self.assertIsInstance(op.entities[0], BSpline)

    def test_coordinate_dimensioning_still_excludes_b_spline(self):
        with self.assertRaisesRegex(ValidationError, "Coordinate dimensioning supports"):
            SketchOp(
                op="sketch",
                label="profile",
                dimensioning="coordinates",
                entities=[
                    {
                        "type": "b_spline",
                        "name": "arc",
                        "degree": 2,
                        "control_points": [[0, 0], [10, 0], [10, 10]],
                    }
                ],
            )


class BSplinePreflightTests(unittest.TestCase):
    def test_clamped_endpoints_close_with_two_lines(self):
        entities = [
            {
                "type": "b_spline",
                "name": "top",
                "degree": 3,
                "control_points": [[0, 0], [10, 8], [30, 9], [45, 2], [50, 0]],
                "knots": [0, 0, 0, 0, 0.5, 1, 1, 1, 1],
            },
            {"type": "line", "name": "right", "start": [50, 0], "end": [50, 20]},
            {"type": "line", "name": "left", "start": [50, 20], "end": [0, 0]},
        ]
        result = closed_profile(entities)
        self.assertEqual(result["closed_contour_count"], 1)


if __name__ == "__main__":
    unittest.main()
