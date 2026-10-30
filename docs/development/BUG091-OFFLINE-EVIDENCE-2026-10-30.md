# BUG-091 N02 离线调查：断连、挂起与重启后退出分现场记录

日期：2026-10-30（Asia/Shanghai）。基线：`7198588df953a63cd61b75f889943478c6f87772`，分支 `codex/dev051-feedback070`。执行前工作区已有其他窗口的未提交修改和运行文件，本次不触碰。调查只读既有文件，未新建 MCP 客户端、未调用 `session_status`、未连接 Toolkit、未启动/结束/重启 Creo、未清 unknown、未构建或运行测试。用户告知当前 Creo 未运行；这是**当前状态**，没有用于补写任何历史时点的进程事实。

**结论：根因未定。** 0.6.1 断连、10/29 折边作业内挂起、该会话消失、以及报告称重启后分钟级自退出，是不同的观察段。`-4` / exit 20 只在前一事故的连接探测和后一事故会话消失后的探测中出现，不能据此归并。10/17 BUG-001 的 `-97` / `-11` 与 AppHang 是另一个历史对照。BUG-001 保持按用户决定关闭，BUG-085 保持调查中且根因未定；BUG-056 也不重开。

## 来源与证据强度

- [BUG-085 离线证据](BUG085-OFFLINE-EVIDENCE-2026-10-30.md) §2—§7、[DEV049 T01](DEV049-T01-ACCEPTANCE.md) §2—§8：10/26 启动日志、矩阵报告、作业和进程快照的逐项核对。以下 0.6.1 时间线主要引用这两份核对；原始 `startup.log` 在本机用户目录，未复制到仓库。
- [DEV051 T11](DEV051-T11-ACCEPTANCE.md) §3.5/§3.8/§4.1/§6：10/29 作业、事件日志摘录、只读探测与后续新会话。`jobs/bb5543fb3c66404e95172876fa1ac9aa/job.json`、`native.log` 和 `build/sheetmetal_relief/20261029T165319_74073f09/report.json` 本次只读核对；后者 SHA256 为 `D80E018E582C37B8B72D42AB4AF810BD4E53ADB0FDEB8225F27C7F7107829505`，与 T11 一致。
- [BUG-001 recovery](../validation/BUG-001-recovery-2026-10-17.md) 与 [10/17 离线核对](../validation/BUG-001-hang-offline-2026-10-17.md) 及其 [结构化证据](../validation/bug-001-hang-offline-2026-10-17/evidence.json)：10/17 的独立历史现场；原恢复记录的 10/29 附记为转述，不是新的原始事件文件。
- [外部 0.8.5 反馈 R80x-4](../validation/feedback-0.8.x-2026-10-30/2026-10-30CREO10.0.0.0-0.8.5-Creo10编译阻断跨三版未修与会话卡死第三次复现无开放条目.md) §2 与 [N00 映射](../validation/feedback-0.8.x-2026-10-30/MAPPING.md) R80x-4：反馈报告者的静态转述，不是其 Creo 10 机器上的会话实测；归档原件 SHA256 `F8705DB7956A7D2BC9A94BFE049858A2398D9EF34B4C0F2788D652ABC0E3F70C`，本次核算与 [manifest](../validation/feedback-0.8.x-2026-10-30/manifest.json) 一致。原件中 `../work-items/` 相对链接按原样保留，正确工作卡路径在 `docs/work-items/`。

表内 UTC 均由有 UTC 原始字段或 Asia/Shanghai 时间减 8 小时得到；只有分钟精度的记载不补秒数。`—` 表示该时点缺少可追溯时间，不代表事件未发生。

## 现场 A：2026-10-26，0.6.1 验收断连

