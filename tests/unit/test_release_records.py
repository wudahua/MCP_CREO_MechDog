"""DEV-083: the release-record gate refuses stale or placeholder documents."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from creo_mechdog.release_integrity import validate_release_records

VERSION = "0.23.1"
DIGEST = "a" * 64
POSTCHECK = "docs/development/RELEASE-POSTCHECK-2026-11-07.md"
RECORD = f"docs/validation/RELEASE-{VERSION}.md"
NOTES = f"docs/RELEASE_NOTES_{VERSION}.md"
RELEASE_URL = f"https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v{VERSION}"
ASSETS = [
    f"MCP_CREO_MechDog-{VERSION}-source.zip",
    f"MCP_CREO_MechDog-{VERSION}-source.zip.sha256",
    f"MCP_CREO_MechDog-{VERSION}-seed-library.zip",
    f"MCP_CREO_MechDog-{VERSION}-seed-library.zip.sha256",
]


def _asset_table() -> str:
    rows = "\n".join(f"| `{name}` | `{'b' * 64}` |" for name in ASSETS)
    return f"| 附件 | SHA256 |\n| --- | --- |\n{rows}"


def _fixture_files() -> dict[str, str]:
    return {
        "version.py": f'VERSION = "{VERSION}"\n',
        "README.md": f"# MCP_CREO_MechDog {VERSION}\n\n当前正式版 **{VERSION}**\n",
        "docs/seed_package.json": (
            f'{{"compatible_server_version": "{VERSION}", "seed_archive_sha256": "{DIGEST}"}}\n'
        ),
        "docs/seed_manifest.json": f'{{"compatible_server_version": "{VERSION}"}}\n',
        "seed_library/seed_manifest.json": f'{{"compatible_server_version": "{VERSION}"}}\n',
        NOTES: (
            f"# {VERSION} 版本说明\n\n"
            f"- [BUG-119](work-items/BUG-119.md)\n"
            f"- [发布记录](validation/RELEASE-{VERSION}.md)\n"
            f"- [版本文件](../version.py)\n"
        ),
        POSTCHECK: (
            "# 发布后附件核对记录\n\n"
            f"## v{VERSION}（预发布）\n\n"
            f"- Release：[v{VERSION}]({RELEASE_URL})\n"
            f"- 种子包 SHA256 `{DIGEST}`\n\n"
            f"{_asset_table()}\n"
        ),
        RECORD: (
            f"# 发布记录 {VERSION}\n\n"
            f"- Release URL：{RELEASE_URL}\n"
            f"- 种子包 SHA256 `{DIGEST}`\n"
            "- source.zip 摘要见同名 sidecar。\n\n"
            f"{_asset_table()}\n\n"
            "## 逐 ID 状态核对\n\n"
            "| ID | 技术状态 | 卡首页 | 主台账 | 差异说明 |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| [BUG-119](../work-items/BUG-119.md) | 已实现并实机验收 | 已交付 {VERSION} "
            f"| 已交付 {VERSION} | 无 |\n"
        ),
        "docs/BACKLOG.md": (
            "# 台账\n\n"
            "| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| [BUG-119](work-items/BUG-119.md) | P1 | 已交付 {VERSION} | {VERSION} | 已交付。 |\n"
        ),
        "docs/work-items/BUG-119.md": (
            f"# BUG-119 surface_loft 实体判定\n\n- 分类：已交付 {VERSION}\n"
        ),
    }


def _write_tree(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(f"MCP_CREO_MechDog/{name}", text)


def _partial_backlog() -> str:
    return (
        "# 台账\n\n"
        "| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| [BUG-119](work-items/BUG-119.md) | P1 | 部分交付，剩余待验收 | {VERSION} | 待验收。 |\n"
    )


class ReleaseRecordGateTest(unittest.TestCase):
    def test_complete_fixture_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, _fixture_files())
            self.assertEqual(validate_release_records(VERSION, root=root), [])

    def test_missing_postcheck_section_is_rejected(self):
        files = _fixture_files()
        files[POSTCHECK] = "# 发布后附件核对记录\n\n## v0.23.0（2026-11-12）\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("no '## v0.23.1' section" in problem for problem in problems))

    def test_placeholder_in_section_is_rejected(self):
        files = _fixture_files()
        files[POSTCHECK] += "\n- 附件摘要：待回填\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("placeholder" in problem for problem in problems))

    def test_source_tree_rejects_placeholder_record(self):
        files = _fixture_files()
        files[RECORD] += "\n- 发布核对：待发布后回填\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("placeholder" in problem for problem in problems))

    def test_stale_documents_inside_source_zip_are_rejected(self):
        files = _fixture_files()
        files[POSTCHECK] = "# 发布后附件核对记录\n\n## v0.23.0（2026-11-12）\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, _fixture_files())
            source = root / ASSETS[0]
            _write_zip(source, files)
            problems = validate_release_records(VERSION, source, root=root)
            self.assertTrue(any("POSTCHECK" in problem for problem in problems))

    def test_work_item_status_mismatch_is_rejected(self):
        files = _fixture_files()
        files["docs/BACKLOG.md"] = (
            "# 台账\n\n"
            "| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| [BUG-119](work-items/BUG-119.md) | P1 | 开发中 | {VERSION} | 仍在开发。 |\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("work card BUG-119" in problem for problem in problems))
            self.assertTrue(any("卡首页" in problem for problem in problems))

    def test_partial_backlog_with_delivered_card_is_rejected(self):
        files = _fixture_files()
        files["docs/BACKLOG.md"] = _partial_backlog()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("work card BUG-119" in problem for problem in problems))

    def test_explained_mismatch_is_allowed(self):
        files = _fixture_files()
        files["docs/BACKLOG.md"] = _partial_backlog()
        files[RECORD] = files[RECORD].replace(
            "| 已交付 0.23.1 | 无 |", "| 已交付 0.23.1 | 整体卡仍有剩余 |"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            self.assertEqual(validate_release_records(VERSION, root=root), [])

    def test_ledger_cell_mismatch_is_rejected(self):
        files = _fixture_files()
        files["docs/BACKLOG.md"] = _partial_backlog()
        files["docs/work-items/BUG-119.md"] = (
            f"# BUG-119 surface_loft 实体判定\n\n- 分类：部分交付 {VERSION}\n"
        )
        files[RECORD] = files[RECORD].replace(
            f"| 已交付 {VERSION} | 已交付 {VERSION} | 无 |",
            f"| 部分交付 {VERSION} | 已交付 {VERSION} | 无 |",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("主台账" in problem for problem in problems))

    def test_release_table_mismatch_outside_release_rows_is_rejected(self):
        files = _fixture_files()
        files["docs/BACKLOG.md"] += (
            "| [FEAT-066](work-items/FEAT-066.md) | P1 | 部分交付，剩余待规划 | 未排期 | 剩余。 |\n"
        )
        files["docs/work-items/FEAT-066.md"] = "# FEAT-066 b_spline\n\n- 分类：已交付 0.23.0\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("work card FEAT-066" in problem for problem in problems))

    def test_broken_release_note_link_is_rejected(self):
        files = _fixture_files()
        files[NOTES] += "\n- [错误](../work-items/BUG-119.md)\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(any("broken local link" in problem for problem in problems))

    def test_broken_link_inside_source_zip_is_rejected(self):
        files = _fixture_files()
        files[NOTES] += "\n- [错误](../work-items/BUG-119.md)\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, _fixture_files())
            source = root / ASSETS[0]
            _write_zip(source, files)
            problems = validate_release_records(VERSION, source, root=root)
            self.assertTrue(any("broken local link" in problem for problem in problems))

    def test_work_item_missing_from_card_is_rejected(self):
        files = _fixture_files()
        del files["docs/work-items/BUG-119.md"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write_tree(root, files)
            problems = validate_release_records(VERSION, root=root)
            self.assertTrue(
                any("missing docs/work-items/BUG-119.md" in problem for problem in problems)
            )

    def test_version_before_enforcement_skips_record_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(validate_release_records("0.23.0", root=Path(temp)), [])

    def test_non_semver_version_is_rejected(self):
        self.assertTrue(validate_release_records("0.23", root=Path(".")))


if __name__ == "__main__":
    unittest.main()
