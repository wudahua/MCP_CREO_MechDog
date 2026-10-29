# DEV-051 T08B 验收卡：body 计数语义（BUG-040，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线定义与实现完成 / 原生计数待实机核对**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业，未创建/删除/重命名任何 body。状态不是“幽灵 body 已修复”：原 0.3.0 报告的 `id=-5778` 记录仍无法逐字重放，材料归属的真实数值要等实机。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约、T08B 节）、[BUG-040 工作卡](../work-items/BUG-040.md)、[DEV051-T03](DEV051-T03-ACCEPTANCE.md)（薄板 185×232×1 = 42 920 mm³ 与厚壁 9 957 440 mm³ 的离线定因）、[DEV051-T05](DEV051-T05-ACCEPTANCE.md)（钣金四壁 body 相关假说 H4）。
- 原始证据：0.3.0 报告第四节第 6 项（第一壁后两个 body，一个 bbox 正常、一个 `id=-5778` 无 bbox）、2026-10-16 履带报告第五节（sweep(add) 后计数 2，state=3/4 各一，后续某次拉伸后变 1）。两份均为历史记录，本次未新取得 request/job/native JSON。
- 本次受派范围仅 T08B 离线阶段：不连接 Creo、不改版本、不合 main、不推标签/不 push、不发布、不做 T08C/T09。工作区既有无关改动（`.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、untracked 的 `0.7.2-FEEDBACK-*` 与 `docs/validation/feedback-0.7.2-2026-10-28/`）均未暂存、未改写、未删除。

## 枚举与状态核对（T08B 第 1 项）

`ProSolidBody.h`（本机 Creo 12.4.0.0 Toolkit）声明：

```text
PRO_BODY_STATE_NONE       = -1
PRO_BODY_STATE_MISSING    = 0
PRO_BODY_STATE_CONSUMED   = 1
PRO_BODY_STATE_NO_CONTR_FEAT = 2
PRO_BODY_STATE_NO_GEOMETRY   = 3
PRO_BODY_STATE_ACTIVE        = 4
```

因此履带报告的 “state=3 和 4 各一” 是 **NO_GEOMETRY 记录 + ACTIVE 材料体**，不是两个实体；0.3.0 报告的无 bbox 记录与 NO_GEOMETRY/NO_CONTR_FEAT 一致。旧输出只给 `state` 数字且对非 ACTIVE 记录**不写** `has_geometry`/`bbox`，调用方无法区分“没有这个键”和“测出来是空”，这正是“幽灵 body”观感的来源。负 ID 本身不是无效证据：`ProSolidBodiesCollect` 返回的是本会话对象，是否参与材料由 state 决定，与 id 正负无关。

| 巡检来源 | 修改前 | 修改后 |
| --- | --- | --- |
| `native/generic.cpp` `inspection()` | `{id, state}`；ACTIVE 才追加 `has_geometry`、`bbox` | 追加 `state_name`；ACTIVE 追加 `surface_count`、`has_geometry`、`material`、`bbox`+`bbox_query_code`；非 ACTIVE 显式 `has_geometry=null`、`material=false` |
| `native/geometry.cpp` `active_body()`/`remove_empty_body()` | 已按 `PRO_BODY_STATE_ACTIVE` 选体，只在显式清理时删 NO_CONTR_FEAT/NO_GEOMETRY | **未改**（复核后无需改；清理仍由既有的 `extrude_or_revolve` 在“恰好一个 ACTIVE body”时调用，`skip_empty_body_cleanup` 可关） |
| `src/creo_mechdog/model_queries.py` `inspection_summary()` | `counts.bodies = len(bodies)`（记录数），无其它口径 | 保留该含义，新增 `body_counts` 透传 |

## counts 字段实际含义（T08B 第 2 项）

**旧字段不变**：`counts.bodies` = inspection 里 `bodies` **记录**条数，包含非 ACTIVE、无几何、负 ID 的记录。它从来不是“材料体数量”，本次不改这一语义（不静默替换）。

**新增字段**（原生 inspection 的 `body_counts`，Python 摘要同名透传）：

| 字段 | 含义 | 未知时 |
| --- | --- | --- |
| `objects` | `ProSolidBodiesCollect` 返回的 body 对象数 | `null` |
| `records` | 实际写入 `bodies` 的记录数（正常等于 `objects`） | `null` |
| `active` | `state == PRO_BODY_STATE_ACTIVE` 的对象数 | `null` |
| `with_material` | ACTIVE 且至少贡献 1 个面（`surface_count > 0`）的对象数 | `null` |
| `without_material` | `records - with_material` | `null` |
| `counts_meaning` | 自描述映射：`{bodies: "body_objects", with_material: "active_bodies_with_surfaces"}` | 缺省不出现 |

装配体没有零件 body，`body_counts` 为 `null`（而不是 0，0 会被读成“实体但无材料”）。Python 侧只做白名单透传：缺块 → `None`；单值非非负整数（含负、字符串、布尔）→ `None`；**不**用记录数回填，避免再次把两种口径混在一个字段。

## 三类件的对照（T08B 第 1 项，离线口径）

| 场景 | 期望的计数合同 | 本次证据 |
| --- | --- | --- |
| 普通实体 | `objects=records=active=with_material=1`，`without_material=0`，该记录 `state=4`、`surface_count>0`、`material=true`、`bbox` 存在且 `bbox_query_code=0` | 单元夹具覆盖；实机未测 |
| 薄钣金 185×232×1 | 同上（钣金身份由 `ProMdlSubtypeGet` 给 `model_type="sheetmetal"`，与 body 清单无关）；体积 42 920 mm³ 属 T03 离线定因 | 单元夹具覆盖（不按厚度分支）；实机未测 |
| 报告厚壁 9 957 440 mm³ | 仍是**一个** ACTIVE 材料体；T03 已定因为驱动面选择导致 185×232×**232**，不是 body 计数问题 | 依赖 T03 离线结论，实机未测 |
| 0.3.0 第一壁后“两个 body” | 一个 ACTIVE 材料体 + 一个 NO_GEOMETRY/NO_CONTR_FEAT 记录；`counts.bodies=2`、`body_counts.with_material=1` | 结构与枚举证据；原始 job 缺失，未重放 |
| 履带 sweep(add) 后 2 → 拉伸后 1 | 第三类记录被既有的“单 ACTIVE 时清空体”移除，计数跟随真实对象变化 | 静态复核调用点；实机未测 |

## 实现（只按已证实规则）

1. 原生逐条记录 `state_name`（覆盖全部 6 个声明值，未知值报 `"unknown"`，不猜），并给 ACTIVE 体记录 `surface_count` 与 `bbox_query_code`，使“有材料/无材料”可追溯到实际面访问与 outline 查询。
2. `material` 由定义决定：ACTIVE 且 `surface_count > 0` 为 true；非 ACTIVE 记录 `material=false`（这些状态按 SDK 语义不承载独立材料），其几何存在性保持 `null`（未访问面，不冒充“测得为空”）。
3. 新增顶层 `body_counts`；`bodies` 记录一条不删、不改 id、不按 bbox 过滤；**没有**任何 `-1`、`len()-1` 或“负 ID 跳过”的算术/过滤。
4. Python 只透传，不重算。

## 本批修改文件

`native/generic.cpp`（body 状态名、逐体 `surface_count`/`material`/`bbox_query_code`、`body_counts`；clang-format 已过）；`src/creo_mechdog/model_queries.py`（`body_counts()` 白名单投影 + 摘要新增字段 + 语义注释）；`tests/unit/test_body_count_semantics.py`（新增 13 项）；本卡；`docs/work-items/BUG-040.md`（追加）。未改 `native/geometry.*`（复核无必要改）、`version.py`、`bridge.py`、`server.py`、schema、台账与另一会话文件。

## 依赖提交、受测身份与指纹

- 依赖提交（基线）：`0b26c66efd11a80826492b3c4dfb240a798b0a32`（T08A 提交，分支 HEAD）。
- 实现提交：本卡所属 T08B 提交（提交号不能自指，以交接报告 `git rev-parse HEAD` 为准）。
- 受测 commit：`0b26c66e` 工作树 + 本批改动；dirty=true（含本批改动、另一会话未提交文件与本机运行数据）。
- `source_fingerprint`：`b96f513243bdabf6e5a422db0fdb0d4e176dc7feee7b4adaba5747fd850aaabb`（与 T07 驱动 `local_provenance()` 同一算法：`git ls-files` 的全部 `*.py` 与 `native/*.h|*.hpp|*.cpp` 共 266 个文件，加本任务相关测试/驱动文件的 CRLF 归一化 SHA256 清单哈希）。
- `tools/dev_check.py` 的 `checked_source_sha256`：`148d966f1cfc667cd85ef34fae634cb32230bad73333ab564e21f49bce732562`（同一最终源码内容）。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；ruff 0.17.0；clang-format 23.1.3；本机 Creo 12.4.0.0 + 匹配 Toolkit SDK 仅用于编译，**未连接 Creo、未启动 MCP/Creo、未提交 Toolkit 作业**。服务版本入口仍为 0.7.2，未改。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_body_count_semantics -v` | exit 0，**Ran 13 tests, OK**；`ruff format` 曾要求合并 3 处跨行，格式化后复跑仍 Ran 13, OK |
| 2 | `.venv\Scripts\python.exe bridge.py build` | exit 0，输出 `build\creo_worker.exe`；exe mtime `1793200512` 晚于 `native/generic.cpp` `1793200484`，确认重新编译（clang-format 后再次重建） |
| 3 | `.venv\Scripts\python.exe -m unittest tests.unit.test_body_count_semantics tests.unit.test_model_queries tests.unit.test_t07_preview` | exit 0，Ran 55 tests, OK（摘要改动未影响既有查询/预览用例） |
| 4 | `.venv\Scripts\python.exe -m unittest discover -s tests` | exit 0，**Ran 1254 tests in 264.231s, OK**（T08A 基线 1241 + 本批 13） |
| 5 | `.venv\Scripts\python.exe tools\dev_check.py` | exit 0，`success=true`、`unit_tests=passed`、`native_validation=not_run`、`style_summary` lint 30 / unformatted 16（均为存量基线计数，未新增）、`cpp_files_checked=33`、`python_files_checked=233`；报告 `build/development_check.json`，SHA256 `5449BE010E14A33C747D0DC4F32D1AE6C967C07B2E7FBD9B452601332DED7675` |
| 6 | clang-format 自检 | 格式化后 `clang-format --style=file --fallback-style=none native/generic.cpp` 输出与文件字节一致（MATCH）；仅重排本批新增的 `body_counts` 初始化块 |

第 5 项即“最后统一执行一次”的全量检查，已在 T08B 最终源码上取得；本卡与 T08A 卡不混用不同指纹的通过数。

## 未测项与下一步

- 未测（需实机，另按共同契约指派并在唯一 dev 服务串行执行）：普通实体、薄钣金 185×232×1、报告厚壁三类件的真实 `body_counts` 数值、`surface_count`、`material`、`bbox_query_code`；0.3.0 原 job 的 `id=-5778` 记录重放；sweep(add) 后 2 → 1 的真实状态变化与 `remove_empty_body()` 的实际效果；`compact` / `full` 两种 detail 下计数一致；保存重载与 revision 不受影响。
- 未关闭理由：原 0.3.0/履带 job 与 native JSON 未交付，本次只把“记录 → 对象/状态/材料”的可追溯链补齐，没有真实数值可对照；BUG-040 的“材料归属”验收标记为待实机。
- 下一步：实机先在空件 → 第一壁 → 折边链上抓 `bodies` 与 `body_counts`（记录 id/state/state_name/surface_count/material/bbox_query_code），再与体积、`counts.bodies`、`compact`/`full` 对照；若出现 `state_name="unknown"`，按真实数字补映射而不是归入“幽灵”。清理策略如要变动（例如扩大到更多状态），必须另开条目并证明只影响本项目可清空体。

## 给集成人的冲突文件与接口变化

- 冲突面：`native/generic.cpp` 被 T02/T04/T06/T08B/T09B 共用——本批只改 `inspection()` 的 body 段与新增 `body_state_name()`，未动 sketch/extrude/hole/round/export 分支；`src/creo_mechdog/model_queries.py` 与 T09C（cursor）同文件，本批只加 `BODY_COUNT_KEYS`、`body_counts()` 与摘要字段。
- 接口变化（只增不改）：
  - 原生 inspection 新增 `body_counts`（装配为 `null`）；每个 body 新增 `state_name`，ACTIVE 体新增 `surface_count`、`material`、`bbox_query_code`，非 ACTIVE 体新增 `material=false` 与 `has_geometry=null`。
  - `counts.bodies` 语义未变（记录数）；新增 `inspection_summary()["body_counts"]`，未知为 `null`，不要用 `counts.bodies` 代替材料体数量。
  - `section_records(model, "metadata")` 的排除集合会自动包含 `body_counts`（因为它出现在摘要里），无需另外登记。
  - 无新工具、无 schema 变更、无版本变更；摘要体积增加约 150 字节，`test_the_separated_block_fits_the_response_budget` 覆盖 40 体仍 < 32 KiB。

## 2026-10-29 实机：五类模型 body_counts 实测（驱动 `tools/test_body_counts_live.py`）

环境：手动打开的 Creo 12.4.0.0、`auto_start_creo=false`、唯一 dev 服务 0.8.4、`ready/connected=true`；未启动/关闭/重启 Creo，未重提作业；每例一个新建模型，挂起预算 180 s。命令：

```text
.\.venv\Scripts\python.exe tools\test_body_counts_live.py --live --confirm-session-usable
```

报告：`build/body_counts/20261029T230048_c2a6bb7b/report.json`，SHA256 `265bb0587fe4cfd9e685ce16976ce2be9bccb032a63995e5d815072b81e39361`，退出码 0，5/5 通过。

| 例 | 模型 / job | 体积 / rev | `body_counts` | body 记录 |
| --- | --- | --- | --- | --- |
| `part_single` 单实体件 | `e9f5d4b46bbf4ccf9a02082bc9fca3a4` / `85638bcfa8da4046af9503c738362144` | 20 000 / 1 | objects=1 records=1 active=1 with_material=1 without_material=0 | 1 条：id 52、`active`、surface_count 6、material true、bbox 50×40×10 |
| `part_two_body` 两实体件 | `85b714d806b441499a5a0b24d48e8c97` / `22f387273d274678b736e5f5ce702d28` | 21 000 / 1 | objects=2 records=2 active=2 with_material=2 without_material=0 | 2 条 ACTIVE（id 52、id 90），各 6 面，`counts.bodies=2` |
| `sheetmetal_wall` 1 mm 钣金壁 | `888c3fe1b2c840d2a5699ae9f0519580` / `c357c07324614ecab5ad58c4e101cac9` | 42 920 / 1 | **objects=2 records=2 active=1 with_material=1 without_material=1** | id −5778 `no_geometry`（material false、bbox null、surface_count null）+ id 49 `active`（6 面、bbox x0…185 / y−232…0 / z−0.5…0.5） |
| `part_surface_quilt` 曲面拉伸叠加 | `01be14ce918e4be79e57db109514b6a7` / `b891e917944d4159be6942902019fe46` | 20 000 / 1 | objects=1 records=1 active=1 with_material=1 without_material=0 | 仍 1 条 ACTIVE，`counts.bodies=1` |
| `assembly_two` 两组件装配 | `d33bdac0d25f4a1e89a75b762c82246d` / `7783bb1cb3fc46388423403d6cea864a` | 40 000 / 1 | **null** | 无 body 记录；components=2（`component_a`/`component_b`，feature_id 40/43） |

结论：

- **幽灵 body 复现**：钣金第一壁后确实是 2 条记录、1 个材料体。`counts.bodies=2` 是记录数，`body_counts.with_material=1` 是材料体数，两者不再混为一个字段；`id=-5778` 的 `no_geometry` 记录就是历史报告里的“无 bbox body”，现在有 `state_name`、`material=false`、`has_geometry=null` 可区分“没有这个键”和“测出来是空”。
- **构造/面组不误计**：曲面（quilt）拉伸叠加后 body 记录仍为 1、体积不变，未把面组算成材料体；装配返回 `null` 而非 0，也未把组件算成 body。
- **多实体装配**：`body_counts` 为 `null`、组件数由 `components` 独立给出，两种口径没有互相顶替。
- **部分验证**：`part_surface_quilt` 的作业成功且 body 不增加，但该模型后续只读巡检返回的 `features` 列表为空，**未独立确认 quilt 特征存在**；这里只能记“未增加 body 记录”，不记“面组已建”。
- 未测：`compact` 与 `full` 两种 detail 的逐字一致性（本轮只走 full 快照）、`surface_count` 与 bbox 的 `bbox_query_code` 异常分支、0.3.0 原 job 的 `id=-5778` 逐字重放、sweep(add) 后 2→1 的真实状态变化、Creo 9/10。BUG-040 的“材料归属”不再需要实机继续调查：本次已给出三类件的真实数值。
