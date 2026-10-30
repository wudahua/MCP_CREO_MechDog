# DEV-051 T02 验收卡：显式弧方向（FEAT-034，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线阶段完成 / 实现待原生验收**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。状态不是“已修复”：显式弧方向的实机闭环（创建/编辑/revision/保存重载/体积容差）尚未执行，见“未测项”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T02 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（FEAT-034/T02 节）、[T00 验收](DEV051-T00-ACCEPTANCE.md)、[FEAT-034 工作卡](../work-items/FEAT-034.md)。
- 0.3.3 报告 B 第 4 节的原始对照数值（R10 弧加弦、深 5：0→90 得 142.699081698 mm³、90→0 得 1428.097245102 mm³）沿用 FEAT-034 卡登记的外部证据；本次不重取原件。
- 受派范围仅 T02 离线阶段：不连接 Creo、不启动 MCP/Creo、不改版本、不合 main、不推标签、不发布、不实施其他任务。工作区既有无关文件（`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`）未暂存、未改写、未删除。

## 输入/输出字段契约（T02 交接）

**输入（弧实体，创建/execute_plan/update_sketch_geometry/分析器共用一套 schema）：**

| 字段 | 契约 |
| --- | --- |
| `dir` | 严格整数 `+1`=CCW、`-1`=CW；缺省 `+1`（旧 start/end 语义不变）。拒绝 bool、浮点 `1.0`、字符串 `"1"`、`null`、`0`、`±2` 及其他值，错误消息含 “strict integer”。 |
| `start_angle` / `end_angle` | 有限角度（度，`allow_inf_nan=False` 加显式 isfinite 校验）。 |
| 扫角 | dir=+1 为 `(end-start) mod 360`，dir=-1 为 `(start-end) mod 360`；结果为 0（零扫角或整圆）一律拒绝并指引改用 `circle`。合法大弧（如 270°）与跨零（如 350→10）允许。 |

**输出（结果回显，杜绝回声输入冒充实测）：**

- 建模结果（`op=sketch` 与 `op=update_sketch_geometry`）新增 `arc_geometry`：每个弧实体一条
  `{name, source, query_code, frame, start_uv, end_uv, start_tangent_uv, end_tangent_uv, dir, sweep_deg}`。
  - `source="native"`：值为执行器对已创建/已重建 section 的实际查询结果，映射到用户局部帧（`frame="sketch_local"`），`query_code=0`。
  - `source="unknown"`：查询不到时返回未知/原码（`query_code` 为原始 ProError 或 section 复制码，无码则 `null`），全部值字段为 `null`；绝不填入请求值。不完整的 `native` 记录自动降级为 `unknown`。
- `update_sketch_geometry` 结果新增 `frame`（`origin/u_axis/v_axis/normal`，来自建模时记录的实际帧）；创建结果原有 `origin/normal/u_axis/v_axis/native_section` 不变。
- 分析器 `analyze_profile` 报告新增 `arc_geometry`，记录为 `source="input"` 的输入侧逻辑几何（起终点/切向/dir/扫角/`frame="sketch_local"`）；与实测回显分字段呈现，不互相冒充。

**底层交换端点规则：** 原生 `Pro2dArcdef` 恒为 CCW；dir=-1 或 section 镜像帧时存储角度交换，交换状态按实体记录（id/name 两级）。交换后用户局部帧中的逻辑起终点、实体名与尺寸/约束绑定保持不变：`start`/`end` 引用经 `logical_point` 映射，坐标极坐标尺寸名 `_start_angle`/`_end_angle` 跟随逻辑端点。

## 入口覆盖表

| 入口 | 路径 | dir 消费 | 逻辑端点/命名绑定 | 实测回显 |
| --- | --- | --- | --- | --- |
| 独立创建 `creo_create_sketch` | schema → `native/generic.cpp` `sketch()` 建弧路径 | 是 | 是 | 是（`arc_geometry`） |
| 计划 `creo_execute_plan`（含 sketch op） | 同上 | 是 | 是 | 是（同一结果投影） |
| 几何更新 `creo_update_sketch_geometry` | schema → `native/sketch_edit.cpp`（匹配 + 重建） | 是 | 是 | 是（含 `frame`） |
| 分析器 `analyze_profile` / `validate_solid_profile` | `src/creo_mechdog/profile_diagnostics.py` | 是（有符号扫角） | 不适用（输入分析） | 输入侧回显（source=input） |
| 嵌套 profile（`populate_profile`，advanced 特征） | `native/generic.cpp` 第二建弧路径 | 是 | 是 | 未提供（结果结构随 advanced 集成，如实记未覆盖） |

