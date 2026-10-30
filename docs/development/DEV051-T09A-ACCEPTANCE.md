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

## 2026-10-29 实机：组件业务标签四项（驱动 `tools/test_component_labels_live.py`）

环境：手动打开的 Creo 12.4.0.0、`auto_start_creo=false`、唯一 dev 服务 0.8.4、`ready/connected=true`；每例一个新建装配与两个新建源件，未重提任何作业，挂起预算 180 s。命令：

```text
.\.venv\Scripts\python.exe tools\test_component_labels_live.py --live --confirm-session-usable
```

报告：`build/component_labels/20261029T230555_a8d01966/report.json`，SHA256 `8f4ae709fe40e1960be34a87843beeeb4df122319e0a1d658a28fab8e76ad568`，退出码 0，4/4 通过。装配 `7fba61e3891b4be4af0b6ac10d96fabb`（job `8ff2db6b3c5f4105978a7266f4265f11`），源件 `790aff5df3be49b091642d9fd4cba471`、`8c8c6c89c15d466d96de73b777a198c5`。

| 用例 | 数据 | 结论 |
| --- | --- | --- |
| `two_components` | rev 1；两条记录 identity feature_id 40/43，`label_state=single`，`label`=`part_alpha`/`part_beta`，`source_model_id` 与源件一致、`source_revision=1` | 业务标签可定位组件，`identity_key=model_identity+feature_id` |
| `cross_job` | 第二个作业 `2f3e2139a5c24deba36b1dc227d047fa`（save）成功，rev 2；标签集合与 feature_id 完全不变 | 标签跨作业解析，物理副本名 `c_<job>_<n>` 未参与 |
| `rename_reinsert` | remove（rev 2）→ 以 `part_gamma` 重插（rev 4）；当前组件 `part_alpha`(40) + `part_gamma`(46)，旧标签不再挂到 46；`deleted_identities=[]` | 旧引用不误指重插记录；本实现里 remove 会一并去掉旧绑定，所以旧标签落在"查无"而不是 `deleted_identities`（两种落点都不误指，但客户端可观测差异需在下轮文档说明） |
| `unknown_label` | 用已移除的 `part_beta` 做 `component_placement`：**准入不拒**，作业 `af09a95aafec4ae0b950211e50df4593` 在原生阶段失败 | 原文 `Unknown feature label: part_beta; available labels: part_alpha, part_gamma`；`toolkit_code=-1`、`failed_stage=execute_component_placement`、`rollback_succeeded=true`，rev 4→4、组件清单不变 |

补充：

- 拒绝是**作业级**而非入口级：标签解析发生在原生执行时，客户端先拿到 `job_id`，必须轮询 `creo_get_job` 才能得到失败与回滚，不能把"已受理"当"已接受"。本轮按此记录，未重提。
- 未测：多标签挂同一 feature_id 的实机（离线 16 项覆盖）、被篡改的 `aliases_ref`、40 组件大清单与 32 KiB 分页的实机、compact/full 一致性、保存重载后重新打开的标签解析、Creo 9/10。

## 2026-10-30 离线阶段：保存重载关联与删除重插不误指（DEV-051 沿用卡，未实机）

阶段：**离线验证与回归完成；生产代码零改动；实机重载/删除重插复验仍未执行**。工作区 `E:\Projects\MCP_CREO_MechDog`，分支 `codex/dev051-feedback070`，基线 HEAD `7c650cf`，本阶段改动**未提交**（提交由派发方统一做），`dirty=true`。未连接 MCP/Toolkit、未启动 Creo、未改 git index、未改 `version.py`、`native/generic.cpp`、`native/advanced.cpp`、`schema.py`、`assembly_bundle.py`、`docs/BACKLOG.md`、`docs/validation/`，未覆盖工作区他人未提交文件。受测源码指纹（`git ls-files` 全部 `*.py` 与 `native/*.h|hpp|cpp`，共 292 个文件的 CRLF 归一化 SHA256 清单哈希）：`b4b2e77528ee36019874ebb02599111fc6a602ef0ccb40ec3dd522bf57dae118`。

### 一、现有标签绑定机制（带行号）

