"""DEV-047 T07: one shared preview step; capture failure stays beside the save.

Offline coverage only. The native assertions read the sources that the single
translation unit (native/worker.cpp) compiles, so a second screenshot path that
bypasses the shared step fails here; nothing connects to Creo.
"""

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import model_registry
from creo_mechdog.preview import apply_preview_projection, normalize_preview

NATIVE = Path(__file__).resolve().parents[2] / "native"
SCREENSHOT_PATHS = ("worker.cpp", "generic.cpp", "drawing.cpp")


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def region(source: str, start: str, stop: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(stop, begin)]


class NativeSharedStep(unittest.TestCase):
    """Structural guard: both image paths go through native/preview.h."""

    def test_raster_call_lives_only_in_the_shared_step(self):
        shared = native_source("preview.h")
        self.assertEqual(shared.count("ProRasterFileWrite("), 1)
        for name in SCREENSHOT_PATHS:
            with self.subTest(path=name):
                self.assertNotIn("ProRasterFileWrite", native_source(name))

    def test_screenshot_paths_do_not_repeat_the_capture_sequence(self):
        # ProWindowRefresh is unique to the shared step; the display-only paths
        # (rollback, adoption, open_file) keep their own refit/repaint.
        for name in SCREENSHOT_PATHS:
            with self.subTest(path=name):
                self.assertNotIn("ProWindowRefresh", native_source(name))
        shared = native_source("preview.h")
        for token in (
            "ProWindowRefit(",
            "ProWindowRefresh(",
            "ProWindowRepaint(",
            "ProViewMatrixSet(",
            "ProRasterFileWrite(",
        ):
            with self.subTest(token=token):
                self.assertEqual(shared.count(token), 1)

    def test_export_branches_delegate_instead_of_repeating_the_sequence(self):
        for name, start, stop in (
            ("generic.cpp", 'if (format == "jpeg") {', '} else if (format == "stl")'),
            ("drawing.cpp", '} else if (format == "jpeg") {', "Drawing export supports PDF/JPEG"),
        ):
            with self.subTest(path=name):
                block = region(native_source(name), start, stop)
                self.assertIn("capture_preview(", block)
                for token in ("ProWindowRefit", "ProWindowRepaint", "ProViewMatrixSet"):
                    self.assertNotIn(token, block)

    def test_every_screenshot_site_uses_the_shared_capture(self):
        self.assertEqual(native_source("generic.cpp").count("capture_preview("), 2)
        self.assertEqual(native_source("drawing.cpp").count("capture_preview("), 1)
        self.assertEqual(native_source("worker.cpp").count("capture_preview("), 1)

    def test_automatic_preview_never_throws_or_fails_the_job(self):
        # The job preview records codes; only the requested export may fail.
        source = native_source("generic.cpp")
        block = region(source, '"display_preview"', 'log("BUILD_SUCCESS=1')
        self.assertIn("capture_preview(", block)
        self.assertNotIn("CK(", block)
        self.assertNotIn("throw ", block)
        self.assertIn('{"preview_code", preview.raster_code}', block)
        self.assertIn('{"preview", preview_json}', block)

    def test_both_paths_publish_the_raw_codes(self):
        generic = native_source("generic.cpp")
        self.assertEqual(generic.count('{"preview", preview_json}'), 2)
        drawing = native_source("drawing.cpp")
        self.assertIn('export_detail["preview_code"] = preview.raster_code', drawing)
        self.assertIn('export_detail["preview"] = preview_json', drawing)
        self.assertIn('plate_result["preview"] = preview_report', native_source("worker.cpp"))
        shared = native_source("preview.h")
        for step in (
            "display",
            "window_get",
            "window_model_get",
            "current_set",
            "current_get",
            "activate",
            "view_matrix_set",
            "repaint",
            "raster",
            "failed_step",
        ):
            with self.subTest(step=step):
                self.assertIn(f'"{step}"', shared)

    def test_the_confirmation_stage_records_the_real_filesystem_error(self):
        # BUG-088: after a zero raster code the probe must publish the path
        # shape, existence, size and the actual std::error_code.
        shared = native_source("preview.h")
        for token in (
            "preview_confirm_file",
            "file_check_absolute",
            "file_check_parent_exists",
            "file_check_exists",
            "file_check_regular",
            "file_check_code",
            "error.category().name()",
            "error.message()",
            "is_regular_file",
            "is_directory",
            '"file_check"',
            '"after_raster"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, shared)

    def test_only_a_missing_path_maps_to_not_found(self):
        shared = native_source("preview.h")
        block = region(shared, "if (error || outcome.file_bytes <= 0) {", "// One capture attempt.")
        self.assertIn("preview_is_missing(error)", block)
        self.assertIn("PRO_TK_E_NOT_FOUND", block)
        self.assertIn("PRO_TK_GENERAL_ERROR", block)
        # The previous blanket mapping reported every filesystem failure as a
        # missing file.
        self.assertNotIn("error ? PRO_TK_E_NOT_FOUND", shared)

    def test_the_probe_does_not_retry_the_capture_or_the_job(self):
        shared = native_source("preview.h")
        probe = region(shared, "static void preview_confirm_file", "// One capture attempt.")
        self.assertNotIn("ProRasterFileWrite", probe)
        self.assertNotIn("sleep", probe)
        self.assertLess(
            shared.index("code = ProRasterFileWrite"), shared.index("preview_confirm_file(outcome)")
        )

    def test_the_step_checks_the_target_window_and_file_size(self):
        shared = native_source("preview.h")
        for token in (
            "ProWindowMdlGet",
            "ProWindowCurrentGet",
            "ProViewMatrixGet",
            "file_size",
            "preview_written",
            "output_file",
        ):
            with self.subTest(token=token):
                self.assertIn(token, shared)


class PreviewProjection(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_preview_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "output").mkdir()
        self.image = self.root / "output" / "preview.jpg"
        self.image.write_bytes(b"\xff\xd8\xff preview bytes")

    def native_block(self, status: str = "written", raster: int = 0) -> dict:
        return {
            "status": status,
            "path": str(self.image),
            "bytes": 16,
            "window": 3,
            "window_matches_model": True,
            "current_window_matches": True,
            "view_matrix_matches": True,
            "codes": {
                "display": 0,
                "window_get": 0,
                "window_model_get": 0,
                "current_set": 0,
                "current_get": 0,
                "activate": 0,
                "view_matrix_set": 0,
                "view_matrix_get": 0,
                "refit": 0,
                "refresh": 0,
                "repaint": 0,
                "raster": raster,
            },
            "failed_step": None if status == "written" else "raster",
            "failed_code": None if status == "written" else raster,
        }

    def test_written_preview_keeps_the_file_and_codes(self):
        result = {"success": True, "preview_code": 0, "preview": self.native_block()}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "written")
        self.assertTrue(block["file_verified"])
        self.assertEqual(block["codes"]["raster"], 0)
        self.assertEqual(block["window"], 3)
        self.assertEqual(block["source"], "native")

    def test_failed_preview_is_never_upgraded_by_an_existing_file(self):
        result = {"success": True, "preview_code": -5, "preview": self.native_block("failed", -5)}
        apply_preview_projection(result, directory=self.root)
        self.assertEqual(result["preview_status"], "failed")
        self.assertIsNone(result["preview_file"])
        self.assertEqual(result["preview_code"], -5)
        self.assertEqual(result["preview"]["failed_step"], "raster")

    def test_claimed_written_image_must_exist_and_be_non_empty(self):
        self.image.unlink()
        result = {"success": True, "preview": self.native_block()}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "output_file_verification")
        self.assertFalse(block["file_verified"])

        self.image.write_bytes(b"")
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "failed")

    def test_legacy_raster_code_without_native_block(self):
        result = {"success": True, "preview_code": 0}
        apply_preview_projection(result, directory=self.root)
        self.assertEqual(result["preview"]["status"], "written")
        self.assertEqual(result["preview"]["source"], "legacy_result")
        self.assertEqual(result["preview_file"], str(self.image))

    def test_unattempted_preview_is_not_reported_as_a_failure(self):
        result = {"success": False, "preview_code": -1}
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "not_attempted")

    def test_failed_code_on_a_saved_job_stays_failed(self):
        result = {"success": True, "preview_code": -3}
        self.assertEqual(normalize_preview(result, directory=self.root)["status"], "failed")

    def test_no_preview_evidence_projects_nothing(self):
        result = {"success": True}
        self.assertIsNone(normalize_preview(result, directory=self.root))
        apply_preview_projection(result, directory=self.root)
        self.assertNotIn("preview_status", result)
        self.assertNotIn("preview", result)

    def test_projection_keeps_the_save_outcome_untouched(self):
        result = {
            "success": True,
            "saved_file_reloaded_and_verified": True,
            "sha256": "a" * 64,
            "revision": 7,
            "preview_code": -5,
            "preview": self.native_block("failed", -5),
        }
        before = copy.deepcopy(result)
        apply_preview_projection(result, directory=self.root)
        for key in ("success", "saved_file_reloaded_and_verified", "sha256", "revision"):
            with self.subTest(key=key):
                self.assertEqual(result[key], before[key])

    def test_export_operation_keeps_one_result_with_preview_codes(self):
        result = {
            "success": True,
            "preview_code": 0,
            "preview": self.native_block(),
            "operations": [
                {
                    "op": "export",
                    "index": 0,
                    "label": "",
                    "succeeded": True,
                    "execution_status": "succeeded",
                    "effect_status": "committed",
                    "file": str(self.image),
                    "preview_code": 0,
                    "preview": self.native_block(),
                }
            ],
        }
        apply_preview_projection(result, directory=self.root)
        self.assertEqual(len(result["operations"]), 1)
        compact = bridge.compact_job({"status": "succeeded", "kind": "generic", "result": result})
        self.assertEqual(len(compact["result"]["operations"]), 1)
        self.assertEqual(compact["result"]["operations"][0]["preview_code"], 0)
        self.assertEqual(compact["result"]["preview_status"], "written")
        self.assertEqual(compact["result"]["preview"]["codes"]["raster"], 0)