环境：项目作者本机 Creo 12.4.0.0；FEAT-030 种子矩阵。第三轮报告中的服务元数据写 `version=0.6.0`，与发布叙述的「0.6.1 验收」不是同一个字段，不能据发布名推断事故时 worker 的逐位身份。来源：[BUG-085 离线证据](BUG085-OFFLINE-EVIDENCE-2026-10-30.md) §2/§4。

| UTC（10/26） | Asia/Shanghai | 观察与来源 |
| --- | --- | --- |
| 00:07:11 | 08:07:11 | `parametric.exe` PID 20180、`xtop.exe` PID 20164 创建；04:38 快照仍为这两个身份。`loft.json:267-285`，见 BUG-085 §2。 |
| 04:29:56—04:30:44 | 12:29:56—12:30:44 | four/five 四个作业均 `succeeded`、连接/断开码 0、保存重载 true，最后作业 `14560f1b98bd41f4abda91d0ff2a6b8c` 于 04:30:44.689Z 结束。各 `jobs/<id>/job.json`、`native.log`，见 DEV049 T01 §2。 |
| 04:30:42 | 12:30:42 | `trail.txt.67` 最后一次已记录 IPC 连接。BUG-085 §2 引 `trail.67:5801-5807`。 |
| 04:30:48 | 12:30:48 | `building_worker` 后 4 分 37 秒无状态发布，**首次异常停止点**。`startup.log:4346-4349`，见 BUG-085 §2。 |
| 04:35:31 | 12:35:31 | 一次 `ready connected=True`；trail 无相应 IPC 初始化记录，二者矛盾，不能判定这次指向哪个端点。`startup.log:4349-4352` 与 trail 对照。 |
| 04:36:29 | 12:36:29 | 首次显式 `not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`；同一秒提交 `f54cda8`，但事故时源码 dirty、实际重建/替换时点与运行二进制哈希缺失。`startup.log:4353-4356`、`loft.json:242-260`、Git 提交，见 BUG-085 §2/§4。 |
| 04:38:23—04:38:24 | 12:38:23—12:38:24 | `parametric` 隐藏且有 hung 窗口；`xtop` 可见且未报告 hung；第三轮 `cases={}`、`jobs=[]`、`success=false`。空汇总不是作业失败或通过。`loft.json:261-299,2-5`。 |
| 04:38—04:45 | 12:38—12:45 | 后续协调器周期两次 timeout；日志共五个周期，文档称「两次重试」，缺显式 retry 调用记录，不能一一对应。BUG-085 §2/§6。 |
| 05:48:13 | 13:48:13 | trail 记录人工退出 Creo；不同于 10/29 的 WER 关闭。BUG-085 §2。 |

断连在四个成功作业**之后、下一作业建立之前**。事故时 `nmsd`/`pro_comm_msg` PID、创建时间和父进程、事故前后 `toolkit.lock` 与 unknown 状态均缺；`selected_session_configured=false` 只说明未配置选定会话。现存 10/27 重建的 `source.sha256`/worker 不能代替 10/26 的二进制身份。运行期改源码与 worker 重建冲突只是候选机制，未证明。

## 现场 B：2026-10-29，第三道折边作业内挂起及会话消失

环境：项目作者本机 Creo 12.4.0.0，DEV-051 T11 实机。报告元数据 `current_version=0.8.3`；这是事故时报告字段，不用后来的 0.8.4/0.9.0 发布号覆盖。T11 §3.8 记运行执行器由 16:53 源码构建，但最终 `source.sha256=541a9657…` 属之后格式化/注释整理后的构建；16:53 运行二进制的逐位哈希未留。来源：[BUG-085 离线证据](BUG085-OFFLINE-EVIDENCE-2026-10-30.md) §3/§4、[T11](DEV051-T11-ACCEPTANCE.md) §3.5/§3.8/§4.1。

