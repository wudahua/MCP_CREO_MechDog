# Creo TOOLKIT：本项目的 API 查证与开发指南

适用于在本仓库开发、修复或评估 Creo MCP 建模功能的开发者和 AI。本文以 **C++17 执行器中调用 C TOOLKIT 的 `Pro*` API** 为主线；Object TOOLKIT C++ 的类接口属于另一套 API，不能直接把它的示例替换进现有执行器。

项目规则以 [AGENTS](../../AGENTS.md) 为准，开发流程见 [DEVELOPMENT](../DEVELOPMENT.md)，职责与源码布局见 [ARCHITECTURE](ARCHITECTURE.md)，资源、错误、单位与编码要求见 [CODING_STANDARD](CODING_STANDARD.md)。本文补充查证方法，不另建规则或能力清单。当前支持边界以 [COMPATIBILITY](../COMPATIBILITY.md)、包内能力登记和相关工作卡为准。

向维护者说明改动时，先读 [给软件工程师看的改动说明](CREO_CHANGE_EXPLANATION.md)：把目标、关键判断和独立验收证据说清，技术追溯随后提供；使用白话不代表降低几何或工程证据要求。该补充的记录见 [DEV-087](../work-items/DEV-087.md)。

2026-11-12：本机资料路径按 Creo **12.4.0.0** 离线核对；这只证明资料可定位，不是本次编译或建模验收。初版实施与验证记录见 [DEV-084](../work-items/DEV-084.md)；外部 skill 评估后的 API 模式补充见 [DEV-085](../work-items/DEV-085.md)，2026-11-13 的验收/交付方法补充见 [DEV-086](../work-items/DEV-086.md)。各阶段指纹仅证明当时受测的文档版本。

## 1. 下次如何使用

在本仓库的 Codex 会话中，可以显式调用项目 skill：

```text
$creo-mechdog-dev 为当前项目扩展一项曲面建模操作，先核对本机 SDK 的官方依据、现有接入点和验证缺口。
```

[skill 入口](../../.agents/skills/creo-mechdog-dev/SKILL.md) 的描述也允许在匹配的开发任务中自动选用；是否实际选用由宿主决定。其他开发客户端可以直接读取本文和 AGENTS，不假定它们识别同一个 skill 目录。首版面向 **Git 检出的项目**，现有源码 ZIP 打包规则未增加 `.agents/skills/`。

若用户只要求 WorkBuddy 黑盒验收或测试提示词，按 AGENTS 的 WorkBuddy 约定处理，不用本文引导它读取 SDK、源码、配置或运行本地脚本。本文中的离线命令属于开发者工作流。

## 2. 官方资料在哪里

本机示例根目录（其他机器按实际安装位置替换）：

```powershell
$sdkRoot = 'C:\Program Files\PTC\Creo 12.4.0.0\Common Files\protoolkit'
```

| 相对 `$sdkRoot` 的位置 | 用来回答什么问题 |
| --- | --- |
| `includes\*.h` | 当前 SDK 的真实声明、类型、枚举、弃用说明、元素树及取值表；不要只读匹配到的一行 |
| `online_help\index.html` | 本机离线帮助总入口 |
| `online_help\creo_toolkit\api\dita\*.html` | API 的参数方向、前置条件、返回码和官方示例链接 |
| `online_help\creo_toolkit\user_guide\*.html` | 功能背景、特征构造方法、流程和限制 |
| `protk_appls\`，尤其 `pt_userguide\` | 官方 C 示例，核对 API 的组合方式和生命周期 |
| `tkuse.pdf` | TOOLKIT 用户手册；优先查同主题 HTML，便于搜索与定位 |
| `Creo_Toolkit_GSG.pdf`、`Creo_Toolkit_RelNotes.pdf` | 入门和版本变化；`chinese_cn\Creo_Toolkit_GSG.pdf` 为本机中文入门资料 |

在线入口：[PTC TOOLKIT 各版本导航](https://www.ptc.com/en/support/help/Creo_Toolkit)、[r12 C TOOLKIT 帮助中心](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r12/usascii/creo_toolkit/about_protoolkit_pma.html)、[APIWizard 说明](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r12/usascii/creo_toolkit/Online_Documentation_in_Creo_Toolkit_APIWizard.html)。2026-11-12 查阅时，在线 r12 首页标注 **12.4.5.0**，不等同于本机 12.4.0.0。在线内容可交叉核对；签名与符号可用性仍需核对目标 SDK，运行结果需目标环境证据。

官方文件留在安装目录；仓库只维护检索方法、原创总结及出处，不复制 SDK、整册手册、官方 HTML 或示例源码进仓库/附件。目录不存在时报告缺失，不修改 PTC 安装或自动换用其他版本。

## 3. 从 API 名称查到可用依据

以下 PowerShell 命令在仓库根目录运行，均只读取资料。先设置上节 `$sdkRoot`。`rg` 无需启动 Creo。

```powershell
# 声明定位助手：按本机 config.json 中的 creo_root 找 includes。
# 只有配置确实指向预期 SDK 时，其结果才代表该 SDK。
.\.venv\Scripts\python.exe tools\sdk_decl.py ProFeatureWithoptionsCreate

