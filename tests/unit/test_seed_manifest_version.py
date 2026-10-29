"""Keep the shipped seed manifests tied to the server and packager."""

import ast
import json
import unittest
from pathlib import Path

from version import VERSION

ROOT = Path(__file__).resolve().parents[2]


class SeedManifestVersionTests(unittest.TestCase):
    def test_shipped_manifests_match_server_version(self):
        library = json.loads((ROOT / "seed_library/seed_manifest.json").read_text(encoding="utf-8"))
        documentation = json.loads((ROOT / "docs/seed_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(library, documentation)
        self.assertEqual(library["compatible_server_version"], VERSION)

    def test_packager_checks_manifest_version(self):
        source = (ROOT / "tools/package_seeds.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        checks = [node.test for node in ast.walk(tree) if isinstance(node, ast.Assert)]
        self.assertTrue(
            any(
                isinstance(check, ast.Compare)
                and isinstance(check.left, ast.Subscript)
                and isinstance(check.left.value, ast.Name)
                and check.left.value.id == "manifest"
                and isinstance(check.left.slice, ast.Constant)
                and check.left.slice.value == "compatible_server_version"
                and len(check.comparators) == 1
                and isinstance(check.comparators[0], ast.Name)
                and check.comparators[0].id == "VERSION"
                and len(check.ops) == 1
                and isinstance(check.ops[0], ast.Eq)
                for check in checks
            )
        )
