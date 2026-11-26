# MCP_CREO_MechDog 0.47.0 版本说明

2026-11-26 MINOR，公开工具数 112（新增只读 `creo_server_info`）。上一版本：0.46.1（`v0.46.1`，提交 `742b2736d209a48629eb965b0c7662fb3d42c601`）。

- **`auto` 求解器回归修复与自助出口提示（[BUG-194](../work-items/BUG-194.md)）**：`profile_dimensioning_choice` 在 `dimensioning="auto"` 时恢复将 `b_spline`/`arc`/`spline`/`ellipse` 路由到 `autodim`（`unsupported_coordinate_entity`），避免 Creo 自身坐标标注量化（`1e-4`–`1e-3 mm`）触发 `coordinates` 的 `1e-5 mm` 硬拒；`line`/`centerline`/`rectangle`/`polyline`/`circle` 继续默认走 `coordinates`（保留 `BUG-108` 位置保护），显式 `dimensioning="coordinates"` 仍支持精确 `b_spline` 与 `arc`。`verify_coordinate_plan` 与 `enforce_geometry_deviation` 拒绝消息新增 `dimensioning='autodim'` 与 `geometry_tolerance_mm=<cap>` 自助提示，并同步更新 `creo_capabilities` 文档。
- **包围盒误差披露、空件平面报错与边选择器歧义提示（[BUG-195](../work-items/BUG-195.md)）**：`solid_bounds.h` 在 `bounding_box_status` 中新增 `measurement_method="tessellated"`、`method_error_bound_mm=0.001` 与 `error_bound_direction="inward"`；`generic.cpp` 对无实体面（`has_solid=false`）模型使用 `{kind:'plane', normal, offset}` 给出指向 `{kind:'datum_plane', axis, offset}` / `{kind:'datum_plane', id}` 的明确报错；`geometry_selectors.cpp` 在多边歧义报错中附带各命中边的 `adjacent_surfaces` 并提示 `on_face:{kind:'surface',id:N}` 与 `ambiguity:'nearest'`。
- **`round` 期望断言与 `sheetmetal_base_flange` 包络偏移（[FEAT-091](../work-items/FEAT-091.md)）**：`RoundOp` 与 `creo_round` 新增可选 `expected_round_kind`（`"convex"`/`"concave"`）与 `expected_material_delta_sign`（`"negative"`/`"positive"`），实测不符时附带 `edge_diagnostics`（含二面角）拒绝并回滚；`sheetmetal_base_flange` 回执（含 compact）新增 `envelope_mm` 与 `u_extension_from_flip_thickness_mm`。
- **只读 `creo_server_info` 与 `region.closed_chain` 封闭链选区（[FEAT-092](../work-items/FEAT-092.md)）**：新增无锁只读工具 `creo_server_info`（返回服务名称、版本、工具数、单通道策略、单位与 `creo_root`）；`ExtrudeOp.region` 新增 `closed_chain`（`[{"geo": i, "reversed": bool}, {"spline": j, "reversed": bool}, {"entity": name, "reversed": bool}]`）并校验证据首尾闭合。
- 实机验证环境为 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK：10 项全链路实机验证全部通过（`b_spline` 与 `arc` `auto→autodim`、`coordinates` 自助提示、`circle` 保留 `coordinates`、`bounding_box_status` 误差字段、空钣金 `plane` 报错与 `datum_plane axis='y'` + `envelope_mm`、边选择器歧义 `adjacent_surfaces` 提示、`round` 期望断言不符回滚与匹配提交、`closed_chain` 区域切除，成功建模均 `saved_file_reloaded_and_verified=True`）。
- 离线门禁：`tools/dev_check.py` 全量通过（4548 项单测通过、6 项跳过、`lint_findings=0`、`unformatted_files=0`、`test_mcp.py --offline` 通过）。
- 未测范围：Creo 9 / Creo 12.4 实机、WorkBuddy 黑盒验收、以及基于 `0.45.1` 原始完整装配（23 实例）重跑。 [发布记录](../validation/RELEASE-0.47.0.md)

## 附件

- `MCP_CREO_MechDog-0.47.0-source.zip`
- `MCP_CREO_MechDog-0.47.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.47.0-seed-library.zip`
- `MCP_CREO_MechDog-0.47.0-seed-library.zip.sha256`

种子包 SHA256 为 `1145977816e4abbfc99eff079da56491a37c9da5eb02c46bb2fb41b7c712e952`。两份同名 sidecar 分别记录各自 ZIP 的摘要。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.47.0)
