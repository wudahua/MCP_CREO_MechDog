# 开发台账完成事项归档

归档建立：2026-10-15；最近追加：2026-11-27；2026-11-26 登记：[DEV-103](work-items/DEV-103.md) 随 0.46.1 完成交付（文档目录治理与历史归档，纯文档整理，无剩余范围与未测项；随 v0.46.1 合入发布，见[发布记录](validation/RELEASE-0.46.1.md)），按台账规则由主台账移入本档案。2026-10-28 登记：[DEV-049](archive/work-items/DEV-049.md) 随 0.7.2 完成交付（0.6.1 两份反馈后续 PATCH，T00—T08；标签 `v0.7.2`，四附件，见[发布验收记录](validation/RELEASE-0.7.2.md)），按台账规则由主台账移入本档案，未测范围原样保留。2026-10-28 登记：[DEV-048](archive/work-items/DEV-048.md) 随 0.7.1 完成交付（0.6.0 四份反馈，T00—T05；main `ffa0a43`，附注标签 `v0.7.1`，四附件），按台账规则由主台账移入本档案，未测范围原样保留。2026-10-27 登记：DEV-047 随 0.7.0 完成交付（0.5.2 三份反馈完整交付，T00—T13；main `2a78358`，附注标签 `v0.7.0`，四附件与 Release 核对一致），按台账规则由主台账移入本档案。2026-10-26 登记：0.6.0 第二批交付（第二批可靠装配重建管线，FEAT-012/BUG-045 矩阵子项、FEAT-048 按路径/批量收养、FEAT-008 第二批配套，开发者实机已通过，WorkBuddy 黑盒经用户决定取消、未执行不记通过）。本轮各卡均有剩余开放范围（FEAT-012 源件更新/嵌套、FEAT-008 首批三项、FEAT-048 准入分支泛化、DEV-046 第三批），无整卡完成，不移动任何行；本批交付状态见[主台账](BACKLOG.md)与 [release-notes/RELEASE_NOTES_0.6.0.md](release-notes/RELEASE_NOTES_0.6.0.md)。当前排期与状态统一查看[主台账](BACKLOG.md)；本文件保留完成摘要、证据与历史来源，不承担当前排期。后续完成事项追加到本文件，主台账移除对应行。

## 已完成事项

以下保留原验收范围与目标版本，不因当前源码已到 0.7.1 而改写历史受测身份。2026-10-15 用户取消全项目 Creo 10 独立验收门槛，历史交接/复测安排不再作为当前要求；朋友反馈具体问题后再跟进。BUG-022 按已有本机证据完成并归档；DEV-015 的历史主干集成已核实，公开交付由 DEV-025 / v0.3.2 累计承接。BUG-038/042/043/044 于 2026-10-16 按用户决定采信 0.3.2 外部报告转已完成，均标注"本仓库无对应提交可核实、本机复现失败须重开"，不代表本机复验通过。

