# 2026-11-11 FEAT-065 M3/M4：曲面放样输入放开与边界相切（计划与分派）

关联：[FEAT-065 工作卡](../../work-items/FEAT-065.md) · [统一台账](../../BACKLOG.md) · [G5 原生契约](../../development/G5-NATIVE-CONTRACT.md) · [AGENTS.md](../../../AGENTS.md)

基线：`main` 提交 `ea753be`（0.21.1，公开工具 107，台账 177 / BUG 77 / FEAT 62 / DEV 38）。开发分支 `codex/FEAT-065-m3-m4-surface-loft`，首个提交 `1661809` 只加 `CLAUDE.md`。

## 0. 性质与红线

- 2026-11-11 用户确认：本轮范围为 T0、T1、T2（构线工具与 `quilt_merge` 增强留到下一轮）；只在开发分支提交，不合 `main`、不发版。
- **本轮未获实机授权。** 不运行 `bridge.py build`（它会产出或替换 `build/creo_worker.exe`，AGENTS.md 把「编译执行器」列在实机放行范围内），不建立 Toolkit 连接，不启动或结束 Creo，不跑任何 `--live` 驱动。允许的操作：schema 与单测、`tools/dev_check.py`、离线驱动，以及不产出执行器的语法检查（输出只写 `.tmp/`）。
- 子 agent 不提交、不改 `docs/validation/`（逐字节冻结）、不清锁或 unknown 保护。提交由主会话审查后完成。

## 1. 目标

用户反馈的三个场景（[0.19.3 球鼻艏](../../validation/feedback-0.19.3-2026-11-10/MAPPING.md)、[0.3.5 五爪瓶底](../../work-items/FEAT-039.md)、[0.10.0 风扇叶片链](../../validation/feedback-0.10.0-2026-11-01/MAPPING.md)）卡在两点：边界混合只认 MCP 自建的平面草图；边界不能和相邻曲面相切。

- **M3**：`surface_loft` 的 `sections`/`guides` 在草图之外，再接受已有曲线、边，以及作为收敛端的点。离线驱动加入 YZ 截面沿 X 排列的用例。
- **M4**：边界相切条件。`Probbl.h` 对 `PRO_E_BNBLN_TAN_COND_TYPE` 只写了有效值 `TAN_COND_FREE`，而且没有可解析的符号定义，所以这是未文档化路线。本轮先做离线候选并保持门禁，再用参照件读回真实整数值，之后才决定是否发布。

## 2. 任务表

状态取值：`待执行` / `执行中` / `完成` / `需用户当次确认`。

| 任务 | 负责 | 依赖 | 状态 | 交付 / 验收 |
| --- | --- | --- | --- | --- |
| T0 文档对账 | 子 agent「文档对账」 | 无 | 完成（`5ba2cf5`） | 见 §3。`tools/check_backlog_counts.py` exit 0，分类表与各分节行数一致 |
| T1 M3 离线实现 | 子 agent「M3 实现」 | 无 | 完成（`b0a0bfa`） | 见 §4。定向单测通过、离线驱动 PASS、Ruff 无新增诊断 |
| T1b quilt 开放边 ID 通道 | 子 agent「开放边清单」 | T1 | 执行中 | `creo_measure_surface_group` 回执加有上限的开放边清单（ID、所属面与 quilt、长度、端点）；驱动 (a) 改用该通道取边 |
| T2a M4 离线候选 | 子 agent「M4 候选」 | T1 | 执行中 | 见 §5。门禁关闭状态下提交前拒绝；候选代码与取证输出就绪 |
| T2b M4 参照树取证 | 主会话 + 用户 | T2a；用户在 Creo 界面建参照件 | 需用户当次确认 | 见 §6 |
| T3 实机验收 | 主会话 | T1（M4 另需 T2b） | 需用户当次确认 | `tools/test_surface_loft_inputs.py --live --confirm-session-usable` 全 PASS，保存重载 verified |
| T4 收尾 | 主会话 | T0、T1、T2a | 待执行 | 全量 `tools/dev_check.py --work-item FEAT-065` success；工作卡与台账回填；分支提交 |

T0 与 T1 改的文件互不重叠，可以并行。T2a 与 T1 改同一批文件（`surface_ops.py`、`surface_loft.cpp`），必须等 T1 完成。

## 3. T0 文档对账（只改文档）

逐项核对并修正，每条保留日期，不改写历史段落：