## 实际修改文件

`src/creo_mechdog/schema.py`、`profile_diagnostics.py`、`operation_results.py`；`native/generic.cpp`（共享归一化/逻辑端点映射、两条建弧路径、`arc_geometry_report`）、`native/sketch_coordinates.cpp`（极坐标尺寸逻辑命名）、`native/sketch_edit.cpp`（dir 匹配/重建/回显）；新增 `tests/unit/test_arc_direction.py`、`tools/test_arc_direction.py`；本卡。提交仅按这些精确路径暂存；`session_activity.json` 及上述既有无关文件不提交。未改 `version.py`、根兼容包装、台账、README、FEAT-034 首页（首页与工具说明属 T01 收口，见“下一步”）。

## 依赖提交、受测身份与指纹

- 依赖提交（基线，DEV-051 T00）：`2726ca54715d547c71c7de61c24fb214ac7f6864`。
- 实现提交：本卡所属 T02 提交，以交接报告和 `git rev-parse HEAD` 为准（提交号不能自指写入同一提交文件）。
- 受测 commit：`2726ca54715d547c71c7de61c24fb214ac7f6864` 工作树 + 本批 T02 改动；dirty=true（含本批改动及既有无关文件）。
- `source_fingerprint`：`a27a2ead25c5ea7ff467f548a4fe09518b4a7d93de3059d810b952ac260353f4`（`tools/test_arc_direction.py` 的 provenance 算法：全部 `*.py` 与 `native/*.h|*.hpp|*.cpp` 的 CRLF 归一化 SHA256 清单哈希；对应报告 `build/arc_direction/20261028T191145_ad8f59a1/report.json`）。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；pydantic 2.13；ruff 0.17.0、clang-format 23.1.3（requirements-dev 锁定）；MSVC x64 与 Creo 12.4 匹配 Toolkit SDK 可用（仅用于离线编译；全程未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业）。服务版本入口仍为 0.7.2，未改。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `..venvScriptspython.exe -m unittest tests.unit.test_arc_direction -v` | exit 0，Ran 29 tests，OK（格式化前后多次一致） |
| 2 | `..venvScriptspython.exe tools	est_arc_direction.py` | exit 0；报告 `build/arc_direction/20261028T191145_ad8f59a1/report.json`，SHA256 `3027c9fc4628d91b3ae9fb2ebc851d2dcc2f304500cb75e3111ef6e88cebf984`（另有 `report.sha256`）；内置复跑单元 29/29 OK |
| 3 | `..venvScriptspython.exe -m unittest discover -s tests -v` | Ran 1157 tests，FAILED (errors=1)；唯一错误见下节“网络受限安装夹具” |
| 4 | `..venvScriptspython.exe toolsdev_check.py` | style 无回归（`regressions=[]`，lint/unformatted 均为存量基线计数）；`unit_tests="failed"`（同 #3 唯一错误）；`success=false`；报告 `build/development_check.json` |
| 5 | `..venvScriptspython.exe bridge.py build` | 成功，产出 `build/creo_worker.exe`（仅编译执行器，未连接 Creo）。首次编译失败（`sketch_edit.cpp` C2065 “mirrored 未声明”＝MSVC 旧 lambda 捕获缺陷，及连锁 C2440），按本文件既有规避模式（在 lambda 体前部先行引用）修复后通过；失败日志 `build/build.log` 同文件覆盖重写 |

