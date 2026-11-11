"""FEAT-065/M3 surface_loft inputs beyond MCP sketches (offline contract).

Sections and guides may name an existing curve ``{kind:'curve',id:N}`` or edge
``{kind:'edge',id:N}``, and the first or last section may be one convergence
point. These tests lock the admission rules, the unchanged sketch path, the
receipt projection/protection and the native source contract. None of them
builds geometry: every new form is still "Creo 12.4 live acceptance pending",
and the live evidence belongs to
``tools/test_surface_loft_inputs.py --live --confirm-session-usable``.
"""

from __future__ import annotations

import asyncio
import copy
import re
import unittest
from pathlib import Path

from creo_mechdog import capabilities
from creo_mechdog import capability_pages as pages
from creo_mechdog.job_projection import SURFACE_LOFT_KEYS, compact_operation
from creo_mechdog.operation_results import (
    FAILED_EVIDENCE_KEYS,
    OUTCOME_OPERATION_KEYS,
    enforce_compact_budget,
)
from creo_mechdog.references import reference_capabilities
from creo_mechdog.schema import validate_operations
from creo_mechdog.surface_ops import LOFT_INPUT_LIVE_STATUS, SurfaceLoftOp

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_loft.cpp"
SERVER = ROOT / "server.py"
DRIVER = ROOT / "tools" / "test_surface_loft_inputs.py"


def loft(**overrides):
    operation = {"op": "surface_loft", "label": "loft_surface", "sections": ["loft_a", "loft_b"]}
    operation.update(overrides)
    return operation


def edge(identifier: int) -> dict:
    return {"kind": "edge", "id": identifier}


def curve(identifier: int) -> dict:
    return {"kind": "curve", "id": identifier}


def point(identifier: int) -> dict:
    return {"kind": "point", "id": identifier}


def tip(label: str = "tip") -> dict:
    return {"kind": "datum_point_feature", "label": label}


def rejected(operations: list[dict]) -> str:
    try:
        validate_operations(operations)
    except ValueError as error:
        return str(error)
    raise AssertionError("the plan was accepted")


class AcceptedInputTests(unittest.TestCase):
    def test_edges_as_sections_with_sketch_guides(self):
        validated = validate_operations(
            [loft(sections=[edge(12), edge(13)], guides=["guide_l", "guide_r"])]
        )
        self.assertEqual(validated[0]["sections"], [edge(12), edge(13)])
        self.assertEqual(validated[0]["guides"], ["guide_l", "guide_r"])

    def test_curve_section_mixes_with_a_sketch(self):
        validated = validate_operations([loft(sections=[curve(41), "loft_b"])])
        self.assertEqual(validated[0]["sections"], [curve(41), "loft_b"])

    def test_curve_and_edge_guides(self):
        validated = validate_operations([loft(guides=[curve(43), edge(14)])])
        self.assertEqual(validated[0]["guides"], [curve(43), edge(14)])

    def test_convergence_point_at_either_end(self):
        for sections in (
            [point(90), "loft_a"],
            ["loft_a", point(90)],
            [tip(), "loft_a", "loft_b"],
            ["loft_a", "loft_b", "loft_c", tip()],
        ):
            with self.subTest(sections=sections):
                interpolation = "smooth" if len(sections) > 2 else "straight"
                validated = validate_operations(
                    [loft(sections=sections, interpolation=interpolation)]
                )
                self.assertEqual(validated[0]["sections"], sections)

    def test_a_point_counts_as_a_section_for_interpolation(self):
        message = rejected([loft(sections=["loft_a", "loft_b", tip()])])
        self.assertIn('interpolation="smooth"', message)

    def test_reference_objects_pass_through_the_dump_unchanged(self):
        sections = [edge(12), curve(41), "loft_c", tip()]
        validated = validate_operations([loft(sections=sections, interpolation="smooth")])
        self.assertEqual(validated[0]["sections"], sections)
        self.assertIsNot(validated[0]["sections"][0], sections[0])


