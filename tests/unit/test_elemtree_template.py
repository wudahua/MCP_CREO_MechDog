"""BUG-123/B1: the exported boundary-blend element-tree template stays loadable.

The template is real Creo 12.4 output (`creo_dump_feature_tree`), not hand-written
XML, so these checks pin the structure the loader will rewrite: three chain
holders per direction, one model-qualified curve reference in each holder, and no
model-specific surface reference hiding in the tangent-condition block.
"""

from __future__ import annotations

import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.export_elemtree_template import case_offline, shape_plan

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates" / "elemtree"
TEMPLATE = TEMPLATES / "loft_s3g3_creo12.4.xml"
MANIFEST = TEMPLATES / "manifest.json"


def holders(root: ET.Element, direction: str) -> list:
    curves = root.find("PRO_E_BNBLN_CURVES")
    if curves is None:
        return []
    block = curves.find(f"PRO_E_BNBLN_{direction}")
    if block is None:
        return []
    array = block.find("PRO_E_BNBLN_DIR_CURVES")
    return list(array) if array is not None else []


@unittest.skipUnless(TEMPLATE.is_file(), "template has not been exported in this checkout")
class TemplateStructure(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(TEMPLATE).getroot()

    def test_it_is_a_boundary_blend_tree(self):
        form = self.root.find("PRO_E_FEATURE_FORM")
        kind = self.root.find("PRO_E_DTM_SRF_TYPE")
        self.assertEqual(form.text, "PRO_USE_SURFS")
        self.assertEqual(kind.text, "11")

    def test_three_sections_and_three_guides(self):
        self.assertEqual(len(holders(self.root, "1DIR")), 3)
        self.assertEqual(len(holders(self.root, "2DIR")), 3)

    def test_every_holder_carries_one_model_qualified_curve_reference(self):
        references = list(self.root.iter("PRO_XML_REFERENCE"))
        self.assertEqual(len(references), 6)
        for reference in references:
            owner = reference.findtext("PRO_XML_REFERENCE_OWNER") or ""
            self.assertTrue(owner.endswith(".prt"), owner)
            self.assertTrue((reference.findtext("PRO_XML_REFERENCE_ID") or "").isdigit())
            self.assertIn(reference.findtext("PRO_XML_REFERENCE_TYPE"), ("PRO_CURVE", "PRO_EDGE"))

    def test_the_tangent_block_holds_no_model_specific_reference(self):
        # If a future template ever pins a surface here, replacing only the curve
        # references would load a tree that points at another model.
        boundary = self.root.find("PRO_E_BNBLN_TAN_COND")
        self.assertIsNotNone(boundary)
        for selection in boundary.iter("PRO_E_SURF_CHAIN_REF"):
            self.assertIsNone(selection.find("PRO_XML_REFERENCE"))

    def test_the_manifest_records_this_exact_file(self):
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = [item for item in document["templates"] if item["file"] == TEMPLATE.name]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["sha256"], hashlib.sha256(TEMPLATE.read_bytes()).hexdigest())
        self.assertEqual(entry["sections"], 3)
        self.assertEqual(entry["guides"], 3)
        self.assertEqual(entry["measured"]["extract_code"], 0)
        self.assertFalse(entry["measured"]["feature_incomplete"])
        self.assertEqual(entry["source"]["tool"], "creo_dump_feature_tree")
        self.assertEqual(entry["source"]["feature_id"], 80)


class DriverOfflineContract(unittest.TestCase):
    def test_s3g3_plan_is_three_sections_plus_three_guides(self):
        loft = shape_plan("s3g3")[-1]
        self.assertEqual(len(loft["sections"]), 3)
        self.assertEqual(loft["guides"], ["guide_left", "guide_mid", "guide_right"])

    def test_schema_accepts_every_template_shape(self):
        for shape in ("s3g3", "s3g2", "plain3"):
            with self.subTest(shape=shape):
                report = case_offline(shape)
                self.assertEqual(report["sections"], 3)
                self.assertEqual(
                    report["guides"], 0 if shape == "plain3" else (3 if shape == "s3g3" else 2)
                )

    def test_offline_mode_never_submits(self):
        report = case_offline("s3g3")
        self.assertEqual(report["mode"], "offline")
        self.assertIn("nothing was submitted", report["note"])


if __name__ == "__main__":
    unittest.main()