测试覆盖（离线，不实例化 MCP 客户端）：dir 严格契约（bool/1.0/"1"/null/0/±2/列表/对象拒绝；缺省 +1；有限角度；零扫角/整圆拒绝指引 circle；180/270°/跨零接受）；旧输入回归与独立 oracle（R10+弦×5：旧 0→90＝125π−250≈142.699081699 mm³、旧 90→0＝375π+250≈1428.097245096 mm³、90→0 且 dir=-1＝前者、0→90 且 dir=-1＝后者；两段体积和＝πR²×深）；分析器有符号扫角（180/270/跨零/反向同几何）；旋转帧与翻转帧（翻转帧同物理弧 dir 取反、扫角不变）；非法编辑拒绝（update 入口）；下游方向切换体积互补；回显投影（native 透传、缺失=unknown+空值、原码保留、不完整 native 记录降级、请求值绝不进入实测字段）。oracle 期望值在测试与驱动内独立按声明 dir 推导，不调用生产归一化/分析函数生成。

### 网络受限安装夹具（与本次改动无关，如实保留）

`tests/test_installation_validation.py::test_installer_native_failure_leaves_client_config_and_resume_instructions` 在临时沙箱运行 `setup.ps1`（不复制 `native/`，原生构建按设计停在编译预检），其“Python source package”阶段执行 `pip install --no-deps --editable` 需联网拉取构建依赖 `setuptools==80.9.0`。当前代理 TLS 握手超时（原始 pip 输出：`ProxyError('Cannot connect to proxy.', TimeoutError('_ssl.c:993: The handshake operation timed out'))`，5 次重试后 `No matching distribution found for setuptools==80.9.0`），轻载时表现为 90 秒子进程超时（`subprocess.TimeoutExpired`），重试下表现为 `INSTALL_INCOMPLETE: failed at Python source package`。归因实验（仅放宽该子进程时限、不改任何测试/生产代码）复现同一 pip 网络错误，功能断言并不依赖本批改动；同会话早期（同一 Python 源码、网络可用时）全量 1157 曾全通过。未修改、未跳过、未加基线规避该用例。

## 未测项与下一步

- 未测（需实机，另按共同契约指派并在唯一 dev 服务串行执行）：创建与方向编辑的真实几何（端点/切向/方向/扫角/帧实测回显）、两体积与解析值绝对误差 ≤0.01 mm³、下游特征、revision、保存重载 `saved_file_reloaded_and_verified=true`、非法修改保持基线/回滚、busy/单通道行为。以上未执行，不能以离线 oracle 代替。
- 未测：`populate_profile`（advanced 嵌套 profile）路径的实测回显；WorkBuddy 黑盒验收；Creo 9/10 独立环境。
- 缺材料：无（0.3.3 原请求 JSON/PRT 缺失不影响本批契约与 oracle）。
- 下一步：集成人按“给集成人的冲突文件与接口变化”合并；T02 实机验收前需人工确认会话可操作及 BUG-001 条件；T01 统一收口时补充工具描述/README 的 `dir` 与 `arc_geometry` 说明、FEAT-034 首页状态；T10 决定版本与发布。

## 给集成人的冲突文件与接口变化

- 共享冲突面：`native/generic.cpp`（T04/T06/T08B/T09B）、`native/sketch_edit.cpp`、`native/sketch_coordinates.cpp`、`src/creo_mechdog/schema.py`（T03/T05）、`profile_diagnostics.py`、`operation_results.py`。
- 接口变化：弧实体新增可选 `dir`（缺省 +1，严格整数）；sketch/update 结果新增 `arc_geometry`（实测或 unknown/原码）与 update 结果 `frame`；`analyze_profile` 报告新增 `arc_geometry`（source=input）；坐标极坐标尺寸名在交换表示下按逻辑端点命名；`_expand` 对零扫角/整圆弧从“静默按整圆”改为明确拒绝（schema 先拒，此为分析器防御路径）。
- 行为保持：不带 `dir` 的旧请求几何语义完全不变（0→90 与 90→0 回归数值固定）；服务标准输出、busy 契约、revision/回滚语义未触碰。

## 实机阶段（2026-10-29，Creo 12.4.0.0）

用户 2026-10-29 授权直接操作 Creo；会话由其手动打开，`config.json` 保持 `auto_start_creo=false`，新增驱动未启动/关闭 Creo、未注入故障、未清保护。本卡此前的实机入口一直缺失（原 `tools/test_arc_direction.py` 明确拒绝 `--live`），本次新增 `tools/test_arc_direction_live.py`：半径 10 mm 弧 + 弦，拉伸 5 mm，每例独立新件。

