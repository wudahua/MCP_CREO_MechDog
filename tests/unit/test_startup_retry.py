"""BUG-008 WorkBuddy follow-up: retry survives damaged shared startup metadata."""

import asyncio
import json
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

import bridge
import server
from creo_mechdog import creo_startup
from tests import test_creo_startup as startup_tests

REAL_MONOTONIC = time.monotonic


class StartupRetry(unittest.TestCase):
    def setUp(self):
        self.fixture = startup_tests.CreoStartupTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.enterContext(patch.object(creo_startup, "boot_info", return_value=None))

    def controller(self):
        return creo_startup.CreoStartup(self.fixture.coordinator)

    def run_retry(self, controller):
        """Keep the real coordinator thread and wait for this invocation to finish."""
        completed = threading.Event()
        run = controller._run

        def observed_run(*args):
            try:
                run(*args)
            finally:
                completed.set()

        with patch.object(controller, "_run", side_effect=observed_run):
            accepted = controller.start(retry=True)
            thread = controller._thread
            self.assertTrue(completed.wait(60), "startup coordinator did not finish")
            thread.join()
        return accepted

    def test_damaged_history_is_preserved_and_cannot_authorize_a_launch(self):
        for content in (
            b"",
            b"\0" * 380,
            b"{",
            b"[]",
            b"{}",
            b'{"state":"ready","launch_reserved":false,"launch_attempt":true}',
        ):
            with self.subTest(content=content):
                path = self.fixture.coordinator / "state.json"
                path.write_bytes(content)
                controller = self.controller()
                value = self.run_retry(controller)
                self.assertIn(value["state"], creo_startup.ACTIVE)
                self.assertFalse(controller._thread.is_alive())
                state = controller.status()
                self.assertEqual(state["state"], "selection_required")
                self.assertFalse(state["connected"])
                self.assertFalse(state["automatic_launch_allowed"])
                self.assertFalse(state["launch_state_known"])
                self.assertEqual(state["coordination_error"]["code"], "startup_state_unreadable")
                self.assertEqual(path.read_bytes(), content)
        self.fixture.launch.assert_not_called()
        self.fixture.probe.assert_not_called()

    def test_untrusted_existing_session_waits_for_a_competing_probe_within_budget(self):
        from creo_mechdog.startup_state import StartupStateError

        self.fixture.inventory.return_value = self.fixture.existing()
        self.fixture.probe.side_effect = [bridge.ToolkitBusy(), startup_tests.READY]
        controller = self.fixture.startup
        controller._recheck_untrusted_state(
            creo_startup.Settings.load(), StartupStateError("fixture")
        )
        self.assertTrue(controller.status()["connected"])
        self.assertEqual(self.fixture.probe.call_count, 2)
        self.assertEqual(self.fixture.clock.elapsed, 0.25)
        self.fixture.launch.assert_not_called()

    def test_untrusted_busy_recheck_stops_at_the_connection_budget(self):
        from creo_mechdog.startup_state import StartupStateError

        self.fixture.inventory.return_value = self.fixture.existing()
        self.fixture.probe.side_effect = bridge.ToolkitBusy()
        controller = self.fixture.startup
        controller._recheck_untrusted_state(
            creo_startup.Settings.load(), StartupStateError("fixture")
        )
        self.assertEqual(controller.status()["state"], "timeout")
        self.assertFalse(controller.status()["connected"])
        self.assertEqual(self.fixture.clock.elapsed, 10)
        self.fixture.launch.assert_not_called()

    def test_existing_session_can_be_verified_without_replacing_corrupt_history(self):
        path = self.fixture.coordinator / "state.json"
        path.write_bytes(b"")
        self.fixture.inventory.return_value = self.fixture.existing()
        controller = self.controller()
        self.run_retry(controller)
        state = controller.status()
        self.assertEqual(state["state"], "ready")
        self.assertTrue(state["connected"])
        self.assertTrue(state["launch_reserved"])
        self.assertFalse(state["automatic_launch_allowed"])
        self.assertEqual(path.read_bytes(), b"")
        self.fixture.probe.assert_called_once_with(
            connect_timeout_seconds=7, build_worker=False, deadline=10
        )
        self.fixture.launch.assert_not_called()

    def test_invalid_schema_is_actionable_and_not_a_new_reservation(self):
        invalid = (
            {"launch_attempt": -1},
            {"launch_reserved": "false"},
            {"phase_deadline_monotonic": "future"},
            {"updated_at": "invalid"},
            {"verified_at": "2026-10-15T12:00:00"},
            {"native": []},
        )
        path = self.fixture.coordinator / "state.json"
        for fields in invalid:
            with self.subTest(fields=fields):
                bridge.write_json(
                    path,
                    {"state": "timeout", "launch_attempt": 4, "launch_reserved": True, **fields},
                )
                before = path.read_bytes()
                controller = self.controller()
                self.run_retry(controller)
                self.assertEqual(controller.status()["state"], "selection_required")
                self.assertEqual(path.read_bytes(), before)
        self.fixture.launch.assert_not_called()

    def test_valid_closed_session_retry_starts_one_coordinator_and_one_launch(self):
        bridge.write_json(
            self.fixture.coordinator / "state.json",
            {
                "state": "timeout",
                "launch_attempt": 17,
                "launch_reserved": True,
            },
        )
        launched = threading.Event()
        process = Mock()
        process.poll.return_value = None

        def launch(*args):
            launched.set()
            return process

        self.fixture.launch.side_effect = launch
        self.fixture.inventory.side_effect = lambda settings: (
            self.fixture.existing() if launched.is_set() else {"processes": [], "uncertain": False}
        )
        controller = self.controller()
        self.run_retry(controller)
        self.assertEqual(controller.status()["state"], "ready")
        self.assertEqual(controller.status()["launch_attempt"], 18)
        self.fixture.launch.assert_called_once()
        self.assertFalse(
            bridge.read_json(self.fixture.coordinator / "state.json")["launch_reserved"]
        )

    def test_retry_reuses_existing_session_without_incrementing_launch_attempt(self):
        bridge.write_json(
            self.fixture.coordinator / "state.json",
            {"state": "timeout", "launch_attempt": 17, "launch_reserved": True},
        )
        self.fixture.inventory.return_value = self.fixture.existing()
        self.fixture.probe.return_value = startup_tests.READY
        controller = self.controller()
        self.run_retry(controller)
        state = controller.status()
        self.assertEqual(state["state"], "ready")
        self.assertEqual(state["launch_attempt"], 17)
        self.assertEqual(state["phase"], "ready")
        self.fixture.launch.assert_not_called()
        self.fixture.probe.assert_called_once_with(
            connect_timeout_seconds=7, build_worker=False, deadline=10
        )

    def test_polling_keeps_the_retry_id_and_a_new_retry_gets_a_new_one(self):
        self.fixture.inventory.return_value = self.fixture.existing()
        self.fixture.probe.return_value = startup_tests.READY
        controller = self.controller()
        self.run_retry(controller)
        first_thread = controller._thread
        self.assertFalse(first_thread.is_alive())
        first = controller.status()
        self.assertEqual(first["retry_id"], controller.status()["retry_id"])
        accepted = self.run_retry(controller)
        self.assertIsNot(controller._thread, first_thread)
        self.assertNotEqual(first["retry_id"], accepted["retry_id"])
        self.assertFalse(controller._thread.is_alive())
        second = controller.status()
        self.assertNotEqual(first["retry_id"], second["retry_id"])
        self.assertEqual(self.fixture.probe.call_count, 2)
        self.fixture.launch.assert_not_called()

    def test_new_retry_gets_new_id_even_within_same_clock_tick(self):
        self.fixture.inventory.return_value = self.fixture.existing()
        self.fixture.probe.return_value = startup_tests.READY
        controller = self.controller()
        with (
            patch.object(bridge, "now", return_value="2026-11-27T12:00:00+00:00"),
            patch.object(creo_startup.time, "monotonic_ns", return_value=123456789),
            patch.object(creo_startup.time, "perf_counter_ns", return_value=987654321),
        ):
            self.run_retry(controller)
            first_thread = controller._thread
            self.assertFalse(first_thread.is_alive())
            first = controller.status()
            self.assertEqual(first["retry_id"], controller.status()["retry_id"])
            accepted = self.run_retry(controller)
            self.assertIsNot(controller._thread, first_thread)
            self.assertNotEqual(first["retry_id"], accepted["retry_id"])
            self.assertFalse(controller._thread.is_alive())
            second = controller.status()
        self.assertNotEqual(first["retry_id"], second["retry_id"])
        self.assertEqual(second["retry_id"], accepted["retry_id"])
        self.assertEqual(self.fixture.probe.call_count, 2)
        self.fixture.launch.assert_not_called()

    def test_cross_process_coordination_adopts_different_retry_id_in_same_tick(self):
        state_path = self.fixture.coordinator / "state.json"
        frozen = "2026-11-27T12:00:00+00:00"
        bridge.write_json(
            state_path,
            {
                "state": "timeout",
                "launch_reserved": False,
                "launch_attempt": 0,
                "retry_id": "prior0000001",
                "updated_at": frozen,
            },
        )
        self.fixture.inventory.return_value = self.fixture.existing()
        controller = self.controller()

        original_read = bridge.read_json
        calls = 0

        def read_with_concurrent_finish(path):
            nonlocal calls
            calls += 1
            if calls == 2 and path == state_path:
                bridge.write_json(
                    state_path,
                    {
                        "state": "ready",
                        "connected": True,
                        "launch_reserved": False,
                        "launch_attempt": 0,
                        "retry_id": "other0000002",
                        "updated_at": frozen,
                        "verified_at": frozen,
                    },
                )
            return original_read(path)

        with (
            patch.object(bridge, "now", return_value=frozen),
            patch.object(bridge, "read_json", side_effect=read_with_concurrent_finish),
        ):
            self.run_retry(controller)
            self.assertFalse(controller._thread.is_alive())
            status = controller.status()
        self.assertTrue(status["coordinated"])
        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["retry_id"], "other0000002")
        self.fixture.probe.assert_not_called()

    def test_busy_probe_during_retry_does_not_open_a_second_channel(self):
        self.fixture.inventory.return_value = self.fixture.existing()
        self.fixture.probe.side_effect = [
            bridge.ToolkitBusy(holder={"job_id": "job" * 8, "operation": "execute_plan"}),
            startup_tests.READY,
        ]
        controller = self.controller()
        self.run_retry(controller)
        state = controller.status()
        self.assertEqual(state["state"], "ready")
        self.assertEqual(self.fixture.probe.call_count, 2)
        self.fixture.launch.assert_not_called()

    def test_retry_dispatch_does_not_block_the_async_protocol_loop(self):
        entered, release = threading.Event(), threading.Event()

        def blocking_start(**kwargs):
            entered.set()
            release.wait(2)
            return {"state": "checking", "connected": False}

        async def check():
            task = asyncio.create_task(server.creo_startup_status(retry=True))
            began = time.perf_counter()
            await asyncio.sleep(0.02)
            elapsed = time.perf_counter() - began
            try:
                self.assertTrue(entered.is_set())
                self.assertLess(elapsed, 0.5)
                self.assertFalse(task.done())
            finally:
                release.set()
                await task

        with (
            patch.object(server.startup, "start", side_effect=blocking_start),
            patch.object(time, "monotonic", REAL_MONOTONIC),
        ):
            asyncio.run(check())

    def test_real_stdio_retry_returns_structured_result_for_corrupt_history(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        (self.fixture.coordinator / "state.json").write_bytes(b"")
        bootstrap = """
import sys
from creo_mechdog import bridge, creo_startup, server
from pathlib import Path
root=Path(sys.argv[1])
bridge.ROOT=root
bridge.JOBS=root/'jobs'
bridge.config=lambda:{'creo_root':str(root/'Creo with spaces'),'creo_startup_timeout_seconds':10}
bridge.channel_health=lambda:{}
creo_startup.inventory=lambda settings:{'processes':[],'uncertain':False}
creo_startup.boot_info=lambda:None
def forbidden(*args,**kwargs):raise AssertionError('No actual launch or Toolkit call is permitted')
creo_startup.launch_creo=forbidden
bridge.session_status=forbidden
server.startup=creo_startup.CreoStartup(root/'coordinator')
server.updates.start=lambda:None
server.mcp.run()
"""

        async def check():
            async with Client(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-c", bootstrap, str(self.fixture.root)],
                    cwd=startup_tests.ROOT,
                ),
                read_timeout_seconds=10,
            ) as client:
                retry, jobs = await asyncio.gather(
                    client.call_tool("creo_startup_status", {"retry": True}),
                    client.call_tool("creo_list_jobs", {}),
                )
                self.assertFalse(retry.is_error)
                self.assertFalse(jobs.is_error)
                for _ in range(30):
                    result = await client.call_tool("creo_startup_status", {})
                    self.assertFalse(result.is_error)
                    value = result.structured_content
                    self.assertEqual(json.loads(result.content[0].text), value)
                    if value["state"] not in creo_startup.ACTIVE:
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(value["state"], "selection_required")
                self.assertEqual(value["coordination_error"]["code"], "startup_state_unreadable")

        with patch.object(time, "monotonic", REAL_MONOTONIC):
            asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
