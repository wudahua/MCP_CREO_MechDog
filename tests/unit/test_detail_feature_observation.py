"""FEAT-051 / N04: round/chamfer/draft result observability contract locks.

Frozen contract (docs/work-items/FEAT-051.md, 2026-10-30 N04): executed
round/chamfer/draft records carry volume_before_mm3 / volume_after_mm3 /
material_delta_mm3 plus material_measurement{status,before_query_code,
after_query_code}; draft adds the feature-tree readback draft_geometry and
all three add reference_application (requested_set_count vs tree-proven
applied_set_count). Values the native executor did not establish stay null;
Python only passes the blocks through and never derives geometry.
"""

from __future__ import annotations

import copy
import math
import unittest
from pathlib import Path

import bridge
from creo_mechdog import operation_results
from creo_mechdog.model_queries import RESPONSE_BUDGET, serialized_size

NATIVE = Path(__file__).resolve().parents[2] / "native"

MEASUREMENT_KEYS = (
    "volume_before_mm3",
    "volume_after_mm3",
    "material_delta_mm3",
    "material_measurement",
)
READBACK_KEYS = ("draft_geometry", "reference_application")
OBSERVATION_KEYS = MEASUREMENT_KEYS + READBACK_KEYS
# Bounded-projection ceiling for all six blocks on one operation record.
BLOCK_BOUND = 1600


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def measured_operation(**overrides) -> dict:
    record = {
        "op": "draft",
        "index": 0,
        "label": "d11_boss",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "unknown",
        "volume_before_mm3": 3895.580255,
        "volume_after_mm3": 3880.174229,
        "material_delta_mm3": -15.406026,
        "material_measurement": {
            "status": "measured",
            "before_query_code": 0,
            "after_query_code": 0,
        },
        "draft_geometry": {
            "source": "feature_tree",
            "query_code": 0,
            "neutral_plane": {"type": 54, "id": 627, "query_code": 0},
            "pull_direction": {"type": 54, "id": 627, "query_code": 0},
            "flip": True,
            "angle_deg": 11.0,
            "pull_vector": {
                "frame": "model",
                "vector": [0.0, 1.0, 0.0],
                "source": "plane_normal",
                "query_code": 0,
            },
        },
        "reference_application": {
            "requested_set_count": 1,
            "applied_set_count": 1,
            "source": "feature_tree",
            "query_code": 0,
        },
    }
    record.update(overrides)
    return record


def unknown_measurement_operation(**overrides) -> dict:
    record = {
        "op": "round",
        "index": 0,
        "label": "fillet",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "unknown",
        "volume_before_mm3": None,
        "volume_after_mm3": None,
        "material_delta_mm3": None,
        "material_measurement": {
            "status": "unknown",
            "before_query_code": 11,
            "after_query_code": None,
        },
        "reference_application": {
            "requested_set_count": 2,
            "applied_set_count": None,
            "source": "unknown",
            "query_code": -1,
        },
    }
    record.update(overrides)
    return record


def annotate(result: dict, inputs: list | None = None) -> dict:
    return operation_results.annotate_native_result(
        result, readonly=False, inputs=inputs if inputs is not None else []
    )


