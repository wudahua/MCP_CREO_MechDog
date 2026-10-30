# 0.9.0 后续任务与分窗派发 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. 用户自行指定 agent 或对话窗口；未获指派不得自行启动其他任务。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 0.9.0 已交付范围之外的反馈建立可独立指派、验证与交接的任务包。

**Architecture:** 保留现有 stdio → Python 调度/桥接 → C++ Toolkit 单通道架构。新业务逻辑遵循现有包内模块边界，几何证据来自原生；同文件修改、原生构建及实机串行，由用户指定集成人统一交付。

**Tech Stack:** Windows x64、PowerShell、Python 3.12+/unittest、C++17/MSVC、Creo 12.4.0.0/匹配 Toolkit SDK；Creo 10 本次兼容问题做定向 SDK 验证。

**Spec:** [已确认基线与范围](../specs/2026-10-30-post090-feedback-design.md)；[0.9.0 版本说明](../../RELEASE_NOTES_0.9.0.md)；[发布记录](../../validation/RELEASE-0.9.0.md)。

## Global Constraints

- 日期：2026-10-30，Asia/Shanghai；本次核对源码 0.9.0、HEAD `d287499`。执行者重新检查实际提交、dirty 状态和依赖，不把静态计划当实时状态。
- BUG-032/T03 板厚 5/5 与 FEAT-031/T13 两段式回导已闭环，作为回归基线。T05 的失败触发条件已定；T09D 已有基准；不追溯变成 0.9.0 发布阻断。
- **本轮只新增设计和派发文档。N00—N13 全部待用户指派，未启动实现或实机。** N00—N13 是派发编号，不是另一套工作台账。
- `docs/BACKLOG.md` 是唯一工作台账；既有问题复用原 ID。DEV-052、BUG-090、BUG-091、FEAT-051 是本次查无占用的**建议编号，尚未登记**，由 N00 再核号入账；发生占用则先更新本表映射，不能复用已有 ID。
  - **2026-10-30 N00 已核号登记（映射不变，四项均未被占用）**：DEV-052、BUG-090、BUG-091、FEAT-051 已按 `docs/templates/WORK_ITEM.md` 入账并各占 [BACKLOG](../../BACKLOG.md) 一行；状态分别为 开发中 / 待复现 / 待复现 / 待规划。**外部 0.8.5 报告建议用「BUG-090」承载会话挂起事故，因该编号已核给 Creo 10 SDK 兼容（N01），会话事故改用 BUG-091（N02）**——见 [归档 MAPPING](../../validation/feedback-0.8.x-2026-10-30/MAPPING.md)。
- 默认只做离线阶段。读文件、SDK 研究、源码实现、单元/离线驱动及不连接 Creo 的构建均可按指派范围执行；实机需要用户点名对应阶段并确认当前会话条件，不因过去已通过而自动连接。
- 只用 `MCP_CREO_MechDog_dev`，路径 `E:\Projects\MCP_CREO_MechDog`。遵守 BUG-001 会话限制，不擅自启动/结束/重启 Creo、清 unknown、故障注入或重提已受理作业。
- 所有 Creo 实机由一个负责人串行执行。busy 立即拒绝、不排队、不重试；已受理只轮询。出现 unknown/挂起停止新提交并保留原件。
- 同一 checkout 不允许多窗口同时切分支或修改同文件。`native/advanced.cpp`、`native/generic.cpp`、schema、共享结果投影与当前入口均有冲突面；原生构建也不能与实机或另一构建并行。
- 以 mm、degrees、合法小写标签及既有 revision/回滚/保存重载契约工作。Python 不模拟 Creo 几何。公共响应沿用 32 KiB 及分页/有界投影规则。
- 历史 `docs/validation/` 原件逐字节保留，不覆盖其他会话未提交改动，不提交生成物、SDK 或许可，不重建风格基线规避检查。
- 每个执行窗只提交本任务明确路径，不用 `git add .`；开发提交按用户指派处理，不自行修改版本、合 main、push 或发布。N13 是未来交付职责，本轮并未授权执行。
- WorkBuddy 若另行指派，只使用公开 MCP 黑盒；本表开发者命令不能复制成 WorkBuddy 的源码/脚本任务。

## Review Focus

1. SDK 没有新函数声明时仍编译失败，或回退路径把请求板厚当实测值：N01 有/无声明与未知厚度拒绝回归。
2. 批处理前面操作有体积变化、后面失败后仍显示已提交：N04 覆盖 rolled_back、not_executed 与 unknown，不由 Python 升级结果。
3. 输入 profile 闭合而求解后截面不符，诊断阈值被误当内核焊接规则：N03 比较两阶段端点并保留原码。
4. 存在 `--live` 参数却没有真正实机实现，或回读缺失仍判通过：N05 先完成正式探针；N07—N10 核对 live 路径及严格判定。
5. 预览文件存在但图像内容错误，或文件未确认而用 job succeeded 判成功：N11 将文件写出与内容分别验收。

## 派发总表

