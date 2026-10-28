# DEV-051 T04 验收卡：钣金重叠增料（BUG-046，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线阶段完成 / 实现待原生验收**。分支：`codex/dev051-feedback070`；工作区：`E:/Projects/MCP_CREO_MechDog`。状态不是“已修复”：三路对照的实机结果、-1 根因与钣金增料支持集合均未验证/未确定，见“未测项”。本次未连接 Creo、未实施任何 Toolkit 作业、未改版本/合 main/推标签/发布。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T04 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（BUG-046/T04 节）、[T00 验收](DEV051-T00-ACCEPTANCE.md)、[T02 验收](DEV051-T02-ACCEPTANCE.md)、[T03 验收](DEV051-T03-ACCEPTANCE.md)、[BUG-046 工作卡](../work-items/BUG-046.md)。
- 反馈证据（外部原始记录，本次未重取、未重放）：0.3.1 S1（`docs/validation/feedback-2026-10-16/2026-10-16_CREO_0.3.1_钣金工具链增料失效与折边方向不可控等10项缺陷.md`）：钣金模型 `56d4cdae6b7242929d7180949905ef1a` 上 10×10×5 重叠增料两次失败（jobs `9256690b7e13417b9bc9c90e45630fe8` / `4b0c0d9b738a4373ba292afe4a65034c`），155×1×76.46 端壁重叠增料失败，⌀10 through_all cut 成功（体积减 78.54 mm³），失败后 `bodies: 1`、cut 仍正常；原始报错 `Toolkit call ProFeatureWithoptionsCreate failed with code -1 during execute_extrude`（`toolkit_code: -1`）。0.3.2 A S1（`docs/validation/FEEDBACK-0.3.2.md`）：`acc_test_sm2` 上 10×10 草图 `extrude(mode="add", depth=5)` 报 `ProFeatureWithoptionsCreate -1`（op index 3），同模型 cut 正常（job `4601aa39ac6149bf93a04d453eb5186d`）。
- 基体采用 T03 已确认薄底板契约（185×232×1，体积 42 920 mm³）；T02 弧方向契约未读写。受派范围仅 T04 离线阶段：不连接 Creo、不启动 MCP/Creo、不改版本、不合 main、不推标签/不 push、不发布、不实施其他任务。工作区既有无关文件（`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、`docs/validation/feedback-0.7.2-2026-10-28/`）未暂存、未改写、未删除。

## 静态定因（读码核对，不猜改参数）

原生只有一个 protrusion 路径：`native/generic.cpp` 的 `extrude_or_revolve`（分发 `execute_extrude` → `extrude_or_revolve(op, kind == "revolve")`），普通件与钣金件共用；报告所称“两条实现路径”在当前源码不存在（与总计划判断一致）。钣金专用原生创建只存在于 `native/advanced.cpp`（`sheetmetal_wall` 薄壁拉伸 + `PRO_DTM_SRF_AS_WALL` 转换、flange、unbend），第一壁转换路径不是 protrusion 路径。

元素树（`create()` 见 `native/geometry.cpp`，父引用是模型本身 `ProMdlToModelitem(board)`，选项 `PRO_FEAT_CR_NO_OPTS`）：

| 元素 | add | cut |
| --- | --- | --- |
| `PRO_E_FEATURE_TYPE` | `PRO_FEAT_PROTRUSION` | `PRO_FEAT_CUT` |
| `PRO_E_REMOVE_MATERIAL` | `PRO_EXT_MATERIAL_ADD` | `PRO_EXT_MATERIAL_REMOVE` |
| `PRO_E_BODY` | 无实体/新体：`PRO_BODY_USE_NEW`；否则 `PRO_BODY_USE_SELECTED` + `ProSolidDefaultBodyGet` 默认体引用 | `PRO_BODY_USE_ALL` |
| 公共 | `PRO_E_FEATURE_FORM=PRO_EXTRUDE`、`PRO_E_EXT_SURF_CUT_SOLID_TYPE=SOLID`、`PRO_E_STD_FEATURE_NAME`、`PRO_E_STD_SECTION/PRO_E_SEC_USE_SKETCH`（草图特征选择）、`PRO_E_STD_DIRECTION`（section_normal_sign×direction）、`PRO_E_STD_EXT_DEPTH`（FROM_NONE/TO_BLIND+值） | 同左 |

结论：失败的 add 与成功的 cut 之间只有上述三处结构差异（特征类型、REMOVE_MATERIAL、BODY 元素），加上钣金材料模型对实体增料的任何限制，都只能靠实机隔离判定；**静态不可定因，本次无生产改动**（“只对静态可确认的根因做最小修复”没有可选项）。原始 -1 返回、报错文本与对应输入原样保留（见驱动报告 `original_evidence` 与本卡“输入与来源”），未改写为任何推测根因。

待实机隔离假设：H1 `PRO_E_BODY`（SELECTED+默认体引用）在钣金件上无效；H2 `PRO_FEAT_PROTRUSION` 实体增料在钣金件上不被接受；H3 重叠材料并入所选体被钣金材料模型拒绝。判别探针：B2 非重叠钣金 add（区分“重叠”与“增料”）、B3 原样重放（depth=5 positive，与 0.3.2 复现同形）。

## 三路对照契约（固定矩形/空间位置/重叠体积）

基体：薄底板 185(X)×232(Y)×1(Z)、体积 42 920 mm³（T03 契约，第一壁由 185 线 + `sheetmetal_wall(depth=1, thickness=232)` 生成；普通件对照为同尺寸闭合矩形 `extrude(add, depth=1)`）。固定重叠体：XY 平面上矩形 min`[20,20]`/max`[30,30]`（10×10），`extrude(depth=2.5, direction="symmetric")` = 10×10×5 跨草图平面块（symmetric 双侧各 2.5，与 DEV-049 斜槽“symmetric 恰为单向两倍”的实测语义一致）。三路仅“基体模型类型 + extrude mode”不同：

| 路 | 基体 | 操作 | 期望体积 mm³ | 状态 |
| --- | --- | --- | --- | --- |
| A `solid_add`（对照） | 普通实体 185×232×1 | 同矩形 add | 42 920+500−100 = **43 320** | 待实机 |
| B `sheetmetal_add`（对象） | 钣金第一壁 185×232×1 | 同矩形 add | 支持时同为 **43 320** | 历史 -1，待实机 |
| C `sheetmetal_cut`（对照） | 钣金第一壁 185×232×1 | 同矩形 cut | 42 920−100 = **42 820**（去料 100） | 待实机 |

重叠体积固定 100 mm³ = 10×10×1：跨平面块覆盖整个 1 mm 板厚，驱动内置放置不变性检查（板厚在 Z 上取 −1～+1.7 区间任一位置，相交厚度恒为 1），因此第一壁 Z 符号未核实（T03 遗留待核）不影响重叠量；矩形足迹 [20,30]² 完全落在 185×232 板足迹内，Y 侧偏移/居中两种已知说法下均成立。厚壁分支**只写待验**：待 T03 实机固定真实几何契约后再定厚壁基体，本阶段不设厚壁几何结论。

## 不支持组合拒绝与负例契约

静态已确认并保持的拒绝（建模前，模型/revision 不变）：

| 组合 | 拒绝消息要点 |
| --- | --- |
| `through_all` + add/surface | “through_all is supported for cuts” |
| 退化/倒置重叠矩形（max≤min） | “Rectangle max must exceed min” |
| 非正 depth / 未知 mode / 未知 direction | 字段级校验拒绝 |
| 第一壁非“单条开放直线”（闭合矩形、弧、多段链等） | “exactly one open straight line”（T03 契约，防回退） |

**不预判**：钣金件上的实体增料（B 路）没有被“建模前拒绝”，因为其支持状态未经实机确认，提前拒绝等于预设结论；本阶段也不实现 `SOLID_ADD_ON_SHEETMETAL_UNSUPPORTED` 一类错误码。若实机确认该组合不支持，按 BUG-046 范围补“明确边界 + 可行工具指引（`sheetmetal_wall`/`sheetmetal_flange`）”而非裸 -1。禁止把“钣金转换普通件”记为钣金增料成功。

负例实机契约（待验）：add 失败须真实回滚——体积/别名/revision 与基线一致，失败尝试保留原始 -1 与元素错误（`last_feature_errors`）；回滚后同件后续合法 cut 可用（与 0.3.1 “失败后 cut 仍正常”对应）。

## 实际修改文件

新增：`tests/unit/test_sheetmetal_overlap.py`、`tools/test_sheetmetal_overlap.py`、本卡；更新：`docs/work-items/BUG-046.md`。**未改**：`native/`（无生产改动）、`src/creo_mechdog/`、`server.py`、根兼容包装、`version.py`、台账、README、T02/T03 的共享契约文件。提交仅按这些精确路径暂存；`session_activity.json` 与既有无关文件不提交。

## 依赖提交、受测身份与指纹

- 依赖提交：`2726ca54715d547c71c7de61c24fb214ac7f6864`（T00）→ `a3c1f4b3e05668aa57d7225dc16394dd272abec9`（T02）→ `601b4bcaca861b2d1edd9930a17cf4752d9768d8` / `f10bee750d6c9d582839306b2ffc029997bfb339`（T03，本卡基线）。
- 实现提交：本卡对应 T04 提交，提交号以交接报告的 `git rev-parse HEAD` 为准（提交号不能自指写入同一提交文件）。
- 受测 commit：`f10bee750d6c9d582839306b2ffc029997bfb339` + 本批未提交改动；dirty=true（含本批改动与既有无关文件）。
- `source_fingerprint`：`7084ce71d012a0a4aff27a566bc3c8a99e72ac7ba3740c26473bf61faa851ba2`（`tools/test_sheetmetal_overlap.py` 的 provenance 算法，与 T03 驱动同实现：全部已跟踪 `*.py` 与 `native/*.h|*.hpp|*.cpp` 的行尾归一化 SHA256 清单哈希，另加本任务两个新增文件的显式路径；对应报告 `build/sheetmetal_overlap/20261028T213453_4cd86819/report.json`，SHA256 `9058ddad4fa08c786dffb449c4bcf909d5523648e405867b593a362846bb3cf9`）。驱动文件格式化修正前的较早一次运行（`20261028T213420_79412da2`，指纹 `208bf13d51d8d311f2e691fb5993d2b4f40f195c5ec2d2c3415da6bc703a4cfb`）已被本次取代；两次指纹不同，勿混用结论，统一以 `7084ce71d012a0a4aff27a566bc3c8a99e72ac7ba3740c26473bf61faa851ba2` 为准。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；pydantic 2.13；ruff 0.17.0（requirements-dev 锁定）；MSVC x64 与 Creo 12.4.0.0 匹配 Toolkit SDK（仅用于离线编译/读 SDK 头）。全程未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业；服务版本入口仍为 0.7.2，未改动。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `./.venv/Scripts/python.exe -m unittest tests.unit.test_sheetmetal_overlap -v` | exit 0，Ran 18 tests，OK（PowerShell 直接调用因 unittest 写 stderr 会出现 NativeCommandError 包装伪影，经重定向取 exit code 为准，非测试失败） |
| 2 | `./.venv/Scripts/python.exe tools/test_sheetmetal_overlap.py` | exit 0；报告 `build/sheetmetal_overlap/20261028T213453_4cd86819/report.json`，SHA256 `9058ddad4fa08c786dffb449c4bcf909d5523648e405867b593a362846bb3cf9`（另有 `report.sha256`）；内置单测 18/18 OK |
| 3 | `./.venv/Scripts/python.exe -m ruff check` 与 `-m ruff format`（仅本批两文件） | 修复 1 处 import 排序并格式化 1 文件后 `All checks passed`，不新增语言诊断 |
| 4 | `./.venv/Scripts/python.exe tools/dev_check.py` | exit 0；`success=true`、`unit_tests=passed`；style `lint_findings=30`、`unformatted_files=16`（与 T03 后存量基线一致，无新增）；报告 `build/development_check.json` |
| 5 | `./.venv/Scripts/python.exe bridge.py build` | exit 0，仅输出 `build/creo_worker.exe` 路径；原生源码本次无改动，**复用**已有执行器（2026-10-28 20:56:05 由 T03 编译生成），`build/source.sha256` 仍为 `f18383ec…b45e11`，未触发重编译 |

测试覆盖（离线，不实例化 MCP 客户端）：三路输入契约（同一矩形/位置/深度/方向，仅 mode 与基体不同，参数经共享准入 `validate_operations` 不被改写）；独立 box oracle（500/100/43 320/42 820）；足迹包含与重叠量放置不变性；独立工具载荷与计划两种提交形态；不支持组合拒绝（through_all×add/surface、退化矩形、非正 depth、未知 mode/direction）；T03 第一壁拒绝/接受防回退；原始 -1 证据字段完整性与归档交叉核对（job/model ID 在 `docs/validation` 原件中可查）。oracle 期望值全部按声明契约独立推导，不调用生产归一化/校验函数生成。

## 未测项与下一步

- 未测（需实机，按共同契约另行指派并在唯一 dev 服务串行执行）：三路对照真实结果（A 期望 43 320、B 支持时 43 320 或原始失败码、C 去料 100）、B2 非重叠探针、B3 原样重放（depth=5 positive）、H1/H2/H3 元素隔离、失败回滚（体积/别名/revision 不变 + 后续合法 cut 可用）、原生特征健康、钣金身份保留与 unbend/bend_back、`saved_file_reloaded_and_verified=true`、revision 回显。
- 未测：厚壁基体分支（等 T03 实机契约）；WorkBuddy 黑盒验收；Creo 9/10 环境。
- 缺材料：0.3.1/0.3.2 的逐调用请求 JSON 与 PRT 未随报告提供（原始 job/model ID 与报错文本已在卡内保留）；无法原样重放原始请求，B3 为同形输入重放而非逐字重放。
- 下一步：集成人按“给集成人的冲突文件与接口变化”合并；实机阶段先确认会话可操作与 BUG-001 条件，再按驱动报告 `live_checklist` 串行执行；定因后才决定是否修复及是否需要可识别错误码/边界披露；T01 收口工具描述/README/能力页（需求见下）；T10 决定版本与发布。

## 给 T01 的公共文档变更需求

1. `creo_extrude` 工具描述补 BUG-046 现状：钣金件上的实体增料支持集合**未确认**（历史 -1 已登记，本批离线只完成三路对照准备），cut 在钣金件上可用；结论确定前不要写“钣金增料已修复/均可用”。
2. 若实机确认该组合不支持：能力页/README 明确“钣金模型仅支持 cut + 壁/折边增料路径”，并指引 `sheetmetal_wall`/`sheetmetal_flange`；错误信息给出可识别错误码，不再以裸 `-1` 暗示任意几何均可。
3. 状态文案沿用“实现待原生验收”；实机后补三路体积/去料实测、根因与支持集合结论。

## 给集成人的冲突文件与接口变化

- 无生产代码改动：`native/generic.cpp`（T02/T06/T08B/T09B 共享面）、`native/advanced.cpp`（T05/T11/T12 共享面）、`src/creo_mechdog/schema.py`（T02/T05 共享面）本批均未触碰，无合并冲突面。
- 新增 `tests/unit/test_sheetmetal_overlap.py`、`tools/test_sheetmetal_overlap.py`（离线驱动，默认不连 Creo，`--live` 拒绝并指向唯一 dev 服务的集成实机步骤）；与 T03 的 `test_sheetmetal_contract.py` 并存，复用其报告/指纹约定但不重复其矩阵。
- 接口变化：无（不新增工具、字段、错误码）。行为变化：无（拒绝规则均为既有契约的回归断言）。
