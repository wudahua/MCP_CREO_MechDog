"""Offline guards for tools/test_flange_direction.py (DEV-051 T05/T11).

The driver answers two questions - does a flange become a 90 degree bend, and does the
direction option really pick the side - and the judgement must stay bbox-only, because
232 x 80 x 1 = 18 560 mm3 is the same volume for a real bend and for the coplanar
extension the 2026-10-29 third round produced.
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

    def test_direction_switch_is_the_section_side(self) -> None:
        section = probe.native_section()
        self.assertTrue(section["section_side_flip_is_the_switch"])
        self.assertTrue(section["traj_normal_not_the_switch"])


class VerdictTest(unittest.TestCase):
    def test_z_growth_of_the_full_height_is_a_bend(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, 0.0), (187.54, 232.0, 81.0)), 80.0, "up")
        self.assertTrue(judged["bent"])
        self.assertEqual(judged["direction"], "up")
        self.assertTrue(judged["direction_matches"])

    def test_coplanar_extension_is_not_a_bend(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, 0.0), (265.0, 232.0, 1.0)), 80.0, "up")
        self.assertFalse(judged["bent"])
        self.assertEqual(judged["direction"], "in_plane")

    def test_downward_flange_is_a_bend_on_the_other_side(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, -81.0), (187.54, 232.0, 1.0)), 80.0, "down")
        self.assertTrue(judged["bent"])
        self.assertEqual(judged["direction"], "down")
        self.assertTrue(judged["direction_matches"])

    def test_a_side_that_did_not_change_fails_the_expectation(self) -> None:
        """The pre-fix defect: both flip values produced the same downward wall."""
        judged = probe.verdict(PLATE, ((0.0, 0.0, -81.0), (187.54, 232.0, 1.0)), 80.0, "up")
        self.assertTrue(judged["bent"])
        self.assertFalse(judged["direction_matches"])


class PlanTest(unittest.TestCase):
    def test_one_variable_per_case_with_an_explicit_side(self) -> None:
        cases = probe.plan()
        self.assertEqual([case["flip"] for case in cases], [False, True])
        self.assertEqual([case["expected_direction"] for case in cases], ["up", "down"])
        self.assertEqual(len({case["case"] for case in cases}), len(cases))

    def test_hang_budget_is_three_minutes(self) -> None:
        self.assertEqual(probe.HANG_BUDGET_SECONDS, 180.0)


if __name__ == "__main__":
    unittest.main()
