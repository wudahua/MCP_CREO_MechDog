# BUG-085 离线证据调查：0.6.1 断连 / 2026-10-29 挂起 两套时间线与证据对照

日期：2026-10-30（Asia/Shanghai）。任务：DEV-051 横切「BUG-085 离线调查」（见 [DEV051-CONTINUATION-TASKS-2026-10-30](DEV051-CONTINUATION-TASKS-2026-10-30.md) 横切表、[当前完善计划](../superpowers/plans/2026-10-30-feedback-072-to-085.md) Task 1 调查部分）。主卡：[BUG-085](../work-items/BUG-085.md)。前序核对：[DEV049-T01-ACCEPTANCE](DEV049-T01-ACCEPTANCE.md)（0.6.1 断连离线核对，2026-10-27）。

**结论先行：根因未定。** 0.6.1 断连（2026-10-26）与 2026-10-29 挂起是否同一根因，结论为**证据不足**——两起事故结束态都出现 `not_found_or_unreadable` / `toolkit_code=-4` / `worker_exit_code=20`，但该映射被证实是"连接不可用"的通用出口（见 §5 判据 3），无鉴别力；两起事故的失败位置、Creo 进程状态、请求是否到达 Creo 均不同或不可比。**不把同码当同根，不编造统一故事。**

本次调查为纯离线静态取证：未创建 MCP 客户端、未调用任何工具、未连接 Toolkit/Creo、未启动/结束 Creo、未清 unknown 保护、未故障注入、未重提任何作业；未执行任何修改 git index 的命令（无 add/commit/stash/切分支）；只新增本文件并在 BUG-085 卡追加一条记录，未改动 `docs/validation/` 历史原件、`docs/BACKLOG.md`、`README`、`docs/DEVELOPMENT.md`。

## 1. 事故口径

| | 事故 A：0.6.1 断连 | 事故 B：10-29 挂起 |
| --- | --- | --- |
| 时间 | 2026-10-26 04:30:48Z 起（12:30:48 起，Asia/Shanghai） | 2026-10-29 08:54:04Z 起（16:54:04 起） |
| 环境 | 本项目作者 Creo 12.4.0.0 验收环境，0.6.1 发布验收 FEAT-030 九种子矩阵 | 同一环境，DEV-051 T11 第三轮实机（FEAT-014 四壁/释放） |
| 现象 | 矩阵重跑时连接/启动阶段断连：`building_worker` 悬挂 4 分 37 秒后探测 `-4`/exit 20，两次 coordinator 重试超时（文档口径） | 第三道折边作业在 `ProFeatureWithoptionsCreate` 内挂起 >420 s；约 2 小时 50 分后 xtop 被 Windows 判定 AppHang 并关闭，Creo 进程消失 |
| 原始记录 | [RELEASE-0.6.1](../validation/RELEASE-0.6.1.md)、[RELEASE_NOTES_0.6.1](../RELEASE_NOTES_0.6.1.md)、[FEAT-030](../work-items/FEAT-030.md) 2026-10-26 节、[DEV049-T01](DEV049-T01-ACCEPTANCE.md) | [DEV051-T11](DEV051-T11-ACCEPTANCE.md) §3.5/§3.8/§4.1、`jobs/bb5543fb…/`、`build/sheetmetal_relief/20261029T165319_74073f09/report.json`、[BUG-001-recovery 2026-10-29 追加](../validation/BUG-001-recovery-2026-10-17.md) |

历史约束（[BUG-001-recovery-2026-10-17](../validation/BUG-001-recovery-2026-10-17.md)）：2026-10-17 BUG-001 关闭时实机卡死根因未定，此后停止新的 Toolkit 连接与故障注入；本调查遵守该约束，只读不连。

## 2. 事故 A 时间线：0.6.1 断连（2026-10-26，UTC / Asia/Shanghai=UTC+8）

来源缩写：`startup.log` = `%LOCALAPPDATA%\MCP_CREO_MechDog\startup\6235eee86323f49c8d99f96a\startup.log`（本次核对共 5097 行，行号为本次读取行号）；`loft.json` = `build/installation_loft_validation.json`（第三轮空汇总，mtime 2026-10-26 12:38:24 本地，448 863 B）；`trail.67` = `build/creo_session/trail.txt.67`（mtime 2026-10-26 13:48:20 本地，356 603 B）。

