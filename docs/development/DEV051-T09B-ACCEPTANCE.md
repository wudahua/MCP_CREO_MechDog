# DEV-051 T09B 验收卡：实际回转轴回显（FEAT-008/BUG-083 关联，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线阶段完成；2026-10-29 实机三例通过（内部中心线、显式基准轴、失败路径），`section_centerline_count` 计入参考线的回显局限待后续处理**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T09B 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（FEAT-008/T09 节）、[FEAT-008 工作卡](../work-items/FEAT-008.md)、[BUG-083 工作卡](../work-items/BUG-083.md)、[DEV051-T02 验收](DEV051-T02-ACCEPTANCE.md)（结果回显不得回声请求的同源契约与 `operation_results` 投影先例）、[DEV051-T08B 验收](DEV051-T08B-ACCEPTANCE.md)（`native/generic.cpp` 巡检契约，回归面）。
- 0.7.0 反馈 R2 P7 原件（`feedback-0.7.0-2026-10-28`，§6）：`revolve` 结果只含 `material_removed_mm3` 与 `length_unit`，不回显实际解析轴（id/label/origin/direction）；含多根 centerline 或多 datum axis 的草图“静默选了一根”无法从结果侧发现；省略 axis 时内部中心线回退静默。建议 `resolved_axis`/`axis_source` 回显。
- 本次受派范围仅 T09B 离线阶段：不连接 Creo、不改版本、不合 main、不推标签、不 push、不发布。工作区既有无关改动（另一会话的 `.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、untracked 的 `0.7.2-FEEDBACK-*` 与 `docs/validation/feedback-0.7.2-2026-10-28/`）均未暂存、未改写、未删除。

## 结果契约（T09B 交接）

每个 `revolve` 操作结果新增 `revolve_axis` 块（只增不改；旧作业无块不补，绝不按请求参数编造）：

| 字段 | 契约 |
| --- | --- |
| `source` | `explicit`（请求显式轴）/ `internal_centerline`（省略或 null 轴，草图构造中心线回退）/ `unknown` |
| `kind` | 实际解析轴的来源分类：`datum_axis`（无归属面的基准轴）/ `surface`（轴由几何面解析——ProAxisSurfaceGet 查到归属面，如孔/圆柱自身轴）/ `section_centerline`（内部中心线）/ `unknown` |
| `id` | 实际解析 id，与 kind 同空间：datum_axis/surface 为模型轴几何项 id（可用于 `{kind:"axis",id:N}`）；section_centerline 为草图 section 实体 id（与 sketch 结果 entity_ids 同空间）；无法判定为 null |
| `origin` / `direction` | **只来自实际轴或 section 中心线查询**；`frame="model"` 时为模型坐标（3 元，direction 单位化）；`frame="sketch_local"` 时为草图截面 (u,v) 坐标（2 元）；未知为 null，**绝不回填请求值** |
| `frame` | `model` / `sketch_local` / null |
| `length_unit` | 与 `datum_axis` 操作结果同形的真实单位查询块（name/query_code/scale_to_mm/...，失败为 null+原码） |
| `geometry_known` | 严格布尔；仅当 frame 合法且 origin/direction 均为实测有效向量时 true |
| `query_code` | 产出几何值的查询码（ProError/section 码），未知为 null |
| `resolution` | 辅助查询证据：`feature_axis_query_code`（创建后回转特征自身轴项访问码）、`axis_item_query_code`、`axis_surface_query_code`（ProAxisSurfaceGet 码）、`section_centerline_count`（实测中心线根数，查询失败为 null）、`section_query_code` |

**多中心线/无中心线的表达**：`resolution.section_centerline_count` 报告实测根数；多根时“用了哪一根”无法从结果侧判定则 `id=null`（几何仍可由特征轴查询给出，若可查）；零根时 `id=null` 且几何未知。**本次不收紧歧义**（不新增拒绝、不改回退）：多中心线内部回退的行为与旧版一致，仅新增可观测性；若未来收紧（例如内部回退遇多中心线显式拒绝），必须按派发表要求显式记录版本影响（新 MINOR 与迁移说明），本卡不预留。

**Python 归一化投影**（`src/creo_mechdog/operation_results.py`）：`normalize_revolve_axis` 严格白名单校验原生块（枚举/整数 id/有限向量/帧维度一致：model=3 元、sketch_local=2 元），不一致的实测字段**降级为显式 unknown（null+保留原查询码）**，而不是保留来历不明的数值；`annotate_revolve_axis` 挂接在 `annotate_native_result`（generic_bridge 持久化路径），不读取、不复制请求轴——缺块保持缺失。

## 入口与兼容

- 独立 `creo_revolve` 与 `creo_execute_plan` 的 `revolve` 操作共用 `native/generic.cpp` `extrude_or_revolve`，两条入口同享回显；结果记录经 `operation_results` 统一投影。
- **准入/回退兼容保持**：显式轴仍只接受 `{kind:"datum_axis_feature",label}` 与 `{kind:"axis",id}`（BUG-083 契约）；省略与 null 等价、走草图构造中心线；空对象/缺 kind/`{entity:"ax"}` 仍入口拒绝；草图创建仍限一条 centerline（既有规则）。无效轴保持既有拒绝路径（Python 预检 + 原生 `validate_revolve_axis` 纵深防御），失败作业不产生 `revolve_axis` 块。
- 显式轴的 kind 分类为**实测**：`ProAxisSurfaceGet` 查到归属面记 `surface`（面解析轴，如孔/圆柱轴或经 `datum_axis_feature` 标签解析到的非基准轴特征的轴）；E_NOT_FOUND 记 `datum_axis`；其他码记 `unknown`。不按请求文本分类。

## 实际修改文件

- `native/generic.cpp`：新增 `#include <ProAxis.h>`、`classify_axis_provenance()`、`revolve_axis_report()`；`extrude_or_revolve` 捕获显式轴解析 id 并在成功后写入 `details["revolve_axis"]`。未改 `validate_revolve_axis` 准入、未改两条建弧路径/sketch_edit/巡检分支（T02/T07/T08B 契约不动）。
- `src/creo_mechdog/operation_results.py`：新增 `normalize_revolve_axis`/`annotate_revolve_axis` 并挂接 `annotate_native_result`；T02 的 arc/profile/feature_state 投影未改。
- 新增 `tests/unit/test_revolve_axis_report.py`（16 项）。本卡；`docs/work-items/FEAT-008.md`（只追加）。未改 `version.py`、`server.py`、schema、台账、README、另一会话文件。