- **存储**：绑定是登记侧 registry 记录（`models/<id>/model.json`）的 `aliases` 映射（或 BUG-077 受控 sidecar `aliases_ref`），键为业务 label，值为 `{op, feature_id, source_model_id, source_revision, ...}`；关联键固定 **model_identity + feature_id**（`src/creo_mechdog/component_identity.py:49-50`）。label 永远不是身份。
- **写入**：原生 `remember`（`native/generic.cpp:841-846`）把每次操作的 label 与 feature_id/op 记入结果 `aliases`；`assemble_component` 的 remember 在 `native/advanced.cpp:1136`。作业成功收尾时 Python 把结果 aliases 提交进模型记录（`generic_bridge.py:593-601`，split 形态走 `aliases_ref`）；失败作业不改写（`generic_bridge.py:612-625`），回滚时原生从请求模型恢复原 aliases（`native/generic.cpp:5314-5316`）。
- **跨作业持久**：新作业原生从请求模型加载 `aliases_ref`/inline aliases（`native/generic.cpp:5017-5018`），结束后随结果返回并重新持久化——重载不触碰登记侧绑定。
- **查询投影**：`project_component_identities`（`component_identity.py:85-152`）只在查询面把绑定投影到组件记录；绑定 feature_id 不在当前记录时落 `deleted_identities`，绝不并入当前记录（`component_identity.py:135-147`）。

### 二、断链/误指场景核对与证据

| 场景 | 现有保护（证据） | 结论 |
| --- | --- | --- |
| 保存重载后标签是否还指回同一组件 | 保存作业原生执行 `ProMdlnameBackup` → `ProMdlErase` → 从磁盘重载 → `verify_saved`（`native/generic.cpp:5193-5221`）；其中**逐组件比较前后 `feature_id` 与 `model_name`**（`native/generic.cpp:3073-3086`），重载后 id/名漂移直接作业失败，不会提交错位绑定。绑定存登记侧，重载不重写 | 关联键（feature_id）的重载稳定性已由原生校验强制；投影层只需锁定"重载后同 id 记录解析原绑定、id 变化时绝不改绑" |
| 删除重插后旧标签误指新组件 | `remove_component` 原生即删除该 feature_id 的**全部**别名条目（`native/advanced.cpp:1292-1297`）；同 label 重插是显式 remember 新 id。投影层把残留 stale 绑定判为 `deleted_identities`，不并入新记录 | 删除后旧标签的落点是"查无"（绑定已删）或 `deleted_identities`（残留），两者都不误指；2026-10-29 实机 `rename_reinsert` 已证 `old_label_on_new_component=false` |
| 会话丢失后从 checkpoint 重载 | 原生 `ProMdlInit` 找不到会话模型时从 `part_file` 重载并用 `verify_saved` 对照登记 inspection（`native/generic.cpp:5121-5147`），aliases 从请求模型照常加载 | 绑定继续按 feature_id 求交，不因会话路径改变 |
| `feature_state` 删除与组件 | `feature_state` 只支持 part/sheetmetal，装配组件只能走 `remove_component`（`src/creo_mechdog/feature_state.py:366-373`） | 不存在经 tombstone 路径的组件绑定残留 |

**未定因（离线不可证）**：Creo 在极端场景（如外部编辑后的重载）是否可能产出 verify_saved 之外的 id 漂移——该情形会先被作业失败拦截，标签最多落入 `deleted_identities`/查无，不误指；真实行为待实机。

### 三、最小修复结论：生产零改动

按上述证据，重载稳定性由原生 `verify_saved` 组件比较强制，删除重插不误指由原生别名删除 + 投影 `deleted_identities` 共同保证。本轮未发现需要改动的生产缺陷，故生产代码零改动；交付为回归锁定与实机验证强化。未重命名任何源文件，未改 `c_<token>_<n>` 物理副本命名。

### 四、新增回归与测试/构建结果

新增离线回归（`tests/unit/test_component_identity.py`，16→19 例）：

| 用例 | 覆盖 |
| --- | --- |
| `test_save_reload_with_unchanged_ids_keeps_labels` | 保存重载后同 id 记录：标签、source 镜像与 `deleted_identities=[]` 完全不变 |
| `test_reload_id_renumbering_never_rebinds_onto_new_records` | 重载后 id 重排（verify_saved 会先拒绝保存）：当前记录全部 unlabeled，旧 id 落 `deleted_identities`，绝不改绑新记录 |
| `test_same_label_reuse_after_remove_binds_only_new_identity` | remove 后同 label 重插：只绑新 id，旧 id 不出现在任何当前记录或 `deleted_identities`（落点"查无"的契约化） |

