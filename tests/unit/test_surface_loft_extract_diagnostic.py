"""BUG-120: distinguish create failure from an unreadable kernel tree.

The 0.23.0/0.23.1 feedback showed Creo 10 returns create_code=0 and then
ProFeatureElemtreeExtract=-18 with ProFeatureIsIncomplete=true. The receipt must
carry that evidence and name the unsupported-extract condition instead of the
generic "cannot extract" text.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")


class SurfaceLoftExtractDiagnosticTests(unittest.TestCase):
    def test_incompleteness_is_read_after_create_and_before_extract(self):
        create = SOURCE.index("ProFeatureWithoptionsCreate")
        incomplete = SOURCE.index("ProFeatureIsIncomplete", create)
        extract = SOURCE.index("ProFeatureElemtreeExtract(&feature", create)
        self.assertLess(create, incomplete)
        self.assertLess(incomplete, extract)

    def test_incomplete_state_is_never_used_to_reject_before_extract(self):
        before_extract = SOURCE[: SOURCE.index("ProFeatureElemtreeExtract")]
        self.assertNotIn('if (details["feature_incomplete"].get<bool>())', before_extract)

    def test_failure_names_the_unsupported_extract_condition(self):
        self.assertIn("SURFACE_LOFT_EXTRACT_UNSUPPORTED", SOURCE)
        self.assertIn('details["extract_unsupported"] = true;', SOURCE)
        self.assertIn('details["kernel_completion"] = "unsupported";', SOURCE)
        self.assertIn('"release_numeric"', SOURCE)
        self.assertIn('"create_code"', SOURCE)
        self.assertIn('"extract_code"', SOURCE)
        self.assertIn('"feature_incomplete"', SOURCE)

    def test_success_publishes_supported_completion(self):
        self.assertIn('details["extract_unsupported"] = false;', SOURCE)
        self.assertIn('details["kernel_completion"] = "supported";', SOURCE)

    def test_message_keeps_both_codes_and_the_rollback(self):
        self.assertIn(
            '"surface_loft created the feature (create_code=" + std::to_string((int)created)',
            SOURCE,
        )
        self.assertIn("the job was rolled back", SOURCE)


if __name__ == "__main__":
    unittest.main()
