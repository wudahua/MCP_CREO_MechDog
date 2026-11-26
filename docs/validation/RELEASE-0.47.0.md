# 发布记录 v0.47.0

2026-11-26 MINOR，公开工具数 112。上一版本：0.46.1（`v0.46.1`，提交 `742b2736d209a48629eb965b0c7662fb3d42c601`）。

## 验收范围

交付 [BUG-194](../work-items/BUG-194.md)、[BUG-195](../work-items/BUG-195.md)、[FEAT-091](../work-items/FEAT-091.md) 与 [FEAT-092](../work-items/FEAT-092.md)，回应 0.45.1 外部机械臂验收反馈中的阻塞与高优先级改进项。

本机 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK 实机链路（10/10 通过）：

- `BUG-194`：`b_spline`（`4ceb4b3410884596a140c01f22b0dbdc`）与 `arc`（`84e34a8f062f45108059b5a4a1b35e29`）在 `dimensioning="auto"` 下路由至 `autodim` 并 `saved_file_reloaded_and_verified=True`；`circle`（`0c475bffa9e74d308dd9e5acaa18a541`）保留 `coordinates`；显式 `coordinates` 超差拒绝（`8a06e39bda474788a193707e3581c0d6`）含 `dimensioning='autodim'` 与 `geometry_tolerance_mm=<cap>` 自助提示。
- `BUG-195`：`bounding_box_status` 输出 `measurement_method="tessellated"`、`method_error_bound_mm=0.001`、`error_bound_direction="inward"`；空钣金件 `{kind:'plane', normal, offset}` 明确拒绝并指引 `datum_plane`（`2c46022cab9543d3a06530ca41778d68`）；`datum_plane` `axis='y'` 成功建模（`939d2fdad7db480caee0de9cc6a4bd4d`）；边选择器多边歧义报错输出 `adjacent_surfaces=` 与 `on_face:{kind:'surface',id:...}` 提示（`d34846dff8504f8eb1bb2d6f44445f58`）。
- `FEAT-091`：`sheetmetal_base_flange` 输出 `envelope_mm` 与 `u_extension_from_flip_thickness_mm=2.0`（`939d2fdad7db480caee0de9cc6a4bd4d`）；`round` 期望凹凸断言不符时拒绝并回滚、revision 不变（`6f9357b0cce34df68bf159eec1d1ad70`），匹配时提交并保存重载通过（`d848c5b4e503428cba0efc950a02982a`）。
- `FEAT-092`：`ExtrudeOp.region.closed_chain` 多轮廓区域切除精确 `5500.0 mm³` 并保存重载通过（`588d5a85c811460094d7ca4531f2cdd1`）；`creo_server_info` 只读工具单测与契约检查通过（`tool_count=112`）。

离线门禁（Windows / Python 3.12.10）：`tools/dev_check.py` 通过（`success=true`，4548 项单测通过、6 项跳过，`lint_findings=0`，`unformatted_files=0`）；`tools/test_mcp.py --offline` 通过。

未测范围：Creo 9 / Creo 12.4 实机、WorkBuddy 黑盒验收、以及基于 `0.45.1` 原始完整装配（23 实例）重跑。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.47.0.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-194 | 0.47.0 | v0.47.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | Creo 10 实机与单测通过；Creo 9 / 12.4 与 WorkBuddy 黑盒未测。 |
| BUG-195 | 0.47.0 | v0.47.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | Creo 10 实机与单测通过；Creo 9 / 12.4 与 WorkBuddy 黑盒未测。 |
| FEAT-091 | 0.47.0 | v0.47.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | Creo 10 实机与单测通过；Creo 9 / 12.4 与 WorkBuddy 黑盒未测。 |
| FEAT-092 | 0.47.0 | v0.47.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | `closed_chain` Creo 10 实机与 `creo_server_info` 离线单测通过；Creo 9 / 12.4 与 WorkBuddy 黑盒未测。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.47.0-source.zip`
- `MCP_CREO_MechDog-0.47.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.47.0-seed-library.zip`
- `MCP_CREO_MechDog-0.47.0-seed-library.zip.sha256`

种子包 SHA256 为 `1145977816e4abbfc99eff079da56491a37c9da5eb02c46bb2fb41b7c712e952`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.47.0)
