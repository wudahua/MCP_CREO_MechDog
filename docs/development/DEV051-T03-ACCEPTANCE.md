# DEV-051 T03 验收卡：钣金壁参数（BUG-032，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线阶段完成 / 实现待原生验收**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。状态不是“已修复”：depth/thickness 矩阵的实机体积、三轴 bbox/重心、驱动面回显、下游折边/展开、revision 与保存重载均未执行，见“未测项”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T03 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（T03 节）、[T00 验收](DEV051-T00-ACCEPTANCE.md)、[T02 验收](DEV051-T02-ACCEPTANCE.md)、[BUG-032 工作卡](../work-items/BUG-032.md)。
- 反馈证据（外部原始记录，本次未重取）：0.3.1 P2-8 闭合矩形 depth=1/30 均 vol=140、z∈[0,1]；0.3.2 S5 `sheetmetal_wall(depth=1.0, thickness=232.0)`、线长 185 得 9 957 440 mm³（job `667c71ae0958460bb63c8fd17b3f1af3`）；0.3.2 前后另报 YZ 草图、线 232、t=1、depth=185、direction=negative 得 42 920 mm³。
- 受派范围仅 T03 离线阶段：不连接 Creo、不启动 MCP/Creo、不改版本、不合 main、不推标签/不 push、不发布、不实施其他任务。工作区既有无关文件（`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`）未暂存、未改写、未删除。
- 依赖 T02 契约（`dir` 缺省 +1 等）未触及；本批改动不读写弧方向字段。

## 根因（离线静态定因，非猜改参数顺序）

原生当前实现（`native/advanced.cpp` `generic_sheetmetal_wall`）分两步：

1. 用 `extrude_or_revolve` 建薄壁拉伸：`depth` → `PRO_E_STD_EXT_DEPTH/PRO_E_EXT_DEPTH_TO_VALUE`，`thickness` → `PRO_E_THICKNESS`，材料侧 `PRO_EXT_MATERIAL_BOTH_SIDES`。**两参数在 Python 与原生均分别传递，来源中不存在 Python 覆写、交换或读错字段**（`server.py`、`schema.SheetmetalWallOp`、`generic.cpp:1768-1786` 均按名取值；单测断言校验后 depth/thickness 原值不变）。
2. 用 `PRO_DTM_SRF_AS_WALL` 转换该实体为原生钣金壁。SDK 文档（`ProSmtDrvSurf.h`）说明该转换以**一个驱动面**加 `PRO_E_STD_SMT_THICKNESS` 重建壁：几何 = 驱动面面内尺寸 × 厚度。旧代码用“bbox 面积最大的平面”挑驱动面，于是：

| depth,thickness | 薄壁拉伸后实体 | 各向平面面积（Z/Y/X） | 旧代码选中的驱动面 | 转换后体积 | 正确值 L·t·d |
| --- | --- | --- | --- | --- | --- |
| 1, 232 | 185×232×1 | 42 920 / 185 / 232 | Z（法向=深度轴） | 185×232×**232** = 9 957 440 | 42 920 |
| 232, 1 | 185×1×232 | 185 / 42 920 / 232 | Y（法向=厚度轴） | 185×232×1 = 42 920 | 42 920 |
| 1, 1 | 185×1×1 | 185 / 185 / 1 | Z（并列取首） | 185×1×1 = 185 | 185 |
| 2, 1 | 185×1×2 | 185 / 370 / 2 | Y | 185×2×1 = 370 | 370 |
| 0.5, 1 | 185×1×0.5 | 185 / 92.5 / 0.5 | Z（法向=深度轴） | 185×1×1 = 185 | 92.5 |

结论：报告的 9 957 440 = 185×232×232 与“驱动面选到深度法向面、厚度沿深度轴再施加一次”完全吻合（比值恰为 232），也与同一报告里 (232,1) 得 42 920（此时 Y 面最大、恰好等价）自洽。差异来源是**转换阶段的驱动面选择**，不是坐标系不同、不是 Python 覆写、也不是参数顺序；旧代码在 (1,232) 与 (0.5,1) 上都会静默改写几何（分别 ×232 与 ×2）。

闭合轮廓（0.3.1 P2-8）缺少完整坐标、厚度与两个 depth 到 job 的对应关系，其 vol=140 不能按上表定量复算，本次不作数值结论。该类截面没有唯一驱动面语义，按 BUG-032 自身验收口径（“若不支持该组合，在建模前给准确说明且模型/revision 不变”）改为**建模前拒绝**。