| UTC | 本地 | 事件 | 来源（文件+行/字段） |
| --- | --- | --- | --- |
| 00:07:11.125 | 08:07:11 | 会话创建：`parametric.exe` PID 20180（00:07:11.125 796Z）、`xtop.exe` PID 20164（00:07:11.802 922Z） | `loft.json:267-269, 283-285`（快照 observed_at 04:38:23.209 686Z） |
| 04:11 | 12:11 | 编辑专项 16/16 通过（断连前最后一轮完整作业） | `docs/validation/RELEASE-0.6.1.md`"修复批实机证据的复用与边界" |
| 04:23:54–04:28:01 | 12:23:54–12:28:01 | 种子 smoke + 第一轮 6 作业全部 succeeded（`b4bd95ca`/`cda3ba3f`/`49268b14`/`7c283eaf`/`7f72eba7`/`cf41d9f9`） | 各 `jobs/<id>/job.json`（明细见 DEV049-T01 §3） |
| 04:29:50.658–04:29:56.232 | 12:29:50–12:29:56 | 协调器周期：checking → waiting_for_channel → building_worker → **ready connected=True** | `startup.log:4342-4345` |
| 04:29:56.99–04:30:44.69 | 12:29:57–12:30:45 | 第二轮四作业成功：`471d5301…`（five 创建）、`633de212…`（five 编辑）、`6c8ed77b…`（four 创建）、`14560f1b…`（four datum"编辑"，体积不变），均 `toolkit_code=0`、`saved_file_reloaded_and_verified=true` | `jobs/<id>/job.json`、`native.log`（DEV049-T01 §2） |
| 04:30:42 | 12:30:42 | trail 最后一次 `connected to Pro/E`（对应 `14560f1b`） | `trail.67:5801-5807`（DEV049-T01 §3 引用） |
| 04:30:48.282–48.392 | 12:30:48 | 协调器 checking → waiting_for_channel → **building_worker**；此后 4 分 37 秒无任何状态发布（下一条日志已是 04:35:25.113） | `startup.log:4346-4348`（4348 与 4349 之间的空窗） |
| 04:35:25.113–31.597 | 12:35:25–12:35:32 | 新周期 → **ready connected=True**（事故窗口内唯一一次连接成功）；`trail.67` 无对应 IPC 初始化记录 | `startup.log:4349-4352`；`trail.67`（对照） |
| 04:36:23.926–29.472 | 12:36:24–12:36:29 | checking → building_worker（5.53 s）→ waiting_for_connection；**首个显式失败**：`connected=false`、`connection_state=not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`、`release_numeric=0`、`selected_session_configured=false` | `startup.log:4353-4356`；`loft.json:242-260`（startup_queries 该条） |
| 04:36:29 | 12:36:29 | 提交 `f54cda8`（`native/sketch_edit.cpp`、`server.py`、`tools/test_editing_closeout.py` 等） | `git show --stat f54cda8`（DEV049-T01 §3 引用） |
| 04:36:29–04:38:23 | 12:36–12:38 | waiting_for_connection 每 ~5.4 s 轮询 | `startup.log:4356-4377` |
| 04:38:23.209 | 12:38:23 | 快照：`parametric` `hidden_only`、3 窗口 0 可见、**`hung_window_observed=true`**；`xtop` 18 窗口 1 可见、`hung_window_observed=false`；`coordinator_pid=10004`、`launch_attempt=46` | `loft.json:261-299`、`loft.json:20-31` |
| 04:38:24 | 12:38:24 | 第三轮写出**空汇总**：`success=false`、`cases={}`、`jobs=[]`、`version=0.6.0` | `loft.json:2-5`；文件 mtime（本次核对） |
| 04:38:25–04:40:29 | 12:38–12:40 | 再一周期 → `timeout`（"Startup total budget expired"） | `startup.log:4378-4404` |
| 04:43:17.99– | 12:43–12:45 | 再一周期 → `timeout` | `startup.log:4405` 起（DEV049-T01 §3 记载至 04:45:20） |
| 05:48:13 | 13:48:13 | **人工退出 Creo**（`ProCmdWinCloseGroup`→`ProCmdOSExit`，确认"未保存的工作将丢失"）；trail 结束 | `trail.67` 尾部；文件 mtime 13:48:20（本次核对） |
| 06:04:36 | 14:04:36 | 0.6.1 合并提交 `2af3853` | `git log`（DEV049-T01 §3 引用） |

