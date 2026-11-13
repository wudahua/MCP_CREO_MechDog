# 0.24.0 发布记录

- 版本：`0.24.0`（MINOR）
- 日期：2026-11-13
- 版本说明：[RELEASE_NOTES_0.24.0](../RELEASE_NOTES_0.24.0.md)
- 主台账：[BACKLOG](../BACKLOG.md)
- 跨版本复测：[Creo 10 交接包](../development/CREO10-RETEST-0232-2026-11-13.md)
- 受测提交：`v0.24.0` 标签指向的 `main` 提交（标签对象与提交号在[POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md) 的 `## v0.24.0` 段登记）

## 包内容对照（相对 0.23.2）

| 项 | 0.23.2 | 0.24.0 | 说明 |
| --- | --- | --- | --- |
| 公开工具 | 107 | 107 | 无增删 |
| 计划操作白名单 | 常规操作 | 常规操作 + `import_geometry` | 单操作、无 `model_id`、独立新 part |
| `surface_loft` 参数 | 无模板 | `template`（file/sha256/sections/guides） | `templates/elemtree/` 两个模板与 manifest 随源码包发行 |
| `assertions` | `volume_mm3` 等 | 增加 `bbox_mm`、`surface_area_mm2`、`surface_area_tolerance_mm2` | 计划级，保存前判定 |
| 能力表 | — | `runtime_admission=refused_before_job` | 命中内核签名时 `surface_loft` 预拒绝 |
| 种子库 | 9 个种子 | 9 个种子 | `compatible_server_version=0.24.0` |
| 单测 | 3494 | 3548 | `tools/dev_check.py` 全量通过 |

## 逐 ID 状态核对

| ID / 工作卡 | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 差异说明 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [BUG-121](../work-items/BUG-121.md) | 部分交付（只读准入与 `readonly_source` 已交付；GUI 漂移与 Creo 10 未验） | 0.24.0（子项） | GUI 保存造成的漂移、Creo 10 复跑 | 部分交付，剩余待验收 | 部分交付，剩余待验收 | 无 | 已列入 | 已列入 | `v0.24.0` |
| [BUG-122](../work-items/BUG-122.md) | 部分交付（预拒绝与能力表字段已交付；Creo 10 与"先失败后成功"序列未验） | 0.24.0（子项） | Creo 10 复跑、12.4 上先失败后成功的序列 | 部分交付，剩余待验收 | 部分交付，剩余待验收 | 无 | 已列入 | 已列入 | `v0.24.0` |
| [BUG-123](../work-items/BUG-123.md) | 部分交付（B1/B2/B3 与打包已交付；Creo 10 解析未复测） | 0.24.0（子项） | Creo 10 解析与创建后 `ProFeatureElemtreeExtract`、模板形态扩充 | 部分交付，剩余待规划 | 部分交付，剩余待规划 | 无 | 已列入 | 已列入 | `v0.24.0` |
| [BUG-124](../work-items/BUG-124.md) | 部分交付（STEP/IGES 导入与门禁删除已交付；Creo 10、纯曲面、英寸模型未验） | 0.24.0（子项） | Creo 10、纯曲面样本、英寸模型回滚确认 | 部分交付，剩余待验收 | 部分交付，剩余待验收 | 无 | 已列入 | 已列入 | `v0.24.0` |
| [FEAT-067](../work-items/FEAT-067.md) | 部分交付（bbox 与面积断言均已交付并取得两态回执；未知单位与空面路径未验） | 0.24.0（子项） | 未知单位模型、`surface_area_mm2` 空面与单面失败路径、装配 | 部分交付，剩余待验收 | 部分交付，剩余待验收 | 无 | 已列入 | 已列入 | `v0.24.0` |

## 未纳入本版

- 台账中新登记的 [DEV-088](../work-items/DEV-088.md)（开发 AI 自主取样与重建验证，文档在写）不在本版交付范围，仍为开发中。
- Creo 10 跨版本结论：本版不声称，复测步骤见交接包。

## 发布核对

本版发布四个附件（逐个列出，不使用通配）：

- `MCP_CREO_MechDog-0.24.0-source.zip`
- `MCP_CREO_MechDog-0.24.0-source.zip.sha256`（源码包摘要记录在同名 sidecar 中，一行 `<64 位 SHA256>  文件名`）
- `MCP_CREO_MechDog-0.24.0-seed-library.zip`
- `MCP_CREO_MechDog-0.24.0-seed-library.zip.sha256`（种子包摘要同样在 sidecar 中）

- 种子包 SHA256：`c6d9a77b04ac397836464f8e12455a9b796e49b1193a796b2e1d28e782cd68f1`（24 个文件、9 个种子，与 `docs/seed_package.json` 一致，重建一次摘要不变）。
- Release：<https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.24.0>
- 打包前置门禁：`tools/check_release_records.py --version 0.24.0`、`tools/package.py` 的包内记录检查与 `tools/dev_check.py`。
- 发布后核对：`python tools/check_release_assets.py --tag v0.24.0`，四附件与两个 sidecar 逐一致，结果回填本文件与 POSTCHECK。
