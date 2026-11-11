"""FEAT-033 batch B: a job may carry its own executor budget.

The 0.19.3 report lost 25 minutes to a job whose native run was still working
while the server-side watchdog already called it ``unknown_outcome``: the
budget was a single server-wide constant. This module pins the bounded,
opt-in override and the watchdog change that keeps the two numbers equal.
Nothing here needs Creo or a Toolkit connection.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge

ROOT = Path(__file__).resolve().parents[2]


class TimeoutValidationTests(unittest.TestCase):
    def test_omitted_budget_keeps_the_server_default(self):
        self.assertIsNone(generic_bridge.validate_executor_timeout(None))

    def test_bounds_are_inclusive(self):
        self.assertEqual(generic_bridge.validate_executor_timeout(60), 60)
        self.assertEqual(generic_bridge.validate_executor_timeout(7200), 7200)

    def test_out_of_range_names_the_range_and_that_no_job_was_created(self):
        for value in (0, 59, 7201, -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    generic_bridge.validate_executor_timeout(value)
                message = str(caught.exception)
                self.assertIn("60-7200", message)
                self.assertIn("no job was created", message)

    def test_bool_and_non_integer_are_rejected(self):
        for value in (True, False, "600", 600.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    generic_bridge.validate_executor_timeout(value)
                self.assertIn("integer number of seconds", str(caught.exception))


class EffectiveBudgetTests(unittest.TestCase):
    def test_request_budget_wins_over_the_server_setting(self):
        with patch.object(bridge, "config", return_value={"generic_timeout_seconds": 600}):
            self.assertEqual(
                generic_bridge.job_timeout_seconds(
                    {"timeout_seconds": 1800, "timeout_source": "job"}
                ),
                1800,
            )

    def test_legacy_request_falls_back_to_the_server_setting(self):
        with patch.object(bridge, "config", return_value={"generic_timeout_seconds": 900}):
            self.assertEqual(generic_bridge.job_timeout_seconds({}), 900)

    def test_a_malformed_persisted_value_never_becomes_the_budget(self):
        with patch.object(bridge, "config", return_value={"generic_timeout_seconds": 600}):
            for value in (True, "1800", 0, -5, None):
                with self.subTest(value=value):
                    self.assertEqual(
                        generic_bridge.job_timeout_seconds({"timeout_seconds": value}), 600
                    )


class WatchdogLifetimeTests(unittest.TestCase):
    def test_generic_job_uses_its_own_budget(self):
        manifest = {"kind": "generic", "timeout_seconds": 1800, "timeout_source": "job"}
        with patch.object(bridge, "config", return_value={"generic_timeout_seconds": 600}):
            self.assertEqual(bridge.expected_lifetime_seconds(manifest), 120 + 180 + 1800 + 30)

    def test_generic_job_without_a_budget_uses_the_server_setting(self):
        with patch.object(bridge, "config", return_value={"generic_timeout_seconds": 600}):
            self.assertEqual(
                bridge.expected_lifetime_seconds({"kind": "generic"}), 120 + 180 + 600 + 30
            )

    def test_non_generic_job_still_uses_the_native_setting(self):
        with patch.object(
            bridge,
            "config",
            return_value={"native_timeout_seconds": 180, "generic_timeout_seconds": 600},
        ):
            self.assertEqual(
                bridge.expected_lifetime_seconds({"kind": "plate"}), 120 + 180 + 180 + 30
            )

    def test_a_long_budget_is_not_cut_short_by_the_default(self):
        # The reported failure mode: 25 minutes of native work, default 600s.
        with patch.object(bridge, "config", return_value={"generic_timeout_seconds": 600}):
            short = bridge.expected_lifetime_seconds({"kind": "generic"})
            long = bridge.expected_lifetime_seconds(
                {"kind": "generic", "timeout_seconds": 3600, "timeout_source": "job"}
            )
        self.assertLess(short, 25 * 60)
        self.assertGreater(long, 25 * 60)


class WiringTests(unittest.TestCase):
    def test_tool_passes_the_budget_to_submit(self):
        text = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("timeout_seconds: int | None = None", text)
        self.assertIn("timeout_seconds=timeout_seconds", text)

    def test_runner_and_watchdog_read_the_frozen_request_value(self):
        runner = (ROOT / "generic_bridge.py").read_text(encoding="utf-8")
        self.assertIn("timeout=job_timeout_seconds(request)", runner)
        self.assertIn('"timeout_seconds": effective_timeout', runner)
        self.assertIn('"timeout_source": timeout_source', runner)
        watchdog = (ROOT / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("expected_lifetime_seconds(manifest)", watchdog)

    def test_timeout_message_names_the_budget(self):
        text = (ROOT / "generic_bridge.py").read_text(encoding="utf-8")
        self.assertIn("Native worker exceeded its {budget}s budget", text)
        self.assertIn("not a completion", " ".join(text.split()))


class NativeDiagnosticTests(unittest.TestCase):
    def test_quilt_visit_failure_names_the_original_target_workaround(self):
        text = (ROOT / "native/quilt_query.h").read_text(encoding="utf-8")
        self.assertIn("ProError", text)
        self.assertIn("Reference the original target quilt instead", text)
        self.assertIn('inspect_model(section=\\"quilts\\")', text)

    def test_project_curve_names_which_of_the_two_steps_failed(self):
        text = (ROOT / "native/project_curve.cpp").read_text(encoding="utf-8")
        self.assertIn("project_curve step 1 of 2", text)
        self.assertIn("project_curve step 2 of 2", text)
        self.assertIn("ProDtmCrv INTERSECT", text)

    def test_quilt_merge_refusal_reports_the_submitted_pair(self):
        text = (ROOT / "native/quilt_merge.cpp").read_text(encoding="utf-8")
        self.assertIn("quilt_merge (JOIN) was refused", text)
        self.assertIn("target quilt ", text)
        self.assertIn("surface_group_measure", text)
        self.assertIn("coplanar-adjacent", text)


if __name__ == "__main__":
    unittest.main()