class LegacySketchInputTests(unittest.TestCase):
    """Strings and integers keep meaning "sketch" exactly as in M1/M2."""

    def test_labels_ids_and_digit_strings(self):
        validated = validate_operations(
            [loft(sections=["loft_a", 19, "12"], interpolation="smooth")]
        )
        self.assertEqual(validated[0]["sections"], ["loft_a", 19, 12])

    def test_old_duplicate_messages_keep_their_keywords(self):
        self.assertRegex(rejected([loft(sections=["loft_a", "loft_a"])]), "distinct")
        self.assertRegex(rejected([loft(guides=["guide_a", "guide_a"])]), "guides must be distinct")
        self.assertRegex(
            rejected([loft(guides=["loft_a", "guide_b"])]),
            "cannot be both a section and a guide",
        )
        self.assertRegex(rejected([loft(guides=["guide_a"])]), "at least two guide")

    def test_negative_and_boolean_ids_stay_refused(self):
        for sections in ([-1, 5], [True, 5]):
            with self.subTest(sections=sections):
                with self.assertRaises(ValueError):
                    validate_operations([loft(sections=sections)])


class RejectedInputTests(unittest.TestCase):
    def test_point_in_the_middle_is_refused_with_its_slot(self):
        message = rejected([loft(sections=["loft_a", point(9), "loft_b"], interpolation="smooth")])
        self.assertIn("sections[1] is a point", message)
        self.assertIn("first or last section", message)

    def test_point_guide_is_refused(self):
        for guide in (point(9), tip()):
            with self.subTest(guide=guide):
                message = rejected([loft(guides=["guide_a", guide])])
                self.assertIn("guides[1] is a point", message)
                self.assertIn("{kind:'edge',id:N}", message)

    def test_two_points_are_refused(self):
        message = rejected([loft(sections=[point(9), point(10)])])
        self.assertIn("one convergence point", message)
        message = rejected(
            [loft(sections=[tip("a_tip"), "loft_b", point(10)], interpolation="smooth")]
        )
        self.assertIn("sections[0] and sections[2] are both points", message)

    def test_repeated_references_are_refused(self):
        message = rejected([loft(sections=[edge(12), edge(12)])])
        self.assertIn("sections[1] repeats sections[0]", message)
        self.assertIn("{kind:'edge',id:12}", message)
        message = rejected([loft(guides=[curve(7), curve(7)])])
        self.assertIn("guides[1] repeats guides[0]", message)

    def test_one_reference_cannot_be_section_and_guide(self):
        message = rejected([loft(sections=[edge(12), "loft_b"], guides=[edge(12), "guide_b"])])
        self.assertIn("cannot be both a section and a guide", message)
        self.assertIn("{kind:'edge',id:12}", message)

    def test_curve_and_edge_with_the_same_number_are_different_kinds(self):
        # Two kinds are two namespaces at admission; the native resolver checks
        # the real geometry type of each id.
        validated = validate_operations([loft(sections=[curve(12), edge(12)])])
        self.assertEqual(validated[0]["sections"], [curve(12), edge(12)])

    def test_geometry_kinds_refuse_labels_and_extra_keys(self):
        for value, expected in (
            ({"kind": "curve", "label": "sec_a"}, "name a sketch by its label"),
            ({"kind": "edge", "label": "e"}, "takes an id, not a label"),
            ({"kind": "point", "label": "tip"}, "datum_point_feature"),
            ({"kind": "edge", "id": 3, "tolerance_mm": 1}, "accepts only kind and id"),
            ({"kind": "datum_point_feature", "id": 3}, "accepts only kind and label"),
            ({"kind": "datum_point_feature", "label": ""}, "non-empty label"),
        ):
            with self.subTest(value=value):
                self.assertIn(expected, rejected([loft(sections=[value, "loft_b"])]))

    def test_invalid_ids_are_refused(self):
        for identifier in (-1, True, "12", 2147483648, 1.5):
            with self.subTest(identifier=identifier):
                message = rejected([loft(sections=[{"kind": "edge", "id": identifier}, "loft_b"])])
                self.assertIn("32-bit integer geometry id", message)

    def test_unknown_or_missing_kinds_name_the_usable_forms(self):
        message = rejected([loft(sections=[{"kind": "quilt", "id": 5}, "loft_b"])])
        self.assertIn("pass one of its edges as {kind:'edge',id:N}", message)
        message = rejected([loft(sections=[{"id": 5}, "loft_b"])])
        self.assertIn("must carry a string kind", message)
        self.assertIn("{kind:'curve',id:N}", message)
        message = rejected([loft(sections=["loft_a", {"kind": "sketch_curves", "label": "s"}])])
        self.assertIn("is not a loft input", message)
        self.assertIn("{kind:'point',id:N}", message)

    def test_messages_stay_inside_the_public_bound(self):
        message = rejected([loft(guides=["guide_a", point(9)])])
        self.assertLess(len(message), 700)


