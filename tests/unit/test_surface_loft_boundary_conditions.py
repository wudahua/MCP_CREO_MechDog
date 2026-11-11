"""FEAT-065/M4 surface_loft boundary conditions (offline candidate, gated).

``boundary_conditions`` names the continuity between one loft boundary and the
face next to it. Probbl.h documents only ``TAN_COND_FREE`` for
``PRO_E_BNBLN_TAN_COND_TYPE`` and gives it no parsable value, so the field is
validated but refused before a job exists (``capabilities.UNAVAILABLE_FIELDS``)
until FEAT-065 T2b reads the real integers from a Creo-built reference part.
These tests lock the gate, the field shape, the unchanged legacy plans and the
native candidate's static contract (empty tables, write only after extraction).
None of them builds geometry.
"""

from __future__ import annotations

import asyncio
import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from creo_mechdog import capabilities
from creo_mechdog.capabilities import (
    UNAVAILABLE_FIELDS,
    UNAVAILABLE_OPERATIONS,
    require_available,
)
from creo_mechdog.job_projection import SURFACE_LOFT_KEYS
from creo_mechdog.operation_results import FAILED_EVIDENCE_KEYS
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_loft.cpp"
GATE_KEY = "surface_loft.boundary_conditions"


def edge(identifier: int) -> dict:
    return {"kind": "edge", "id": identifier}


def condition(boundary: str, value: str = "tangent") -> dict:
    return {"boundary": boundary, "condition": value}


def loft(**overrides) -> dict:
    operation = {
        "op": "surface_loft",
        "label": "loft_surface",
        "sections": [edge(12), edge(13)],
    }
    operation.update(overrides)
    return operation


def rejected(operations: list[dict]) -> str:
    try:
        validate_operations(operations)
    except ValueError as error:
        return str(error)
    raise AssertionError("the plan was accepted")


def gate_message(operation: dict) -> str:
    validated = validate_operations([operation])
    try:
        require_available(validated)
    except ValueError as error:
        return str(error)
    raise AssertionError("the gate let the request through")


class GateTests(unittest.TestCase):
    def test_any_non_empty_list_is_refused_with_its_reason(self):
        for conditions in (
            [condition("first_section")],
            [condition("last_section", "curvature")],
            [condition("first_section", "free")],
        ):
            with self.subTest(conditions=conditions):
                message = gate_message(loft(boundary_conditions=conditions))
                self.assertIn("no native job was queued", message)
                self.assertIn(GATE_KEY, message)
                self.assertIn("TAN_COND_FREE", message)
                self.assertIn("FEAT-065 T2b", message)

    def test_the_operation_itself_stays_published(self):
        self.assertNotIn("surface_loft", UNAVAILABLE_OPERATIONS)
        self.assertIn(GATE_KEY, UNAVAILABLE_FIELDS)

    def test_submit_refuses_before_the_toolkit_channel(self):
        import bridge
        import generic_bridge

        with (
            patch.object(bridge, "toolkit_lock") as lock,
            patch("pathlib.Path.mkdir") as mkdir,
        ):
            with self.assertRaisesRegex(ValueError, "no native job was queued"):
                generic_bridge.submit(
                    [loft(boundary_conditions=[condition("first_section")])],
                    model_id="0" * 32,
                    expected_revision=1,
                )
            lock.assert_not_called()
            mkdir.assert_not_called()

    def test_removing_the_one_entry_is_the_whole_switch(self):
        operation = validate_operations([loft(boundary_conditions=[condition("first_section")])])
        with patch.dict(UNAVAILABLE_FIELDS, clear=True):
            require_available(operation)
            self.assertEqual(capabilities.families()["surface_loft"]["unavailable_fields"], {})

    def test_capabilities_publish_the_gate(self):
        entry = capabilities.families()["surface_loft"]
        self.assertEqual(
            entry["unavailable_fields"], {"boundary_conditions": UNAVAILABLE_FIELDS[GATE_KEY]}
        )
        for phrase in ("FEAT-065 M4 boundary_conditions", "UNAVAILABLE_FIELDS", "FEAT-065 T2b"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, entry["limits"])
        # The compact limits note keeps its published prefix.
        self.assertTrue(entry["limits"].startswith("2-32 sections"))


