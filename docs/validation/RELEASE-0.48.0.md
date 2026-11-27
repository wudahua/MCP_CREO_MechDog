# 发布记录 v0.48.0

2026-11-27 MINOR，公开工具数 112。上一版本：0.47.1（`v0.47.1`，提交 `937dd2b289c28a2d77b845a23c47e7773bb92721`）。

## 验收范围

交付 0.47.0 / 0.47.1 两份外部反馈原件（已逐字节归档至 [feedback-0.47.0-0.47.1-2026-11-26](../validation/feedback-0.47.0-0.47.1-2026-11-26/SOURCE_MANIFEST.json)）对应的 [BUG-196](../work-items/BUG-196.md)、[BUG-197](../work-items/BUG-197.md) 与 [DEV-105](../work-items/DEV-105.md)，并随分支合并同步合入 [DEV-103](../work-items/DEV-103.md) 校验冷数据归档剥离（提交 `bc794edd`，将 14 份共 18.40 MB 的大体积历史校验文件转存至归档 Release `archive-validation-2026-11`）。

本机 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK MCP stdio 实机链路通过：

- 会话健康与状态拆分（`creo_session_status`）：`connected=true`，`session_health.connection_health.status="connected"`（`toolkit_code=0`），`session_health.save_verification_health={"status": "no_failure_observed", "reason": "recent_verified_save"}`。
- 原生拉伸、离散包围盒口径与 compact 摘要（模型 `51894e20c45d417da266764d1370289f`，作业 `75d3ab58db244fe4a47bf5157627502c`、`726b8b89c04f409baff803606e11aca6`、`9b5c6fef6eaa4c88a3cc1e0737104d60`，`revision=3`，`part_sha256=4b4aba80b13543c476142bd3e2153d8d5482b4cac5d15a2c35a9997c00b7e3d6`）：`saved_file_reloaded_and_verified=true`，`bounding_box_status.state="measured"`、`basis="tessellated_solid_union"`、`query_code=0`、`method_error_bound_mm=0.001`；`creo_get_job(compact)` 自动填充 `result.inspection.total_surface_area_mm2=904.7786842338605`，`sections=["inspection_summary"]` 完整输出摘要。
- 历史快照退化检测与只读无版本破坏回填：将临时模型 `model.json` 退化为 pre-0.41.0 结构后，`creo_inspect_model(compact)` 输出 `snapshot.stale_fields=["total_surface_area_mm2", "bounding_box_mm", "surfaces[].area_mm2"]` 与 `refresh_hint`；调用 `creo_refresh_model(..., write_back_snapshot=True)`（作业 `f02aa955b1154ff6955d6a97249083f2`）返回 `snapshot_write_back.applied=true`，回填后 `revision` 保持 `3` 且 `part_sha256` 不变，`snapshot.source="refresh_verified"`、`stale_fields` 清除，`total_surface_area_mm2=904.7786842338605` 与 4 个面 `area_mm2`（`201.0619`/`201.0619`/`251.3274`/`251.3274`）均可从控制快照与 `section="surfaces"` 分页直接读出。

离线门禁（Windows / Python 3.12.10）：`tools/test_unit.py` 全量单测通过（4,563 项，0 失败、0 错误、6 跳过，详细运行摘要及受测源码指纹见发布门禁报告 `build/unit_test_report.json`），`tools/dev_check.py --skip-unit`、`tools/test_mcp.py --offline`、`tools/test_mcp.py --offline --legacy-entry`、`tools/check_backlog_counts.py`、`tools/check_release_records.py --version 0.48.0` 及 `0.47.0`/`0.47.1` `--post-release` 全部通过。发布后远端核对见 [发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md) 和 Release 正文。

未测范围：Creo 9 / Creo 12.4 实机、外部 WorkBuddy 黑盒复测及 0.39.0 原历史模型实机复验。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.48.0.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-196 | 0.48.0 | v0.48.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 交付 `creo_refresh_model(write_back_snapshot=True)` 只读快照回写与 `model_summary` `stale_fields`/`refresh_hint`，本机 Creo 10 退化快照复测与单测全过；Creo 9 / 12.4、外部 WorkBuddy 与 0.39.0 原模型未测。 |
| BUG-197 | 0.48.0 | v0.48.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 交付 `bounding_box_status` `basis`/`query_code`、`compact_job` 巡检摘要、`round`/`chamfer` 示例与 `session_health` 连接/保存双子块，本机 Creo 10 实机与单测全过；Creo 9 / 12.4 与外部 WorkBuddy 未测。 |
| DEV-105 | 0.48.0 | v0.48.0 | 已交付 0.48.0 | 已交付 0.48.0 | 已完成（0.48.0 交付） | 补齐 `v0.47.0`/`v0.47.1` 发布后核对实证，固化 `check_release_records.py --post-release` 门禁与单测并转入完成档案；随 v0.48.0 发布同步回填。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.48.0-source.zip`
- `MCP_CREO_MechDog-0.48.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.0-seed-library.zip`
- `MCP_CREO_MechDog-0.48.0-seed-library.zip.sha256`

种子包 SHA256 为 `c30953f986123190393862e211a5d6660c69b19c2369cc6855adb03b56c4ed31`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.0)
