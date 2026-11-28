"""Regression tests for BUG-198..BUG-201 and FEAT-093 (2026-11-27 feedback)."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

import bridge
import server
from creo_mechdog import (
    adoption,
    creo_startup,
    desktop_worker,
    model_queries,
    operation_results,
    panel_session_guard,
)
from creo_mechdog import generic_bridge as general
from creo_mechdog import reconciliation as rec
from creo_mechdog.schema import OPERATIONS, dump_plan_operations, validate_operations


def _win_err(winerror: int) -> PermissionError:
    err = PermissionError(f"simulated WinError {winerror}")
    err.winerror = winerror
    return err


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class Bug198JsonReplaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bug198_")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows WinError 5 semantics")
    def test_winerror5_retries_when_destination_missing_or_stat_locked(self):
        target = self.root / "job.json"
        calls = 0

        def flaky_replace(temp: Path, dest: Path) -> None:
            nonlocal calls
            calls += 1
            if calls <= 2:
                raise _win_err(5)
            os.replace(temp, dest)

        with (
            patch.object(bridge, "_atomic_replace", side_effect=flaky_replace),
            patch.object(bridge.time, "sleep"),
        ):
            bridge.write_json(target, {"status": "queued"})
        self.assertEqual(calls, 3)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["status"], "queued")

        # Also verify transient PermissionError during stat() does NOT abort retries.
        calls = 0
        with (
            patch.object(bridge, "_atomic_replace", side_effect=flaky_replace),
            patch.object(Path, "stat", side_effect=_win_err(5)),
            patch.object(bridge.time, "sleep"),
        ):
            bridge.write_json(target, {"status": "running"})
        self.assertEqual(calls, 3)

    @unittest.skipUnless(os.name == "nt", "Windows read-only semantics")
    def test_real_readonly_temp_is_not_retried(self):
        target = self.root / "out.json"
        temp = self.root / ".ro.tmp"
        temp.write_text("{}", encoding="utf-8")
        temp.chmod(stat.S_IREAD)
        try:
            with (
                patch.object(bridge, "_atomic_replace", side_effect=_win_err(5)) as replace,
                patch.object(bridge.time, "sleep") as sleep,
            ):
                with self.assertRaises(PermissionError):
                    bridge._replace_json(temp, target)
            self.assertEqual(replace.call_count, 1)
            sleep.assert_not_called()
        finally:
            temp.chmod(stat.S_IWRITE | stat.S_IREAD)

    @unittest.skipUnless(os.name == "nt", "Windows unlink retry semantics")
    def test_unlink_with_retry_cleans_transient_locked_temp(self):
        temp = self.root / ".locked.tmp"
        temp.write_text("{}", encoding="utf-8")
        orig_unlink = Path.unlink
        attempts = 0

        def flaky_unlink(self_path: Path, missing_ok: bool = False):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise _win_err(5)
            return orig_unlink(self_path, missing_ok=missing_ok)

        with (
            patch.object(Path, "unlink", autospec=True, side_effect=flaky_unlink),
            patch.object(bridge.time, "sleep"),
        ):
            bridge._unlink_with_retry(temp)
        self.assertEqual(attempts, 3)
        self.assertFalse(temp.exists())


class Bug199LifecycleAndRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bug199_")
        self.root = Path(self.tmp.name)
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        self.orig = (bridge.ROOT, bridge.JOBS, general.MODELS)
        bridge.ROOT = self.root
        bridge.JOBS = self.root / "jobs"
        general.MODELS = self.root / "models"

    def tearDown(self):
        bridge.ROOT, bridge.JOBS, general.MODELS = self.orig
        self.tmp.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows Job Object detach semantics")
    def test_spawn_detached_runner_uses_explorer_when_in_job_and_verifies_handle(self):
        log_path = self.root / "runner.log"
        with (
            patch.object(bridge, "_process_in_job", return_value=True),
            patch.object(bridge, "config", return_value={"creo_worker_launch": "auto"}),
            patch.object(desktop_worker, "launch_detached_command") as launch,
            log_path.open("ab") as log_file,
        ):
            proc, detached = bridge.spawn_detached_runner(
                ["python.exe", str(self.root / "bridge.py"), "run-job", "a" * 32],
                cwd=self.root,
                log_file=log_file,
            )
        self.assertIsNone(proc)
        self.assertTrue(detached)
        launch.assert_called_once()
        cmd = launch.call_args.args[0]
        self.assertIn("--log-file", cmd)

        # If Explorer fails and Popen child remains inside a Job Object, detached=False.
        fake_proc = MagicMock()
        fake_proc._handle = 9999

        def check_in_job(handle=None):
            return True

        with (
            patch.object(bridge, "_process_in_job", side_effect=check_in_job),
            patch.object(bridge, "config", return_value={"creo_worker_launch": "direct"}),
            patch.object(bridge, "_REAL_POPEN", return_value=fake_proc) as real_popen,
            log_path.open("ab") as log_file,
        ):
            proc2, detached2 = bridge.spawn_detached_runner(
                ["python.exe", str(self.root / "bridge.py"), "run-job", "a" * 32],
                cwd=self.root,
                log_file=log_file,
                popen=real_popen,
            )
        self.assertIs(proc2, fake_proc)
        self.assertFalse(detached2)

    @unittest.skipUnless(os.name == "nt", "Windows Job Object detach semantics")
    def test_replaced_default_process_factory_never_launches_via_explorer(self):
        command = ["python.exe", str(self.root / "bridge.py"), "run-job", "a" * 32]
        with (
            patch.dict(os.environ, {"MECHDOG_DISABLE_DESKTOP_DETACH": "0"}),
            patch.object(bridge, "_process_in_job", return_value=True),
            patch.object(bridge, "config", return_value={"creo_worker_launch": "auto"}),
            patch.object(bridge.subprocess, "Popen") as factory,
            patch.object(desktop_worker, "launch_detached_command") as launch,
            (self.root / "runner.log").open("ab") as log_file,
        ):
            proc, _ = bridge.spawn_detached_runner(command, cwd=self.root, log_file=log_file)
        self.assertIs(proc, factory.return_value)
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args, (command,))
        launch.assert_not_called()

    def test_explorer_shell_rejects_zero_tid_as_desktop_unverified(self):
        fake_desktop = MagicMock()
        fake_desktop.HWND = 65856
        fake_app = MagicMock()
        fake_app.Windows.return_value.FindWindowSW.return_value = fake_desktop
        with (
            patch.object(desktop_worker.pythoncom, "CoInitialize"),
            patch.object(desktop_worker.pythoncom, "CoUninitialize"),
            patch.object(desktop_worker.win32com.client, "Dispatch", return_value=fake_app),
            patch.object(
                desktop_worker.win32process,
                "GetWindowThreadProcessId",
                return_value=(0, 123456),
            ),
        ):
            with self.assertRaisesRegex(desktop_worker.DesktopUnavailable, "desktop"):
                with desktop_worker._explorer_shell():
                    pass

    def test_cancel_job_uses_runner_identity_pid_and_handles_128_when_dead(self):
        job_id = "c" * 32
        model_id = "d" * 32
        jdir = self.root / "jobs" / job_id
        _write_json(
            jdir / "job.json",
            {
                "job_id": job_id,
                "model_id": model_id,
                "status": "queued",
                "stage": "waiting_for_channel",
                "worker_started": None,
                "runner_identity": {"pid": 31572, "created": 134402135661345989},
            },
        )
        _write_json(jdir / "request.json", {"new": False, "model": {"model_id": model_id}})
        _write_json(
            self.root / "models" / model_id / "model.json",
            {
                "model_id": model_id,
                "model_name": "m1",
                "revision": 1,
                "status": "ready",
                "pending_job": job_id,
                "part_file": None,
            },
        )
        # Stale channel claim points at a different PID (28164).
        _write_json(
            self.root / bridge.CHANNEL_CLAIM_FILE,
            {"job_id": job_id, "runner_pid": 28164},
        )
        with (
            patch.object(
                general,
                "_terminate_process_tree",
                return_value={"attempted": True, "pid": 31572, "returncode": 128},
            ) as kill,
            patch.object(general, "_live_job_owners", return_value=[]),
            patch.object(bridge.os, "name", "nt"),
        ):
            res = general.cancel_job(job_id)
        kill.assert_called_once_with(31572)
        self.assertTrue(res["cancelled"])
        self.assertEqual(res["status"], "cancelled")
        self.assertTrue(res["termination"]["already_exited"])
        model_after = json.loads((self.root / "models" / model_id / "model.json").read_text())
        self.assertIsNone(model_after["pending_job"])
        self.assertFalse((self.root / bridge.CHANNEL_CLAIM_FILE).exists())

    def test_reconcile_owners_proves_stopped_when_worker_started_is_none_and_no_artifacts(self):
        job_id = "e" * 32
        jdir = self.root / "jobs" / job_id
        _write_json(
            jdir / "job.json",
            {
                "job_id": job_id,
                "status": "queued",
                "stage": "waiting_for_channel",
                "worker_started": None,
                "runner_identity": {"pid": 31572, "created": 123456},
                "created_at": bridge.now(),
            },
        )
        with patch.object(
            rec, "process_identity", side_effect=lambda pid: {"pid": pid, "alive": False}
        ):
            owners = rec._owners(job_id)
        self.assertTrue(owners["runner"]["stopped"])
        self.assertTrue(owners["worker"]["stopped"])
        self.assertTrue(owners["stopped"])

    def test_confirm_panel_closed_allowed_when_running_job_owners_are_recorded_and_dead(self):
        job_id = "f" * 32
        model_id = "1" * 32
        jdir = self.root / "jobs" / job_id
        out_dir = self.root / "models" / model_id / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            jdir / "job.json",
            {
                "job_id": job_id,
                "model_id": model_id,
                "kind": "generic",
                "status": "running",
                "stage": "panel_macro_submit",
                "worker_started": True,
                "runner_identity": {"pid": 18972, "created": 111},
                "created_at": bridge.now(),
            },
        )
        _write_json(jdir / "request.json", {"new": False, "model": {"model_id": model_id}})
        _write_json(jdir / "native_owner.json", {"pid": 14872, "created": 222})
        _write_json(
            self.root / "models" / model_id / "model.json",
            {
                "model_id": model_id,
                "model_name": "bulb",
                "revision": 1,
                "status": "unknown_outcome",
                "pending_job": job_id,
                "part_file": None,
                "output_directory": str(out_dir),
            },
        )
        panel_session_guard.reserve(
            job_id,
            nonce="n" * 32,
            profile_id="creo10-bbl-1",
            mode="certified",
            model_id=model_id,
            root=self.root,
        )
        with (
            patch.object(bridge, "config", return_value={}),
            patch.object(rec, "_deployment", return_value={"mode": "fixture"}),
            patch.object(
                rec, "process_identity", side_effect=lambda pid: {"pid": pid, "alive": False}
            ),
        ):
            inspected = rec.inspect(model_id)
            self.assertTrue(inspected["actions"]["confirm_panel_closed"]["available"])
            retired = rec.apply(
                model_id,
                "confirm_panel_closed",
                inspected["revision"],
                inspected["pending_job"],
                inspected["evidence_token"],
                "dead_owners_panel_confirm",
                confirm_panel_closed=True,
            )
        self.assertEqual(retired["panel_session_guard"]["state"], "retired")
        self.assertIsNone(panel_session_guard.inspect(self.root))

    def test_startup_classifies_panel_session_locked_separately(self):
        coord_dir = self.root / "startup"
        coord_dir.mkdir()
        startup = creo_startup.CreoStartup(directory=coord_dir)
        locked = panel_session_guard.PanelSessionLocked(
            "panel open", {"job_id": "a" * 32, "model_id": "b" * 32}
        )
        settings = creo_startup.Settings(
            executable=Path("C:/Creo/parametric.exe"),
            psf=Path("C:/Creo/parametric.psf"),
            auto_start=False,
            timeout=10,
            selected=False,
        )
        with (
            patch.object(creo_startup.Settings, "load", return_value=settings),
            patch.object(creo_startup, "coordination_lock", side_effect=locked),
        ):
            startup._run(retry=False)
        status = startup.status()
        self.assertEqual(status["state"], "panel_session_locked")
        self.assertEqual(status["panel_session_guard"]["model_id"], "b" * 32)
        self.assertIn("b" * 32, status["next_steps"][0])
        with (
            patch.object(creo_startup.Settings, "load", return_value=settings),
            patch.object(creo_startup, "process_snapshot", return_value={}),
            patch.object(bridge, "session_status", side_effect=locked),
        ):
            explicit = startup.session_status()
        self.assertEqual(explicit["connection_state"], "panel_session_locked")
        self.assertEqual(explicit["startup"]["next_steps"], status["next_steps"])
        self.assertFalse(explicit["live_probe"]["performed"])

    def test_get_job_exposes_owner_liveness_for_dead_runner(self):
        job_id = "2" * 32
        jdir = self.root / "jobs" / job_id
        _write_json(
            jdir / "job.json",
            {
                "job_id": job_id,
                "kind": "generic",
                "status": "queued",
                "stage": "waiting_for_channel",
                "worker_started": False,
                "runner_identity": {"pid": 31572, "created": 12345},
                "timeout_seconds": 600,
                "created_at": bridge.now(),
            },
        )
        with (
            patch.object(bridge, "config", return_value={}),
            patch.object(bridge, "process_identity", return_value=None),
        ):
            compact = bridge.get_job(job_id, detail="compact")
        self.assertTrue(compact["owner_liveness"]["all_recorded_owners_dead"])
        self.assertFalse(compact["owner_liveness"]["runner_alive"])
        self.assertIn("creo_cancel_job", compact["owner_liveness"]["next_step"])


class Feat093AndBug200And201Tests(unittest.TestCase):
    def test_extrude_depth2_schema_and_cut_volume_check(self):
        ops = dump_plan_operations(
            OPERATIONS.validate_python(
                [
                    {
                        "op": "extrude",
                        "label": "asym_boss",
                        "sketch": "sk1",
                        "depth": 8.4,
                        "depth2": 1.0,
                        "mode": "add",
                        "direction": "positive",
                    }
                ]
            )
        )
        self.assertEqual(ops[0]["depth2"], 1.0)
        with self.assertRaisesRegex(ValueError, "symmetric"):
            OPERATIONS.validate_python(
                [
                    {
                        "op": "extrude",
                        "label": "bad_sym",
                        "sketch": "sk1",
                        "depth": 10.0,
                        "depth2": 2.0,
                        "direction": "symmetric",
                    }
                ]
            )
        with self.assertRaisesRegex(ValueError, "blind"):
            OPERATIONS.validate_python(
                [
                    {
                        "op": "extrude",
                        "label": "bad_thru",
                        "sketch": "sk1",
                        "mode": "cut",
                        "depth_type": "through_all",
                        "depth2": 2.0,
                    }
                ]
            )

        native = {
            "success": True,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk1",
                    "profile": {"material_area_mm2": 100.0},
                },
                {
                    "op": "extrude",
                    "label": "cut1",
                    "material_removed_mm3": 940.0,
                    "extrude_depth": {
                        "effective_depth_type": "blind",
                        "effective_depth_mm": 8.4,
                        "effective_depth2_mm": 1.0,
                    },
                },
            ],
        }
        annotated = operation_results.annotate_native_result(
            native,
            readonly=False,
            inputs=[
                {"op": "sketch", "label": "sk1"},
                {"op": "extrude", "label": "cut1", "sketch": "sk1", "mode": "cut"},
            ],
        )
        chk = annotated["operations"][1]["cut_volume_check"]
        self.assertAlmostEqual(chk["effective_depth_mm"], 9.4)
        self.assertAlmostEqual(chk["expected_prism_volume_mm3"], 940.0)
        self.assertAlmostEqual(chk["removal_ratio"], 1.0)

    def test_adaptive_utility_worker_timeout(self):
        with patch.object(bridge, "config", return_value={}):
            small = bridge.utility_worker_timeout_seconds(file_size_bytes=1024, feature_count=10)
            large = bridge.utility_worker_timeout_seconds(
                file_size_bytes=6_051_648, feature_count=589
            )
        self.assertEqual(small, 300)
        self.assertGreaterEqual(large, 414)
        with self.assertRaisesRegex(ValueError, "timeout_seconds"):
            bridge.utility_worker_timeout_seconds(timeout_seconds=10)

    def test_adoption_records_worker_terminated_on_timeout(self):
        with tempfile.TemporaryDirectory(prefix="bug200_") as tmp:
            jdir = Path(tmp)
            _write_json(jdir / "request.json", {"adoption": {"action": "apply"}})
            manifest = {"job_id": "a" * 32, "model_id": "b" * 32}
            with (
                patch.object(bridge, "build_native", return_value=jdir / "creo_worker.exe"),
                patch.object(bridge, "native_environment", return_value={}),
                patch.object(
                    adoption.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired("creo_worker.exe", 300),
                ),
            ):
                with self.assertRaises(subprocess.TimeoutExpired):
                    adoption._native(jdir, manifest)
            self.assertTrue(manifest["worker_terminated_on_timeout"])

    def test_capabilities_callback_consistency_and_ux_hints(self):
        artifacts = {"artifact_status": "prepared", "registry_file": "x"}
        cached = {
            "readiness": "ready",
            "reason": "live_identity_verified",
            "next_action": None,
            "checked_at": "2026-11-28T00:00:00Z",
        }
        with (
            patch.object(server, "callback_setup_status", return_value=artifacts),
            patch.object(bridge, "callback_admission_status", return_value=cached),
            patch.object(bridge, "surface_loft_admission_identity", return_value={}),
            patch.object(bridge, "channel_health", return_value={}),
            patch.object(server.seeds, "list_seeds", return_value=[]),
            patch.object(server.updates, "snapshot", return_value={}),
        ):
            payload = server._capabilities_payload([])
        self.assertEqual(payload["direct_blend_callback"]["readiness"], "ready")
        self.assertEqual(
            payload["families"]["loft"]["runtime_admission"]["callback_readiness"], "ready"
        )

        with (
            patch.object(server.startup, "status", return_value={"coordinator_running": True}),
            patch.object(bridge, "callback_status") as cb_status,
        ):
            cb = asyncio.run(server.creo_callback_status())
        cb_status.assert_not_called()
        self.assertEqual(cb["readiness"], "unknown")
        self.assertEqual(cb["reason"], "startup_in_progress")
        self.assertTrue(cb["startup_in_progress"])
        self.assertEqual(cb["readiness_phase"], "starting")

        with self.assertRaisesRegex(ValidationError, "min.*max"):
            OPERATIONS.validate_python(
                [
                    {
                        "op": "sketch",
                        "label": "sk1",
                        "plane": "XY",
                        "entities": [
                            {
                                "type": "rectangle",
                                "name": "r1",
                                "corner1": [0, 0],
                                "corner2": [10, 10],
                            }
                        ],
                    }
                ]
            )
        with self.assertRaisesRegex(ValueError, "single-point datum_points"):
            validate_operations(
                [
                    {
                        "op": "datum_plane",
                        "label": "pl1",
                        "reference": {"kind": "through_points", "points": ["p1", "p2", "p3"]},
                    }
                ]
            )
        legacy = model_queries.qualify_bounding_box(
            {"bounding_box_mm": {"min": [0, 0, 0], "max": [1, 1, 1]}}
        )
        self.assertIn("refresh_hint", legacy["bounding_box_status"])


if __name__ == "__main__":
    unittest.main()