class PlanLevelPointTests(unittest.TestCase):
    def datum(self, label: str, count: int) -> dict:
        return {
            "op": "datum_points",
            "label": label,
            "points": [{"name": f"p{index}", "position": [index, 0, 0]} for index in range(count)],
        }

    def test_single_point_producer_earlier_in_the_plan(self):
        validated = validate_operations([self.datum("tip", 1), loft(sections=["loft_a", tip()])])
        self.assertEqual(validated[1]["sections"][1], tip())

    def test_multi_point_producer_is_refused(self):
        message = rejected([self.datum("tip", 2), loft(sections=["loft_a", tip()])])
        self.assertIn("operations[1].sections[1]", message)
        self.assertIn("single-point datum_points feature", message)

    def test_non_datum_points_producer_is_refused(self):
        sketch = {
            "op": "sketch",
            "label": "tip",
            "plane": "XY",
            "entities": [{"type": "line", "name": "l", "start": [0, 0], "end": [1, 0]}],
        }
        message = rejected([sketch, loft(sections=["loft_a", tip()])])
        self.assertIn("op 'sketch'", message)

    def test_later_producer_is_refused(self):
        message = rejected([loft(sections=["loft_a", tip()]), self.datum("tip", 1)])
        self.assertIn("not before the surface_loft", message)

    def test_a_label_from_an_earlier_plan_is_left_to_the_native_resolver(self):
        validated = validate_operations([loft(sections=[tip("old_tip"), "loft_b"])])
        self.assertEqual(validated[0]["sections"][0], tip("old_tip"))