读法（沿用并复核 DEV049-T01 §3）：**首次异常停止点是 04:30:48 的 `building_worker` 悬挂**，不是 04:36:29 的 `-4`；断连发生在**作业之外**（连接/启动阶段），四个 job 全部在断连前成功收尾。文档"两次 coordinator 重试超时"与日志 5 个协调器周期的口径差异见 §6 矛盾点②。

## 3. 事故 B 时间线：2026-10-29 挂起（UTC / Asia/Shanghai=UTC+8）

来源缩写：`report.1653` = `build/sheetmetal_relief/20261029T165319_74073f09/report.json`（T11 卡记 SHA256 `D80E018E…`）；`T11` = `docs/development/DEV051-T11-ACCEPTANCE.md`。

| UTC | 本地 | 事件 | 来源（文件+行/字段） |
| --- | --- | --- | --- |
| 08:53:22 | 16:53:22 | 第三轮驱动启动（run_id `20261029T165319_74073f09`，`mode=live`） | `report.1653:4-6`（`started_at` 1793264002.302 830 7，本次换算） |
| 08:53:28 | 16:53:28 | 会话确认 `ready/connected=true`、`toolkit_code=0`、`release_numeric=44`、`coordinator_pid=21836`、`launch_attempt=48`；session identity `2194098641453425411`（`sessions_observed=2`、`changed=true`）、`session_health=no_failure_observed` | `report.1653` `creo.startup` 段 |
| 08:53:33 | 16:53:33 | job `579dc118…` 底板 succeeded（42 920 mm³，rev 1） | `jobs/579dc118…/job.json`（本次核对 `status=succeeded`）；`T11:294` |
| 08:53:43 | 16:53:43 | job `07b5ec25…` `f_px`（边 105）succeeded（61 480 mm³，rev 2） | `jobs/07b5ec25…/job.json`；`T11:295` |
| 08:53:54 | 16:53:54 | job `b57c115d…` `f_nx`（边 104）succeeded（80 040 mm³，rev 3） | `jobs/b57c115d…/job.json`；`T11:296` |
| 08:54:04.627 | 16:54:04 | job `bb5543fb…` `f_ny`（边 103，height 80、angle 90、radius 2.54、y_factor 0.5）创建；`started_at` 08:54:05.002Z，runner pid 21140 | `jobs/bb5543fb…/job.json`（本次核对） |
| — | — | **挂起点**：`native.log` 停在 `ProFeatureWithoptionsCreate` 之前的最后一次 `ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), …)`；`worker.log`/`runner.log` 为空 | `jobs/bb5543fb…/native.log` 尾部（本次核对）；`T11:297` |
| 08:54:05–09:01:05 | 16:54:05–17:01:05 | 驱动每秒 `creo_get_job` 轮询，全部 `status=running`，持续 420 s 后 `LiveStop`："Job bb5543fb… still running after 420s; do not resubmit" | `report.1653:4737`（`stopped`）、`report.1653:4744`（`finished_at` 1793264465.053 223，本次换算 09:01:05Z）；轮询 calls 末段 `at` 1793264355–1793264465 |
| — | 17:01 后 | `toolkit.lock` 仍被该作业持有，本轮后续实机全部无法执行 | `T11:301` |
| — | 17:01–19:51 | **~2 小时 50 分无任何记录** | 无原件（§7 缺证 B-3） |
| — | 19:51:03 | Windows Application 日志：WER 1001 `AppHangB1`（`P1: xtop.exe`、`P2: 40.0.2025.111`）；Application Hang 1002"程序 xtop.exe 版本 40.0.2025.111 停止与 Windows 交互并已关闭" | `T11:338-339`（转述事件日志；**无 evtx 原件导出**，§7 缺证 B-5） |
| — | 19:53 / 20:06 | `tasklist` 两次确认 `parametric.exe`/`xtop.exe` 均无运行任务；**只剩 `nmsd`（pid 6504）** | `T11:340` |
| — | 20:04 | `creo_startup_status`：`state=timeout`、`connected=false`、`auto_start_enabled=false`、`launch_attempt=48`、`launch_reserved=false` | `T11:341` |
| — | 20:04 | `creo_session_status` 9 秒只读探测：`connected=false`、`not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`、`creo_process_snapshot.processes=[]`（`uncertain=false`） | `T11:342` |
| — | 20:04 后 | `bb5543fb` 随会话消失，永远读不到终态；`job.json` 至今仍 `status=running`、`stage=executing_feature_plan` | `T11:344`；`jobs/bb5543fb…/job.json`（本次核对） |
| 14:05:41 | 22:05:41 | 协调器拉起新 Creo（PID 15156）→ `ready/connected=true`；`trail.txt.69` 创建于 22:05:48、**0 字节**（本次核对 `build/creo_session` 目录） | `T11:424`；`build/creo_session/trail.txt.69`（mtime/大小，本次核对） |
| 14:06– | 22:06– | 后续两轮（`build/flange_side_probe/`、rebuild）全部 job 180 s 内到达终态、无挂起 | `T11:428-439, 471` |
| 22:49:14 | (10-30) 06:49:14 | `build/toolkit_health.json` 最后一次探测（事故后）：`not_found_or_unreadable`、`-4`、`worker_exit_code=20` | 现文件 `checked_at=2026-10-29T22:49:14.633 281+00:00`（本次读取；发起方未记录，§7 缺证 B-8） |

