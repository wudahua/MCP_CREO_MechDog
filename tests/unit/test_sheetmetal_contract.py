"""DEV-051 T03 / BUG-032 offline contract for the sheetmetal first wall.

The matrix fixes the frame (one 185 mm straight line on the X axis of a datum
plane, positive direction) and only varies depth/thickness, so a difference can
never be explained by a coordinate-system change. Expected volumes and bounding
boxes are derived here from the declared contract, never from production code:

    volume = line length x thickness x depth

where thickness is the in-plane thin width and depth is the extrusion along the
sketch normal. Admission cases cover the standalone tool payload and the
same-plan execute_plan path, which share validate_operations. Offline only: no
MCP client is instantiated and no Toolkit connection is made.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from creo_mechdog.schema import validate_operations
from creo_mechdog.sheetmetal import first_wall_section_problem

LINE_LENGTH_MM = 185.0
# (depth, thickness) with the reported open-line matrix.
MATRIX = ((1.0, 232.0), (232.0, 1.0), (1.0, 1.0), (2.0, 1.0), (0.5, 1.0))
# BUG-032 0.3.2 report: sheetmetal_wall(depth=1.0, thickness=232.0) on a 185 line.
REPORTED_VOLUME_MM3 = 9_957_440.0


def wall_sketch(length: float = LINE_LENGTH_MM, **entity_overrides) -> dict:
    line = {"type": "line", "name": "wall_line", "start": [0.0, 0.0], "end": [length, 0.0]}
    line.update(entity_overrides)
    return {"op": "sketch", "label": "s1", "plane": "XY", "entities": [line]}


def wall_op(depth: float, thickness: float, sketch: object = "s1", **overrides) -> dict:
    operation = {
        "op": "sheetmetal_wall",
        "label": "wall1",
        "sketch": sketch,
        "depth": depth,
        "thickness": thickness,
    }
    operation.update(overrides)
    return operation


def oracle_volume(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> float:
    return length * thickness * depth


def oracle_extents(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> list[float]:
    return sorted((length, thickness, depth))


class SheetmetalWallMatrixTest(unittest.TestCase):
    """depth/thickness matrix on one fixed frame."""

    def test_matrix_is_accepted_without_rewriting_parameters(self) -> None:
        for depth, thickness in MATRIX:
            with self.subTest(depth=depth, thickness=thickness):
                validated = validate_operations([wall_sketch(), wall_op(depth, thickness)])
                operation = validated[1]
                # Neither value may be swapped, clamped or replaced on the way in.
                self.assertEqual(operation["depth"], depth)
                self.assertEqual(operation["thickness"], thickness)
                self.assertEqual(operation["direction"], "positive")
                self.assertEqual(validated[0]["entities"][0]["end"], [LINE_LENGTH_MM, 0.0])

    def test_matrix_volume_and_three_axis_extents(self) -> None:
        for depth, thickness in MATRIX:
            with self.subTest(depth=depth, thickness=thickness):
                volume = oracle_volume(depth, thickness)
                self.assertAlmostEqual(volume, LINE_LENGTH_MM * thickness * depth, places=9)
                self.assertEqual(
                    oracle_extents(depth, thickness),
                    sorted([LINE_LENGTH_MM, thickness, depth]),
                )
        # 185 x 232 x 1 keeps one volume for both parameter orders.
        self.assertAlmostEqual(oracle_volume(1.0, 232.0), 42_920.0, places=9)
        self.assertAlmostEqual(oracle_volume(232.0, 1.0), 42_920.0, places=9)

    def test_reported_volume_means_depth_was_replaced_by_thickness(self) -> None:
        # 185 x 232 x 232 = 9957440: the thin width and the thickness axis were
        # both 232, i.e. the conversion re-thickened the wall from the
        # depth-normal 185 x 232 face instead of keeping depth 1.
        self.assertAlmostEqual(LINE_LENGTH_MM * 232.0 * 232.0, REPORTED_VOLUME_MM3, places=6)
        intended = oracle_volume(1.0, 232.0)
        self.assertAlmostEqual(intended, 42_920.0, places=9)
        self.assertAlmostEqual(REPORTED_VOLUME_MM3 / intended, 232.0, places=9)


class SheetmetalWallAdmissionTest(unittest.TestCase):
    """Only one open straight line can drive the first wall."""

    def assert_rejected(self, entities: list[dict], reason: str) -> None:
        # Plan-level admission raises ValueError, like the other cross-operation
        # checks in validate_operations; the pydantic field errors stay separate.
        with self.assertRaises(ValueError) as failure:
            validate_operations(
                [
                    {"op": "sketch", "label": "s1", "plane": "XY", "entities": entities},
                    wall_op(1.0, 1.0),
                ]
            )
        self.assertIn(reason, str(failure.exception))
        self.assertIn("operations[1]", str(failure.exception))

    def test_closed_rectangle_is_rejected(self) -> None:
        self.assert_rejected(
            [{"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [40.0, 7.0]}],
            "exactly one open straight line",
        )

    def test_closed_polyline_is_rejected(self) -> None:
        self.assert_rejected(
            [
                {
                    "type": "polyline",
                    "name": "outline",
                    "points": [[0.0, 0.0], [40.0, 0.0], [40.0, 7.0], [0.0, 7.0]],
                    "closed": True,
                }
            ],
            "exactly one open straight line",
        )

    def test_arc_is_rejected(self) -> None:
        self.assert_rejected(
            [
                {
                    "type": "arc",
                    "name": "bend",
                    "center": [0.0, 0.0],
                    "radius": 20.0,
                    "start_angle": 0.0,
                    "end_angle": 90.0,
                }
            ],
            "exactly one open straight line",
        )

    def test_two_line_chain_is_rejected(self) -> None:
        self.assert_rejected(
            [
                {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [90.0, 0.0]},
                {"type": "line", "name": "l2", "start": [90.0, 0.0], "end": [185.0, 0.0]},
            ],
            "got 2 drawing entities",
        )

    def test_centerline_alone_is_not_a_profile(self) -> None:
        self.assert_rejected(
            [{"type": "centerline", "name": "axis", "start": [0.0, 0.0], "end": [185.0, 0.0]}],
            "got 0 drawing entities",
        )

    def test_construction_line_alone_is_not_a_profile(self) -> None:
        self.assert_rejected(
            [
                {
                    "type": "line",
                    "name": "guide",
                    "start": [0.0, 0.0],
                    "end": [185.0, 0.0],
                    "construction": True,
                }
            ],
            "got 0 drawing entities",
        )

    def test_centerline_with_one_line_is_accepted(self) -> None:
        validated = validate_operations(
            [
                {
                    "op": "sketch",
                    "label": "s1",
                    "plane": "XY",
                    "entities": [
                        {
                            "type": "centerline",
                            "name": "axis",
                            "start": [0.0, 0.0],
                            "end": [185.0, 0.0],
                        },
                        {
                            "type": "line",
                            "name": "wall_line",
                            "start": [0.0, 5.0],
                            "end": [185.0, 5.0],
                        },
                    ],
                },
                wall_op(1.0, 2.0),
            ]
        )
        self.assertEqual(validated[1]["op"], "sheetmetal_wall")

    def test_cross_job_sketch_is_left_to_the_native_check(self) -> None:
        # Python cannot see a section created by an earlier job; the native
        # operation applies the same rule for both dispatch paths.
        for sketch in (48, "wall_line_earlier"):
            with self.subTest(sketch=sketch):
                validated = validate_operations([wall_op(1.0, 232.0, sketch=sketch)])
                self.assertEqual(validated[0]["sketch"], sketch)
                self.assertEqual(validated[0]["depth"], 1.0)
                self.assertEqual(validated[0]["thickness"], 232.0)

    def test_standalone_tool_payload_is_accepted(self) -> None:
        # Exactly the dictionary creo_sheetmetal_wall submits.
        payload = {
            "op": "sheetmetal_wall",
            "label": "wall1",
            "sketch": 12,
            "depth": 1.0,
            "thickness": 232.0,
            "direction": "positive",
        }
        validated = validate_operations([payload])[0]
        self.assertEqual(validated, payload)

    def test_parameters_must_be_positive_and_bounded(self) -> None:
        for depth, thickness in ((0.0, 1.0), (-1.0, 1.0), (1.0, 0.0), (1.0, -2.0), (1.0, 100001.0)):
            with self.subTest(depth=depth, thickness=thickness):
                with self.assertRaises(ValidationError):
                    validate_operations([wall_op(depth, thickness)])

    def test_unknown_direction_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_operations([wall_op(1.0, 1.0, direction="symmetric")])


class SheetmetalWallLegacyTest(unittest.TestCase):
    """The previously accepted open-line wall keeps its input and geometry."""

    def test_legacy_open_line_40_by_1_by_30(self) -> None:
        validated = validate_operations(
            [
                {
                    "op": "sketch",
                    "label": "s1",
                    "plane": "XY",
                    "entities": [
                        {
                            "type": "line",
                            "name": "wall_line",
                            "start": [0.0, 0.0],
                            "end": [40.0, 0.0],
                        }
                    ],
                },
                wall_op(30.0, 1.0),
            ]
        )
        self.assertEqual(validated[1]["depth"], 30.0)
        self.assertEqual(validated[1]["thickness"], 1.0)
        self.assertAlmostEqual(oracle_volume(30.0, 1.0, 40.0), 1200.0, places=9)

    def test_negative_direction_is_preserved(self) -> None:
        validated = validate_operations(
            [wall_sketch(length=232.0), wall_op(185.0, 1.0, direction="negative")]
        )
        self.assertEqual(validated[1]["direction"], "negative")
        self.assertAlmostEqual(oracle_volume(185.0, 1.0, 232.0), 42_920.0, places=9)


class FirstWallSectionPredicateTest(unittest.TestCase):
    """The shared predicate used by plan admission and documented for the tool."""

    def test_single_open_line_is_supported(self) -> None:
        self.assertIsNone(
            first_wall_section_problem(
                [{"type": "line", "name": "wall_line", "start": [0.0, 0.0], "end": [185.0, 0.0]}]
            )
        )

    def test_other_sections_report_the_supported_form(self) -> None:
        cases = (
            [{"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [1.0, 1.0]}],
            [{"type": "circle", "name": "ring", "center": [0.0, 0.0], "radius": 5.0}],
            [{"type": "centerline", "name": "axis", "start": [0.0, 0.0], "end": [1.0, 0.0]}],
            [],
        )
        for entities in cases:
            with self.subTest(entities=entities):
                problem = first_wall_section_problem(entities)
                self.assertIsNotNone(problem)
                self.assertIn("exactly one open straight line", problem)


if __name__ == "__main__":
    unittest.main()
