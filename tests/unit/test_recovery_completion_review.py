"""FEAT-018 batch B: the uncertain-job evidence summary.

The 0.19.3 report (A-P3) hit ``unknown_outcome`` after a watchdog timeout even
though the native run had finished. The caller then had to read the native
result, the checkpoint and the saved file separately before guessing. These
tests pin the bounded summary and, just as important, that it never claims
authority to accept a model state.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creo_mechdog import recovery


class CompletionReviewVerdictTests(unittest.TestCase):
    def test_successful_verified_save_with_a_dead_runner_is_likely_completed(self):
        review = recovery.completion_review(
            {"success": True, "saved_file_reloaded_and_verified": True, "revision": 7},
            None,
            False,
            True,
        )
        self.assertEqual(review["verdict"], "likely_completed")
        self.assertEqual(
            review["suggested_next_action"], "inspect_saved_file_then_reconcile_accept_live"
        )
        self.assertEqual(review["signals"]["reported_revision"], 7)

    def test_an_alive_runner_outranks_a_successful_native_result(self):
        review = recovery.completion_review(
            {"success": True, "saved_file_reloaded_and_verified": True}, None, True, False
        )
        self.assertEqual(review["verdict"], "still_running")
        self.assertEqual(review["suggested_next_action"], "wait_for_runner")

    def test_success_without_a_verified_reload_is_only_partially_confirmed(self):
        review = recovery.completion_review({"success": True}, None, False, True)
        self.assertEqual(review["verdict"], "partially_confirmed")
        self.assertEqual(
            review["suggested_next_action"], "inspect_saved_file_then_operator_reconciliation"
        )

    def test_a_failed_native_result_is_not_completed(self):
        review = recovery.completion_review({"success": False}, None, False, True)
        self.assertEqual(review["verdict"], "not_completed")
        self.assertEqual(review["suggested_next_action"], "operator_reconciliation")

    def test_no_evidence_stays_insufficient(self):
        review = recovery.completion_review(None, None, None, None)
        self.assertEqual(review["verdict"], "insufficient_evidence")
        self.assertEqual(review["suggested_next_action"], "operator_reconciliation")

    def test_the_checkpoint_can_supply_the_missing_signals(self):
        review = recovery.completion_review(
            None,
            {
                "success": True,
                "delivery_complete": True,
                "saved_file_reloaded_and_verified": True,
            },
            False,
            True,
        )
        self.assertEqual(review["verdict"], "likely_completed")
        self.assertTrue(review["signals"]["checkpoint_delivery_complete"])

    def test_the_review_never_authorizes_anything(self):
        for result in (
            {"success": True, "saved_file_reloaded_and_verified": True},
            {"success": False},
            None,
        ):
            with self.subTest(result=result):
                review = recovery.completion_review(result, None, False, True)
                self.assertTrue(review["read_only"])
                self.assertFalse(review["authorizes_replay"])
                self.assertFalse(review["authorizes_revision_change"])
                self.assertIn("creo_reconcile_model", review["note"])


class JobEvidenceIntegrationTests(unittest.TestCase):
    def _evidence(self, files: dict[str, object], model=None) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            for name, payload in files.items():
                (directory / name).write_text(json.dumps(payload), encoding="utf-8")
            manifest = {"job_id": "job123", "model_id": "model123"}
            return recovery.job_evidence(directory, manifest, model)

    def test_a_leftover_successful_native_result_is_summarized(self):
        evidence = self._evidence(
            {
                "native_result.json": {
                    "success": True,
                    "saved_file_reloaded_and_verified": True,
                    "revision": 3,
                }
            },
            model={"status": "ready", "revision": 3, "pending_job": None},
        )
        # Without a recorded runner identity the review cannot prove the runner
        # is gone, so it stops short of "likely completed".
        self.assertEqual(evidence["completion_review"]["verdict"], "partially_confirmed")
        self.assertIsNone(evidence["completion_review"]["signals"]["runner_alive"])
        self.assertTrue(evidence["native_result_present"])
        self.assertIn("completion_review", evidence["next_steps"])

    def test_a_recorded_dead_runner_upgrades_the_verdict(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "native_result.json").write_text(
                json.dumps(
                    {"success": True, "saved_file_reloaded_and_verified": True, "revision": 3}
                ),
                encoding="utf-8",
            )
            manifest = {
                "job_id": "job123",
                "model_id": "model123",
                "runner_identity": {"pid": 999999, "created": 123},
            }
            evidence = recovery.job_evidence(
                directory, manifest, {"status": "ready", "revision": 3, "pending_job": None}
            )
        self.assertFalse(evidence["completion_review"]["signals"]["runner_alive"])
        self.assertEqual(evidence["completion_review"]["verdict"], "likely_completed")

    def test_an_unreadable_native_result_degrades_without_claiming_success(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "native_result.json").write_text("{not json", encoding="utf-8")
            evidence = recovery.job_evidence(
                directory, {"job_id": "job123", "model_id": "model123"}, None
            )
        self.assertEqual(evidence["completion_review"]["verdict"], "insufficient_evidence")

    def test_an_oversized_native_result_is_not_read(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            path = directory / "native_result.json"
            with path.open("wb") as stream:
                stream.truncate(16 * 1024 * 1024 + 1)
            evidence = recovery.job_evidence(
                directory, {"job_id": "job123", "model_id": "model123"}, None
            )
        self.assertEqual(evidence["completion_review"]["verdict"], "insufficient_evidence")
        self.assertIsNone(evidence["completion_review"]["signals"]["native_result_success"])


if __name__ == "__main__":
    unittest.main()
