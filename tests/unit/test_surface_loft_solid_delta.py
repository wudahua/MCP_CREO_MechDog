"""BUG-119: surface_loft must judge solid creation by local delta.

The 0.22.0 feedback showed that ``inspection(false)["has_solid"]`` describes the
whole model: on a part that already had a solid, every surface loft was rolled
back as if it had created material. The fix captures the material state before
the feature and compares it after.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")


class SurfaceLofSolidDeltaTests(unittest.TestCase):
    def test_state_is_captured_before_the_feature_tree(self):
        before = SOURCE.index("const SurfaceLoftMaterialState material_before")
        create = SOURCE.index("ProFeatureWithoptionsCreate")
        self.assertLess(before, create)

    def test_state_is_captured_after_the_feature(self):
        after = SOURCE.index("const SurfaceLoftMaterialState material_after")
        create = SOURCE.index("ProFeatureWithoptionsCreate")
        self.assertGreater(after, create)

    def test_gate_uses_local_delta_not_the_global_flag(self):
        self.assertIn("created_solid_material", SOURCE)
        self.assertIn("material_after.material_bodies > material_before.material_bodies", SOURCE)
        self.assertIn("*material_after.volume_mm3 - *material_before.volume_mm3 > 1e-6", SOURCE)
        self.assertNotIn('if (details["has_solid"].get<bool>())', SOURCE)

    def test_receipt_publishes_before_and_after_evidence(self):
        for field in (
            '"has_solid_before"',
            '"has_solid_after"',
            '"created_solid_material"',
            '"material_bodies_before"',
            '"material_bodies_after"',
            '"volume_mm3_before"',
            '"volume_mm3_after"',
        ):
            self.assertIn(field, SOURCE)

    def test_error_message_names_the_delta(self):
        self.assertIn("has_solid ", SOURCE)
        self.assertIn("material bodies ", SOURCE)


if __name__ == "__main__":
    unittest.main()