驱动扩展（`tools/test_component_labels_live.py`）：离线模式新增 `reload_guard` 契约检查（上述三场景，投影层逐项断言）；live `cross_job` 用例把 `saved_file_reloaded_and_verified=true` 与**全量身份/镜像对照**（identity+source_model_id+source_revision）纳入 passed 判定；live `rename_reinsert` 用例新增 `old_label_observable` 记录旧标签可观测落点（`absent`/`deleted_identities`）。

命令与结果（Windows 11 x64 / PowerShell / `.venv` Python 3.12.14 / ruff 0.17.0；仅离线，不连 Creo）：

```text
.\.venv\Scripts\python.exe -m unittest tests.unit.test_component_identity -v
    Ran 19 tests in 0.112s   OK
.\.venv\Scripts\python.exe -m unittest tests.unit.test_component_identity tests.unit.test_model_queries tests.unit.test_component_changes tests.unit.test_driver_inspect_contract
    Ran 77 tests in 1.045s   OK
.\.venv\Scripts\python.exe tools\test_component_labels_live.py
    离线报告 build/component_labels/20261030T100437_7052fa7b/report.json
    projection 4 项 true；reload_guard 3 项 true
.\.venv\Scripts\python.exe -m ruff format / ruff check（两份改动文件）
    通过（All checks passed）
.\.venv\Scripts\python.exe bridge.py build
    exit 0 -> build\creo_worker.exe（本轮未改 native；构建未被并发 generic.cpp 改动阻塞）
```

### 五、实机待验步骤（本轮未执行，需另派实机阶段）

前提：唯一 dev 服务 `MCP_CREO_MechDog_dev` 指向 E 盘项目，满足 BUG-001 本次会话可操作条件；不擅自启动/结束 Creo、不擦用户模型。

1. **保存重载关联**：复跑 `tools\test_component_labels_live.py --live --confirm-session-usable`。强化后的 `cross_job` 会要求 save 作业 `saved_file_reloaded_and_verified=true` 且两组件的 identity/source 镜像逐项不变；该作业原生即做擦除+磁盘重载，因此通过即为"保存重载后标签仍指回同一组件"的直接证据。
2. **删除重插不误指**：`rename_reinsert` 用例复跑，记录 `old_label_observable`（预期 `absent`），确认旧标签既不挂新组件也不出现在 `deleted_identities` 指向新 id；`unknown_label` 复跑确认已移除标签的 placement 仍作业级拒绝。
3. **会话丢失重载（可选，仅自然发生时）**：若会话中该装配自然不在（如 Creo 重启后），对同一 `model_id` 提交一次编辑作业——原生将从 checkpoint 重载并 verify_saved；随后 `creo_list_components` 断言标签与 feature_id 不变。**不做故障注入、不为造场景擦受管模型**（`creo_erase_session_models` 不接受受管模型）。
4. 未测范围（如实记录）：以上实机全部未跑；多标签挂同一 feature_id 实机、被篡改 `aliases_ref` 实机、40 组件大清单分页实机、compact/full 一致性实机、Creo 9/10 均未测。离线阶段不等于整项验收通过。

## 2026-10-30：N09 实机补验的离线预检

阶段：**离线预检完成；实机未执行**。分支 `codex/dev051-feedback070`，接手时基线 `79b02ed`，本节提交前 HEAD `a6d4a3d`（并行 N03 窗口提交，非本节改动）。本节**未连接 MCP/Toolkit、未启动 Creo、未创建 MCP 客户端、未运行任何 `--live`、未运行 `bridge.py build`、未运行 `tools\dev_check.py`、未跑全量单测**。本节**未改生产逻辑**（生产实现已存在，原补强为零生产改动），未改 `c_<token>_<n>` 物理副本命名，未改 `src/creo_mechdog/`、`server.py`、`native/`。工作区 `dirty=true`（含并行窗口未提交文件，未暂存未改写）。

