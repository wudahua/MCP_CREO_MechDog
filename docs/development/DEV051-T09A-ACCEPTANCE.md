# DEV-051 T09A 验收卡：组件业务标签（FEAT-023/008，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线阶段完成 / 实现待原生验收**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业。状态不是“已修复”：跨作业装配查询与保存重载的实机闭环尚未执行，见“未测项”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T09A 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（FEAT-023/008 与 T09 节）、[FEAT-023 工作卡](../work-items/FEAT-023.md)、[FEAT-008 工作卡](../work-items/FEAT-008.md)、[DEV051-T02 验收](DEV051-T02-ACCEPTANCE.md)（结果回显不得回声输入的同源契约）、[DEV051-T08B 验收](DEV051-T08B-ACCEPTANCE.md)（查询投影与预算先例）。
- 0.7.0 反馈 R2 P4 原件（`feedback-0.7.0-2026-10-28`）：组件副本名为 `C_<job>` 派生名、`components` 无业务 label；0.3.5 报告两组件清单 170,512 字符。业务 label 需从 aliases 恢复，物理副本名不改。
- 本次受派范围仅 T09A 离线阶段：不连接 Creo、不改版本、不合 main、不推标签、不 push、不发布。工作区既有无关改动（`.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、untracked 的 `0.7.2-FEEDBACK-*` 与 `docs/validation/feedback-0.7.2-2026-10-28/`）均未暂存、未改写、未删除。

## 关联键契约（T09A 交接，固定）

**关联键 = 模型身份 + feature_id**：模型身份取组件清单所属登记记录的 `model_id`；`feature_id` 为原生组件特征 id。label 永远不是身份：同名 label 可存在于不同模型，删除重插后 label 不变但 `feature_id` 换新，因此求交只在**同一模型身份内**按 **feature_id** 进行；绑定不可能跨模型挂接，也不可能挂到重插后的新记录上。

**绑定识别规则**（与 `component_changes` 一致）：alias 条目满足 `op="assemble_component"`（原生 `remember` 恒写 op）或其 `feature_id` 属于当前组件记录 id 集，即为组件绑定；通用特征别名（sketch/extrude/...）永不进入。

**多标签与已删除身份的表达**（每个组件记录新增字段，全部只增不改）：

| 字段 | 含义 |
| --- | --- |
| `identity` | `{model_id, feature_id}`，即固定关联键本身 |
| `labels` | 挂在该 feature_id 上的全部业务 label（按字典序） |
| `label` | 恰一个绑定时为该 label，否则 `null` |
| `label_state` | `single` / `multi`（多标签）/ `unlabeled`（旧结果、收养装配无绑定） |
| `source_model_id` / `source_revision` | 恰一个绑定时镜像该绑定值；多标签或无绑定时 `null`（禁止任选一个冒充） |
| `bindings` | 每个绑定一条 `{label, source_model_id, source_revision}`，多标签时的完整事实 |

**已删除身份**：组件绑定的 `feature_id` 不在当前组件记录中时，作为独立条目输出到 `deleted_identities`（`identity` + `labels` + `bindings` + `reason="feature_id_not_in_verified_components"`），**绝不合并进任何当前记录**；旧引用（旧 job 结果/旧 feature_id）因此只会落到 deleted_identities 或查无，不会误指重插后的新组件。绑定缺整数 feature_id 时不参与求交（无法构成关联键）。

**投影边界**：只在查询面（`creo_list_components`、`creo_inspect_model` 的 components 节与整页快照）投影；存储的 inspection/aliases 载荷绝不改写，`c_<token>_<n>` 物理副本命名（`native/advanced.cpp` `assemble_component`）未触碰。aliases 经 `model_registry.aliases_of` 解析，详情引用（aliases_ref sidecar，BUG-077）与内联记录行为一致，被篡改的引用按既有契约拒绝而不是静默丢 label。投影为纯函数，不修改输入，不编造 label/id/源件值。

## 实际修改文件

- 新增 `src/creo_mechdog/component_identity.py`（投影实现，业务逻辑在包内）。
- `src/creo_mechdog/model_queries.py`：`section_records` 的 components 节返回投影记录；`inspect_page` 整页快照（whole fast path）的 inspection.components 同步投影，与分页形态一致（T08 feature_state 先例）。
- `server.py`：`creo_list_components` 改用投影（`components` 内联 label/身份，新增 `deleted_identities`、`identity_key`，`aliases` 原样保留）；仅此调用适配，无签名/注册变化。
- 新增 `tests/unit/test_component_identity.py`（16 项）。
- 本卡；`docs/work-items/FEAT-023.md`（只追加）。未改 `version.py`、native、`bridge.py`、schema、台账、README、另一会话文件。

## 依赖提交、受测身份与指纹

- 依赖（基线）：`5b37e9429d39a0386fc3d94bac9a1e2e566d02be`（T09C，分支 HEAD）。
- 实现提交：本卡所属 T09A 提交（提交号不能自指，以交接报告 `git rev-parse HEAD` 为准）。
- 受测 commit：`5b37e942` 工作树 + 本批 T09A 改动；dirty=true（含本批改动与另一会话未提交文件、本机运行数据）。
- `source_fingerprint`：`42f1dde0247088dbb8e92f9de96fd457b943a90f758f944de8757332d0c9f9cc`（与 T07/T08B 同一算法：`git ls-files` 的全部 `*.py` 与 `native/*.h|*.hpp|*.cpp` 加本批新增 2 文件，共 270 个文件的 CRLF 归一化 SHA256 清单哈希）。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；ruff 0.17.0（requirements-dev 锁定）；**未连接 Creo、未启动 MCP/Creo、未提交 Toolkit 作业**。服务版本入口仍为 0.7.2，未改。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_component_identity -v` | exit 判定 OK，**Ran 16 tests, OK**（ruff format 后复跑仍 Ran 16, OK） |
| 2 | `.venv\Scripts\python.exe -m unittest tests.unit.test_model_queries tests.unit.test_component_changes tests.unit.test_model_registry tests.unit.test_driver_inspect_contract` | **Ran 86 tests, OK**（既有查询/变更摘要/登记/驱动契约用例不回归） |
| 3 | `.venv\Scripts\python.exe -m ruff format --check / ruff check`（本批 4 文件） | 新增文件按项目格式格式化后通过；lint 全过（All checks passed），无新增诊断、未动基线 |

按共同要求，全量 `-m unittest discover -s tests` 与 `tools\dev_check.py` 在 T09B 实现完成后统一执行一次；其结果记录于 [DEV051-T09B 验收卡](DEV051-T09B-ACCEPTANCE.md) 与交接回传报告。本卡提交时该全量检查尚未执行，如实记录，不以定向测试冒充全量。

测试覆盖（离线，不实例化 MCP 客户端）：单 label 镜像；多标签（`label_state="multi"`、单值字段 null、bindings 完整、字典序）；旧结果无 label（unlabeled、不编造）；同名不同模型不跨模型挂接；跨 job 别名持久解析；删除重插（旧 feature_id 进 deleted_identities、新记录只挂新绑定、旧引用不误指）；无 op 旧别名按 id 归属照常关联；通用特征别名排除；source 值非法不镜像；输入零修改；identity_key 固定为 model_identity+feature_id；compact 不展开 components（32 KiB 内）；full 分页节与整页快照投影一致；aliases_ref 详情引用解析出 label；40 组件 × 绑定分页全程 ≤ 32 KiB 且无重漏。

## 未测项与下一步

- 未测（需实机，另按共同契约指派并在唯一 dev 服务串行执行）：真实装配的跨作业组件查询、删除重插后的实机 aliases/清单对照、保存重载与 revision、大装配清单体量（历史 170,512 字符案）与 32 KiB 分页的实机观测、compact/full 实机一致性。
- 未测：WorkBuddy 黑盒验收；Creo 9/10 独立环境。
- 缺材料：无（0.3.5/0.7.0 原始 job/PRT 缺失不影响本批投影契约与离线用例）。
- 提请 T01 统一收口的描述/文档改动：`creo_list_components` 工具描述补一句“组件记录内联 label/labels/label_state/source_model_id/source_revision/bindings 与 identity 键，另返回 deleted_identities/identity_key”；README/能力说明补组件身份查询示例。本批未直接改工具描述与 README。
- 下一步：集成人按“给集成人的冲突文件与接口变化”合并；T09A 实机验收需人工确认会话可操作及 BUG-001 条件；T10 决定版本与发布。

## 给集成人的冲突文件与接口变化

- 冲突面：`src/creo_mechdog/model_queries.py`（与 T09C cursor 同文件——本批只加 components 节投影与整页快照一致性块）、`server.py`（只动 `creo_list_components` 函数体）。native 无改动，`c_<token>_<n>` 命名与 `verify_saved`/component_changes 读取路径（存储载荷）不受影响。
- 接口变化（只增不改）：
  - `creo_list_components` 返回的 `components` 每条新增 `identity/labels/label/label_state/source_model_id/source_revision/bindings`；顶层新增 `deleted_identities`、`identity_key`；`aliases`、`model_id`、`revision` 不变。
  - `creo_inspect_model`（detail=full 的 components 节、整页快照、`read_full_model` 重组）的组件记录同样携带上述投影字段（加性；既有消费者按字段访问不受影响）。
  - compact 摘要不变（counts 只计数，不内联记录）；分页/cursor/32 KiB 预算语义不变，投影字段计入页体积。
  - 无新工具、无 schema 变更、无版本变更。
