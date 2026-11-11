"""Offline self-check of the FEAT-065/M4 continuity driver's live flow.

``tools/test_surface_loft_continuity.py --live`` needs a confirmed Creo
session. Here a stand-in client answers the same public MCP tools with the
T2b numbers (or with a deliberately wrong kernel), so the live logic - edge
pick, loft, one model per seam, merge-receipt source order, curvature reading,
judges and the negative case - is exercised without Creo. A pass here is not
live evidence.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from creo_mechdog.capabilities import require_available
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]


def load_driver():
    # The driver puts tools/ on sys.path for its sibling harness modules; keep
    # that from leaking into later imports of this test process.
    saved = list(sys.path)
    try:
        import tools.test_surface_loft_continuity as driver
    finally:
        sys.path[:] = saved
    return driver


class FakeCreo:
    """Just enough of each public tool, shaped like the real responses."""

    STRIP_QUILTS = {"strip_a": 63, "strip_b": 95}
    BRIDGE_QUILT = 300

    def __init__(self, driver, *, kernel_honours_tangent=True, full_page=True, jobs_root=None):
        self.driver = driver
        self.kernel_honours_tangent = kernel_honours_tangent
        self.full_page = full_page
        self.jobs_root = jobs_root
        self.jobs: dict[str, dict] = {}
        self.models: dict[str, dict] = {}
        self.plans: list[list[dict]] = []

    async def call_tool(self, tool, arguments):
        payload = getattr(self, tool)(arguments)
        if isinstance(payload, str):
            return SimpleNamespace(
                structured_content=None, content=[SimpleNamespace(text=payload)], isError=True
            )
        return SimpleNamespace(structured_content=payload, content=[], isError=False)

    def creo_startup_status(self, arguments):
        return {"connected": True, "state": "ready"}

    def creo_capabilities(self, arguments):
        return {"operations": ["surface_loft", "quilt_merge", "surface_curvature"]}

    def creo_execute_plan(self, arguments):
        try:
            operations = validate_operations(arguments["operations"])
            require_available(operations)
        except ValueError as error:
            return f"Error executing tool creo_execute_plan: {error}"
        self.plans.append(operations)
        model_id = arguments.get("model_id") or f"model{len(self.models)}"
        model = self.models.setdefault(model_id, {"revision": 0, "tangent": None})
        if arguments.get("model_id") and arguments.get("expected_revision") != model["revision"]:
            return "Error executing tool creo_execute_plan: revision conflict"
        compact, full = [], []
        for index, operation in enumerate(operations):
            record, raw = self.run(model, index, operation)
            compact.append(record)
            full.append(raw)
        model["revision"] += 1
        job_id = f"job{len(self.jobs)}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "model_id": model_id,
            "status": "succeeded",
            "revision": model["revision"],
            "result": {"operations": compact, "saved_file_reloaded_and_verified": True},
            "full": full,
        }
        if self.jobs_root is not None:
            directory = Path(self.jobs_root) / job_id
            directory.mkdir(parents=True)
            (directory / "job.json").write_text(
                json.dumps({"job_id": job_id, "result": {"operations": full}}), encoding="utf-8"
            )
        return {"job_id": job_id, "status": "queued"}

    def run(self, model, index, operation):
        record = {"op": operation["op"], "index": index, "label": operation.get("label")}
        if operation["op"] == "surface_loft":
            conditions = operation.get("boundary_conditions") or []
            asked = any(item["condition"] == "tangent" for item in conditions)
            model["tangent"] = asked and self.kernel_honours_tangent
            echo = []
            for position, item in enumerate(conditions):
                entry = {
                    "index": position,
                    "boundary": item["boundary"],
                    "condition": item["condition"],
                    "edge_id": None,
                    "surface_id": None,
                    "status": "kernel_default",
                }
                if item["condition"] == "tangent":
                    slot = 0 if item["boundary"] == "first_section" else 1
                    entry.update(
                        edge_id=operation["sections"][slot]["id"],
                        surface_id=55 + 32 * slot,
                        status="written",
                        tnc_index=slot,
                        tan_cond_type=2,
                        stretch=-1.0 if slot == 0 else 1.0,
                        connect_chain="kernel_default",
                    )
                echo.append(entry)
            record.update(
                quilt_id=self.BRIDGE_QUILT,
                quilt_count=1,
                quilt_closed_native="open",
                has_solid=False,
                surface_area_mm2=982.5887974169791 if model["tangent"] else 800.0,
                section_source_kinds=["edge", "edge"],
                section_geometry_ids=[[item["id"]] for item in operation["sections"]],
                boundary_conditions=echo,
                unverified_input_forms=[],
            )
            return record, dict(record)
        if operation["op"] == "quilt_merge":
            # The compact projection has no quilt_merge whitelist, so the real
            # compact record carries no result_quilt_id either.
            raw = {
                **record,
                "result_quilt_id": self.STRIP_QUILTS[operation["target"]["label"]],
                "merged_surface_ids": [55, 301],
            }
            return record, raw
        return record, dict(record)

    def creo_get_job(self, arguments):
        job = self.jobs[arguments["job_id"]]
        if arguments.get("detail") == "full":
            records = [
                item for item in job["full"] if self.full_page or item["op"] != "quilt_merge"
            ]
            return {
                "detail": "full",
                "section": "operations_result",
                "data": {"operations_result": records},
            }
        return {key: value for key, value in job.items() if key != "full"}

    def creo_measure_surface_group(self, arguments):
        model = self.models[arguments["model_id"]]
        return {
            "job_id": "measure",
            "model_id": arguments["model_id"],
            "revision": model["revision"],
            "group": self.driver.inputs.synthetic_strip_group(),
        }

    def creo_inspect_model(self, arguments):
        model = self.models[arguments["model_id"]]
        z_max = 15.120004800192012 if model["tangent"] else 10.12
        box = [[-0.12, -0.12, 9.88], [40.12, 20.12, z_max]]
        return {"data": {"quilts": [{"quilt_id": self.BRIDGE_QUILT, "bbox_mm": box}]}}

    def creo_measure_surface_curvature(self, arguments):
        tangent = self.models[arguments["model_id"]]["tangent"]
        return {
            "quilt_id": arguments["target"]["id"],
            "g1_max_angle_deg": 0.0 if tangent else 90.0,
            "within_g1": bool(tangent),
            "g1_threshold_deg": 0.5,
            "g1_status": {"available": True},
        }


class ContinuityDriverLiveFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = load_driver()

    def run_flow(self, **options):
        with tempfile.TemporaryDirectory() as jobs_root:
            fake = FakeCreo(self.driver, jobs_root=jobs_root, **options)
            recorder = self.driver.inputs.Recorder()
            asyncio.run(self.driver.run_live_cases(fake, recorder, jobs_root=Path(jobs_root)))
        return fake, recorder

    def failed(self, recorder) -> set:
        return {item["check"] for item in recorder.checks if not item["ok"]}

    def test_the_measured_behaviour_passes_every_check(self):
        fake, recorder = self.run_flow()
        self.assertEqual(self.failed(recorder), set())
        names = {item["check"] for item in recorder.checks}
        for name in (
            "free_strips_built",
            "free_free_conditions_write_nothing",
            "free_area_is_the_800_plane",
            "free_seam_a_about_90_deg",
            "tangent_seam_a_scene_boundary_conditions_written",
            "tangent_seam_a_scene_area_above_900",
            "tangent_seam_a_scene_arch_rises_above_z14",
            "tangent_seam_a_scene_saved_file_reloaded_and_verified",
            "tangent_seam_a_g1_within_0_5_deg",
            "tangent_seam_b_g1_within_0_5_deg",
            "tangent_reversed_seam_a_g1_within_0_5_deg",
            "tangent_reversed_seam_b_g1_within_0_5_deg",
            "tangent_reversed_matches_tangent_area",
            "negative_curvature_refused_before_a_job",
        ):
            with self.subTest(name=name):
                self.assertIn(name, names)
        # One model per seam: free + 2 tangent + 2 reversed builds.
        builds = [plan for plan in fake.plans if plan[0]["label"] == "strip_a_line"]
        self.assertEqual(len(builds), 5)
        reversed_lines = [
            plan[0]["entities"][0]["start"]
            for plan in builds
            if plan[0]["entities"][0]["start"] != [0.0, 0.0]
        ]
        self.assertEqual(len(reversed_lines), 2)
        merges = [plan[0] for plan in fake.plans if plan[0]["op"] == "quilt_merge"]
        self.assertEqual(
            [merge["target"]["label"] for merge in merges],
            ["strip_a", "strip_a", "strip_b", "strip_a", "strip_b"],
        )
        self.assertEqual(
            recorder.observations["merge_receipt_sources"],
            ["creo_get_job full operations_result"],
        )

    def test_a_tangent_request_the_kernel_ignores_fails(self):
        _, recorder = self.run_flow(kernel_honours_tangent=False)
        failed = self.failed(recorder)
        for name in (
            "tangent_seam_a_scene_area_above_900",
            "tangent_seam_a_scene_arch_rises_above_z14",
            "tangent_seam_a_g1_within_0_5_deg",
            "tangent_reversed_seam_b_g1_within_0_5_deg",
        ):
            with self.subTest(name=name):
                self.assertIn(name, failed)
        self.assertNotIn("free_seam_a_about_90_deg", failed)
        self.assertNotIn("negative_curvature_refused_before_a_job", failed)

    def test_the_merge_receipt_falls_back_to_the_job_record(self):
        _, recorder = self.run_flow(full_page=False)
        self.assertEqual(self.failed(recorder), set())
        self.assertEqual(recorder.observations["merge_receipt_sources"], ["jobs/<job_id>/job.json"])

    def test_a_merge_without_a_result_quilt_fails_the_seam(self):
        driver = self.driver
        with tempfile.TemporaryDirectory() as jobs_root:
            fake = FakeCreo(driver, full_page=False, jobs_root=None)
            recorder = driver.inputs.Recorder()
            asyncio.run(driver.run_live_cases(fake, recorder, jobs_root=Path(jobs_root)))
        failed = self.failed(recorder)
        self.assertIn("free_seam_a_merged", failed)
        self.assertIn("tangent_seam_b_merged", failed)
        self.assertEqual(recorder.observations["merge_receipt_sources"], ["None"])

    def test_the_offline_contract_passes(self):
        report = self.driver.case_offline()
        self.assertTrue(report["passed"], [item for item in report["checks"] if not item["ok"]])


if __name__ == "__main__":
    unittest.main()
