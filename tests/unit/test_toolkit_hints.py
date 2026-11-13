"""BUG-030/BUG-031 worker launch mode, -4 fallback and Toolkit return-code hints."""

import contextlib
import json
import subprocess
import unittest
from unittest.mock import patch

import bridge
import desktop_worker

WORKER = "C:/repo/build/creo_worker.exe"


def probe(code, connected=False, state="connection_failed", exit_code=20):
    payload = json.dumps(
        {"connected": connected, "connection_state": state, "toolkit_code": code}
    ).encode()
    return subprocess.CompletedProcess([WORKER, "status", "2"], exit_code, payload, b"")


class HintTests(unittest.TestCase):
    def test_hints_name_the_observed_condition_without_local_paths(self):
        bad_context = bridge.toolkit_hint({"toolkit_code": -4, "worker_exit_code": 20})
        busy = bridge.toolkit_hint({"toolkit_code": -38, "worker_exit_code": 20})
        self.assertIn("PRO_TK_BAD_CONTEXT", bad_context)
        self.assertIn("not a license", bad_context)
        self.assertIn("modal dialog", busy)
        self.assertIn("exit 20", busy)
        for text in (bad_context, busy):
            self.assertNotIn(":\\", text)

    def test_unknown_code_and_success_are_described(self):
        self.assertEqual(bridge.toolkit_hint({"toolkit_code": 0}), "Toolkit connection verified")
        self.assertIn("-77", bridge.toolkit_hint({"toolkit_code": -77}))


class LaunchModeTests(unittest.TestCase):
    def mode(self, value):
        config = {"creo_root": "C:/Creo"}
        if value is not None:
            config["creo_worker_launch"] = value
        with patch.object(bridge, "config", return_value=config):
            return bridge.worker_launch_mode()

    def test_default_is_auto_and_invalid_values_are_rejected(self):
        self.assertEqual(self.mode(None), "auto")
        self.assertEqual(self.mode("desktop"), "desktop")
        with self.assertRaisesRegex(ValueError, "creo_worker_launch"):
            self.mode("explorer")
        with self.assertRaisesRegex(ValueError, "creo_worker_launch"):
            self.mode(1)


class SessionStatusTests(unittest.TestCase):
    def run_status(self, mode, direct, desktop):
        with (
            patch.object(bridge, "worker_launch_mode", return_value=mode),
            patch.object(
                bridge, "toolkit_lock", side_effect=lambda **kwargs: contextlib.nullcontext()
            ),
            patch.object(bridge, "build_native", return_value=WORKER),
            patch.object(bridge, "native_environment", return_value={"PATH": "x"}),
            patch.object(bridge.subprocess, "run", return_value=direct) as run,
            patch.object(desktop_worker, "run", return_value=desktop) as desktop_run,
        ):
            value = bridge.session_status(2)
        return value, run, desktop_run

    def test_direct_mode_never_uses_the_desktop(self):
        value, run, desktop_run = self.run_status(
            "direct", probe(-4), probe(0, True, "connected", 0)
        )
        self.assertEqual(value["worker_launch"], "direct")
        self.assertEqual(value["toolkit_code"], -4)
        self.assertIn("PRO_TK_BAD_CONTEXT", value["toolkit_hint"])
        desktop_run.assert_not_called()
        self.assertEqual(run.call_count, 1)

    def test_auto_mode_retries_through_the_desktop_after_bad_context(self):
        value, _, desktop_run = self.run_status("auto", probe(-4), probe(0, True, "connected", 0))
        self.assertEqual(value["worker_launch"], "desktop")
        self.assertTrue(value["connected"])
        self.assertEqual(desktop_run.call_count, 1)

    def test_desktop_failure_keeps_the_direct_result(self):
        value, _, desktop_run = self.run_status("auto", probe(-4), None)
        self.assertEqual(value["worker_launch"], "direct")
        self.assertEqual(value["desktop_retry"], "unavailable")
        self.assertEqual(desktop_run.call_count, 1)

    def test_desktop_result_that_is_still_bad_context_is_reported_but_not_adopted(self):
        value, _, _ = self.run_status("auto", probe(-4), probe(-4))
        self.assertEqual(value["worker_launch"], "direct")
        self.assertEqual(value["desktop_retry"]["toolkit_code"], -4)

    def test_other_failures_do_not_trigger_a_desktop_attempt(self):
        value, _, desktop_run = self.run_status("auto", probe(-38), probe(0, True, "connected", 0))
        self.assertEqual(value["worker_launch"], "direct")
        desktop_run.assert_not_called()
