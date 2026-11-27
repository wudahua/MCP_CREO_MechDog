# FEAT-072 多 Creo 会话的可验证发现和显式选择

分类：**部分交付 0.35.6**（候选列表与进程内选定已随 0.35.6 交付并实机；真实 ID A→A 与 Creo 9/12 未排期）

类型：功能。优先级：P1。目标版本：0.35.6（选定与候选列表已交付）；余项未排期。

0.35.2 外部双会话 -36，现有配置选择依赖重启服务。Creo 10 `ProCore.h` 的 `ProProcessHandle` 是 Toolkit `PeerIdx`，不能把 PID 或 Windows 进程句柄当作连接 ID。先验证受支持的发现方式，披露已识别/不可识别候选，再设计进程内显式选择，保持失效 ID、当前活动作业和未知模型保护。双会话实测需要覆盖 A→A、无效 ID 无回落及退出换代；窗口、模型名只取实际观察。自动择机另作决策。关联 FEAT-019、BUG-139。

来源：[本批反馈计划](../archive/development/0.35.0-FEEDBACK-PLAN-2026-11-21.md)。

## 本轮实现（开发分支 `codex/bug-144-release-evidence-plan`，基线 `98c598f`）

- 发现：`creo_startup_status` 与 `creo_session_status` 新增 `session_candidates`。按进程披露 pid、镜像、创建时间、是否匹配配置安装路径、窗口状态；每条 `identified=false`、`session_id=null`，并给出原因（`ProProcessHandle` 是 `PeerIdx`，没有 PID→会话 ID 的换算依据）。窗口标题与模型名按既有只读边界不读取。
- 不把进程数冒充为会话数：`ambiguity.observed` 只描述“观察到多个进程”，`proven_by_toolkit` 固定 `null`；只有 `toolkit_code=-36` 才证明多会话。一次 Creo 本来就会显示 parametric.exe + xtop.exe 两个进程。
- 选定：`creo_startup_status(retry=true, session_id=...)` 在进程内固定目标（`src/creo_mechdog/session_choice.py`），作用于该服务随后启动的每个 worker 与启动探测；`clear_session_id=true` 回到 `config.json`。只存在进程内存，不写 `config.json`、不跨重启，`describe()` 只返回指纹不返回原始 ID。
- 只连接选定目标：`bridge.native_environment()` 的 `MECHDOG_CREO_SESSION_ID` 取运行时选择（覆盖配置文件）；原生侧仍在连接后用 `ProEngineerConnectIdGet` 比对，发现回落即断开。选中 ID 不可用时发布 `selection_required` 并标出 `source`，不启动替代 Creo、不连其他会话。
- 未新增公开工具（公开工具数仍为 110）：候选列表挂在两个状态工具上，无人值守客户端不必多调一次。
- 歧义提示语：`selection_required` 先说明候选列表与 PID 不是会话 ID，再给 `session_id=`（作用于运行中的服务、无需重启）、关闭其他会话后重试、`config.json` 加重启这三条路径，并保留“单独改 `config.json` 不影响运行中的服务”。`tests/unit/test_feedback_0193_contract.py` 的文案契约同步断言上述要素。
- 作业保护不变：当前活动作业仍由 Toolkit 单通道 busy 立即拒绝；会话选择不改 revision、pending 或未知结局保护。

## 验证

离线：`tests/unit/test_feat072_session_selection.py` 13 项，覆盖覆盖优先级、清空回落、控制字符/超长/非字符串拒绝、worker 环境变量、`start()` 必须同时 `retry=true`、`Settings.load()` 的生效选择、候选构建（多进程/不可用清单/无作业历史）、以及两个工具的 schema 契约。

实机（本机 Creo 10.0.0.0，第一次探测时 parametric.exe 9912 + xtop.exe 8020）：

| 步骤 | 结果 |
| --- | --- |
| 无选择探测 | `connected=true`、`connection_state=connected`、`toolkit_code=0` |
| 进程内选中错误 ID 后探测 | `connected=false`、`connection_state=not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`，未连到正在运行的会话（无回落） |
| 清除选择后探测 | `connected=true`、`toolkit_code=0` |
| 候选列表 | 2 个进程（9912 / 8020），均 `matches_configured_installation=true`，`window_state` 分别为 `hidden_only` / `visible`，均 `identified=false` |

双会话现场（2026-11-21 晚，在同一台机器上另起一个 Creo，共 4 个进程）：

| 步骤 | 结果 |
| --- | --- |
| 两次 `parametric.exe` 并存 | 探测返回 `connected=false`、`connection_state=ambiguous`、`toolkit_code=-36`，公开工具首次在真实现场给出歧义 |
| `creo_startup_status(retry=true)` | `state=selection_required`，`connected=false`；提示语即本节改写的文案（候选列表、PID 推不出 ID、`session_id=` 无需重启、关闭其他会话或 `config.json`+重启） |
| 候选列表 | 4 条：9912/29044 为 `parametric.exe`，8020/23372 为各自的 `xtop.exe`；`count=4`、`ambiguity.observed=multiple_processes`、`proven_by_toolkit=null` |
| 歧义下选中错误 ID | `connected=false`、`not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`，未偷偷连上其中任一会话 |
| 关闭多余会话后（未重启服务） | `connected=true`、`connection_state=connected`、`toolkit_code=0`，候选回落到 2 个进程 |

`toolkit_code=-4` 与 `not_found_or_unreadable` 是本项目既有 `ABSENT` 契约，即“该 worker 连不上任何会话”，而不是“连到了别的会话”。

全量（提交 `98c598f`、`dirty=true`、指纹 `71e17084…`）：4,330 项，0 失败、0 错误、6 跳过；`tools/dev_check.py --skip-unit` 的 Ruff 与格式化均为 0 发现。

## 未验证

- 用真实 session id 做 A→A 切换：本机 ID 只能从 Creo 的 Session Info 读取，未在自动化流程中取得；歧义现场与错误 ID 都已验证，缺的是“正确 ID 连上了预期会话”这一正向步骤。
- Object Toolkit `ConnectById`/未登记会话的发现方式；`created_at` 与真实会话的对应关系仍只按观察记录。
- Creo 9/12 运行时。

## 边界

未登记会话仍无法枚举 ID，因此保留 `selection_required`；ID 来源是 Creo Session Info 或此前可用的值。自动择机（按最近保存/身份匹配自动消歧）未实现，按原卡交后续决策。