读法：事故 B 的异常起点是 **16:54 的原生调用内挂起**（不是连接失败）；`-4`/exit 20 出现在 **19:51 会话消失之后**的探测上，且当时 `processes=[]`（根本没有 Creo 进程）。把 20:04 的 `-4`/exit 20 当作"与 0.6.1 相同的断连"是误读（§5 判据 3）。

## 4. 技术证据表

强度标注：**硬** = 仓库内原件可直接复核；**转述** = 历史文档记载、原件不在仓库；**缺** = 无证据；**推测** = 未证实假设。

| 证据项 | 事故 A（10-26） | 强度 | 事故 B（10-29） | 强度 |
| --- | --- | --- | --- | --- |
| worker/服务版本 | 服务元数据 `version=0.6.0`（`loft.json:2`、`loft.json:308` update.current_version） | 硬 | 服务 `current_version=0.8.3`（`report.1653` update 段） | 硬 |
| 源码提交锚点 | 事故时 HEAD ≈ `83bd7b6`（10-26 11:48）；事故后 6 分钟提交 `f54cda8`（12:36:29）；**事故时源码 dirty、未采 `source.sha256`** | 硬（锚点）/缺（指纹） | 分支 `codex/dev051-feedback070`；T11 §4 起点 HEAD `e5fe021`，§5 起点 `cce1922` | 硬（转述自 T11 卡） |
| 构建时间/`source.sha256` | **缺**：现 `build/source.sha256`、`build/creo_worker.exe` 均为 2026-10-27 08:17Z 重建值，不代表事故时二进制（DEV049-T01 §1） | 缺 | 本轮 `bridge.py build` 6 次；**运行时执行器为 16:53 构建**（`T11:324`）；最终 `source.sha256=541a9657…`（`T11:325`）为格式化后值，报告本身**不记录源码指纹**（本次核对 `report.1653` 无该字段） | 半硬（叙述）/缺（逐位指纹） |
| worker 二进制哈希 | RELEASE-0.6.1 回顾记"留存 worker SHA256 `631c5314…`"与 native 快照 `320cedaa…`；**是否为 04:36 断连时刻的二进制无法确认**（可能为事故后重建） | 转述/存疑 | 未留存运行时 worker 哈希 | 缺 |
| 进程生命周期 | `parametric` 20180 / `xtop` 20164 自 00:07:11Z 持续存活至 04:38+ 快照；`parametric` hidden_only + **hung**；05:48:13Z 人工退出 | 硬 | 16:54 挂起在 `ProFeatureWithoptionsCreate` 内；19:51:03 xtop `AppHangB1` 被 Windows 关闭；19:53/20:06 两进程均不存在；22:05:41 新 PID 15156 | 硬（快照/日志）+转述（事件日志） |
| nmsd 状态 | **缺**：无 PID/创建时间/父进程原件，跨批次判断不可做 | 缺 | 19:53/20:06 **只剩 `nmsd`（pid 6504）**（进程残留）；创建时间/父进程**未记录**，是否跨批次不可知 | 半硬（存在性）/缺（身份） |
| IPC/通道错误码 | `not_found_or_unreadable`、`-4`、`exit 20`（04:36:29.472Z，`loft.json:248-260`）；另 04:35:31 ready=True 与 trail 无 IPC 记录并存 | 硬 | 挂起本身**无错误码**（调用未返回）；20:04 探测 `-4`/`exit 20` 且 `processes=[]`；`job.json` 无 worker exit 字段 | 硬 |
| 任务终态登记 | 4 job 全部 `succeeded`/`toolkit_code=0`/重载 true；断连在作业之外；第三轮 `cases={}` `jobs=[]`（空汇总≠通过） | 硬 | `579dc118`/`07b5ec25`/`b57c115d` 三 job `succeeded`（本次核对）；`bb5543fb` **永久 `running`**（会话消失，终态不可达） | 硬 |
| 锁状态 | 未记录（断连在启动/连接阶段，非作业内） | 缺 | `toolkit.lock` 被挂起作业持有，后续实机全阻塞（`T11:301`）；`native_owner.json`：pid 20408、session_fingerprint `2194098641453425411` | 硬 |
| 会话身份 | `selected_session_configured=false`（`loft.json:238`），会话核对分支未触发 | 硬 | identity `2194098641453425411`（`report.1653`；与 `native_owner.json` 一致）；当天 `sessions_observed=2`、`changed=true` | 硬 |
| GUI 观测 | FEAT-030 文字"隐藏的『重新生成进度』框残留、无可见模态框"，与快照 `hidden_only`+hung 相合；**无截图** | 转述 | 挂起时 GUI 状态未观测；19:51 由 WER 判定挂起并关闭 | 转述 |
| trail 证据 | `trail.67:5801-5807` 最后 IPC 04:30:42Z；04:35:31 ready 无对应 IPC（矛盾） | 硬 | **10-29 挂起会话无任何 trail 文件**（`trail.68` 为 10-26 18:49，`trail.69` 为 22:05:48 创建、0 B，本次核对目录） | 硬（缺失本身） |
| 运行期二进制变更 | 事故窗口内 `native/sketch_edit.cpp` 被改（`f54cda8` 04:36:29Z 提交），`building_worker` 可能重建并替换 `creo_worker.exe` | 硬（提交）/推测（重建冲突） | 16:53 本轮构建早于作业；无运行期重建记录 | 硬 |

