"""FEAT-023/FEAT-008 T09A offline tests for the component-label live driver.

``tools/test_component_labels_live.py`` decides whether the T09A remainder
passed. These tests pin the parts that can be judged without a Creo session:

* the projection contract - labels, identity, bindings and deleted identities
  are kept exactly as the projection states them;
* the reload guard - a reload with unchanged ids keeps the labels, a reload
  with renumbered ids never rebinds them onto the new records, and a
  same-label reinsert binds only the new identity;
* the three scenarios the live run must cover (reload association, delete then
  unique-label reinsert, id renumbering) and what each one proves;
* the offline stage fails when a contract statement does not hold, instead of
  printing a false value and exiting successfully.
"""

import json
import tempfile
import unittest
from pathlib import Path

from tools import test_component_labels_live as driver


class ProjectionContractTests(unittest.TestCase):
    def test_the_offline_projection_contract_holds(self):
        projection = driver.check_projection_contract()
        self.assertTrue(projection["multi_label_kept"])
        self.assertTrue(projection["single_label_mirrors_source"])
        self.assertTrue(projection["bindings_kept_per_record"])
        self.assertTrue(projection["deleted_identity_kept_separately"])
        self.assertEqual(projection["identity_key"]["key"], "model_identity+feature_id")

    def test_the_bindings_are_carried_per_record(self):
        projection = driver.check_projection_contract()
        self.assertIn("bindings_kept_per_record", projection)


class ReloadGuardTests(unittest.TestCase):
    def test_all_three_reload_guards_hold(self):
        guard = driver.check_reload_guard_contract()
        self.assertTrue(guard["reload_with_unchanged_ids_keeps_labels"])
        self.assertTrue(guard["reload_id_renumbering_never_rebinds"])
        self.assertTrue(guard["same_label_reinsert_binds_only_new_identity"])

    def test_a_broken_guard_is_reported_as_a_failure(self):
        failures = driver.contract_failures(
            {"multi_label_kept": True},
            {"reload_id_renumbering_never_rebinds": False},
        )
        self.assertEqual(failures, ["reload_guard.reload_id_renumbering_never_rebinds"])

    def test_a_healthy_contract_reports_no_failures(self):
        failures = driver.contract_failures(
            driver.check_projection_contract(),
            driver.check_reload_guard_contract(),
        )
        self.assertEqual(failures, [])


class ScenarioCoverageTests(unittest.TestCase):
    def test_the_three_scenarios_are_stated(self):
        scenarios = driver.scenario_expectations()
        for name in (
            "reload_association",
            "delete_then_unique_label_reinsert",
            "id_renumbering_never_rebinds",
        ):
            with self.subTest(scenario=name):
                self.assertIn(name, scenarios)
                self.assertTrue(scenarios[name]["expect"])
                self.assertTrue(scenarios[name]["fails_when"])

    def test_the_scenarios_name_real_live_cases(self):
        scenarios = driver.scenario_expectations()
        self.assertEqual(scenarios["reload_association"]["live_case"], "cross_job")
        self.assertEqual(
            scenarios["delete_then_unique_label_reinsert"]["live_case"], "rename_reinsert"
        )

    def test_the_renumbering_scenario_is_not_claimed_as_a_live_pass(self):
        scenario = driver.scenario_expectations()["id_renumbering_never_rebinds"]
        self.assertIn("partially covered live", scenario["live_verifiability"])
        self.assertIn("not constructible through this service", scenario["live_verifiability"])


class OfflineEntryTests(unittest.TestCase):
    def test_the_offline_run_writes_a_report_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "run" / "report.json"
            self.assertEqual(driver.main(["--output", str(target)]), 0)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "offline")
            self.assertEqual(report["native_acceptance"], "not_run")
            self.assertEqual(report["contract_failures"], [])
            self.assertIn("scenarios", report)
            self.assertTrue(target.with_name("report.sha256").is_file())

    def test_an_existing_report_is_refused_before_any_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                driver.main(["--output", str(stale)])

    def test_a_contract_violation_fails_the_offline_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            original = driver.check_reload_guard_contract
            try:
                driver.check_reload_guard_contract = lambda: {
                    "reload_with_unchanged_ids_keeps_labels": True,
                    "reload_id_renumbering_never_rebinds": False,
                    "same_label_reinsert_binds_only_new_identity": True,
                }
                code = driver.main(["--output", str(target)])
            finally:
                driver.check_reload_guard_contract = original
            self.assertEqual(code, 1)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(
                report["contract_failures"],
                ["reload_guard.reload_id_renumbering_never_rebinds"],
            )


if __name__ == "__main__":
    unittest.main()
