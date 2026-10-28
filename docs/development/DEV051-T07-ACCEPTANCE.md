# DEV-051 T07 验收卡：多环替代补验（BUG-049，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线复核完成 / 替代夹具待原生验收 / 原案仍开放**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次未连接 Creo、未启动 MCP/Creo、无 Toolkit 作业；原生源码无改动。状态不是“缺陷已修复”：5/10 四弧环的实机 cut 结果尚未取得，原始 gear10 案不可逐字回放，见“未测项”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T07 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（BUG-049/T07 节）、[BUG-049 工作卡](../work-items/BUG-049.md)、[DEV-049 T05 记录](DEV049-T05-ACCEPTANCE.md)、[DEV051-T02](DEV051-T02-ACCEPTANCE.md)/[T03](DEV051-T03-ACCEPTANCE.md)/[T06](DEV051-T06-ACCEPTANCE.md) 验收卡。
- 复用既有驱动 `tools/test_dev049_profile_replay.py` 与 `tests/unit/test_dev049_profile_replay.py`（DEV-049 T05 交付），**未重新开发同类脚本**；本批只做核对、显式 `dir=+1` 等价对照与记录。
- 受派范围仅 T07 离线阶段：不连接 Creo、不改版本、不合 main、不推标签/不 push、不发布、不实施其他任务。工作区既有无关文件（`.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`docs/work-items/BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、untracked 的 `0.7.2-FEEDBACK-*` 与 `docs/validation/feedback-0.7.2-2026-10-28/`）均未暂存、未改写、未删除。

## 原件查缺（T07 第 1 项）

2026-10-28 复核：项目工作树与文件名检索（`gear10*`、`sketch_entities*`、`Part2*`）在仓库内只有文档/夹具注释中的文字引用，无任何原始 JSON/PRT/图像；`C:\Users\Administrator\Downloads\0.7.0` 只有四份 0.7.0 反馈 Markdown；`C:\Users\Administrator\Downloads` 近期文件与既有检索范围（含 0.6.1、`build/*.zip`）内亦无 `gear10.json`/`sketch_entities.json`/原 Part2 模型或预览图。**原 gear10 未新近取得**，继续标 `original_case_replay=not_possible_missing_attachments`、`replacement_verification=true`（驱动 `original_inputs()` 已补 `last_checked` 与含 `0.7.0` 的检索范围）。原件获得后另做原样重放；在此之前原案保持开放。

## 复核范围与结论（T07 第 2、3 项）

| T07 要求 | 复核方式 | 结论 |
| --- | --- | --- |
| 2 圆/5 环/10 环几何拓扑 | 夹具逐环 `closure_gap ≤ 1e-9`（四段 0→90/90→180/180→270/270→360 弧闭合，2 圆为单 circle 实体）；环数/实体数显式 2/2、5/20、10/40 | 通过（离线） |
| 相离关系 | `pairwise_gap`（中心距 − 两半径）> 0：2 圆最小 12.0 mm（±8、R2），5/10 环最小 6.0 mm（间距 12、R3） | 通过（离线） |
| 面积×厚度 oracle | 独立解析 πr² 与采样多边形+外推交叉核对（不调用生产逻辑）：2 圆 25.132741228718345 mm²×5 = 125.66370614359172 mm³（与报告 125.663706 六位一致）；5 环 141.3716694115407→706.8583470577034 mm³；10 环 282.7433388230814→1413.7166941154069 mm³；错误值（0/双倍/深 8/直径混淆/非数值）全部被拒 | 通过（离线） |
| 报告不覆盖 | `resolve_output` 拒绝已存在路径，且在任何连接前返回 2；每次运行新 `build/dev049_t05/<run_id>/report.json` | 通过（离线） |
| 默认离线 | 无双开关时打印 `OFFLINE ONLY`，不实例化 MCP 客户端、不调 `live()` | 通过（离线） |
| 双门槛 | 单独 `--live` 或 `--confirm-session-usable` 一律离线并说明缺另一开关；两者齐全才进 live 入口 | 通过（离线） |
| 旧不带 dir 输入 | 三例 live 输入仍为不含 `dir` 键的旧实体（T02 缺省 +1 语义不变），单元 `test_live_cases_still_carry_no_dir_key` 断言不变 | 通过（离线） |
| 显式 `dir=+1` 等价对照（T02 已集成） | 新增 `explicit_dir_equivalence()`：同坐标 5/10 环行的旧输入 vs 显式 `dir=+1` 输入，逐实体比较（除 `dir` 外字段相等、旧实体无 `dir` 键）、T02 扫角规则 `(end-start)%360` 均为 90.0° 且两侧行一致、解析面积逐位相等、闭合/相离保持、显式计划过 `validate_operations` | 通过（离线等价；实机几何等价待验） |
| 不写两环上限/不自动并集吸附分组 | 报告 `contour_limit_claim=not_asserted`，驱动无并集/吸附/分组/重试逻辑；单元 `test_no_contour_limit_is_claimed` | 保持 |