| 编号 | 任务及归属 | 默认可做 | 主要依赖 | 交付物 |
| --- | --- | --- | --- | --- |
| N00 | 原件归档、登记、当前状态校正；**DEV-052（已登记）** | 文档/离线 | 无 | 7 份原件与映射、新 ID 入账、更新的当前入口 |
| N01 | Creo 10 SDK 兼容；**BUG-090（已登记）** | 实现/单元/SDK 构建 | N00 登记；共享源码写入时段 | 三处调用统一兼容路径、定向证据 |
| N02 | 会话挂起/退出调查；**BUG-091（已登记）**，关联 BUG-085 | 离线调查 | N00 登记 | 独立时间线、证据缺口、恢复/取证条件 |
| N03 | 近容差端点诊断；BUG-049 | 离线夹具/诊断 | N00 映射；原件可缺 | 可复现夹具、求解前后差异、最小修复结论 |
| N04 | 细节特征结果回报；**FEAT-051（已登记）** | 实现/单元/SDK 构建 | N00 登记；共享源码时段 | 原生体积差、方向及引用应用证据 |
| N05 | 钣金原生诊断、trim 探针；FEAT-014/T05 | 先离线 | N01 涉及的 advanced.cpp 变更接入；T03 基线 | 正式诊断入口、trim 量测与内部机理证据 |
| N06 | 钣金角部最小实现；FEAT-014/T05/T11 | 条件式设计/实现 | N05 明确机理及用户选择的具体方案 | 有限角部能力及四壁/释放验收 |
| N07 | 弧方向余项实机；FEAT-034/T02 | 离线预检；点名后实机 | 受测源码固定、当前会话可用 | 编辑/下游/非法输入/重载证据 |
| N08 | 回转中心线计数实机；FEAT-008/T09B | 同上 | 同上；真多线需外部夹具 | 用户中心线计数、ID、实际轴与重载 |
| N09 | 组件标签余项实机；FEAT-023/T09A | 同上 | 同上 | 重载关联、删除重插不误指 |
| N10 | 沉孔/沉头余项实机；FEAT-035/T12 | 同上 | 同上 | 盲孔/方向/尺寸编辑/回滚六例 |
| N11 | 预览诊断与原件回补；BUG-088/066，T06/T07/T08C | 材料核对/离线 | N00 映射；实机需会话可用 | 空件预览与内容分项结论、缺件清单 |
| N12 | 性能补测与热点调查；FEAT-033/T09D，调查按 P3 | 离线口径核对 | 固定受测源码、稳定会话 | large 重复基准及可观测阶段结论 |
| N13 | 所选范围集成、文档与新版本发布；**DEV-052（已登记）** | 先汇总交接 | 用户选择范围及各依赖已交接 | 定向回归、版本、Release、附件 SHA256 |

### 可并行与必须串行

- N00 登记前，各窗仅先只读研究。N00 完成后，N02 离线调查、N11 查缺及各实机任务的离线预检可与代码研究并行；这些窗口不共同改台账。
- 同一 checkout 的 N01 → N05 → N06、N03 ↔ N04 均有共享源码，写入应错开；N04 还触碰 advanced.cpp，需加入同一文件调度。若使用独立工作区，由指定集成人接入后才构建实机候选。
- N07/N08/N09/N10 可分别交给不同 agent 准备，但实机只能由一个负责人逐项运行。N01/N04/N05/N06/N11 的实机也进入同一时段安排。
- 编译、替换 worker、切换受测源码与实机互斥。取得 N05 实机证据后再派 N06；没有确定机理时可交付诊断阶段，不能虚报四壁实现完成。
- N12 使用固定源码，不与建模/构建/重载等负载混跑。N13 不等待无关缺件或未选范围，但所选范围的失败/未验必须明确披露。

## 共用命令、记录与指派方法

命令在仓库根目录 PowerShell 执行，统一使用 `.\.venv\Scripts\python.exe`。代码任务完成对应专项后，按实际改动运行 `tools\dev_check.py --work-item <固定ID>`；原生改动另跑 `bridge.py build`。纯文档核对不为凑步骤运行全量单测。

没有 `--live` 的默认离线驱动不能算原生验收；有 `--live` 也先读当前实现。下列实机命令只供用户指定后的负责人执行，**本计划没有执行任何一条**。

所有报告写唯一运行目录，拒绝覆盖；为历史默认固定输出路径的驱动显式给新 `--output`。一次任务结束提交：任务编号/固定 ID、依赖提交、文件、commit/dirty/受测源码指纹、环境、命令与退出码、报告路径/SHA256、通过与失败、原始错误、未测/缺件；实机加输入、job/model/revision、几何/参数、保存重载、回滚及后续合法操作。没有公开查询的内部事实不要求 WorkBuddy 补齐。

**复制给新窗口的通用前缀：**