# 保留原始注释上下文：声明助手会剥离注释，不能用于核实所有权或错误码。
rg -n -C 8 'ProArrayAlloc|ProArrayFree' "$sdkRoot\includes\ProArray.h"
rg -n -C 12 'ProFeatureCreate|ProFeatureWithoptionsCreate' "$sdkRoot\includes\ProFeature.h"

# API 页面文件名常为数字，按标题确认目标页，避免把正文交叉引用当成目标页。
rg -l '<title>Function (ProArrayAlloc|ProArrayFree|ProFeatureWithoptionsCreate)</title>' "$sdkRoot\online_help\creo_toolkit\api\dita" -g '*.html'

# 官方示例与仓库实现分别查，不把本项目旧用法当作官方契约。
rg -n -F 'ProFeatureWithoptionsCreate' "$sdkRoot\protk_appls\pt_userguide\ptu_featcreat\UgChamferTemplate.c"
rg -n 'ProFeatureWithoptionsCreate|ProArrayFree|ProSelectionFree' native/geometry.cpp native/surface_loft.cpp
```

先按精确 API 名或符号搜索，再查它所属对象/特征章节。查元素树时直接读原始头文件和用户指南的父子结构、条件及表格；`sdk_decl.py` 不是完整 C/C++ 解析器，也不提供这些信息。它当前只提取含 `extern`/`typedef` 的声明段；本机 `ProArrayAlloc` / `ProArrayFree` 使用 `LIB_COREUTILS_API` 前缀，会被助手漏报为 `not found`，应使用上面的原始头文件搜索。因此，助手未找到不能作为 SDK 不支持的证据，本批不修改助手。不要对整个仓库搜索运行模型、作业或虚拟环境；限定 `src/`、`native/`、`tools/`、`tests/` 和相关文档。

对准备使用的 API，写清以下依据，缺的项目明确标为“未确认”：

| 核对项 | 需要得到的具体信息 |
| --- | --- |
| 声明与版本 | 头文件、符号、参数类型/方向；是否弃用、后继 API、所需 SDK 符号 |
| 行为与限制 | 所需模型/特征/引用状态、允许的选项；有文档依据的返回码含义 |
| 资源 | 谁创建、谁持有、哪个 API 释放、何时失效；成功及失败路径分别处理 |
| 使用方式 | 同版本官方示例位置，以及本项目最接近的实现；两者有差异时解释差异 |
| 验证 | 只有静态查证、已有历史实测，还是本次实际验证；记录各自日期、版本和范围 |

对返回 `ProError` 的 Toolkit 调用逐项检查原始结果并保留 API/阶段，其他返回类型按对应契约检查。不能把一个通用失败码直接解释成许可不足或“不支持”；先找该 API 的返回值说明和实际上下文。官方示例也不能代替对当前调用成功、失败和中途退出路径的清理核对。

处理对象句柄、Visit 回调、装配 Selection、字符串或多实体时，按需读 [API 使用模式](CREO_TOOLKIT_API_PATTERNS.md)。函数实际返回类型也需逐项核对：并非所有 `Pro*` 函数都返回 `ProError`，不能统一套检查宏。

### 三条已离线核对的查证路径

以下路径相对 `$sdkRoot`，数字 HTML 名只用于本机这一份资料；换 SDK 后按符号重新搜索。

| 场景 | 头文件 → API 说明 → 官方示例 | 本项目使用方式 |
| --- | --- | --- |
| 动态数组 | `includes\ProArray.h` 的 `ProArrayAlloc` / `ProArrayFree` → `api\dita\144.html` / `145.html`（位于上表 API 目录）→ `protk_appls\pt_userguide\ptu_featcreat\UgSktFirstFeatureCreate.c` | `native/geometry.cpp` 的创建选项数组使用 `ProArray`，用匹配的 `ProArrayFree` 释放，不能用 `delete[]` 替代 |
| 特征创建 | `includes\ProFeature.h` 的 `ProFeatureWithoptionsCreate` → `api\dita\1425.html` → `protk_appls\pt_userguide\ptu_featcreat\UgChamferTemplate.c` | 对照 `native/geometry.cpp` 的 `create` 和 `native/surface_loft.cpp`；`ProFeatureCreate` 的文档标注弃用，不能因为旧示例使用它就机械照搬 |
| 边界混合元素树 | `includes\Probbl.h` → 同主题用户指南和 `includes\ProElemId.h` 的实际符号 → 本项目 `native/surface_loft.cpp` | 按 `BNBLN_1DIR/2DIR`、曲线集合和边界条件的父子位置核对；常量存在不说明树形、合法枚举或内核行为均已文档化 |

`ProArrayFree` 释放数组不代表自动释放数组元素所引用的所有其他 Toolkit 对象。`ProSelection`、`ProElement`、`ProSection` 及输出资源分别查对应 API 的所有权约定，不能统一套用 C 堆释放。创建 API 的顶层返回码和 `ProErrorlist` 是不同层的诊断，两者都要读取，后者的存储归属按 SDK 定义核对，不猜测不存在的释放函数。

## 4. 把能力接入当前项目

先从 [BACKLOG](../BACKLOG.md) 找现有 ID 和工作卡；新增工作先登记目标、范围、环境及验收。涉及已报告失败时先复现并区分现象与推测根因。以下是接入点导航，不表示每次都要修改全部位置。

| 层次 | 现有位置与要核对的事 |
| --- | --- |
| 输入契约 | 包内 `schema.py` 及其领域模块，例如 [surface_ops.py](../../src/creo_mechdog/surface_ops.py)；参数、引用、单位、拒绝分支、旧调用兼容；根包装共享包内类型 |
| 能力与公开工具 | [capabilities.py](../../src/creo_mechdog/capabilities.py) 是登记与限制来源；只有需要独立公开工具时在根 `server.py` 加薄包装，工具数由实际登记计算 |
| 计划、任务与保护 | 根 `generic_bridge.py` 核对计划、模型登记与 revision；根 `bridge.py` 持有 Toolkit 通道。按现有入口接入，不创建第二套调度或锁 |
| 原生执行 | `native/generic.cpp` 的操作分派、对应特征实现及 include 顺序；对照 [surface_loft.cpp](../../native/surface_loft.cpp)。几何在原生端计算，Python 不模拟 Creo |
| 回执与查询 | 包内 [operation_results.py](../../src/creo_mechdog/operation_results.py)、[job_projection.py](../../src/creo_mechdog/job_projection.py)：成功/失败字段、原始诊断、full/compact 投影；必要测量标量不能在 compact 中丢失 |
| 测试与文档 | 新增单元放 `tests/unit/`，集成驱动沿用 `tools/`；同步受影响的语法、能力限制和工作卡，不把离线成功写成原生成功 |

本项目尚有单翻译单元文本包含：`native/worker.cpp` 包含实现，`generic.cpp` 再包含特征 `.cpp`。新增文件应先核对实际包含与分派链，不能假定放进 `native/` 就参与构建，也不能在功能任务中顺手全量拆分；迁移方向见 ARCHITECTURE。新增依赖还需核对构建指纹和源码身份覆盖。

保持现有 busy 立即拒绝、已接受任务仅轮询、revision、失败回滚与 unknown 保护。不要引入隐含队列或自动重交；详细边界引用 AGENTS 和 [BUG-009](../work-items/BUG-009.md)。

## 5. 元素树、常量和版本兼容

1. 找到与目标特征相符的官方树及取值表，确认父子关系、数组、selection、条件必填项和单位。只在 `ProElemId.h` 找到一个名字，不足以推导完整树。
2. 元素 ID 和枚举用符号名。需要新常量时检查现有 `tools/generate_constants.py` 的头清单和探测机制；`native/constants.inc` 是由本机 SDK 生成的产物，不手改、不提交、不跨机复制。本资料任务不执行生成或编译。
3. 针对实际依赖的符号/可调用声明做 SDK 门控，核对生成器、原生分支和 worker 能力披露是否一致。头文件有无不能替代内部符号的可用性判断。
4. 区分“SDK 可编译”“目标 Creo 运行支持”“几何、保存重载已通过”。只有目标环境的本次适用证据才能支持最后一项；Creo 12.4 的结果不外推到 Creo 9/10。
5. 没有完整官方树时，把假设和证据缺口写入工作卡，按下节由开发 AI 发现、取样和验证参照。实际读取 Creo 特征树属于实机操作；仅查原始 XML、清单、驱动源码及已有记录可离线完成，不能把“只读探测”当成未经授权连接 Creo 的理由。

### 开发 AI 自行完成参照取样与重建验证

本流程用于新增/修复元素树结构、未知选项或引用，以及需要证明可复用的模板路线。技术证据的准备、执行和判断归开发 AI；维护者可追查结果，不负责确认每个节点、手工做一个样本或凭画面判定正确。已有完整可靠依据的小改动可复用适用证据，不为形式重复取样。

1. **先定义要证明什么。** 写出最小输入、目标几何/选项、预期依据及失败判据，区分“树或两条路线一致”和“满足用户几何要求”。优先采用可复算算例、已知尺寸/关系、官方语义或有来源的参照数据，不能只比较两条共享同一假设的实现。
2. **自行发现参照。** 先查相关工作卡、既有模板清单/原始 XML、种子与已验证任务，核对形态、来源版本、文件指纹和适用限制。再考虑用现有 MCP/驱动生成最小临时参照；尚无该能力时，开发 AI 先核对官方实现方法，必要时按已登记条目补最小验证驱动，或评估本次可用且获准的其它建模自动化路径。不把“请用户在 GUI 建好并确认”设为默认前置；确无可用样本或自动化路径时，记录具体缺口和下一步，不臆造树或通过结论。
3. **先核对本次权限，再实际取样。** 资料离线分析和实际 Creo 操作分开。无当次授权时先完成可做的查证、方案与预期，汇总具体临时模型范围、构建/取样/重建/检查动作后申请必要授权；不要求用户确认技术对错。已明确允许的范围连续执行，不为每个已覆盖步骤反复询问，不沿用历史授权，不擅自操作用户模型或进程。
4. **取完整可追溯数据。** 优先复用 [read_reference_tree.py](../../tools/read_reference_tree.py)、[export_elemtree_template.py](../../tools/export_elemtree_template.py) 及 `creo_dump_feature_tree` 的适用入口；先读实际脚本参数/行为，不因名字或示例开关就假定它是离线安全的。官方可核实路线是 `pt_userguide` 的 Export XML，对应 `ProFeatureElemtreeExtract` → `ProElemtreeWrite`；本机示例为 `protk_appls/pt_userguide/ptu_featcreat/UgXMLFeat.c`。未经核对的 `pt_feat_dump` 名称不作为命令依据；`pt_feats` 的文本信息输出也不等同于完整 XML 引用数据。
5. **用单变量对照理解变化。** 固定其余输入，分别生成基准与只改变一个选项的参照（例如自由边界与相切边界）。对照节点路径、父子/数组结构、数据类型、值及模型引用，先识别名字/ID/顺序等实例差异，再核对官方语义。导出结果可能包含数字枚举、内部/可选节点和模型相关引用，不把“出现于一次成功树”当成所有输入都必填或取值已完整文档化。提取的树副本按 `ProFeatureElemtreeFree` 约定释放；新建/读入的树及其它资源按各 API 自身所有权处理。
6. **适配引用后重建。** 按角色重绑实际需要的 owner/id/type 与装配路径；曲线数量、方向、特征名及相关条件分支一并核对。不能只替换看到的第一组引用，不能假定其它模板的条件子树也没有模型引用；形态/数量不符按契约拒绝，不裁剪、近似或任意删节点。读取 XML 成功只说明完成了加载，不证明它适用于目标特征；创建、完成和再生仍需分别检查。
7. **由 AI 执行并判定验收。** 在本次允许的临时模型和通道内核对目标特征最终有效性、实际引用、独立几何期望、单位、保存重载，以及适用的 revision/回滚反例。相切等目标要有对应几何关系证据，不能只凭一个选项值或相同面积称为通过。保持已有 busy/unknown 保护，已接受任务只轮询，不另开并发会话或重新提交。结果用白话报告“验证了什么、依据和实际结果、未验证范围”，不再交给维护者批准节点或几何技术结论。

| 遇到的情况 | 开发 AI 应怎样处理 |
| --- | --- |
| 有适用的旧参照/历史实测，但无本次实机授权 | 自行解析清单/XML/源码并形成可执行验证方案；明确历史证据与当前待测，不执行真实取树/重建，不要求用户代验 |
| 已获准本次取样与重建 | 在范围内自行完成、判断和记录；授权不是已通过，临时模型也不代表可清锁、结束进程或改写用户模型 |
| 同宿主/特征已知提取 `-18`，或 XML 有版本/结构错误 | 保留原码与阶段、版本和元素错误；停止重复同一路线，不靠换转储包装、乱改枚举或用高版本成功掩盖失败。继续可做的离线定位/有依据的替代方案；新的验证须有明确假设且在允许范围内 |
| 创建阶段有未完成特征 | 结合该路线是否需要后续补齐/重定义判断，不能一见中间状态就误拒绝；到要求的完成点仍不满足状态或几何目标时，不能报成功 |
| 缺参照、测量接口或明确工程输入 | 说明究竟缺什么、已查哪些来源及可继续的动作；能自动解决的继续处理。只向用户索取必要输入/授权或设计选择，不让用户“人工确认这棵树/这个结果没问题” |

官方依据：[XML 重用说明](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r12/usascii/creo_toolkit/user_guide/Tips_for_Recycling_XML_Output_of_Element_Trees.html)、[特征树提取及释放说明](https://support.ptc.com/help/creo_toolkit/protoolkit_pma/r12/usascii/creo_toolkit/user_guide/Feature_Inquiry_1.html)。官方不保证跨版本 XML 可直接使用；验证哪个环境就报告哪个环境，不由 Creo 12.4 的一致性试验推出 Creo 10 可用，也不额外引入全项目双版本放行门槛。

本项目已有 BUG-123 的 3 截面/3 导线样本与模板重建记录，可作为该形态的查证起点；不把这份固定样本当作所有曲面/扫描的通用模板。本流程责任与情境试用记录见 [DEV-088](../work-items/DEV-088.md)。

### 与当前曲面开发直接相关的记录

| 记录 | 能复用什么；不能据此推出什么 |
| --- | --- |
| [G5-NATIVE-CONTRACT](G5-NATIVE-CONTRACT.md) | 按 SDK 符号核对树形与资料缺口的方法；其中“未验证”内容保留该身份，不变成默认实现 |
| [FEAT-065](../work-items/FEAT-065.md)、[2026-11-11 交接 B2/B3](FEAT-065-HANDOFF-2026-11-11.md) | `Probbl.h`、`ProCrvcollection.h` 到放样输入/边界条件的查证线索，以及当时 Creo 12.4 的实测。文档只列出 `TAN_COND_FREE` 不等于其他边界值可凭名称或数值猜测；交接中的旧限制先核对当前卡与兼容矩阵 |
| [REFERENCE-TREES](REFERENCE-TREES.md) | 2026-11-05 自建特征读回的树，以及当时的缺口；属于历史观察，不是对所有特征/版本的普遍结论 |
| [DEV-082](../work-items/DEV-082.md) | `Probbl.h` 存在性门控曾不足，需核对 `ProElemId.h` 中实际依赖的符号；当前源码是核实具体门控的入口 |
| [BUG-120](../work-items/BUG-120.md) | 外部 Creo 10 的元素树抽取失败与诊断范围；不能以本机声明存在替代目标环境运行证据 |
| [BUG-119](../work-items/BUG-119.md)、[BUG-118](../work-items/BUG-118.md) | 几何判定应对照操作前后变化，回执还要核对 compact 结果；旧交接的“已有实体一律失败”等描述不作为当前能力真值 |

这些记录只提供开发线索。查引用是否仍适用时，同时核对工作卡当前摘要、实际源码与 COMPATIBILITY，不改写历史原件。

## 6. 如何声明完成和未验证范围

涉及自动建模、改型或模型交付的能力开发时，按需读 [设计意图、验收与原生交付](CREO_MODELING_ACCEPTANCE.md)：先定义可测目标，再核对实际草绘/坐标、装配源快照、保存后结果与依赖文件；不从预览、正体积或外部案例成功推导本次完整通过。

| 证据层 | 能说明什么 |
| --- | --- |
| 本次离线资料核对 | 路径、声明、官方说明、示例和仓库接入点已找到；不证明可编译或可建模 |
| 本次开发者检查 | 实际执行的格式/语言/单元或离线驱动范围；不能替代原生运行 |
| 获准后的原生验收 | 匹配 SDK 构建、任务终态、几何及参数、保存重载和适用回滚；逐项记录结果 |
| WorkBuddy 黑盒 | 公开 MCP 的最终用户行为；不补做源码检查，也不由开发者证据替代 |

未来原生实现的验收命令、成功标准和证据身份沿用 DEVELOPMENT；必须记录源码提交、dirty、受测指纹、命令、环境与未测范围，不能只写“返回成功”。用户当次明确确认后才可编译执行器或进行实机联调；本指南和 skill 自身不授予这些权限，也不要求恢复已失效的“先查清卡死根因”前置。禁止擅自结束/重启进程、清锁、清 unknown 保护或处理用户模型，详见 AGENTS 的当前规则。

纯文档/skill 整理只做适用的格式、链接、台账和只读查证。本次没有新增建模能力，不更新工具数、版本或发布声明；没有实机结果的项目明确写“未验证”。后续任务的实际验证范围由改动决定。