## 依赖提交、受测身份与指纹

- 依赖（基线）：`c5145d78e466cf50a7809832a5566389cf574510`（T09A，分支 HEAD）。
- 实现提交：本卡所属 T09B 提交（提交号不能自指，以交接报告 `git rev-parse HEAD` 为准）。
- 受测 commit：`c5145d78` 工作树 + 本批 T09B 改动；dirty=true（含本批改动、另一会话未提交文件与本机运行数据）。
- `source_fingerprint`：`74321cc82a15bb3566c44ee239c398982d2d0e86ade71b552cd2ca0eb0c2ff43`（同一算法：`git ls-files` 的全部 `*.py` 与 `native/*.h|*.hpp|*.cpp` 加本批新增测试，共 271 个文件的 CRLF 归一化 SHA256 清单哈希）。
- `tools/dev_check.py` 的 `checked_source_sha256`：`61df478d6baa4f602479f23298064b853f58498ba11341e5f9bc8cc5c6f69955`（同一最终源码内容）。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；ruff 0.17.0、clang-format 23.1.3；MSVC x64 与 Creo 12.4.0.0 匹配 Toolkit SDK 可用（**仅用于离线编译**；全程未连接 Creo、未启动 MCP/Creo、未提交 Toolkit 作业）。服务版本入口仍为 0.7.2，未改。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_revolve_axis_report -v` | **Ran 16 tests, OK**（ruff format 后复跑仍 OK） |
| 2 | `.venv\Scripts\python.exe bridge.py build` | exit 0，产出 `build\creo_worker.exe`（mtime 新于 `native/generic.cpp`，确认重编译）；`build/build.log` 仅存量 C4819 codepage 告警，无本批新增告警/错误 |
| 3 | `.venv\Scripts\python.exe -m unittest tests.unit.test_arc_direction tests.unit.test_body_count_semantics tests.unit.test_dev049_profile_replay` | **Ran 75 tests, OK**（T02 dir 契约 29 + T08B 巡检 13 + T07 多环 33，均不回归） |
| 4 | `.venv\Scripts\python.exe tools\test_arc_direction.py` | exit 0，内置复跑 29/29 OK；报告 `build/arc_direction/20261029T002746_0a2966b6/report.json`，SHA256 `3d8671574d5c17fcaab8986b9ef86a5b7acb6e4c72d0d94adaa9d2ae3390a81c` |
| 5 | `.venv\Scripts\python.exe tools\test_dev049_profile_replay.py` | exit 0，offline_cases=3 validated；`original_case_replay=not_possible`（gear10.json/sketch_entities.json 仍缺失）、`replacement_verification=true`；报告 `build/dev049_t05/20261029T002755_7a28275f/report.json` |
| 6 | clang-format 23.1.3 字节一致性 | `native/generic.cpp` 格式化输出与文件字节一致（MATCH） |
| 7 | `.venv\Scripts\python.exe -m unittest discover -s tests`（共同收口全量） | **Ran 1290 tests in 349.423s，FAILED (errors=1)**；唯一错误见下节“网络受限安装夹具” |
| 8 | `.venv\Scripts\python.exe tools\dev_check.py`（共同收口） | exit 1，`unit_tests=failed`（同一夹具）、`native_validation=not_run`、`success=false`；`style_summary` lint 30 / unformatted 16、cpp 33 / python 237（lint/未格式化计数与既有基线一致，**无新增**）；报告 `build/development_check.json` |

第 7/8 项即共同要求的“最后统一执行一次”全量检查，同时覆盖 T09A 与 T09B 的最终源码（T09A 卡提交时该项尚未执行，结果以本表为准）；两任务单测计数不混用不同指纹。

### 网络受限安装夹具（与本次改动无关，如实保留）

`tests/test_installation_validation.py::test_installer_native_failure_leaves_client_config_and_resume_instructions` 在临时沙箱运行 `setup.ps1`，其 pip 阶段需联网拉取构建依赖；当前代理网络受限（T02 卡已记录同类 `ProxyError`/TLS 超时），本次表现为 `subprocess.TimeoutExpired: ... setup.ps1 ... timed out after 90 seconds`。全量 1290 项中其余 1289 项全部通过；**未修改、未跳过、未加基线**规避该用例。

测试覆盖（离线，不实例化 MCP 客户端）：显式 datum 轴实测透传；surface 解析轴 kind 保留；内部中心线回退 source/kind/id；sketch_local 2D 几何显式标注；多中心线计数保留且不猜 id；无中心线零计数无值；不一致实测字段降级 unknown（geometry_known=false/向量缺失/帧非法/维度不符）；非法枚举与 id 归 unknown；非对象块→显式 unknown；length_unit 只透传查询块；缺块不补、不回声请求值；其他操作不被加块；省略/null 轴三态兼容、非法轴仍拒、多中心线草图规则未变（收紧需记版本影响）。

## 未测项与下一步

- 未测（需实机，另按共同契约指派并在唯一 dev 服务串行执行）：显式轴/内部中心线/多中心线的真实建模与 `revolve_axis` 实测值（origin/direction 与独立回转体积对照、revision、`saved_file_reloaded_and_verified=true`、失败回滚基线不变）；`ProFeatureGeomitemVisit(PRO_AXIS)` 对回转特征的实际返回与 `ProAxisSurfaceGet` 分类的实机确认；surface 解析轴（非基准轴特征标签/面归属轴）实机样例；无中心线失败消息原样保留的实机确认。
- 未测：WorkBuddy 黑盒验收；Creo 9/10 独立环境；`populate_profile`（advanced 嵌套）路径无 revolve 回显需求（不适用）。
- 缺材料：无（0.7.0 原始 job/PRT 缺失不影响本批契约与离线用例）。
- 提请 T01 统一收口的描述/文档改动：`creo_revolve` 工具描述与 [REFERENCE_SYNTAX.md](../../REFERENCE_SYNTAX.md) 回转轴节补 `revolve_axis` 结果字段（source/kind/id/frame/length_unit/geometry_known/query_code/resolution 与未知语义）；能力说明同步。本批未直接改工具描述与文档入口。
- 下一步：集成人按“给集成人的冲突文件与接口变化”合并；实机验收前人工确认会话可操作及 BUG-001 条件；T10 决定版本与发布。BUG-083 引用拒绝修复不等于本任务完成，该卡剩余原生非法分支实机验证不受影响。

## 给集成人的冲突文件与接口变化

- 冲突面：`native/generic.cpp` 被 T02/T04/T06/T08B/T09B 共用——本批只新增两个静态 helper、一处 include 与 `extrude_or_revolve` 内两小段（显式轴 id 捕获、结果块写入），未动 sketch/extrude 建弧路径、sketch_edit、hole/round/export、inspection/body 分支；`src/creo_mechdog/operation_results.py` 与 T02 同文件——只新增 revolve 轴归一化函数与 `annotate_native_result` 一处挂接，arc/profile/feature_state 投影不变。
- 接口变化（只增不改）：
  - `revolve` 操作结果新增 `revolve_axis` 块（schema 形态见“结果契约”）；旧作业/失败作业无块不补；`material_removed_mm3`、`length_unit` 等既有字段不变。
  - 结果持久化路径（`generic_bridge` → `annotate_native_result`）自动归一化；compact job 投影不新增字段（本批不动 `bridge.compact_job`）。
  - 准入 schema、工具签名、busy/revision/回滚语义、服务标准输出均未触碰；无版本变更。

## 2026-10-29 实机：回转轴回显三例（驱动 `tools/test_revolve_axis_live.py`）

环境：手动打开的 Creo 12.4.0.0、`auto_start_creo=false`、唯一 dev 服务 0.8.4、`ready/connected=true`；每例一个新建件，挂起预算 180 s，未重提作业。命令：

```text
.\.venv\Scripts\python.exe tools\test_revolve_axis_live.py --live --confirm-session-usable
```

报告：`build/revolve_axis/20261029T230937_a27309f6/report.json`，SHA256 `a8336afbf3c6886813fe46599c468f390a75b1a3a54f55f84e740cc75d9e59d8`，退出码 0，3/3 通过。体积 oracle 由请求几何独立推导：环 π(20²−10²)×10 = 9 424.777961、圆柱 π5²×10 = 785.398163。

| 用例 | job / 模型 / rev | 体积 | `revolve_axis` 实测 |
| --- | --- | --- | --- |
| `internal_centerline`（草图中心线，未给 axis） | `1daefcb3d95241a4bebb8232433d1b47` / `ef9f986cb7e7419085bb0e31bb91452f` / 1 | 9 424.777960 769 377（误差 0） | `source=internal_centerline`、`kind=section_centerline`、`frame=model`、`origin=[−6.1e−16,−5,0]`、`direction=[1.2e−16,1,0]`、`geometry_known=true`、`query_code=0`、`resolution.section_centerline_count=3` |
| `explicit_datum_axis`（基准轴 `x_axis`，id 52） | `00b4646420d7480394c333284e257469` / `e3db09a5490a48b4a173396ce1b15fa2` / 1 | 785.398163 397 448（误差 0） | `source=explicit`、`kind=datum_axis`、`id=52`、`origin=[10,0,6.1e−21]`、`direction=[1,0,0]`、`frame=model`、`geometry_known=true`、`resolution.axis_surface_query_code=-4`（E_NOT_FOUND ⇒ 基准轴归类） |
| `no_centerline`（无中心线、无 axis） | `0921884a7f6e44e89741b9c224de7935` / `e260db19561347f894289f4d386c9133` / 0 | 无 | **无 `revolve_axis` 块**；失败原文含“must contain a centerline, or an explicit axis must be supplied”、`toolkit_code=-1`、`failed_stage=execute_revolve`、`rollback_succeeded=false`（新件无基线，与 BUG-012 语义一致） |

结论：

- 两条成功路径的轴**几何正确**：独立体积 oracle 与回显方向/位置一致；显式轴的 `id=52` 与 `inspection.datum_axes[0].id` 相同，origin/direction 逐位一致；内部中心线回退给出的是模型坐标的 +Y 轴（x=0、z=0 上的点）。
- 失败路径不产生块，符合“失败作业不输出轴回显”。
- **回显局限（本轮新发现，未修）**：`internal_centerline` 用例里用户只画了 1 条中心线，`resolution.section_centerline_count` 实测为 **3**，于是 `id` 只能为 `null`。计数把草图参考几何（两条参考线）也算了进去，既高估了“多中心线歧义”，也让 `id` 分支在正常草图上永远走不到。几何不受影响（frame=model 已给出方向），但“选了哪一条”的可观测性没有兑现。需要后续按真实 section 实体类型过滤参考线后再给 `id`，本轮只记录、不改代码。
- `frame` 的实测口径与卡面文字需要对齐：卡面把 `sketch_local` 列为内部中心线的形式，实测在能取到回转特征自身轴时 **优先给 `model`**，`sketch_local` 只在特征轴不可读时作为回退。本卡以实测为准，代码注释同样如此。
- 未测：多中心线草图（用户真的画 2 条以上）、`surface` 解析轴样例（非基准轴特征标签）、`ProAxisSurfaceGet` 非 E_NOT_FOUND 分支、显式轴解析失败时的 unknown 分支、保存重载、Creo 9/10。

## 2026-10-30 中心线计数修复（离线阶段，沿用 FEAT-008，不新增工作 ID）

日期：2026-10-30（Asia/Shanghai）。分支：`codex/dev051-feedback070`，基线 HEAD `3851963`；本批改动未提交（按派发约定由派发方统一提交）。任务来源：[DEV051 续派表](DEV051-CONTINUATION-TASKS-2026-10-30.md)「可单独指派的横切任务」T09B 行、[当前完善计划](../superpowers/plans/2026-10-30-feedback-072-to-085.md)任务 6。本轮仅离线：未连接 MCP/Toolkit、未启动 Creo、未改版本、未合 main、未 push、未发布。

### 根因（带文件行号，实测证据 + SDK 语义，非数量猜测）

缺陷现象：10-29 实机 `internal_centerline` 用例只画 1 条用户中心线，`resolution.section_centerline_count` 实测 **3**（报告 `build/revolve_axis/20261029T230937_a27309f6/report.json`），`id` 因此恒为 null。

身份链路，每条 section 线元素的真实来源：

1. `sketch()` 建草图时向 section 投影**系统参考**：方向参考平面投影 `ProSectionEntityFromProjection`（`native/generic.cpp:1420`，必有一次）+ 锚点平面/基准轴投影（`native/generic.cpp:1443` 或 `:1467`，标准情形恰一次）——即正常草图恰含 **2 条系统投影参考**。
2. Creo 将这些投影参考以 center-line 类型实体存入 section（`Pro2dLinedef` 覆盖 `PRO_2D_LINE, PRO_2D_CENTER_LINE`，`Pro2dEntdef.h`）；10-29 实测 3 = 2 系统投影 + 1 用户线，与本链路精确吻合。
3. 计数循环只按类型过滤 `def->type == PRO_2D_CENTER_LINE`（修复前 `native/generic.cpp:1899-1911`），**缺少本仓库其他 section 遍历都有的投影/构造过滤**（对照 `native/generic.cpp:1203-1211` 的 `ProSectionEntityIsConstruction`/`ProSectionEntityIsProjection`、`native/advanced.cpp:195-199` 同模式）——这就是错的那个过滤条件。

SDK 语义（本机 Creo 12.4.0.0 匹配 SDK `ProSection.h`）：`ProSectionEntityIsProjection` 判定实体是否"created by projection"，即系统参考的权威身份测试。用户画线 vs 系统参考由此区分，不靠数量推断。

### 最小修复

`native/generic.cpp`（21 行增量，clang-format 23.1.3 字节一致）：

- 计数循环内对每个 `PRO_2D_CENTER_LINE` 实体补 `ProSectionEntityIsProjection` 探测（现 `native/generic.cpp:1908-1926`）：`code==PRO_TK_NO_ERROR && is_projection==TRUE` → 系统参考，跳过；探测失败无法分类时**保留计数**（不静默丢弃）；并写 `SECTION_CENTERLINE_PROBE entity=… code=… is_projection=…` 原生日志供实机诊断。
- 语义收紧说明（注释，`native/generic.cpp:1883-1887`）：计数只含用户中心线；≥2 条真实用户线时"用了哪根"不可判，`id` 保持 null，调用方必须显式给轴——与既有"不武断选第一条"行为一致，未新增准入收紧、未改 schema/回退。
- 未改：`validate_revolve_axis` 准入、显式轴分支、sketch/extrude 建弧路径、`operation_results.py` 归一化白名单（按窗口边界未触碰）、`native/advanced.cpp`、schema、server。

### 新增回归

`tests/unit/test_revolve_axis_report.py`（16→19 项）新增 `CenterlineAccountingContract`：

1. `test_single_user_centerline_count_one_with_entity_id`——修复后形态：count=1 + id=草图 section 实体 id，原样透传（ID 来源锁）。
2. `test_inflated_reference_count_is_reported_verbatim_never_reinterpreted`——10-29 缺陷形态（count=3、id=null）必须逐字透传：投影层不得缩成 1、不得发明 `id=第一条`。
3. `test_two_true_user_centerlines_stay_ambiguous_without_a_guessed_id`——真 2 条用户线：count=2 保留、`id=null`、不猜几何（歧义不误判为单线）。

`tools/test_revolve_axis_live.py`（离线契约 + 实机判定同步收紧，离线模式 exit 0）：

- `internal_centerline` 期望新增 `section_centerline_count=1` 与 `sketch_entity="spin_centerline"`；实机判定补：计数膨胀即失败（系统参考不得计入）、`id` 必须等于计划结果 sketch 操作 `entity_ids['spin_centerline']`（ID 来源）、显式轴用例 `id` 必须等于 `inspection.datum_axes[0].id`。
- 成功用例新增**保存重载阶段**：`creo_save_model`（带 `expected_revision`）→ 校验作业 `succeeded` 且 `result.saved_file_reloaded_and_verified is True` → 重载后快照体积不变；显式轴用例进一步要求重载后 `inspection.datum_axes` 同 id、origin/direction 逐项 1e-6 一致（同一轴线可再定位）。内部中心线用例的 inspection 不列出回转特征自身轴（10-29 实测 `datum_axes=[]`），故该用例的轴再定位记 `axis_relocation_after_reload="not_observable_via_inspection"`，不猜通过。
- 离线报告契约新增 `centerline_accounting` 块（count 规则、ID 来源）；本次离线报告 `build/revolve_axis/20261030T092522_401c7896/report.json`。

### 命令与真实结果（本机 Windows 11 x64 / Python 3.12.14 venv / Creo 12.4.0.0 匹配 SDK 仅离线编译）

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_revolve_axis_report -v` | **Ran 19 tests, OK**（16 旧 + 3 新） |
| 2 | `.venv\Scripts\python.exe -m ruff check <两文件>` + `ruff format --check` | 全部通过；format 后复跑 MATCH |
| 3 | clang-format 23.1.3 vs `native/generic.cpp` | 字节一致（MATCH，257793 bytes） |
| 4 | `.venv\Scripts\python.exe tools\test_revolve_axis_live.py`（离线） | exit 0；报告 `build/revolve_axis/20261030T092522_401c7896/report.json` |
| 5 | `.venv\Scripts\python.exe bridge.py build` | exit 0，`build/creo_worker.exe`（09:25:44）新于 `native/generic.cpp`（09:20:30）；`build/build.log` 仅存量 C4819 告警，无新增错误；`native/advanced.cpp` 未报错（T13 窗口当时未改动它） |
| 6 | `.venv\Scripts\python.exe -m unittest tests.unit.test_revolve_axis_report tests.unit.test_arc_direction tests.unit.test_body_count_semantics tests.unit.test_dev049_profile_replay` | **Ran 94 tests, OK**（T02 弧/T08B 巡检/T07 回放均不回归） |
| 7 | `.venv\Scripts\python.exe -m unittest discover -s tests` | 第一次（与 T13 窗口并发同工作区）：**Ran 1482 tests, FAILED (errors=6)**，6 错全部在 `tests/unit.test_assembly_bundle.test_unresolved_identity_never_marks_complete`（"native_bundle already exists for this job"）——该用例属于 T13 窗口当时正在修改的 `assembly_bundle.py`/`test_assembly_bundle.py`（本批开始时干净、中途变为 modified），且该模块单独复跑 9 项 OK，判为瞬态并发冲突、与本批无关；空闲复跑（`build/t09b_full_unittest2.log`）：**Ran 1482 tests, OK**，exit 0 |