1. `docs/BACKLOG.md`：「使用与计数」分类表与各分节实际行数不一致（例如「部分交付，剩余待规划」声明的数量与该节行数不同，FEAT-033 的状态与所在分节不符）。把行移到与其「当前状态」一致的分节，保证分类表各数之和等于 177，且逐类与分节行数一致。第 282 行之后仍写「驱动中 3 截面用例发布前未复跑」等已关闭事项的，按 0.21.1 的事实更正。FEAT-065 行由主会话维护，T0 不改。
2. `docs/work-items/FEAT-009.md` 首页和 BACKLOG 的 FEAT-009 行：「≥3 截面、smooth 不公开」已被 FEAT-065 M1/M2（0.21.0）取代，改成当前事实并链接 FEAT-065。
3. `docs/work-items/FEAT-055.md` 第 3、13 行附近：「`surface_loft` 没有公开工具」已过时（0.18.3 起公开）。
4. `docs/COMPATIBILITY.md`：「当前已发布 0.19.0」等版本口径更新到 0.21.1，补 `surface_loft` 多截面/导线的已测与未测范围（Creo 12.4 已测，Creo 9/10 未测）。
5. 报告中列出发现但没有修改的其它过时描述，交给主会话决定。

## 4. T1 M3 设计约束

- **向后兼容**：`sections`/`guides` 的元素由 `str | int`（草图标签或特征 ID）扩为 `str | int | 引用对象`；字符串和整数仍然表示草图，旧计划行为不变。
- **新引用对象**：
  - `{kind:'curve', id:N}`：任意曲线几何 ID，例如 `project_curve` 回执的 `curve_id`。
  - `{kind:'edge', id:N}`：曲面或实体的边。
  - 收敛端：只有 `sections` 的第一项或最后一项可以是点（`{kind:'point', id:N}`，或仓库已有的基准点特征引用形式）。点在链容器里的写法 SDK 没有文档，作为实验项，在回执和能力文案中单独标注。
  - 引用语法先查 `src/creo_mechdog/references.py` 和 `docs/REFERENCE_SYNTAX.md` 的既有约定，不要新造写法。
- **原生**：复用 `generic.cpp` 已有的 `curve_collection` 与选择解析；`surface_loft_curves()` 只负责草图来源，新来源走独立解析函数。每个引用解析失败都给出结构化拒绝：第几个、什么类型、改用什么。
- **回执**：增加每个截面/导线的来源类型与实际使用的曲线/边 ID（字段名与 `section_curve_ids`/`guide_curve_ids` 风格一致），并在 `job_projection.py` 和 `operation_results.py` 中纳入投影；需要保护的标量按 BUG-118 的方式进入保护集合。
- **公开面**：同步 `server.py` 中 `creo_surface_loft` 的签名与文档字符串、`capabilities.py` 的 `surface_loft` limits、`references.py` 与 `docs/REFERENCE_SYNTAX.md`。新形态在 T3 之前一律写成「Creo 12.4 实机未验收」，不得写成已支持。
- **任意正交平面**：先不改代码，只在离线驱动里加入 YZ 截面沿 X 排列的计划，交给 T3 实测。
- **测试**：
  - 单测 `tests/unit/test_surface_loft_inputs.py`：新引用形态的接受与拒绝、旧形态不变、点只能出现在首末、点不能出现在导线中、重复引用拒绝、回执投影字段。
  - 驱动 `tools/test_surface_loft_inputs.py`：默认离线；`--live --confirm-session-usable` 时依次执行：
    - (a) 四边补面：两张拉伸曲面的边作为截面，加两条草图导线；用 `creo_measure_surface_group` 量 gap 与开放边。
    - (b) 用 `project_curve` 的曲线作为截面。
    - (c) 球鼻艏简化版：3 个 YZ 椭圆截面沿 X 排列，加一个收敛点。
    - (d) 负例：不存在的边 ID、点出现在中间位置。
  - 写法参照 `tools/test_surface_loft_guides.py`。T1 只跑离线部分。

## 5. T2a M4 离线候选

- 新增可选字段，表达「某条边界与相邻曲面的连续条件」。字段名由实现者按现有命名风格确定，并在报告中说明。条件取值为 `free | tangent | curvature | normal`。首版只允许用在来源为 `edge` 的首、末截面或首、末导线上，相邻面取该边所属的曲面。
- 路线：先建 INCOMPLETE 骨架 → `ProFeatureElemtreeExtract` → 改写 `PRO_E_BNBLN_TAN_COND_TYPE` 和 `PRO_E_BNBLN_CONNECT_SURF_CHAIN` → `ProFeatureWithoptionsRedefine`。不得在创建前写这些元素：2026-11-01 的探针证明那样会导致 UNREGENERATED。
- 「条件 → 整数」映射表在 T2b 取证前留空，原生只在映射存在时写入；同时 `capabilities.py` 把这个字段登记为不可用，提交前就拒绝，写法参照 `UNAVAILABLE_OPERATIONS`。
- 取证输出：回执里带回提取后 `PRO_E_BNBLN_TAN_COND` 子树的样本（复用 `loft_tree_json`），供 T2b 对照。
- 单测：门禁拒绝、只允许 edge 来源、取值校验、映射为空时原生不写值的静态契约。
- 实机验收标准（T3）：用 `creo_measure_surface_curvature` 在共享边上测得 `g1_max_angle_deg < 0.5` 且 `within_g1=true`，保存重载 verified。

