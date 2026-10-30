# FEAT-051：round / chamfer / draft 的结果可观测性（体积差、方向与引用应用证据）

日期：2026-10-30（Asia/Shanghai）。类型：功能。优先级：P2。状态：待规划。目标版本：未排期。

来源与关联：外部反馈 [0.8.5 细节特征报告](../validation/feedback-0.8.x-2026-10-30/20261030_CREO_v0.8.5_细节特征无体积回报_拔模方向只能靠体积反查.md) 全篇。关联 [DEV-052](DEV-052.md) 的 N04 任务；与 [FEAT-035](FEAT-035.md)（沉孔/沉头参数与几何）、[FEAT-034](FEAT-034.md)（T02 严格判定口径）、[BACKLOG](../BACKLOG.md) 的 BUG-018 行（逐操作结果契约）、[FEAT-014](FEAT-014.md)（钣金方向语义）相关但不同条目。

分类依据：新结果契约的范围与字段尚未冻结；按模板「输入、规则或预期仍不清楚」填「待规划」。**不填「已实现」或「已修复」**——外部报告只观察到「没有回报」，本仓库未复现，也未定义契约。

## 问题或目标

**外部观察（2026-10-30，反馈环境 Creo Parametric 10.0.0.0 / release_numeric 42 / mmns 模板 / MCP 0.8.5）**：

`creo_extrude` 的 cut 会回报 `material_removed_mm3`，可以逐刀对账；但 `round` / `chamfer` / `draft` 三个操作成功时**只回报 `succeeded: true`，不带任何体积增减量**。

报告方给出一个可复跑的三步例子（模型 `part2_rocker`，圆凸台柱面 `surface id=633`，中性面 `surface id=627`，TXT 要求 11° 内拔模，正确应去除约 15.42 mm³）：

| 步骤 | 入参 | 操作回报 | 实测体积变化 |
| --- | --- | --- | --- |
| 1 | `flip: false` | `succeeded: true`，无任何体积字段 | 3895.580255 → 3913.143937，**+17.564（加料，错）** |
| 2 | `feature_state delete d11_boss` | `applied: 1, tombstone_count: 1` | 回到 3895.580255 |
| 3 | `flip: true` | `succeeded: true`，无任何体积字段 | 3895.580255 → 3880.174229，−15.406（正确，解析 −15.416） |

两次调用**都返回 succeeded**，差别只有体积符号。若不做前后体积比对，第 1 步会被当成成功写入并保存——**拔模方向取反会静默加料并照样报成功**。

**建议（报告方提出，尚未定案）**

1. 给 `round` / `chamfer` / `draft` 也回报体积增减量，与 extrude 对齐，例如 `material_delta_mm3`（带符号）或 `material_removed_mm3` / `material_added_mm3`。这是唯一能让调用方自证「这一刀方向对不对」的证据。
2. `draft` 的方向语义需要显式化：当前 `neutral_plane` + `flip` + 可选 `pull_direction` 三者共同决定锥度方向，`pull_direction` 允许为 `null`，调用前无法预知符号。建议在返回结果里带上实际解析出的 pull 方向向量与锥度符号（外扩/内收），或在 `flip` 省略且 `pull_direction` 为 null 时把「方向未确定」作为 caveat 明确写出。
3. `chamfer` / `round` 建议回报命中的边/面数。报告方一次提交 3 组 face-pair 只回 `succeeded: true`，无法确认 3 组是否都命中（事后靠 `edges` 计数 159→169 反推）。

**本仓库现状（2026-10-30 静态核对）**：`material_removed_mm3` 目前只出现在 `native/generic.cpp` 的拉伸/旋转路径（`generic.cpp:2066`、`generic.cpp:2277`），round / chamfer / draft 路径确实没有等价字段；`creo_round`（`server.py:1171`）、`creo_chamfer`（`server.py:1199`）、`creo_draft`（`server.py:1442`）均为**独立公开工具**（`references` 为集合列表，入参 `radius`/`distance` 单位 mm）。因此外部观察在当前源码上**方向上成立**，但本轮**未实机复现**，也未测量过 `flip` 取反的实际体积符号。

