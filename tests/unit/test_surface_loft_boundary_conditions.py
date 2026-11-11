"""FEAT-065/M4 surface_loft boundary conditions (measured contract).

``boundary_conditions`` names the continuity between one loft boundary and the
face next to it. Probbl.h documents only ``TAN_COND_FREE`` for
``PRO_E_BNBLN_TAN_COND_TYPE``, so the values were measured on Creo 12.4.0.0
(FEAT-065 T2b, 2026-11-11): ``tangent`` at an edge first/last section is
TAN_COND_TYPE 2 plus PRO_E_BNBLN_STRETCH -1/+1 and gave G1 0.0 deg at both
seams of a two-strip bridge. Curvature, normal and guide boundaries were not
proved, so the schema refuses them before a job and the native executor repeats
the refusal before any feature exists. The field gate
(``capabilities.UNAVAILABLE_FIELDS``) is now empty, with its mechanism kept.
These tests lock the admission rules, the empty gate, the unchanged legacy
plans and the native static contract. None of them builds geometry.
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
from creo_mechdog.surface_ops import LOFT_CONDITION_REFUSALS, LOFT_TANGENT_BOUNDARIES

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


class AvailabilityTests(unittest.TestCase):
    """Which conditions pass admission, measured on Creo 12.4.0.0."""

    def test_tangent_at_edge_end_sections_passes_schema_and_gate(self):
        for conditions in (
            [condition("first_section")],
            [condition("last_section")],
            [condition("first_section"), condition("last_section")],
        ):
            with self.subTest(conditions=conditions):
                validated = validate_operations([loft(boundary_conditions=conditions)])
                self.assertEqual(validated[0]["boundary_conditions"], conditions)
                require_available(validated)

    def test_tangent_boundaries_are_the_measured_two(self):
        self.assertEqual(LOFT_TANGENT_BOUNDARIES, ("first_section", "last_section"))

    def test_curvature_and_normal_are_refused_with_the_measured_reason(self):
        for value, evidence in (
            ("curvature", "kept a 90 deg seam"),
            ("normal", "same 800 mm2 plane as 'free'"),
        ):
            for boundary in ("first_section", "last_section"):
                with self.subTest(condition=value, boundary=boundary):
                    message = rejected([loft(boundary_conditions=[condition(boundary, value)])])
                    self.assertIn(f"condition '{value}' is not available", message)
                    self.assertIn(evidence, message)
                    self.assertIn("Creo 12.4.0.0", message)
                    self.assertIn("use 'tangent'", message)
        self.assertEqual(set(LOFT_CONDITION_REFUSALS), {"curvature", "normal"})

    def test_curvature_and_normal_are_refused_on_any_source_and_boundary(self):
        # The refusal comes before the slot checks: no source makes them valid.
        guides = [edge(21), edge(22)]
        for value in ("curvature", "normal"):
            for operation in (
                loft(
                    sections=["loft_a", "loft_b"],
                    boundary_conditions=[condition("first_section", value)],
                ),
                loft(guides=guides, boundary_conditions=[condition("first_guide", value)]),
            ):
                with self.subTest(condition=value, operation=operation):
                    self.assertIn("is not available", rejected([operation]))

    def test_non_free_guide_boundaries_are_refused_as_unmeasured(self):
        for guides in ([edge(21), edge(22)], ["guide_a", "guide_b"]):
            for boundary in ("first_guide", "last_guide"):
                with self.subTest(guides=guides, boundary=boundary):
                    message = rejected(
                        [loft(guides=guides, boundary_conditions=[condition(boundary)])]
                    )
                    self.assertIn(f"'tangent' on '{boundary}' is not available", message)
                    self.assertIn("guide boundaries were not measured", message)

    def test_free_is_accepted_on_every_boundary(self):
        validated = validate_operations(
            [
                loft(
                    sections=["loft_a", "loft_b"],
                    guides=["guide_a", "guide_b"],
                    boundary_conditions=[
                        condition(name, "free")
                        for name in ("first_section", "last_section", "first_guide", "last_guide")
                    ],
                )
            ]
        )
        require_available(validated)
        self.assertEqual(
            [item["condition"] for item in validated[0]["boundary_conditions"]], ["free"] * 4
        )

    def test_submit_refuses_an_unmeasured_condition_before_the_toolkit_channel(self):
        import bridge
        import generic_bridge

        with (
            patch.object(bridge, "toolkit_lock") as lock,
            patch("pathlib.Path.mkdir") as mkdir,
        ):
            with self.assertRaisesRegex(ValueError, "condition 'curvature' is not available"):
                generic_bridge.submit(
                    [loft(boundary_conditions=[condition("first_section", "curvature")])],
                    model_id="0" * 32,
                    expected_revision=1,
                )
            lock.assert_not_called()
            mkdir.assert_not_called()


class FieldGateTests(unittest.TestCase):
    """The UNAVAILABLE_FIELDS mechanism stays; it is empty since T2b."""

    def test_the_gate_is_empty_and_the_operation_published(self):
        self.assertEqual(UNAVAILABLE_FIELDS, {})
        self.assertNotIn(GATE_KEY, UNAVAILABLE_FIELDS)
        self.assertNotIn("surface_loft", UNAVAILABLE_OPERATIONS)
        self.assertEqual(capabilities.families()["surface_loft"]["unavailable_fields"], {})

    def test_an_entry_would_still_refuse_before_a_job(self):
        operation = validate_operations([loft(boundary_conditions=[condition("first_section")])])
        with patch.dict(UNAVAILABLE_FIELDS, {GATE_KEY: "test reason"}):
            with self.assertRaisesRegex(ValueError, "no native job was queued") as raised:
                require_available(operation)
            self.assertIn(f"{GATE_KEY}: test reason", str(raised.exception))
            self.assertEqual(
                capabilities.families()["surface_loft"]["unavailable_fields"],
                {"boundary_conditions": "test reason"},
            )
        require_available(operation)

    def test_capabilities_publish_the_measured_contract(self):
        entry = capabilities.families()["surface_loft"]
        limits = " ".join(entry["limits"].split())
        for phrase in (
            "FEAT-065 M4 boundary_conditions",
            "'tangent' is published at first_section/last_section only",
            "single adjacent face",
            "continuing the neighbouring face",
            "982.5888 mm2",
            "G1 0.0 deg at both seams",
            "800 mm2 plane at 90 deg",
            "915.99 mm2",
            "guide boundaries were not measured",
            "SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED",
            "not_available",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, limits)
        self.assertNotIn("UNAVAILABLE_FIELDS", limits)
        self.assertNotIn("continuity/tangency", limits)
        self.assertIn("FEAT-065 M4", entry["scope"])
        # The compact limits note keeps its published prefix.
        self.assertTrue(entry["limits"].startswith("2-32 sections"))
        chain = capabilities.families()["surface_chain"]
        self.assertIn("boundary continuity is 'tangent' only", chain["limits"])
        self.assertNotIn("no closed, continuity or solid output", chain["limits"])


class FieldShapeTests(unittest.TestCase):
    def test_accepted_shapes(self):
        guides = [edge(21), edge(22)]
        for operation in (
            loft(boundary_conditions=[condition("first_section")]),
            loft(boundary_conditions=[condition("last_section")]),
            loft(
                sections=["loft_a", edge(13)],
                boundary_conditions=[
                    condition("first_section", "free"),
                    condition("last_section"),
                ],
            ),
            loft(
                guides=guides,
                boundary_conditions=[
                    condition("first_section"),
                    condition("last_section"),
                    condition("first_guide", "free"),
                    condition("last_guide", "free"),
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
            {"boundary": "first_section", "condition": "tangent", "stretch": -1.0},
        ):
            with self.subTest(item=item):
                rejected([loft(boundary_conditions=[item])])

    def test_at_most_four_entries(self):
        items = [
            condition(name, "free")
            for name in ("first_section", "last_section", "first_guide", "last_guide")
        ]
        rejected([loft(guides=[edge(21), edge(22)], boundary_conditions=[*items, items[0]])])

    def test_tangent_needs_an_edge_boundary(self):
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
        message = rejected([loft(boundary_conditions=[condition("first_guide", "free")])])
        self.assertIn("has no guides", message)
        # A non-free guide condition is refused as unmeasured whether or not
        # the loft has guides, so the caller is not told to add guides first.
        message = rejected([loft(boundary_conditions=[condition("first_guide")])])
        self.assertIn("guide boundaries were not measured", message)


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

    def test_tool_schema_and_description_publish_tangent(self):
        import server

        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        tool = tools["creo_surface_loft"]
        self.assertIn("boundary_conditions", tool.input_schema["properties"])
        text = " ".join(tool.description.split())
        for phrase in (
            "Only condition='tangent' is published",
            "boundary='first_section' or 'last_section'",
            "edge {kind:'edge',id:N} with a single adjacent face",
            "continuing the neighbouring face",
            "boundary_conditions=[{boundary:'first_section', condition:'tangent'}",
            "982.5888 mm2",
            "G1 0.0 deg",
            "'curvature'",
            "'normal'",
            "first_guide/last_guide",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("NOT AVAILABLE", text)
        self.assertNotIn("FEAT-065 T2b", text)


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


def _flat(code: str) -> str:
    return " ".join(code.split())


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        text = NATIVE.read_text(encoding="utf-8")
        start = text.index("#if MECHDOG_HAS_PROBBL_HEADER")
        end = text.index("#else", start)
        self.code = _code(text[start:end]) + "\n"
        self.whole = _code(text)

    def test_mapping_tables_hold_the_measured_values(self):
        flat = _flat(self.code)
        for declaration in (
            'static const std::map<std::string, int> SURFACE_LOFT_TAN_COND_TYPE_VALUES = {{"tangent", 2}};',
            "static const std::map<std::string, int> SURFACE_LOFT_TNC_BOUNDARY_INDEX = "
            '{{"first_section", 0}, {"last_section", 1}};',
            "static const std::map<std::string, double> SURFACE_LOFT_TANGENT_STRETCH = "
            '{{"first_section", -1.0}, {"last_section", 1.0}};',
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, flat)
                self.assertEqual(_flat(self.whole).count(declaration), 1)
        # Only measured entries: no curvature/normal value, no guide boundary.
        tables = flat[flat.index("SURFACE_LOFT_TAN_COND_TYPE_VALUES") :]
        tables = tables[: tables.index("SURFACE_LOFT_TAN_COND_SAMPLE_LIMIT")]
        for unmeasured in ('"curvature"', '"normal"', '"first_guide"', '"last_guide"'):
            with self.subTest(unmeasured=unmeasured):
                self.assertNotIn(unmeasured, tables)
        # No guessed symbol: TAN_COND_FREE has no definition, so it only ever
        # appears inside message text.
        self.assertNotIn("TAN_COND_FREE", re.sub(r'"(?:[^"\\]|\\.)*"', '""', self.whole))

    def test_unmeasured_conditions_are_refused_before_the_tree_is_built(self):
        body = _function(
            self.code, "static std::vector<SurfaceLoftCondition> surface_loft_conditions("
        )
        refusal = body.index('refuse("not_available"')
        self.assertIn('item.condition != "free"', body[:refusal])
        self.assertIn("SURFACE_LOFT_TAN_COND_TYPE_VALUES.count(item.condition)", body[:refusal])
        self.assertIn("SURFACE_LOFT_TNC_BOUNDARY_INDEX.count(item.boundary)", body[:refusal])
        # The refusal precedes the edge resolution of the same entry.
        self.assertLess(refusal, body.index('"boundary_not_an_edge"'))
        loft = _function(self.code, "static void generic_surface_loft(const J &op)")
        self.assertLess(
            loft.index("surface_loft_conditions(op, section_inputs, guide_inputs, details)"),
            loft.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        )

    def test_unmapped_conditions_are_refused_before_any_write(self):
        body = _function(self.code, "static void surface_loft_apply_conditions(")
        refusal = body.index('"SURFACE_LOFT_BOUNDARY_CONDITION_UNMAPPED"')
        lookup = body.index("SURFACE_LOFT_TAN_COND_TYPE_VALUES.count(item.condition)")
        first_write = body.index("CK(ProElementIntegerSet(type, value));")
        self.assertLess(refusal, first_write)
        self.assertLess(lookup, first_write)
        self.assertIn("SURFACE_LOFT_TNC_BOUNDARY_INDEX.count(item.boundary)", body)
        self.assertIn("SURFACE_LOFT_TANGENT_STRETCH.count(item.boundary)", body)
        self.assertIn(
            "const int value = SURFACE_LOFT_TAN_COND_TYPE_VALUES.at(item.condition);", body
        )
        # Free requests keep the kernel default: nothing is touched.
        self.assertLess(body.index("if (!any)\n        return;"), first_write)

    def test_measured_mapping_writes_type_and_stretch_and_keeps_the_kernel_chain(self):
        body = _function(self.code, "static void surface_loft_apply_conditions(")
        for fragment in (
            "get_optional(entry, {PRO_E_BNBLN_TAN_COND_TYPE}, &type_code)",
            "const double stretch = SURFACE_LOFT_TANGENT_STRETCH.at(item.boundary);",
            "get_optional(entry, {PRO_E_BNBLN_STRETCH}, &stretch_code)",
            "node(entry, PRO_E_BNBLN_STRETCH)",
            "CK(ProElementDoubleSet(stretch_element, stretch));",
            'record["status"] = "written";',
            'record["tnc_index"] = position;',
            'record["tan_cond_type"] = value;',
            'record["stretch"] = stretch;',
            'record["connect_chain"] = "kernel_default";',
            '"tan_cond_entry_missing"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, body)
        self.assertLess(
            body.index("CK(ProElementIntegerSet(type, value));"),
            body.index("CK(ProElementDoubleSet(stretch_element, stretch));"),
        )
        # The kernel-filled connect chain (SURF_CHAIN_METHOD 1, the face next to
        # the edge) is kept: nothing removes or rebuilds it any more.
        for absent in (
            "PRO_E_BNBLN_CONNECT_SURF_CHAIN",
            "ProElemtreeElementRemove",
            "PRO_E_SURF_CHAIN",
            "selection(item.surface_id, PRO_SURFACE)",
            "surf_chain_method",
        ):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, body)
        for absent in ("SURFACE_LOFT_CONNECT_CHAIN_METHOD", '"surf_chain_method"'):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, self.whole)

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
            '"not_available"',
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
        # The creation tree never carries TAN_COND or STRETCH (the 2026-11-01
        # probe stayed UNREGENERATED when they were written before creation).
        self.assertNotIn("PRO_E_BNBLN_TAN_COND", body[creation:create])
        self.assertNotIn("PRO_E_BNBLN_STRETCH", body[creation:create])
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
