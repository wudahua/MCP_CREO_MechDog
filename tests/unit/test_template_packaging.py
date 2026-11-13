"""BUG-123: element tree templates ship with the source package, digest-checked.

``templates/elemtree/manifest.json`` is the allowlist and the provenance record:
the packager ships exactly the templates it names, and only when the bytes on
disk still produce the declared SHA256. Otherwise a client could apply an
element tree nobody measured - the exact failure BUG-123 spent a live run
ruling out.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from creo_mechdog import release_integrity
from tools import package

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "templates" / "elemtree"
MANIFEST = LIBRARY / "manifest.json"


class TemplateLibraryFiles(unittest.TestCase):
    def test_the_repository_manifest_matches_the_template_bytes(self):
        files = release_integrity.template_library_files(ROOT)
        self.assertEqual(files[0], MANIFEST)
        self.assertIn(LIBRARY / "loft_s3g3_creo12.4.xml", files)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in manifest["templates"]:
            path = LIBRARY / entry["file"]
            data = path.read_bytes()
            self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_the_measured_shape_is_recorded_with_the_template(self):
        # The manifest is what a client reads to know which request shape the
        # template accepts; a template without sections/guides is unusable.
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        (entry,) = manifest["templates"]
        self.assertEqual((entry["sections"], entry["guides"]), (3, 3))
        self.assertEqual(entry["template_id"], "loft_s3g3")
        self.assertTrue(entry["source"]["job_ids"])


class TemplateLibraryRefusals(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = self.temp / "source"
        shutil.copytree(ROOT / "templates", self.root / "templates")
        self.manifest = self.root / "templates" / "elemtree" / "manifest.json"
        self.template = self.root / "templates" / "elemtree" / "loft_s3g3_creo12.4.xml"

    def test_a_changed_template_is_refused(self):
        self.template.write_bytes(self.template.read_bytes() + b"\n")
        with self.assertRaises(ValueError) as caught:
            release_integrity.template_library_files(self.root)
        self.assertIn("re-export the template", str(caught.exception))

    def test_a_missing_template_is_refused(self):
        self.template.unlink()
        with self.assertRaises(ValueError) as caught:
            release_integrity.template_library_files(self.root)
        self.assertIn("missing or is a symlink", str(caught.exception))

    def test_a_missing_manifest_is_refused(self):
        self.manifest.unlink()
        with self.assertRaises(ValueError) as caught:
            release_integrity.template_library_files(self.root)
        self.assertIn("manifest is missing", str(caught.exception))

    def test_a_template_the_manifest_does_not_name_is_not_shipped(self):
        (self.root / "templates" / "elemtree" / "unmeasured.xml").write_text(
            "<root/>", encoding="utf-8"
        )
        files = release_integrity.template_library_files(self.root)
        self.assertNotIn(
            self.root / "templates" / "elemtree" / "unmeasured.xml",
            files,
        )

    def test_an_unnamed_entry_is_refused(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["templates"][0]["file"] = ""
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            release_integrity.template_library_files(self.root)
        self.assertIn("invalid template file name", str(caught.exception))

    def test_an_entry_without_a_digest_is_refused(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        del manifest["templates"][0]["sha256"]
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            release_integrity.template_library_files(self.root)
        self.assertIn("no valid sha256", str(caught.exception))


class SourcePackageContents(unittest.TestCase):
    def test_the_source_package_ships_the_template_and_its_manifest(self):
        names = {
            path.relative_to(ROOT).as_posix()
            for path in package.source_files()
            if path.is_relative_to(ROOT)
        }
        self.assertIn("templates/elemtree/loft_s3g3_creo12.4.xml", names)
        self.assertIn("templates/elemtree/manifest.json", names)

    def test_the_packager_uses_the_shared_allowlist(self):
        source = (ROOT / "tools" / "package.py").read_text(encoding="utf-8")
        self.assertIn("template_library_files(ROOT)", source)


if __name__ == "__main__":
    unittest.main()