## 5. 同根判断（三选一：证据不足）

对照旧案 [BUG-056](../work-items/BUG-056.md)（2026-10-17 通道静默失效，用户确认关闭；根因链=跨批次遗留 nmsd + trail 证明请求未到达 Creo + 快速 `-4`）与两起事故：

| 维度 | BUG-056（10-17） | 事故 A（10-26） | 事故 B（10-29） |
| --- | --- | --- | --- |
| 错误映射 | `-4`/exit 20/not_found_or_unreadable | 相同 | 相同（仅出现在会话消失后的探测） |
| 失败位置 | 作业内被 `-4` 打断（`unknown_outcome`） | **作业之外**（连接/启动阶段） | **作业内挂起**（`ProFeatureWithoptionsCreate` 不返回） |
| Creo 进程 | 存活 | 存活（`parametric` hidden+hung） | **死亡**（`processes=[]`） |
| 请求是否到达 Creo | trail 证明未到达 | **矛盾**（ready=True 但 trail 无 IPC） | **到达**（native.log 元素树已建） |
| 跨批次 nmsd | 已证 | 缺证 | 缺证（nmsd 残留 pid 6504，身份未知） |
| 失败节奏 | 固定 37–41 s 周期性静默 | building_worker 悬挂 4m37s + 快速 `-4` | 单次调用无限挂起 → ~2h50m 后 AppHang |

判据：

1. `exit 20` 是探测失败分支的固定返回码（`native/worker.cpp` `return result ? 20 : 0`，BUG-056.md:16），**不是**worker 崩溃或"进程级退出"的证据；R1/BUG-085 早期"worker 进程级退出"表述不成立为区分或归并依据（DEV049-T01 §5 已纠正，本次复核同意）。
2. 三案错误映射相同只落在"映射层"；BUG-056 根因链的三条中，事故 A 仅"快速 `-4`"成立（另两条缺/矛盾），事故 B 三条全不适用（其 `-4` 是会话消失的结果而非原因）。
3. **关键证据（本次新增）**：事故 B 在 20:04 与事故后 06:49（10-30）两次探测都返回同一组 `-4`/exit 20 映射，而前者 `processes=[]`（无 Creo 进程）——证明该映射是"无可连接端点"的**通用出口**，本身无根因鉴别力。把"同码"当"同根"的推理不成立。
4. 事故 A 独有变量（parametric 隐藏且 hung、运行期 native 改动/可能的 worker 重建）与事故 B 独有变量（原生调用内挂起、会话随后被 WER 关闭）没有交集证据。
5. 事故 B 与 0.7.0 时代"第三道 `-1`"（`ProFeatureWithoptionsCreate=-1`）为同一调用的不同失败形态（`-1`→挂起），这是"第三道折边调用不稳定"的线索，**不能**上推为与事故 A 断连同根。