| UTC（10/29） | Asia/Shanghai | 观察与来源 |
| --- | --- | --- |
| 08:53:22—08:53:28 | 16:53:22—16:53:28 | 驱动启动；`ready/connected=true`，会话 identity `2194098641453425411`，`sessions_observed=2`。`report.json` 的 `started_at`、`creo.startup`。这是事前快照，不预测下一调用。 |
| 08:53:33—08:53:54 | 16:53:33—16:53:54 | 底板 `579dc118…`、前两道折边 `07b5ec25…`、`b57c115d…` 均成功，模型 `6512c820cf674516912024ac5855610a` 到 rev 3，保存重载通过。T11 §3.5 与各 job。 |
| 08:54:04—08:54:05 | 16:54:04—16:54:05 | 第三道 `bb5543fb3c66404e95172876fa1ac9aa` 建立并开始，runner PID 21140，`worker_started=true`、`stage=executing_feature_plan`。作业 `job.json` 原件。 |
| 起点精确秒数缺 | 16:54 后 | `native.log` 最后一行是成功的 `ProArrayAlloc(1, sizeof(ProFeatureCreateOptions), …)`；下一步拟进入 `ProFeatureWithoptionsCreate`，**没有该调用的入口/返回记录，不能写成已证明在函数内部挂住**。原生日志末尾与 T11 §3.5。 |
| 09:01:05 | 17:01:05 | 420 秒 `creo_get_job` 仍为 running，驱动 `LiveStop`，未重提。`report.json:4737,4744`。T11 当时记 `toolkit.lock` 仍被该作业持有，后续实机阻塞。 |
| 09:01—11:51 | 17:01—19:51 | 无 GUI/进程连续观测、用户操作、trail 或等待链原件；不能填补为「一直挂起」。BUG-085 §3/§7。 |
| 11:51:03 | 19:51:03 | T11 §4.1 转述 Windows Application WER 1001 `AppHangB1` 和 Application Hang 1002，`xtop.exe` 版本 `40.0.2025.111` 被关闭；**仓库无该次 evtx/XML/dump 原件**。文件版本不等于 Creo 产品版本。 |
| 11:53、12:04、12:06 | 19:53、20:04、20:06 | 两次 tasklist 均无 `parametric`/`xtop`，记 `nmsd` PID 6504。20:04 旧有只读探测 `processes=[]`、`not_found_or_unreadable`、`-4`、exit 20；`creo_startup_status` 为 timeout、auto start disabled。T11 §4.1。 |

挂起本身**没有返回 `-4` 或 exit 20**。这组码来自会话已经消失的 20:04 探测，是后果层的连接失败映射。`job.json` 在本次只读时仍为 `running`，没有持久化终态；不能据此声称旧 worker 仍在运行，也不能伪填失败/回滚。T11 当时的 `native_owner.json` 记 PID 20408、相同 session fingerprint；runner PID 21140 与 owner PID 不是同一字段，worker PID/创建时间/退出码没有完整配对记录。`nmsd` 6504 的创建时间/父进程缺失，`pro_comm_msg` 状态缺失；19:51 后锁的持有/释放与 unknown 状态缺历史快照，不以当前文件推回。

## 现场 C：报告的「重启后几分钟自行退出」

