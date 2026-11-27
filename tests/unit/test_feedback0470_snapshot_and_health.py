"""Unit tests for BUG-196 and BUG-197 (0.47.0 / 0.47.1 external feedback fixes)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from creo_mechdog import (  # noqa: E402
    bridge,
    compact_sections,
    generic_bridge,
    model_queries,
    model_registry,
    server,
    session_health,
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegacySnapshotBackfillTest(unittest.TestCase):
    """BUG-196: legacy snapshots surface stale_fields and refresh write-back preserves revision."""

    def test_model_summary_detects_legacy_stale_fields_and_refresh_verified(self):
        # Pre-0.41.0 saved model without surface detail array, area, bbox, or merged_counts:
        legacy = {
            "model_id": "a" * 32,
            "model_name": "legacy_block",
            "model_type": "part",
            "status": "ready",
            "revision": 1,
            "part_file": "D:/tmp/legacy_block.prt.1",
            "part_sha256": "a" * 64,
            "inspection": {
                "inspection_available": True,
                "has_solid": True,
                "counts": {"solids": 1, "surfaces": 6, "edges": 12},
                "surface_ids": [1, 2, 3, 4, 5, 6],
                "bounding_box_status": {"measured": False, "source": "legacy_regeneration_outline"},
            },
        }
        summary = model_queries.model_summary(legacy)
        snap = summary.get("snapshot", {})
        self.assertIn("total_surface_area_mm2", snap.get("stale_fields", []))
        self.assertIn("bounding_box_mm", snap.get("stale_fields", []))
        self.assertIn("merged_counts", snap.get("stale_fields", []))
        self.assertIn("write_back_snapshot=True", snap.get("refresh_hint", ""))

        # Inline surfaces without area_mm2 also trigger surfaces[].area_mm2:
        legacy_with_surfaces = {
            **legacy,
            "inspection": {
                **legacy["inspection"],
                "surfaces": [{"id": 1, "type": "plane", "normal": [0, 0, 1]}],
            },
        }
        snap_surfaces = model_queries.model_summary(legacy_with_surfaces).get("snapshot", {})
        self.assertIn("surfaces[].area_mm2", snap_surfaces.get("stale_fields", []))

        refreshed = {
            **legacy,
            "snapshot_source": "refresh_verified",
            "snapshot_refreshed_at": "2026-11-27T01:00:00Z",
            "inspection": {
                "inspection_available": True,
                "has_solid": True,
                "counts": {"solids": 1, "surfaces": 6, "edges": 12},
                "total_surface_area_mm2": 600.0,
                "bounding_box_mm": {"min": [0, 0, 0], "max": [10, 10, 10]},
                "bounding_box_source": "solid_surface_mesh",
                "bounding_box_status": {
                    "measured": True,
                    "basis": "tessellated_solid_union",
                    "query_code": 0,
                },
                "merged_counts": {
                    "merged_solid_count": 1,
                    "merged_surface_count": 6,
                    "merged_edge_count": 12,
                },
                "surfaces": [{"id": 1, "type": "plane", "area_mm2": 100.0}],
            },
        }
        fresh_summary = model_queries.model_summary(refreshed)
        self.assertEqual(fresh_summary["snapshot"].get("source"), "refresh_verified")
        self.assertEqual(fresh_summary["snapshot"].get("refreshed_at"), "2026-11-27T01:00:00Z")
        self.assertNotIn("stale_fields", fresh_summary["snapshot"])

    def test_submit_validates_write_back_snapshot(self):
        with self.assertRaises(ValueError):
            generic_bridge.submit(
                [],
                model_id="a" * 32,
                readonly=False,
                write_back_snapshot=True,
            )
        with self.assertRaises(ValueError):
            generic_bridge.submit(
                [{"op": "extrude"}],
                model_id="a" * 32,
                readonly=True,
                write_back_snapshot=True,
            )
        with self.assertRaises(ValueError):
            generic_bridge.submit(
                [],
                model_id=None,
                readonly=True,
                write_back_snapshot=True,
            )
        with self.assertRaises(ValueError):
            generic_bridge.submit(
                [],
                model_id="a" * 32,
                readonly=True,
                write_back_snapshot="yes",  # type: ignore[arg-type]
            )

    def test_compact_sections_keeps_snapshot_write_back(self):
        self.assertIn("snapshot_write_back", compact_sections.RESULT_KEYS)
        self.assertIn("snapshot_write_back", compact_sections.PROTECTED_RESULT_KEYS)

    def test_run_generic_job_write_back_updates_snapshot_only_when_sha_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            models_dir = root / "models"
            jobs_dir = root / "jobs"
            tpl_dir = root / "creo" / "Common Files" / "templates"
            models_dir.mkdir()
            jobs_dir.mkdir()
            tpl_dir.mkdir(parents=True)
            (tpl_dir / "mmns_part_solid_abs.prt").write_bytes(b"TPL")

            part_dir = models_dir / ("a" * 32) / "output"
            part_dir.mkdir(parents=True)
            part_path = part_dir / "legacy_block.prt.1"
            part_path.write_bytes(b"CREO-PART-V1")
            part_sha = _sha256_file(part_path)

            model_id = "a" * 32
            m_dir = models_dir / model_id
            legacy_record = {
                "model_id": model_id,
                "model_name": "legacy_block",
                "model_type": "part",
                "status": "ready",
                "revision": 3,
                "updated_at": "2025-12-01T00:00:00Z",
                "last_job": "job_old",
                "part_file": str(part_path),
                "part_sha256": part_sha,
                "inspection": {
                    "inspection_available": True,
                    "has_solid": True,
                    "counts": {"solids": 1, "surfaces": 6, "edges": 12},
                    "surface_ids": [1, 2, 3, 4, 5, 6],
                    "edge_ids": list(range(1, 13)),
                },
            }
            model_registry.write_model(m_dir, legacy_record)

            fresh_inspection = {
                "inspection_available": True,
                "has_solid": True,
                "counts": {"solids": 1, "surfaces": 6, "edges": 12},
                "total_surface_area_mm2": 600.0,
                "bounding_box_mm": {"min": [0, 0, 0], "max": [10, 10, 10]},
                "bounding_box_source": "solid_surface_mesh",
                "bounding_box_status": {
                    "measured": True,
                    "basis": "tessellated_solid_union",
                    "query_code": 0,
                },
                "merged_counts": {
                    "merged_solid_count": 1,
                    "merged_surface_count": 6,
                    "merged_edge_count": 12,
                },
                "surfaces": [{"id": 1, "type": "plane", "area_mm2": 100.0}],
            }

            with (
                mock.patch.object(bridge, "ROOT", root),
                mock.patch.object(generic_bridge, "MODELS", models_dir),
                mock.patch.object(bridge, "JOBS", jobs_dir),
                mock.patch.object(bridge, "config", return_value={"creo_root": str(root / "creo")}),
                mock.patch.object(
                    bridge,
                    "spawn_detached_runner",
                    return_value=(mock.MagicMock(pid=99999), False),
                ),
                mock.patch.object(bridge, "toolkit_lock", return_value=nullcontext()),
                mock.patch.object(bridge, "build_native", return_value=Path("creo_executor.exe")),
            ):
                submitted = generic_bridge.submit(
                    [],
                    model_id=model_id,
                    readonly=True,
                    write_back_snapshot=True,
                )
                job_id = submitted["job_id"]
                j_dir = bridge.job_path(job_id)
                manifest = bridge.read_json(j_dir / "job.json")

                def fake_worker(_exe, directory, _request, _manifest, _log):
                    (Path(directory) / "native_result.json").write_text(
                        json.dumps(
                            {
                                "ok": True,
                                "success": True,
                                "part_file": str(part_path),
                                "sha256": part_sha,
                                "inspection": fresh_inspection,
                                "operations": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    return 0

                with mock.patch.object(
                    generic_bridge, "_run_worker_with_watchdog", side_effect=fake_worker
                ):
                    generic_bridge.run_generic_job(job_id, manifest)

                updated = model_registry.read_control(m_dir)
                self.assertEqual(updated["revision"], 3)
                self.assertEqual(updated["part_sha256"], part_sha)
                self.assertEqual(updated["updated_at"], "2025-12-01T00:00:00Z")
                self.assertEqual(updated["last_job"], job_id)
                self.assertEqual(updated["snapshot_source"], "refresh_verified")
                self.assertTrue(updated.get("snapshot_refreshed_at"))
                self.assertEqual(updated["inspection_summary"]["total_surface_area_mm2"], 600.0)

                final_job = bridge.read_json(j_dir / "job.json")
                self.assertEqual(final_job["status"], "succeeded")
                self.assertTrue(final_job["result"]["snapshot_write_back"]["applied"])

                # Simulate disk SHA mismatch -> write-back must refuse cleanly
                part_path.write_bytes(b"CREO-PART-CHANGED")
                mismatched_sha = _sha256_file(part_path)
                submitted2 = generic_bridge.submit(
                    [],
                    model_id=model_id,
                    readonly=True,
                    write_back_snapshot=True,
                )
                job_id2 = submitted2["job_id"]
                j_dir2 = bridge.job_path(job_id2)
                manifest2 = bridge.read_json(j_dir2 / "job.json")

                def fake_worker_mismatch(_exe, directory, _request, _manifest, _log):
                    (Path(directory) / "native_result.json").write_text(
                        json.dumps(
                            {
                                "ok": True,
                                "success": True,
                                "part_file": str(part_path),
                                "sha256": mismatched_sha,
                                "inspection": {**fresh_inspection, "total_surface_area_mm2": 999.0},
                                "operations": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    return 0

                with mock.patch.object(
                    generic_bridge, "_run_worker_with_watchdog", side_effect=fake_worker_mismatch
                ):
                    generic_bridge.run_generic_job(job_id2, manifest2)

                after_mismatch = model_registry.read_control(m_dir)
                self.assertEqual(
                    after_mismatch["inspection_summary"]["total_surface_area_mm2"], 600.0
                )
                final_job2 = bridge.read_json(j_dir2 / "job.json")
                self.assertEqual(final_job2["status"], "succeeded")
                self.assertFalse(final_job2["result"]["snapshot_write_back"]["applied"])
                self.assertEqual(
                    final_job2["result"]["snapshot_write_back"]["reason"],
                    "part_sha256_mismatch_or_missing",
                )

    def test_split_legacy_part_detects_missing_surface_areas_and_clears_after_write_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            models_dir = root / "models"
            jobs_dir = root / "jobs"
            tpl_dir = root / "creo" / "Common Files" / "templates"
            models_dir.mkdir()
            jobs_dir.mkdir()
            tpl_dir.mkdir(parents=True)
            (tpl_dir / "mmns_part_solid_abs.prt").write_bytes(b"TPL")

            model_id = "b" * 32
            part_dir = models_dir / model_id / "output"
            part_dir.mkdir(parents=True)
            part_path = part_dir / "p01_piston.prt.6"
            part_path.write_bytes(b"CREO-PART-0390")
            part_sha = _sha256_file(part_path)

            m_dir = models_dir / model_id
            legacy_split = {
                "model_id": model_id,
                "model_name": "p01_piston",
                "model_type": "part",
                "status": "ready",
                "revision": 6,
                "updated_at": "2026-11-23T15:29:07Z",
                "last_job": "job_0390",
                "part_file": str(part_path),
                "part_sha256": part_sha,
                "inspection": {
                    "inspection_available": True,
                    "has_solid": True,
                    "counts": {"solids": 1, "surfaces": 2, "edges": 4},
                    "surfaces": [
                        {"id": 1, "type": "plane", "normal": [0, 0, 1]},
                        {"id": 2, "type": "cylinder", "radius": 10.0},
                    ],
                    "edges": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
                },
            }
            with mock.patch.object(bridge, "ROOT", root):
                model_registry.write_model(m_dir, legacy_split)
                stored_split = model_registry.read_control(m_dir)
                self.assertNotIn("inspection", stored_split)
                self.assertFalse(stored_split["inspection_summary"]["surface_areas_available"])

                # 1) Split record written without per-surface area_mm2 or total/bbox:
                # surface_areas_available=False flags surfaces[].area_mm2 even when
                # inspection is split to a sidecar.
                snap_split = model_queries.model_summary(stored_split)["snapshot"]
                self.assertIn("surfaces[].area_mm2", snap_split.get("stale_fields", []))
                self.assertIn("total_surface_area_mm2", snap_split.get("stale_fields", []))
                self.assertIn("bounding_box_mm", snap_split.get("stale_fields", []))

                # 2) Pre-0.41.0 split record on disk (lacking merged_counts and
                # surface_areas_available in stored inspection_summary):
                pre_0481 = {
                    **stored_split,
                    "inspection_summary": {
                        k: v
                        for k, v in stored_split["inspection_summary"].items()
                        if k not in ("surface_areas_available", "merged_counts")
                    },
                }
                snap_pre = model_queries.model_summary(pre_0481)["snapshot"]
                self.assertIn("surfaces[].area_mm2", snap_pre.get("stale_fields", []))
                self.assertIn("merged_counts", snap_pre.get("stale_fields", []))

                # 3) Refresh with write_back_snapshot=True fills per-surface area_mm2 and clears
                # stale_fields while preserving revision/part_sha256/updated_at.
                fresh_inspection = {
                    "inspection_available": True,
                    "has_solid": True,
                    "counts": {"solids": 1, "surfaces": 2, "edges": 4},
                    "total_surface_area_mm2": 58171.597,
                    "bounding_box_mm": {"min": [0, 0, 0], "max": [85, 95, 85]},
                    "bounding_box_source": "solid_surface_mesh",
                    "bounding_box_status": {
                        "state": "measured",
                        "basis": "tessellated_solid_union",
                        "query_code": 0,
                    },
                    "surfaces": [
                        {"id": 1, "type": "plane", "area_mm2": 1000.0},
                        {"id": 2, "type": "cylinder", "area_mm2": 57171.597},
                    ],
                    "edges": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
                }
                with (
                    mock.patch.object(generic_bridge, "MODELS", models_dir),
                    mock.patch.object(bridge, "JOBS", jobs_dir),
                    mock.patch.object(
                        bridge, "config", return_value={"creo_root": str(root / "creo")}
                    ),
                    mock.patch.object(
                        bridge,
                        "spawn_detached_runner",
                        return_value=(mock.MagicMock(pid=99999), False),
                    ),
                    mock.patch.object(bridge, "toolkit_lock", return_value=nullcontext()),
                    mock.patch.object(
                        bridge, "build_native", return_value=Path("creo_executor.exe")
                    ),
                ):
                    submitted = generic_bridge.submit(
                        [],
                        model_id=model_id,
                        readonly=True,
                        write_back_snapshot=True,
                    )
                    job_id = submitted["job_id"]
                    manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")

                    def fake_worker(_exe, directory, _request, _manifest, _log):
                        (Path(directory) / "native_result.json").write_text(
                            json.dumps(
                                {
                                    "ok": True,
                                    "success": True,
                                    "part_file": str(part_path),
                                    "sha256": part_sha,
                                    "inspection": fresh_inspection,
                                    "operations": [],
                                }
                            ),
                            encoding="utf-8",
                        )
                        return 0

                    with mock.patch.object(
                        generic_bridge, "_run_worker_with_watchdog", side_effect=fake_worker
                    ):
                        generic_bridge.run_generic_job(job_id, manifest)

                updated = model_registry.read_control(m_dir)
                self.assertEqual(updated["revision"], 6)
                self.assertEqual(updated["part_sha256"], part_sha)
                self.assertEqual(updated["updated_at"], "2026-11-23T15:29:07Z")
                self.assertTrue(updated["inspection_summary"]["surface_areas_available"])
                updated_summary = model_queries.model_summary(updated)
                self.assertNotIn("stale_fields", updated_summary["snapshot"])
                surfaces_page = model_queries.inspect_page(
                    updated, detail="full", section="surfaces"
                )
                self.assertEqual(
                    [s["area_mm2"] for s in surfaces_page["data"]["surfaces"]],
                    [1000.0, 57171.597],
                )

    def test_assembly_snapshot_stale_fields_never_requires_merged_counts(self):
        refreshed_asm = {
            "model_id": "c" * 32,
            "model_name": "engine_asm",
            "model_type": "assembly",
            "status": "ready",
            "revision": 4,
            "part_file": "D:/tmp/engine_asm.asm.4",
            "part_sha256": "c" * 64,
            "snapshot_source": "refresh_verified",
            "inspection_summary": {
                "inspection_available": True,
                "model_type": "assembly",
                "has_solid": True,
                "counts": {
                    "features": 29,
                    "surfaces": 0,
                    "edges": 0,
                    "quilts": 0,
                    "bodies": 0,
                    "components": 29,
                },
                "total_surface_area_mm2": 905372.068,
                "bounding_box_mm": {
                    "min": [-638.173, 68.707, -299.449],
                    "max": [-49.173, 459.902, 93.077],
                },
                "bounding_box_source": "solid_surface_mesh",
                "bounding_box_status": {
                    "state": "measured",
                    "basis": "tessellated_solid_union",
                    "query_code": 0,
                },
            },
            "inspection_ref": {"file": "D:/tmp/ins.json", "sha256": "d" * 64, "bytes": 100},
        }
        self.assertNotIn("stale_fields", model_queries.model_summary(refreshed_asm)["snapshot"])

        legacy_asm = {
            **refreshed_asm,
            "inspection_summary": {
                "inspection_available": True,
                "model_type": "assembly",
                "has_solid": True,
                "counts": {"features": 29, "surfaces": 0, "edges": 0, "components": 29},
            },
        }
        self.assertEqual(
            model_queries.model_summary(legacy_asm)["snapshot"].get("stale_fields"),
            ["total_surface_area_mm2", "bounding_box_mm"],
        )


class NativeFeedbackContractsTest(unittest.TestCase):
    """BUG-197: compact inspection_summary, docs examples, C++ bbox basis/query_code, health split."""

    def test_solid_bounds_header_emits_basis_and_query_code(self):
        text = (ROOT / "native" / "solid_bounds.h").read_text(encoding="utf-8")
        self.assertIn('"basis"', text)
        self.assertIn('"tessellated_solid_union"', text)
        self.assertIn('"query_code"', text)
        self.assertIn("static_cast<int>(bounds.code)", text)
        self.assertNotIn(
            "bounds.code ? nlohmann::json(static_cast<int>(bounds.code)) : nlohmann::json(nullptr)",
            text,
        )

    def test_compact_job_surfaces_inspection_summary_fallback(self):
        manifest = {
            "job_id": "job_c1",
            "status": "completed",
            "model_id": "m_c1",
            "model_name": "p1",
            "result": {
                "ok": True,
                "inspection_ref": "models/m_c1/details/ins.json",
                "inspection_summary": {
                    "solid_count": 1,
                    "surface_count": 6,
                    "edge_count": 12,
                    "total_surface_area_mm2": 1234.5,
                    "bounding_box_mm": {"min": [0, 0, 0], "max": [10, 10, 10]},
                },
                "operations": [],
            },
        }
        compact = bridge.compact_job(manifest)
        self.assertEqual(compact["result"]["inspection"]["total_surface_area_mm2"], 1234.5)

        sectioned = bridge.compact_job(manifest, sections=["inspection_summary"])
        self.assertIn("inspection_summary", sectioned["result"])
        self.assertEqual(
            sectioned["result"]["inspection_summary"]["total_surface_area_mm2"], 1234.5
        )

    def test_tool_descriptions_cover_bbox_basis_sections_and_round_example(self):
        tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
        get_job_sections_desc = tools["creo_get_job"].input_schema["properties"]["sections"][
            "description"
        ]
        self.assertIn("inspection_summary", get_job_sections_desc)
        self.assertIn("tessellated_solid_union", server.creo_inspect_model.__doc__ or "")
        self.assertIn("write_back_snapshot", server.creo_refresh_model.__doc__ or "")
        server_src = (ROOT / "src" / "creo_mechdog" / "server.py").read_text(encoding="utf-8")
        self.assertIn("'tolerance_mm':0.5", server_src)
        self.assertIn("'full_circle':true", server_src)

    def test_session_health_separates_connection_and_save_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "jobs" / "job_save_fail").mkdir(parents=True)
            (root / "build").mkdir()
            now = datetime(2026, 11, 27, 1, 0, 0, tzinfo=timezone.utc)
            now_iso = now.isoformat()
            (root / "build" / "toolkit_health.json").write_text(
                json.dumps(
                    {
                        "checked_at": now_iso,
                        "connected": True,
                        "connection_state": "connected",
                        "toolkit_code": 0,
                        "probe_error": None,
                    }
                ),
                encoding="utf-8",
            )
            (root / "jobs" / "job_save_fail" / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": "job_save_fail",
                        "kind": "generic",
                        "created_at": now_iso,
                        "finished_at": now_iso,
                        "status": "failed",
                        "readonly": False,
                        "model_id": "model_damaged",
                        "result": {
                            "success": False,
                            "connected": True,
                            "session_fingerprint": "pid=1234|creo=10.0.0.0",
                            "toolkit_code": -1,
                            "failed_stage": "save_and_reload",
                            "failed_toolkit_call": "ProMdlnameBackup",
                            "message": "Toolkit call ProMdlnameBackup failed with code -1",
                        },
                    }
                ),
                encoding="utf-8",
            )
            snap = session_health.snapshot(root=root, now=now, refresh=True)
            self.assertEqual(snap["connection_health"]["status"], "connected")
            self.assertEqual(snap["save_verification_health"]["status"], snap["status"])
            self.assertNotEqual(snap["save_verification_health"]["status"], "connected")
            self.assertEqual(snap["save_verification_health"]["reason"], snap["reason"])
            self.assertEqual(snap["facts"]["last_save"]["job_id"], "job_save_fail")

    def test_creo_session_status_refreshes_health_on_demand(self):
        with (
            mock.patch.object(
                server,
                "session_health",
                return_value={
                    "status": "degraded",
                    "reason": "save_verification_failed",
                    "connection_health": {"status": "unknown", "connected": None},
                    "save_verification_health": {
                        "status": "degraded",
                        "reason": "save_verification_failed",
                    },
                },
            ),
            mock.patch.object(
                server.startup,
                "session_status",
                return_value={"connected": True, "creo_running": True},
            ),
        ):
            res = asyncio.run(server.creo_session_status())
        self.assertTrue(res["connected"])
        self.assertEqual(res["session_health"]["connection_health"]["status"], "connected")
        self.assertEqual(res["session_health"]["save_verification_health"]["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