class PublicSurfaceTests(unittest.TestCase):
    def test_tool_schema_accepts_reference_objects(self):
        import server

        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        schema = tools["creo_surface_loft"].input_schema["properties"]
        for name in ("sections", "guides"):
            text = repr(schema[name])
            with self.subTest(parameter=name):
                self.assertIn("'object'", text)
                self.assertIn("'integer'", text)
                self.assertIn("'string'", text)
        description = tools["creo_surface_loft"].description
        self.assertIn("live acceptance pending", description)
        self.assertIn("SURFACE_LOFT_INPUT_REJECTED", description)

    def test_model_annotation_carries_the_reference_form(self):
        annotation = repr(SurfaceLoftOp.model_fields["sections"].annotation)
        self.assertIn("dict", annotation)

    def test_capability_limits_name_the_unverified_forms(self):
        limits = capabilities.families()["surface_loft"]["limits"]
        for phrase in (
            "FEAT-065 M3",
            "not live-verified on Creo 12.4",
            "{kind:'curve',id:N}",
            "{kind:'edge',id:N}",
            "first or last section only",
            "PRO_CURVCOLL_ADD_POINT_INSTR",
            "unverified_input_forms",
            "SURFACE_LOFT_INPUT_REJECTED",
            "creo_measure_surface_group group.open_edge_records",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, limits)
        self.assertIn("live acceptance pending", capabilities.families()["surface_loft"]["scope"])
        self.assertIn("not live-verified", capabilities.families()["surface_chain"]["limits"])
        self.assertNotIn(
            "exactly two single-curve", capabilities.families()["surface_chain"]["scope"]
        )

    def test_compact_limits_note_keeps_its_published_prefix(self):
        pages.reset_snapshot()
        import server

        compact = pages.capabilities_response(lambda: server._capabilities_payload([]))
        note = compact["families"]["surface_loft"]["limits_note"]
        self.assertIn("2-32 sections", note)
        self.assertIn("straight is exact only with two sections", note)

    def test_reference_examples_validate(self):
        entry = reference_capabilities()["by_tool"]["creo_surface_loft"]
        operations = [
            loft(sections=entry["sections"]),
            loft(sections=[entry["section_curve"], entry["section_edge"]]),
            loft(sections=[entry["convergence_point"], "loft_b"]),
            loft(sections=["loft_a", entry["convergence_point_by_label"]]),
            loft(guides=entry["guides"]),
            loft(guides=entry["guide_curve_or_edge"]),
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                validate_operations([operation])
        self.assertIn("not live-verified", entry["live_status"])
        self.assertIn("SURFACE_LOFT_INPUT_REJECTED", entry["rejected"]["unknown_id"])

    def test_live_status_marker_is_published(self):
        self.assertIn("pending", LOFT_INPUT_LIVE_STATUS)


def loft_record(**extra) -> dict:
    record = {
        "op": "surface_loft",
        "index": 0,
        "label": "loft_surface",
        "succeeded": True,
        "execution_status": "succeeded",
        "effect_status": "committed",
        "quilt_id": 77,
        "quilt_count": 1,
        "quilt_closed_native": "open",
        "has_solid": False,
        "surface_area_mm2": 800.0,
        "surface_area_status": {"available": True},
        "section_count": 2,
        "section_curve_ids": [],
        "section_source_kinds": ["edge", "edge"],
        "section_geometry_ids": [[12], [13]],
        "section_sources": [
            {"index": 0, "source": "edge", "ids": [12], "adjacent_surface_ids": [40]},
            {"index": 1, "source": "edge", "ids": [13], "adjacent_surface_ids": [41]},
        ],
        "guide_count": 2,
        "guide_curve_ids": [51, 52],
        "guide_source_kinds": ["sketch", "sketch"],
        "guide_geometry_ids": [[51], [52]],
        "guide_sources": [],
        "convergence_point": None,
        "unverified_input_forms": ["edge"],
    }
    record.update(extra)
    return record


class ReceiptProjectionTests(unittest.TestCase):
    def test_compact_projection_keeps_the_new_fields(self):
        for key in (
            "section_source_kinds",
            "section_geometry_ids",
            "section_sources",
            "guide_source_kinds",
            "guide_geometry_ids",
            "guide_sources",
            "convergence_point",
            "unverified_input_forms",
            "failed_loft_input",
        ):
            with self.subTest(key=key):
                self.assertIn(key, SURFACE_LOFT_KEYS)
        compact = compact_operation(loft_record())
        self.assertEqual(compact["section_source_kinds"], ["edge", "edge"])
        self.assertEqual(compact["section_geometry_ids"], [[12], [13]])
        self.assertEqual(compact["unverified_input_forms"], ["edge"])
        self.assertEqual(compact["section_sources"][0]["adjacent_surface_ids"], [40])

    def test_source_identity_is_protected_from_the_budget_trim(self):
        for key in (
            "section_source_kinds",
            "section_geometry_ids",
            "guide_source_kinds",
            "guide_geometry_ids",
            "unverified_input_forms",
        ):
            with self.subTest(key=key):
                self.assertIn(key, OUTCOME_OPERATION_KEYS)
        self.assertIn("failed_loft_input", FAILED_EVIDENCE_KEYS)
        record = loft_record(section_sources=[{"blob": "x" * 4000}])
        summary = {"status": "succeeded", "result": {"operations": [record]}}
        trimmed = enforce_compact_budget(copy.deepcopy(summary), budget=1500)
        kept = trimmed["result"]["operations"][0]
        self.assertTrue(kept["detail_truncated"])
        self.assertNotIn("section_sources", kept)
        self.assertEqual(kept["section_source_kinds"], ["edge", "edge"])
        self.assertEqual(kept["section_geometry_ids"], [[12], [13]])
        self.assertEqual(kept["unverified_input_forms"], ["edge"])
        self.assertEqual(kept["surface_area_mm2"], 800.0)

    def test_a_failed_input_block_survives_the_trim(self):
        failure = {
            "role": "section",
            "index": 0,
            "slot": "sections[0]",
            "request": {"kind": "edge", "id": 999999},
            "reason": "edge_not_found",
            "query_code": -1,
            "use_instead": "pass a current edge id from creo_inspect_model",
        }
        record = loft_record(
            succeeded=False,
            execution_status="failed",
            effect_status="rolled_back",
            failed_loft_input=failure,
            section_sources=[{"blob": "x" * 4000}],
        )
        summary = {
            "status": "failed",
            "result": {"operations": [record], "failed_operation_index": 0},
        }
        trimmed = enforce_compact_budget(copy.deepcopy(summary), budget=1800)
        kept = trimmed["result"]["operations"][0]
        self.assertEqual(kept["failed_loft_input"], failure)


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        self.text = NATIVE.read_text(encoding="utf-8")
        start = self.text.index("#if MECHDOG_HAS_PROBBL_HEADER")
        end = self.text.index("#else", start)
        self.gated = self.text[start:end]

    def test_new_resolution_lives_inside_the_probbl_gate(self):
        for symbol in (
            "struct SurfaceLoftInput",
            "static SurfaceLoftInput surface_loft_input(",
            "static void surface_loft_reject(",
            "static ProError surface_loft_probe(",
            "static void surface_loft_point_chain(",
            "static void surface_loft_chain(",
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, self.gated)
                self.assertEqual(self.text.count(symbol), 1)

    def test_sketch_path_still_uses_the_m1_resolver(self):
        code = _code(self.gated)
        self.assertIn("input.ids = surface_loft_curves(reference, legacy.c_str());", code)
        # The M1/M2 refusal texts stay byte-identical for sketch inputs.
        for message in (
            '" repeats curve "',
            '"; every section must name a different sketch"',
            '" repeats a guide sketch; every guide must be a "',
            '" must own exactly one non-composite curve; a guide is one curve "',
            '" as a section; a guide must be its own curve"',
        ):
            with self.subTest(message=message):
                self.assertIn(message, code)

    def test_explicit_ids_are_proved_before_the_tree_is_built(self):
        code = _code(self.gated)
        for call in (
            "ProModelitemInit(board, id, type, &item)",
            "ProCurveInit((ProSolid)board, id, &curve)",
            "ProEdgeInit((ProSolid)board, id, &edge)",
            "ProPointInit((ProSolid)board, id, &point)",
            "ProEdgeNeighborsGet(",
            "PRO_FEAT_DATUM_POINT",
        ):
            with self.subTest(call=call):
                self.assertIn(call, code)
        self.assertLess(
            code.index("surface_loft_input(sections[index]"),
            code.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        )

    def test_rejections_are_structured(self):
        code = _code(self.gated)
        self.assertIn('"SURFACE_LOFT_INPUT_REJECTED: surface_loft "', code)
        self.assertIn('details["failed_loft_input"]', code)
        for reason in (
            "curve_not_found",
            "edge_not_found",
            "point_not_found",
            "point_not_at_end",
            "point_in_guides",
            "second_point",
            "repeated_geometry",
            "unsupported_kind",
            "invalid_id",
            "label_not_found",
            "not_a_datum_point_feature",
            "point_count",
        ):
            with self.subTest(reason=reason):
                self.assertIn(f'"{reason}"', code)
        for key in ("role", "index", "slot", "request", "reason", "query_code", "use_instead"):
            with self.subTest(key=key):
                self.assertIn(f'{{"{key}", ', code)

    def test_point_chain_is_the_documented_instruction_and_marked_unproven(self):
        code = _code(self.gated)
        self.assertIn("ProCrvcollinstrAlloc(PRO_CURVCOLL_ADD_POINT_INSTR, &instruction)", code)
        self.assertIn("SURFACE_LOFT_POINT_CHAIN_REFUSED", code)
        self.assertIn('{"live_verified", false}', code)

    def test_receipt_fields_are_written(self):
        code = _code(self.gated)
        for key in (
            "section_source_kinds",
            "section_geometry_ids",
            "section_sources",
            "guide_source_kinds",
            "guide_geometry_ids",
            "guide_sources",
            "convergence_point",
            "unverified_input_forms",
            "adjacent_surface_ids",
        ):
            with self.subTest(key=key):
                self.assertRegex(code, rf'"{re.escape(key)}"')
        # The M1/M2 curve lists keep meaning "PRO_CURVE ids only".
        self.assertIn(
            "if (input.type == PRO_CURVE)\n                curve_ids.push_back(id);", code
        )

    def test_tangency_elements_stay_unwritten(self):
        # FEAT-065/M4 may write PRO_E_BNBLN_TAN_COND* into the extracted tree
        # only; the creation tree never carries them.
        code = _code(self.text)
        creation = code[
            code.index("node(nullptr, PRO_E_FEATURE_TREE)") : code.index(
                "ProFeatureWithoptionsCreate("
            )
        ]
        self.assertNotIn("PRO_E_BNBLN_TAN_COND", creation)
        self.assertNotIn("PRO_E_BBL_ADD_CLOSED", code)


class DriverContractTests(unittest.TestCase):
    def test_driver_has_offline_default_and_the_four_live_cases(self):
        text = DRIVER.read_text(encoding="utf-8")
        self.assertIn("--confirm-session-usable", text)
        for case in (
            "case_a_edge_bridge",
            "case_b_projected_curve",
            "case_c_bulb_convergence",
            "case_d_negative",
        ):
            with self.subTest(case=case):
                self.assertIn(f"def {case}(", text)
        self.assertIn('"plane": "YZ"', text)


if __name__ == "__main__":
    unittest.main()
