"""Offline contract checks for the single native custom-hole path."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
BASE = {
    "op": "hole",
    "label": "hole_one",
    "placement": {"kind": "surface", "id": 1},
    "reference1": {"kind": "datum_plane", "id": 2},
    "reference2": {"kind": "datum_plane", "id": 3},
    "diameter": 6,
}


def oracle_removed(diameter: float, depth: float, option: dict) -> float:
    """Flat-bottom analytical reference for a fully embedded hole in a plate."""
    base = math.pi * diameter**2 * depth / 4
    if "counterbore" in option:
        bore = option["counterbore"]
        return base + math.pi * (bore["diameter"] ** 2 - diameter**2) * bore["depth"] / 4
    sink = option["countersink"]
    height = (sink["diameter"] - diameter) / (2 * math.tan(math.radians(sink["angle"] / 2)))
    outer = (
        math.pi * height * (sink["diameter"] ** 2 + sink["diameter"] * diameter + diameter**2) / 12
    )
    return base + outer - math.pi * diameter**2 * height / 4


class NativeCountersinkTest(unittest.TestCase):
    def test_old_hole_payload_is_unchanged(self):
        self.assertEqual(
            validate_operations([BASE])[0], {**BASE, "offset1": 0, "offset2": 0, "flip": False}
        )

    def test_each_option_and_plan(self):
        for option in (
            {"counterbore": {"diameter": 10, "depth": 2}},
            {"countersink": {"diameter": 10, "angle": 90}},
        ):
            with self.subTest(option=option):
                op = validate_operations([{**BASE, "depth": 12, **option}])[0]
                self.assertEqual(op[next(iter(option))], next(iter(option.values())))
                self.assertGreater(oracle_removed(6, 12, option), math.pi * 6**2 * 12 / 4)

    def test_invalid_combinations(self):
        cases = [
            {
                "counterbore": {"diameter": 10, "depth": 2},
                "countersink": {"diameter": 10, "angle": 90},
            },
            {"counterbore": {"diameter": 6, "depth": 2}},
            {"counterbore": {"diameter": 10, "depth": 12}, "depth": 12},
            {"countersink": {"diameter": 6, "angle": 90}},
            {"countersink": {"diameter": 10, "angle": 0}},
            {"countersink": {"diameter": 10, "angle": 180}},
            {"countersink": {"diameter": 10, "angle": 10}, "depth": 2},
        ]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_operations([{**BASE, **extra}])

    def test_native_tree_is_one_hole_and_old_branch_remains(self):
        source = (ROOT / "native/generic.cpp").read_text(encoding="utf-8")
        start = source.index("static J generic_hole(")
        end = source.index("static J ", start + 1)
        body = source[start:end]
        self.assertEqual(body.count("PRO_FEAT_HOLE"), 1)
        self.assertIn("PRO_HLE_CUSTOM_TYPE", body)
        self.assertIn("PRO_HLE_NEW_TYPE_STRAIGHT", body)
        for name in (
            "PRO_E_HLE_ADD_CBORE",
            "PRO_E_HLE_ADD_CSINK",
            "PRO_E_HLE_CBOREDIAM",
            "PRO_E_HLE_CBOREDEPTH",
            "PRO_E_HLE_CSINKDIAM",
            "PRO_E_HLE_CSINKANGLE",
            "PRO_E_HLE_DRILLDEPTH",
            "PRO_E_HLE_DEPTH",
        ):
            self.assertIn(name, body)
        self.assertEqual(body.count("ProFeature f = create(root)"), 1)


if __name__ == "__main__":
    unittest.main()