| ID | 优先级 | 状态 | 目标版本 | 完成摘要与证据 |
| --- | --- | --- | --- | --- |
| [BUG-175](work-items/BUG-175.md) | P1 | 已完成（0.47.1 外部复测） | 0.43.2（补修交付） | 两段启动单测共用假时钟。补修候选解包 120/120、慢探测 3/3；报告方随后在官方干净源码树两轮各 60/60 通过，补齐最后一项验收。[0.43.2 发布记录](validation/RELEASE-0.43.2.md) · [0.47.1 反馈 §2.3](validation/feedback-0.47.0-0.47.1-2026-11-26/originals/v0471-postcheck-backfill-missing.md) |
| [DEV-052](work-items/DEV-052.md) | P1 | 已完成（0.10.0 交付） | 0.10.0 | N00—N13 归档、集成和发布完成。Phase B 已回填主干、标签及远端四附件核验。后续反馈由 DEV-053 接续，原件、会话与几何余项仍按各技术卡跟踪。 [发布记录](validation/RELEASE-0.10.0.md) |
| [DEV-065](work-items/DEV-065.md) | P1 | 已完成（0.11.6 交付） | 0.11.6 | R13 五份原件已归档，四项夹具在 Creo 12.4 完成批次验收，标签及附件已核对。真实停滞、刚体平移放行和失败确认成功分支分别由 BUG-109、BUG-108、BUG-110 跟踪，BUG-111 已另行归档。 [发布记录](validation/RELEASE-0.11.6.md) |
| [DEV-105](work-items/DEV-105.md) | P1 | 已完成（0.48.0 交付） | 0.48.0 | 2026-11-27：补齐 `v0.47.0`（Release `459454832`）与 `v0.47.1`（Release `459515636`）远端四附件核对实证至 `RELEASE-POSTCHECK-2026-11-07.md` 及 `0.47.1.json`（`verified`），新增 `release_integrity.validate_post_release_backfill` 与 `tools/check_release_records.py --post-release` 门禁及 `PostReleaseBackfillGateTest` 单测，随 v0.48.0 交付并同步回填。[发布记录](validation/RELEASE-0.48.0.md) |
| [DEV-104](work-items/DEV-104.md) | P2 | 已完成（0.47.1 交付） | 0.47.1 | 2026-11-26：统一 `CLAUDE.md`/`README.md`/`docs/DEVELOPMENT.md`/`docs/development/ARCHITECTURE.md` 开发入口，完成四批 P1/P2 台账复核与分类校正（归档 `BUG-133`/`BUG-080`，对齐 `BUG-146/148/149/132/129/102/108/193`、`FEAT-078/001/009/055`、`DEV-076/081/095` 归属与计数）。随 v0.47.1 合入发布。[发布记录](validation/RELEASE-0.47.1.md) |
| [BUG-080](work-items/BUG-080.md) | P1 | 验收完成（0.5.2） | 0.5.2 | 单层英寸装配与毫米组件的变换、原始矩阵及只读重复查询已通过[第三轮 WorkBuddy 黑盒](validation/wb080-blackbox-round3-2026-10-24.md)。多级嵌套、缺件、父变换失败、子装配遍历失败仅有离线覆盖，实机范围见 [0.5.2 发布记录](validation/RELEASE-0.5.2.md)。 |
| [BUG-133](work-items/BUG-133.md) | P1 | 已交付 0.35.4 | 0.35.4 | Python 与原生旋转矩阵准入容差统一为 `1e-7`，Creo 10 已实测边界；其他 Creo 版本及 WorkBuddy 未测。[发布记录](validation/RELEASE-0.35.4.md) |
| [DEV-103](work-items/DEV-103.md) | P2 | 已完成（0.46.1 交付） | 0.46.1 | 2026-11-26：新增 docs/README.md 文档目录与维护规范，AGENTS.md 历史演进抽离至 docs/development/GOVERNANCE_HISTORY.md，70 个过程文档零改动归档至 docs/archive/（stage-notes、superpowers）；受发布完整性约束的台账与发布文档保留原路径。随 v0.46.1 合入发布。未测：无（纯文档整理）。 |
| [BUG-151](archive/work-items/BUG-151.md) | P2 | 已完成（0.36.1 协议契约修复；0.37.1 实机与全链路收口） | 0.37.1 | 2026-11-23：归档 0.35.8 反馈原件 [test-mcp-capabilities-drift.md](validation/feedback-0.35.8-2026-11-22/originals/test-mcp-capabilities-drift.md)。0.36.1 已把 `tools/test_mcp.py` 的 `creo_capabilities` 断言迁移至共享模块 `src/creo_mechdog/mcp_contract.py` 并新增 `--protocol-only`；0.37.1 复测实机发现该脚本未等待 `creo_startup_status` 即直调 `creo_session_status` 必命中 `building_worker` 失败，遂补齐 `wait_for_startup`、`tools/mcp_readiness.py` 对齐 `creo_startup.ACTIVE`（补 `connecting`/`waiting_for_channel`）、新增无 Creo/网络副作用的 `--offline` 模式纳入 `dev_check.OFFLINE_ACCEPTANCE_SCRIPTS`、显式打印异常回溯避开 TaskGroup 遮蔽、支持 `--create` 分页 `result_entries` 兜底与 `cancelled` 终态；同时排查并修复其余 9 个 `tools/` 脚本对 compact `creo_capabilities({})` 残留读取 `runtime`/`references`/`seed_library`/`tools` 的漂移，在 `tests/unit/test_mcp_contract.py` 增加静态护栏，并按反馈 §3 放宽 `test_startup_reboot` 2s 等待至 10s。本机 Creo 10.0.0.0（release 42）实机全模式通过：`--offline`、`--protocol-only`、默认、`--classic`（均 111 工具/2 页/契约通过）、`--create --simple`（job `55adbac9…`，7560 mm³，保存重载 true）与 `--create`（job `3390da54…`，81535.537 mm³、1 拉伸/1 圆角/5 孔，保存重载 true）；`tools/test_reference_contract.py` 协议面通过。未测：Creo 9/12 实机与 WorkBuddy 黑盒。见[发布记录](validation/RELEASE-0.37.1.md)。 |
| [BUG-144](archive/work-items/BUG-144.md) | P1 | 已完成（0.35.5 交付） | 0.35.5 | 2026-11-21：修复打包单测跨轮次污染。`tools/test_unit.py` 运行前原子写 `build/unit_test_run.json`（`running`/`completed`/`interrupted`、`run_id`、PID、源码身份；`O_EXCL` 锁仅在死 PID 时接管），报告带 `run_id` 并以 `.tmp`+`os.replace` 发布；`release_integrity.UNIT_EVIDENCE_ENFORCED_FROM=(0,35,5)` 起要求状态与报告共同支撑“全量通过”声明（`completed`、版本、`run_id`、两侧指纹等于当前受测源、`tests_run>0`），更早版本保持仅 `success=true`；`tools/package.py` 新增 `--source-root`/`--unit-report`，门禁移到写 ZIP、sidecar、stage 之前。`SeedPackagingGateTests` 在临时 checkout 副本上覆盖显式/默认/stage 三条路径与六类拒绝；新增 `tests/unit/test_unit_evidence.py`。修复前在 `5b32ef7` 临时 worktree 用陈旧失败报告复现 exit 1 与 `release record gate rejected ... success=False`（`build/bug144_repro_old_failure.txt`）。未测：外部反馈环境（Windows 10/Python 3.13/Creo 9 SDK）复跑。 |
| [DEV-099](archive/work-items/DEV-099.md) | P3 | 已完成（0.35.5 交付） | 0.35.5 | 2026-11-21：README 特性段固定“109 个公开工具”改为引用 `creo_capabilities.tool_count`，去掉重复静态计数并保留隐藏工具说明；复用 BUG-138 两条离线验收，`tools/test_update_check.py --network-failure` exit 0（`tool_count=110`）、`tools/test_model_reconciliation.py --offline` exit 0。范围限文档，不涉及 Creo 实机与 WorkBuddy。 |
| [BUG-142](archive/work-items/BUG-142.md) | P1 | 已完成（0.35.5 交付） | 0.35.5 | 2026-11-21：补做真实 disconnect 阻塞路径。`native/result_delivery.h` 增加默认关闭的 `MECHDOG_TEST_DISCONNECT_DELAY_MS`（上限 60000 ms），在预断开 checkpoint 后、`ProEngineerDisconnect` 前休眠；本机 Creo 10.0.0.0 / release 42 作业 `9a73ad5e6a50466c8b4c2d3fdf6fc583` 在延迟窗口内写出预发布 `native_result.json`（`delivery_complete=false`、`before_disconnect`、`success=true`、保存重载 true、无 `.tmp`），对 worker pid 25844 发 `SIGTERM` 后转 `unknown_outcome`（模型 `revision=0`、`pending_job` 保留、无残留 `.tmp`）；对照作业 `8d84a22553f14c5583338b7330cd1959` `succeeded` 证明会话仍可用。证据 `build/bug142_live_disconnect.json`；原生 `delay` 模式与 Python 用例 12 项通过。未测：其他 Creo 版本、WorkBuddy 黑盒与 0.32.0 原模型。 |
| [DEV-098](archive/work-items/DEV-098.md) | P2 | 已完成（0.35.2 交付；2026-11-21 补齐装配坐标实机） | 0.35.2 | 2026-11-21：0.35.1 的通用 `geometry_selector` 零候选 `nearest_edges`（本机 Creo 10 方块 `candidate_count=12`、候选 ids 54/55/56/59/60）与 0.35.2 的 `target="surface"` 零匹配 `nearest_surfaces`（方块 6 候选、列 5 条 ids 65/67/58/53/63）及装配坐标 `requested_coordinate_space` 溯源已随版本发布。2026-11-21 本机 Creo 10.0.0.0 / release 42 补齐装配坐标实机：60×40×10 基板固定于装配 `x=100`，`coordinate_space="assembly"`、`points_mm=[[1000,1000,1000]]` 的 mate 面选择器零匹配，作业 `6eae1dd56414441a904fa5b6ce431681` 失败于 `constraint_stage="reference"`，诊断保留 `requested_coordinate_space="assembly"`、`candidate_count=6`、`matched_ids=[]`，`nearest_surfaces` 5 条（ids 65/69/67/58/53）；面 `origin_mm` 的 x 为 `0`/`60` 而非装配坐标 `100`/`160`（纯平移不改变点面距离，帧别以原点判定；最近 `points_offset_mm=840` 与换算后的组件坐标 `(900,1000,1000)` 到 x=60 面一致），证明候选按 occurrence 放置换到组件帧测量且绝不自动选中。证据 `build/dev098_assembly_space.json`。未测：Creo 12.4/9 同一诊断、圆边轴与其他选择器组合、WorkBuddy 黑盒。 |
| [BUG-137](archive/work-items/BUG-137.md) | P1 | 已完成（0.34.0 交付） | 0.34.0 | 2026-11-21：隔离 `tests/unit/test_inspection_only_admission.py` 的真实 `subprocess.Popen`，消除 `runner.log` 继承句柄导致的 teardown WinError 32；发布记录出现全量单测通过声明时必须由 `build/unit_test_report.json` 的 `success=true` 支撑。全量 4229 项通过、0 failures、0 errors、6 skipped，完整 dev_check exit 0；已随 v0.34.0 发布。证据见[发布记录](validation/RELEASE-0.34.0.md)。 |
| [BUG-138](archive/work-items/BUG-138.md) | P1 | 已完成（0.34.0 交付） | 0.34.0 | 2026-11-21：去除独立验收脚本硬编码工具数 82/84，改为 `creo_capabilities` 与实际工具列表一致性校验并保留可见断言上下文；`dev_check` 每次执行两项离线验收门禁，当前均 exit 0，完整 dev_check 通过。已随 v0.34.0 发布，证据见[发布记录](validation/RELEASE-0.34.0.md)。 |
| [DEV-097](archive/work-items/DEV-097.md) | P2 | 已完成（0.34.0 交付） | 0.34.0 | 2026-11-21：自 0.34.0 起强制 Release 正文列出四附件名与 sidecar 指引，正文出现的每个 SHA256 均须匹配真实 sidecar；历史版本祖父化。v0.34.0 远端执行 `tools\check_release_assets.py --tag v0.34.0` exit 0，四附件、两个 sidecar 与正文自证全部通过；v0.33.0 回归无误报。证据见[发布后核对](development/RELEASE-POSTCHECK-2026-11-07.md)。 |
| [DEV-093](archive/work-items/DEV-093.md) | P2 | 已完成（0.31.1 交付） | 0.31.1 | 2026-11-19：`AGENTS.md` 实机联调补充改为 2026-11-19 常设授权，可直接启动/重启 Creo 与 nmsd、结束卡死或异常进程、确认后清理残留 `toolkit.lock` 与 unknown 保护状态、编译执行器、建模、GUI 操作与几何/保存重载验收，不再逐次确认；授权延续到后续会话。数据边界（不删除或改写用户模型、历史证据与已发布产物）与 Toolkit 单通道、busy 拒绝、revision 保护、保存重载核验不变。`docs/DEVELOPMENT.md` 中“实机确认制”表述同步。仅文档/规则变更，未改代码与原生，公开工具仍 109；无实机验收项。 |
| [BUG-125](archive/work-items/BUG-125.md) | P1 | 已完成（0.24.1 交付） | 0.24.1 | 2026-11-13：`config.json` 新增 `creo_startup_args`，参数以 `list2cmdline` 拼在 PSF 之后交给 `parametric.exe`（PSF 内 `RUN=` 追加会被丢弃）；数组/非空字符串/禁控制字符校验；`build_native` 的 `startup_keys` 排除该键与 `creo_worker_launch`，改启动选项不触发重编。Creo 12.4 实机：`xtop.exe -g:no_graphics -i:rpc_input -ppid 5100`、无界面、`toolkit_code=0`。离线 5 项单测。未测 Creo 13.4/9/10。证据 [STARTUP-HEADLESS-2026-11-13](validation/STARTUP-HEADLESS-2026-11-13.md#bug-125启动参数)。 |
| [BUG-126](archive/work-items/BUG-126.md) | P1 | 已完成（0.24.1 交付） | 0.24.1 | 2026-11-13：无图形会话中 `create_plate()` 的 `ProWindowActivate=-8` 原被判为整任务失败（几何、存盘、重载均已通过）；改为记录 `window_activate_code` 并进结果 JSON，其余窗口步骤保持严格。Creo 12.4 无图形 job `907995ee…` succeeded（12475.327397219 / 12475.3274122872 mm³、`window_activate_code=-8`、预览生成），GUI job `3e57c202…` succeeded（`window_activate_code=0`）。未测 `generic.cpp`/`drawing.cpp` 同类调用与 Creo 13.4。证据 [STARTUP-HEADLESS-2026-11-13](validation/STARTUP-HEADLESS-2026-11-13.md#bug-126无图形会话的窗口激活容错)。 |
| [BUG-127](archive/work-items/BUG-127.md) | P1 | 已完成（0.24.1 交付） | 0.24.1 | 2026-11-13：新增 `desktop_worker.py`，经 `Shell.Application`（explorer.exe 内执行）以 `SW_HIDE` 启动 worker 并回收 stdout/退出码，校验会话/映像/用户 SID，许可环境不一致时放弃该路径；`creo_worker_launch` 支持 `auto`/`direct`/`desktop`，`auto` 仅在直连 `-4` 时复核一次，失败回退并附 `desktop_retry`，返回值新增 `worker_launch`。Creo 12.4：无会话时两路径均 `-4` 并正确回退；有会话时 `direct`/`desktop` 均 `toolkit_code=0`。报告宿主（Creo 13.4 + WorkBuddy）未验，BUG-005 状态不变。离线 22 项。证据 [STARTUP-HEADLESS-2026-11-13](validation/STARTUP-HEADLESS-2026-11-13.md#bug-127worker-桌面复核)。 |
| [BUG-128](archive/work-items/BUG-128.md) | P2 | 已完成（0.24.1 交付） | 0.24.1 | 2026-11-13：`session_status` 新增 `toolkit_hint`，覆盖 `0`/`-4`/`-8`/`-36`/`-38` 与未知码，`-4` 明示「不是许可或版本问题」、`-38` 明示「先看 xtop 窗口标题」、退出码 20 说明为探针约定；`creo_startup` 的 `launch_failed` 引用该提示；文本不含路径/许可值/命令行。未构造 `-38` 模态框，不改既有错误码语义（FEAT-006 独立）。证据 [STARTUP-HEADLESS-2026-11-13](validation/STARTUP-HEADLESS-2026-11-13.md#bug-128返回码提示)。 |
| [DEV-089](archive/work-items/DEV-089.md) | P2 | 已完成（0.24.1 交付） | 0.24.1 | 2026-11-13：`docs/INSTALL.md` 新增编译工具链实物预检（`cl.exe`/`windows.h`/`kernel32.lib` 三条 `Test-Path`、`vs_installer --quiet` 无输出不等于卡死、`-VcVars64` 包装脚本与 SDK 升级同步）、`creo_startup_args` 无图形示例与 `creo_worker_launch` 说明、四条排错项；`docs/COMPATIBILITY.md` 新增 Creo 13.4.0.0 编译层实测分节并声明不作支持。未改 `setup.ps1`/CI，未复现 Creo 13.4 安装。证据 [STARTUP-HEADLESS-2026-11-13](validation/STARTUP-HEADLESS-2026-11-13.md#dev-089安装文档)。 |
| [DEV-088](archive/work-items/DEV-088.md) | P2 | 已完成（本地离线资料） | 未排期 | 2026-11-13：skill/指南明确由开发 AI 自主发现参照、取树对照、重绑与重建验收；责任、授权不足/缺参照/已知提取失败/中间状态分支及独立几何判据完整。静态解析、四情境只读试用、格式/链接/台账与终审通过。本次仅资料，无真实 Creo 取样或重建，未改产品/实机/发布。 |
| [DEV-087](archive/work-items/DEV-087.md) | P2 | 已完成（本地离线资料） | 未排期 | 2026-11-13：新增面向软件维护者的白话说明和历史示例，skill 默认先讲行为/因果/独立证据，区分软件、几何、工程；结构/链接/台账核验、独立只读试用和终审通过，修正试用中等体积的过度概括。仅资料，未改产品/实机或发布；不承诺 AI 试用替代用户理解反馈。 |
| [DEV-086](archive/work-items/DEV-086.md) | P2 | 已完成（本地离线资料） | 未排期 | 2026-11-13：参考后台建模案例，独立补充设计意图/几何/坐标/任务效果/重载/装配依赖与工艺证据边界，skill 薄路由和指南入口同步；离线校验、独立试用/终审通过。未引入 Java 后端/第二会话/教材，未动其它任务产品现场，未编译、实机或发布；命令、指纹与未测范围见工作卡。 |
| [DEV-085](archive/work-items/DEV-085.md) | P2 | 已完成（本地离线资料） | 未排期 | 2026-11-12：评估 CSCTACG/creo-dev 固定提交，从本机 12.4 SDK 独立补充 API 模式专题及 skill 路由；9 个 API 页面、7 个正式头文件与示例辅助头查证，格式/链接/台账检查、独立只读试用/终审通过。未复制上游原文/代码，未改产品/打包，未编译、实机、合 main 或发布；来源、指纹与未测范围见工作卡。 |
| [DEV-084](archive/work-items/DEV-084.md) | P2 | 已完成（本地离线资料） | 未排期 | 2026-11-12：新增中文 TOOLKIT 开发指南、项目 `creo-mechdog-dev` skill 与开发入口；本机 12.4.0.0 SDK 三条查证路径、skill 格式/文档链接/台账检查、独立只读试用与终审通过。仅 Git 检出的本项目资料，未编译/实机/WorkBuddy，未改产品和打包，未合 main 或发布；具体命令、指纹与未测范围见工作卡。 |
| [BUG-118](archive/work-items/BUG-118.md) | P1 | 已完成（0.21.1 交付） | 0.21.1 | 2026-11-11：3 截面 + 2 导线曲面放样（FEAT-065/M2）在 `detail=compact` 下整条 `surface_loft` 记录只剩 `detail_truncated`，`surface_area_mm2`/`guide_count`/`quilt_count`/`quilt_closed_native` 全缺（job `6510998c…`），而同一作业 `detail=full` 有 `section_count=3`、`guide_count=2`、`quilt_count=1`、`surface_area_mm2=1599.9999999999995`。根因：`src/creo_mechdog/operation_results.py::enforce_compact_budget` 第 2 阶段自最后一条记录倒序剥可选字段，放样恰为计划末条且测量字段不在保护集合。修复：新增 `OUTCOME_OPERATION_KEYS`（面积/闭合/计数/曲线与夸特 ID 等标量）并入 `_status_core` 保护集合，大块 `profile`/`surface_group`/`native_section` 仍可裁、`RESPONSE_BUDGET` 上限不变。验证：`tests/unit/test_large_plan_result_budget.py` 30 项 OK（含新增 `test_a_trimmed_surface_receipt_keeps_its_measurements`）、全量 3314 项 OK；实机 `tools\test_surface_loft_guides.py --live --confirm-session-usable` 离线 12 项 + 实机 22 项全 PASS（3 截面 job `2a2ee086…`、单张开放 quilt、bbox 40.12/40.12 mm、保存重载 verified）。未测：其他可能被整体剥掉的 op 类型、保护标量后的极端预算压测、Creo 9/10 与 WorkBuddy。见[版本说明](release-notes/RELEASE_NOTES_0.21.1.md)与[发布记录](validation/RELEASE-0.21.1.md)。 |
| [DEV-075](work-items/DEV-075.md) | P1 | 已完成（0.18.2 交付） | 0.18.2 | 2026-11-07：0.18.0 升级复核反馈的离线修复批。新增 `creo_mechdog.git_evidence`，t07 与另外 7 个离线驱动在无 git / 非仓库目录降级为文件遍历并标记 `git_unavailable`，官方 `source.zip` 解压后全量单测 2835 项 0 失败 0 错误（此前 t07 13 项 ERROR）；`release_download` 增加 `api.github.com` asset API 二级通道；`RELEASING` 补源码包解压门禁、「当前版本为 X」逐 ID 行与 DEV-072 表；新增 [发布后附件核对](development/RELEASE-POSTCHECK-2026-11-07.md) 实测 v0.17.4/v0.18.0/v0.18.1；修正 RELEASE-0.18.0 文件名、FEAT-059 状态与 2744 口径。门禁提交 `9e57b05`（dirty=false、指纹 `e3afe4a9…`）。未测：Creo 实机（无原生改动）、asset API 真实直连失败、WorkBuddy 与 Creo 9/10。见[版本说明](release-notes/RELEASE_NOTES_0.18.2.md)与[发布记录](validation/RELEASE-0.18.2.md)。 |
| [DEV-068](archive/work-items/DEV-068.md) | P3 | 已完成（交付核对见 PR） | 0.12.1 | 用户 README 改版单独合入，校正版本/97 工具与示例；补 离线测试隔离准备。业务/原生实现与种子 PRT 字节不变；本轮未连接 Toolkit。检查及远端四附件核对见 [PR #12](https://github.com/wudahua/MCP_CREO_MechDog/pull/12)、[发布记录](validation/RELEASE-0.12.1.md)。 |
| [DEV-049](archive/work-items/DEV-049.md) | P1 | 已完成（已随 0.7.2 交付并发布） | 0.7.2 | 2026-10-28：0.6.1 两份反馈后续 PATCH（T00—T08）随 0.7.2 交付：T00 原件逐字节归档与 32 章节映射；T01 断连事故离线核对结论为证据不足、根因未定（BUG-085，13 正例 + 2 负例编辑闭环缺口保留）；T02 `dev_check --unit-timeout-seconds` 默认 900 秒（DEV-050）；T03 PS5.1 安装 stderr 误报修复与 T08 批内补充 `Invoke-ExternalStep` 统一 8 处外部调用（BUG-086）；T04 原斜槽六例经 BUG-087 修复后实机 6/6（autodim run `20261028T102858_b2d5e5c9`、coordinates run `20261028T104324_57f20a2d`）与 Right 面 ±Z 回归无退化；T05 多环/预览查缺与替代夹具离线就绪（差项实机未跑，原输入缺失）；T06 种子 15+2 实机全部通过（FEAT-030 转已验收未收口）；T07 文档收口；T08 集成与发布（main 合并、附注标签 `v0.7.2`、Release 四附件，逐件下载哈希核对）。全量 `dev_check --work-item DEV-049` 1128 项单元通过、无 timed_out；新目录 `setup.ps1` 以 `2> err.log` 重定向形式安装验证通过（exit 0、九种子 SHA256 与清单一致、原生执行器编译成功）；公开工具保持 94。GAP-1/GAP-2（0.7.1 后主干回填 `d2e37b0` 差异）由本版覆盖。未测：WorkBuddy 按用户 2026-10-26 决定未执行、外部 Creo 9/10 未复测、BUG-085 根因未定、BUG-066 待复现、Creo 9 实机编译与建模未验收、未做新 Toolkit 连接与故障注入。见[发布验收记录](validation/RELEASE-0.7.2.md)与[版本说明](release-notes/RELEASE_NOTES_0.7.2.md)。 |
| [DEV-047](archive/work-items/DEV-047.md) | P1 | 已完成（已随 0.7.0 交付并发布） | 0.7.0 | 2026-10-27：0.5.2 三份外部反馈完整交付（T00—T13）。main 合并提交 `2a7835808e1ea2981df411c7e2a4e94d1fd4d92d`，附注标签 `v0.7.0` peeled 指向同一提交；[GitHub Release v0.7.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.0)（424956318，非草稿、非 prerelease）四附件与正文 SHA256 一致。本机 966 项单元测试、dev_check、SDK 构建、Creo 12.4 实机矩阵（T05 毫米 18/18+英寸、T06—T09、T12、装配专项 38 作业、T07 图像目视）及全新目录 setup.ps1 安装冒烟通过；公开工具 92→94。未测：WorkBuddy 按用户 2026-10-26 决定未执行、外部 Creo 9/10 未复测、unknown 单位仅离线覆盖、BUG-078 三现场未 apply、BUG-066 原始失真未复现、FEAT-050/嵌套回放/新约束类型/世代二进制可复现性等父卡范围保留。历史阶段记录与未测项保持原日期，见[发布验收记录](validation/RELEASE-0.7.0.md)与[版本说明](release-notes/RELEASE_NOTES_0.7.0.md)。 |
| [DEV-048](archive/work-items/DEV-048.md) | P1 | 已完成（已随 0.7.1 交付并发布） | 0.7.1 | 2026-10-28：0.6.0 四份反馈批次（T00—T05）随 0.7.1 交付。main 提交 `ffa0a433736917812d1040dba7c6d7190b5f82f6`，附注标签 `v0.7.1` peeled 指向同一提交；[GitHub Release v0.7.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.7.1)（非草稿、非 prerelease，四附件；源码包 5 365 479 B、种子包 493 394 B，与[发布记录](validation/RELEASE-0.7.1.md)核对表一致）。T01 收养侧车完整性与原子发布、T02 拒绝后引用生命周期、T03 工作卡与发布检查回填、T04 Right 面 ±Z 定向实机（实际帧、800 mm³、八点 AABB 与重心、保存重载 true、平行法向原生拒绝并回滚）、T05 集成与 PATCH 发布；公开工具保持 94，本机 1017 项单元测试。未测：WorkBuddy 按用户 2026-10-26 决定未执行、外部 Creo 9/10 未复测、T04 只覆盖 Right 面 ±Z（`native_acceptance=partial`，未重跑 DEV-047 完整矩阵）、倾斜面/多轮廓/纯 Z u_axis 历史现象不在本版范围、未做真实 worker 超时与文件锁注入。工作卡历史与未测项保持原日期，见[发布验收记录](validation/RELEASE-0.7.1.md)与[版本说明](release-notes/RELEASE_NOTES_0.7.1.md)。 |
| [DEV-045](archive/work-items/DEV-045.md) | P2 | 已完成（外部确认关闭） | 未排期 | 2026-10-23：RELEASING 第 7 项"Release body 必含两包文件名与完整 SHA256 并核对远端"已两次实际执行通过（[0.4.7](validation/RELEASE-0.4.7.md) 首次、[0.5.1](validation/RELEASE-0.5.1.md)）；[0.5.0 外部报告三 §4](validation/feedback-0.5.0-2026-10-22/manifest.json)确认两包命名自 0.4.7 起按 `MCP_CREO_MechDog-{version}-source.zip`/`-seed-library.zip` 定名执行、Release body 附两包完整 SHA256 与 `.sha256` 附件且远端下载复核一致（源码包 `dd8b49bb…`/种子包 `fb84a37d…`）。按报告关闭移入本档案，工作卡历史保留。 |
| [DEV-041](archive/work-items/DEV-041.md) | P1 | 已完成（Release 发布与附件核对通过） | 0.3.6 | 2026-10-18：PR #11 合并 `ca105b9`、指纹链提交 `1f38069`（种子清单版本与 seeds.py 指纹同步），`v0.3.6` 标签指向该提交；[Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.3.6)（Pre-release）附源码包（588 文件，SHA256 `6cf1d925…`）与种子包（9 种子，`829474ed…`），远端下载核对一致，核对回填 [PR #11](https://github.com/wudahua/MCP_CREO_MechDog/pull/11#issuecomment-6245231613)。范围：DEV-040 的 BUG-059 修复、BUG-057 随版诊断脚本、六份 0.3.5 反馈补录与台账重构；无 C++ 改动故无原生回归。验收：dev_check 356/356、隔离黑盒三场景、复核 12/12；未测范围见[版本记录](validation/RELEASE-0.3.6.md)。 |
| [DEV-040](archive/work-items/DEV-040.md) | P1 | 已完成（本机诊断与 Python/MCP 修复阶段） | 未排期 | 2026-10-18：BUG-057 本机未复现，交付纯文件竞争/错误分类诊断，原环境根因保留；BUG-059 修复原生前自身占位悬挂并澄清原生后 unknown 阶段；BUG-058 仅静态核对。完整开发检查 356/356，WorkBuddy 隔离 A/B/C 补齐拒绝、保护、幂等与 compact/full，标准 stdio 复核 12/12。按用户收尾要求归档已交付阶段，G2 原环境机制与 G3 锁修复未完成仍归 BUG-057；真实 Creo 恢复、几何与并发未测（该阶段收尾时未合入/发布，修复已随 0.3.6/DEV-041 交付）。见[复核](validation/DEV-040-closeout-review-2026-10-18.md)与[隔离报告](validation/DEV-040-isolated-contract-2026-10-18.md)。 |
| [BUG-059](archive/work-items/BUG-059.md) | P1 | 已修复（Python/MCP 隔离契约验收） | 未排期 | 原生派发前拒绝为 failed/reconciliation_refused，附 reason/failure_phase，锁内仅释放自身 recovery_pending；原生连接后指纹拒绝保留 unknown 与保护。WorkBuddy A 验证实际 Python 拒绝、占位释放与状态不变，B/C 明确合成边界，幂等与 compact/full 一致；标准 stdio 12/12。真实会话切换/中断与原生恢复未测，FEAT-018 继续验收；未合入/发布。见[收尾记录](validation/DEV-040-closeout-review-2026-10-18.md)。 |
| [DEV-039](archive/work-items/DEV-039.md) | P2 | 已完成 | 未排期 | 2026-10-18 重读最新台账，将原 37 项待核实分为 20 待复现、10 规则核对、2 待开发、2 工程规划、1 剩余验收、2 历史观察。全部 87 个 ID、原优先级、目标版本和范围保留；同步 19 份既有任务卡、补 BUG-019 卡并更新模板和开发入口。最新反馈、兼容矩阵及原有未提交修改保留，文档一致性检查通过；没有把分类当作修复或新增测试。 |
| [DEV-036](archive/work-items/DEV-036.md) | P1 | 已完成 | 未排期 | BUG-056 执行卡，四轮闭环（未合入 main/未发布，开发基线 0.3.5）：①定位跨批次遗留 nmsd 会话信息失效（trail 证明失败请求未达 Creo），「40 秒周期」为轮询伪影，服务侧无缺陷，`creo_session_status` 增只读 `creo_process_snapshot`（7 例单测+dev_check）；②用户处置环境后 38 次探测跨 7.5 分钟+建模闭环无掉线（T03～T05）；③T08 M2 经 live 取证 abandon_new 收尾（跨会话指纹保护一次正确拒绝后成功，幂等/审计保留）；④WorkBuddy 黑盒全部通过（新字段、3 次间隔稳定、MCP 建模 rev 0→2、T07 空值协议含字面 "null" 完整终态补齐 BUG-055 遗留、M2 终态确认），开发者核对 9/9。证据见[核实记录](validation/BUG-056-DEV-036-investigation-2026-10-17.md)、[WorkBuddy 验收](validation/DEV-036-WorkBuddy-acceptance-2026-10-17.md)及[提示词](validation/DEV-036-WorkBuddy-test.md)。遗留观察：未知参数键静默忽略未立卡；`creo_process_snapshot` 失败场景黑盒表现待自然出现。 |
| [BUG-056](archive/work-items/BUG-056.md) | P1 | 已完成（用户确认关闭） | 未排期 | Toolkit 通道验证通过后约 37～41 秒静默失效（-4/exit 20），Creo 存活、用户确认非人为。2026-10-17 DEV-036 两轮核实：定位为跨批次遗留 nmsd（名字服务）会话信息失效——失败请求未到达 Creo（trail 无 IPC 初始化记录），「40 秒周期」为客户端轮询+快照 30 秒 stale 期伪影，服务侧探测/快照/分类无缺陷；`creo_session_status` 增只读进程快照（服务重启后生效）。清理遗留 nmsd 并重启 Creo 后，38 次探测跨约 7.5 分钟+空闲对照与建模闭环（rev 0→2、保存重载、体积精确一致）全部通过。nmsd 内部触发器为黑盒残余假设；T07/T08、WorkBuddy 黑盒由 DEV-036 跟踪。证据见[核实记录](validation/BUG-056-DEV-036-investigation-2026-10-17.md)。 |
| [DEV-038](archive/work-items/DEV-038.md) | P2 | 已完成 | 未排期 | 2026-10-17 按 humanizer-zh 改写主台账的 85 项任务说明，解释常见术语，保留任务编号、优先级、目标版本和证据链接。同步另一次 DEV-036 调查的最新进度，未自行关闭任务。任务、表格、链接和其他文件摘要检查通过；本次只改文字，未执行建模或发布。 |
| [DEV-037](archive/work-items/DEV-037.md) | P2 | 已完成 | 未排期 | 2026-10-17 核对较早完成事项均已归档，迁入旧进展与 10 段反馈补录并折叠显示，主台账从 56,381 缩至 34,736 字节（减少 38.4%）。原有 85 项未完成行、39 项完成行及其状态/验收边界保持；ID、链接/入站锚点、表格、历史原件/上一轮修改摘要和 diff 检查通过。仅文档整理，未连接 Toolkit、未升版或发布。 |
| [DEV-035](archive/work-items/DEV-035.md) | P1 | 已完成（发布候选） | 0.3.5 | 用户指定统一交付DEV-033/BUG-054、DEV-034/BUG-055及反馈/BUG-056登记；两目录各307项单元/增量检查、84工具、SDK实际编译/6521常量、12项ABI、独立安装和9种子ZIP通过。已知通道问题和M2未取得范围保留；实际main/Release/四附件SHA256在[PR #10](https://github.com/wudahua/MCP_CREO_MechDog/pull/10)回填，见[验收](validation/RELEASE-0.3.5.md)。 |
| [BUG-054](archive/work-items/BUG-054.md) | P1 | 已完成（本机实机及WorkBuddy已测范围） | 0.3.5 | 拉伸/旋转切除零去料曾静默成功。2026-10-17 在 0.3.4 复现并按 DEV-033 修复：cut 前后测体积，零去料抛错回滚（revision 不变、别名无残留），成功返回 material_removed_mm3；T01～T08 实机与 WorkBuddy 5 场景黑盒均通过，revolve 正反例纳入。外部 Creo 10/9、thin/装配/钣金 cut 未测；BUG-016 不随本项关闭。证据见[验收记录](validation/BUG-054-cut-material-2026-10-17.md)与[黑盒记录](validation/BUG-054-WorkBuddy-acceptance-2026-10-17.md)。 |
| [BUG-055](archive/work-items/BUG-055.md) | P1 | 已完成（WorkBuddy核心范围，M2未完成） | 0.3.5 | 根因链闭环：WorkBuddy 实测客户端把显式 null 降级为空串（服务端回显 received ''），服务端各层无转换；修复后空串精确拒绝、省略字段替代路径端到端成功。M1 abandoned 闭环+幂等+历史保留全过；M2 终态与稳定通道字面 null 对照因通道静默掉线未取得（保护按契约保留），外部 Creo 9 未复测。2026-10-17 补录：BUG-056 关闭后 M2 已按用户确认经 live 取证 abandon_new 收尾（abandoned/rev 0/保护清除），字面 null 稳定通道对照仍归 DEV-036 T07。 |
| [DEV-033](archive/work-items/DEV-033.md) | P1 | 已完成（本机实机及WorkBuddy已测范围） | 0.3.5 | 2026-10-17 按 G0～G5 执行 BUG-054：会话条件核对后复现、确定孔类一致契约、最小修复（native 守卫+docstring+compact 白名单+4 项单元回归）、实机 T01～T08 与 WorkBuddy 5 场景黑盒全通过（revolve 正反例纳入），台账/能力说明同步。未测边界（外部 Creo 10/9、thin/装配/钣金 cut）保留；未合入 main、未发布。 |
| [DEV-034](archive/work-items/DEV-034.md) | P1 | 已完成（WorkBuddy核心范围，M2未完成） | 0.3.5 | G0～G4 完成后 WorkBuddy 核心验收通过（客户端 null→空串降级实证、M1 闭环、空串精确拒绝、字面 null 接受、unknown 保护保留），开发者只读核对一致。未取得：M2 终态与稳定通道对照（通道 37–41 秒静默掉线三次，环境异常，是否另立条目待用户定）、外部 Creo 9。事实边界：同名残留模型触发 abandon owned 保护、journal 临时名过深数据根逼近 260 路径上限。不升版、不合入、不发布。 |
| [DEV-032](archive/work-items/DEV-032.md) | P1 | 已完成（发布候选） | 0.3.4 | 用户指定版本并要求汇总七个待合分支；BUG-001按用户决定关闭，FEAT-018/029仍验收中。两目录各297项单元/增量语言、独立SDK编译、12项ABI、84工具、源码分发及九种子ZIP安装通过；实机/WorkBuddy本轮未执行。实际main/标签/Release/四附件SHA256回填[PR #9](https://github.com/wudahua/MCP_CREO_MechDog/pull/9)，见[本版记录](validation/RELEASE-0.3.4.md)。 |
| [BUG-001](archive/work-items/BUG-001.md) | P0 | 已完成（用户决定关闭） | 0.3.4 | 2026-10-17用户要求先关闭并将待合分支一并交付main。正式恢复实现及部分实机证据保留；IPC初始化通信失败/Creo无响应根因未定，完整恢复与WorkBuddy未完成，不代表全部验收通过。详见[离线排查](validation/BUG-001-hang-offline-2026-10-17.md)；后续复现沿用本ID重开，FEAT-018/029仍验收中。 |
| [DEV-029](archive/work-items/DEV-029.md) | P1 | 已完成 | 0.3.3 | main@9ee923c、v0.3.3 与公开 [Pre-release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.3.3)一致；两目录各263项、原生回归和主干CI通过，四份主干附件已回下载核对SHA256；最终交付见 [PR #8](https://github.com/wudahua/MCP_CREO_MechDog/pull/8)，[候选验收](validation/RELEASE-0.3.3.md)及未测范围保留。 |
| [DEV-015](archive/work-items/DEV-015.md) | P1 | 已完成（历史主干准备与集成） | 0.3.1 | 已核实 main@515d50b；未存在的 0.3.1 Release 不补造，累计公开交付由 DEV-025 / 0.3.2 承接。 |
| [DEV-025](archive/work-items/DEV-025.md) | P1 | 已完成（发布候选验收） | 0.3.2 | 三批代码及完成文档集成，新目录独立安装、247 项单元、匹配 SDK 构建、8 成功/1 预期回滚作业、82 工具/9 种子和种子 ZIP 实际安装通过。见[本次证据](validation/RELEASE-0.3.2.md)；实际 main/标签/公开附件交付在 [PR #6](https://github.com/wudahua/MCP_CREO_MechDog/pull/6) 回填。 |
| [DEV-028](archive/work-items/DEV-028.md) | P1 | 已完成 | 未排期 | 2026-10-16 Creo 9 编译与安装闭环：统一 BUG-033、DEV-019～022；14 项新增定向回归、260 项完整单元/语言守卫、本机 Creo 12.4 SDK 构建、显式环境真实 x64 编译运行及七个原生作业全部保存重载通过。[本批证据](validation/DEV-028.md)明确桌面启动环境、普通宿主 -4、此前失败与未测范围；Creo 9 实机编译/运行时未验收，版本 0.3.1，一个本地提交，不推送/发布。 后续 [WorkBuddy](validation/DEV-028-WorkBuddy-review-20261016.md) 的部署/通用单孔/通孔+盲孔已测范围通过，底板专用入口参数受阻仍未覆盖；本次仅补录，不改公共接口。 |
| [BUG-033](archive/work-items/BUG-033.md) | P1 | 已完成 | 未排期 | 本机 SDK 生成 MECHDOG_HAS 探针，geometry/generic 两孔调用在两探针均存在时走原路径；常量表包含位置前移。缺失/部分/完整 SDK 夹具及 Creo 12.4 通用孔/底板孔的几何与保存重载通过，见 DEV-028；本机无 Creo 9 SDK，不外推实际旧版编译或运行时。 |
| [DEV-019](archive/work-items/DEV-019.md) | P2 | 已完成 | 未排期 | 构建失败只读日志尾部 128 KiB、最多 15 条 error 摘要；仅实际 C2065 的 PRO_ 标识符提示 SDK 版本方向。纯函数与 bridge 失败路径夹具通过，不改变 MCP stdout，见 DEV-028。 |
| [DEV-020](archive/work-items/DEV-020.md) | P2 | 已完成 | 未排期 | INSTALL 补微软官方 --includeRecommended 命令、静默缺组件症状及与显式环境/Python 占位一致的排错表；官方来源和文档检查通过，未运行 VS 安装器，见 DEV-028。 |
| [DEV-021](archive/work-items/DEV-021.md) | P2 | 已完成 | 未排期 | config.json + setup.ps1 -VcVars64Env 两层完整 INCLUDE/LIB/PATH，校验/回写/环境检查/前置自检与默认路径兼容；PowerShell/cmd 夹具及真实 x64 编译运行通过，受限机器完整安装未验证，见 DEV-028。 |
| [DEV-022](archive/work-items/DEV-022.md) | P2 | 已完成 | 未排期 | WindowsApps Python 在执行前提示 Microsoft Store placeholder 和 -Python；自动发现/显式路径夹具及真实 Python -CheckOnly 通过，真实商店交互未验证，见 DEV-028。 |
| [BUG-008](archive/work-items/BUG-008.md) | P0 | 已完成 | 未排期 | 2026-10-16 按本机 Creo 12.4 已验证范围关闭：246 项单元，断开/探针有界保护，同实现真实冷态自动归档/重建/单次启动，以及新 [WorkBuddy](validation/BUG-008-WorkBuddy-reboot-retest-result-2026-10-16.md) 单次/重叠 retry、120 mm³ 建模/保存重载和 unknown 保护通过；见[关闭复核](validation/BUG-008-closure-2026-10-16.md)。WorkBuddy 冷态/异常环境和历史完整故障链仍未验证；未知任务不解锁，BUG-001/005/011 保留，未推送或发布。 |
| [BUG-009](archive/work-items/BUG-009.md) | P0 | 已完成 | 未排期 | 模型锁内收尾、释放后发布终态；busy 保留协议错误并补占用/重试诊断。210 项开发检查及本机 Creo 12.4 [WorkBuddy 验收](validation/BUG-009-WorkBuddy-acceptance-20261015.md)已测范围通过；报告 33 个作业只读核对一致，协议疑点及即时性边界已[复核](validation/BUG-009.md#2026-10-15-验收复核与关闭)。真实挂死/失联恢复及其他宿主范围不外推，服务仍 0.3.1，未另发布。 |
| [BUG-002](archive/work-items/BUG-002.md) | P1 | 已完成 | 0.2.6 | Windows 共享读取、单步原子替换、有界重试及自有临时文件清理；90 项单元、4,000 次压力写入与 Creo 12.4 并发/MCP 验收通过；原外部复测安排已随 DEV-018 取消。[本次证据](validation/BUG-002.md) |
| [BUG-006](archive/work-items/BUG-006.md) | P1 | 已完成 | 0.3.0 | 修复提交 `ccc7366`：axis_pattern 兼容 datum_feature 轴标签，补齐逐工具引用契约与可操作错误；9 项新回归、158 项检查、stdio schema 与全新安装通过。用户 N1 确认后，本轮报告 P0-1 再次记录别名归一化通过及 by_tool 15 工具；仍无完整任务/模型 ID 清单，其他包装差异归 FEAT-008。开发者 timeout 保留；见 [证据](validation/BUG-006.md)、[引用说明](REFERENCE_SYNTAX.md) 与 [复测步骤](validation/BUG-006-WorkBuddy-test.md) |
| [BUG-007](archive/work-items/BUG-007.md) | P0 | 已完成 | 未排期 | 本环境核心验收通过：标签引用两/三截面straight/smooth、已有底座追加、计划入口、几何/原生参数/保存重载/revision/回滚及后续通道；[最终WorkBuddy报告](validation/BUG-007-WorkBuddy-acceptance-2026-10-14.md)。整数公开引用失败单列BUG-028，开发者stdio整数成功证据保留；Creo10/并发/外部模态/策略未测，不外推 |
| [BUG-022](archive/work-items/BUG-022.md) | P1 | 已完成 | 未排期 | 本机 Creo 12.4 边参考定位修复及 [WorkBuddy 四场景](validation/BUG-022-WorkBuddy-retest-20261015.md)通过，0.3.1 报告补真实去料正例；用户取消 Creo 10 独立验收门槛后按本机已测范围关闭。原报告来源、根因未确认及未测事实保留，收到新反馈再沿用本 ID 跟进。 |
| [FEAT-019](archive/work-items/FEAT-019.md) | P1 | 已完成 | 0.2.6 | 用户接受 WorkBuddy / Creo 12.4 最终 MCP 验收：自动启动与真实 Toolkit 就绪、新建/草图/拉伸/尺寸驱动/倒角、保存重载通过；Codex MCP 只读复核 6 个成功修改任务与 revision=6 / volume=9980 mm³；121 项 Windows 单元/语言检查通过；Creo 10 及真实多客户端并发/退出后重连未测，Codex 冷启动失败单列 BUG-005；见 [证据](validation/FEAT-019.md) |
| [DEV-001](archive/work-items/DEV-001.md) | P1 | 已完成 | 0.2.6 | 开发入口、台账、模板、语言基线与守卫、Windows CI 配置、源码分发同步；[本批验收](validation/DEV-001.md) |
| DEV-010 | P2 | 已完成 | 0.2.6 | 根 AGENTS.md 与[开发入口](DEVELOPMENT.md#workbuddy-测试约定)统一 WorkBuddy 最终 MCP 黑盒测试约定，不查看源码、不运行本地源码测试；2026-10-13 Windows 文档引用与约定一致性检查通过，未执行 WorkBuddy 测试 |
| [DEV-011](archive/work-items/DEV-011.md) | P1 | 已完成 | 0.2.6 | 合并近两日三个开发分支至 main；121 项单元/语言守卫、SDK 构建、协议、解压与九种子 ZIP 安装通过；v0.2.6 预发布，源码/种子附件及 SHA256；本轮 Toolkit 超时、Creo 10 未测、BUG-005 保留，见 [发布证据](validation/RELEASE-0.2.6.md) |
| [DEV-012](archive/work-items/DEV-012.md) | P2 | 已完成 | 0.2.6 文档补充 | 根据用户确认与已有 Creo 12.4 实机证据，统一 Creo 10 / Creo 12 可用性说明并补充 12.4 安装示例；文档链接与范围一致性检查通过，GitHub Release 正文已修改并回读核对；历史测试日期、未测分支、BUG-005、标签及附件保持原样；本次未执行新实机测试，见 [记录](archive/work-items/DEV-012.md) |
| [DEV-013](archive/work-items/DEV-013.md) | P1 | 已完成 | 0.3.0 | PR #3 普通合并保留历史，v0.3.0 Pre-release 已公开；本地/全新安装各 158 项及 Windows CI 通过，82 工具/九种子、四份附件回下载与摘要、公开更新发现通过；FEAT-020 未测场景、DEV-002 后续批次及 BUG-005 保留；见 [发布证据](validation/RELEASE-0.3.0.md) |
| [DEV-014](archive/work-items/DEV-014.md) | P2 | 已完成 | 0.3.0 文档补录 | 原报告归档与原件 SHA256 一致，补录统计/覆盖边界并映射固定 ID，P0 三项建立独立卡；BUG-006/FEAT-020 同步本轮证据与未测范围。文档链接、ID/来源映射、表格和 diff 检查通过，见 [检查记录](validation/DEV-014.json)；仅文档整理，未修复缺陷或新做建模测试 |
| [DEV-016](archive/work-items/DEV-016.md) | P2 | 已完成 | 未排期 | 2026-10-15 精简主台账并归档原有 10 项完成记录，合并三项重复登记；原有 62 个 ID 的状态、优先级与目标版本保留，文档完整性及链接检查通过。 |
| [DEV-017](archive/work-items/DEV-017.md) | P2 | 已完成 | 未排期 | 原样归档0.3.1全量报告，17个问题及部署建议完成去重映射；新增4项待核实缺陷与4项能力建议，同步复验和覆盖边界。报告字节/哈希、ID保留、映射与本次引用检查通过，见[文档证据](validation/DEV-017.json)；DEV-002同期链接单独记录，未修复程序或新增建模测试。 |
| [DEV-018](archive/work-items/DEV-018.md) | P2 | 已完成 | 未排期 | 按用户要求取消全项目 Creo 10 独立复测、双版本验收及正式基线门槛，同步当前规则、台账和任务卡；DEV-002 第二批按开发与 WorkBuddy 已测范围完成，BUG-022 按本机证据归档。历史报告与未测事实保留，收到朋友新反馈再跟进；[文档检查](validation/DEV-018.json)通过，无新程序或实机测试。 |
| DEV-023 | P2 | 已完成 | 流程规范（不升版） | 2026-10-16 按用户要求，将每次合入 main 必须发布对应版本 GitHub Release 写入[根级规范](../AGENTS.md#提交合入-main-与-release项目全局)、[开发入口](DEVELOPMENT.md)与[发布规则](development/RELEASING.md#合入-main-必须同步发布)，同步 PR 模板；覆盖文档/配置变更，要求版本、主干提交、标签及附件一致，发布未完成则交付未完成。Windows 下 9 项规则检查、13 个本地文档链接及定向 git diff --check 通过；仅文档变更，版本仍为 0.3.1，未执行合并、实际发布或原生测试。 |
| [DEV-024](archive/work-items/DEV-024.md) | P2 | 已完成 | 未排期 | 2026-10-16 阅读并原样归档下载目录4份Markdown，41个编号问题及构建线索去重映射；新增14项待核实缺陷BUG-034～047、2项能力候选FEAT-029～030，同步已有工作卡及证据边界。[文档检查](validation/DEV-024.json)核对原件/哈希、ID、来源、链接与表格；保留同期BUG-008外部更新，仅同步文档，未复现、修复或执行新建模测试。 |
| [BUG-038](archive/work-items/BUG-038.md) | P2 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 B](validation/FEEDBACK-0.3.2.md) 的 Creo 9.0.0.0 实测（`true` 存为 `BOOLEAN(53)=True`，0.3.0 为 REAL(52)=1）转已完成：本仓库无对应修复提交可核实，未在本机复验布尔映射与保存重载；本机复现失败须重开本 ID。 |
| [BUG-042](archive/work-items/BUG-042.md) | P1 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 A](validation/FEEDBACK-0.3.2.md) P1（100×100×10 底块 + 2 个互不相邻矩形一次 add，体积 103 000 逐项吻合，job `7fee41d0c5604db2b80b06497c30fb11`）转已完成：本仓库无对应修复提交可核实，未在本机复验多区域增料；本机复现失败须重开本 ID。 |
| [BUG-043](archive/work-items/BUG-043.md) | P1 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 A](validation/FEEDBACK-0.3.2.md) P2（面贴合 add 成功并入同一实体 `bodies:1`、体积 +1 000，job `194f59d6ff9e40559d1aa9d1f82313e9`）转已完成：本仓库无对应修复提交可核实，未在本机复验共面合并；本机复现失败须重开本 ID。 |
| [BUG-044](archive/work-items/BUG-044.md) | P2 | 已完成 | 未排期 | 2026-10-16 按用户决定采信 [0.3.2 报告 A](validation/FEEDBACK-0.3.2.md) P4（闭合 `polyline` 截面拉伸成功、体积 +1 000）转已完成：开放链不可作实体截面属预期限制；本仓库无对应修复提交可核实，未在本机复验 polyline 截面；本机复现失败须重开本 ID。 |
| [DEV-026](archive/work-items/DEV-026.md) | P2 | 已完成 | 未排期 | 2026-10-16 归档并映射下载目录 3 份 0.3.2 报告（A/B/C 与原件逐字节一致），新增 DEV-027、BUG-048、FEAT-031；按用户决定把 BUG-038/042/043/044 转入本归档并标注外部证据边界；Creo 9 与 Toolkit 9 纳入文档支持范围。[文档检查](validation/DEV-026.json)核对原件/哈希、编号覆盖、ID 与链接；仅同步文档，未复现、修复或执行新建模测试。 |


> 2026-10 历史来源索引与早期进展映射已归档至 [完成档案历史记录](archive/BACKLOG_COMPLETED_HISTORY_2026.md)。

## 2026-11-07：DEV-073 归档与历史进展

本节仅为日期档案，不是当前任务入口。以下进展保留原日期与当时结论；部分“已发布”声明在本地集成快照中写早，交付事实以对应发布核对为准。当前状态只看 [BACKLOG](BACKLOG.md)。本轮纯文档复核，未重新运行历史测试。

### 本轮完成项

| ID | 优先级 | 状态 | 目标版本 | 完成摘要与证据 |
| --- | --- | --- | --- | --- |
| [BUG-111](work-items/BUG-111.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.6（已发布） | 选集语义和几何重合/交叠已定因；诊断与文案修正已发布；历史范围与证据见工作卡。 |
| DEV-055 | P2 | 已完成（2026-11-07 复核归档） | 未排期 | BACKLOG 明示 2026-11-02 已完成；四头文件已加入并在本机 SDK 核对；无独立卡；历史范围与证据见工作卡。 |
| [BUG-077](work-items/BUG-077.md) | P0 | 已完成（2026-11-07 复核归档） | 0.4.7 | 注册表治理及迁移/收养主线已交付，外部原环境已验证；健康会话 accept 两动作各 3/3；历史范围与证据见工作卡。 |
| [DEV-060](archive/work-items/DEV-060.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.2（已发布） | 归档/对账任务随 0.11.2 发布；BUG 子卡余项不属 DEV-060；历史范围与证据见工作卡。 |
| [DEV-062](archive/work-items/DEV-062.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.3（已发布） | 归档/登记任务随 0.11.3 发布；BUG/FEAT 子卡余项另列；历史范围与证据见工作卡。 |
| [BUG-104](archive/work-items/BUG-104.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.3（已发布） | 0.17.3 实机 15/15 完成补基线、拒绝及 adopted_live；旧检查点样本和失败注入属补证；历史范围与证据见工作卡。 |
| [FEAT-056](work-items/FEAT-056.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.3（已发布） | 0.17.3 随机与标签色板实机成功，核心能力完成；80 组件夹具归 FEAT-052；历史范围与证据见工作卡。 |
| [BUG-112](archive/work-items/BUG-112.md) | P1 | 已完成（2026-11-07 复核归档） | 0.15.0+ | ProQuiltInit 返回码修复与面积来源保护已交付；偏置计量实机范围由 FEAT-039 承接；历史范围与证据见工作卡。 |
| [DEV-064](archive/work-items/DEV-064.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.4（已发布） | R12 批已随 0.11.4 发布、附件核验；原件缺失属各子卡；历史范围与证据见工作卡。 |
| [BUG-096](archive/work-items/BUG-096.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.1 | 新零件/装配失败清理 S1–S4 实机断言通过；历史范围与证据见工作卡。 |
| [BUG-097](archive/work-items/BUG-097.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.1 | L1/L2 斜面草图修复已于 0.11.1 本机实机通过；历史范围与证据见工作卡。 |
| [BUG-099](archive/work-items/BUG-099.md) | P1 | 已完成（2026-11-07 复核归档） | 0.11.1 | 失败 worker 含未提交代码，本树源码不可复现，源码归因已定；历史范围与证据见工作卡。 |
| [BUG-100](archive/work-items/BUG-100.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.1 | 背靠背/并发 busy 与预约释放 0.11.1 实机复验通过；历史范围与证据见工作卡。 |
| [BUG-092](archive/work-items/BUG-092.md) | P2 | 已完成（2026-11-07 复核归档） | 0.10.1 | 驱动退出后 server.py 残留 0，实机尾项已收口；历史范围与证据见工作卡。 |
| [BUG-093](archive/work-items/BUG-093.md) | P2 | 已完成（2026-11-07 复核归档） | 0.10.1 | 五非法例及恢复编辑实机通过，体积同源证据补齐；历史范围与证据见工作卡。 |
| [BUG-089](archive/work-items/BUG-089.md) | P1 | 已完成（2026-11-07 复核归档） | 0.8.2 | 版本/摘要修复、防复发闸门与远端正式附件核对已完成；历史范围与证据见工作卡。 |
| [BUG-087](archive/work-items/BUG-087.md) | P1 | 已完成（2026-11-07 复核归档） | 0.7.2 | 重复第二参照修复 0.7.2 已发布并六例实机通过；后续 T06 属 BUG-064 顺序调查；历史范围与证据见工作卡。 |
| [BUG-086](archive/work-items/BUG-086.md) | P1 | 已完成（2026-11-07 复核归档） | 0.7.2 | PS 5.1 stderr 判断修复、回归与真实新目录安装验证通过；历史范围与证据见工作卡。 |
| [FEAT-034](archive/work-items/FEAT-034.md) | P1 | 已完成（2026-11-07 复核归档） | 0.8.0/0.8.3/0.10.0 | BUG-093 后续五非法例及恢复编辑实机通过，原卡首页滞后；历史范围与证据见工作卡。 |
| [DEV-061](archive/work-items/DEV-061.md) | P2 | 已完成（2026-11-07 复核归档） | 0.11.2 | 种子包仓库摘要闸门已随 0.11.2 交付；远端附件人工核验属于发布流程；历史范围与证据见工作卡。 |
| [DEV-050](archive/work-items/DEV-050.md) | P2 | 已完成（2026-11-07 复核归档） | 0.7.2 | 默认 900 秒配置已实现，后续多版 dev_check 全量记录已覆盖 T08 目标；历史范围与证据见工作卡。 |
| [DEV-073](archive/work-items/DEV-073.md) | P2 | 已完成（独立本地文档交付，未合 main） | 未排期 | BUG 分类复核与入口精简、历史字节及链接/状态检查、独立审查完成；未做产品/实机验证，本批仅本地提交。 |

### 存量无独立工作卡的登记

这些 ID 早于工作卡规范，保留原登记和证据；本批按用户要求仅新增 DEV-073，不批量补卡。当前剩余仍在 BACKLOG，一旦实施可在既有相关卡中接续。

<a id="legacy-dev-055"></a>

**DEV-055（原登记）**：`tools/generate_constants.py` 的 HEADERS 已包含 `Probbl.h`、`ProTrim.h`、`ProStdSection.h`、`ProMerge.h`（轮1 `efb0676` 已加入），供后续三曲面操作探测使用；2026-11-02 复核四头文件在本机 Creo 12.4.0.0 SDK `protoolkit/includes` 均存在。

<a id="legacy-bug-003"></a>

**BUG-003（原登记）**：检查倾斜草图的尺寸是否正确：用 30° 矩形拉伸 4 mm，核对体积是否为 800 mm³。还要测试尺寸编辑、保存后重新打开，以及失败时能否恢复修改前的模型。 [0.5.2反馈映射](validation/feedback-0.5.2-2026-10-26/MAPPING.md#r3-12)：T05以倾斜10×20×4=800独立夹具作受影响对照，不关闭本项全部历史范围。

<a id="legacy-bug-004"></a>

**BUG-004（原登记）**：在实验环境检查 Creo 12 的两截面种子。先核对 Blend 引用、对象句柄和种子文件身份，再对比直线、平滑及三截面情况。完成要求包括几何、尺寸编辑和保存后重新打开均正确。

<a id="legacy-bug-015"></a>

**BUG-015（原登记）**：t30_probe 中，对 body id=52 做 translation=[0,0,15]，特征创建后保存失败，干净模型的对照测试却成功。用查询得到的真实 body ID，分别测试 group、pattern、shell 与 transform 的组合，查清保存阶段的问题。成功时体积不变、位置正确且能重载；失败时保留保存点和 revision，并检查模型是否仍可用。返回字段的含义另由 BUG-012 处理。

<a id="legacy-bug-011"></a>

**BUG-011（原登记）**：通道异常时，状态查询有时给空错误或仍显示旧 ready。已有会话首次查询还出现 building_worker/connected=false，跨日出现 checking 不结束，建模返回 connect=-4。需要说明结果来自实时检查还是旧快照，并显示验证时间和是否过期；查询、提交都应在规定时间内返回明确原因。TimeoutExpired/launch_reserved 的新反馈尚未复测，关联 FEAT-001；异常通道恢复与未知任务保护按现行恢复契约处理。

<a id="legacy-bug-012"></a>

**BUG-012（原登记）**：transform 失败后，几何和 revision 没变，模型却被标为 failed；0.3.1 还有成功作业返回 rollback_succeeded=false，履带报告也出现同样误读。0.3.5/Creo 10 实机再现：新建零件失败（自交轮廓）时 inspection=null、rollback_succeeded=false 并残留 failed/revision 0 的登记与 .prt.1——新件无检查点可回滚是事实，但 false 易被误读为"回滚失败"，反馈建议改 null/not_applicable；另守卫触发时作业级 toolkit_code=-1 属异常路径汇总码（disconnect_code=0、通道健康），建议与真实 Toolkit 故障区分。需要分别说明回滚未尝试、成功、失败和无法确认时的含义，以及模型还能否使用，并检查保存点和旧字段兼容性。false 本身不能证明模型损坏，unknown_outcome 保护也不能直接清除。关联 FEAT-018。

<a id="legacy-bug-016"></a>

**BUG-016（原登记）**：solidify(cut) 用 z=30、positive 侧的基准面裁剪 z=20..40 的实体后，体积和 bbox 未变，却显示特征成功。先查清 side、pull_direction 和引用是否适用，再对比两侧裁剪并检查重载。应区分允许不改材料的操作、无效输入和真正切除，不能把所有零变化都判失败。

<a id="legacy-bug-018"></a>

**BUG-018（原登记）**：旧报告中 export/dump_tree/update_sketch_geometry 的结果重复；0.3.1 和 0.3.2 的失败计划又只返回 null 或空 operations。每个请求应对应一条带序号的结果，说明已执行、已回滚、失败、未执行或结果未知，并带上文件、特征和参数。0.3.5 钣金回归中 5 次失败计划仍均返回空 operations 数组，调用方无法知道哪些已成功、只能整批重发。核对成功及失败时的数量、顺序和失败位置；operation_outcomes 的接口建议仍待评估，不能据此自动重跑后半段。关联 FEAT-006。 [0.5.2反馈R1 §4.4](validation/feedback-0.5.2-2026-10-26/MAPPING.md#r1-12)续报重复；T02按[DEV-047接口基线](archive/work-items/DEV-047.md#interface-baseline)固定零基index、execution_status/effect_status及每输入一结果，离线实现完成（[T02记录](archive/development/DEV047-T02-ACCEPTANCE-2026-10-26.md)），实机与集成由T13收口。

<a id="legacy-bug-010"></a>

**BUG-010（原登记）**：旧报告中 drawing_view_update(scale=2) 失败，但 0.3.1 已成功把 v_front 从 1 放大到 2。还要查清两次测试的差异，测试位置更新、图纸保存重载和 revision；失败时应保留原图。  本次只调整为剩余验收，不认定位置更新和保存重载已通过。

<a id="legacy-feat-002"></a>

**FEAT-002（原登记）**：遇到 DLL 提示等需要人工处理的情况时，说明正在等什么。测试等待超时后，任务上下文是否保留、相关模块能否清理。

<a id="legacy-feat-003"></a>

**FEAT-003（原登记）**：支持并测试带单位的关系式，例如 `8[mm]`。确认它能真实驱动尺寸、带动相关参数变化，并保留用户对单位的检查设置。

<a id="legacy-feat-005"></a>

**FEAT-005（原登记）**：revision 冲突时，返回 model_id、current_revision 和 expected_revision，让调用者看到哪个版本不一致。继续拒绝过期请求，拒绝时不创建 job。 **2026-11-07**：`generic_bridge` 过期 revision 拒绝文本改为 `Stale revision: model_id=… current_revision=… expected_revision=…; no job was created`；`tests/test_registry_io.py` 精确断言三字段。纯 Python、无原生依赖。

<a id="legacy-feat-011"></a>

**FEAT-011（原登记）**：增加复合轨迹、可变截面和螺旋扫掠，分别明确范围并测试。

<a id="legacy-feat-013"></a>

**FEAT-013（原登记）**：增加剖视、局部放大、装配图和 BOM（物料清单），逐项检查模型变化后图纸能否同步更新。

<a id="legacy-feat-015"></a>

**FEAT-015（原登记）**：评估模具、NC 加工和仿真能力，先选一个最小场景做完整流程，暂不承诺支持全部模块。

<a id="legacy-feat-016"></a>

**FEAT-016（原登记）**：增加翼型凸度和 NACA 四位数系列，检查能否通过原生参数编辑，并验证实际几何。

<a id="legacy-feat-017"></a>

**FEAT-017（原登记）**：分别复现并测试布尔、曲面和拔模中尚未测过的用法，再决定扩大哪些支持范围。

<a id="legacy-feat-021"></a>

**FEAT-021（原登记）**：设计受控取消任务，先说明 queued、running、unknown_outcome 各能否取消，再检查执行器和模型状态。不能安全中断时说明原因。取消后要检查最终状态、保存点、revision、锁和下一次任务是否正常；不能把杀 worker 或清 pending_job 当作取消成功。与未知结果恢复分别验收，任务状态名称不表示当前已有排队能力。

<a id="legacy-feat-024"></a>

**FEAT-024（原登记）**：lookup_constants 没找到结果时，说明没有匹配，并提示可用前缀。测试不存在的前缀、空条件、合法前缀及旧返回规则；保留正常命中的行为。当前按体验改进处理，不直接把空字典认定为缺陷。

<a id="legacy-feat-025"></a>

**FEAT-025（原登记）**：评估 creo_loft 在回调未就绪时，能否用 2～6 截面种子完成部分操作。先说明支持哪些截面和模式、怎样保留模型身份，再检查已有特征、编辑、revision、保存重载和失败恢复。种子能新建零件，不代表能追加到已有零件；不自动加载 DLL 或改变策略，也不预先承诺实现成本低。

<a id="legacy-feat-026"></a>

**FEAT-026（原登记）**：提供 create_feature_tree 能运行的最小 dict 示例，说明 dump XML 能否转换或导入。先让示例建模、参数、几何和重载通过，非法树能指出问题元素，再评估导出后重新导入。无效示例失败不能证明工具不可用。

<a id="legacy-feat-027"></a>

**FEAT-027（原登记）**：说明删除实体后是否保留 label，以及何时可以安全释放或重新绑定。测试创建、删除、同名重用和旧引用、历史作业、revision 的关系，防止旧别名误指新对象。先说明现有规则，再评估可选接口，不默认允许覆盖。 [0.5.2反馈R3 §6.3](validation/feedback-0.5.2-2026-10-26/MAPPING.md#r3-20)归T08/0.7.0子项；[共享基线](archive/work-items/DEV-047.md#interface-baseline)固定删除墓碑、抑制保留身份，禁止旧别名重新绑定。T08 已实现墓碑登记与旧标签新建/引用拒绝（专项与回归见[记录](archive/development/DEV047-T08-ACCEPTANCE-2026-10-26.md)），[T13](archive/development/DEV047-T13-ACCEPTANCE-2026-10-26.md) 在 Creo 12.4 实机验证删除、墓碑登记与删除后用旧标签建新草图被拒。剩余：显式释放/重绑定接口与跨版本历史作业核对，仍待规划，不默认允许覆盖。

<a id="legacy-feat-028"></a>

**FEAT-028（原登记）**：create_plate为一次性产物，未注册为可继续编辑的模型；[0.4.7黑盒](validation/WORKBUDDY-0.4.7-2026-10-21.md)再次确认1000mm³成功但无model_id，属既有边界。评估是否返回 one_shot/registered 或支持可选注册。若增加后续编辑，须检查列表和 inspect 能找到模型、revision 正确、编辑和保存重载通过，失败后可恢复。计数问题仍由 BUG-014 处理。

<a id="legacy-feat-038"></a>

**FEAT-038（原登记）**：提供不建立 Toolkit 连接的安装自检路径：校验部署产物与配置一致性（常量表、执行器与源码指纹、种子哈希与清单、protk/loader 注册文件），让按约束停止 Toolkit 连接的受限环境也能确认安装正确性，不必冒卡死风险连 Creo。先确定自检覆盖哪些项、怎样判定"一致"，以及自检通过与实机就绪的关系（自检通过不等于通道可用）。来源见[Creo 10 反馈](validation/FEEDBACK-0.3.5-CREO10-2026-10-18.md)，关联 FEAT-022。

<a id="legacy-bug-020"></a>

**BUG-020（原登记）**：STEP 导出会留下 *_out.log.N。需要说明哪些文件是交付产物、哪些是诊断附件，只清理本作业生成的副产物。检查 STEP 仍有效、用户文件未受影响。文件清理由开发者检查，MCP 黑盒只验证返回的文件说明。

**2026-11-17 离线补录（BUG-020）**：新增 `creo_mechdog.export_artifacts`，在作业终结时只扫描本作业 `output` 目录：名称含 `_out.log` 的 Creo 诊断摘录移动到 `output/diagnostics/`，作业结果新增 `export_artifacts`、`export_diagnostics` 与 `export_diagnostics_note`；`.stp/.step/.igs/.iges/.stl` 与调用方其它文件不移动、不删除。非导出计划完全不动文件。4 项单测通过。真实 Creo STEP/IGES 导出与用户文件归属仍待实机复测。

**2026-11-17 实机通过（BUG-020，本机 Creo 12.4.0.0）**：30×20×10 方块执行 `export(step)`，job `defe4eb0b...` `succeeded`；`.stp` 8622 字节、头部 `ISO-10303-21`；`b020step_880934__out.log.1`（4401 字节）已移动到 `output/diagnostics/`，`export_artifacts=["output/b020step_880934.stp"]`、`export_diagnostics=["output/diagnostics/b020step_880934__out.log.1"]`，`saved_file_reloaded_and_verified=true`；`preview.jpg` 等其它文件未被移动。证据 `build/live_bug020/20261117T100224_defe4eb0/report.json`（SHA256 `c5dae447f4658c44cf54c9effbbde199a3382a1767ccd647d1002f01eca4568e`）。STEP/IGES 与用户文件归属在真实导出上闭环。

<a id="legacy-dev-003"></a>

**DEV-003（原登记）**：整理 C++ 的执行上下文、模块接口和资源由谁创建、释放，再用受影响的 SDK 构建并运行原生测试。

<a id="legacy-dev-004"></a>

**DEV-004（原登记）**：在 DEV-003 完成后，让各模块可以独立编译，并整理原生测试目录。检查构建缓存、安装、保存重载和失败回滚。

<a id="legacy-dev-005"></a>

**DEV-005（原登记）**：按工具和参数用法记录本机哪些测过、哪些没测，并注明真实环境，同步安装和能力说明。其他环境收到具体反馈再补；不要求双版本验收，也不能拿“82 工具测过”的汇总代替每种用法的兼容性测试。

<a id="legacy-dev-006"></a>

**DEV-006（原登记）**：补测会话、中断、真正并发、倾斜草图、两截面和 Creo 12 直接混合。0.3.1 还缺回调就绪的 loft、有效 UDF 和元素树、种子 directory/archive、JPEG 和图纸 PDF 的成功用例。记录完整输入、ID、几何、编辑、重载和回滚。Creo 9 的种子、筋和放样冒烟测试要有实际环境再做；新工具还须经真实 stdio MCP 测试空值、省略、非法字段、错误传递及 inspect→apply。模拟协议、原生和 WorkBuddy 结果分别记录，不能用输入被拒绝或工具总数代替成功用例，也不新增双版本发布门槛。

<a id="legacy-dev-007"></a>

**DEV-007（原登记）**：与 DEV-006 共用一份回归清单，在发布候选上执行，避免维护两套记录。包括 0.3.3 提出的 Creo 9 最小冒烟，以及新工具的空值、省略和非法字段 MCP 调用检查，逐环境标明已测、未测。外部编译通过或一个孔成功，不能代表全部运行时可用；本地 Python 直调也不能代替 MCP 协议测试。

<a id="legacy-dev-008"></a>

**DEV-008（原登记）**：查清旧清单第 5/6/7/9 项分别来自哪里、现在归哪个任务，补上对照关系。来源是 NEXT_STEPS_025 的“完善建议 5”。

<a id="legacy-dev-009"></a>

**DEV-009（原登记）**：按模块分别整理代码格式，每批完成后做回归检查，不自动增加历史问题的豁免项。2026-10-14 的历史统计为 67 条 Ruff 问题、36 个 Python 和 14 个 C++ 文件，见[历史记录](BACKLOG_COMPLETED.md)。


> 原台账日期进展（截至基点 `1cf9d3f`）已归档至 [完成档案历史记录](archive/BACKLOG_COMPLETED_HISTORY_2026.md#原台账日期进展截至基点-1cf9d3f)。

