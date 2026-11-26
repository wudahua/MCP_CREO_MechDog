# 发布记录 v0.47.1

2026-11-26 PATCH，公开工具数 112。上一版本：0.47.0（`v0.47.0`，提交 `baeb3d66aa7166a874d474187fb73bfcfdf210f4`）。

## 验收范围

交付 [BUG-187](../work-items/BUG-187.md) 的默认主基准面偏移法线规范对齐与草图帧反向告警（归档 0.46.1 外部反馈原件至 [feedback-0.46.1-2026-11-26](../validation/feedback-0.46.1-2026-11-26/SOURCE_MANIFEST.json)），以及 [DEV-104](../work-items/DEV-104.md) 的开发入口统一与四批台账复核。

本机 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK 实机链路（3/3 通过）：

- 默认 XZ 偏移 `-30` + 默认字典草图（作业 `2df364a78c39444db9118890cb015a5d`，模型 `41521fc98820429f90410125ec162338`）：`datum_plane` 回执 `plane_frame.normal=[0,-1,0]`、`canonical_frame_aligned=True`、`effective_flip=True`；草图 `normal=[0,-1,0]`、`v_axis=[0,0,1]`、无 `frame_warning`；拉伸 `volume_mm3=5600.0`、包围盒 `[-20,-37,-10]–[20,-30,10]`、`saved_file_reloaded_and_verified=True`。
- 显式 `datum_plane(flip=True)` + 默认字典草图（作业 `323445719f8046ee988c9294d864c201`，模型 `71929bc22c574f058dc4ac3472117424`）：`plane_frame.normal=[0,1,0]`；草图 `normal=[0,1,0]`、`v_axis=[0,0,-1]`、触发 `frame_warning.code="frame_mismatch"`（`principal_frame="XZ"`）；拉伸 `volume_mm3=5600.0`、包围盒 `[-20,-30,-10]–[20,-23,10]`、`saved_file_reloaded_and_verified=True`。
- 显式 `datum_plane(flip=True)` + 显式 `v_axis=[0,0,1]`（作业 `d732c45a1a6349e88e104b08466b18e5`）：草图覆盖为 `normal=[0,-1,0]`、`v_axis=[0,0,1]`、无 `frame_warning`；拉伸 `volume_mm3=5600.0`、包围盒 `[-20,-37,-10]–[20,-30,10]`、`saved_file_reloaded_and_verified=True`。

离线门禁（Windows / Python 3.12.10）：`tools/test_unit.py`、`tools/dev_check.py`、`tools/test_mcp.py --offline`、`tools/test_mcp.py --offline --legacy-entry` 与 `tools/check_backlog_counts.py` 通过（`tool_count=112`、`capability_contract_verified=true`、`lint_findings=0`、`unformatted_files=0`）。发布门禁要求候选工作树全量单测通过，打包时核对本轮 `tools/test_unit.py` 报告与发布提交的源码指纹。发布后远端核对见 [发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md) 和 Release 正文。

未测范围：Creo 9 / Creo 12.4 实机与外部 WorkBuddy 黑盒复测。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.47.1.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-187 | 0.47.1 | v0.47.1 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 0.47.1 交付主基准面偏移法线默认对齐 `frames.XY/XZ/YZ`、`plane_frame` 回执与字典草图 `frame_mismatch` 告警，本机 Creo 10 三组实机与保存重载通过；Creo 9 / 12.4 与外部 WorkBuddy 黑盒复测未验。 |
| DEV-104 | 0.47.1 | v0.47.1 | 已交付 0.47.1 | 已交付 0.47.1 | 已完成（0.47.1 交付） | 开发入口统一与四批 P1/P2 台账复核随 v0.47.1 合入并转入完成档案。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.47.1-source.zip`
- `MCP_CREO_MechDog-0.47.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.47.1-seed-library.zip`
- `MCP_CREO_MechDog-0.47.1-seed-library.zip.sha256`

种子包 SHA256 为 `326eb7ac1c140fdf26205c2e17d282a326b34d2417b6bac459c53a9fde3e58d8`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.47.1)