串行执行 `tools\test_arc_direction_live.py --live --confirm-session-usable`，**exit 0**，报告 `build/arc_direction_live.json`：

| 用例 | dir | job_id | model_id | revision | oracle mm³ | 实测 mm³ | 误差 mm³ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 旧输入 0→90 | 缺省 | `5eaaa067504149d294e944415b04b8b2` | `84b78e1280f64199a08f0058e7897279` | 1 | 142.69908169872414 | 142.69908169840258 | 3.2e-10 |
| 旧输入 90→0 | 缺省 | `3b209bf3826b403a8b858ff9e2993177` | `b7f3b4c4d673461c8b89faad5161b6f1` | 1 | 1428.0972450961724 | 1428.09724510173 | 5.6e-9 |
| 90→0 且 dir=-1 | -1 | `e31e5c8ff10647dca97718599b86c9c0` | `4d5dff5038304cc98b65b56a10343696` | 1 | 142.69908169872414 | 142.69908169840258 | 3.2e-10 |
| 0→90 且 dir=-1 | -1 | `d12188975415451590a2b4c6c2541449` | `6de96c64cc0d4379acb10dad9abd2708` | 1 | 1428.0972450961724 | 1428.09724510173 | 5.6e-9 |

- 四例误差均远小于 0.01 mm³；**旧语义未变、显式 `dir=-1` 确实反转主弧**，两对结果逐位一致。
- 实测回显为真实原生数据，不是输入复述：`{"source":"native","query_code":0,"frame":"sketch_local","start_uv":[10,0],"end_uv":[0,10],"start_tangent_uv":[0,1],"end_tangent_uv":[-1,0],"dir":1,"sweep_deg":90}`。
- 本组用 `creo_execute_plan`（含 sketch+extrude，无 save 操作），因此**未产生 `saved_file_reloaded_and_verified`**（报告为 `null`）；保存/重载与命令后编辑仍属未测，不得按本组声明。
- 未测：方向编辑（`creo_update_geometry` 改 dir）、下游特征、`revision` 递增语义、非法 `dir` 的实机拒绝、busy/单通道、WorkBuddy、Creo 9/10。

给集成人：本次新增 `tools/test_arc_direction_live.py`（离线默认、`--live` 需双开关），无生产代码改动。

## 2026-10-30：T02 弧方向编辑与保存重载补验——离线阶段

分支 `codex/dev051-feedback070`，接手时 HEAD `641edb3`。上一窗口半成品已在工作区（`tools/test_arc_direction_live.py` 大幅重写），本窗口核对后补完离线阶段：**未连接 MCP/Toolkit、未启动 Creo、未执行 `bridge.py build`、未改 `native/`、未改版本、未合 main、未 push、未发布**。工作期间 T05 并行窗口提交 `f4adc99`（吸收 `src/creo_mechdog/schema.py`、`server.py`、`native/advanced.cpp`、`tests/unit/test_sheetmetal_box_live.py` 等）；派发时曾标注为 T02 的 `schema.py` +14 行实为 T05 `end_trim_mm` 契约（`SheetmetalFlangeOp` 可选正数字段 + 拒布尔校验，与 `server.py`/`advanced.cpp` 端到端一致，缺省不改旧行为，必要且保守），本窗口未回退、未触碰，已随 `f4adc99` 入库，归属见 [T05 卡](DEV051-T05-ACCEPTANCE.md)。本节改动仅 `tools/test_arc_direction_live.py` 与新增 `tests/unit/test_arc_direction_live.py`。

### 两个判定缺陷：修复前后对比