**结论：证据不足，两案不能归并；BUG-085 保持根因未定。不重开 BUG-056，不清任何保护。**

## 6. 相互矛盾点清单

1. **（事故 A）04:35:31.598Z `ready connected=True` vs `trail.67` 自 04:30:42Z 后无任何 IPC 初始化记录。** 两种解释都排除不了：(a) 2 秒探测的连接/断开不在 trail 留痕；(b) 该次 ready 指向了另一会话端点。因此"trail 无记录=请求未到达 Creo"在本案不成立（DEV049-T01 §3 记载，本次复核同意）。
2. **（事故 A）"coordinator 两次显式 retry 超时"（RELEASE-0.6.1/RELEASE_NOTES_0.6.1/FEAT-030:75 口径）vs `startup.log` 窗口内 5 个协调器周期**（04:30:48 静默、04:35:25 成功、04:36:23 失败、04:38:25 timeout、04:43:17 timeout）。日志无 `retry` 标志，"两次"无法逐次对应；口径差异保留，不改写任一文档。
3. **（术语）"worker 进程级退出"（R1 反馈/BUG-085 早期描述）vs exit 20 的真实语义**（探测失败分支返回码）。T01 已纠正；本调查确认纠正有效，不再以"进程级退出 vs 通道静默"作为两案区分依据。
4. **（事故 B）20:04 探测的 `-4`/exit 20 易被读作"0.6.1 同款断连"，但 `processes=[]` 证明当时没有 Creo 进程**——该记录是"会话消失的结果"，不是独立断连事件。与 16:54 的挂起点必须分开评价。
5. **（事故 B）`report.1653` 的 `session_health=no_failure_observed / recent_verified_save`（16:53:28）与 22 秒后即发生的挂起**：健康快照只反映已记录历史，不能预测下一调用；不构成数据错误，但任何"当时健康=当时无隐患"的推论无效。
6. **（事故 B）`job.json` 至今 `status=running`** 与"会话已消失、作业永不终态"并存：登记层与事实层不一致，属既定保护行为（不重提、不伪造终态），不是新缺陷，但读台账时不能把 `running` 当作仍在执行。

## 7. 缺证清单

### 事故 A（0.6.1 断连）——沿用 DEV049-T01 §8 九项，本次复核后逐项确认仍缺

1. 事故时点 `build/toolkit_health.json`（已被 10-27 之后的探测覆盖；现文件 checked_at 2026-10-29T22:49:14Z，属事故后）。
2. `nmsd.exe`/`pro_comm_msg.exe` 的 PID/创建时间/父进程——跨批次判断不可做。
3. 前两轮矩阵 summary（固定输出路径 `build/installation_loft_validation.json` 被第三轮空汇总覆盖；现文件即空汇总）。
4. 三轮驱动 stdout/stderr 与异常栈（未归档）。
5. 事故时点源码指纹（dirty；`source.sha256`/worker 均为 10-27 重建值，只能用 `83bd7b6`/`f54cda8` 夹逼）。
6. `retry=true` 调用记录与次数（文档"两次"无法逐次对应）。
7. 断连时 GUI/再生进度框截图或窗口枚举原件。
8. 事故会话 `std.err`/`std.out`（`build/creo_session` 仅有 10-26 18:49 的后续会话 `std.out`）。
9. 作业路径的 worker 退出码字段（`job.json` 不记录）。

### 事故 B（10-29 挂起）

1. `bb5543fb` 作业终态/失败阶段/`ProFeatureWithoptionsCreate` 返回值——永远缺失（会话消失）。
2. 挂起原因（Creo 模态框？死锁？再生阻塞？）——未观测；T11 §3.7-2 建议的"确认是否弹对话框"未执行。
3. 17:01→19:51 约 2 小时 50 分的现场（窗口状态、trail、std.err、用户操作）——无任何记录。
4. 10-29 挂起会话的 **trail 文件**——不存在（`trail.68` 与 `trail.69` 之间无条目；`trail.69` 为 22:05 新会话且 0 B）。
5. WER `AppHangB1` 原始事件（evtx 导出/挂起栈）——仓库内只有 T11 §4.1 的转述行。
6. `nmsd`（pid 6504）创建时间/父进程/所属批次——只有 pid，跨批次不可判。
7. 运行时 worker 二进制指纹（16:53 构建的逐位哈希未留存；`report.1653` 无源码指纹字段）。
8. 事故后 `build/toolkit_health.json`（checked_at 2026-10-29T22:49:14Z）的发起方与背景——未记录；只能作为"映射无鉴别力"的旁证。

