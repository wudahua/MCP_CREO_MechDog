"""DEV-051 T09D: offline coverage for the plan performance baseline driver."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from creo_mechdog.schema import validate_operations
from tools import test_plan_performance as driver


def specs():
    return dict(driver.SPECS)


class FixtureLayoutTests(unittest.TestCase):
    def test_pockets_stay_inside_the_plate_with_margin(self):
        for name, spec in specs().items():
            with self.subTest(model_class=name):
                details = driver.validate_layout(spec)
                self.assertGreater(details["edge_margin_mm"], 0.0)

    def test_pockets_never_overlap(self):
        for name, spec in specs().items():
            details = driver.validate_layout(spec)
            with self.subTest(model_class=name):
                self.assertGreaterEqual(details["minimum_pairwise_gap_mm"], 0.0)

    def test_large_fixture_targets_the_observed_edge_scale(self):
        self.assertEqual(driver.EDGE_SCALE_REFERENCE["observed_edges"], 1408)
        self.assertEqual(driver.EDGE_SCALE_REFERENCE["meaning"], "edges, not parts")
        details = driver.validate_layout(driver.SPECS["large"])
        self.assertEqual(details["pocket_count"], 96)
        self.assertEqual(details["cut_operation_count"], 8)
        self.assertEqual(details["contours_per_cut"], 12)

    def test_expected_volumes_subtract_every_pocket(self):
        for name, spec in specs().items():
            with self.subTest(model_class=name):
                driver.validate_expectation(spec)
                pocket = spec["pocket"]
                removed = (
                    driver.pocket_count(spec)
                    * pocket["width"]
                    * pocket["height"]
                    * pocket["depth"]
                )
                self.assertAlmostEqual(
                    driver.expected_final_volume_mm3(spec),
                    driver.plate_volume_mm3(spec) - removed,
                    places=9,
                )

    def test_every_plan_passes_schema_validation(self):
        for name, spec in specs().items():
            with self.subTest(model_class=name):
                validate_operations(driver.plate_operations(spec))
                for pair in driver.single_mode_jobs(spec):
                    validate_operations(pair)
                validate_operations(driver.batch_mode_plan(spec))

    def test_model_names_are_legal_and_unique_per_rep_family(self):
        seen = set()
        for name in ("small", "large"):
            candidate = f"t09d_{name[:2]}s1_abcdef12"[:16]
            self.assertLessEqual(len(candidate), 31)
            self.assertTrue(candidate[0].isalnum())
            self.assertEqual(candidate, candidate.lower())
            seen.add(candidate)
        self.assertEqual(len(seen), len(seen))


class ModeEquivalenceTests(unittest.TestCase):
    def test_single_and_batch_expect_the_identical_result(self):
        checks = driver.equivalence_checks()
        self.assertTrue(checks["passed"])
        for name, equivalence in checks["modes"].items():
            with self.subTest(model_class=name):
                self.assertTrue(equivalence["volumes_equal"])
                self.assertTrue(equivalence["cut_deltas_equal"])
                self.assertEqual(
                    equivalence["single_save_reload_events"],
                    driver.cut_count(driver.SPECS[name]),
                )
                self.assertEqual(equivalence["batch_save_reload_events"], 1)

    def test_batch_plan_is_the_flattened_single_jobs(self):
        for name, spec in specs().items():
            flattened = driver.batch_mode_plan(spec)
            with self.subTest(model_class=name):
                self.assertEqual(
                    flattened,
                    [op for pair in driver.single_mode_jobs(spec) for op in pair],
                )

    def test_save_reload_event_difference_is_declared_not_hidden(self):
        for equivalence in driver.equivalence_checks()["modes"].values():
            self.assertIn("note", equivalence)
            self.assertIn("recorded", equivalence["note"])


class TimingRecorderTests(unittest.TestCase):
    TERMINAL = {
        "created_at": "2026-10-30T10:00:00+08:00",
        "finished_at": "2026-10-30T10:00:51+08:00",
    }

    def test_synthetic_checks_pass_and_stay_labelled_synthetic(self):
        checks = driver.synthetic_timing_checks()
        self.assertTrue(checks["passed"])
        self.assertTrue(checks["synthetic_data"])
        self.assertTrue(checks["not_a_benchmark"])
        self.assertIn("Not a measurement", checks["statement"])

    def test_server_window_comes_from_the_terminal_manifest(self):
        record = driver.job_timing_record(0.25, [0.01, 0.02], 52.0, self.TERMINAL)
        self.assertEqual(record["server_accept_to_terminal_s"], 51.0)
        self.assertEqual(record["submit_round_trip_s"], 0.25)
        self.assertEqual(record["client_total_s"], 52.0)
        self.assertEqual(record["poll_count"], 2)

    def test_missing_or_garbage_timestamps_yield_null_not_an_estimate(self):
        for terminal in (
            {},
            {"created_at": self.TERMINAL["created_at"]},
            {"created_at": "garbage", "finished_at": self.TERMINAL["finished_at"]},
            {"created_at": None, "finished_at": None},
        ):
            with self.subTest(terminal=terminal):
                record = driver.job_timing_record(0.1, [], 1.0, terminal)
                self.assertIsNone(record["server_accept_to_terminal_s"])

    def test_every_native_sub_stage_is_marked_unobservable(self):
        record = driver.job_timing_record(0.1, [], 1.0, self.TERMINAL)
        self.assertEqual(sorted(record["stages"]), sorted(driver.UNOBSERVABLE_STAGES))
        for stage in driver.UNOBSERVABLE_STAGES:
            entry = record["stages"][stage]
            with self.subTest(stage=stage):
                self.assertIsNone(entry["value"])
                self.assertEqual(entry["status"], "unobservable")
                self.assertIn("never estimated", entry["reason"])

    def test_summary_median_and_range(self):
        self.assertEqual(
            driver.summarize([3.0, 1.0, 2.0, 4.0]),
            {"n": 4, "median_s": 2.5, "min_s": 1.0, "max_s": 4.0},
        )
        self.assertEqual(
            driver.summarize([5.0, 1.0, 3.0]),
            {"n": 3, "median_s": 3.0, "min_s": 1.0, "max_s": 5.0},
        )
        self.assertEqual(
            driver.summarize([]), {"n": 0, "median_s": None, "min_s": None, "max_s": None}
        )

    def test_case_summary_tracks_save_reload_completeness(self):
        jobs = [
            {
                "timing": {
                    "server_accept_to_terminal_s": 10.0,
                    "client_total_s": 11.0,
                },
                "saved_file_reloaded_and_verified": True,
            },
            {
                "timing": {
                    "server_accept_to_terminal_s": None,
                    "client_total_s": 12.0,
                },
                "saved_file_reloaded_and_verified": True,
            },
        ]
        summary = driver.case_summary(jobs, 0.0, 23.0)
        self.assertEqual(summary["measured_job_count"], 2)
        self.assertIsNone(summary["measured_server_window_sum_s"])
        self.assertEqual(summary["per_job_server_window_s"], [10.0, None])
        self.assertEqual(summary["save_reload_events"], 2)
        self.assertTrue(summary["save_reload_complete"])
        incomplete = driver.case_summary(
            [dict(job, saved_file_reloaded_and_verified=None) for job in jobs], 0.0, 23.0
        )
        self.assertFalse(incomplete["save_reload_complete"])


class OfflineEntryTests(unittest.TestCase):
    def run_main(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = driver.main(argv)
        return code, output.getvalue()

    def test_default_run_is_offline_and_never_builds_a_client(self):
        client = Mock(side_effect=AssertionError("MCP client must not be created"))
        with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
            with patch.object(driver, "live", new=AsyncMock()) as live:
                code, text = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("OFFLINE ONLY", text)
        self.assertIn("synthetic_data=true not_a_benchmark=true", text)
        self.assertIn("LIVE NOT RUN", text)
        live.assert_not_awaited()
        client.assert_not_called()

    def test_a_single_live_flag_cannot_connect(self):
        for argv in (["--live"], ["--confirm-session-usable"]):
            with self.subTest(argv=argv):
                client = Mock(side_effect=AssertionError("MCP client must not be created"))
                with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                    with patch.object(driver, "live", new=AsyncMock()) as live:
                        code, text = self.run_main(argv)
                self.assertEqual(code, 0)
                self.assertIn("both --live and --confirm-session-usable are required", text)
                live.assert_not_awaited()
                client.assert_not_called()

    def test_both_flags_reach_the_live_entry_point_only(self):
        with patch.object(driver, "live", new=AsyncMock()) as live:
            code, text = self.run_main(["--live", "--confirm-session-usable"])
        self.assertEqual(code, 0)
        self.assertEqual(text, "")
        live.assert_awaited_once()

    def test_non_positive_reps_are_rejected(self):
        for reps in ("0", "-3"):
            with self.subTest(reps=reps), self.assertRaises(SystemExit):
                driver.main(["--reps", reps])

    def test_an_existing_report_is_refused_before_any_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            client = Mock(side_effect=AssertionError("MCP client must not be created"))
            for argv in ([], ["--live", "--confirm-session-usable"]):
                with self.subTest(argv=argv):
                    with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                        with patch.object(driver, "live", new=AsyncMock()) as live:
                            code, text = self.run_main([*argv, "--output", str(stale)])
                    self.assertEqual(code, 2)
                    self.assertIn("REFUSED BEFORE CONNECTION", text)
                    live.assert_not_awaited()
                    client.assert_not_called()

    def test_offline_report_marks_itself_synthetic_and_not_a_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            code, _ = self.run_main(["--output", str(target)])
            self.assertEqual(code, 0)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "offline")
            self.assertFalse(report["live_run"])
            self.assertEqual(report["native_acceptance"], "not_run")
            self.assertTrue(report["synthetic_data"])
            self.assertTrue(report["not_a_benchmark"])
            self.assertIn("improvement claim", report["statement"])
            self.assertTrue(report["checks"]["fixtures"]["passed"])
            self.assertTrue(report["checks"]["synthetic_timing"]["passed"])
            for stage in driver.UNOBSERVABLE_STAGES:
                entry = report["observability"]["unobservable_stages"][stage]
                self.assertIsNone(entry["value"])
                self.assertEqual(entry["status"], "unobservable")

    def test_resolve_output_rejects_an_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                driver.resolve_output(stale, "run")
            fresh = Path(directory) / "fresh.json"
            self.assertEqual(driver.resolve_output(fresh, "run"), fresh)


class NoResubmissionTests(unittest.IsolatedAsyncioTestCase):
    def runner(self):
        with patch.object(driver, "local_provenance", return_value={}):
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            return driver.PlanPerformanceRun(
                None, Path(directory.name) / "report.json", "testrun", reps=1
            )

    async def test_each_submission_increments_the_session_job_index(self):
        runner = self.runner()
        runner.call = AsyncMock(return_value={"job_id": "j1", "model_id": "m1"})
        manifest, _ = await runner.submit_job({"operations": []})
        self.assertEqual(runner.session_job_index, 1)
        self.assertEqual(manifest["job_id"], "j1")
        await runner.submit_job({"operations": []})
        self.assertEqual(runner.session_job_index, 2)

    async def test_budget_exhaustion_raises_and_does_not_resubmit(self):
        runner = self.runner()
        runner.timed_call = AsyncMock(return_value=({"status": "running"}, 0.01))
        with patch.object(driver.asyncio, "sleep", new=AsyncMock()):
            with self.assertRaisesRegex(TimeoutError, "do not resubmit"):
                await runner.wait_job("j1", budget=0)
        for call_args in runner.timed_call.await_args_list:
            self.assertEqual(call_args.args[0], "creo_get_job")

    async def test_unknown_terminal_status_is_recorded_and_not_resubmitted(self):
        runner = self.runner()
        runner.timed_call = AsyncMock(return_value=({"status": "corrupted"}, 0.01))
        with self.assertRaisesRegex(RuntimeError, "do not resubmit"):
            await runner.wait_job("j1")
        runner.timed_call.assert_awaited_once_with("creo_get_job", {"job_id": "j1"})

    async def test_failed_jobs_carry_the_raw_error_fields(self):
        runner = self.runner()
        runner.call = AsyncMock(return_value={"job_id": "j", "model_id": "m"})
        terminal = {
            "status": "failed",
            "message": "boom",
            "reason": "why",
            "reason_details": {"detail": True},
        }
        runner.wait_job = AsyncMock(return_value=(terminal, 1.0, [0.5]))
        record = await runner.run_measured_job("k", {}, None)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["raw_error"]["message"], "boom")
        self.assertEqual(record["raw_error"]["reason_details"], {"detail": True})

    async def test_warm_cold_is_the_session_job_index(self):
        runner = self.runner()
        runner.call = AsyncMock(return_value={"job_id": "j", "model_id": "m"})
        runner.wait_job = AsyncMock(
            return_value=({"status": "succeeded", "result": {}}, 1.0, [0.5])
        )
        cold = await runner.run_measured_job("a", {}, None)
        warm = await runner.run_measured_job("b", {}, None)
        self.assertEqual(cold["warm_cold"], "cold")
        self.assertEqual(warm["warm_cold"], "warm")


class ModeComparisonTests(unittest.TestCase):
    def make_case(self, model_class, mode, volume, edges, reloaded=True):
        return {
            "model_class": model_class,
            "plan_mode": mode,
            "rep": 1,
            "jobs": [{"placeholder": True}],
            "result": {
                "final_volume_mm3": volume,
                "expected_final_volume_mm3": volume,
                "final_counts": {"edges": edges},
                "volume_match": True,
            },
            "summary": {
                "save_reload_events": 1 if reloaded else 0,
                "save_reload_complete": reloaded,
            },
        }

    def runner(self):
        with patch.object(driver, "local_provenance", return_value={}):
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            instance = driver.PlanPerformanceRun(
                None, Path(directory.name) / "report.json", "testrun", reps=1
            )
            return instance

    def test_comparable_rows_require_equal_edges_and_full_reload(self):
        runner = self.runner()
        single = self.make_case("small", "single", 17500.0, 40)
        batch = self.make_case("small", "batch", 17500.0, 40)
        row = runner.compare_modes(single, batch)
        self.assertTrue(row["comparable"])
        self.assertTrue(row["edges"]["equal"])
        self.assertEqual(row["save_reload_events"], {"single": 1, "batch": 1})

    def test_different_edge_counts_are_never_called_comparable(self):
        runner = self.runner()
        row = runner.compare_modes(
            self.make_case("small", "single", 17500.0, 40),
            self.make_case("small", "batch", 17500.0, 44),
        )
        self.assertFalse(row["comparable"])
        self.assertFalse(row["edges"]["equal"])

    def test_summary_groups_by_class_and_mode(self):
        runner = self.runner()
        runner.report["cases"] = [
            {
                "model_class": "small",
                "plan_mode": "single",
                "passed": True,
                "jobs": [{"warm_cold": "cold"}],
                "summary": {
                    "measured_client_total_s": 2.0,
                    "measured_server_window_sum_s": 1.5,
                    "save_reload_events": 2,
                },
            },
            {
                "model_class": "small",
                "plan_mode": "single",
                "passed": True,
                "jobs": [{"warm_cold": "warm"}],
                "summary": {
                    "measured_client_total_s": 4.0,
                    "measured_server_window_sum_s": 3.5,
                    "save_reload_events": 2,
                },
            },
        ]
        summary = runner.build_summary()
        self.assertEqual(len(summary), 1)
        entry = summary[0]
        self.assertEqual(entry["model_class"], "small")
        self.assertEqual(entry["plan_mode"], "single")
        self.assertEqual(entry["client_total_s"]["median_s"], 3.0)
        self.assertEqual(entry["server_window_sum_s"]["median_s"], 2.5)
        self.assertEqual(entry["cold_jobs"], 1)
        self.assertEqual(entry["passed_cases"], 2)


if __name__ == "__main__":
    unittest.main()
