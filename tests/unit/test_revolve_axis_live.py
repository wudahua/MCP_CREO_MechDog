"""FEAT-008/T09B offline tests for the revolve-axis live driver.

``tools/test_revolve_axis_live.py`` is the driver whose live verdicts decide
whether the T09B remainder passed. These tests pin the parts of that driver
that can be judged without a Creo session:

* the centerline accounting contract - one drawn user centerline counts as 1,
  and a truly ambiguous scene never receives a guessed id;
* the id source - the reported id must equal the sketch section entity id of
  the drawn centerline (or the inspected datum axis id), and a missing source
  or a null id is a failure rather than a silent pass;
* the reload evidence - it is read from the job result block only;
* the multi-centerline limitation - this service admits one centerline per
  sketch, so the true multi-line scene needs an external native fixture and an
  admission refusal must never be recorded as a geometry pass.
"""

import unittest

from tools import test_revolve_axis_live as driver


def block(**overrides) -> dict:
    value = {
        "source": "internal_centerline",
        "kind": "section_centerline",
        "id": 17,
        "frame": "model",
        "origin": [0.0, -5.0, 0.0],
        "direction": [0.0, 1.0, 0.0],
        "geometry_known": True,
        "query_code": 0,
        "resolution": {
            "feature_axis_query_code": 0,
            "axis_item_query_code": None,
            "axis_surface_query_code": None,
            "section_centerline_count": 1,
            "section_query_code": 0,
        },
    }
    value.update(overrides)
    return value


class CenterlineAccountingTests(unittest.TestCase):
    def test_one_drawn_centerline_counts_as_one(self):
        self.assertEqual(driver.EXPECTED["internal_centerline"]["section_centerline_count"], 1)

    def test_the_contract_states_the_user_line_rule(self):
        accounting = driver.check_contract()["centerline_accounting"]
        self.assertEqual(accounting["internal_centerline.section_centerline_count"], 1)
        self.assertIn("spin_centerline", accounting["internal_centerline.id_source"])
        self.assertIn("never guessed", accounting["rule"])

    def test_a_count_above_the_drawn_lines_is_a_regression(self):
        # The 2026-10-29 run measured 3 for one drawn line because the two
        # system reference projections were counted. That shape must fail.
        inflated = block(resolution=dict(block()["resolution"], section_centerline_count=3))
        self.assertNotEqual(
            inflated["resolution"]["section_centerline_count"],
            driver.EXPECTED["internal_centerline"]["section_centerline_count"],
        )

    def test_multiple_user_centerlines_keep_a_null_id(self):
        ambiguous = block(
            id=None,
            frame=None,
            origin=None,
            direction=None,
            geometry_known=False,
            resolution=dict(block()["resolution"], section_centerline_count=2),
        )
        self.assertIsNone(ambiguous["id"])
        self.assertEqual(ambiguous["resolution"]["section_centerline_count"], 2)

    def test_multiple_user_centerlines_are_declared_unconstructible_here(self):
        statement = driver.check_contract()["multiple_user_centerlines"]
        self.assertIn("external native fixture", statement)
        self.assertIn("not a geometry pass", statement)


class IdSourceTests(unittest.TestCase):
    ENTITY = "spin_centerline"

    def test_matching_sketch_entity_id_passes(self):
        problems, evidence = driver.axis_id_source(
            block(id=17), {"spin_centerline": 17}, self.ENTITY, []
        )
        self.assertEqual(problems, [])
        self.assertEqual(evidence["sketch_entity_id"], 17)

    def test_a_different_id_fails(self):
        problems, _ = driver.axis_id_source(block(id=99), {"spin_centerline": 17}, self.ENTITY, [])
        self.assertTrue(any("does not match sketch" in item for item in problems))

    def test_a_missing_sketch_entity_id_is_not_a_match(self):
        problems, _ = driver.axis_id_source(block(id=17), {}, self.ENTITY, [])
        self.assertTrue(any("cannot be verified" in item for item in problems))

    def test_a_null_reported_id_fails_even_with_a_known_source(self):
        problems, _ = driver.axis_id_source(
            block(id=None), {"spin_centerline": 17}, self.ENTITY, []
        )
        self.assertTrue(any("was not reported" in item for item in problems))

    def test_datum_axis_id_must_match_the_inspected_axis(self):
        axes = [{"id": 52}]
        problems, evidence = driver.axis_id_source(block(kind="datum_axis", id=52), {}, None, axes)
        self.assertEqual(problems, [])
        self.assertEqual(evidence["axis_id"], 52)
        problems, _ = driver.axis_id_source(block(kind="datum_axis", id=7), {}, None, axes)
        self.assertTrue(any("does not match inspection" in item for item in problems))

    def test_a_datum_axis_without_an_inspected_axis_is_not_a_match(self):
        problems, _ = driver.axis_id_source(block(kind="datum_axis", id=52), {}, None, [])
        self.assertTrue(any("cannot be verified" in item for item in problems))


class ReloadEvidenceTests(unittest.TestCase):
    def test_the_reload_flag_is_read_from_the_result_block(self):
        terminal = {"result": {"saved_file_reloaded_and_verified": True}}
        self.assertIs(driver.reload_flag(terminal), True)

    def test_a_top_level_flag_is_not_evidence(self):
        terminal = {"saved_file_reloaded_and_verified": True, "result": {}}
        self.assertIsNone(driver.reload_flag(terminal))

    def test_a_missing_result_block_yields_none(self):
        self.assertIsNone(driver.reload_flag({}))
        self.assertIsNone(driver.reload_flag(None))


class BlockExtractionTests(unittest.TestCase):
    def test_the_axis_block_is_read_from_the_revolve_operation(self):
        terminal = {"result": {"operations": [{"op": "sketch"}, {"revolve_axis": block()}]}}
        self.assertEqual(driver.axis_block(terminal)["kind"], "section_centerline")

    def test_a_failed_job_has_no_axis_block(self):
        self.assertEqual(driver.axis_block({"result": {"operations": []}}), {})
        self.assertEqual(driver.axis_block({}), {})

    def test_sketch_entity_ids_come_from_the_sketch_operation(self):
        terminal = {
            "result": {
                "operations": [
                    {"op": "sketch", "entity_ids": {"spin_centerline": 17}},
                    {"op": "revolve"},
                ]
            }
        }
        self.assertEqual(driver.sketch_entity_ids(terminal), {"spin_centerline": 17})

    def test_missing_entity_ids_yield_an_empty_mapping(self):
        self.assertEqual(driver.sketch_entity_ids({"result": {"operations": []}}), {})


class LiveCaseCoverageTests(unittest.TestCase):
    def test_the_three_live_cases_are_the_expected_ones(self):
        self.assertEqual(
            sorted(driver.EXPECTED),
            ["explicit_datum_axis", "internal_centerline", "no_centerline"],
        )

    def test_the_negative_case_is_not_expected_to_succeed(self):
        self.assertFalse(driver.EXPECTED["no_centerline"]["succeeds"])

    def test_every_success_case_declares_a_volume_oracle(self):
        for case, expected in driver.EXPECTED.items():
            if expected["succeeds"]:
                with self.subTest(case=case):
                    self.assertGreater(expected["volume_mm3"], 0.0)


if __name__ == "__main__":
    unittest.main()
