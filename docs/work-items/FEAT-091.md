# FEAT-091：`round` 期望凹凸/加减料断言与 `sheetmetal_base_flange` 包络偏移回执

类型：功能。优先级：P3。

分类：**已有修复但待验收**。0.47.0 交付 `round` 期望断言与 `sheetmetal_base_flange` 包络偏移回执；Creo 10 实机与 4548 项单测通过。 [发布记录](../validation/RELEASE-0.47.0.md)

## 来源与现象

2026-11-26 外部 0.45.1 / Creo 10.0.0.0 反馈 §5、§7.1、§14.6：

1. **§7.1**：`round` 在凹边上会加料（`round_kind="concave"`、`material_delta_mm3 > 0`），但缺少类似 `expected_width_direction_world` 的事前断言，误选边时静默提交。
2. **§5**：`sheetmetal_base_flange` + `flip_thickness=true` 会沿草图 u 轴产生 `thickness` 包络偏移，回执已有 `envelope` 对象但缺少紧凑列表形式 `envelope_mm` 与 `u_offset_from_fraction_mm`。

## 范围与验收

1. `RoundOp` 与 `creo_round` 增加可选 `expected_round_kind`（`"convex"`/`"concave"`）与 `expected_material_delta_sign`（`"negative"`/`"positive"`），在 `native/generic.cpp` 对照实测 `round_kind` 与 `material_delta_mm3`，不符时附带 `edge_diagnostics`（含二面角）并抛错回滚。
2. `native/base_flange.cpp` 回执新增 `envelope_mm: {u: [min, max], v: [min, max], n: [min, max]}` 与 `u_offset_from_fraction_mm`。
3. 补充 schema/单元测试，编译原生执行器并在 Creo 10 实机验证正反断言回滚与 `base_flange` 包络字段。