### 两案共通缺证

- 两案的 `pro_comm_msg` 进程关系、Creo 侧 `std.err`、名字服务批次身份——均无原件；同根判断所依赖的"连接层级/请求路径"证据链因此无法闭合。

## 8. 证据强度结论

**能站住的（硬证据，可复查原件）：**

- 四 + 三 + 一 = 八个作业的终态、连接码、保存重载标志与 native.log 内容（jobs/ 目录原件）。
- 事故 A 的协调器状态机序列与空窗（startup.log 行号）、`-4`/exit 20 探测条目（loft.json:242-260）、进程快照（loft.json:261-299）、空汇总（loft.json:2-5）。
- 事故 A 断连在作业之外、trail 最后 IPC 于 04:30:42Z。
- 事故 B 挂起点在 `ProFeatureWithoptionsCreate` 之前（native.log 尾部）、420 s 轮询与 LiveStop（report.1653:4737/4744）、三作业成功、`bb5543fb` 永久 running。
- 事故 B 会话消失后 `processes=[]` + `-4`/exit 20（T11 §4.1 转述 + 探测字段），及 `-4`/exit 20 作为"无端点"通用出口的旁证（toolkit_health.json 现文件）。
- `exit 20` = 探测失败分支固定返回码（native/worker.cpp 映射，BUG-056.md:16）。

**只是推测 / 不得当结论用的：**

- "0.6.1 断连与 10-29 挂起同根"——无交集证据，仅同码。
- "并发重建 worker 导致事故 A 悬挂"——候选机制（`f54cda8` 提交在窗口内），未验证。
- "跨批次 nmsd 导致事故 A 断连"——证据缺失，不能沿用 BUG-056 结论。
- "事故 B 挂起是 `ProFeatureWithoptionsCreate` 弹模态框/死锁"——未观测。
- "04:35:31 的 ready 指向另一会话"或"2 秒探测不留 trail"——矛盾点①的两种解释均未证实。
- RELEASE-0.6.1"留存 worker SHA256 `631c5314…`"=事故时二进制——时间归属存疑。

## 9. 下一步最小可验证步骤（需用户指派，不在本任务内执行）

1. **nmsd 身份采集（判跨批次）**：按 BUG-001 纪律人工确认会话可操作后，在**新会话**先做一次有界只读探测，同时采集 `creo_process_snapshot` 与 `nmsd`/`pro_comm_msg` 的 PID/创建时间/父进程；失败即停。直接回答事故 A/B 的 nmsd 缺证（A-2/B-6）。
2. **排除运行期重建假设（事故 A）**：验证"运行期重建 worker 与活动通道冲突"（只记录，不改生产代码）；如确认，最小修复范围为构建互斥/延后替换，另行登记。
3. **挂起点取证（事故 B）**：会话恢复后先确认第三道折边 `ProFeatureWithoptionsCreate` 是否弹出模态框（T11 §3.7-2）；拿根因前不重试该边、不重提 `bb5543fb`。
4. **归档补强（纯离线可做，属改进建议）**：未来实机开工即采 `nmsd` 进程身份 + `source.sha256` + 会话 `std.err/std.out`；驱动唯一输出目录（T06 已落实）杜绝 summary 覆盖。
5. 若需补 17:01–19:51 空窗：检索 Windows 事件日志该时段 xtop/WER 全部条目并导出 evtx——只能由人工在本机进行，现仓库内无材料。

## 10. 本次调查边界

未创建 MCP 客户端、未调用 `session_status`/任何工具、未连接 Toolkit/Creo、未启动/结束/重启 Creo、未清 unknown 或任何保护、未故障注入、未重提作业、未改生产代码、未改版本/台账/README/开发入口、未动 `docs/validation/` 原件、未执行任何 git 索引操作。本文件与 BUG-085 卡的追加条目是本次仅有的两处写入。离线调查完成不代表连接已恢复或根因已定。
