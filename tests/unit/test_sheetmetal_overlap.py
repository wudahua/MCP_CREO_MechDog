"""DEV-051 T04 / BUG-046 offline contract: overlapping solid add on sheetmetal.

Three-way comparison on the confirmed thin base plate 185 x 232 x 1 mm
(volume 42 920 mm3, DEV-051 T03): solid-part add, sheetmetal add and
sheetmetal cut share one rectangle, one spatial position and one overlap
volume; only the base model kind and the extrude mode differ.

The overlap prism is a 10 x 10 x 5 mm block centred on the sketch plane
("symmetric" sweeps 2.5 mm to each side), so it spans the full 1 mm plate
thickness under every plausible Z placement of the first wall and the overlap
stays 10 x 10 x 1 = 100 mm3. Expected volumes come from the independent box
oracle defined here, never from production code.

The original BUG-046 evidence (bare ProFeatureWithoptionsCreate -1 and its
inputs) is carried as constants and cross-checked against the archived
reports. Offline only: no MCP client is instantiated and no Toolkit
connection is made.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

from creo_mechdog.schema import validate_operations

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- confirmed thin base plate (DEV-051 T03, 185 x 232 x 1 mm) --------------
BASE_LENGTH_MM = 185.0
BASE_WIDTH_MM = 232.0
BASE_THICKNESS_MM = 1.0
BASE_VOLUME_MM3 = 42_920.0

# --- shared overlap prism (identical rectangle/position/overlap per route) --
OVERLAP_MIN = [20.0, 20.0]
OVERLAP_MAX = [30.0, 30.0]
# The XZ wall base occupies y = -232 ... 0, so the same block sits at y = -30 ... -20
# over that plate instead of y = 20 ... 30.
SHEETMETAL_OVERLAP_MIN = [20.0, -30.0]
SHEETMETAL_OVERLAP_MAX = [30.0, -20.0]
PRISM_SIDE_MM = 10.0
# direction "symmetric" sweeps depth to both sides (DEV-049 tilted cut matrix
# measures exactly twice the one-sided volume for the same depth value).
PRISM_HALF_DEPTH_MM = 2.5
PRISM_VOLUME_MM3 = 500.0
OVERLAP_VOLUME_MM3 = 100.0
ROUTE_ADD_VOLUME_MM3 = 43_320.0
ROUTE_CUT_VOLUME_MM3 = 42_820.0

# --- original BUG-046 evidence (0.3.1 S1 / 0.3.2 A S1), preserved ----------
ORIGINAL_ADD_JOBS = (
    "9256690b7e13417b9bc9c90e45630fe8",
    "4b0c0d9b738a4373ba292afe4a65034c",
)
ORIGINAL_CUT_JOB = "4601aa39ac6149bf93a04d453eb5186d"
ORIGINAL_ADD_MODEL = "56d4cdae6b7242929d7180949905ef1a"
ORIGINAL_REPRO_MODEL = "acc_test_sm2"
ORIGINAL_ADD_ERROR = "Toolkit call ProFeatureWithoptionsCreate failed with code -1"
ORIGINAL_TOOLKIT_CODE = -1


# --- fixtures: one source for the three routes ----------------------------


def overlap_sketch() -> dict:
    return {
        "op": "sketch",
        "label": "overlap_sketch",
        "plane": "XY",
        "entities": [
            {
                "type": "rectangle",
                "name": "overlap_box",
                "min": list(OVERLAP_MIN),
                "max": list(OVERLAP_MAX),
            }
        ],
    }


def sheetmetal_overlap_sketch() -> dict:
    """Same 10 x 10 block over the XZ wall base, which lies in y = -232 ... 0.

    The wall is built from an XZ line extruded 232 mm in -Y with a 1 mm thickness
    centred on z = 0: live inspection of the base (2026-10-29) measured the body
    bbox as x 0..185, y -232..0, z -0.5..0.5. A block at the solid-route position
    (y 20..30) would be disjoint from that sheet, so the footprint keeps the same
    10 x 10 size and moves into the plate while the prism stays over z = 0.
    """
    sketch = overlap_sketch()
    sketch["label"] = "sheetmetal_overlap_sketch"
    sketch["entities"][0]["min"] = list(SHEETMETAL_OVERLAP_MIN)
    sketch["entities"][0]["max"] = list(SHEETMETAL_OVERLAP_MAX)
    return sketch


def prism_op(mode: str, label: str, **overrides) -> dict:
    operation = {
        "op": "extrude",
        "label": label,
        "sketch": "overlap_sketch",
        "depth": PRISM_HALF_DEPTH_MM,
        "mode": mode,
        "direction": "symmetric",
        "depth_type": "blind",
    }
    operation.update(overrides)
    return operation


def solid_plate_sketch() -> dict:
    return {
        "op": "sketch",
        "label": "plate_sketch",
        "plane": "XY",
        "entities": [
            {
                "type": "rectangle",
                "name": "plate_box",
                "min": [0.0, 0.0],
                "max": [BASE_LENGTH_MM, BASE_WIDTH_MM],
            }
        ],
    }


def solid_base_op() -> dict:
    return {
        "op": "extrude",
        "label": "base_plate",
        "sketch": "plate_sketch",
        "depth": BASE_THICKNESS_MM,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    }


def wall_sketch() -> dict:
    # DEV-051 T04: the sketch plane decides where the sheet thickness lives. XZ keeps
    # the 1 mm thin width in Z and the 232 mm extrusion in Y, so the base is a genuine
    # 1 mm sheet (see test_sheetmetal_flange.wall_base_op for the measured evidence).
    return {
        "op": "sketch",
        "label": "wall_sketch",
        "plane": "XZ",
        "entities": [
            {
                "type": "line",
                "name": "wall_line",
                "start": [0.0, 0.0],
                "end": [BASE_LENGTH_MM, 0.0],
            }
        ],
    }


def wall_base_op(sketch: str = "wall_sketch") -> dict:
    # "thickness" is the sheet metal thickness (PRO_E_STD_SMT_THICKNESS) and "depth" is
    # the extrusion, so a 185 x 232 x 1 sheet is depth=232 / thickness=1.
    return {
        "op": "sheetmetal_wall",
        "label": "base_wall",
        "sketch": sketch,
        "depth": BASE_WIDTH_MM,
        "thickness": BASE_THICKNESS_MM,
        "direction": "positive",
    }


def route_solid_add() -> list[dict]:
    return [solid_plate_sketch(), solid_base_op(), overlap_sketch(), prism_op("add", "boss_add")]


def route_sheetmetal_add() -> list[dict]:
    return [
        wall_sketch(),
        wall_base_op(),
        sheetmetal_overlap_sketch(),
        prism_op("add", "boss_add", sketch="sheetmetal_overlap_sketch"),
    ]


def route_sheetmetal_cut() -> list[dict]:
    return [
        wall_sketch(),
        wall_base_op(),
        sheetmetal_overlap_sketch(),
        prism_op("cut", "pocket_cut", sketch="sheetmetal_overlap_sketch"),
    ]


ROUTES = (
    ("solid_add", route_solid_add),
    ("sheetmetal_add", route_sheetmetal_add),
    ("sheetmetal_cut", route_sheetmetal_cut),
)


# --- independent box oracle ----------------------------------------------


def prism_volume_mm3() -> float:
    return PRISM_SIDE_MM * PRISM_SIDE_MM * (2.0 * PRISM_HALF_DEPTH_MM)


def overlap_volume_mm3() -> float:
    # The straddling block crosses the whole plate thickness at any Z placement.
    return PRISM_SIDE_MM * PRISM_SIDE_MM * BASE_THICKNESS_MM


def archived_reports_containing(token: str) -> list[str]:
    root = REPO_ROOT / "docs" / "validation"
    return [
        str(path.relative_to(REPO_ROOT))
        for path in sorted(root.rglob("*.md"))
        if token.encode("ascii") in path.read_bytes()
    ]


class ThreeWayInputContractTest(unittest.TestCase):
    """One rectangle, one position, one overlap volume across the three routes."""

    def test_routes_share_rectangle_position_and_prism(self) -> None:
        sides = [
            [
                hi - lo
                for lo, hi in zip(
                    route()[2]["entities"][0]["min"], route()[2]["entities"][0]["max"]
                )
            ]
            for _, route in ROUTES
        ]
        for side in sides:
            self.assertEqual(side, [PRISM_SIDE_MM, PRISM_SIDE_MM])
        prisms = [route()[3] for _, route in ROUTES]
        for prism in prisms:
            self.assertEqual(prism["depth"], PRISM_HALF_DEPTH_MM)
            self.assertEqual(prism["direction"], "symmetric")
        # The sheetmetal routes place the same block over the XZ wall base (y -232..0);
        # the prism label follows that sketch so nothing references a missing label.
        self.assertEqual([prism["sketch"] for prism in prisms][0], "overlap_sketch")
        self.assertEqual(
            [prism["sketch"] for prism in prisms][1:], ["sheetmetal_overlap_sketch"] * 2
        )
        self.assertEqual([prism["mode"] for prism in prisms], ["add", "add", "cut"])

    def test_routes_are_accepted_with_parameters_preserved(self) -> None:
        for name, route in ROUTES:
            validated = validate_operations(route())
            prism = validated[-1]
            self.assertEqual(prism["mode"], route()[-1]["mode"], name)
            self.assertEqual(prism["depth"], PRISM_HALF_DEPTH_MM, name)
            self.assertEqual(prism["direction"], "symmetric", name)
            self.assertEqual(prism["sketch"], route()[-1]["sketch"], name)

    def test_add_routes_volume_oracle(self) -> None:
        self.assertAlmostEqual(prism_volume_mm3(), PRISM_VOLUME_MM3)
        self.assertAlmostEqual(overlap_volume_mm3(), OVERLAP_VOLUME_MM3)
        self.assertAlmostEqual(
            BASE_VOLUME_MM3 + prism_volume_mm3() - overlap_volume_mm3(),
            ROUTE_ADD_VOLUME_MM3,
        )

    def test_cut_route_volume_oracle(self) -> None:
        self.assertAlmostEqual(
            BASE_VOLUME_MM3 - overlap_volume_mm3(),
            ROUTE_CUT_VOLUME_MM3,
        )

    def test_base_plate_matches_confirmed_thin_plate(self) -> None:
        self.assertAlmostEqual(
            BASE_LENGTH_MM * BASE_WIDTH_MM * BASE_THICKNESS_MM,
            BASE_VOLUME_MM3,
        )
        validated = validate_operations([wall_sketch(), wall_base_op()])
        # The sheet thickness must be the 1 mm axis and the extrusion must be the
        # 232 mm one; swapping them keeps the volume and the bbox but types the part
        # as a 232 mm sheet, which no flange can bend.
        self.assertEqual(validated[0]["plane"], "XZ")
        self.assertEqual(validated[1]["thickness"], BASE_THICKNESS_MM)
        self.assertEqual(validated[1]["depth"], BASE_WIDTH_MM)

    def test_overlap_footprint_is_inside_plate_footprint(self) -> None:
        for lo in OVERLAP_MIN:
            self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(OVERLAP_MAX[0], BASE_LENGTH_MM)
        self.assertLessEqual(OVERLAP_MAX[1], BASE_WIDTH_MM)
        side = [hi - lo for lo, hi in zip(OVERLAP_MIN, OVERLAP_MAX)]
        self.assertEqual(side, [PRISM_SIDE_MM, PRISM_SIDE_MM])

    def test_sheetmetal_footprint_is_inside_measured_wall_bbox(self) -> None:
        # Live inspection of the XZ wall base (2026-10-29): x 0..185, y -232..0,
        # z -0.5..0.5. The block must fall inside the sheet, not next to it.
        measured = {"x": (0.0, 185.0), "y": (-232.0, 0.0), "z": (-0.5, 0.5)}
        for axis, lo in zip("xy", SHEETMETAL_OVERLAP_MIN):
            self.assertGreaterEqual(lo, measured[axis][0], axis)
        for axis, hi in zip("xy", SHEETMETAL_OVERLAP_MAX):
            self.assertLessEqual(hi, measured[axis][1], axis)
        self.assertEqual(
            [hi - lo for lo, hi in zip(SHEETMETAL_OVERLAP_MIN, SHEETMETAL_OVERLAP_MAX)],
            [PRISM_SIDE_MM, PRISM_SIDE_MM],
        )
        # "symmetric" halves the requested depth per side, so the offline 2.5 mm gives
        # a 2.5 mm tall block that still spans the whole 1 mm sheet thickness.
        self.assertGreaterEqual(PRISM_HALF_DEPTH_MM, BASE_THICKNESS_MM)
        self.assertLessEqual(-PRISM_HALF_DEPTH_MM, measured["z"][0])
        self.assertGreaterEqual(PRISM_HALF_DEPTH_MM, measured["z"][1])

    def test_overlap_volume_is_fixed_across_plate_z_placements(self) -> None:
        block = (-PRISM_HALF_DEPTH_MM, PRISM_HALF_DEPTH_MM)
        for low in (-1.0, -0.5, 0.0, 0.7):
            plate = (low, low + BASE_THICKNESS_MM)
            crossed = max(0.0, min(plate[1], block[1]) - max(plate[0], block[0]))
            self.assertAlmostEqual(crossed, BASE_THICKNESS_MM, msg=f"plate z={plate}")
            self.assertAlmostEqual(
                PRISM_SIDE_MM * PRISM_SIDE_MM * crossed,
                OVERLAP_VOLUME_MM3,
            )

    def test_standalone_prism_payloads_share_admission(self) -> None:
        for mode, label in (("add", "boss_add"), ("cut", "pocket_cut")):
            validated = validate_operations([prism_op(mode, label)])
            self.assertEqual(validated[0]["mode"], mode)


class UnsupportedCombinationTest(unittest.TestCase):
    """Combinations the contract rejects before any modelling happens."""

    def assert_rejected(self, operations: list[dict], reason: str) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_operations(operations)
        self.assertIn(reason, str(ctx.exception))

    def test_through_all_add_is_rejected(self) -> None:
        self.assert_rejected(
            [overlap_sketch(), prism_op("add", "boss_add", depth_type="through_all")],
            "through_all is supported for cuts",
        )

    def test_through_all_surface_is_rejected(self) -> None:
        self.assert_rejected(
            [overlap_sketch(), prism_op("surface", "surf_extrude", depth_type="through_all")],
            "through_all is supported for cuts",
        )

    def test_degenerate_overlap_rectangle_is_rejected(self) -> None:
        broken = overlap_sketch()
        broken["entities"][0]["max"] = list(OVERLAP_MIN)
        self.assert_rejected(
            [broken, prism_op("add", "boss_add")],
            "Rectangle max must exceed min",
        )

    def test_nonpositive_prism_depth_is_rejected(self) -> None:
        self.assert_rejected(
            [overlap_sketch(), prism_op("add", "boss_add", depth=0.0)],
            "greater than 0",
        )

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_operations([overlap_sketch(), prism_op("weld", "boss_add")])

    def test_unknown_direction_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_operations([overlap_sketch(), prism_op("add", "boss_add", direction="up")])


class ContractRegressionTest(unittest.TestCase):
    """T03 first-wall contract is consumed by the sheetmetal routes; no rollback."""

    def test_first_wall_closed_rectangle_still_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_operations([solid_plate_sketch(), wall_base_op("plate_sketch")])
        self.assertIn("exactly one open straight line", str(ctx.exception))

    def test_first_wall_open_line_still_accepted(self) -> None:
        validated = validate_operations([wall_sketch(), wall_base_op()])
        self.assertEqual(validated[1]["op"], "sheetmetal_wall")


class OriginalEvidenceTest(unittest.TestCase):
    """The original bare -1 and its inputs stay attached to the fixture."""

    def test_minus_one_evidence_block_is_complete(self) -> None:
        self.assertEqual(ORIGINAL_TOOLKIT_CODE, -1)
        self.assertIn("ProFeatureWithoptionsCreate failed with code -1", ORIGINAL_ADD_ERROR)
        for job in (*ORIGINAL_ADD_JOBS, ORIGINAL_CUT_JOB):
            self.assertRegex(job, r"^[0-9a-f]{32}$")

    def test_evidence_ids_appear_in_archived_reports(self) -> None:
        for token in (
            *ORIGINAL_ADD_JOBS,
            ORIGINAL_CUT_JOB,
            ORIGINAL_ADD_MODEL,
            ORIGINAL_REPRO_MODEL,
        ):
            self.assertTrue(archived_reports_containing(token), token)


if __name__ == "__main__":
    unittest.main()