| 缺陷 | 修复前（`641edb3` 版驱动） | 修复后（本节） |
| --- | --- | --- |
| ①「只看体积就算 passed」 | `passed = measured is not None and abs(measured-expected) ≤ 0.01`；不查原生回显、不查重载证据。2026-10-29 四例实机报告 `saved_file_reloaded_and_verified=null` 仍全部 passed | `judge_create_case`/`judge_direction_edit`/`judge_save_reload` 要求：job succeeded ∧ 实测体积对上独立 oracle ∧ `arc_geometry` 原生回显（`source="native"` 且 dir/扫角一致）∧ `result.saved_file_reloaded_and_verified is True`；缺任一项记 `failures` 且 `passed=false`。回归：`test_missing_native_arc_echo_cannot_pass`、`test_missing_reload_evidence_cannot_pass`、`test_volume_only_evidence_cannot_pass` |
| ②「从 terminal 顶层取重载标志」 | `terminal.get("saved_file_reloaded_and_verified")`——该字段实际只在 `result` 块（`generic_bridge.py` 对成功非只读作业强制校验该字段；`creo_get_job` 全量返回 `result.*`），顶层永远取不到 → 永远 null，无法区分「没保存验证」与「读错位置」 | `reload_flag()` 只读 `result.saved_file_reloaded_and_verified`；顶层同名字段不算证据。回归：`test_top_level_reload_flag_is_not_evidence`、`test_save_reload_ignores_top_level_flag` |

### 本次覆盖（任务②）与判定口径

- **弧方向编辑**：`EDIT_CASES` 三例经 `creo_update_sketch_geometry` 就地切换 dir——`edit_switch_dir_0_to_90`（0→90，1→−1）、`edit_switch_dir_cross_zero`（350→10 跨零）、`edit_switch_dir_tilted_xz`（XZ 倾斜帧）。
- **下游特征跟随**：`judge_direction_edit` 要求体积变为 to_dir oracle 且不再等于 from_dir（`geometry_did_not_change` 即失败），revision 恰好 +1，`preserved_feature_id` 与 `body` 别名 feature_id 保持（矛盾即 `sketch_identity_changed`/`downstream_identity_changed`；数据缺失只记录不判）。
- **非法编辑报错且不破坏模型**：`ILLEGAL_EDIT_CASES` 五例——`illegal_dir_zero`、`illegal_dir_float`、`illegal_zero_sweep`、`illegal_full_circle`（schema 拒绝）与 `illegal_open_profile`（schema 合法、原生失败走回滚）。`judge_illegal_edit` 要求 rejected、前后**同源实测**体积不变（基线取 stage 3 保存后实测，不再用 oracle 冒充基线）、revision 不变（本窗口新增显式判定 `revision_evidence_missing`/`revision_changed_after_illegal_edit`），原生失败终端须有 `rollback_succeeded`/`model_unchanged` 证据（沉默不算证据）。stage 5 随后合法回切 dir + 保存重载，证明模型未卡死。
- **保存重载后方向与几何仍正确**：创建/编辑/恢复各阶段后显式 `creo_save_model`，以保存作业 `result.saved_file_reloaded_and_verified=true` 加重载后实测体积判定（弓形体积 142.7/1428.1 mm³（及跨零 1.76/1569.0）相差数量级，方向可判别）。
- **旧四例不动**：`legacy_0_to_90`、`legacy_90_to_0`、`dir_minus1_90_to_0`、`dir_minus1_0_to_90` 的角度、dir、容差 0.01 mm³ 与 2026-10-29 接受值一致；单测 `test_four_geometry_cases_are_not_loosened`、`test_oracle_volumes_keep_the_2026_10_29_values` 钉死，未放宽。

### 改动文件与每处意图

| 文件 | 意图 |
| --- | --- |
| `tools/test_arc_direction_live.py`（接手半成品续做，对 `641edb3` 为 +684/−65） | 判定拆成纯函数（`result_block`/`reload_flag`/`arc_echoes`/`native_arc_echo`/`echo_failures`/`edit_identity`/`judge_create_case`/`judge_direction_edit`/`judge_illegal_edit`/`judge_save_reload`）；唯一 run 目录 + 拒绝覆盖报告 + 逐阶段落盘 + `local_provenance`；五阶段 live 矩阵（创建含 XZ、编辑、非法、恢复、各阶段保存重载）；offline 输出创建/编辑/非法 oracle 台账 |
| 同上，本窗口在半成品之上补的四处 | ①`judge_illegal_edit` 增 revision 稳定性判定与行内记录；②非法编辑基线体积改用 stage 3 保存后同源实测值（实测对实测证明“未破坏”）；③`EDIT_CASES` 增倾斜 XZ 编辑例并在创建/台账透传 plane；④删除半成品遗留的未用参数 `submit_job(allow_failure)` |
| `tests/unit/test_arc_direction_live.py`（新增） | 判定回归 27 用例：两个具名缺陷回归、顶层标志不算证据、体积单独不可过、完整证据正例、方向编辑（几何变化/revision/回显/identity）、非法编辑（接受/变几何/变 revision/缺 revision 证据/缺回滚）、保存重载、旧四例钉死、报告目录拒绝覆盖 |