替代失败定位约定（实机阶段约束，写入 BUG-049）：若替代夹具实机失败，先固定草图平面、方向、材质侧与容差并定位，保留原始错误码/回滚，不自动并集/吸附/分组重试，不写未经证实的“两环上限”。

## 本批修改文件

`tools/test_dev049_profile_replay.py`（`arc_ring`/`ring_row` 增加可选 `arc_dir`，缺省不写 `dir` 键；新增 `explicit_dir_equivalence()` 并进入离线报告 `dir_equivalence`；`original_inputs()` 增加 `last_checked` 与含 `0.7.0` 的检索范围）；`tests/unit/test_dev049_profile_replay.py`（新增 `ExplicitDirEquivalenceTests` 4 项，既有用例未改动）；本卡；`docs/work-items/BUG-049.md`（只追加）。未改 `version.py`、生产/原生代码、schema、根兼容包装、台账、README、两份计划与另一会话文件。提交仅按这些精确路径暂存。

## 依赖提交、受测身份与指纹

- 依赖提交（基线）：`414d1f7cabb9900711c6eaed9bba64ed67591320`（分支 HEAD，含 T06；T02 实现已在本分支集成，`src/creo_mechdog/schema.py` Arc 具备严格 `dir` 字段）。
- 实现提交：本卡所属 T07 提交（提交号不能自指写入同一提交文件，以交接报告 `git rev-parse HEAD` 为准）。
- 受测 commit：`414d1f7cabb9900711c6eaed9bba64ed67591320` 工作树 + 本批 T07 改动；dirty=true（含本批改动与另一会话/本机运行数据的未提交文件）。
- `source_fingerprint`：`94ce9cb02cd5058f9893534eaf8f49c8256b960c31db55c08e8a0f157334b098`（驱动 provenance 算法：`git ls-files` 的全部 `*.py` 与 `native/*.h|*.hpp|*.cpp` 加本任务两个测试文件的 CRLF 归一化 SHA256 清单哈希；对应报告 `build/dev049_t05/20261028T224733_0c2838ab/report.json`，为格式化后最终源码的一次运行）。
- `tools/dev_check.py` 的 `checked_source_sha256`：`16dd97ba873213b0e0b9c2b418ba479f78a2c964a692ccb93e3d49b64bdfb1a3`（同一最终源码内容）。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；ruff 0.17.0（requirements-dev 锁定）；全程未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业。原生源码无改动，按任务约定未强制 `bridge.py build`。服务版本入口仍为 0.7.2，未改。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_dev049_profile_replay -v` | 首轮 exit 1：Ran 33，7 errors，全部由本批新增 `explicit_dir_equivalence()` 的 `zip(legacy, strict=True)` 漏传第二序列导致（`ValueError: not enough values to unpack`）；修复为 `zip(legacy, explicit, strict=True)` 后复跑 exit 0，Ran 33 tests，OK（格式化后再次复跑 Ran 33，OK）。既有用例未修改、未跳过 |
| 2 | `.venv\Scripts\python.exe tools\test_dev049_profile_replay.py`（默认离线） | exit 0；`offline_cases=3 validated`、`original_case_replay=not_possible`、`replacement_verification=true`、`reported_control_agrees=True`、`LIVE NOT RUN`；最终报告 `build/dev049_t05/20261028T224733_0c2838ab/report.json`，SHA256 `E9F52AC20E81B10992DEF1391AA7C4747D12E771ADF6F40C80C621EC1AAEA5DB`，`dir_equivalence.passed=true`（5/10 两行 `sweeps=90.0`、面积逐位相等、显式计划过 schema） |
| 3 | `.venv\Scripts\python.exe -m unittest discover -s tests` | 最终源码上 exit 0，Ran 1233 tests in 270.604s，OK（格式化前同源码亦 Ran 1233，OK） |
| 4 | `.venv\Scripts\python.exe tools\dev_check.py` | 首轮 exit 1，唯一回归项 `tools/test_dev049_profile_replay.py: new or changed file must pass its formatter`；用 ruff format（0.17.0）格式化该文件（`1 file reformatted`）后复跑 exit 0：`success=true`、`unit_tests=passed`、`native_validation=not_run`、`style_summary` lint 30 / unformatted 16（均为存量基线计数）、`checked_source_sha256=16dd97ba…bdfb1a3`，报告 `build/development_check.json`，SHA256 `894EB9D2FC48DE7ACBFA81A1AAA2372794B4A1DA9D4048BF749C174593DC19D7`。未改基线、未跳过检查 |

说明：#3 与 #4 首轮在格式化前的同一内容上运行，格式化只改空白；为避免混用指纹，#1、#2、#3 的最终通过记录均在格式化后的最终源码上重新取得，#4 的最终通过即该源码内容。不把不同运行的通过数合并计算。

## 未测项与下一步

- 未测（需实机，另按共同契约指派并在唯一 dev 服务串行执行）：2 圆、5 环、10 环三例 cut 的真实 section 环数/实体数/开端数、独立去料体积（面积×厚度 ±0.01 mm³）、原生特征健康（cut+1、protrusion+0）、revision、`saved_file_reloaded_and_verified=true`、失败原码与真实回滚、busy/单通道行为；显式 `dir=+1` 输入的实机几何等价；单一受测源码指纹上的完整矩阵判断。
- 缺材料：`gear10.json`、`sketch_entities.json`、原 Part2 模型/预览图仍缺失，原 gear10 案 `not_possible_missing_attachments`，**原案保持开放**，不以本替代范围关闭 BUG-049 父卡其他范围。
- 下一步：会话条件满足（人工确认可操作、BUG-001 条件）后由唯一 dev 服务串行执行 `tools\test_dev049_profile_replay.py --live --confirm-session-usable`；替代失败按上文固定平面/方向/材质侧/容差定位；原件获得后另做原样重放（先离线核对闭合/面积/图元/交点再实机）。T01 收口时补工具说明；T10 决定版本与发布。

## 给集成人的冲突文件与接口变化

- 无共享生产冲突面：本批只改 `tools/test_dev049_profile_replay.py`、`tests/unit/test_dev049_profile_replay.py`、本卡与 BUG-049 追加段，未触碰 `native/*`、`schema.py`、`server.py`、版本与主台账。
- 接口变化：无生产接口变化。驱动 `arc_ring`/`ring_row` 增加可选 `arc_dir`（缺省 None=旧输入，不写 `dir` 键），live 提交输入不变；离线报告新增 `dir_equivalence` 字段与 `original_inputs.last_checked` 字段（只增不改旧字段）。
