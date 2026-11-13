"""BUG-124/C1: STEP/IGES import is one new plan that the importer itself creates.

The documented entry point (``ProIntfimport.h``) always creates a model, so the
contract is not "add an import feature": it is "one import operation, no
model_id, no other operation". Everything here is offline: the schema, the
admission rules and the native call sites. No Creo session is touched, and no
claim is made that a licence admits the import - the operation stays behind
``UNAVAILABLE_OPERATIONS`` until a live run proves it.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creo_mechdog import capabilities
from creo_mechdog.capabilities import REGISTERED_OPERATIONS, require_available
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
IMPORT_NATIVE = ROOT / "native" / "import_geometry.cpp"
GENERIC_NATIVE = ROOT / "native" / "generic.cpp"
SERVER = ROOT / "server.py"


def write(path: Path, content: bytes = b"ISO-10303-21;") -> Path:
    path.write_bytes(content)
    return path


class ImportGeometrySchema(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.part = write(self.directory / "bulb.stp")
        self.profile = write(self.directory / "step_profile.prof")

    def operation(self, **overrides):
        payload = {
            "op": "import_geometry",
            "file": str(self.part),
            "profile": str(self.profile),
            "format": "step",
        }
        payload.update(overrides)
        return payload

    def test_accepts_a_step_import_and_fills_both_digests(self):
        (validated,) = validate_operations([self.operation()])
        self.assertEqual(validated["format"], "step")
        self.assertEqual(validated["file"], str(self.part.resolve()))
        self.assertEqual(
            validated["file_sha256"], hashlib.sha256(self.part.read_bytes()).hexdigest()
        )
        self.assertEqual(
            validated["profile_sha256"], hashlib.sha256(self.profile.read_bytes()).hexdigest()
        )

    def test_the_extension_must_match_the_declared_format(self):
        iges = write(self.directory / "bulb.igs")
        with self.assertRaises(ValueError) as caught:
            validate_operations([self.operation(file=str(iges))])
        self.assertIn("needs a .stp or .step file", str(caught.exception))

    def test_a_missing_file_is_refused_with_its_path(self):
        missing = self.directory / "gone.step"
        with self.assertRaises(ValueError) as caught:
            validate_operations([self.operation(file=str(missing))])
        self.assertIn("does not exist", str(caught.exception))

    def test_a_declared_digest_must_match_the_file(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([self.operation(file_sha256="0" * 64)])
        self.assertIn("does not match the file on disk", str(caught.exception))

    def test_iges_is_accepted_with_its_own_suffix(self):
        iges = write(self.directory / "bulb.iges")
        (validated,) = validate_operations([self.operation(file=str(iges), format="iges")])
        self.assertEqual(validated["format"], "iges")

    def test_the_profile_is_optional_and_defaults_to_creos_own_settings(self):
        # ProIntfimport.h keeps a passed profile for the whole session, so the
        # default route must be able to omit it entirely.
        (validated,) = validate_operations(
            [{"op": "import_geometry", "file": str(self.part), "format": "step"}]
        )
        self.assertNotIn("profile", validated)
        self.assertNotIn("profile_sha256", validated)

    def test_a_profile_digest_without_a_profile_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations(
                [
                    {
                        "op": "import_geometry",
                        "file": str(self.part),
                        "format": "step",
                        "profile_sha256": "0" * 64,
                    }
                ]
            )
        self.assertIn("without a profile", str(caught.exception))


class ImportGeometryAdmission(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.part = write(self.directory / "bulb.stp")
        self.profile = write(self.directory / "step_profile.prof")
        # The gate is the only thing between the caller and this route in the
        # release; the admission rules below are exercised with it removed so
        # they keep working on the day the entry is deleted.
        gate = patch.dict(capabilities.UNAVAILABLE_OPERATIONS, clear=True)
        gate.start()
        self.addCleanup(gate.stop)

    def operation(self):
        return {
            "op": "import_geometry",
            "file": str(self.part),
            "profile": str(self.profile),
            "format": "step",
        }

    def submit(self, operations, **kwargs):
        import generic_bridge

        return generic_bridge.submit(operations, **kwargs)

    def test_an_existing_model_cannot_receive_an_import(self):
        with self.assertRaises(ValueError) as caught:
            self.submit([self.operation()], model_id="0" * 32)
        self.assertIn("creates its own new part", str(caught.exception))

    def test_the_import_must_be_the_only_operation(self):
        with self.assertRaises(ValueError) as caught:
            self.submit([self.operation(), {"op": "save"}], model_name="bulb")
        self.assertIn("only operation of its plan", str(caught.exception))

    def test_a_read_only_submission_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.submit([self.operation()], model_name="bulb", readonly=True)
        self.assertIn("cannot run read-only", str(caught.exception))

    def test_an_assembly_import_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self.submit([self.operation()], model_name="bulb", model_type="assembly")
        self.assertIn("imports into a part model", str(caught.exception))


class ImportGeometryReleaseGate(unittest.TestCase):
    def test_the_operation_is_registered(self):
        self.assertIn("import_geometry", REGISTERED_OPERATIONS)

    def test_it_is_published_only_because_a_live_run_proved_it(self):
        # The gate left the table on 2026-11-13 after STEP and IGES imports ran on
        # Creo 12.4; the evidence lives in the geometry_import family and in the
        # BUG-124 work item, so a regression must put the entry back rather than
        # quietly keep publishing an unproved route.
        self.assertNotIn("import_geometry", capabilities.UNAVAILABLE_OPERATIONS)
        require_available([{"op": "import_geometry"}])

    def test_the_family_records_the_live_evidence_and_the_limits(self):
        family = capabilities.families()["geometry_import"]
        self.assertTrue(family["enabled"])
        self.assertIn("create_code=0", family["native_test"])
        self.assertIn("never into an existing model", family["limits"])

    def test_it_is_not_smuggled_into_the_read_only_allowlist(self):
        import generic_bridge

        self.assertNotIn("import_geometry", generic_bridge.INSPECTION_ONLY_OPERATIONS)


class ImportGeometryNativeContract(unittest.TestCase):
    def setUp(self):
        self.source = IMPORT_NATIVE.read_text(encoding="utf-8")
        self.generic = GENERIC_NATIVE.read_text(encoding="utf-8")

    def test_it_calls_the_documented_entry_point_with_the_master_representation(self):
        self.assertIn("ProIntfimportModelWithOptionsMdlnameCreate", self.source)
        self.assertIn("PRO_IMPORTREP_MASTER", self.source)
        self.assertIn("PRO_MDL_UNUSED", self.source)
        self.assertIn("PRO_INTF_IMPORT_STEP", self.source)
        self.assertIn("PRO_INTF_IMPORT_IGES", self.source)

    def test_a_licence_refusal_keeps_its_own_code(self):
        self.assertIn("PRO_TK_NO_LICENSE", self.source)
        self.assertIn('"create_code_name"', self.source)

    def test_both_inputs_are_re_hashed_before_the_import(self):
        self.assertIn("mechdog_callback::sha256", self.source)
        self.assertIn("IMPORT_GEOMETRY_INPUT_CHANGED", self.source)

    def test_an_unmeasured_area_is_published_with_its_status(self):
        self.assertIn(
            'area_fields_json(area, units, scale, "area_mm2", "area_status")', self.source
        )
        self.assertIn('"quilt_closure"', self.source)

    def test_the_receipt_says_whether_a_profile_was_set(self):
        # The header keeps a profile for the whole session, so a job that passes
        # one must be distinguishable from a job that rode the session default.
        self.assertIn('"profile_source"', self.source)
        self.assertIn("has_profile ? profile_file : nullptr", self.source)

    def test_the_mixed_plan_and_the_existing_model_are_refused_natively(self):
        self.assertIn("must be the only operation of its plan", self.source)
        self.assertIn("the import call creates ", self.source)
        self.assertIn("so nothing can run before it", self.source)
        self.assertIn("instead of appending it to an existing model", self.source)
        self.assertIn(
            "import_geometry creates its own new part and cannot be appended to an", self.generic
        )

    def test_generic_includes_dispatches_and_creates_through_the_import(self):
        self.assertIn('#include "import_geometry.cpp"', self.generic)
        self.assertIn('kind == "import_geometry"', self.generic)
        self.assertIn("board = import_geometry_create(", self.generic)
        self.assertIn("import_geometry_reset();", self.generic)
        # The template copy must be the fallback, never a step before the import:
        # the importer creates the part itself.
        create_at = self.generic.index("board = import_geometry_create(")
        copy_at = self.generic.index("ProMdlnameCopy(templ, new_name, &board)", create_at)
        self.assertLess(create_at, copy_at)

    def test_the_new_source_file_is_part_of_the_runtime_identity(self):
        self.assertIn("native/import_geometry.cpp", SERVER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