## depth/thickness 契约（固定帧）

固定帧：单条开放直线 185 mm 沿草图 X 轴（XY 基准面），direction=positive。约定 `thickness` 是板厚（薄壁面内偏置宽度），`depth` 是沿草图法向的拉伸距离，因此体积 = 线长 × 厚度 × 深度，三轴名义尺寸为 {185, thickness, depth}。**符号/原点偏移（薄壁向 +Y 或 −Y、拉伸向 +Z 或 −Z）属实机待核项**，离线只锁定各轴尺寸与体积。

| depth | thickness | 期望体积 mm³ | 期望三轴尺寸 mm（X/Y/Z） | 期望重心 mm（按 +Y/+Z 约定） |
| --- | --- | --- | --- | --- |
| 1 | 232 | 42 920 | 185 / 232 / 1 | 92.5 / 116 / 0.5 |
| 232 | 1 | 42 920 | 185 / 1 / 232 | 92.5 / 0.5 / 116 |
| 1 | 1 | 185 | 185 / 1 / 1 | 92.5 / 0.5 / 0.5 |
| 2 | 1 | 370 | 185 / 1 / 2 | 92.5 / 0.5 / 1 |
| 0.5 | 1 | 92.5 | 185 / 1 / 0.5 | 92.5 / 0.5 / 0.25 |
| 闭合矩形（任意 depth/thickness） | — | 不支持 | — | 建模前拒绝，模型/revision 不变 |

## 实现（只改已确认根因）

1. **驱动面改为厚度轴法向面**（`native/advanced.cpp`）：由新壁实体 bbox 找出尺寸≈`thickness` 的轴（相对误差 ≤2%），只在该轴的两个边界平面中按面内面积选取驱动面，并写 `SHEETMETAL_WALL_DRIVING_FACE`（id/axis/normal/area）。识别不到厚度轴时明确报错，不再退回“最大面”。
2. **截面准入**（`first_wall_line_length`）：转换前用 `ProFeatureSectionCopy` 读取草图 section，忽略 construction/projection/centerline，要求恰好 1 条直线；否则在建任何特征前报错。该检查位于原生操作入口，**独立工具与 execute_plan 共用**，也覆盖 Python 看不到实体的跨作业草图引用。
3. **参数不被静默改写**：转换后按 `线长 × thickness × depth` 校验实测体积（容差 max(0.01 mm³, 0.1%)），不符即失败并给出实测/期望值；通过时把 `wall_contract{line_length_mm, expected_volume_mm3, measured_volume_mm3, driving_face_id, driving_axis}` 记入该特征别名记录（实测值与前缀明确的期望值并列，不回填请求值冒充实测）。
4. **计划级准入**（`src/creo_mechdog/schema.py` `validate_operations`）：同计划内声明的草图若不是一个开放直线，在建模前以 `operations[N]: ...` 拒绝；判定逻辑放在新模块 `src/creo_mechdog/sheetmetal.py`，独立工具与计划都经同一 `validate_operations`（`generic_bridge.submit`）。
5. 未改：schema 字段与类型、`depth`/`thickness` 取值范围、`direction`、钣金转换元素（`PRO_E_STD_MATRLSIDE=0`、`SWAP_DRV_SIDE=0`、厚度元素）保持不变；旧合法参数（开放直线）仍被接受。

## 入口覆盖表

| 入口 | 路径 | 截面准入 | 参数保持 | 实测证据 |
| --- | --- | --- | --- | --- |
| 独立工具 `creo_sheetmetal_wall` | `server.py` → `general.submit` → `validate_operations`（同计划草图可前置拒绝）→ 原生 | 原生必查（种子草图可先拒） | 驱动面 + 体积恒等式 | 待实机 |
| 计划 `creo_execute_plan` | 同上 | 同上（同计划草图前置拒绝） | 同上 | 待实机 |
| 跨作业草图引用 | Python 无实体信息 → 原生 `first_wall_line_length` | 原生 | 同上 | 待实机 |
| 非法/不适用组合 | 闭合矩形/闭合 polyline/arc/circle/spline/多段链/仅中心线/仅构造线 | Python（同计划）或原生（跨作业）在建特征前拒绝 | 不变 | 待实机（模型/revision 不变） |

## 实际修改文件