class FieldShapeTests(unittest.TestCase):
    def test_accepted_shapes(self):
        guides = [edge(21), edge(22)]
        for operation in (
            loft(boundary_conditions=[condition("first_section")]),
            loft(boundary_conditions=[condition("last_section", "normal")]),
            loft(
                sections=["loft_a", edge(13)],
                boundary_conditions=[
                    condition("first_section", "free"),
                    condition("last_section", "curvature"),
                ],
            ),
            loft(
                guides=guides,
                boundary_conditions=[
                    condition("first_section"),
                    condition("last_section"),
                    condition("first_guide", "curvature"),
                    condition("last_guide", "normal"),
                ],
            ),
        ):
            with self.subTest(operation=operation):
                validated = validate_operations([operation])
                self.assertEqual(
                    validated[0]["boundary_conditions"], operation["boundary_conditions"]
                )

    def test_each_boundary_once(self):
        message = rejected(
            [
                loft(
                    boundary_conditions=[
                        condition("first_section"),
                        condition("first_section", "free"),
                    ]
                )
            ]
        )
        self.assertIn("boundary_conditions[1] repeats boundary 'first_section'", message)

    def test_condition_and_boundary_values(self):
        for item in (
            condition("first_section", "G1"),
            condition("first_section", "tangency"),
            condition("middle_section"),
            {"boundary": "first_section"},
            {"boundary": "first_section", "condition": "tangent", "weight": 1.0},
        ):
            with self.subTest(item=item):
                rejected([loft(boundary_conditions=[item])])

    def test_at_most_four_entries(self):
        items = [
            condition(name)
            for name in ("first_section", "last_section", "first_guide", "last_guide")
        ]
        rejected([loft(guides=[edge(21), edge(22)], boundary_conditions=[*items, items[0]])])

    def test_non_free_needs_an_edge_boundary(self):
        for sections, slot in (
            (["loft_a", edge(13)], "sections[0]"),
            ([{"kind": "curve", "id": 41}, edge(13)], "sections[0]"),
            ([{"kind": "point", "id": 9}, edge(13)], "sections[0]"),
        ):
            with self.subTest(sections=sections):
                message = rejected(
                    [loft(sections=sections, boundary_conditions=[condition("first_section")])]
                )
                self.assertIn(f"needs {slot} to be an edge", message)
                self.assertIn("{kind:'edge',id:N}", message)
        message = rejected(
            [
                loft(
                    sections=[edge(12), edge(13), "loft_c"],
                    interpolation="smooth",
                    boundary_conditions=[condition("last_section")],
                )
            ]
        )
        self.assertIn("needs sections[2] to be an edge", message)

    def test_free_is_allowed_on_any_boundary_source(self):
        validated = validate_operations(
            [
                loft(
                    sections=["loft_a", "loft_b"],
                    boundary_conditions=[condition("first_section", "free")],
                )
            ]
        )
        self.assertEqual(validated[0]["boundary_conditions"][0]["condition"], "free")

    def test_guide_boundaries_need_guides(self):
        for value in ("tangent", "free"):
            with self.subTest(condition=value):
                message = rejected([loft(boundary_conditions=[condition("first_guide", value)])])
                self.assertIn("has no guides", message)
        message = rejected(
            [
                loft(
                    guides=[edge(21), "guide_b"],
                    boundary_conditions=[condition("last_guide")],
                )
            ]
        )
        self.assertIn("needs guides[1] to be an edge", message)


class LegacyBehaviourTests(unittest.TestCase):
    def test_omitted_field_leaves_the_dumped_plan_unchanged(self):
        validated = validate_operations([loft(sections=["loft_a", "loft_b"])])
        self.assertNotIn("boundary_conditions", validated[0])
        self.assertEqual(set(validated[0]), {"op", "label", "sections", "interpolation", "guides"})
        require_available(validated)

    def test_empty_list_passes_the_gate(self):
        validated = validate_operations([loft(boundary_conditions=[])])
        self.assertEqual(validated[0]["boundary_conditions"], [])
        require_available(validated)

    def test_server_only_forwards_a_non_empty_list(self):
        import server

        captured = AsyncMock(return_value={"status": "accepted"})
        base = dict(model_id="m", expected_revision=1, label="loft_surface", sections=["a", "b"])
        with patch.object(server, "invoke", captured):
            for value in (None, []):
                asyncio.run(server.creo_surface_loft(**base, boundary_conditions=value))
                self.assertNotIn("boundary_conditions", captured.call_args.args[1][0])
            items = [condition("first_section")]
            asyncio.run(server.creo_surface_loft(**base, boundary_conditions=items))
            self.assertEqual(captured.call_args.args[1][0]["boundary_conditions"], items)

    def test_tool_schema_and_description_name_the_gate(self):
        import server

        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        tool = tools["creo_surface_loft"]
        self.assertIn("boundary_conditions", tool.input_schema["properties"])
        self.assertIn("NOT AVAILABLE", tool.description)
        self.assertIn("FEAT-065 T2b", tool.description)


class ProjectionTests(unittest.TestCase):
    def test_receipt_fields_are_projected_and_failure_is_protected(self):
        for key in ("boundary_conditions", "failed_boundary_condition", "tan_cond_tree"):
            with self.subTest(key=key):
                self.assertIn(key, SURFACE_LOFT_KEYS)
        self.assertIn("failed_boundary_condition", FAILED_EVIDENCE_KEYS)


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def _function(code: str, signature: str) -> str:
    start = code.index(signature)
    end = code.index("\n}\n", start)
    return code[start:end]


