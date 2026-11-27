# MCP_CREO_MechDog 0.48.0 版本说明

2026-11-27 MINOR，公开工具数 112。上一版本：0.47.1（`v0.47.1`，提交 `937dd2b289c28a2d77b845a23c47e7773bb92721`）。

- **历史模型快照只读回填与过期字段提示（[BUG-196](../work-items/BUG-196.md)）**：回应 0.47.0 外部反馈 §1（原件已逐字节归档至 [feedback-0.47.0-0.47.1-2026-11-26](../validation/feedback-0.47.0-0.47.1-2026-11-26/SOURCE_MANIFEST.json)）。`creo_refresh_model(model_id, write_back_snapshot=False)` 新增可选只读回填开关 `write_back_snapshot`；当 `write_back_snapshot=true` 且磁盘 `part_sha256` 未变时，将实测 `inspection`/`inspection_ref`/`inspection_summary` 写入模型控制记录快照并标明 `snapshot.source="refresh_verified"` 与 `refreshed_at`，**保持 `revision`、`part_file`、`part_sha256` 与 `updated_at` 不变**（SHA 不匹配则拒绝回写并报告 `part_sha256_mismatch_or_missing`）；`model_summary` 对仍缺 `total_surface_area_mm2`、`bounding_box_mm`、`merged_counts` 或内联 `surfaces[].area_mm2` 的历史模型快照输出 `snapshot.stale_fields` 与 `snapshot.refresh_hint`；`compact_sections.py` 将 `snapshot_write_back` 列入受保护结果键。
- **包围盒口径 `basis` 与真实 `query_code`、`compact_job` 巡检摘要、圆角/倒角示例及健康状态拆分（[BUG-197](../work-items/BUG-197.md)）**：`native/solid_bounds.h` 为 `bounding_box_status` 新增 `basis="tessellated_solid_union"`（并在实测成功或报错时输出真实整型 `query_code`，如 `0` 而非恒 `null`）；`creo_inspect_model` 文档补齐面片细分并集口径说明；`bridge.compact_job` 在 `native.inspection` 尚无有效数据时自动填入 `result.inspection = inspection_summary`，`creo_get_job.sections` 描述示例同步列出 `["operations", "inspection_summary", "preview"]`；`creo_round` 与 `creo_chamfer` 的 `references` 描述补充可复制 `tolerance_mm: 0.5` 与 `full_circle: true` 示例；`session_health` 与 `creo_session_status` 保持顶层 `status`/`reason` 兼容并拆分 `connection_health` 与 `save_verification_health` 双健康子块（`creo_session_status` 按需刷新探针）。
- **补齐 v0.47.0 / v0.47.1 发布后核对并固化 `--post-release` 门禁（[DEV-105](../work-items/DEV-105.md)）**：回应 0.47.1 外部反馈。在 `src/creo_mechdog/release_integrity.py` 新增 `validate_post_release_backfill` 并在 `tools/check_release_records.py` 新增 `--post-release` 校验；核对并回填 `v0.47.0`（Release `459454832`）与 `v0.47.1`（Release `459515636`）四件附件实算摘要至 [发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md) 与 `docs/releases/0.47.1.json`。
- **同步合入校验冷数据归档剥离（[DEV-103](../work-items/DEV-103.md)）**：本版主干合并同步带入 `codex/dev-103-offload-validation-cold-data`（提交 `bc794edd`），将 14 份大体积历史校验文件（18.40 MB）转存至归档 Release `archive-validation-2026-11`，显著缩减源码包体积，历史索引见 [COLD_DATA_INVENTORY](../validation/COLD_DATA_INVENTORY.md)。
- 实机与离线验收：Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）MCP stdio 全链路实机通过（模型 `51894e20c45d417da266764d1370289f`：拉伸作业 `9b5c6fef6eaa4c88a3cc1e0737104d60` `basis="tessellated_solid_union"`、`query_code=0`，退化旧快照后 `stale_fields=["total_surface_area_mm2", "bounding_box_mm", "surfaces[].area_mm2"]`，`creo_refresh_model(write_back_snapshot=True)` 作业 `f02aa955b1154ff6955d6a97249083f2` 回填后 `revision=3`、`part_sha256` 未变且 4 个面 `area_mm2` 全部恢复，`creo_session_status` 返回独立 `connection_health.status="connected"` 与 `save_verification_health`）。
- 未测范围：Creo 9 / Creo 12.4 实机、外部 WorkBuddy 黑盒复测及 0.39.0 原历史模型实机复验。 [发布记录](../validation/RELEASE-0.48.0.md)

## 附件

- `MCP_CREO_MechDog-0.48.0-source.zip`
- `MCP_CREO_MechDog-0.48.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.0-seed-library.zip`
- `MCP_CREO_MechDog-0.48.0-seed-library.zip.sha256`

种子包 SHA256 为 `c30953f986123190393862e211a5d6660c69b19c2369cc6855adb03b56c4ed31`。两份同名 sidecar 分别记录各自 ZIP 的摘要。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.0)