### 未测项与实机待验步骤

未测（离线不可达）：一切真实 Creo 行为——投影过滤的实机计数、`ProSectionEntityIsProjection` 在 `ProFeatureSectionCopy` 重读 section 上的实际返回、真多条用户线（服务准入限一条，**无法经本服务 MCP 构造**，需外部 Creo 手工草绘模型）、保存重载、Creo 9/10、WorkBuddy 黑盒。修复前 10-29 实机三例的通过结论保留其历史时点，不代表修复后状态。

实机待验（按共同契约另指派；唯一 `MCP_CREO_MechDog_dev` 串行，满足 BUG-001 会话条件）：

1. `.\.venv\Scripts\python.exe tools\test_revolve_axis_live.py --live --confirm-session-usable`（驱动已内置以下断言）：
   - **一条线=1**：`internal_centerline` 用例 `resolution.section_centerline_count == 1`（旧缺陷会得 3）；原生日志应出现 `SECTION_CENTERLINE_PROBE` 行，2 条系统参考 `is_projection=1` 被剔除。
   - **ID 来源**：`revolve_axis.id == sketch 结果 entity_ids['spin_centerline']`；显式轴用例 `id == inspection.datum_axes[0].id`。
   - **轴帧**：既有 origin/direction/frame 断言保持（model 或 sketch_local 均须与独立体积 oracle 一致）。
   - **保存重载**：每成功用例真实 `creo_save_model` 且 `saved_file_reloaded_and_verified=true`、重载后体积不变；显式轴重载后同 id 同几何（同一轴线可再定位）。
2. **真多线不误判**：在 Creo 中手工绘制含 ≥2 条用户中心线的草图并入会话（或采用外部文件收养），对其实际提交 revolve——预期 `section_centerline_count≥2` 且 `id=null`，不静默选第一根；随后用显式轴完成同几何。若无法取得该夹具，如实记"真多线未测"。
3. 记录 job/model/revision、体积 oracle、原生 `SECTION_CENTERLINE_PROBE` 日志行、重载与适用回滚；首次挂起/unknown 即停，保留现场。

### 给集成人的冲突面

本批只改 `native/generic.cpp`（`revolve_axis_report` 内部回退分支 + 两段注释，约 21 行）、`tools/test_revolve_axis_live.py`、`tests/unit/test_revolve_axis_report.py` 与本卡；未触碰 `native/advanced.cpp`、`server.py`、`schema.py`、`operation_results.py`、钣金/弧方向驱动及任何台账。接口形态不变：`revolve_axis.resolution.section_centerline_count` 语义修正为"仅用户中心线"，无字段增删、无版本影响。
