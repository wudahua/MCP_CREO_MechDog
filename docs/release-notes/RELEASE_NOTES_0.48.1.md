# MCP_CREO_MechDog 0.48.1 版本说明

2026-11-27 PATCH，公开工具数 112。上一版本：0.48.0（`v0.48.0`，提交 `b9d11b85ccfcba1247e37deb43ce887b954a6d50`）。

- **补修分拆快照 `surfaces[].area_mm2` 过期检出与装配体 `merged_counts` 误报（[BUG-196](../work-items/BUG-196.md)）**：复核 0.47.0 外部反馈原件（已在 0.48.0 归档于 [feedback-0.47.0-0.47.1-2026-11-26](../validation/feedback-0.47.0-0.47.1-2026-11-26/SOURCE_MANIFEST.json)）后补齐两处仅靠分拆控制记录暴露的边界：
  1. 真实持久化零件经 `model_registry.write_model` 分拆后，`model.json` 仅保留 `inspection_ref` 与 `inspection_summary`（无内联 `inspection.surfaces`）。`inspection_summary()` 新增 `surface_areas_available` 标记（全部 `surfaces[]` 均含 `area_mm2` 时为 `true`）；`model_summary()` 在非装配且无内联 `surfaces` 时，若 `surface_areas_available is False` 或历史分拆快照缺失该标记且 `counts.surfaces > 0`、`total_surface_area_mm2 is None`，同样将 `surfaces[].area_mm2` 列入 `snapshot.stale_fields`，执行 `creo_refresh_model(..., write_back_snapshot=True)` 回写后自动清除。
  2. 装配体（`model_type == "assembly"`）不生成零件级 `merged_counts`，`model_summary()` 不再将装配缺失 `merged_counts` 误判为 `stale_fields`。
- **台账复核与全量活跃文档断链治理（[DEV-106](../work-items/DEV-106.md)）**：完成三批台账与活跃文档治理——复核部分交付待验组 23 张 P1（归档 `DEV-052`/`DEV-065`、2 项转待规划）、复核待验收组 51 项 P1（按 0.47.1 外部两轮 60/60 复测归档 `BUG-175` 并收窄 4 项余项）、清零 `开发中` 存量 10 项（归档 `DEV-079`、重分类 8 项并校正 `DEV-091`），并修复全量 115 份活跃非冻结文档的 364 处迁移断链（303 份活跃非冻结 Markdown 扫描 `broken_files=0`、`broken_anchors=0`）。
- 离线验收：Windows x64 / Python 3.12.10 运行 `tools/test_unit.py` 全量单测、`tools/dev_check.py --skip-unit`、`tools/test_mcp.py --offline` / `--legacy-entry`、`tools/check_backlog_counts.py`（276 项一致）与 `tools/check_release_records.py --version 0.48.1` 全通过。
- 未测范围：Creo 9 / Creo 10 / Creo 12.4 实机与外部 WorkBuddy 黑盒复测（本版未改动原生 C++ 代码）。 [发布记录](../validation/RELEASE-0.48.1.md)

## 附件

- `MCP_CREO_MechDog-0.48.1-source.zip`
- `MCP_CREO_MechDog-0.48.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.1-seed-library.zip`
- `MCP_CREO_MechDog-0.48.1-seed-library.zip.sha256`

种子包 SHA256 为 `1497d2d338ece74b4eaf517357228b061e0f48084e22cd3211435d841f0149e7`。两份同名 sidecar 分别记录各自 ZIP 的摘要。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.1)
