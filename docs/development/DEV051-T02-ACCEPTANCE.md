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
