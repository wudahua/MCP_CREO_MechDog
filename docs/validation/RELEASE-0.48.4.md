# 发布记录 v0.48.4

2026-11-28 PATCH，公开工具数 112。上一版本：0.48.3（`v0.48.3`，提交 `718b477f0bd1c54f32989eda57085db7df9144e4`）。

## 验收范围

[DEV-112](../work-items/DEV-112.md) 的文档提交为 `8d2012b9`。开发阶段检查了 3,137 个本地链接、276 个活跃 ID 和 58 项专项回归。受测文档指纹见工作卡。

制作源码包的条件是本轮全量单测通过，打包时核验报告、运行 ID 及提交对应的源码指纹。另执行 `tools/dev_check.py`、链接与计数检查，并在源码 ZIP 解包后独立运行单测。最终受测提交、命令、运行标识及结果见 Release 正文和[发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md)。

本版改动为文档与版本元数据。验收环境为 Windows x64 / Python 3.12.10。未运行 Creo 9、10、12.4 实机建模或外部 WorkBuddy 黑盒。 与直接前版对照，`native/`、第三方许可、原生回调源码及种子 PRT 均沿用前版；本版未重编 worker 或回调 DLL。

## 逐 ID 状态核对

[完成档案](../BACKLOG_COMPLETED.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.48.4.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| DEV-112 | 0.48.4 | v0.48.4 | 已交付 0.48.4 | 已交付 0.48.4 | 已完成（0.48.4 交付） | 文档优化完成，原有建模条目的剩余范围保留。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.48.4-source.zip`
- `MCP_CREO_MechDog-0.48.4-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.4-seed-library.zip`
- `MCP_CREO_MechDog-0.48.4-seed-library.zip.sha256`

种子包 SHA256 为 `7607128038de9ce304f12ecb7196bcf8f47580ab5d0c93290e0f65d7d5373220`。源码包和种子包的摘要分别记录在同名 sidecar。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.4)