class NativeCandidateContractTests(unittest.TestCase):
    def setUp(self):
        text = NATIVE.read_text(encoding="utf-8")
        start = text.index("#if MECHDOG_HAS_PROBBL_HEADER")
        end = text.index("#else", start)
        self.code = _code(text[start:end]) + "\n"
        self.whole = _code(text)

    def test_mapping_tables_are_empty_until_t2b(self):
        for declaration in (
            "static const std::map<std::string, int> SURFACE_LOFT_TAN_COND_TYPE_VALUES = {};",
            "static const std::map<std::string, int> SURFACE_LOFT_TNC_BOUNDARY_INDEX = {};",
            "static const int SURFACE_LOFT_CONNECT_CHAIN_METHOD = -1;",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, self.code)
                self.assertEqual(self.whole.count(declaration), 1)
        # No guessed symbol: TAN_COND_FREE has no definition, so it only ever
        # appears inside message text.
        self.assertNotIn("TAN_COND_FREE", re.sub(r'"(?:[^"\\]|\\.)*"', '""', self.whole))

    def test_unmapped_conditions_are_refused_before_any_write(self):
        body = _function(self.code, "static void surface_loft_apply_conditions(")
        refusal = body.index('"SURFACE_LOFT_BOUNDARY_CONDITION_UNMAPPED"')
        lookup = body.index("SURFACE_LOFT_TAN_COND_TYPE_VALUES.count(item.condition)")
        first_write = body.index("CK(ProElementIntegerSet(type, value));")
        self.assertLess(refusal, first_write)
        self.assertLess(lookup, first_write)
        self.assertIn("SURFACE_LOFT_TNC_BOUNDARY_INDEX.count(item.boundary)", body)
        self.assertIn(
            "const int value = SURFACE_LOFT_TAN_COND_TYPE_VALUES.at(item.condition);", body
        )
        # Free requests keep the kernel default: nothing is touched.
        self.assertLess(body.index("if (!any)\n        return;"), first_write)

    def test_known_mapping_rewrites_type_and_connect_chain(self):
        body = _function(self.code, "static void surface_loft_apply_conditions(")
        for fragment in (
            "get_optional(entry, {PRO_E_BNBLN_TAN_COND_TYPE}, &type_code)",
            "ProElemtreeElementRemove(entry, path, &removed)",
            'check(remove_code, "ProElemtreeElementRemove(PRO_E_BNBLN_CONNECT_SURF_CHAIN)")',
            "CK(ProElementFree(&removed))",
            "node(entry, PRO_E_BNBLN_CONNECT_SURF_CHAIN)",
            "node(chain, PRO_E_SURF_CHAIN_CMPND)",
            "node(compound, PRO_E_SURF_CHAIN_REF_SURFS)",
            "node(surfaces, PRO_E_SURF_CHAIN_SURF)",
            "selection(item.surface_id, PRO_SURFACE)",
            "ref(surface, PRO_E_SURF_CHAIN_REF, face)",
            "ProSelectionFree(&face)",
            '"tan_cond_entry_missing"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, body)

    def test_neighbour_face_is_the_single_adjacent_face_of_an_edge(self):
        body = _function(
            self.code, "static std::vector<SurfaceLoftCondition> surface_loft_conditions("
        )
        for fragment in (
            'input.source != "edge"',
            '"boundary_not_an_edge"',
            'input.record.value("adjacent_surface_ids", J(nullptr))',
            "faces.size() != 1",
            '"adjacent_face_count"',
            '"SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED"',
            '"repeated_boundary"',
            '"no_guides"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, body)

    def test_writes_happen_only_between_extract_and_redefine(self):
        body = _function(self.code, "static void generic_surface_loft(const J &op)")
        resolve = body.index("surface_loft_conditions(op, section_inputs, guide_inputs, details)")
        creation = body.index("node(nullptr, PRO_E_FEATURE_TREE)")
        create = body.index("ProFeatureWithoptionsCreate(")
        extract = body.index("ProFeatureElemtreeExtract(")
        apply = body.index("surface_loft_apply_conditions(extracted, conditions, details)")
        redefine = body.index("redefine(&feature, extracted)")
        self.assertLess(resolve, creation)
        self.assertLess(create, extract)
        self.assertLess(extract, apply)
        self.assertLess(apply, redefine)
        self.assertNotIn("PRO_E_BNBLN_TAN_COND", body[creation:create])
        # A refusal frees the extracted tree and rethrows into the job rollback.
        handler = body[apply : body.index("throw;", apply)]
        self.assertIn('details["tan_cond_tree"] = tan_cond_tree;', handler)
        self.assertIn("CK(ProFeatureElemtreeFree(&feature, extracted));", handler)

    def test_tan_cond_sample_has_its_own_budget(self):
        self.assertIn("static constexpr int SURFACE_LOFT_TAN_COND_SAMPLE_LIMIT = 64;", self.code)
        body = _function(self.code, "static J surface_loft_tan_cond_json(ProElement tree)")
        self.assertIn("get_optional(tree, {PRO_E_BNBLN_TAN_COND}, &code)", body)
        self.assertIn("loft_tree_json(array, SURFACE_LOFT_TAN_COND_SAMPLE_LIMIT)", body)
        loft = _function(self.code, "static void generic_surface_loft(const J &op)")
        self.assertEqual(len(re.findall(r'details\["tan_cond_tree"\] = tan_cond_tree;', loft)), 4)
        # The shared sample now reports truncation instead of a constant false.
        self.assertNotIn('{"truncated", false}', _function(self.code, "static J loft_tree_json("))


if __name__ == "__main__":
    unittest.main()
