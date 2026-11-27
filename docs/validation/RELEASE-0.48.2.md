# 发布记录 v0.48.2

2026-11-27 PATCH，公开工具数 112。上一版本：0.48.1（`v0.48.1`，提交 `b82c3beaa7df4f9e1890c4e6c258c589a046d1ef`）。

## 验收范围

[DEV-107](../work-items/DEV-107.md) Windows CI 在整个 Python 作业中启用 UTF-8，使离线检查能输出中文 JSON 并继续运行全量单测。

在修复提交 `c3d7875d` 上运行 `tools/dev_check.py`，GitHub 托管 Windows / Python 3.12 的三项离线检查通过，全量单测通过（4,557 项，10 跳过，0 失败，0 错误）。同一提交首次运行有一项启动重试 ID 断言失败，第二次运行通过。 [分支 CI 报告](https://github.com/wudahua/MCP_CREO_MechDog/actions/runs/45980797321/attempts/2)

候选与主干运行的提交、环境、单测计数和源码指纹见 Release 正文与[发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md)。

未测范围：Creo 9 / 10 / 12.4 实机和外部 WorkBuddy 黑盒。本次变更限于 Windows CI 输出编码。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.48.2.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| DEV-107 | 0.48.2 | v0.48.2 | 已交付 0.48.2 | 已交付 0.48.2 | 已完成（0.48.2 交付） | Windows CI 中文输出与全量单测已在托管 runner 验证。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.48.2-source.zip`
- `MCP_CREO_MechDog-0.48.2-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.2-seed-library.zip`
- `MCP_CREO_MechDog-0.48.2-seed-library.zip.sha256`

种子包 SHA256 为 `fdecb1c343944b276a342158deee915958293fc594f98c2befeb7bf9941eb642`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.2)
