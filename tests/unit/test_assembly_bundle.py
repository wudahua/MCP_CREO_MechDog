"""Offline native bundle ownership, closure, manifest and cleanup fixtures."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creo_mechdog.assembly_bundle import create_bundle
from creo_mechdog.schema import validate_operations


class AssemblyBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owned = self.root / "model" / "output"
        self.owned.mkdir(parents=True)
        self.job = self.root / "job" / "output"
        self.job.mkdir(parents=True)
        self.asm = self.owned / "pump.asm.2"
        self.asm.write_bytes(b"assembly version 2")
        (self.owned / "pump.asm.1").write_bytes(b"old version")
        (self.owned / "c_one.prt.1").write_bytes(b"old part")
        (self.owned / "c_one.prt.2").write_bytes(b"part version 2")
        self.model = {"model_type": "assembly", "part_file": str(self.asm), "revision": 7}

    def test_closure_relative_paths_hashes_and_source_unchanged(self):
        inspection = {"components": [{"model_name": "c_one", "model_type": "part"}]}
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.owned.iterdir()}
        result = create_bundle(self.model, inspection, self.job, self.owned)
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertEqual([f["path"] for f in manifest["files"]], ["pump.asm", "c_one.prt"])
        self.assertEqual((self.job / "native_bundle" / "c_one.prt").read_bytes(), b"part version 2")
        self.assertFalse(any(":" in f["path"] or ".." in f["path"] for f in manifest["files"]))
        self.assertEqual(self.model["revision"], 7)
        self.assertEqual(
            before,
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.owned.iterdir()},
        )

    def test_missing_and_nested_unknown_are_explicit(self):
        inspection = {
            "components": [
                {"model_name": "absent", "model_type": "part"},
                {"model_name": "nested", "model_type": "assembly"},
            ]
        }
        result = create_bundle(self.model, inspection, self.job, self.owned)
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertFalse(manifest["complete"])
        self.assertGreaterEqual(result["missing"], 2)
        self.assertIn("nested_closure_unknown", str(manifest["unresolved_references"]))

    def test_nested_reference_closure_when_children_are_known(self):
        (self.owned / "nested.asm.1").write_bytes(b"nested assembly")
        (self.owned / "leaf.prt.1").write_bytes(b"leaf part")
        inspection = {
            "components": [
                {
                    "model_name": "nested",
                    "model_type": "assembly",
                    "components": [{"model_name": "leaf", "model_type": "part"}],
                }
            ]
        }
        result = create_bundle(self.model, inspection, self.job, self.owned)
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertTrue(manifest["complete"])
        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["pump.asm", "nested.asm", "leaf.prt"],
        )

    def test_external_root_and_unsafe_identity_refused(self):
        external = self.root / "external.asm.1"
        external.write_bytes(b"external")
        with self.assertRaisesRegex(ValueError, "owned"):
            create_bundle(
                {**self.model, "part_file": str(external)}, {"components": []}, self.job, self.owned
            )
        result = create_bundle(
            self.model, {"components": [{"model_name": "../secret"}]}, self.job, self.owned
        )
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertFalse(manifest["complete"])
        self.assertEqual(manifest["unresolved_references"][0]["reason"], "unresolved_identity")

    def test_failure_removes_only_new_bundle_directory(self):
        sentinel = self.job / "existing.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with patch(
            "creo_mechdog.assembly_bundle.shutil.copyfile", side_effect=OSError("disk full")
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                create_bundle(self.model, {"components": []}, self.job, self.owned)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.job / "native_bundle").exists())
        self.assertTrue(self.asm.is_file())

    def test_old_export_contract_and_explicit_new_format(self):
        self.assertEqual(
            validate_operations([{"op": "export"}]), [{"op": "export", "format": "step"}]
        )
        for fmt in ("step", "stl", "iges", "jpeg", "pdf", "native_bundle"):
            self.assertEqual(
                validate_operations([{"op": "export", "format": fmt}])[0]["format"], fmt
            )


if __name__ == "__main__":
    unittest.main()
