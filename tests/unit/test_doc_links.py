"""Contract tests for the active non-frozen Markdown link/anchor checker (DEV-111)."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from creo_mechdog.doc_links import check_doc_links, discover_active_markdown

ROOT = Path(__file__).resolve().parents[2]


class DocLinksTest(unittest.TestCase):
    def test_current_repository_active_docs_have_no_broken_links_or_anchors(self):
        report = check_doc_links(ROOT)
        self.assertTrue(report["consistent"], report)
        self.assertEqual(report["broken_files"], [])
        self.assertEqual(report["broken_anchors"], [])
        self.assertGreater(report["files_scanned"], 0)
        self.assertGreater(report["links_checked"], 0)

    def test_missing_target_file_fails_in_api_and_cli(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "README.md").write_text("See [missing](docs/missing.md).\n", encoding="utf-8")
        report = check_doc_links(root)
        self.assertFalse(report["consistent"])
        self.assertEqual(len(report["broken_files"]), 1)
        self.assertEqual(report["broken_files"][0]["link"], "docs/missing.md")
        self.assertEqual(report["broken_files"][0]["reason"], "missing_file")

        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "check_doc_links.py"), "--root", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('"consistent": false', result.stdout)

    def test_existing_file_with_bad_anchor_fails_in_api_and_cli(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "guide.md").write_text("# 标题示例\n\n## 子节\n", encoding="utf-8")
        (root / "README.md").write_text("See [bad](docs/guide.md#不存在锚点).\n", encoding="utf-8")
        report = check_doc_links(root)
        self.assertFalse(report["consistent"])
        self.assertEqual(report["broken_files"], [])
        self.assertEqual(len(report["broken_anchors"]), 1)
        self.assertEqual(report["broken_anchors"][0]["anchor"], "不存在锚点")

        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "check_doc_links.py"), "--root", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('"broken_anchors": [', result.stdout)

    def test_discovery_is_dynamic_and_skips_frozen_dirs(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for sub in ("archive", "validation", "release-notes", "work-items"):
            (root / "docs" / sub).mkdir(parents=True)
        (root / "docs" / "archive" / "old.md").write_text("[x](nope.md#bad)\n", encoding="utf-8")
        (root / "docs" / "validation" / "hist.md").write_text("[x](nope.md)\n", encoding="utf-8")
        (root / "docs" / "release-notes" / "rn.md").write_text("[x](nope.md)\n", encoding="utf-8")
        (root / "docs" / "work-items" / "DEV-1.md").write_text(
            "Link to [frozen](../validation/hist.md).\n", encoding="utf-8"
        )
        self.assertEqual(len(discover_active_markdown(root)), 1)
        (root / "docs" / "work-items" / "DEV-2.md").write_text("# New\n", encoding="utf-8")
        self.assertEqual(len(discover_active_markdown(root)), 2)
        report = check_doc_links(root)
        self.assertTrue(report["consistent"], report)
        self.assertEqual(report["files_scanned"], 2)

    def test_valid_anchors_duplicates_html_ids_and_code_blocks(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "target.md").write_text(
            '# 第一节\n\n## 重复\n\n## 重复\n\n<a id="legacy-id"></a>\n',
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "[h1](docs/target.md#第一节)\n"
            "[d0](docs/target.md#重复)\n"
            "[d1](docs/target.md#重复-1)\n"
            "[html](docs/target.md#legacy-id)\n"
            "`[ignored](missing.md#nope)`\n"
            "```markdown\n[ignored-fence](missing.md#nope)\n```\n",
            encoding="utf-8",
        )
        report = check_doc_links(root)
        self.assertTrue(report["consistent"], report)
        self.assertEqual(report["links_checked"], 4)

    def test_isolated_copy_without_site_packages_exits_zero(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (root / "tools").mkdir()
        (root / "src" / "creo_mechdog").mkdir(parents=True)
        (root / "docs").mkdir()
        shutil.copyfile(
            ROOT / "tools" / "check_doc_links.py", root / "tools" / "check_doc_links.py"
        )
        shutil.copyfile(
            ROOT / "src" / "creo_mechdog" / "doc_links.py",
            root / "src" / "creo_mechdog" / "doc_links.py",
        )
        (root / "README.md").write_text("[guide](docs/guide.md#intro)\n", encoding="utf-8")
        (root / "docs" / "guide.md").write_text("# Intro\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(root / "tools" / "check_doc_links.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"consistent": true', result.stdout)

    def test_backlog_has_no_duplicate_recent_entries_and_preserves_anchors(self):
        text = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
        for needle in (
            "2026-11-27（0.48.2 PATCH）",
            "2026-11-26（0.46.1 PATCH",
            "2026-11-25：登记 [BUG-191]",
            "2026-11-24 及更早历史动态已归档至",
        ):
            self.assertEqual(text.count(needle), 1, needle)
        for anchor in (
            '<a id="输入或规则待核实"></a>',
            '<a id="未来能力候选"></a>',
            '<a id="当前优先功能"></a>',
            '<a id="workbuddy-030-全量实测问题映射"></a>',
        ):
            self.assertIn(anchor, text)


if __name__ == "__main__":
    unittest.main()
