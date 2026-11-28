"""BUG-122: a measured host-kernel refusal stops a later surface_loft before the job.

Creo 10 reports `create_code=0` and then refuses the element-tree read (`-18`). BUG-120
published that observation as disclosure only, so every retry created an incomplete
feature and rolled the job back. Admission now refuses the same signature on the same
worker; unknown, foreign or transient observations keep the previous pass-through.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import bridge
from creo_mechdog import capabilities
from creo_mechdog import generic_bridge as general
from tests.unit import test_toolkit_channel as channel_tests

WORKER_SHA = "b95cd7c2655b0799bb8efb6f68e21ac891157af970b42d78c135f53e5326864a"


def identity(**feature):
    rel = feature.pop("release_numeric", 44)
    ev = feature.pop(
        "evidence",
        {
            "release_numeric": rel,
            "create_code": 0,
            "extract_code": -18,
            "feature_incomplete": True,
        },
    )
    entry = {
        "available": True,
        "state": "compiled",
        "kernel_completion": "unsupported",
        "worker_sha256": WORKER_SHA,
        "release_numeric": rel,
        "job_id": "be450d6a74bb4868acc1ddd3d897cd63",
        "observed_at": "2026-11-13T00:00:00+08:00",
        "evidence": ev,
    }
    entry.update(feature)
    return {
        "identity_status": "verified",
        "identity_source": "creo_worker.exe build-info",
        "worker_sha256": WORKER_SHA,
        "release_numeric": rel,
        "features": {"surface_loft": entry},
    }


def loft():
    return {"op": "surface_loft", "label": "loft_surface", "sections": ["loft_a", "loft_b"]}


class KernelAdmissionRules(unittest.TestCase):
    def test_measured_signature_is_refused(self):
        with self.assertRaisesRegex(ValueError, "refused before a job"):
            capabilities.require_kernel_completion([loft()], identity())

    def test_refusal_names_the_evidence_and_the_clearing_path(self):
        with self.assertRaises(ValueError) as caught:
            capabilities.require_kernel_completion([loft()], identity())
        text = str(caught.exception)
        for part in ("create_code=0", "extract_code=-18", WORKER_SHA, "worker SHA256"):
            self.assertIn(part, text)
        self.assertIn("No native job was queued", text)

    def test_supported_observation_passes_through(self):
        capabilities.require_kernel_completion(
            [loft()], identity(kernel_completion="supported", evidence={"create_code": 0})
        )

    def test_unknown_observation_passes_through(self):
        capabilities.require_kernel_completion(
            [loft()], identity(kernel_completion="unknown", evidence=None)
        )

    def test_transient_failure_without_the_kernel_signature_passes_through(self):
        for evidence in (
            {"create_code": -1, "extract_code": -18},
            {"create_code": 0, "extract_code": -1},
            {"create_code": 0},
            None,
            "not a dict",
        ):
            with self.subTest(evidence=evidence):
                capabilities.require_kernel_completion(
                    [loft()], identity(kernel_completion="unsupported", evidence=evidence)
                )

    def test_unverified_or_foreign_identity_passes_through(self):
        unverified = identity()
        unverified["identity_status"] = "unknown"
        capabilities.require_kernel_completion([loft()], unverified)
        capabilities.require_kernel_completion([loft()], {})
        capabilities.require_kernel_completion([loft()], None)

    def test_other_operations_never_consult_the_observation(self):
        capabilities.require_kernel_completion([{"op": "extrude"}], identity())

    def test_explicit_geometry_only_completion_bypasses_the_refusal(self):
        capabilities.require_kernel_completion(
            [{**loft(), "accept_unverified_completion": True}], identity(release_numeric=44)
        )

    def test_creo10_refuses_element_tree_even_with_accept_unverified_completion(self):
        creo10 = identity(release_numeric=42, kernel_completion="unknown", evidence=None)
        for op in (loft(), {**loft(), "accept_unverified_completion": True}):
            with self.assertRaisesRegex(ValueError, "resident_panel"):
                capabilities.require_kernel_completion([op], creo10)

    def test_an_unflagged_operation_in_the_same_plan_keeps_the_refusal(self):
        with self.assertRaisesRegex(ValueError, "refused before a job"):
            capabilities.require_kernel_completion(
                [{**loft(), "accept_unverified_completion": True}, loft()], identity()
            )


class ProjectionAdmitsTheRefusal(unittest.TestCase):
    def test_runtime_admission_is_published_when_the_signature_matches(self):
        families = {"surface_loft": {"available": True, "enabled": True}}
        projected = capabilities.project_worker_availability(
            families,
            identity(),
            {
                "kernel_completion": "unsupported",
                "worker_sha256": WORKER_SHA,
                "release_numeric": 42,
                "job_id": "j",
                "observed_at": "t",
                "evidence": {"create_code": 0, "extract_code": -18},
            },
        )
        entry = projected["surface_loft"]
        self.assertTrue(entry["available"])
        self.assertEqual(entry["runtime_admission"]["status"], "refused_before_job")
        self.assertEqual(entry["runtime_admission"]["extract_code"], -18)

    def test_a_supported_observation_publishes_no_admission_block(self):
        families = {"surface_loft": {"available": True, "enabled": True}}
        projected = capabilities.project_worker_availability(
            families, identity(), {"kernel_completion": "supported", "worker_sha256": WORKER_SHA}
        )
        self.assertNotIn("runtime_admission", projected["surface_loft"])


class SubmissionRefusesBeforeTheChannel(unittest.TestCase):
    setUp = channel_tests.ToolkitChannel.setUp

    def parsed_identity(self, worker_sha=WORKER_SHA):
        parsed = bridge._parse_worker_build_info(
            {
                "identity_schema": 1,
                "source_digest": "a" * 64,
                "features": {
                    "surface_loft": {
                        "available": True,
                        "state": "compiled",
                        "sdk_requirements": ["Probbl.h"],
                        "missing_sdk_requirements": [],
                    }
                },
            },
            worker_sha,
        )
        self.assertIsNotNone(parsed)
        return parsed

    def record(self, completion="unsupported", evidence=None):
        bridge.record_surface_loft_runtime(
            {
                "job_id": "measured_job",
                "result": {
                    "operations": [
                        {
                            "op": "surface_loft",
                            "kernel_completion": completion,
                            "kernel_evidence": evidence
                            if evidence is not None
                            else {"release_numeric": 42, "create_code": 0, "extract_code": -18},
                        }
                    ]
                },
            }
        )

    def test_surface_loft_is_refused_before_the_lock(self):
        raw = self.parsed_identity()
        with (
            patch.object(bridge, "worker_build_identity", return_value=raw),
            patch.object(bridge, "toolkit_lock") as lock,
        ):
            self.record()
            self.assertEqual(
                bridge.channel_health()["surface_loft_runtime"]["worker_sha256"], WORKER_SHA
            )
            with self.assertRaisesRegex(ValueError, "refused before a job"):
                general.submit([loft()])
            lock.assert_not_called()
        self.assertNotIn("kernel_completion", raw["features"]["surface_loft"])
        self.assertFalse((self.root / "jobs").exists())

    def test_foreign_worker_observation_does_not_block(self):
        recorded = self.parsed_identity()
        current = self.parsed_identity("b" * 64)
        with patch.object(bridge, "worker_build_identity", return_value=recorded):
            self.record()
        with (
            patch.object(bridge, "worker_build_identity", return_value=current),
            patch.object(bridge.subprocess, "Popen"),
        ):
            self.assertEqual(general.submit([loft()])["status"], "queued")
            self.assertEqual(
                bridge.surface_loft_admission_identity()["features"]["surface_loft"][
                    "kernel_completion"
                ],
                "unknown",
            )

    def test_supported_and_unknown_observations_pass(self):
        raw = self.parsed_identity()
        with (
            patch.object(bridge, "worker_build_identity", return_value=raw),
            patch.object(bridge.subprocess, "Popen"),
        ):
            self.assertEqual(
                bridge.surface_loft_admission_identity()["features"]["surface_loft"][
                    "kernel_completion"
                ],
                "unknown",
            )
            self.record(completion="supported")
            self.assertEqual(
                bridge.surface_loft_admission_identity()["features"]["surface_loft"][
                    "kernel_completion"
                ],
                "supported",
            )
            self.assertEqual(general.submit([loft()])["status"], "queued")
        self.assertNotIn("kernel_completion", raw["features"]["surface_loft"])

    def test_other_operations_still_reach_the_channel(self):
        with patch.object(bridge.subprocess, "Popen"):
            created = general.submit([{"op": "regenerate"}])
        self.assertEqual(created["status"], "queued")


if __name__ == "__main__":
    unittest.main()