class PreviewFileConfirmation(unittest.TestCase):
    """BUG-088: the raster stage and the filesystem stage stay distinguishable.

    Every fixture is isolated: a private temporary directory, no Creo, no job.
    A zero raster code is never enough on its own to report written.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t08a_preview_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "output").mkdir()
        self.image = self.root / "output" / "preview.jpg"

    def native(self, **overrides) -> dict:
        block = {
            "status": "written",
            "path": str(self.image),
            "bytes": 16,
            "codes": {"display": 0, "refit": 0, "repaint": 0, "raster": 0},
            "failed_step": None,
            "failed_code": None,
            "file_check": {
                "stage": "after_raster",
                "absolute": True,
                "parent_exists": True,
                "exists": True,
                "is_file": True,
                "size": 16,
                "error_code": 0,
                "error_category": None,
                "error_message": None,
            },
        }
        block.update(overrides)
        return block

    def test_raster_failure_never_reports_a_file_check(self):
        # Stage 1 fails: there is no file to confirm, so the block stays null.
        result = {
            "success": True,
            "preview_code": -5,
            "preview": self.native(
                status="failed",
                bytes=-1,
                failed_step="raster",
                failed_code=-5,
                file_check=None,
                codes={"display": 0, "refit": 0, "repaint": 0, "raster": -5},
            ),
        }
        block = normalize_preview(result, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "raster")
        self.assertEqual(block["failed_code"], -5)
        self.assertIsNone(block["file_check"])

    def test_missing_file_after_a_zero_raster_code_keeps_the_real_error(self):
        check = {
            "stage": "after_raster",
            "absolute": True,
            "parent_exists": True,
            "exists": False,
            "is_file": False,
            "size": -1,
            "error_code": 2,
            "error_category": "system",
            "error_message": "The system cannot find the file specified.",
        }
        preview = self.native(
            status="failed", bytes=-1, failed_step="output_file", failed_code=-4, file_check=check
        )
        block = normalize_preview({"success": True, "preview": preview}, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "output_file")
        self.assertEqual(block["failed_code"], -4)
        self.assertEqual(block["file_check"]["error_code"], 2)
        self.assertEqual(block["file_check"]["error_category"], "system")
        self.assertFalse(block["file_check"]["exists"])
        self.assertEqual(block["verification_error"], "FileNotFoundError")

    def test_empty_file_is_failed_even_though_the_path_exists(self):
        self.image.write_bytes(b"")
        preview = self.native(bytes=0, failed_step="output_file", failed_code=-1)
        block = normalize_preview({"success": True, "preview": preview}, directory=self.root)
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["bytes"], 0)
        # The native size claim is preserved; it is not rewritten by the probe.
        self.assertEqual(block["file_check"]["size"], 16)
        self.assertFalse(block["file_verified"])
        self.assertIsNone(block["verification_error"])

    def test_a_failed_stat_is_reported_without_an_invented_code(self):
        check = self.native()["file_check"] | {
            "exists": False,
            "size": -1,
            "error_code": 5,
            "error_category": "system",
            "error_message": "Access is denied.",
        }
        preview = self.native(file_check=check)
        with patch.object(Path, "stat", side_effect=PermissionError(13, "Access is denied")):
            block = normalize_preview({"success": True, "preview": preview}, directory=self.root)
        # The native says written but the file cannot be confirmed: the
        # projection downgrades it and reports the probe failure instead of a
        # code borrowed from the raster call.
        self.assertEqual(block["status"], "failed")
        self.assertEqual(block["failed_step"], "output_file_verification")
        self.assertIsNone(block["failed_code"])
        self.assertEqual(block["file_check"]["error_code"], 5)
        self.assertEqual(block["verification_error"], "PermissionError")

    def test_a_confirmed_file_stays_written_and_keeps_the_probe(self):
        self.image.write_bytes(b"confirmed preview bytes")
        preview = self.native()
        block = normalize_preview(
            {"success": True, "preview_code": 0, "preview": preview}, directory=self.root
        )
        self.assertEqual(block["status"], "written")
        self.assertTrue(block["file_verified"])
        self.assertEqual(block["file_check"]["stage"], "after_raster")
        self.assertIsNone(block["verification_error"])


class JobLevelDecoupling(unittest.TestCase):
    """A failed capture beside a verified save keeps the job succeeded."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="t07_job_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, name, value in (
            (bridge, "ROOT", self.root),
            (bridge, "JOBS", self.root / "jobs"),
            (general, "MODELS", self.root / "models"),
        ):
            stack.enter_context(patch.object(obj, name, value))
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        self.model_id = "d" * 32
        path = general.model_path(self.model_id)
        (path / "output").mkdir(parents=True)
        self.part = path / "output" / "disk.prt.1"
        self.part.write_bytes(b"native part bytes")
        model = {
            "model_id": self.model_id,
            "model_name": "disk",
            "revision": 3,
            "status": "ready",
            "model_type": "part",
            "aliases": {},
            "inspection": {"features": [], "bodies": [{"id": 1}]},
            "part_file": str(self.part),
            "output_directory": str(path / "output"),
        }
        model_registry.write_model(path, model)
        self.job_id = "e" * 32
        directory = bridge.job_path(self.job_id)
        (directory / "output").mkdir(parents=True)
        self.directory = directory
        self.request = {
            "new": False,
            "model": {
                key: model[key] for key in ("model_id", "model_name", "model_type", "revision")
            },
            "operations": [{"op": "regenerate"}],
            "readonly": False,
        }
        bridge.write_json(directory / "request.json", self.request)
        self.manifest = {
            "job_id": self.job_id,
            "kind": "generic",
            "model_id": self.model_id,
            "status": "queued",
        }
        bridge.write_json(directory / "job.json", self.manifest)

    def run_worker(self, result: dict) -> dict:
        def fake_run(*args, **kwargs):
            bridge.write_json(self.directory / "native_result.json", result)
            return subprocess.CompletedProcess([], 0)

        with (
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge, "note_native_outcome", return_value=None),
            patch.object(bridge, "config", return_value={}),
        ):
            general.run_generic_job(self.job_id, copy.deepcopy(self.manifest))
        return bridge.read_json(self.directory / "job.json")

    def plan_result(self, preview: dict, preview_code: int) -> dict:
        return {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "inspection": {"features": [], "bodies": [{"id": 1}]},
            "preview_code": preview_code,
            "preview": preview,
            "operations": [
                {
                    "op": "regenerate",
                    "index": 0,
                    "label": "",
                    "succeeded": True,
                    "execution_status": "succeeded",
                    "effect_status": "committed",
                }
            ],
        }

    def failed_preview(self) -> dict:
        return {
            "status": "failed",
            "path": str(self.directory / "output" / "preview.jpg"),
            "bytes": 0,
            "window": -1,
            "window_matches_model": False,
            "current_window_matches": False,
            "view_matrix_matches": False,
            "codes": {"display": 0, "window_get": -4, "refit": 0, "repaint": 0, "raster": -5},
            "failed_step": "raster",
            "failed_code": -5,
        }

    def test_preview_failure_does_not_fail_the_saved_job(self):
        manifest = self.run_worker(self.plan_result(self.failed_preview(), -5))
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 4)
        self.assertTrue(manifest["result"]["saved_file_reloaded_and_verified"])
        self.assertEqual(manifest["result"]["preview_status"], "failed")
        self.assertIsNone(manifest["result"]["preview_file"])
        self.assertEqual(manifest["result"]["preview"]["codes"]["raster"], -5)
        self.assertEqual(manifest["result"]["preview"]["codes"]["window_get"], -4)
        self.assertEqual(manifest["result"]["operations"][0]["effect_status"], "committed")

    def test_written_preview_is_reported_beside_the_saved_model(self):
        image = self.directory / "output" / "preview.jpg"
        image.write_bytes(b"\xff\xd8\xff real capture")
        preview = self.failed_preview()
        preview.update(
            status="written", failed_step=None, failed_code=None, bytes=len(image.read_bytes())
        )
        manifest = self.run_worker(self.plan_result(preview, 0))
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["result"]["preview_status"], "written")
        self.assertEqual(manifest["result"]["preview_file"], str(image))
        compact = bridge.compact_job(manifest)
        self.assertEqual(compact["result"]["preview"]["status"], "written")

    def test_save_failure_is_not_masked_by_a_failed_preview(self):
        image = self.directory / "output" / "preview.jpg"
        image.write_bytes(b"\xff\xd8\xff stale capture")
        result = self.plan_result(self.failed_preview(), -5)
        result.update(success=False, saved_file_reloaded_and_verified=False, message="save failed")
        result.pop("inspection", None)
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["result"]["preview_status"], "failed")
        self.assertIn("save failed", manifest["message"])


if __name__ == "__main__":
    unittest.main()