`native/advanced.cpp`；`src/creo_mechdog/schema.py`；新增 `src/creo_mechdog/sheetmetal.py`、`tests/unit/test_sheetmetal_contract.py`、`tools/test_sheetmetal_contract.py`、本卡；更新 `docs/work-items/BUG-032.md`。未改 `version.py`、`server.py` 签名/描述、根兼容包装、台账、README、`native/generic.cpp` 与 `native/sketch_edit.cpp`（T02 契约不动）。提交仅按这些精确路径暂存。

## 依赖提交、受测身份与指纹

- 依赖提交：`2726ca54715d547c71c7de61c24fb214ac7f6864`（T00）→ `a3c1f4b3e05668aa57d7225dc16394dd272abec9`（T02，本卡基线）。
- 实现提交：`601b4bcaca861b2d1edd9930a17cf4752d9768d8`（本卡首次提交；本节的指纹补正为其后的同任务提交）。
- 受测 commit：`601b4bcaca861b2d1edd9930a17cf4752d9768d8` + 工作区既有无关修改（`session_activity.json` 等未提交）；dirty=true。
- `source_fingerprint`：`fc7ced085fd0ea26aad16f0e321a0475cc74aa4325748a9adce3ab54afccf127`（`tools/test_sheetmetal_contract.py` 的 provenance 算法：全部已跟踪 `*.py` 与 `native/*.h|*.hpp|*.cpp` 的 CRLF 归一化 SHA256 清单哈希，另加本任务两个新增测试文件的显式路径；对应报告 `build/sheetmetal_contract/20261028T210821_dffd031b/report.json`，SHA256 `73cd0c5ef9557dba0c15df29ba81191b8a9ecad53fbf25466e033ee61592c53b`）。
- 追溯说明：提交前同一内容的一次运行得到 `3a52f4ff…`（报告 `build/sheetmetal_contract/20261028T210643_b9e02018/report.json`）。差异仅因 `src/creo_mechdog/sheetmetal.py` 当时未被 git 跟踪而不在 `git ls-files` 清单中，源码内容相同；以上述 `fc7ced08…` 为准，勿混用两个指纹的结论。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；pydantic 2.13；ruff 0.17.0、clang-format 23.1.3（requirements-dev 锁定）；MSVC x64 与 Creo 12.4.0.0 匹配 Toolkit SDK（仅用于离线编译/读取 SDK 头文件）。全程未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业；服务版本入口仍为 0.7.2。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_sheetmetal_contract -v` | exit 0（经 `Start-Process` 取值），Ran 18 tests，OK。注意：PowerShell 直接调用时因 unittest 写 stderr 会被包装成 NativeCommandError 并返回 1，属调用方式伪影，非测试失败 |
| 2 | `.venv\Scripts\python.exe tools\test_sheetmetal_contract.py` | exit 0；实现提交后运行报告 `build/sheetmetal_contract/20261028T210821_dffd031b/report.json`，SHA256 `73cd0c5ef9557dba0c15df29ba81191b8a9ecad53fbf25466e033ee61592c53b`（另有 `report.sha256`）；内置复跑单元 18/18 OK。提交前同内容的一次运行见上节追溯说明 |
| 3 | `.venv\Scripts\python.exe tools\dev_check.py` | exit 0；`success=true`、`unit_tests=passed`、`regressions=[]`；style `lint_findings=30`、`unformatted_files=16`（均为存量基线计数，前一次运行 31/17 含本批新增文件）；`checked_source_sha256=cb2dc045234a2091feef88f3a1062dc7b72d5208c4bd20d6e05cb982bd7c9d98`；报告 `build/development_check.json` |
| 4 | `.venv\Scripts\python.exe bridge.py build` | 成功；`build/build.log`：`COMPILER_PREFLIGHT` 通过 → 编译 `worker.cpp`，仅 3 条存量 C4819（`assembly_units.h`、`assembly_walk.h`、`generic.cpp`，代码页 936 警告，与本批无关），无错误；`build/creo_worker.exe` 重新生成（2026-10-28 20:56:05），`build/source.sha256` 更新为 `f18383ec…b45e11` |

测试覆盖（离线，不实例化 MCP 客户端）：矩阵 5 例被接受且 depth/thickness/direction 原值保留；按独立 oracle 计算体积与三轴尺寸（含 185×232×1 与 185×1×232 同为 42 920）；9 957 440 与 42 920 的比例关系及“深度被厚度替换”的算术特征；合法直线 40×1×30=1200 旧参数回归与 direction=negative 保留；独立工具 payload 与 execute_plan 两种提交形态；闭合矩形、闭合 polyline、arc、两段链、仅中心线、仅构造线的拒绝与 `operations[1]` 定位；跨作业草图由原生兜底的说明性用例；非正/超界 depth/thickness 与非正 direction 的拒绝；`first_wall_section_problem` 直接判定。oracle 期望值全部在测试与驱动内按声明契约推导，不调用生产归一化/校验函数生成。

## 未测项与下一步

- 未测（需实机，按共同契约另行指派并在唯一 dev 服务串行执行）：5 例矩阵真实体积/三轴 bbox/重心（容差 0.01 mm³）、`SHEETMETAL_WALL_DRIVING_FACE`/`SHEETMETAL_WALL_VOLUME` 实际值、厚度轴识别（依赖“薄壁面内尺寸 = thickness”这一 0.3.2 证据推论）、材料侧与 bbox 摆放、闭合/弧/链拒绝后模型与 revision 不变、失败回滚证据、下游 flange/展开/折回、revision 与 `saved_file_reloaded_and_verified=true`。
- 未测：`wall_contract` 别名新增字段在 `creo_get_model`/detail 投影中的呈现与 32 KiB 预算；WorkBuddy 黑盒验收；Creo 9/10 环境。
- 缺材料：0.3.1 闭合轮廓坐标/厚度与 job 对应关系缺失（不影响开放直线定因）；无法据原件重放闭合分支，已改为明确拒绝。
- 下一步：集成人按“给集成人的冲突文件与接口变化”合并；实机阶段先确认会话可操作与 BUG-001 条件，再串行跑矩阵与拒绝用例；T01 收口工具描述/README/能力页；T04/T05/T11 使用本轮确认后的开放直线底板（185×232×1 = 42 920 mm³）作为基体；T10 决定版本与发布。

## 给 T01 的公共文档变更需求

1. **`creo_sheetmetal_wall` 工具描述**（`server.py` docstring，现为 “Create the first flat sheetmetal wall from an open straight-line sketch, depth and thickness … Curved or closed first-wall sketches are not validated”）改为明确契约：仅接受**恰好一条开放直线**的截面；`thickness` 为板厚（薄壁面内宽度），`depth` 为沿草图法向的拉伸距离；体积 = 线长 × thickness × depth；闭合轮廓、弧、样条、多段链在建模前拒绝（不再写“not validated”这种“可能被接受”的表述）。
2. **能力页/README 钣金章节**：给出 185×232×1 = 42 920 mm³ 与 185×1×232 = 42 920 mm³ 两个等价示例，说明参数语义与三轴名义尺寸；说明非法组合会返回明确错误且模型/revision 不变。
3. **勘误**：0.3.x/0.7.x 文档中“depth 被 thickness 覆盖”的表述应改为“转换阶段以单一驱动面重建壁，旧实现在 depth< 面内尺寸时改写厚度轴”，避免把根因归到请求层。
4. 修复状态文案沿用“实现待原生验收”，在实机矩阵通过前不要写成“已修复”；实机后补充实测体积/bbox/重心与 `wall_contract` 字段说明。

## 给集成人的冲突文件与接口变化

- 共享冲突面：`native/advanced.cpp`（T05/T11/T12）、`src/creo_mechdog/schema.py`（T02/T05 已改，新增 import 与 `validate_operations` 一处分支是叠加，未改 T02 的 `dir` 契约）。本批**未**改 `native/generic.cpp`、`native/sketch_edit.cpp`、`profile_diagnostics.py`、`operation_results.py`。
- 接口变化（均为增量）：新增包内模块 `creo_mechdog.sheetmetal.first_wall_section_problem`；`sheetmetal_wall` 特征别名记录新增 `wall_contract` 对象（实测线长/实测体积/期望体积/驱动面 id/轴）；原生新增日志 `SHEETMETAL_WALL_LINE_LENGTH_MM`、`SHEETMETAL_WALL_DRIVING_FACE`、`SHEETMETAL_WALL_VOLUME`。
- 行为变化：非“单条开放直线”的第一壁截面由“成功但几何被改写”改为**建模前失败**（同计划草图在 Python 拒绝，跨作业草图在原生拒绝）；其余合法输入不变。
- 合并注意：若集成时保留旧的“最大 bbox 面”驱动面逻辑，`tools/test_sheetmetal_contract.py` 的 `native_source` 静态断言会失败（`largest_face_heuristic_removed=false`），可据此发现回退。
