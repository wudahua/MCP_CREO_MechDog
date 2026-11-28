"""Contract tests for the BACKLOG table/declaration count check (DEV-077)."""

import unittest
from pathlib import Path

from creo_mechdog.backlog_counts import summarize

BACKLOG = Path(__file__).resolve().parents[2] / "docs" / "BACKLOG.md"

SAMPLE = """# ledger

## 使用与计数

当前唯一 ID **3**（BUG **2**、FEAT **1**、DEV **0**）；历史说明不影响计数。

| 当前分类 | 唯一 ID 数 |
| --- | --- |
| 仍需修复 | 2 |
| 待规划 | 1 |

## 仍需修复

| ID / 工作卡 | 优先级 | 当前状态 |
| --- | --- | --- |
| [BUG-001](work-items/BUG-001.md) | P1 | 仍需修复 |
| [BUG-002](work-items/BUG-002.md) | P2 | 仍需修复 |

## 待规划

| ID / 工作卡 | 优先级 | 当前状态 |
| --- | --- | --- |
| [FEAT-001](work-items/FEAT-001.md) | P1 | 待规划 |
"""


class BacklogCountsTest(unittest.TestCase):
    def test_consistent_sample_has_no_problems(self):
        report = summarize(SAMPLE)
        self.assertEqual(report["actual"], {"BUG": 2, "FEAT": 1, "DEV": 0})
        self.assertEqual(report["actual_total"], 3)
        self.assertEqual(report["category_total"], 3)
        self.assertEqual(report["duplicates"], [])
        self.assertEqual(report["problems"], [])
        self.assertTrue(report["consistent"])

    def test_stale_declared_total_is_reported(self):
        report = summarize(SAMPLE.replace("**3**（BUG", "**4**（BUG", 1))
        self.assertFalse(report["consistent"])
        self.assertIn("declared_total", report["problems"])

    def test_stale_prefix_count_is_reported(self):
        report = summarize(SAMPLE.replace("FEAT **1**", "FEAT **2**", 1))
        self.assertFalse(report["consistent"])
        self.assertIn("declared_FEAT", report["problems"])

    def test_category_rows_must_sum_to_table_rows(self):
        report = summarize(SAMPLE.replace("| 待规划 | 1 |", "| 待规划 | 2 |", 1))
        self.assertFalse(report["consistent"])
        self.assertIn("category_total", report["problems"])

    def test_duplicate_id_is_reported(self):
        report = summarize(
            SAMPLE.replace(
                "[FEAT-001](work-items/FEAT-001.md)",
                "[BUG-001](work-items/BUG-001.md)",
                1,
            )
        )
        self.assertFalse(report["consistent"])
        self.assertEqual(report["duplicates"], ["BUG-001"])

    def test_current_repository_backlog_is_consistent(self):
        report = summarize(BACKLOG.read_text(encoding="utf-8"))
        self.assertTrue(report["consistent"], report["problems"])
        self.assertEqual(report["category_mismatches"], [])

    def test_same_total_swapped_group_counts_fails_and_names_both_groups(self):
        text = BACKLOG.read_text(encoding="utf-8")
        baseline = summarize(text)
        count_a = baseline["declared_categories"]["已有修复但待验收"]
        count_b = baseline["declared_categories"]["部分交付，剩余待验收"]
        old_a, new_a = f"| 已有修复但待验收 | {count_a} |", f"| 已有修复但待验收 | {count_a - 1} |"
        old_b, new_b = (
            f"| 部分交付，剩余待验收 | {count_b} |",
            f"| 部分交付，剩余待验收 | {count_b + 1} |",
        )
        self.assertIn(old_a, text)
        self.assertIn(old_b, text)
        mutated = text.replace(old_a, new_a, 1).replace(old_b, new_b, 1)
        report = summarize(mutated)
        self.assertFalse(report["consistent"])
        self.assertEqual(report["category_total"], report["actual_total"])
        self.assertNotIn("category_total", report["problems"])
        self.assertIn("category_mismatch:已有修复但待验收", report["problems"])
        self.assertIn("category_mismatch:部分交付，剩余待验收", report["problems"])
        by_name = {item["category"]: item for item in report["category_mismatches"]}
        self.assertEqual(
            by_name["已有修复但待验收"],
            {
                "category": "已有修复但待验收",
                "declared": count_a - 1,
                "actual": count_a,
                "reason": "count_mismatch",
            },
        )
        self.assertEqual(
            by_name["部分交付，剩余待验收"],
            {
                "category": "部分交付，剩余待验收",
                "declared": count_b + 1,
                "actual": count_b,
                "reason": "count_mismatch",
            },
        )

    def test_zero_entry_group_passes_when_heading_exists_and_fails_when_missing(self):
        with_zero = SAMPLE.replace("| 待规划 | 1 |", "| 开发中 | 0 |\n| 待规划 | 1 |", 1).replace(
            "## 待规划",
            "## 开发中\n\n| ID / 工作卡 | 优先级 | 当前状态 |\n| --- | --- | --- |\n\n## 待规划",
            1,
        )
        ok_report = summarize(with_zero)
        self.assertTrue(ok_report["consistent"], ok_report["problems"])
        self.assertEqual(ok_report["actual_categories"]["开发中"], 0)

        missing_heading = SAMPLE.replace("| 待规划 | 1 |", "| 开发中 | 0 |\n| 待规划 | 1 |", 1)
        bad_report = summarize(missing_heading)
        self.assertFalse(bad_report["consistent"])
        self.assertIn("category_missing:开发中", bad_report["problems"])

    def test_undeclared_section_with_id_rows_fails(self):
        extra = (
            SAMPLE
            + "\n## 未知分组\n\n| ID / 工作卡 |\n| --- |\n| [DEV-999](work-items/DEV-999.md) |\n"
        )
        mutated = extra.replace(
            "**3**（BUG **2**、FEAT **1**、DEV **0**）",
            "**4**（BUG **2**、FEAT **1**、DEV **1**）",
            1,
        )
        report = summarize(mutated)
        self.assertFalse(report["consistent"])
        self.assertIn("category_undeclared:未知分组", report["problems"])


if __name__ == "__main__":
    unittest.main()