### 单元结果

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_component_identity tests.unit.test_component_changes tests.unit.test_model_queries` | exit 0，Ran 66，OK |
| `.\.venv\Scripts\python.exe -m unittest tests.unit.test_component_labels_live`（本节新增模块） | exit 0，Ran 11，OK |

### 驱动覆盖缺口与是否已补

| 缺口 | 是否已补 | 说明 |
| --- | --- | --- |
| **`reload_guard` 契约违例不失败**：旧 `check_reload_guard_contract()` 只返回布尔字典，离线 `main()` 恒 `return 0` —— 三条守卫任一为假，报告里写着 `false`，**退出码仍是 0** | **已补** | 新增 `contract_failures()` 汇总违例项写入报告 `contract_failures` 字段；离线有违例 → 退出码 **1** 并在 stderr 打印 `CONTRACT FAILED: ...`。单测 `test_a_contract_violation_fails_the_offline_run` 钉死 |
| `check_projection_contract()` 未核 `bindings` 内容（只核 labels/label_state/deleted） | **已补** | 补 `bindings` 逐条断言（多标签记录的 bindings 完整且字典序、单标签记录的单条 binding），新增 `bindings_kept_per_record` 结果项 |
| 三场景无机器可读预期 | **已补** | 新增 `scenario_expectations()`：reload_association / delete_then_unique_label_reinsert / id_renumbering_never_rebinds，各带 `input`、`expect`、`fails_when`，随离线报告发布 |
| 驱动无单元模块 | **已补** | 新增 `tests/unit/test_component_labels_live.py`（11 例） |

核实结果（字段与重载强制判定**原本已具备**）：`identity`（model_id+feature_id）、`labels`、`label`、`label_state`（single/multi/unlabeled）、`source_model_id`/`source_revision`、`bindings[]`、顶层 `deleted_identities[]`（`reason="feature_id_not_in_verified_components"`）、`identity_key`；live `cross_job` 要求 save 作业 `saved_file_reloaded_and_verified is True` **且** identity+source 镜像逐项不变，缺一即失败。

### 三场景与预期

1. **重载后关联** — live `cross_job`：save 作业原生即擦除+磁盘重载；要求标签集合不变 + 两组件 identity/source 镜像逐项不变。
2. **删除后新唯一 label 重插** — live `rename_reinsert`：remove `part_beta` → 以**新唯一 label** `part_gamma` 重插；要求 `part_gamma` 恰一条且带新 feature_id、`part_beta` 不在任何当前组件、旧标签可观测落点记 `absent`/`deleted_identities`。
3. **ID 重排不误绑** — live `cross_job`（原生 `verify_saved` 拒绝该保存）：离线侧当前记录全部 unlabeled、旧 id 落 `deleted_identities`，绝不改绑新记录。

### 实机命令与预期判定（待指定）

```powershell
.\.venv\Scripts\python.exe tools\test_component_labels_live.py --live --confirm-session-usable --output build\post090_live_<runid>\n09_component_labels\report.json
```

预期：`two_components` 两记录 `label_state=single`、label 与源件 `source_model_id`/`source_revision` 一致；`cross_job` **必须** `saved_file_reloaded_and_verified=true` ∧ 标签集合不变 ∧ identity/source 镜像不变；`rename_reinsert` remove 与 reinsert 均 succeeded、`part_gamma` 恰一条、`part_beta` 不在任何当前组件；`unknown_label` 作业级失败（原文含 "Unknown feature label: part_beta"、`toolkit_code=-1`、`failed_stage=execute_component_placement`、`rollback_succeeded=true`）、revision 不变。物理副本名 `c_<job>_<n>` 未参与身份判定。

### 未测范围与风险

全部实机未跑。多标签挂同一 feature_id 实机、被篡改 `aliases_ref` 实机、40 组件大清单分页实机、compact/full 一致性实机均未测。**`ID 重排不误绑` 仅部分实机可验**：原生 `verify_saved` 拒绝该保存（可观测为拒绝），但"重排后仍被提交的模型"无法经本服务构造 —— 投影侧由离线回归证明，原生侧只能观察拒绝，**该半场景不得整体记为实机通过**。离线阶段不等于整项验收通过。

离线产物：`build/post090_live_precheck_20261030T212525_b09a058e/n09_component_labels/report.json`（含 `projection`、`reload_guard`、`scenarios`、`contract_failures`）。合并预检小结：同目录 `precheck.md`。