**目标**：让调用方能区分**实测材料变化**、**实际方向/引用证据**和**未知结果**——成功不被误读成符合所有设计意图，回滚不被报告为已提交。

## 范围

**包含**

- 建议的结果契约（**实施前须与既有投影核对后冻结**）：原生在相应 `result.operations[]` 增加 `volume_before_mm3`、`volume_after_mm3`、`material_delta_mm3 = after - before`；`material_measurement{status, before_query_code, after_query_code}`，`status` 取 `measured` / `unknown` / `not_applicable`，未知值为 `null`。
- `draft_geometry`：记录实际引用 / flip / 角度 / 方向及 source / query_code，不能回读的字段为 `null`；多面拔模**不强塞**一个无法成立的全局「内收/外扩」。
- `reference_application`：分开 `requested_set_count` 与可由原生树证实的 `applied_set_count` / source / query_code。
- 真实原生块透传、缺查询保持 `null`、每操作一条结果、后续失败时先前变化标 `rolled_back`、`not_executed` 无伪造读数；compact/full 透传一致，公共响应保持 32 KiB 与有界投影规则。

**不包含**

- 输入不变、默认材料方向不变；旧 `material_removed_mm3` 字段不改义。
- 不在原生操作边界每操作额外做两次全模型 inspection；优先复用已有检查。
- 全模型边数差**不能冒充**命中数；输入数量不等于应用数量；无法取得应用数时明确未知。
- 若提出 `expected_material_effect` 等新输入，另交方案，不夹带实施。
- 本卡为 N04 的离线实现 + SDK 构建 + 定向证据；实机阶段另需用户点名并确认当前会话条件。

## 验收标准

| 环境 / 用例 | 命令或操作 | 可判断的预期结果 |
| --- | --- | --- |
| Windows / Python | `python -m unittest tests.unit.test_detail_feature_observation tests.unit.test_t02_operation_results -v` | 真实原生块透传；缺查询保持 `null`；每操作一条结果；批中途失败时先前变化标 `rolled_back`、`not_executed` 无读数；公共响应预算保持 |
| Windows / 匹配 SDK | `python bridge.py build` | 编译 exit 0；执行器重建 |
| 本机 Creo 12.4 / 匹配 SDK | `python tools\test_detail_feature_observation.py --live --confirm-session-usable` | 凸/凹圆角、三组 face-pair 倒角、draft flip 双向、缺省/显式 pull、批中途失败的夹具逐例通过；单位覆盖 mm/in/混合与未知；差值与独立几何预期一致；零差值如合法就报告零，不新增无依据拒绝 |

按当前项目规则，不要求 Creo 10 独立复测或双版本验收作为完成门槛；其他环境收到具体反馈后再跟进，证据始终标明实际环境。禁止只写「能运行」或引用历史成功数代替本次验收。

## 实现与证据

**2026-10-30（登记，仅静态核对，未实现）**

本轮为 N00 文档阶段：依据外部 0.8.5 报告登记本卡，并只读核对当前源码——`material_removed_mm3` 仅存在于拉伸/旋转路径；`creo_round` / `creo_chamfer` / `creo_draft` 已是独立公开工具（报告方在同一份报告的「附带更正」中亦更正了早前一轮「只在 plan 通道」的说法，与本仓库一致）。未编译、未运行单元测试、未连接 Creo、未改任何生产代码。

未验证范围：外部报告的「只回 succeeded、无体积字段」**未在本机实机复现**；`flip` 取反导致的 +17.564 mm³ 加料**未实测**；11° 拔模的解析值 −15.416 mm³ 为报告方计算，本机未独立复算。契约字段名与状态取值**尚未冻结**。证据：见 [归档 MAPPING](../validation/feedback-0.8.x-2026-10-30/MAPPING.md) 与 [manifest](../validation/feedback-0.8.x-2026-10-30/manifest.json)。

下一步：按 N04 指派执行离线实现与 SDK 构建；契约字段先与既有投影核对再冻结，实机阶段另需用户点名。