## 6. T2b 参照树取证（需要用户配合）

1. 用户在 Creo 12.4 界面里建一个 mm 单位零件：两张相邻曲面，再做一个边界混合，一侧边界设「相切」，另一侧设「曲率」，保存为 `.prt`。
2. 用户当次确认实机后，主会话运行 `tools/read_reference_tree.py <file.prt> --json <out.json>`，读回 `TAN_COND_TYPE` 的实际整数值和 `CONNECT_SURF_CHAIN` 的结构，回填 G5 契约与 T2a 的映射表。
3. 如果读不回来，或者 redefine 不接受这些值：记录反证，M4 保持门禁，FEAT-065 的 M4 记为「实机反证，不发布」。

## 7. 子 agent 共同规则

- 用中文报告。只改自己任务范围内的文件。T1 和 T2a 不改 `docs/BACKLOG.md`、`docs/COMPATIBILITY.md`、`FEAT-009.md`、`FEAT-055.md`；T0 不改代码，也不改 FEAT-065 工作卡。
- 遵守 [CODING_STANDARD](../../development/CODING_STANDARD.md)：每个 Toolkit 调用检查 `ProError`；资源所有权明确；改动的 Python 文件过一遍 Ruff 格式化；C++ 用仓库 `.clang-format`，只格式化自己改动的段落。
- 只跑定向单测和离线驱动。全量 `tools/dev_check.py` 由主会话在 T4 统一执行，避免与另一个并行 agent 的半成品互相干扰。
- 报告内容：改了哪些文件、做了哪些设计决定、执行的命令与结果、未验证的范围、发现但未处理的问题。

## 8. 执行记录

- **T0（`5ba2cf5`）**：FEAT-033 移入与其状态一致的「部分交付，剩余待规划」分节，九类计数与分节行数逐类一致（177）；FEAT-009、FEAT-055 首页与 COMPATIBILITY 按 0.21.x 更正，旧文保留在带日期标题下。发现但未改的问题已转入 T4 待办（见下）。
- **T1（`b0a0bfa`）**：`sections`/`guides` 接受 `{kind:'curve'}`、`{kind:'edge'}`，首末截面可为收敛点；草图来源的解析和报错与 M1/M2 一致。原生拒绝带 `SURFACE_LOFT_INPUT_REJECTED` 与 `failed_loft_input`；回执新增来源种类、几何 ID、边的相邻面、`convergence_point`、`unverified_input_forms`。收敛点使用 `ProCrvcollection.h` 文档化的 `PRO_CURVCOLL_ADD_POINT_INSTR`，但它能否放进边界混合链容器，Probbl.h 没有写，属于实验路线。证据：定向单测 74 项 OK、受影响模块 537 项 OK、四个离线驱动 PASS、`cl /Zs` 语法检查 exit 0；未编译执行器、未连 Creo。
- **旧驱动修正（`b8e80e7`）**：`tools/test_surface_loft.py` 仍要求两截面拒绝 `smooth`（M1 遗留），改为正向检查。
- **T1 发现的两个限制**：
  1. quilt 边没有公开 ID 通道，`creo_inspect_model` 的 `edges` 只列实体面上的边。由 T1b 处理：`surface_group.cpp` 测量时已逐条收集开放边，只是没有输出。
  2. 原生 `has_solid` 检查看的是整个模型有没有实体，所以模型里已有实体时 `surface_loft` 一律失败，「用实体边补面」走不通。本轮未改，记入 FEAT-065 剩余范围。
- **T4 待办（来自 T0/T1 报告）**：0.21.0 版本说明漏列 M1，按发布核对台账的勘误方式补记，不改已发布原文；FEAT-065 工作卡中场景 E（799.94 mm²）与验收段曲线导线（600.0 mm²）的数值关系需要说明；BACKLOG 中状态写法与分节名不符的行（DEV-077/079/080、DEV-081、FEAT-055、DEV-074、FEAT-014、FEAT-039、FEAT-058）留给台账维护者判断，本轮不移动。