### 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.\.venv\Scripts\python.exe -m unittest tests.unit.test_arc_direction tests.unit.test_arc_direction_live tests.unit.test_sketch_stability tests.unit.test_sketch_geometry_edit tests.unit.test_profile_checks tests.unit.test_t02_operation_results tests.unit.test_sheetmetal_flange tests.unit.test_sheetmetal_contract` | exit 0，Ran 145，OK |
| 2 | 同上两模块首跑（写测试时） | 一处 FAIL：`test_volume_only_evidence_cannot_pass` 报 `AssertionError: 'reload_verification_missing' not found in ['native_arc_echo_missing']`——**测试夹具缺陷**（`terminal()` 默认带 reload=true，未表达“仅有体积”），修正夹具为 `reload_value=MISSING` 后全过；判定逻辑本身未动 |
| 3 | `.\.venv\Scripts\python.exe tools\test_arc_direction_live.py` | exit 0；输出 offline oracle：5 创建行（含 XZ）、3 编辑行、5 非法用例名；`LIVE NOT RUN: no MCP client, no Toolkit call, no Creo connection.` |
| 4 | `.\.venv\Scripts\python.exe -m ruff check tools\test_arc_direction_live.py tests\unit\test_arc_direction_live.py src\creo_mechdog\schema.py` 与 `ruff format --check` 同路径 | check 通过；format 首轮两文件需重排（半成品遗留格式 + 新增），`ruff format` 后复检通过；`schema.py` 本窗口未改动（已随 `f4adc99` 入库） |

### 未测范围

- 全部实机行为未验：本节零 MCP/Toolkit/Creo 调用。真实 `arc_geometry` 原生回显、方向编辑后下游再生体积、revision 递增语义、保存重载、非法编辑的原生拒绝/回滚字段形态、恢复编辑、busy/单通道（须真实并行调用才可报告）均未观察，不能以离线 oracle 或单测代替。
- `creo_update_sketch_geometry` 弧编辑在服务端标注 experimental；XZ 倾斜帧上的弧编辑、开口 profile 原生失败是否恰带 `rollback_succeeded`/`model_unchanged` 未实测。
- WorkBuddy 黑盒验收、Creo 9/10、`populate_profile` 嵌套 profile 回显、T09B 中心线计数均不在本节。
- 未改任何生产代码与 `native/generic.cpp`（按约束未动、未编译）；若实机发现原生缺回显/回滚字段，再按条目登记生产修复，不得先放宽判定。

### 实机待验步骤（另行指派；须先满足 BUG-001 会话可操作条件）

1. 前置：按 AGENTS.md 与 BUG-001 条件确认会话可操作；`config.json` 保持 `auto_start_creo=false`；只经 `MCP_CREO_MechDog_dev` 串行执行；不启动/结束 Creo、不清 unknown、不故障注入。
2. `.\.venv\Scripts\python.exe tools\test_arc_direction_live.py --live --confirm-session-usable`（落盘 `build\arc_direction_live\<run_id>\report.json` + `report.sha256`，唯一目录、拒绝覆盖；任何失败行立即 raise 并保留已落盘证据，不重提作业）。
3. 预期：5 创建例逐例 create→inspect→save→inspect 全 passed；3 编辑例 create→update→save 全 passed（体积按 to_dir oracle、revision +1、identity 保持）；5 非法例 rejected 且体积/revision 不变（原生失败例须见回滚证据）；恢复编辑 + 保存重载 passed。
4. 核对报告：`arc_echo.source="native"`、`result` 块 `saved_file_reloaded_and_verified=true`（不是顶层）、`identity`、`rollback`、`revision_before/after`、provenance（commit/branch/dirty/source_fingerprint）。
5. 证据回填本卡实机节；FEAT-034 首页与工具描述的 `dir`/`arc_geometry` 说明归 T01 收口。
