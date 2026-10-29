"""Offline guards for tools/test_flange_direction.py (DEV-051 T05/T11).

The driver answers one question - does a flange become a 90 degree bend - and the
judgement must stay bbox-only, because 232 x 80 x 1 = 18 560 mm3 is the same volume for
a real bend and for the coplanar extension the 2026-10-29 third round produced.
"""

from __future__ import annotations

import unittest

from tools import test_flange_direction as probe

PLATE = ((0.0, 0.0, 0.0), (185.0, 232.0, 1.0))


class NativeSectionTest(unittest.TestCase):
    def test_section_matches_the_stock_shape_structure(self) -> None:
        section = probe.native_section()
        self.assertTrue(section["leg_on_sketch_normal"])
        self.assertTrue(section["centerline_removed"])
        self.assertEqual(section["profile_entity_count"], 1)
        self.assertTrue(section["height_type_none"])


class VerdictTest(unittest.TestCase):
    def test_z_growth_of_the_full_height_is_a_bend(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, 0.0), (187.54, 232.0, 81.0)), 80.0)
        self.assertTrue(judged["bent"])
        self.assertEqual(judged["direction"], "up")

    def test_coplanar_extension_is_not_a_bend(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, 0.0), (265.0, 232.0, 1.0)), 80.0)
        self.assertFalse(judged["bent"])
        self.assertEqual(judged["direction"], "in_plane")

    def test_downward_flange_is_a_bend_but_not_an_up_flange(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, -81.0), (187.54, 232.0, 1.0)), 80.0)
        self.assertTrue(judged["bent"])
        self.assertEqual(judged["direction"], "down")


class PlanTest(unittest.TestCase):
    def test_one_variable_per_case(self) -> None:
        cases = probe.plan()
        self.assertEqual([case["flip"] for case in cases], [False, True])
        self.assertEqual(len({case["case"] for case in cases}), len(cases))

    def test_hang_budget_is_three_minutes(self) -> None:
        self.assertEqual(probe.HANG_BUDGET_SECONDS, 180.0)


if __name__ == "__main__":
    unittest.main()
