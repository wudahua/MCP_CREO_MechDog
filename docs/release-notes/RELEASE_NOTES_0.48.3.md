# MCP_CREO_MechDog 0.48.3 版本说明

2026-11-27 PATCH，公开工具数 112。上一版本：0.48.2（`v0.48.2`，提交 `51a1c3895b9881f5d1ff6290592cc06da4edc667`）。

- [DEV-108](../work-items/DEV-108.md)：修复 Windows 默认 15.625 ms 时钟刻度内启动重试 `retry_id` 偶发重复与 `CreoStartup._run()` 误采用旧 `state.json` 的缺陷，补充同刻度冻结时钟与跨进程协调回归单测。
- [DEV-109](../work-items/DEV-109.md)：扩展 `src/creo_mechdog/backlog_counts.py` 按状态标题逐组比对 `docs/BACKLOG.md` 实际行数，保留总数、类型与重复 ID 检查及 `tools/check_backlog_counts.py` 入口。
- [DEV-110](../work-items/DEV-110.md)：只读核实本机 Git 主检出目录 `D:\my\MCP_CREO_MechDog` 与 WorkBuddy `MCP_CREO_MechDog` 加载来源，校正 `AGENTS.md` 与 `docs/DEVELOPMENT.md` 指引及运行期核查方法。
- [DEV-111](../work-items/DEV-111.md)：去除 `docs/BACKLOG.md` 页首与 `## 近期动态` 的重复段落并保留全部章节与显式锚点；新增 `src/creo_mechdog/doc_links.py`、`tools/check_doc_links.py` 动态扫描活跃非冻结 Markdown 本地链接与 `#锚点`，并接入 `.github/workflows/checks.yml`。
- [BUG-131](../work-items/BUG-131.md)：在 Creo 10.0.0.0（`release_numeric=42`）完成 `revision == 0` 新装配收尾实机验收（`abandon_new`、`ack_failure` 与 `revision == 1` 拒绝负对照）。

本机全量单元测试、离线门禁、台账计数门禁与活跃文档链接门禁全通过；托管 Windows CI 已在候选分支首轮全量通过（4,569 项，10 跳过，0 失败，0 错误）。

未测范围：Creo 9 / 12.4 实机、外部 WorkBuddy 黑盒、[BUG-017](../work-items/BUG-017.md)（缺 Creo 9 运行时与最小输入）、[BUG-034](../work-items/BUG-034.md)（缺 Creo 9 SDK `.lib` / 许可与种子生产来源）及 [BUG-131](../work-items/BUG-131.md) 原 23 组件 `hom_1` 挂死根因（缺原装配与操作步骤）。 [发布记录](../validation/RELEASE-0.48.3.md)

## 附件

- `MCP_CREO_MechDog-0.48.3-source.zip`
- `MCP_CREO_MechDog-0.48.3-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.3-seed-library.zip`
- `MCP_CREO_MechDog-0.48.3-seed-library.zip.sha256`

种子包 SHA256 为 `2f392cb45dcadae72bfc3a62b63ff1cadbff42a66680f05a304ed58f2fa61b4e`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.3)
