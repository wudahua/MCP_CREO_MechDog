# FEAT-067：计划级包围盒与总面积断言（mm），为曲面任务提供可复算验收

## 当前摘要（2026-11-13）

分类：**部分交付，剩余待验收**。类型：功能/验收。优先级：P2。目标版本：0.24.0（子项）；剩余未排期。

交付范围：`bbox_mm` 与 `surface_area_mm2` 均已交付，两者都有 12.4 实机通过与失败两态回执；剩余未验的是未知单位模型与装配场景。

来源：`C:\Users\Administrator\Downloads\反馈包-球鼻艏-20261112` 主报告第 13.2 节：球鼻艏可用 `X∈[6409.4736, 7809.4736]`、`Y∈[0, 181.325]`、`Z∈[-660, -460]`（容差 1e-3 mm）作为自动断言，无需主观判断。现有 `Assertions` 只有 `require_solid`/`volume_mm3`/`geometry_deviation`。

## 已交付

- `src/creo_mechdog/schema.py`：新增 `AssertionBbox`（`min`/`max` 各三个有限坐标，`tolerance_mm` 默认 1e-3 且必须为正，`min≤max` 逐轴校验）与 `Assertions.bbox_mm`。
- `native/generic.cpp`：新增 `measured_bbox_mm(state)`，用 inspection 已经记录的**每实体 `bbox`** 求并集，再按 `length_scale_to_mm` 换算为 mm；长度单位不可换算时不产出数值。`verify_assertions` 在 `require_solid` 之后逐轴比较，失败消息给出轴、实测区间、期望区间与容差，沿用既有"末次操作后、保存前判定，失败回滚"路径。
- `tests/unit/test_bbox_assertion.py` 10 项：schema 正负例、默认容差、`bbox_mm` 不进原生请求当未指定、原生源码契约（用记录实体框、未知单位失败、门禁在保存阶段之前）。

- `src/creo_mechdog/schema.py`：`Assertions.surface_area_mm2`（有限非负）与 `surface_area_tolerance_mm2`（默认 0.01 mm²，必须有限正数）；布尔与文本一律拒绝。
- `native/generic.cpp`：新增 `total_surface_area_native()`（`ProSolidSurfaceVisit` 逐面调 `surface_area_native` 求和，回调传 `nullptr` 过滤器；任一面测不出、遍历失败或空模型都不产出数值）与 `measured_surface_area_mm2(state)`（按 `scale.scale * scale.scale` 换算 mm²，非 part/未知单位直接不可用）；`verify_assertions` 在 bbox 之后按绝对容差比较 mm²，失败消息给出实测、期望与容差。
- `tests/unit/test_surface_area_assertion.py` 13 项：schema 正负例（含 0、NaN/Inf、布尔、文本、负值、容差）、未指定时不进原生请求、原生源码契约（逐面遍历、平方换算、失败不冒充零、装配拒绝、门禁在保存前）。

## 未交付

- 无。`surface_area_mm2` 于 2026-11-13 补齐（离线实现与单测）。

## 验证

- `bridge.py build` exit 0（原生编译通过，`build\creo_worker.exe` 已重编）。
- `tests/unit/test_bbox_assertion.py` 10 项、`tests/unit/test_surface_area_assertion.py` 13 项通过；`tools/dev_check.py --work-item FEAT-067` 全量 3548 项通过（`success: true`，风格门禁 0 回归）。
- Creo 12.4 实机（2026-11-13，`build/live_acceptance_20261113T150422/report.json`，`release_numeric=44`）：40×40×10 实体作业 `841d50bb8ea54135bb2106cb80a61c4c` 通过 `bbox_mm` 断言；同一模型再叠一块后仍用原期望，作业 `99e8a458cab3424ebb5d920a026f7841` 失败并原样报 `Bounding box assertion failed on Z: measured [0.000000, 15.000000] expected [0.000000, 10.000000] tolerance 0.001000 mm`，模型 revision 保持 1（回滚未改模型）。
- 同日另一轮 `build/live_acceptance_20261113T145133/report.json`（通过 `42311f20b593462981e84be681421c78`、失败 `a0b25c7a6bc64d42826dbc4406a1b0d4`）结论相同，两轮共 20 项检查全 PASS。
- 面积两态（`build/live_acceptance_20261113T160310/report.json`，14 项检查全 PASS）：40×40×10 方块作业 `c7c20fd3544b453fb8731900b8fb68c3` 以 4800 mm² 断言通过（模型 `5344029b3e624c318ee69acc6c26f363`，revision 1）；同一模型再叠一块后仍用 4800，作业 `a759523eac444d4eb9914c0d8aa186fc` 失败并报 `Surface area assertion failed: measured 5600.000000 mm2 expected 4800.000000 mm2 tolerance 0.500000 mm2`，模型 revision 保持 1。
- 5600 = 顶/底各 1600 + 四周各 600，说明逐面求和取的是实体外表面，两段叠合处的内部面没有被重复计入；`ProSolidSurfaceVisit` 传 `nullptr` 过滤器的用法在实机上成立。

## 未验证

- 未知单位（非 mm）模型上的 `bbox_mm` 与 `surface_area_mm2` 未验。
- 空面模型与"某一面测不出"的失败路径只有源码契约，实机未构造。
- 非毫米模型（英寸/未知单位）在断言下的失败文本。
- 装配模型（当前只取 part 的实体框；装配计划应避免使用该断言，未在 schema 层拦截）。

## 用法

```json
{"assertions": {"bbox_mm": {"min": [6409.4736, 0.0, -660.0],
                            "max": [7809.4736, 181.325, -460.0],
                            "tolerance_mm": 0.001},
                "surface_area_mm2": 4800.0,
                "surface_area_tolerance_mm2": 0.5}}
```

`surface_area_mm2` 是整块实体的总面积（40×40×10 的方块为 4800 mm²），不是某个 quilt 的面积；容差是绝对 mm²。
