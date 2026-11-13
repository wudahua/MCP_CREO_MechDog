"""BUG-121: a plan that cannot change the model is admitted read-only.

A GUI edit and save between MCP jobs moves the saved baseline. Read-only reads
(export, tree dump, measurement) must keep working through that, while a writable
plan keeps the strict baseline compare and now names the action that unblocks it.
"""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import model_registry
from creo_mechdog.reconciliation import admission_failure_message
from tests.unit import test_toolkit_channel as channel_tests


class InspectionOnlyAdmission(unittest.TestCase):
    setUp = channel_tests.ToolkitChannel.setUp
    submit = channel_tests.ToolkitChannel.submit
    worker = channel_tests.ToolkitChannel.worker
    run_job = channel_tests.ToolkitChannel.run_job

    def ready_without_baseline(self) -> str:
        """A ready model whose checkpoint was never verified (no saved baseline)."""
        created = self.submit()
        self.run_job(created)
        model_id = created["model_id"]
        path = general.model_path(model_id)
        model = general.model_info(model_id)
        model.update(part_file=None, part_sha256=None)
        model_registry.write_model(path, model)
        return model_id

    def test_export_only_plan_is_admitted_without_a_saved_baseline(self):
        model_id = self.ready_without_baseline()
        created = general.submit(
            [{"op": "export", "format": "step"}], model_id=model_id, expected_revision=1
        )
        self.assertTrue(created["readonly"])
        self.assertEqual(created["readonly_source"], "inspection_only_plan")
        self.run_job(created)

    def test_expected_revision_stays_optional_for_the_downgraded_plan(self):
        model_id = self.ready_without_baseline()
        created = general.submit([{"op": "dump_tree", "feature": 3}], model_id=model_id)
        self.assertEqual(created["readonly_source"], "inspection_only_plan")
        self.run_job(created)

    def test_writable_plan_keeps_the_strict_baseline_compare(self):
        model_id = self.ready_without_baseline()
        with self.assertRaisesRegex(ValueError, "model_reconciliation_required"):
            general.submit([{"op": "regenerate"}], model_id=model_id, expected_revision=1)

    def test_explicit_readonly_still_limits_the_operation_set(self):
        model_id = self.ready_without_baseline()
        with self.assertRaisesRegex(ValueError, "Read-only requests may only inspect/export"):
            general.submit(
                [{"op": "regenerate"}], model_id=model_id, readonly=True, expected_revision=1
            )

    def test_writable_request_records_its_readonly_source(self):
        # An empty plan keeps the caller's flag; the downgrade never rewrites it.
        created = self.submit()
        self.assertFalse(created["readonly"])
        self.assertEqual(created["readonly_source"], "request")
        self.run_job(created)

    def test_a_new_model_is_never_downgraded(self):
        created = general.submit([])
        self.assertFalse(created["readonly"])
        self.run_job(created)


class AdmissionMessageHint(unittest.TestCase):
    def test_prefixed_message_names_the_action(self):
        text = admission_failure_message(
            "model_reconciliation_required: Saved feature/body count changed"
        )
        self.assertTrue(
            text.startswith("model_reconciliation_required: Saved feature/body count changed")
        )
        self.assertIn("creo_reconcile_model", text)
        self.assertIn("read-only reads", text)
        self.assertEqual(text.count("Action:"), 1)

    def test_other_messages_are_untouched(self):
        for text in (
            "Volume assertion failed",
            "model_reconciliation_required: no saved baseline; inspect creo_reconcile_model",
            "",
            None,
        ):
            self.assertEqual(admission_failure_message(text), text)

    def test_a_message_naming_the_tool_is_not_extended_twice(self):
        once = admission_failure_message("model_reconciliation_required: Saved model type changed")
        self.assertEqual(admission_failure_message(once), once)


class FailureMessageProjection(unittest.TestCase):
    setUp = channel_tests.ToolkitChannel.setUp
    submit = channel_tests.ToolkitChannel.submit

    def run_job(self, created):
        native = "model_reconciliation_required: Saved feature/body count changed"

        def run(*args, **kwargs):
            model = general.model_info(created["model_id"])
            part = general.model_path(created["model_id"]) / f"output/{model['model_name']}.prt.1"
            part.write_bytes(b"synthetic native result")
            bridge.write_json(
                bridge.job_path(created["job_id"]) / "native_result.json",
                {
                    "success": False,
                    "part_file": str(part),
                    "rollback_succeeded": True,
                    "inspection": {"volume_mm3": 10},
                    "message": native,
                },
            )
            return subprocess.CompletedProcess(args[0], 1)

        with (
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge.subprocess, "run", side_effect=run),
        ):
            bridge.run_job(created["job_id"])

    def test_failed_job_message_keeps_the_native_text_and_adds_the_action(self):
        created = self.submit()
        self.run_job(created)
        manifest = bridge.read_json(bridge.job_path(created["job_id"]) / "job.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("Saved feature/body count changed", manifest["message"])
        self.assertIn("creo_reconcile_model", manifest["message"])
        self.assertEqual(
            manifest["result"]["native_message"],
            "model_reconciliation_required: Saved feature/body count changed",
        )
        raw = bridge.read_json(bridge.job_path(created["job_id"]) / "native_result.json")
        self.assertEqual(
            raw["message"], "model_reconciliation_required: Saved feature/body count changed"
        )


if __name__ == "__main__":
    unittest.main()