class NativeSourceContractTests(unittest.TestCase):
    """The native side owns the measurement; its field names are contract."""

    def test_generic_emits_the_material_measurement_contract(self):
        source = native_source("generic.cpp")
        for token in (
            "volume_before_mm3",
            "volume_after_mm3",
            "material_delta_mm3",
            "material_measurement",
            "before_query_code",
            "after_query_code",
            '"measured"',
            '"unknown"',
            '"not_applicable"',
            "ProSolidMassPropertyWithDensityGet",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_generic_emits_reference_application_for_round_and_chamfer(self):
        source = native_source("generic.cpp")
        for token in (
            "reference_application",
            "requested_set_count",
            "applied_set_count",
            "PRO_E_RNDCH_SET",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_advanced_emits_the_draft_geometry_readback(self):
        source = native_source("advanced.cpp")
        for token in (
            "draft_geometry",
            "reference_application",
            "plane_normal",
            "axis_direction",
            "PRO_E_DIRECTION_FLIP",
            "PRO_E_DRAFT_ANGLE_1",
            "ProFeatureElemtreeExtract",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_material_fields_absent_from_the_old_cut_contract(self):
        # The legacy cut field keeps its own meaning; the new contract never
        # renames or repurposes it.
        source = native_source("generic.cpp")
        self.assertIn("material_removed_mm3", source)

    def test_python_projection_never_derives_material_geometry(self):
        source = (
            Path(__file__).resolve().parents[2] / "src" / "creo_mechdog" / "operation_results.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("material_delta", source)
        self.assertNotIn("draft_geometry", source)
        self.assertNotIn("reference_application", source)


class ProjectionPassThroughTests(unittest.TestCase):
    """Real native blocks pass through; nothing is filled, dropped or upgraded."""

    def test_real_native_blocks_pass_through_unchanged(self):
        record = measured_operation()
        expected = copy.deepcopy(record)
        annotated = annotate({"success": True, "operations": [copy.deepcopy(record)]})
        for key in OBSERVATION_KEYS:
            with self.subTest(key=key):
                self.assertEqual(annotated["operations"][0][key], expected[key])

    def test_missing_blocks_are_not_fabricated(self):
        annotated = annotate(
            {"success": True, "operations": [{"op": "round", "index": 0, "succeeded": True}]},
            inputs=[{"op": "round", "label": "", "size": 2.0, "references": []}],
        )
        record = annotated["operations"][0]
        for key in OBSERVATION_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, record)

    def test_unestablished_values_stay_null(self):
        record = unknown_measurement_operation()
        annotated = annotate({"success": True, "operations": [copy.deepcopy(record)]})
        projected = annotated["operations"][0]
        self.assertIsNone(projected["volume_before_mm3"])
        self.assertIsNone(projected["volume_after_mm3"])
        self.assertIsNone(projected["material_delta_mm3"])
        self.assertIsNone(projected["material_measurement"]["after_query_code"])
        self.assertEqual(projected["material_measurement"]["status"], "unknown")
        self.assertIsNone(projected["reference_application"]["applied_set_count"])

    def test_zero_material_delta_is_reported_as_zero(self):
        record = measured_operation(
            volume_before_mm3=50.0, volume_after_mm3=50.0, material_delta_mm3=0.0
        )
        annotated = annotate({"success": True, "operations": [copy.deepcopy(record)]})
        projected = annotated["operations"][0]
        self.assertEqual(projected["material_delta_mm3"], 0.0)
        self.assertIsNotNone(projected["material_delta_mm3"])
        self.assertEqual(projected["material_measurement"]["status"], "measured")

    def test_not_executed_records_carry_no_readings(self):
        record = {
            "op": "draft",
            "index": 2,
            "label": "d_late",
            "succeeded": False,
            "execution_status": "not_executed",
            "effect_status": "no_effect",
        }
        annotated = annotate({"success": False, "operations": [record]})
        projected = annotated["operations"][0]
        self.assertEqual(projected["execution_status"], "not_executed")
        for key in OBSERVATION_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, projected)

    def test_rolled_back_prior_change_keeps_its_measurements(self):
        # The native finalizer labels the executed prior change rolled_back
        # when the rollback is verified; the measurement stays as history.
        record = measured_operation(index=0, effect_status="rolled_back")
        annotated = annotate({"success": False, "operations": [copy.deepcopy(record)]})
        projected = annotated["operations"][0]
        self.assertEqual(projected["effect_status"], "rolled_back")
        for key in OBSERVATION_KEYS:
            with self.subTest(key=key):
                self.assertEqual(projected[key], record[key])

    def test_rollback_evidence_labels_unfinalized_records_without_touching_readings(self):
        record = measured_operation(index=0)
        record.pop("effect_status")
        normalized = operation_results.normalize_operations(
            [record], job_status="failed", rollback_confirmed=True
        )
        self.assertEqual(normalized[0]["effect_status"], "rolled_back")
        self.assertEqual(normalized[0]["material_delta_mm3"], -15.406026)
        self.assertEqual(normalized[0]["material_measurement"]["status"], "measured")

    def test_failed_operation_keeps_partial_measurement_as_is(self):
        record = unknown_measurement_operation(
            execution_status="failed",
            effect_status="unknown",
            succeeded=False,
            material_measurement={
                "status": "unknown",
                "before_query_code": 0,
                "after_query_code": None,
            },
            volume_before_mm3=100.5,
        )
        annotated = annotate({"success": False, "operations": [copy.deepcopy(record)]})
        projected = annotated["operations"][0]
        self.assertEqual(projected["execution_status"], "failed")
        self.assertEqual(projected["volume_before_mm3"], 100.5)
        self.assertIsNone(projected["volume_after_mm3"])
        self.assertIsNone(projected["material_delta_mm3"])

    def test_one_record_per_input_survives_projection(self):
        operations = [
            measured_operation(index=0, label="f0"),
            unknown_measurement_operation(index=1, label="f1"),
            {
                "op": "chamfer",
                "index": 2,
                "label": "c0",
                "execution_status": "not_executed",
                "effect_status": "no_effect",
                "succeeded": False,
            },
        ]
        annotated = annotate({"success": False, "operations": copy.deepcopy(operations)})
        self.assertEqual(len(annotated["operations"]), 3)
        self.assertEqual([op["index"] for op in annotated["operations"]], [0, 1, 2])


class CompactFullPassThroughTests(unittest.TestCase):
    """compact and full views carry the same observation blocks."""

    def test_compact_keeps_all_observation_keys(self):
        record = measured_operation()
        compact = bridge.compact_job({"result": {"operations": [copy.deepcopy(record)]}})
        projected = compact["result"]["operations"][0]
        for key in OBSERVATION_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, projected)
                self.assertEqual(projected[key], record[key])

    def test_compact_keeps_unknown_blocks_with_nulls(self):
        record = unknown_measurement_operation()
        compact = bridge.compact_job({"result": {"operations": [copy.deepcopy(record)]}})
        projected = compact["result"]["operations"][0]
        self.assertEqual(projected["material_measurement"], record["material_measurement"])
        self.assertIsNone(projected["volume_after_mm3"])

    def test_compact_does_not_add_blocks_to_plain_records(self):
        compact = bridge.compact_job(
            {"result": {"operations": [{"op": "round", "index": 0, "succeeded": True}]}}
        )
        record = compact["result"]["operations"][0]
        for key in OBSERVATION_KEYS:
            self.assertNotIn(key, record)


class ResponseBudgetTests(unittest.TestCase):
    """Bounded projection: fixed-size blocks, no unbounded lists.

    The hard 32 KiB page budget is enforced (with paging) by the capabilities
    and model-query tools, which carry no operations[] and are unaffected here.
    Compact job results bound each projection instead: the observation blocks
    are fixed-size and add at most BLOCK_BOUND bytes per operation.
    """

    def test_each_observation_block_stays_small(self):
        record = measured_operation()
        for key in OBSERVATION_KEYS:
            with self.subTest(key=key):
                self.assertLess(serialized_size(record[key]), 1024)

    def test_observation_overhead_per_operation_is_bounded(self):
        record = measured_operation()
        lean = {key: value for key, value in record.items() if key not in OBSERVATION_KEYS}
        overhead = serialized_size(record) - serialized_size(lean)
        self.assertLessEqual(overhead, BLOCK_BOUND)

    def test_single_operation_job_stays_inside_the_response_budget(self):
        # The standalone tools (creo_round/creo_chamfer/creo_draft) submit one
        # operation per job; that public response keeps the 32 KiB budget.
        compact = bridge.compact_job({"result": {"operations": [measured_operation()]}})
        self.assertLessEqual(serialized_size(compact), RESPONSE_BUDGET)


class DriverFormulaTests(unittest.TestCase):
    """Independent geometry oracles behind the fixture expectations."""

    def test_convex_round_delta_matches_the_corner_cross_section(self):
        from tools import test_detail_feature_observation as driver

        expected = 20.0 * 3.0**2 * (1.0 - math.pi / 4.0)
        self.assertAlmostEqual(
            driver.round_delta_mm3(length=20.0, radius=3.0, concave=False), -expected, places=9
        )
        self.assertAlmostEqual(
            driver.round_delta_mm3(length=20.0, radius=3.0, concave=True), expected, places=9
        )

    def test_chamfer_delta_matches_the_triangle_prism(self):
        from tools import test_detail_feature_observation as driver

        self.assertAlmostEqual(
            driver.chamfer_delta_mm3(length=20.0, distance=2.0), -20.0 * 2.0**2 / 2.0, places=9
        )

    def test_draft_11deg_cylinder_matches_the_reported_analytic_case(self):
        from tools import test_detail_feature_observation as driver

        inward = driver.draft_delta_mm3(radius=3.0, height=3.0, angle_deg=11.0, inward=True)
        outward = driver.draft_delta_mm3(radius=3.0, height=3.0, angle_deg=11.0, inward=False)
        # External 0.8.5 report analytic values for the same cylinder/angle.
        self.assertAlmostEqual(inward, -15.416, places=2)
        self.assertAlmostEqual(outward, 17.555, places=2)
        self.assertLess(inward, 0.0)
        self.assertGreater(outward, 0.0)

    def test_numeric_integration_agrees_with_the_closed_forms(self):
        from tools import test_detail_feature_observation as driver

        self.assertTrue(driver.numeric_oracles_agree(tolerance=1e-6))

    def test_volume_scale_conversion_follows_the_cube_rule(self):
        from tools import test_detail_feature_observation as driver

        self.assertEqual(driver.volume_to_mm3(8.0, 1.0), 8.0)
        self.assertEqual(driver.volume_to_mm3(8.0, 25.4), 8.0 * 25.4**3)
        self.assertIsNone(driver.volume_to_mm3(8.0, None))


class DriverFixtureMatrixTests(unittest.TestCase):
    """The offline fixture matrix covers every scenario the card names."""

    def setUp(self):
        from tools import test_detail_feature_observation as driver

        self.driver = driver
        self.cases = driver.build_cases()

    def test_matrix_covers_round_chamfer_draft_pull_and_batch(self):
        names = {case["case"] for case in self.cases}
        for required in (
            "round_convex",
            "round_concave",
            "chamfer_three_face_pairs",
            "draft_flip_false",
            "draft_flip_true",
            "draft_default_pull",
            "draft_explicit_pull",
            "batch_mid_failure",
            "zero_delta",
        ):
            with self.subTest(case=required):
                self.assertIn(required, names)

    def test_flip_pair_expect_both_analytic_directions(self):
        by_name = {case["case"]: case for case in self.cases}
        for name in ("draft_flip_false", "draft_flip_true"):
            expected = by_name[name]["expected_delta_mm3"]
            self.assertEqual(len(expected), 2)
            self.assertLess(min(expected), 0.0)
            self.assertGreater(max(expected), 0.0)

    def test_unit_matrix_covers_mm_inch_mixed_and_unknown(self):
        names = {case["name"] for case in self.driver.UNIT_CASES}
        self.assertEqual(names, {"mm", "inch", "mixed_other", "unknown"})

    def test_fixture_expectations_match_the_formulas(self):
        by_name = {case["case"]: case for case in self.cases}
        self.assertAlmostEqual(
            by_name["round_convex"]["expected_delta_mm3"][0],
            self.driver.round_delta_mm3(20.0, 3.0, concave=False),
            places=9,
        )
        self.assertAlmostEqual(
            by_name["round_concave"]["expected_delta_mm3"][0],
            self.driver.round_delta_mm3(20.0, 3.0, concave=True),
            places=9,
        )
        self.assertAlmostEqual(
            by_name["chamfer_three_face_pairs"]["expected_delta_mm3"][0],
            3 * self.driver.chamfer_delta_mm3(20.0, 2.0),
            places=9,
        )
        self.assertEqual(by_name["zero_delta"]["expected_delta_mm3"], [0.0])

    def test_case_names_are_valid_model_names(self):
        for case in self.cases:
            name = case["model_name"]
            self.assertLessEqual(len(name), 31)
            self.assertTrue(name[0].isalnum())
            self.assertTrue(all(c.islower() or c.isdigit() or c == "_" for c in name))

    def test_fixture_plans_validate_against_admission(self):
        from creo_mechdog.schema import validate_operations

        for case in self.cases:
            if case["case"] == "batch_mid_failure":
                continue  # the invalid edge id is rejected at execution, not admission
            with self.subTest(case=case["case"]):
                validate_operations(case["operations"])


class DriverJudgementTests(unittest.TestCase):
    """Judgements read measured blocks only; unknowns never pass as measured."""

    def setUp(self):
        from tools import test_detail_feature_observation as driver

        self.driver = driver

    def record(self, delta, status="measured", **overrides):
        record = {
            "op": "round",
            "material_delta_mm3": delta,
            "volume_before_mm3": 100.0,
            "volume_after_mm3": 100.0 + delta if delta is not None else None,
            "material_measurement": {
                "status": status,
                "before_query_code": 0,
                "after_query_code": 0,
            },
        }
        record.update(overrides)
        return record

    def test_matching_measured_delta_passes(self):
        verdict = self.driver.judge_measurement(
            self.record(-38.6282), [-38.6282, 38.6282], tolerance=0.01
        )
        self.assertEqual(verdict["status"], "pass")

    def test_wrong_sign_or_magnitude_fails(self):
        verdict = self.driver.judge_measurement(self.record(38.0), [-38.6282], tolerance=0.01)
        self.assertEqual(verdict["status"], "fail")

    def test_null_delta_is_never_judged_pass(self):
        verdict = self.driver.judge_measurement(self.record(None), [-15.4], tolerance=0.01)
        self.assertEqual(verdict["status"], "unknown")

    def test_zero_delta_is_a_passing_measurement(self):
        verdict = self.driver.judge_measurement(self.record(0.0), [0.0], tolerance=0.01)
        self.assertEqual(verdict["status"], "pass")

    def test_batch_failure_verdicts_require_rollback_and_no_readings(self):
        good = self.record(-38.6282, **{"effect_status": "rolled_back"})
        failed = self.record(
            None,
            status="unknown",
            material_measurement={
                "status": "unknown",
                "before_query_code": 0,
                "after_query_code": None,
            },
            volume_after_mm3=None,
            **{"execution_status": "failed", "effect_status": "rolled_back"},
        )
        late = {
            "op": "chamfer",
            "execution_status": "not_executed",
            "effect_status": "no_effect",
            "succeeded": False,
        }
        verdict = self.driver.judge_batch_failure([good, failed, late])
        self.assertEqual(verdict["status"], "pass")

    def test_batch_failure_without_rollback_evidence_fails(self):
        good = self.record(-38.6282, **{"effect_status": "unknown"})
        failed = self.record(
            None,
            status="unknown",
            material_measurement={
                "status": "unknown",
                "before_query_code": 0,
                "after_query_code": None,
            },
            volume_after_mm3=None,
            **{"execution_status": "failed"},
        )
        late = {"op": "chamfer", "execution_status": "not_executed", "effect_status": "no_effect"}
        verdict = self.driver.judge_batch_failure([good, failed, late])
        self.assertEqual(verdict["status"], "fail")

    def test_not_executed_readings_are_rejected(self):
        good = self.record(-38.6282, **{"effect_status": "rolled_back"})
        failed = self.record(None, status="unknown", **{"execution_status": "failed"})
        late = {
            "op": "chamfer",
            "execution_status": "not_executed",
            "effect_status": "no_effect",
            "material_delta_mm3": 1.0,
        }
        verdict = self.driver.judge_batch_failure([good, failed, late])
        self.assertEqual(verdict["status"], "fail")

    def test_pull_readback_verdict_matches_the_expected_reference(self):
        geometry = {
            "pull_direction": {"type": 54, "id": 627, "query_code": 0},
        }
        self.assertEqual(
            self.driver.judge_pull_readback(geometry, {"kind": "surface", "id": 627}), "pass"
        )
        self.assertEqual(
            self.driver.judge_pull_readback(geometry, {"kind": "axis", "id": 9}), "fail"
        )
        self.assertEqual(
            self.driver.judge_pull_readback({"pull_direction": None}, {"id": 627}), "unknown"
        )
        self.assertEqual(
            self.driver.judge_pull_readback(
                {"pull_direction": {"type": None, "id": None, "query_code": -1}}, {"id": 627}
            ),
            "unknown",
        )


class DriverTerminalRevisionTests(unittest.TestCase):
    """The live runner reads the top-level manifest revision, never result.revision.

    The 2026-10-30 N04 live run crashed on ``result.revision`` with a bare
    KeyError right after the first base creation: job manifests carry the model
    revision as a top-level key. A terminal without it must fail with a clear
    RuntimeError, never a KeyError.
    """

    def setUp(self):
        from tools import test_detail_feature_observation as driver

        self.driver = driver

    def test_top_level_int_revision_is_read(self):
        terminal = {"status": "succeeded", "revision": 1, "result": {"success": True}}
        self.assertEqual(self.driver.terminal_model_revision(terminal, "base"), 1)

    def test_result_nested_revision_is_not_the_source(self):
        terminal = {"status": "succeeded", "result": {"revision": 2, "success": True}}
        with self.assertRaises(RuntimeError) as caught:
            self.driver.terminal_model_revision(terminal, "base creation")
        self.assertNotIsInstance(caught.exception, KeyError)
        self.assertIn("revision", str(caught.exception))
        self.assertIn("base creation", str(caught.exception))

    def test_missing_revision_reports_a_clear_error(self):
        with self.assertRaises(RuntimeError) as caught:
            self.driver.terminal_model_revision({"result": {"success": True}}, "base")
        self.assertNotIsInstance(caught.exception, KeyError)
        self.assertIn("revision", str(caught.exception))
        self.assertIn("top level", str(caught.exception))

    def test_non_integer_revision_is_rejected(self):
        for value in (None, True, 1.0, "1"):
            with self.subTest(revision=value):
                with self.assertRaises(RuntimeError):
                    self.driver.terminal_model_revision({"revision": value}, "base")

    def test_non_dict_terminal_is_rejected_with_context(self):
        with self.assertRaises(RuntimeError) as caught:
            self.driver.terminal_model_revision(None, "base")
        self.assertIn("base", str(caught.exception))

    def test_driver_source_no_longer_reads_result_revision(self):
        source = (
            Path(__file__).resolve().parents[2] / "tools" / "test_detail_feature_observation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('["result"]["revision"]', source)
        self.assertIn("terminal_model_revision(", source)


class DriverOfflineShellTests(unittest.TestCase):
    """Output routing and provenance stay refuse-overwrite and unique."""

    def test_default_output_is_under_the_task_run_directory(self):
        from tools import test_detail_feature_observation as driver

        path = driver.resolve_output(None, "runid123")
        self.assertIn("post090_n04", str(path))
        self.assertIn("runid123", str(path))
        self.assertEqual(path.name, "report.json")

    def test_existing_report_is_refused(self):
        import tempfile
        from pathlib import Path

        from tools import test_detail_feature_observation as driver

        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "report.json"
            existing.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                driver.resolve_output(existing, "runid123")

    def test_selection_helpers_pick_geometry_not_order(self):
        from tools import test_detail_feature_observation as driver

        edges = [
            {"id": 11, "start": [0.0, 0.0, 0.0], "end": [0.0, 0.0, 20.0]},
            {"id": 12, "start": [0.0, 0.0, 20.0], "end": [40.0, 0.0, 20.0]},
            {"id": 13, "start": [5.0, 5.0, 0.0], "end": [5.0, 5.0, 20.0]},
        ]
        picked = driver.select_vertical_edges(edges, length_mm=20.0)
        self.assertEqual(sorted(picked), [11, 13])
        surfaces = [
            {"id": 51, "type": 48, "normal": [0.0, 0.0, 1.0], "origin": [0.0, 0.0, 20.0]},
            {"id": 52, "type": 48, "normal": [1.0, 0.0, 0.0], "origin": [40.0, 0.0, 0.0]},
            {
                "id": 53,
                "type": 42,
                "radius": 3.0,
                "origin": [0.0, 0.0, 0.0],
                "axis": [0.0, 0.0, 1.0],
            },
        ]
        self.assertEqual(driver.select_plane_surface(surfaces, [0.0, 0.0, 1.0], 20.0), 51)
        self.assertEqual(driver.select_cylinder_surface(surfaces, 3.0), 53)


if __name__ == "__main__":
    unittest.main()
