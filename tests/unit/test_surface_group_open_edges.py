"""FEAT-065 T1b: the open boundary edge list of creo_measure_surface_group.

``creo_inspect_model`` lists solid edges only, so a quilt boundary edge had no
public id for ``surface_loft``'s ``{kind:'edge',id:N}``. The measurement now
publishes ``group.open_edge_records`` (edge_id, surface_id, quilt_id,
length_mm, endpoints_mm) with a bound, a total and a truncation marker.

Offline only: no Creo, no Toolkit. The projection rules, the compact budget
and the public text are tested in Python; the native record builder is
compiled on its own with stand-in inputs (``tests/native/
test_surface_group_open_edges.cpp``) when a local compiler configuration
exists. Creo 12.4.0.0 named the quilt edges and evaluated their endpoints in
the FEAT-065 T3 live run (2026-11-11: 8 open edges of two strips listed, the
two top edges picked by endpoint); that evidence belongs to
``tools/test_surface_loft_inputs.py --live``, not to these tests.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import subprocess
import unittest
from pathlib import Path

import bridge
import server
from creo_mechdog import capabilities
from creo_mechdog.job_projection import compact_operation
from creo_mechdog.model_queries import RESPONSE_BUDGET, serialized_size
from creo_mechdog.operation_results import (
    SURFACE_GROUP_OPEN_EDGE_RECORD_LIMIT,
    SURFACE_GROUP_OUTCOME_KEYS,
    annotate_surface_group,
    enforce_compact_budget,
    normalize_surface_group,
)

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_group.cpp"
HARNESS = ROOT / "tests" / "native" / "test_surface_group_open_edges.cpp"


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def edge_record(index: int, *, quilt: int = 21) -> dict:
    # Long, non-round coordinates: the worst case for the serialized size.
    x = 12.345678901234567 + index
    return {
        "edge_id": 1000 + index,
        "surface_id": 500 + index,
        "quilt_id": quilt,
        "length_mm": 40.00000000000001,
        "endpoints_mm": [
            [x, -23.456789012345678, 34.56789012345678],
            [x + 40.00000000000001, -23.456789012345678, 34.56789012345678],
        ],
    }


def status(**overrides) -> dict:
    block = {
        "available": True,
        "reason": None,
        "query_code": 0,
        "scale_to_mm_known": True,
        "unit_name": "mm",
    }
    block.update(overrides)
    return block


def group_block(count: int = 6, **overrides) -> dict:
    records = [edge_record(index) for index in range(min(count, 32))]
    block = {
        "quilt_ids": [21, 22],
        "quilt_count": 2,
        "face_count": 2,
        "faces": [{"surface_id": 31, "quilt_index": 0}, {"surface_id": 41, "quilt_index": 1}],
        "boundary_edges": count + 2,
        "joined_edges": 2,
        "open_edges": count,
        "open_edges_status": status(
            boundary_edges=count + 2, joined_edges=2, topologically_shared_edges=0
        ),
        "gap_max_mm": 0.0,
        "gap_max_status": status(tolerance_mm=0.01, gap_search_mm=1.0, within_tolerance=True),
        "overlap_area_mm2": 0.0,
        "overlap_status": status(detected=False, area_is_estimate=True),
        "overlap_pairs": [],
        "state": "closed",
        "state_reason": None,
        "boundary_closed": False,
        "tolerance_mm": 0.01,
        "gap_search_mm": 1.0,
        "open_edge_records": records,
        "open_edge_records_total": count,
        "open_edge_records_truncated": count > len(records),
        "open_edge_records_status": status(
            limit=32,
            returned=len(records),
            mm_values_reason=None,
            edge_id_failures=0,
            length_failures=0,
            endpoint_failures=0,
        ),
    }
    block.update(overrides)
    return block


class OpenEdgeRecordProjectionTests(unittest.TestCase):
    def test_measured_records_pass_through_unchanged(self):
        block = group_block()
        cleaned = normalize_surface_group(copy.deepcopy(block))
        self.assertEqual(cleaned["open_edge_records"], block["open_edge_records"])
        self.assertEqual(cleaned["open_edge_records_total"], 6)
        self.assertIs(cleaned["open_edge_records_truncated"], False)
        self.assertEqual(normalize_surface_group(copy.deepcopy(cleaned)), cleaned)

    def test_unknown_unit_scale_keeps_ids_and_nulls_every_mm_value(self):
        block = group_block(
            open_edges_status=status(scale_to_mm_known=False, unit_name=None),
            open_edge_records_status=status(
                scale_to_mm_known=False, unit_name=None, mm_values_reason="unit_scale_unknown"
            ),
        )
        cleaned = normalize_surface_group(block)
        records = cleaned["open_edge_records"]
        self.assertEqual([record["edge_id"] for record in records], list(range(1000, 1006)))
        self.assertTrue(all(record["quilt_id"] == 21 for record in records))
        self.assertTrue(all(record["length_mm"] is None for record in records))
        self.assertTrue(all(record["endpoints_mm"] is None for record in records))
        self.assertEqual(cleaned["open_edge_records_total"], 6)

    def test_unread_boundary_nulls_the_list_total_and_marker(self):
        unavailable = status(available=False, reason="contour_edge_visit_failed", query_code=-1)
        cleaned = normalize_surface_group(
            group_block(open_edges_status=unavailable, open_edge_records_status=unavailable)
        )
        self.assertIsNone(cleaned["open_edges"])
        self.assertIsNone(cleaned["open_edge_records"])
        self.assertIsNone(cleaned["open_edge_records_total"])
        self.assertIsNone(cleaned["open_edge_records_truncated"])
        self.assertEqual(cleaned["open_edge_records_status"]["reason"], "contour_edge_visit_failed")

    def test_list_without_its_own_status_is_not_trusted(self):
        block = group_block()
        del block["open_edge_records_status"]
        cleaned = normalize_surface_group(block)
        self.assertIsNone(cleaned["open_edge_records"])
        self.assertIsNone(cleaned["open_edge_records_total"])

    def test_more_records_than_the_bound_are_cut_and_marked(self):
        block = group_block(40)
        block["open_edge_records"] = [edge_record(index) for index in range(40)]
        block["open_edge_records_truncated"] = False
        cleaned = normalize_surface_group(block)
        self.assertEqual(len(cleaned["open_edge_records"]), SURFACE_GROUP_OPEN_EDGE_RECORD_LIMIT)
        self.assertIs(cleaned["open_edge_records_truncated"], True)
        self.assertEqual(cleaned["open_edge_records_total"], 40)

    def test_native_truncation_and_total_survive(self):
        cleaned = normalize_surface_group(group_block(50))
        self.assertEqual(len(cleaned["open_edge_records"]), 32)
        self.assertEqual(cleaned["open_edge_records_total"], 50)
        self.assertIs(cleaned["open_edge_records_truncated"], True)

    def test_inconsistent_total_is_not_published(self):
        block = group_block(6, open_edge_records_total=3)
        cleaned = normalize_surface_group(block)
        self.assertIsNone(cleaned["open_edge_records_total"])
        self.assertEqual(len(cleaned["open_edge_records"]), 6)

    def test_malformed_values_become_null_without_dropping_the_record(self):
        block = group_block(3)
        records = block["open_edge_records"]
        records[0]["edge_id"] = -1
        records[0]["length_mm"] = math.inf
        records[1]["endpoints_mm"] = [[0.0, 0.0, math.nan], [1.0, 0.0, 0.0]]
        records[1]["quilt_id"] = True
        records[2]["endpoints_mm"] = [[0.0, 0.0, 0.0]]
        records[2]["reason"] = "endpoint_eval_failed"
        records[2]["query_code"] = -3
        cleaned = normalize_surface_group(block)["open_edge_records"]
        self.assertEqual(len(cleaned), 3)
        self.assertIsNone(cleaned[0]["edge_id"])
        self.assertIsNone(cleaned[0]["length_mm"])
        self.assertIsNone(cleaned[1]["endpoints_mm"])
        self.assertIsNone(cleaned[1]["quilt_id"])
        self.assertIsNone(cleaned[2]["endpoints_mm"])
        self.assertEqual(cleaned[2]["reason"], "endpoint_eval_failed")
        self.assertEqual(cleaned[2]["query_code"], -3)

    def test_receipts_without_the_list_gain_no_keys(self):
        block = group_block()
        for key in (
            "open_edge_records",
            "open_edge_records_total",
            "open_edge_records_truncated",
            "open_edge_records_status",
        ):
            del block[key]
        cleaned = normalize_surface_group(block)
        self.assertFalse(any(key.startswith("open_edge_records") for key in cleaned))

    def test_persisted_measurement_record_is_projected(self):
        block = group_block(open_edge_records_status=status(scale_to_mm_known=False))
        result = {"operations": [{"op": "surface_group_measure", "group": block}]}
        annotate_surface_group(result)
        records = result["operations"][0]["group"]["open_edge_records"]
        self.assertTrue(all(record["endpoints_mm"] is None for record in records))


class OpenEdgeRecordBudgetTests(unittest.TestCase):
    def full_bound_group(self) -> dict:
        """The largest receipt the bound allows next to a busy group."""
        block = group_block(80)
        block["quilt_ids"] = list(range(21, 29))
        block["quilt_count"] = 8
        block["faces"] = [{"surface_id": 100 + i, "quilt_index": i % 8} for i in range(32)]
        block["face_count"] = 32
        block["overlap_pairs"] = [
            {
                "first_surface_id": 100 + i,
                "second_surface_id": 101 + i,
                "first_quilt_index": i % 8,
                "second_quilt_index": (i + 1) % 8,
                "area_mm2": 12.345678901234567,
            }
            for i in range(20)
        ]
        return normalize_surface_group(block)

    def test_synchronous_tool_response_stays_inside_the_budget_at_the_bound(self):
        group = self.full_bound_group()
        self.assertEqual(len(group["open_edge_records"]), 32)
        response = {
            "job_id": "0" * 32,
            "model_id": "1" * 32,
            "revision": 12,
            "readonly": True,
            "unit_name": "mm",
            "length_scale_to_mm": 1.0,
            "tolerance_mm": 0.01,
            "gap_search_mm": 1.0,
            "group": group,
        }
        self.assertLess(serialized_size(response), RESPONSE_BUDGET * 3 // 4)

    def test_compact_job_samples_the_list_and_keeps_the_scalars(self):
        record = {
            "op": "surface_group_measure",
            "index": 0,
            "succeeded": True,
            "execution_status": "succeeded",
            "unit_name": "mm",
            "length_scale_to_mm": 1.0,
            "group": self.full_bound_group(),
        }
        self.assertIn("group", compact_operation(record))
        manifest = {
            "job_id": "j" * 32,
            "model_id": "m" * 32,
            "status": "succeeded",
            "readonly": True,
            "operations": [{"op": "surface_group_measure"}],
            "result": {"success": True, "operations": [record]},
        }
        summary = bridge.compact_job(manifest)
        self.assertLessEqual(serialized_size(summary), RESPONSE_BUDGET)
        group = summary["result"]["operations"][0]["group"]
        self.assertNotIn("detail_truncated", summary["result"]["operations"][0])
        self.assertEqual(group["open_edge_records"]["total"], 32)
        self.assertIs(group["open_edge_records"]["truncated"], True)
        self.assertEqual(group["open_edge_records_total"], 80)
        self.assertIs(group["open_edge_records_truncated"], True)
        self.assertEqual(group["state"], "closed")

    def test_budget_trim_keeps_the_group_scalars_and_drops_the_lists(self):
        record = {
            "op": "surface_group_measure",
            "index": 0,
            "succeeded": True,
            "execution_status": "succeeded",
            "group": self.full_bound_group(),
        }
        summary = {"job_id": "j", "result": {"operations": [record]}}
        trimmed = enforce_compact_budget(copy.deepcopy(summary), budget=1500)
        kept = trimmed["result"]["operations"][0]
        self.assertTrue(kept["detail_truncated"])
        self.assertEqual(set(kept["group"]), set(SURFACE_GROUP_OUTCOME_KEYS))
        self.assertEqual(kept["group"]["open_edges"], 80)
        self.assertEqual(kept["group"]["open_edge_records_total"], 80)
        self.assertIs(kept["group"]["open_edge_records_truncated"], True)
        self.assertEqual(kept["group"]["state"], "closed")
        self.assertNotIn("open_edge_records", kept["group"])
        self.assertNotIn("faces", kept["group"])

    def test_other_operations_are_trimmed_as_before(self):
        record = {
            "op": "surface_loft",
            "index": 0,
            "succeeded": True,
            "quilt_id": 7,
            "group": {"state": "open"},
            "surface_group": {"group": group_block()},
        }
        trimmed = enforce_compact_budget({"result": {"operations": [record]}}, budget=10)
        kept = trimmed["result"]["operations"][0]
        self.assertNotIn("group", kept)
        self.assertNotIn("surface_group", kept)
        self.assertEqual(kept["quilt_id"], 7)


class OpenEdgeRecordPublicTextTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_description_names_the_list_its_bound_and_live_status(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        text = " ".join(tools["creo_measure_surface_group"].description.split())
        for phrase in (
            "group.open_edge_records",
            "live-verified on Creo 12.4.0.0",
            "{kind:'edge',id:N}",
            "At most 32 records",
            "open_edge_records_total always equals open_edges",
            "open_edge_records_truncated=true",
            "endpoints_mm",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("live acceptance pending", text)

    def test_capability_limits_publish_the_edge_id_channel(self):
        limits = capabilities.families()["surface_chain"]["limits"]
        self.assertIn("open_edge_records", limits)
        self.assertIn("quilt edge id channel", limits)
        self.assertIn("FEAT-065 T1b, live-verified on Creo 12.4.0.0", limits)
        self.assertNotIn("not live-verified", limits)

    def test_reference_syntax_points_quilt_edges_at_the_measurement(self):
        text = (ROOT / "docs" / "REFERENCE_SYNTAX.md").read_text(encoding="utf-8")
        self.assertIn("creo_measure_surface_group", text)
        self.assertIn("group.open_edge_records", text)
        self.assertNotIn("quilt 边目前没有公开的 ID 发现通道", text)


class OpenEdgeRecordNativeContractTests(unittest.TestCase):
    def setUp(self):
        self.code = _code(NATIVE.read_text(encoding="utf-8"))

    def test_bound_matches_the_python_projection(self):
        match = re.search(r"SURFACE_GROUP_OPEN_EDGE_RECORD_LIMIT = (\d+);", self.code)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), SURFACE_GROUP_OPEN_EDGE_RECORD_LIMIT)

    def test_only_the_measurement_receipt_carries_the_list(self):
        self.assertIn("bool with_open_edge_records = false", self.code)
        self.assertRegex(
            self.code,
            r"surface_group_receipt\(quilt_ids, tolerance_mm, gap_search_mm,\s*"
            r"/\*with_open_edge_records=\*/true\)",
        )
        for name in ("surface_loft.cpp", "surface_boundary_fill.cpp"):
            with self.subTest(module=name):
                other = _code((ROOT / "native" / name).read_text(encoding="utf-8"))
                self.assertNotIn("with_open_edge_records", other)
                self.assertNotIn("open_edge_records", other)

    def test_endpoints_are_the_edge_parameter_ends_with_their_codes(self):
        self.assertIn("ProEdgeXyzdataEval(edge, (double)end", self.code)
        self.assertIn(
            "record.endpoints_code = group_edge_endpoints(edge, record.endpoints);", self.code
        )
        self.assertIn("const ProError id_code = ProEdgeIdGet(edge, &edge_id);", self.code)
        self.assertIn("record.sample_code = sample_code;", self.code)

    def test_records_follow_the_open_edges_definition_and_the_unit_rule(self):
        start = self.code.index("static GroupOpenEdgeRecords group_open_edge_records(")
        body = self.code[start : self.code.index("static void group_state_decide(", start)]
        self.assertIn("if (edge.joined)\n            continue;", body)
        self.assertIn("scaled && edge.endpoints_ok", body)
        self.assertIn("scaled && has_length", body)
        self.assertIn("quilt_ids[edge.quilt_index]", body)
        receipt = self.code[self.code.index("if (with_open_edge_records) {") :]
        self.assertIn('scaled ? J(nullptr) : J("unit_scale_unknown")', receipt)
        self.assertIn(
            'group["open_edge_records"] = listed ? open_records.records : J(nullptr);', receipt
        )

    def test_compiled_record_builder_matches_its_contract(self):
        if os.name != "nt" or not (ROOT / "config.json").exists():
            self.skipTest("local Windows compiler configuration not available")
        from creo_mechdog.build_support import compiler_setup_script

        source = NATIVE.read_text(encoding="utf-8")
        start = source.index("struct GroupOpenEdgeRecords {")
        end = source.index("// Group-state decision.", start)
        directory = ROOT / "build" / "surface_group_open_edges_test"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "open_edges_under_test.inc").write_text(source[start:end], encoding="utf-8")
        settings = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
        exe = directory / "open_edges.exe"
        batch = directory / "build.cmd"
        batch.write_text(
            "@echo off\n"
            + compiler_setup_script(settings)
            + f'\ncl /nologo /std:c++17 /EHsc /utf-8 /I "{directory}" '
            + f'/Fo:"{directory / "open_edges.obj"}" /Fe:"{exe}" '
            + f'"{HARNESS}"\nexit /b %errorlevel%\n',
            encoding="utf-8",
        )
        built = subprocess.run(
            ["cmd.exe", "/d", "/c", str(batch)],
            cwd=directory,
            capture_output=True,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(
            built.returncode, 0, (built.stdout + built.stderr).decode(errors="replace")
        )
        ran = subprocess.run(
            [str(exe)], capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.assertEqual(ran.returncode, 0, f"open edge record case {ran.returncode} failed")


if __name__ == "__main__":
    unittest.main()