```text
工作目录 E:\Projects\MCP_CREO_MechDog。读取 AGENTS.md、docs/DEVELOPMENT.md、docs/superpowers/specs/2026-10-30-post090-feedback-design.md 和 docs/superpowers/plans/2026-10-30-post090-task-dispatch.md。
只执行我点名的 Nxx 及阶段，先读取对应工作卡和最后的有效证据，以用户确认的0.9.0最终账为基线。检查N00登记、依赖提交和当前dirty状态，保留其他窗口修改。
未写“实机/完整阶段”时默认离线，不创建MCP客户端或连接Toolkit；不自行启动、结束或重启Creo、清unknown、故障注入、改版本、合main、push或发布。不得切换其他窗口正在使用的分支或覆盖受测执行器。
按本任务步骤交付实现或调查结果、适用验证、未测范围和可接续的交接报告；只做本任务，不自行扩大范围或启动其他窗口。
```

实际指派时把下面各任务的短指派语接在该前缀之后。用户已选择自己分配窗口，本文件不创建任何 Codex 对话。

## N00：原件归档、唯一台账登记与当前状态校正

**归属：**建议 DEV-052；文档任务。**Files:** 新建 `docs/work-items/DEV-052.md`、`BUG-090.md`、`BUG-091.md`、`FEAT-051.md`（核号后）；归档目录 `docs/validation/feedback-0.8.x-2026-10-30/`；修改 `docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、`docs/work-items/DEV-051.md` 当前入口及受影响卡首页、`docs/development/RELEASING.md`。不改历史验收原件。

**Interfaces:** 消费本设计和用户最终账；产出已登记的固定 ID、7 份原件的 manifest/MAPPING、各任务可引用的基线。DEV-052 只汇总本次接续，既有 ID 不重复新增。

- [x] 核实上述建议编号仍未占用；按模板登记目标、范围、状态、验收、环境。BUG-090/091 当前版本无本轮复现则写待复现，FEAT-051 写待规划/设计；不填已修复。**（2026-10-30 N00 完成：四项编号均未被占用，已按模板登记；状态 开发中 / 待复现 / 待复现 / 待规划）**
- [x] 从 `C:\Users\Administrator\Downloads\0.8.x` 原样复制全部 7 个 Markdown，保留原名/字节并逐件核 SHA256；建立源文件名、大小、hash、反馈环境、报告版本清单。**（2026-10-30 N00 完成：7/7 SHA256 逐件一致；清单见 [manifest.json](../../validation/feedback-0.8.x-2026-10-30/manifest.json)）**
- [x] 按七份报告实际章节/建议逐项映射：已在 0.9.0 闭环、已有余项、新 ID、推测或记录更正。缺附件列名字、用途、来源与现有检索范围，不把 Markdown 引用当成附件已存在。**（2026-10-30 N00 完成：见 [MAPPING.md](../../validation/feedback-0.8.x-2026-10-30/MAPPING.md)，含缺件汇总表）**
- [x] 以最终账修正当前入口、DEV-051 首页/当前矩阵及 T03/T13/T05/T09D 行；早期阶段加日期限定或跳转，不改写历史通过/失败记录。修正 RELEASING 当前版本。**（2026-10-30 N00 完成）**
- [x] 校验相对链接、固定 ID 唯一性和受影响分类统计；回读本派发表编号映射并交接。以后每个实现窗只更新自己的卡，主台账由指定文档/集成窗串行回填。**（2026-10-30 N00 完成：相对链接全通；BACKLOG 130 行 = 130 个唯一 ID；分类统计已回填）**

**完成标准：**7/7 hash 一致；新 ID 真实入账；当前入口不再同时出现“0.9.0 已交付”和“T03/T13 未验/未发布”的冲突。只完成规划登记，不把技术问题置为完成。

**短指派语：**“执行 N00 文档阶段：归档七份0.8.x反馈，核号登记下一批，按0.9.0最终账校正当前入口，给后续窗口固定ID与证据映射；不实现、不实机、不提交发布。”

## N01：Creo 10 SDK 函数兼容

**归属：**建议 BUG-090，P1；关联 BUG-032、已完成 BUG-033（仅复用探测机制，不重开）。**Files:** `native/advanced.cpp` 三处板厚读取、`tools/generate_constants.py`、`tests/unit/test_generate_constants.py`、`tests/unit/test_sheetmetal_contract.py`、`docs/COMPATIBILITY.md` 和本卡；如 SDK 读取助手独立成头文件，登记到现有源码身份/打包覆盖范围。

**Interfaces:** 消费 T03 的参数驱动与真实回读契约；产出匹配 SDK 的统一板厚查询，真实值/查询码/是否可知，不用请求值补结果。0.9.0 首壁同步前后硬校验保留。

- [ ] 分别记录外部 0.8.2/0.8.5 的 C3861 证据、当前三处调用和本机可获得 SDK；不能把旧失败改写为当前0.9.0实测。
- [ ] 在 `test_generate_constants.py` 补有/无函数声明夹具，覆盖注释或同名文本不构成可调用声明、既有两个常量探测不退化；运行专项先确认缺能力守卫的失败。
- [ ] 核对匹配 SDK，选择真实参数/维度等可验证读取路径并统一三处使用，生成函数能力宏或等效编译守卫。SDK 无可靠读数时，首壁明确失败；仅信息字段可降级未知，不能使未校验板厚静默成功。
- [ ] 补回归：未知板厚不能通过；1.0请求/3.71实读不通过；1.0实读通过；SDK缺API时编译单元不引用它。运行 `-m unittest tests.unit.test_generate_constants tests.unit.test_sheetmetal_contract -v` 和适用 dev_check。
- [ ] 串行 `bridge.py build`；本机无 Creo10 SDK 则定向编译记未验，提供外部复验输入，不复制他机 constants.inc。
- [ ] 被指定实机后，跑 `tools\test_sheetmetal_contract.py --live --confirm-session-usable` 并做受影响折边回归；补兼容说明和原始回读/几何/重载证据。

**完成标准：**代码不再无条件引用缺失API；新旧SDK路径均有有意义证据，T03防错不退化。离线交付与Creo10真实SDK编译/运行验收分别标状态。

**短指派语：**“执行 N01 离线实现和SDK构建，解决三处板厚API兼容，保留0.9.0真实板厚硬校验；无Creo10SDK明确未验，不做Toolkit连接。”

## N02：会话挂起、退出与 BUG-085 接续调查

**归属：**建议 BUG-091，P1；关联 BUG-001/BUG-085，不自动重开已关闭旧案。**Files:** 新卡与 `docs/development/BUG091-OFFLINE-EVIDENCE-2026-10-30.md`（执行日变化则用实际日期）；读 BUG-001/085、recovery、BUG085-OFFLINE-EVIDENCE、已有作业/进程/Windows事件原件。

**Interfaces:** 消费可追溯的历史证据，产出分现场时间线、同根判据、缺证清单和受控取证前置条件。调查任务不产出“会话已恢复”的推断。

- [ ] 将0.6.1断连、10/29挂起、重启后退出等观察分开，逐条列来源/时间/环境，不把今天进程快照补作历史事实。
- [ ] 对齐UTC与Asia/Shanghai、Creo/worker/nmsd进程身份、构建/替换时点、作业阶段与终态、锁与unknown状态；缺失直接记缺失。
- [ ] 对照 exit20/-4 的失败映射，列相同/不同/证据不足的依据；不从同码推同根，不新增重连、重试或杀进程方案。
- [ ] 提交下一次人工核对可操作条件、允许的最小取证动作和立即停止条件；不实际探测session_status或新建MCP客户端。
- [ ] 更新本卡调查结论和后续所需材料，交给用户指定会话负责人。若发现确定的代码根因，给出最小修复设计，另获指派后实现。

**验证：**只核证据链接/hash/时间线与范围，纯文档不跑全量单元、不构建、不实机。**完成标准：**每项结论有原件或明确缺失，独立开放事故卡可接续；根因证据不足时保持未定。

**短指派语：**“执行 N02 离线调查，分开挂起/断连/退出现场，交付时间线、缺证及会话取证条件；不探测、不恢复、不清保护、不实现推测修复。”

## N03：近容差端点与 profile/native_section 差异

**归属：**BUG-049，P1数值边界子项。**Files:** `src/creo_mechdog/profile_diagnostics.py`、`src/creo_mechdog/operation_results.py`、`native/generic.cpp` 的 section_profile_summary/草图/切除诊断、`tools/test_dev049_profile_replay.py`、对应单元；需要新夹具时创建 `tools/test_profile_endpoint_diagnostics.py`、`tests/unit/test_profile_endpoint_diagnostics.py`。

**Interfaces:** 消费 N00 原件/缺件表；产出原输入到求解后实体的差异记录，含实体名/ID、阶段、来源、gap、查询码、计数口径。已有 Python 详细 items 先查公开投影，不重复造分析器；原生诊断只做有界样本并报告总数/截断。

- [ ] 查原 `gear10.json`、精确闭合对照及前置模型；拿不到则固定直线/弧混合替代夹具，明确不是原案回放。
- [ ] 补精确闭合、0.5/0.77/1.0/1.2×1e-6 mm 间隙和真实开链对照；校验输入几何与独立面积/体积预期，记录 dimensioning 模式。常量是实验取样，不是新准入阈值。
- [ ] 测试锁定：Python输入分析/native截面诊断分别标来源；缺原生查询不填成功；投影保留有界实体/gap信息；样本截断不丢总数。先跑新增单元确认当前缺口。
- [ ] 在匹配SDK核对求解前后实体端点/弧心半径/约束与维度，最小补诊断；1e-4输入闭合、1e-9精确阈值和1e-6诊断聚类均不宣称是内核焊接容差。
- [ ] 运行专项/默认离线夹具、dev_check与原生构建。若因果已证，给最小修复及回归；涉及自动吸附、改变几何或新输入参数则先交具体方案，不擅自实现默认行为变化。
- [ ] 被指定实机后核草图、切除、失败原码、回滚/revision/恢复合法操作和保存重载；保留5/10环正例。缺原件与原案未关闭继续明示。

**完成标准：**至少能定位到阶段/实体/gap或明确不可观测；诊断任务完成不等于原BUG关闭。不得宣称“两环上限”或用调大阈值掩盖失败。

**短指派语：**“执行 N03 离线阶段，建立近容差最小夹具和求解前后端点诊断，核公开投影是否裁掉已有详情；不默认吸附或放宽容差，根因不足则交调查而非猜修复。”

## N04：round/chamfer/draft 的结果可观测性

**归属：**建议 FEAT-051，P2；新结果契约需在本卡明确。**Files:** `native/generic.cpp` generic_round/execute_operation_body/质量属性，`native/advanced.cpp` generic_draft，`src/creo_mechdog/operation_results.py`、实际结果投影入口、`server.py`工具说明；新建 `tests/unit/test_detail_feature_observation.py`、`tools/test_detail_feature_observation.py`（默认离线，live双开关），复用 `tests/unit/test_t02_operation_results.py`。

**Interfaces（本任务建议契约，写入前与既有投影核对）：**原生在相应 `result.operations[]` 增加 `volume_before_mm3`、`volume_after_mm3`、`material_delta_mm3=after-before`；`material_measurement{status,before_query_code,after_query_code}`，status 为 measured/unknown/not_applicable，未知值为null。`draft_geometry` 记录实际引用/flip/角度/方向及source/query_code，不能回读的字段为null；`reference_application` 分开 requested_set_count 与可由原生树证实的 applied_set_count/source/query_code。输入不变、默认材料方向不变，旧 material_removed_mm3 字段不改义。

- [ ] 对照外部11°圆柱案例与当前实现，冻结字段/单位/未知规则及compact/full透传，留有界引用样本；多面拔模不强塞一个无法成立的全局“内收/外扩”。
- [ ] 补有意义回归：真实原生块透传、缺查询保持null、每操作一条结果、后续失败时先前变化标rolled_back、not_executed无伪造读数，公共响应预算保持。
- [ ] 在原生操作边界取得有效before/after，优先复用已有检查，不每操作额外做两次全模型inspection。质量属性查询失败保原码；Python只透传，不推导几何。
- [ ] draft回读实际参考/参数和可证向量；round/chamfer读取实际原生集合或引用应用证据，输入数量、全模型边数差不能冒充命中。无法取得应用数明确未知。
- [ ] 建立凸/凹圆角、三组face-pair倒角、draft flip双向、缺省/显式pull、批中途失败的夹具；单位覆盖mm/in/混合与未知，检查差值与独立几何预期。零差值如合法就报告零，不新增无依据拒绝。
- [ ] 专项、dev_check、SDK构建后，被指定实机再运行新驱动 `--live --confirm-session-usable`，逐例重载/回滚并比较额外查询成本。若提出 expected_material_effect 等新输入，另交方案，不夹带实施。

**完成标准：**调用方能区分实测材料变化、实际方向/引用证据和未知结果；成功不被误读成符合所有设计意图，回滚不被报告为已提交。

**短指派语：**“执行 N04 离线实现与SDK构建，为圆角/倒角/拔模补原生逐操作体积差、方向与应用引用证据；保持输入与默认行为，覆盖unknown和批回滚，不用请求回显冒充实测。”

## N05：钣金内部诊断与 end_trim_mm 实测入口

**归属：**FEAT-014/T05，P2。**Files:** `native/advanced.cpp` 折边失败取证，`tools/test_sheetmetal_box_live.py`、`tools/test_sheetmetal_relief.py`、`tools/sheetmetal_live.py`、`tests/unit/test_sheetmetal_box_live.py`、T05/T11卡。**重要现状：**现有 box 驱动即使同时给 live 双开关仍主动 exit 2；10/30三组实机来自未入库的build一次性探针。

**Interfaces:** 接收已闭环 T03 和 N01 的兼容修改；产出可复现的正式探针、trim实际含义、失败内部机理和候选方案对照，交 N06。失败原始码、邻接面/边、元素树与回滚证据有界保存，未知几何量留null。

- [ ] 保留真1mm基线 `plane=XZ, depth=232, thickness=1`，核参数/几何/保存重载；需要的green/white面距作为本诊断场景量测，不重开T03。
- [ ] 将三组一次性探针对照固化到正式驱动：−Y独立、+X→−Y、+X→−X→−Y；每组新件，按最新inspect选边。离线默认无连接，双开关与当前会话核对后才进入live。
- [ ] 回归锁定缺一个开关不连接、输出不覆盖、未知测量不判通过、第三壁失败不误作成功；完成live实现前不删除原有拒绝守卫。固定输出分阶段持久化。
- [ ] 在自由边实测无trim与正trim的跨度/位置/体积，确定是否链端setback；未证先不用于角部归因。
- [ ] 增加原生边端/邻接bend/面类型、截面位置与特征错误诊断。比较自由边及单/双端相邻，区分“已知触发条件”与截面越界/相邻料重叠等内部假设，不直接写corner规则。
- [ ] 离线单元/构建通过且被指定实机后，用完成的新正式box入口串行探测；记录原码、status/几何、回滚/revision、可量几何与未定项，提交给N06的方案依据。

**命令：**当前可运行离线 `tools\test_sheetmetal_box_live.py`；未来新live入口完成并通过守卫测试后才用其 `--live --confirm-session-usable`。现有relief驱动同双开关可做其已覆盖场景，不能代替新增trim/机理探针。

**完成标准：**正式驱动可重复取得有效诊断，trim语义有实测或明确未证；N06只有在机理证据足以支持具体方案后启动。任务不是四壁能力实现。

**短指派语：**“执行 N05 离线诊断和正式探针准备，保留T05已证触发条件，补trim量测及内部失效取证；现有box live会拒绝，先补真实入口和守卫，不直接实现corner relief。”

## N06：按证据实现有限角部能力并闭环

**归属：**FEAT-014/T05/T11。**Files:** `native/advanced.cpp`、必要的包内schema/`server.py`参数薄层、`capabilities.py`、上述box/relief驱动及单元、FEAT-014卡。**依赖：**N05诊断证据、用户选择的具体方案；未满足可先读SDK，不改猜测性几何规则。

**Interfaces:** 输入N05的失败机理与实测trim；产出有限且明示支持范围的角部处理。不能以“明确拒绝”交付冒充四壁支持；若当前SDK仍无法支持，交限制/调查结论并保持功能开放。

- [ ] 按证据给出截面/引用修复、corner relief或miter等可行方案，冻结本次参数与默认兼容性；公开新输入按设计技能提交具体方案，由用户指定后实现。
- [ ] 对选定方案补失败回归及缺省行为不变测试；先证明问题，再最小修改，不用普通实体拼块或多次cut冒充原生折边能力。
- [ ] 建自由端负对照与材料端有效基线；none/1×1/4×4/单端按实际相交材料计算独立预期，不强套完整矩形公式。
- [ ] 运行sheetmetal专项、dev_check和SDK构建；独立记录离线与原生结果。
- [ ] 被指定实机后验四壁4/4、方向、角部/缺口位置尺寸及体积、展开折回、编辑、逐例保存重载；故意失败回滚后可继续合法操作。
- [ ] 同步实际能力边界，保留仍不支持组合；将T03参数/方向契约及T13受影响范围作为回归检查，不扩大为全库复测。

**完成标准：**所声称能力的原生几何和闭环全有证据；仅参数回显、元素树接受、体积正确之一均不足通过。

**短指派语：**“执行 N06 指定阶段，先接收N05证据和选定方案，最小实现有限角部能力，完成四壁/材料端释放/展开折回/编辑重载及回滚；依赖未满足不猜修复。”

## N07：T02 弧方向余项实机复测

**归属：**FEAT-034/T02。**Files:** `tools/test_arc_direction_live.py`、`tests/unit/test_arc_direction_live.py`、T02卡；仅失败证明确有缺陷时另列实现范围。

**Interfaces:** 消费已交付弧方向判定和编辑夹具；产出当前源码的真实验收报告。

- [ ] 读T02最后记录，核实只认 `result.saved_file_reloaded_and_verified`、native arc回显和独立体积，三者缺一不通过；已有四例创建证据不当作新余项结果。
- [ ] 离线运行 `-m unittest tests.unit.test_arc_direction tests.unit.test_arc_direction_live -v` 及默认驱动，检查实际live用例含方向就地编辑、跨零、倾斜帧、下游和非法编辑。
- [ ] 获指定且会话可用后执行 `tools\test_arc_direction_live.py --live --confirm-session-usable`，保留逐例输入/终态。
- [ ] 对照实际弧扫向/轴帧与体积，核编辑ID/revision、非法拒绝或原生回滚及后续合法操作、每例保存重载；未真实并行则并发未验证。
- [ ] 给出逐项通过/失败/未执行及原始错误，失败先定位，不自动重放已受理任务。

**完成标准：**本次新增余项逐项有严格原生证据，不能用旧四例数值替代。**短指派语：**“执行 N07 的 T02 实机复测；先离线预检与当前会话核对，按已有严格判定跑编辑/下游/非法编辑和重载，不重复实现已交付逻辑。”

## N08：T09B 用户中心线计数与实际回转轴

**归属：**FEAT-008/T09B。**Files:** `tools/test_revolve_axis_live.py`、`tests/unit/test_revolve_axis_report.py`、`tests/unit/test_revolve_axis.py`、T09B卡。

**Interfaces:** 消费已交付的系统参考剔除逻辑；产出单用户线计数/ID、实际轴帧及重载证据。外部真多中心线夹具单列，不改变当前服务仅一条用户中心线准入。

- [ ] 运行 `-m unittest tests.unit.test_revolve_axis tests.unit.test_revolve_axis_report -v` 和默认驱动，核单用户线计1、原生ID来源及未知不猜第一条。
- [ ] 检查当前live用例是否覆盖改后的count/id、轴帧与保存重载；缺重载判定先补驱动/单元，不直接沿用旧三例创建成功结论。
- [ ] 获指定后运行 `tools\test_revolve_axis_live.py --live --confirm-session-usable`，验证内部中心线、显式基准轴、无中心线负例、几何及原生回显。
- [ ] 多中心线仅在取得外部手工原生夹具后另跑，记录其来源；缺件明确未验，不能将服务准入拒绝记为该几何场景通过。
- [ ] 记录revision/重载和失败后模型状态，更新本卡实际范围。

**完成标准：**单线count/id与轴/帧/重载一致；多线未知或未验如实保留。**短指派语：**“执行 N08 的 T09B 实机复测，重点验证一条用户线计1及真实ID、实际轴和重载；真多线无外部夹具则列未验，不猜ID。”

## N09：T09A 组件标签保存重载与删除重插

**归属：**FEAT-023/FEAT-008/T09A。**Files:** `tools/test_component_labels_live.py`、既有组件身份单元、T09A卡；生产实现已存在，原补强为零生产改动。

**Interfaces:** 消费model_identity+feature_id关联，不把业务label或物理副本名当唯一身份；产出跨作业/重载/删除重插的关联证据。

- [ ] 读T09A最后记录和驱动 `check_contract`，离线核标签/identity/bindings、deleted_identities字段和重载强制判定；需要时定位对应单元，不重复实现标签功能。
- [ ] 核默认驱动的无连接行为与新输出路径，准备重载后关联、删除后新唯一label重插、ID重排不误绑的场景及预期。
- [ ] 获指定后运行 `tools\test_component_labels_live.py --live --confirm-session-usable`，逐步核实际ID、源revision、位姿、身份与业务label关联。
- [ ] 区分删除墓碑、标签生命周期及物理副本名，检查旧绑定不误指新对象；回读重载证据，不拿T13单例标签保留代替本矩阵。
- [ ] 交接当前通过范围及外部未验；无失败不改生产逻辑。

**完成标准：**关联与删除重插矩阵在本次源码实机通过。**短指派语：**“执行 N09 的 T09A 实机补验，验证重载关联、删除重插及ID重排不误绑；优先使用既有实现，保持物理副本命名。”

## N10：T12 盲孔、方向、尺寸编辑与回滚

**归属：**FEAT-035/T12。**Files:** `tools/test_native_countersink.py`、`tests/unit/test_native_countersink.py`、T12卡。

**Interfaces:** 消费既有6例余项和独立oracle；只声称真实dimension ID的尺寸值编辑，不扩展成任意孔型/放置/flip重定义编辑。

- [ ] 运行 `-m unittest tests.unit.test_native_countersink -v` 和默认驱动；确认待测6例及 `matched_variant` 备选公式不判通过。
- [ ] 核盲孔depth为overall、三种盲孔的体积/新增面/尺寸/圆柱轴与bbox预期，以及翻向守卫失败后的恢复孔。
- [ ] 获指定后运行 `tools\test_native_countersink.py --live --confirm-session-usable`（默认余项；先核当前 `--case` 选择器，避免误把旧3例重复当新增验收）。
- [ ] 用真实dimension ID改直径与沉孔深度，核几何、参数、revision和逐例重载；负例核真实回滚/模型不变及合法恢复。
- [ ] 输出主oracle与备选命中分开判定，保留原始错误和未支持孔型。

**完成标准：**六例实际余项逐项有证据，不能仅凭成功job或旧沉孔创建证据关闭。**短指派语：**“执行 N10 的 T12 六例实机余项，按已有独立oracle验证盲孔/方向/真实尺寸编辑、重载与回滚，不扩大为任意孔型编辑。”

## N11：空件预览、图像内容与原件回补

**归属：**BUG-088/T08A、BUG-066/T08C；查缺关联T06/T07。**Files:** `native/preview.h`、`src/creo_mechdog/preview.py`、`tools/test_t07_preview.py`、`tests/unit/test_t07_preview.py`、相关卡；新材料归档进N00指定目录并保原字节。

**Interfaces:** 消费缺件表；产出文件写出和内容正确性两份结论。缺原件不阻塞其他任务，不以替代图像关闭原失真案。

- [ ] 回补原Part/PRT、原图、同作业request/native/job JSON；T06原截面/帧/前置模型、T07 gear10原始/精确版亦只记录真实可得材料，不无限遍历或推测重建原件。
- [ ] 离线运行 `-m unittest tests.unit.test_t07_preview -v`，核raster/file_check/verification_error/失败阶段原码与缺失图像不能通过。
- [ ] 补空件→同会话实体预览、独立JPEG、钣金对照，先查驱动是否覆盖；输出指定新的唯一 `--output build/post090_preview_<run_id>/report.json`。
- [ ] 获指定且会话可用后执行 `tools\test_t07_preview.py --live --confirm-session-usable --output <新路径>`；分别核实际文件/大小、目标窗口模型和图像可见面孔槽，不能由view_matrix_matches=false直接判失真。
- [ ] 有真实可复现I/O原因后再最小修复；未定因不添加掩盖问题的自动重试。不将预览失败升级成已成功几何的失败，也不由几何体积证明图像正确。
- [ ] 交文件验收/内容人工复核/原案回放三类状态；缺件保留开放并列下一次所需材料。

**完成标准：**空件原案有复现或准确未复现，内容有可审查图像及对照，缺件清单可执行。**短指派语：**“执行 N11 材料核对及离线诊断，重点空件output_file失败与图像内容分开；原件不足列缺件，未获实机指派不连接Creo。”

## N12：补足性能基准，按证据选热点

**归属：**FEAT-033/T09D；本子任务按P3调查。**Files:** `tools/test_plan_performance.py`、`tests/unit/test_plan_performance.py`、T09D卡。当前任务以测量/调查为交付；生产优化另按有证据的最小范围指派。

**Interfaces:** 消费0.9.0已有基准，不改写旧数据；产出固定受测源码下small/large×single/batch各至少3次独立模型，warm/cold标注、中位数/范围和等价性。

- [ ] 读T09D末节，保留138.7/261.0秒及small三联已有事实；核本轮是否复用相同指纹/规模，不拼接不同源码报告成同一统计。
- [ ] 离线运行 `-m unittest tests.unit.test_plan_performance -v` 和默认驱动，核等价几何、失败不计样本、重载证据和阶段未知规则。
- [ ] 固定执行器和空闲测量时段，按实际边/特征规模校准large；若用于解释1408边观测，规模与输入差异须明示。准备可跨工具超时保留分阶段报告的运行方式，不能通过取消保存重载缩时。
- [ ] 获指定后串行 `tools\test_plan_performance.py --live --confirm-session-usable --reps 3 --output <新路径>`；保留中断和未满样本，不自动重放已受理任务。
- [ ] 核每类样本、体积/边数/cut增量/保存重载与save_reload_events，再给中位数/范围。求解/检查/保存重载未暴露则null/unobservable；如需新增计时，另列明确实现范围，不估算分段。
- [ ] 依据可观测事实提出下一补丁热点与回归，不承诺提速百分比，不加队列/重试。

**完成标准：**本轮重复基准与局限可审查；没有分段证据时不能声称定位原生瓶颈。**短指派语：**“执行 N12 性能调查指定阶段，补足large等价重复样本并记录保存重载次数；保留0.9.0历史数据，不减少验证或预先优化生产逻辑。”

## N13：所选任务集成与新版本交付

**归属：**建议 DEV-052，用户单独指定的集成人。**Files:** 所选变更、工作卡/主台账/入口、`version.py`、新版本说明/发布记录、适用发布元数据与打包输入；不改已发布0.9.0附件和标签。

**Interfaces:** 消费各窗完整交接与依赖提交；产出一个固定受测源码的交付版本。未被用户选择的工作保留开放，不因打包一起关闭。

- [ ] 收集各窗结果，按依赖和共享文件逐项合入开发分支；处理冲突后重新核语义，不把各分支单独通过合并为集成后通过。
- [ ] 固定候选源码，核受影响单元/dev_check、SDK构建及定向实机；代码变化后只补必要验证。WorkBuddy若另行要求只用MCP黑盒，与开发者脚本报告分开。
- [ ] 串行更新当前状态和能力边界，核每个所选ID的技术状态、交付版本、未测/缺件和证据；T03/T13保持已有闭环，受影响部分有本轮回归事实。
- [ ] 按项目规则确定未发布目标版本，新增公开功能/不兼容输入按MINOR评估，兼容修复按PATCH；同步version与适用元数据，不预设下个版本号。
- [ ] 用户指派交付后，按RELEASING完成合main、正式Release、源码/种子附件及SHA256；标签指向本次主干源码，已发布标签和同名附件不得覆盖/移动。
- [ ] 核远端提交、标签、Release正文/附件哈希，回填交付记录；发布失败或附件缺失仍为交付未完成。

**完成标准：**所选范围在同一源码上通过适用验证并正式交付，开放项明确；不能以合main或Release草稿结束。**短指派语：**“执行 N13，集成我明确选择的任务范围，核依赖与受测源码，完成适用回归、文档及新版本正式Release和附件校验；不夹带未选功能、不覆盖0.9.0。”

## 本轮计划自检

- [x] 已覆盖七份反馈中的SDK兼容、会话事故、端点、细节特征回报、钣金、预览与模型材料；旧能力误判不新增同义工具。
- [x] 已把T03/T13从未完成主线移除；T05触发条件与内部机理分开；T09D已有数据与待补样本分开。
- [x] T02/T09B/T09A/T12可分别指派；真多中心线及T06/T07/T08C缺件分别保留。
- [x] 已核当前box驱动会拒绝live，不给接手者虚假的可执行实机命令；新驱动标明尚待实现。
- [x] 新固定ID只作建议，先N00登记；公共文件、构建/实机互斥与当前会话限制明确。
- [x] 每个任务有依赖、文件、步骤、验证/完成标准和短指派语；用户自行指定窗口，本轮未派发任何实现。
