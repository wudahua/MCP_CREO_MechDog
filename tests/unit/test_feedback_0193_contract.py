"""Offline contract regressions for the 2026-11-10 0.19.3 feedback batch.

Each case pins one caller-facing text or shape that the reports showed to be
misleading on a real model: the draft neutral-plane example, the
``feature_state`` target shape error, the ambiguous-session message, and the
dependency-list hint. Behaviour that needs Creo is not asserted here.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import creo_startup
from creo_mechdog.references import reference_capabilities
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]


class DraftNeutralPlaneExampleTests(unittest.TestCase):
    def test_capability_example_uses_the_geometric_plane_form(self):
        tools = reference_capabilities()["by_tool"]
        neutral = tools["creo_draft"]["neutral_plane"]
        self.assertEqual(neutral["kind"], "plane")
        self.assertEqual(neutral["normal"], [0, 0, 1])
        self.assertIn("offset", neutral)

    def test_syntax_explains_the_datum_plane_single_face_requirement(self):
        syntax = reference_capabilities()["syntax"]
        note = syntax["plane_by_position"]
        self.assertIn("datum_plane", note)
        self.assertIn("several parallel", note)
        self.assertIn("id", note)

    def test_example_still_validates_as_a_draft_operation(self):
        draft = reference_capabilities()["by_tool"]["creo_draft"]
        values = validate_operations([{**draft, "op": "draft", "label": "d", "angle": 15}])
        self.assertEqual(values[0]["neutral_plane"]["kind"], "plane")


class FeatureStateTargetShapeTests(unittest.TestCase):
    def test_selection_object_is_refused_with_a_caller_facing_example(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations(
                [
                    {
                        "op": "feature_state",
                        "action": "delete",
                        "targets": [{"kind": "feature", "label": "door"}],
                    }
                ]
            )
        message = str(caught.exception)
        self.assertIn("targets must be a list of feature label strings", message)
        self.assertIn('["door_upper_neg", 6823]', message)
        self.assertNotIn("function-wrap", message)
        self.assertNotIn("_explain_label_pattern", message)

    def test_plain_label_and_id_arrays_still_validate(self):
        values = validate_operations(
            [{"op": "feature_state", "action": "delete", "targets": ["door", "6823"]}]
        )
        self.assertEqual(values[0]["targets"], ["door", 6823])

    def test_dependency_messages_offer_the_retry_shape(self):
        for path, marker in (
            (ROOT / "src/creo_mechdog/feature_state.py", "Append these feature IDs to targets"),
            (ROOT / "native/feature_state.cpp", "Append the feature_id values above to targets"),
        ):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("do not cover every affected dependency", text)
                self.assertIn(marker, text)


class QuiltMergeReferenceGuidanceTests(unittest.TestCase):
    def test_capability_limits_name_the_original_target_workaround(self):
        text = (ROOT / "src/creo_mechdog/capabilities.py").read_text(encoding="utf-8")
        flat = " ".join(text.split())
        self.assertIn("a merge result has no separately referenceable quilt label", flat)
        self.assertIn("keep referencing the original target quilt", flat)
        self.assertIn("ProFeatureGeomitemVisit -4", flat)

    def test_reference_syntax_documents_the_workaround(self):
        text = (ROOT / "docs/REFERENCE_SYNTAX.md").read_text(encoding="utf-8")
        flat = " ".join(text.split())
        self.assertIn("没有可独立引用的 quilt 标签", flat)
        self.assertIn("继续引用**原始 target**", flat)
        self.assertIn("BUG-115", flat)


class AmbiguousSessionMessageTests(unittest.TestCase):
    def test_message_names_both_recovery_paths_and_the_restart(self):
        text = (ROOT / "creo_startup.py").read_text(encoding="utf-8")
        start = text.index('native.get("connection_state") == "ambiguous"')
        block = " ".join(text[start : start + 1400].split())
        self.assertIn("toolkit_code=-36", block)
        self.assertIn("Close every Creo instance", block)
        self.assertIn("restart the MCP service", block)
        self.assertIn("editing config.json alone does not change the running service", block)
        self.assertIn("cannot choose a", block)
        self.assertIn("session programmatically", block)

    def test_startup_settings_are_read_from_disk_on_each_load(self):
        # The report's dead end was "edit config.json and retry" against a
        # service that had already loaded the value. Settings.load() must stay
        # a read of bridge.config(), not a cached snapshot.
        source = (ROOT / "creo_startup.py").read_text(encoding="utf-8")
        self.assertIn("value = bridge.config()", source)
        self.assertTrue(hasattr(creo_startup.Settings, "load"))


if __name__ == "__main__":
    unittest.main()