这是一段**独立的进程生命周期观察**，目前只有 [BUG-001 recovery 的 10/29 附记](../validation/BUG-001-recovery-2026-10-17.md#2026-10-29-追加现场事实不改-2026-10-17-结论)、[外部反馈 R80x-4 §2](../validation/feedback-0.8.x-2026-10-30/2026-10-30CREO10.0.0.0-0.8.5-Creo10编译阻断跨三版未修与会话卡死第三次复现无开放条目.md) 的转述：「重启能启动，几分钟内自行退出，只留 `pro_comm_msg`」，并称 `session_health.reason=session_identity_stale`。反馈是静态分析，不能算报告方 Creo 10 的实机复现。

| UTC | Asia/Shanghai | 观察与限度 |
| --- | --- | --- |
| 缺 | 10/29 19:51 后，具体时刻缺 | 重启尝试次数、每次 `parametric`/`xtop` PID 与创建/退出时刻、是否正常退出或崩溃、当时 `pro_comm_msg` 身份均无可追溯原件。「几分钟」不是可换算的精确间隔。 |
| 14:05:41（10/29） | 22:05:41 | T11 §6 与 BUG-085 §3 又记录**新会话** PID 15156、`ready/connected=true`，22:06 后两轮作业取得终态。这是后来新会话的事实，不能反证先前是否发生短命重启，也不能把前述「自行退出」延长为此后一直不可用。 |
| 缺 | 记录 `session_identity_stale` 的精确时刻缺 | 附记和反馈有该 reason，T11 §4.1 的 20:04 表只列 `connection_state`/进程快照；缺完整原始响应，不能将 stale 绑定到 20:04 或某次重启 PID。 |

另有用词差异：T11 19:53/20:06 写「只剩 `nmsd` PID 6504」，附记/反馈写「只留 `pro_comm_msg`」。这些可能指不同时间的进程清单，但时间/原件不足，**不视为同一快照，也不擅自择一**。重启是否由人工或协调器、何时替换 worker、锁/unknown 当时状态均缺；`auto_start_creo=false` 只可绑定到 T11 的 20:04，不覆盖所有后续时段。

## 10/17 BUG-001 历史对照（不并入 A/B/C）

本机 Creo 12.4.0.0：10/17 09:36:45—09:36:52（UTC 01:36:45—01:36:52）非法尺寸 ID 作业回滚与断开成功；随后 trail 无精确时间戳的 IPC 初始化 `-97`/Warning，09:36:52—09:37:27（01:36:52—01:37:27）新作业 connect `-11`、未建模；09:52:07（01:52:07）Windows WER 1001/1002 记录同一 `xtop` PID 22520 `AppHangB1`。来源：[10/17 离线核对](../validation/BUG-001-hang-offline-2026-10-17.md)「已确认的失败链」及结构化证据。该次 `-97/-11` 是连接初始化通信失败，不是 A/B 的 `-4` 映射；事件前后的因果、SDK 或双安装并发根因仍未证明。12:42 的历史进程快照只说明 10/17 采集时没有 Creo，不能用于 10/29 或今天。

## 三方对照与同根判据

| 维度 | A：0.6.1 断连 | B：10/29 挂起/会话消失 | C：重启后退出 | 判定 |
| --- | --- | --- | --- | --- |
| `-4` / exit 20 | 04:36 连接探测 | 20:04 会话消失后探测 | 没有绑定该次重启的原码 | A/B **相同映射**，C 证据不足 |
| 首异常阶段 | 作业外 `building_worker` 空窗，随后 connect 失败 | 已受理第三道折边，原生日志停在特征创建前 | 新进程启动后生命周期，作业关联缺 | **不同** |
| Creo 进程 | 04:38 仍存活，`parametric` hidden+hung | 19:53/20:06 `parametric`/`xtop` 已消失 | 每次重启 PID/时刻缺；22:05 后有新会话 | **不同/不可比** |
| worker/nmsd | A 的 nmsd 身份及事故二进制缺 | B 的 nmsd 仅知 PID 6504，worker 逐位身份缺 | 均缺 | **证据不足** |
| 请求是否到达 Creo | 04:35 ready 与 trail 无 IPC 记录矛盾 | 已有原生元素树，特征创建是否进入/返回缺 | 无调用记录 | **证据不足** |
| 锁/unknown | 事故时缺 | 17:01 锁仍持有，终态缺；之后缺 | 缺 | **证据不足** |

`native/worker.cpp` 的探测失败分支固定返回 exit 20（[BUG-056](../work-items/BUG-056.md) §问题/代码映射）；它不是 worker 崩溃证据。B 在 `processes=[]` 时仍给 `-4`/exit 20，说明该组码也可表示没有可连接端点。若要判同根，至少须在**相同故障前阶段**取得会话/worker/nmsd 的 PID+创建时间+父子关系、运行二进制/源码指纹、连接请求是否到达 Creo 的 trail/原生日志，以及相同触发因素的可复核对照。若要判不同根，须取得足以排除共同机制的正证据；现在只可说失败阶段和观测面不同，**两种根因关系均证据不足**。没有确定代码根因，故无「待指派实现」的修复设计；不从并发构建、模态框或名字服务残留的候选假设直接设计重连、重试或杀进程。

## 缺证与下一次人工核对

| 现场 | 必要但缺失的材料 | 回答的问题 |
| --- | --- | --- |
| A | 事故时 `source.sha256`、worker 哈希与构建/替换时间；nmsd/pro_comm_msg PID、创建与父进程；当时 `toolkit_health`、锁/unknown 快照；前两轮 summary、驱动 stdout/stderr、`retry=true` 记录、GUI/进度框截图、事故会话 std.err/out | `building_worker` 空窗、一次 ready 与后续 -4 是否来自同一端点/构建；是否跨批次名字服务。详见 BUG-085 §7 A1—A9。 |
| B | 17:01—19:51 的 GUI/进程/用户动作；挂起会话 trail、WER 1001/1002 evtx/XML、等待链/dump；运行 worker 哈希、worker PID/创建/退出；19:51 后锁与 unknown 快照；nmsd 6504 完整身份、pro_comm_msg 身份 | 原生调用是否进入/返回、是否模态框/再生阻塞；会话消失与作业终态登记的关系。详见 BUG-085 §7 B1—B8。 |
| C | 每次重启的操作者/方式、起止时刻、`parametric`/`xtop`/nmsd/pro_comm_msg PID+创建/父进程、对应 Windows 事件、trail/std.err/out、完整 `session_health` 原始响应与时间、锁/unknown | 「几分钟自退出」是否确为新会话、何种退出、与 19:51 旧会话及 22:05 新会话的关系。 |

以上历史缺件不能靠今天的进程快照补齐。下一次取证须由用户指定的**会话负责人**执行，并先由使用者人工确认新/现有 Creo GUI 能响应菜单、模型视图及保存提示，核对产品版本和 PID/创建时间，确认只有 E 盘 `MCP_CREO_MechDog_dev` 面向该会话、没有其他窗口构建/替换 worker、没有活动原生作业或未处置 unknown；发现未处置 unknown 时保持保护并先走独立授权处置，不为取证清除它。当前 Creo 未运行，因此**现在不满足 GUI 可操作条件**，不作会话探测。

在上述条件由负责人重新确认且获后续实机/取证指派后，允许的**最小动作**：先固定时间（UTC+08）、进程 PID/创建时间/父进程与 GUI 状态、现有锁/unknown 和构建指纹，复制现存 Windows 事件、trail、std.err/out 与作业原件并计算哈希；随后最多一次有界、公开的只读 `session_health`/会话状态核对，同时记录完整原码、session fingerprint 和进程快照。只读健康值只证明采样时状态，不能单独放行建模。若需重启 Creo，先由会话所有者确认现场已留存、没有活动 worker/作业和未处置保护，并明确安排人工操作；本调查没有重启授权或自动重启步骤。

**立即停止条件：** GUI 无响应、Warning/模态框或再生进度不退、`building_worker` 长时间无终态、连接探测失败/超时/identity stale、会话 PID 变化或进程消失、worker/构建身份不符、`toolkit.lock` 忙或 unknown 存在、作业停在 running 且原生日志不再推进。出现任一项即保留原件，停止新提交及连续探测；已受理作业只按既有轮询契约查看，不重提、不清锁、不杀进程。交由会话负责人决定下一步人工取证范围。

本文件是历史证据重组与交接，不构成新复现、会话恢复、BUG-001 重开、BUG-085 定因、完整单元测试或原生验收。
