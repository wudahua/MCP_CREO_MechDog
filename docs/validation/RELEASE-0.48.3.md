# 发布记录 v0.48.3

2026-11-27 PATCH，公开工具数 112。上一版本：0.48.2（`v0.48.2`，提交 `51a1c3895b9881f5d1ff6290592cc06da4edc667`）。

## 验收范围

- [DEV-108](../work-items/DEV-108.md)：修复 Windows 15.625 ms 时钟刻度内启动重试 `retry_id` 重复与 `CreoStartup._run()` 误采用旧 `state.json` 缺陷；分支 `codex/dev-108-111-closeout`（提交 `207e9289`）在托管 Windows CI [运行 46002779873](https://github.com/wudahua/MCP_CREO_MechDog/actions/runs/46002779873) 首轮通过（4,569 项，10 跳过，0 失败，0 错误）。
- [DEV-109](../work-items/DEV-109.md)：`backlog_counts.py` 按状态标题逐组比对声明计数；88/62→87/63 错组检测、零条目分组与当前台账（276 项）通过。
- [DEV-110](../work-items/DEV-110.md)：只读核实本机源码目录 `D:\my\MCP_CREO_MechDog` 与 WorkBuddy `MCP_CREO_MechDog` 加载来源，校正 `AGENTS.md` 与 `docs/DEVELOPMENT.md`。
- [DEV-111](../work-items/DEV-111.md)：`docs/BACKLOG.md` 近期动态去重；新增 `doc_links.py`/`tools/check_doc_links.py` 接入 `.github/workflows/checks.yml`，308 份活跃文档 3,098 处链接 0 断链 0 坏锚点。
- [BUG-131](../work-items/BUG-131.md)：在 Creo 10.0.0.0（`release_numeric=42`）完成 `revision == 0` 新装配收尾实机验收（`abandon_new`、`ack_failure` 与 `revision == 1` 拒绝负对照）。

本机全量单元测试、离线门禁、台账计数门禁与活跃文档链接门禁全通过。候选与主干运行的提交、环境、单测计数和源码指纹见 Release 正文与[发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md)。

未测范围：Creo 9 / 12.4 实机、外部 WorkBuddy 黑盒、[BUG-017](../work-items/BUG-017.md)（缺 Creo 9 运行时与最小输入）、[BUG-034](../work-items/BUG-034.md)（缺 Creo 9 SDK `.lib` / 许可与种子生产来源）及 [BUG-131](../work-items/BUG-131.md) 原 23 组件 `hom_1` 挂死根因（缺原装配与操作步骤）。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.48.3.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| DEV-108 | 0.48.3 | v0.48.3 | 已交付 0.48.3 | 已交付 0.48.3 | 已完成（0.48.3 交付） | 同刻度重试 ID 与旧快照隔离已通过托管 Windows CI 首轮验证。 |
| DEV-109 | 0.48.3 | v0.48.3 | 已交付 0.48.3 | 已交付 0.48.3 | 已完成（0.48.3 交付） | 台账逐组计数校验已覆盖同总数错组与零条目分组。 |
| DEV-110 | 0.48.3 | v0.48.3 | 已交付 0.48.3 | 已交付 0.48.3 | 已完成（0.48.3 交付） | 仅只读核查并校正指引，未改动其他客户端配置。 |
| DEV-111 | 0.48.3 | v0.48.3 | 已交付 0.48.3 | 已交付 0.48.3 | 已完成（0.48.3 交付） | 台账已去重；活跃非冻结文档链接/锚点检查已接入 CI。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.48.3-source.zip`
- `MCP_CREO_MechDog-0.48.3-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.3-seed-library.zip`
- `MCP_CREO_MechDog-0.48.3-seed-library.zip.sha256`

种子包 SHA256 为 `2f392cb45dcadae72bfc3a62b63ff1cadbff42a66680f05a304ed58f2fa61b4e`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.3)
