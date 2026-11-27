# 发布记录 v0.48.1

2026-11-27 PATCH，公开工具数 112。上一版本：0.48.0（`v0.48.0`，提交 `b9d11b85ccfcba1247e37deb43ce887b954a6d50`）。

## 验收范围

复核 0.47.0 外部反馈原件（已在 0.48.0 逐字节归档至 [feedback-0.47.0-0.47.1-2026-11-26](../validation/feedback-0.47.0-0.47.1-2026-11-26/SOURCE_MANIFEST.json)）与 0.48.0 实现后，补齐 [BUG-196](../work-items/BUG-196.md) 两处 Python 侧快照检测边界（分拆 `inspection_ref` 零件快照的 `surfaces[].area_mm2` 过期检出与装配体 `merged_counts` 误报消除），并合入交付 [DEV-106](../work-items/DEV-106.md)（三批 P1 台账复核与全量 115 份活跃非冻结文档 364 处迁移断链修复，归档 `DEV-052`/`DEV-065`/`BUG-175`/`DEV-079` 并将 `开发中` 存量清零转入完成档案）。

离线门禁（Windows x64 / Python 3.12.10）：

- 专项回归（`tests/unit/test_feedback0470_snapshot_and_health.py` 11 项 + `tests/unit/test_model_queries.py` 15 项）：共 26 项全通过，覆盖真实 `model_registry.write_model` 分拆零件快照的 `surface_areas_available` 检测、pre-0.41.0 分拆记录兼容、`write_back_snapshot=True` 回写清除 `stale_fields` 且保持 `revision`/`part_sha256`/`updated_at` 不变，以及装配快照不误报 `merged_counts`。
- 全量单元与门禁：`tools/test_unit.py` 全量单测通过（详细运行摘要及受测源码指纹见发布门禁报告 `build/unit_test_report.json` 与发布后核对记录），`tools/dev_check.py --skip-unit`、`tools/test_mcp.py --offline`、`tools/test_mcp.py --offline --legacy-entry`、`tools/check_backlog_counts.py`（276 项：BUG 143、FEAT 89、DEV 44）与 `tools/check_release_records.py --version 0.48.1` 全部通过；全量 303 份活跃非冻结 Markdown 扫描 `broken_files=0`、`broken_anchors=0`。发布后远端核对见 [发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md) 和 Release 正文。

未测范围：Creo 9 / Creo 10 / Creo 12.4 实机与外部 WorkBuddy 黑盒复测（本版无原生 C++ 改动）。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.48.1.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-196 | 0.48.1 | v0.48.1 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 0.48.0 主修已验 Creo 10；0.48.1 补修分拆 `inspection_ref` 快照 `surfaces[].area_mm2` 过期检出与装配 `merged_counts` 误报，单测全过；Creo 9 / 10 / 12.4 实机与外部 WorkBuddy 复测待验。 |
| DEV-106 | 0.48.1 | v0.48.1 | 已交付 0.48.1 | 已交付 0.48.1 | 已完成（0.48.1 交付） | 完成三批台账与全量活跃非冻结文档断链整理（归档 `DEV-052`/`DEV-065`/`BUG-175`/`DEV-079`，清零 `开发中` 存量并修复 115 文件 364 处断链），随 v0.48.1 合入交付。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.48.1-source.zip`
- `MCP_CREO_MechDog-0.48.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.1-seed-library.zip`
- `MCP_CREO_MechDog-0.48.1-seed-library.zip.sha256`

种子包 SHA256 为 `1497d2d338ece74b4eaf517357228b061e0f48084e22cd3211435d841f0149e7`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.1)
