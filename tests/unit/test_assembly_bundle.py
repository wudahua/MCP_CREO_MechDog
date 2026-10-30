"""Offline native bundle ownership, closure, manifest and cleanup fixtures."""

from __future__ import annotations

import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creo_mechdog.assembly_bundle import create_bundle
from creo_mechdog.schema import validate_operations


def component(feature_id: int, kind: str = "part", **extra) -> dict:
    record = {"feature_id": feature_id, "model_type": kind}
    record.update(extra)
    return record


def binding(feature_id: int, snapshot_name: object, label: str) -> dict:
    return {
        label: {
            "op": "assemble_component",
            "feature_id": feature_id,
            "snapshot_name": snapshot_name,
        }
    }


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
        self.model = {
            "model_type": "assembly",
            "part_file": str(self.asm),
            "revision": 7,
            "aliases": binding(40, "c_one", "part_alpha"),
        }

    def bundle(self, inspection: dict, model: dict | None = None) -> dict:
        # create_bundle refuses to overwrite a job's bundle directory, so every
        # call in one test gets its own job output directory.
        output = self.job / f"attempt-{len(list(self.job.iterdir()))}"
        output.mkdir()
        result = create_bundle(model or self.model, inspection, output, self.owned)
        result["manifest_payload"] = json.loads(
            Path(result["manifest"]).read_text(encoding="utf-8")
        )
        return result

    def test_closure_relative_paths_hashes_and_source_unchanged(self):
        inspection = {"components": [component(40)]}
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.owned.iterdir()}
        result = self.bundle(inspection)
        manifest = result["manifest_payload"]
        self.assertTrue(result["complete"])
        self.assertEqual([f["path"] for f in manifest["files"]], ["pump.asm", "c_one.prt"])
        self.assertEqual((Path(result["directory"]) / "c_one.prt").read_bytes(), b"part version 2")
        self.assertFalse(any(":" in f["path"] or ".." in f["path"] for f in manifest["files"]))
        self.assertEqual(self.model["revision"], 7)
        self.assertEqual(
            before,
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.owned.iterdir()},
        )

    def test_unresolved_identity_never_marks_complete(self):
        """No record, a mangled name and an ambiguous name all refuse to bundle."""
        cases = {
            "no_record": (
                {"components": [component(40)]},
                {**self.model, "aliases": {}},
            ),
            "foreign_name": (
                {"components": [component(40)]},
                {**self.model, "aliases": binding(40, "▩C_ONE0001", "part_alpha")},
            ),
            "path_name": (
                {"components": [component(40)]},
                {**self.model, "aliases": binding(40, "../secret", "part_alpha")},
            ),
            "upper_name": (
                {"components": [component(40)]},
                {**self.model, "aliases": binding(40, "C_ONE", "part_alpha")},
            ),
            "name_is_not_a_string": (
                {"components": [component(40)]},
                {**self.model, "aliases": binding(40, None, "part_alpha")},
            ),
            "missing_feature_id": (
                {"components": [{"model_type": "part"}]},
                self.model,
            ),
            "ambiguous_identity": (
                {"components": [component(40)]},
                {
                    **self.model,
                    "aliases": {
                        **binding(40, "c_one", "part_alpha"),
                        **binding(40, "c_other", "part_alpha_again"),
                    },
                },
            ),
        }
        for label, (inspection, model) in cases.items():
            with self.subTest(label):
                result = self.bundle(inspection, model)
                manifest = result["manifest_payload"]
                self.assertFalse(manifest["complete"], label)
                self.assertFalse(result["complete"], label)
                self.assertEqual(
                    [ref["reason"] for ref in manifest["unresolved_references"]],
                    ["unresolved_identity"],
                    label,
                )

    def test_repeated_occurrences_share_verified_file(self):
        (self.owned / "c_two.prt.1").write_bytes(b"second part")
        model = {
            **self.model,
            "aliases": {
                **binding(40, "c_one", "part_alpha"),
                **binding(41, "c_one", "part_alpha_again"),
                **binding(42, "c_two", "part_beta"),
            },
        }
        result = self.bundle({"components": [component(40), component(41), component(42)]}, model)
        manifest = result["manifest_payload"]
        self.assertTrue(manifest["complete"])
        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["pump.asm", "c_one.prt", "c_two.prt"],
        )
        self.assertEqual(result["missing"], 0)

    def test_missing_and_nested_unknown_are_explicit(self):
        (self.owned / "c_nested.asm.1").write_bytes(b"nested assembly")
        model = {
            **self.model,
            "aliases": {
                **binding(40, "c_absent", "part_alpha"),
                **binding(41, "c_nested", "part_beta"),
            },
        }
        result = self.bundle({"components": [component(40), component(41, "assembly")]}, model)
        manifest = result["manifest_payload"]
        self.assertFalse(manifest["complete"])
        self.assertGreaterEqual(result["missing"], 2)
        self.assertIn("nested_closure_unknown", str(manifest["unresolved_references"]))

    def test_nested_reference_closure_when_children_are_known(self):
        (self.owned / "c_nested.asm.1").write_bytes(b"nested assembly")
        (self.owned / "c_leaf.prt.1").write_bytes(b"leaf part")
        model = {
            **self.model,
            "aliases": {
                **binding(40, "c_nested", "part_alpha"),
                **binding(41, "c_leaf", "part_beta"),
            },
        }
        result = self.bundle(
            {
                "components": [
                    component(40, "assembly", components=[component(41)]),
                ]
            },
            model,
        )
        manifest = result["manifest_payload"]
        self.assertTrue(manifest["complete"])
        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["pump.asm", "c_nested.asm", "c_leaf.prt"],
        )

    def test_read_only_source_is_copied_without_writing_back(self):
        source = self.owned / "c_one.prt.2"
        source.chmod(stat.S_IREAD)
        self.addCleanup(source.chmod, stat.S_IREAD | stat.S_IWRITE)
        self.assertEqual(source.stat().st_mode & stat.S_IWRITE, 0)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        result = self.bundle({"components": [component(40)]})
        self.assertTrue(result["manifest_payload"]["complete"])
        self.assertEqual((Path(result["directory"]) / "c_one.prt").read_bytes(), b"part version 2")
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
        self.assertEqual(source.stat().st_mode & stat.S_IWRITE, 0)

    def test_external_root_and_unsafe_identity_refused(self):
        external = self.root / "external.asm.1"
        external.write_bytes(b"external")
        with self.assertRaisesRegex(ValueError, "owned"):
            create_bundle(
                {**self.model, "part_file": str(external)}, {"components": []}, self.job, self.owned
            )
        result = self.bundle(
            {"components": [component(40)]},
            {**self.model, "aliases": binding(40, "../secret", "part_alpha")},
        )
        self.assertFalse(result["manifest_payload"]["complete"])
        self.assertEqual(
            result["manifest_payload"]["unresolved_references"][0]["reason"], "unresolved_identity"
        )

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
