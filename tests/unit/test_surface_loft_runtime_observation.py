"""BUG-120: disclosure-only kernel completion observations."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bridge
from creo_mechdog.capabilities import project_worker_availability

WORKER_SHA = "a" * 64
OTHER_SHA = "b" * 64


def _identity(sha: str = WORKER_SHA) -> dict:
    return {
        "identity_status": "verified",
        "identity_source": "worker_self_report",
        "source_digest": "c" * 64,
        "worker_sha256": sha,
        "features": {
            "surface_loft": {
                "available": True,
                "state": "compiled",
                "sdk_requirements": ["ProElemId.h"],
                "missing_sdk_requirements": [],
            }
        },
    }


def _manifest(completion: str = "unsupported") -> dict:
    return {
        "job_id": "job-1",
        "result": {
            "operations": [
                {
                    "op": "surface_loft",
                    "kernel_completion": completion,
                    "kernel_evidence": {
                        "release_numeric": 42,
                        "create_code": 0,
                        "extract_code": -18,
                        "feature_incomplete": True,
                    },
                }
            ]
        },
    }


class SurfaceLoftRuntimeObservationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.patch = mock.patch.object(bridge, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.identity_patch = mock.patch.object(
            bridge, "worker_build_identity", return_value=_identity()
        )
        self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)

    def _health(self) -> dict:
        return json.loads((self.root / "build/toolkit_health.json").read_text(encoding="utf-8"))

    def test_receipt_is_recorded_for_the_current_worker(self):
        bridge.record_surface_loft_runtime(_manifest())
        observed = self._health()["surface_loft_runtime"]
        self.assertEqual(observed["kernel_completion"], "unsupported")
        self.assertEqual(observed["worker_sha256"], WORKER_SHA)
        self.assertEqual(observed["release_numeric"], 42)
        self.assertEqual(observed["job_id"], "job-1")

    def test_status_probe_keeps_the_observation(self):
        bridge.record_surface_loft_runtime(_manifest())
        bridge.record_channel_health(True, connection_state="ready")
        health = self._health()
        self.assertTrue(health["connected"])
        self.assertEqual(health["surface_loft_runtime"]["kernel_completion"], "unsupported")

    def test_observation_is_ignored_for_another_worker(self):
        bridge.record_surface_loft_runtime(_manifest())
        self.assertEqual(
            bridge.surface_loft_runtime_observation(_identity(OTHER_SHA)),
            {"kernel_completion": "unknown"},
        )

    def test_observation_matches_the_same_worker(self):
        bridge.record_surface_loft_runtime(_manifest())
        self.assertEqual(
            bridge.surface_loft_runtime_observation(_identity())["kernel_completion"],
            "unsupported",
        )

    def test_missing_observation_stays_unknown(self):
        self.assertEqual(
            bridge.surface_loft_runtime_observation(_identity()),
            {"kernel_completion": "unknown"},
        )

    def test_non_surface_loft_receipts_are_ignored(self):
        manifest = {"job_id": "job-2", "result": {"operations": [{"op": "extrude"}]}}
        bridge.record_surface_loft_runtime(manifest)
        self.assertFalse((self.root / "build/toolkit_health.json").exists())

    def test_capability_projection_discloses_without_changing_availability(self):
        families = {"surface_loft": {"available": True, "enabled": True}}
        identity = _identity()
        runtime = {
            "kernel_completion": "unsupported",
            "worker_sha256": WORKER_SHA,
            "release_numeric": 42,
            "observed_at": "2026-11-13T00:00:00+08:00",
            "job_id": "job-1",
            "evidence": {"extract_code": -18},
        }
        projected = project_worker_availability(families, identity, runtime)
        entry = projected["surface_loft"]
        self.assertTrue(entry["available"])
        self.assertEqual(entry["worker_build_identity"]["kernel_completion"], "unsupported")
        self.assertEqual(entry["worker_build_identity"]["release_numeric"], 42)

    def test_capability_projection_ignores_a_foreign_worker(self):
        families = {"surface_loft": {"available": True, "enabled": True}}
        runtime = {"kernel_completion": "unsupported", "worker_sha256": OTHER_SHA}
        projected = project_worker_availability(families, _identity(), runtime)
        self.assertEqual(
            projected["surface_loft"]["worker_build_identity"]["kernel_completion"], "unknown"
        )

    def test_capability_projection_defaults_to_unknown(self):
        families = {"surface_loft": {"available": True, "enabled": True}}
        projected = project_worker_availability(families, _identity())
        self.assertEqual(
            projected["surface_loft"]["worker_build_identity"]["kernel_completion"], "unknown"
        )


if __name__ == "__main__":
    unittest.main()
