# 统一开发台账

最新正式版 **0.50.0**（2026-11-28 MINOR，公开工具 112）。交付 [BUG-202](work-items/BUG-202.md)–[BUG-209](work-items/BUG-209.md)、[DEV-113](work-items/DEV-113.md)、[FEAT-094](work-items/FEAT-094.md) 与 [FEAT-095](work-items/FEAT-095.md)。完整近况见 [近期动态](#近期动态)，当前分类统计见 [使用与计数](#使用与计数)，更早记录见 [历史时间线](archive/BACKLOG_TIMELINE_2026.md)。

## 使用与计数

每个 ID 仅一行，保留优先级、当前状态、剩余工作和工作卡入口。目标版本统一表示剩余范围的安排，已交付子项版本/日期保留在工作卡；未分配的新工作不继承旧已发布目标。无独立卡的存量 ID 链接至完成档案的原登记，本轮不批量补卡。

诊断交付不等于根因修复；部分交付不关整卡；缺其他版本证据不自动判未修。观察项等自然新现场，不制造故障。已完成且无保留范围的行移入 [完成档案](BACKLOG_COMPLETED.md#已完成事项)。原进展/证据保留日期，不再回填第二份待办。小修复沿用卡与证据，复杂跨模块任务才另建完整计划。

当前唯一 ID **292**（BUG **155**、FEAT **92**、DEV **45**）；2026-11-07整理时移入完成档案23项（含DEV-073、DEV-075），该句为历史时点，归档项不计入当前行数。DEV-077起运行 `python tools/check_backlog_counts.py` 自检声明行、表行与分类表三方计数，不一致exit 1；该脚本只校验计数，不替代逐ID人工核对。

| 当前分类 | 唯一 ID 数 |
| --- | --- |
| 仍需修复 | 3 |
| 待复现/待核实 | 31 |
| 已有修复但待验收 | 103 |
| 观察中 | 3 |
| 其它 agent 处理范围 | 20 |
| 开发中 | 0 |
| 部分交付，剩余待验收 | 62 |
| 部分交付，剩余待规划 | 18 |
| 待规划 | 52 |

BUG 分类是互斥主分类；“其它 agent”行仍写明已完成子项与真实缺口，勿重复派工。

## 仍需修复

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-017](work-items/BUG-017.md) | P1 | 仍需修复 | 未排期 | 取得 Creo 9 同环境最小输入，对照界面 Profile Rib 与 MCP 的材料侧、特征状态和失败阶段，定位修复点或明确支持边界。 |
| [BUG-034](work-items/BUG-034.md) | P1 | 仍需修复 | 未排期 | 取得叶片种子的生产来源及匹配的 Creo 9 SDK 和许可，定位原生加载返回 -16 的原因，再决定是否重生种子。 |
| [BUG-131](work-items/BUG-131.md) | P1 | 仍需修复 | 未排期 | `revision==0` 新装配出口已在 Creo 10 实机验收（2026-11-27）；仍缺 Creo 10 原 23 组件装配与 `hom_1` 步骤以获取选择器阶段原生栈/轨迹并定位挂死根因。 |

<a id="输入或规则待核实"></a>

## 待复现/待核实

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-147](work-items/BUG-147.md) | P2 | 已有诊断待材质实测 | 未排期 | 已补 Toolkit API 与返回码提示；Creo 10 实机复现同一 `material_query_failed`（`material_assigned=true`、`mass:-1`），指定 `density_g_cm3=7.85` 得 31.4 g what-if 正确。剩：带具体材质的密度读取归因、多实体与单位换算。 |
| [FEAT-069](work-items/FEAT-069.md) | P2 | 部分交付，剩余待验收 | 0.27.0（区域适配层子项）；原生选区未排期 | 已交付 `region_selection` 契约：三套原始签名、frame `(1.5,v,-u)` 校验、无序/反向等价、重复/歧义/零命中拒绝，`region_index_hint` 不参与。0.26.0 复核真实 TXT 三签名解析与唯一匹配通过；新增 `ExtrudeOp.region` + 派生草图适配（准入前展开、实体原样复制、`region_adaptation` 回执，离线 24 项），源草图须为坐标草图且只支持简单闭环。原生选区、实机去料与 Creo 10 未验。 |
| [BUG-004](BACKLOG_COMPLETED.md#legacy-bug-004) | P1 | 待复现/待核实 | 未排期 | 核对对象句柄、种子身份、直线/平滑/三截面编辑和重载；依赖：需可用 Creo 12 会话与原始失败输入。 |
| [BUG-011](BACKLOG_COMPLETED.md#legacy-bug-011) | P1 | 待复现/待核实 | 未排期 | 取得状态查询与提交时间线，标明快照时间及实时性；依赖：需真实异常通道现场；禁止主动制造。 |
| [BUG-012](BACKLOG_COMPLETED.md#legacy-bug-012) | P1 | 待复现/待核实 | 未排期 | 区分未尝试/成功/失败/未知；核对新件无检查点和旧字段兼容；依赖：需失败样例与当前回执对照。 |
| [BUG-014](work-items/BUG-014.md) | P1 | 待复现/待核实 | 未排期 | counts=null 与后续查询有值的时点/来源差异及恢复失败路径仍待核对。 |
| [BUG-015](BACKLOG_COMPLETED.md#legacy-bug-015) | P2 | 待复现/待核实 | 未排期 | 以真实 body ID 做干净件/组合件保存重载对照，定位保存阶段；依赖：t30_probe 模型、原生返回与 Creo 会话。 |
| [BUG-016](BACKLOG_COMPLETED.md#legacy-bug-016) | P2 | 待复现/待核实 | 未排期 | 核对 side、工具面与切除语义，做双侧几何、体积及重载对照；依赖：原报告操作输入及 Creo 可用会话。 |
| [BUG-018](BACKLOG_COMPLETED.md#legacy-bug-018) | P2 | 待复现/待核实 | 未排期 | 逐输入结果契约已实施；历史 effect/status 矛盾需按当前返回核对，关联 T02/T13。 |
| [BUG-031](work-items/BUG-031.md) | P1 | 待复现/待核实 | 未排期 | 先建并查询唯一 x=45 平面，再与显式 ID/标签对照；依赖：需 Creo 几何对照。 |
| [BUG-035](work-items/BUG-035.md) | P1 | 待复现/待核实 | 未排期 | 补 shell+孔夹具，对照轴阵列与树依赖、材料体积；依赖：缺完整原模型/leader 历史与 Creo 实机。 |
| [BUG-037](work-items/BUG-037.md) | P1 | 待复现/待核实 | 未排期 | 测尺寸类型×引用数量及端点矩阵；依赖：缺完整草图请求与 Creo 9/12 对照。 |
| [BUG-039](work-items/BUG-039.md) | P2 | 待复现/待核实 | 未排期 | 与 extrude 对照原生 body ID、材料、体积、重载；依赖：曲面来源、厚度、侧及原 job/model。 |
| [BUG-041](work-items/BUG-041.md) | P2 | 待复现/待核实 | 未排期 | 先定普通约束非零 offset 契约，再加准入拒绝或显式转换，验证面距及保存值；依赖：原始约束输入/回读，或构造最小对照的 Creo 会话。 |
| [BUG-048](work-items/BUG-048.md) | P2 | 待复现/待核实 | 未排期 | 补等价特征序列并隔离镜像、顺序、变换和壳引用，取得原生诊断；依赖：原模型、引用、job；可用 Creo 会话。 |
| [BUG-049](work-items/BUG-049.md) | P1 | 待复现/待核实 | 未排期 | 原件取得后同件 gap/snapped 对照，确认多环支持边界；依赖：缺 gear10.json/sketch_entities.json。 |
| [BUG-052](work-items/BUG-052.md) | P2 | 待复现/待核实 | 未排期 | 以已知几何查询 Toolkit 返回语义，再设计兼容的 geometry_type 字段；依赖：平面/圆柱等原生夹具与 Creo 查询。 |
| [BUG-053](work-items/BUG-053.md) | P1 | 待复现/待核实 | 未排期 | 同一快照分段计时及调用计数后再选优化；依赖：缺大模型样本与阶段日志。 |
| [BUG-058](work-items/BUG-058.md) | P1 | 待复现/待核实 | 未排期 | 只在自然现场采集进程、窗口和通道时间线；依赖：需外部 Creo 9 无主窗口现场。 |
| [BUG-060](work-items/BUG-060.md) | P2 | 待复现/待核实 | 未排期 | 核对 schema/resolve 接受的引用类型，明确报错或扩展支持，验证重载；依赖：原始 S6 输入、固定面选择规则与 Creo 会话。 |
| [BUG-061](work-items/BUG-061.md) | P2 | 待复现/待核实 | 未排期 | 与 BUG-031 联查解析路径；明确接受或拒绝并给出 datum_plane 替代；依赖：用户契约决定与 Creo 几何对照。 |
| [BUG-063](work-items/BUG-063.md) | P1 | 待复现/待核实 | 未排期 | 取得外部轴引用形式/原模型并对照修复后 BUG-084；依赖：缺外部 Creo 10 原案。 |
| [BUG-065](work-items/BUG-065.md) | P2 | 待复现/待核实 | 未排期 | 保留 Creo 10 原案待复现；斜交与单平面回归依关联矩阵；依赖：外部原始模型与 Creo 10 环境。 |
| [BUG-066](work-items/BUG-066.md) | P2 | 待复现/待核实 | 未排期 | 取原 Part1/Part2、同作业请求及图像；实机逐图复核失真路径；依赖：原模型、preview.jpg、同作业 JSON。 |
| [BUG-075](work-items/BUG-075.md) | P2 | 待复现/待核实 | 未排期 | 下次自然出现时收集 worker 日志和时序，辨别探针异常/连接竞争；依赖：自然复发时原始探针日志。 |
| [BUG-078](work-items/BUG-078.md) | P1 | 待复现/待核实 | 未排期 | 偶发编辑 -1 未复现；三旧现场待选择 restore_baseline；依赖：现场日志/操作者。 |
| [BUG-081](work-items/BUG-081.md) | P1 | 待复现/待核实 | 未排期 | 自然现场验证 MCP 拒绝时序后决定 alive=None 规则；依赖：缺同型残留 worker/外部 Creo 9 现场。 |
| [BUG-085](work-items/BUG-085.md) | P1 | 待复现/待核实 | 未排期 | 自然事故时采集 nmsd 身份、worker 与源码指纹；依赖：缺原始时序和受控现场。 |
| [BUG-091](work-items/BUG-091.md) | P1 | 待复现/待核实 | 未排期 | 自然现场核对分层事实与外部时间线；依赖：缺真实断连/挂起现场。 |
| [BUG-106](work-items/BUG-106.md) | P2 | 部分交付（文案+裁定）；实机链路待验 | 0.27.0（离线裁定）；实机复测未排期 | 文案已修；2026-11-17 离线裁定不纳入 `adopt_session_copy`（一致性判定/身份改写/审计边界未冻结，现有两步文案已覆盖可恢复路径），反向断言保持 0 命中。只剩真实同名外部模型的 save/erase 两步链路实机复测。 |
| [BUG-109](work-items/BUG-109.md) | P1 | 待复现/待核实 | 未排期 | 自然现场取得子阶段时间线以定位阻塞；依赖：缺 Creo 9 真实停滞的 native.log/request.json。 |

## 已有修复但待验收

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-202](work-items/BUG-202.md) | P1 | 已有修复但待验收 | 0.50.0 | 面板锁未知 `model_id` 披露/活动持有者保护与退役、无 Creo `restore_baseline`/`accept_live` 提交前拒绝并保留状态已通过 Creo 10 实机；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [DEV-113](work-items/DEV-113.md) | P1 | 已有修复但待验收 | 0.50.0 | `test_startup_retry.py` 改用显式事件握手消除 `join(2)` 竞态，隔离 `2×60` 与并发 `3×120` 压测均为 0 失败；剩：托管 CI 同并发复测。 |
| [BUG-203](work-items/BUG-203.md) | P1 | 已有修复但待验收 | 0.50.0 | 分离公开 `weld_pairs` 与内部 `weld_plan`，40 弧等价夹具实机验证显式报错/仅 weld 拒绝/`snap_endpoints` `184.9802 mm³` 重载通过；剩：外部 `scripts/gear10.json`、Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-204](work-items/BUG-204.md) | P1 | 已有修复但待验收 | 0.50.0 | 定位冷启动 `not_loaded` 根因为 `protkdat` `delay_start true`；`startup`/`session` 补非阻塞 `callback_advisory`，`callback_status` 输出 `affected_operations`/`recovery_steps` 与 Creo 10 冷启动一致；剩：交互桌面手动启动回调后最小 `creo_loft` 创建、Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-205](work-items/BUG-205.md) | P1 | 已有修复但待验收 | 0.50.0 | Creo 10（release 42）`element_tree`（含 `accept_unverified_completion=true`）提交前拒绝并在 `creo_capabilities` compact 明确披露；剩：交互桌面启动回调后 `resident_panel` 100 mm² 曲面复验、Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-206](work-items/BUG-206.md) | P2 | 已有修复但待验收 | 0.50.0 | `creo_list_seeds` 输出精确 9 组合与 `5/straight` 缺失并标明 `new_part_only`，Creo 10 `5/straight` 拒绝与 `2/straight` 重载通过；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-207](work-items/BUG-207.md) | P1 | 已有修复但待验收 | 0.50.0 | 修正混合弧 `selection_reason`、补 `autodim→coordinates` 回退与 `PRO_2D_ELLIPSE` `coordinates` 标注/偏差快照，Creo 10 混合弧三路与偏置椭圆 `max_deviation=0.0` 重载通过；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-208](work-items/BUG-208.md) | P1 | 已有修复但待验收 | 0.50.0 | `boolean_bodies` 支持活动初始体 `-5778`（4625.0 mm³、1 实体、重载通过）与空 `-5778` 拒绝（`BOOLEAN_BODY_NOT_FOUND`）及正+正对照（12000.0 mm³）；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-209](work-items/BUG-209.md) | P2 | 已有修复但待验收 | 0.50.0 | `known_limitations` 披露相切/相交轮廓限制，共享边/点接触/自交三例提交前报错、合法嵌套 `1680.0 mm³` Creo 10 重载通过；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [FEAT-095](work-items/FEAT-095.md) | P2 | 已有修复但待验收 | 0.50.0 | 新增状态轮询 `detail="compact"`（实测缩减 90.7%–92.9% 至 1.2–1.9 KiB）及 20 操作计划体量量化；剩：WorkBuddy 黑盒与默认值变更兼容性评估。 |
| [BUG-198](work-items/BUG-198.md) | P1 | 已有修复但待验收 | 0.49.0 | 修复 Windows JSON 原子替换把缺失目标/瞬时 `stat` 锁误判为永久 WinError 5 及 `.tmp` 清理失败，`dev_check` 4592 单测通过；剩：真实索引器/杀软锁与 WorkBuddy 黑盒。 |
| [BUG-199](work-items/BUG-199.md) | P0 | 已有修复但待验收 | 0.49.0 | 补全 Job Object 实测探测/Explorer 脱离、`tid==0` 防护、`owner_liveness`、`cancel_job` PID/128、`confirm_panel_closed` 死所有者解锁及模态框日志，Creo 10 断连清锁通过；剩：`WinSta0\Default` 断连保活、Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-200](work-items/BUG-200.md) | P1 | 已有修复但待验收 | 0.49.0 | 移除 115 s 硬编码超时，落地可配/自适应 `utility_worker_timeout_seconds`（300–3600 s）及超时强杀证据，单测通过；剩：大模型实机加载与 WorkBuddy 黑盒。 |
| [BUG-201](work-items/BUG-201.md) | P2 | 已有修复但待验收 | 0.49.0 | 统一 `creo_capabilities` `direct_blend_callback.readiness` 口径、消歧 `startup_in_progress`、强制 UTF-8 stderr 及提示完善，单测与契约通过；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [FEAT-093](work-items/FEAT-093.md) | P1 | 已有修复但待验收 | 0.49.0 | 交付 `ExtrudeOp.depth2` 双向不等深拉伸、`datum_planes[].name` 及 `cut_scope` 边界说明，Creo 10 增/切与重载验收通过；剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-196](work-items/BUG-196.md) | P1 | 已有修复但待验收 | 0.48.1 | 0.48.0 交付 `creo_refresh_model(write_back_snapshot=True)` 无版本破坏只读快照回写与 `stale_fields`/`refresh_hint`，0.48.1 补修分拆 `inspection_ref` 快照 `surfaces[].area_mm2` 检出与装配 `merged_counts` 误报；Creo 10 退化快照实机与单测通过。剩：Creo 9/12.4、WorkBuddy 黑盒与 0.39.0 原模型复验。 |
| [BUG-197](work-items/BUG-197.md) | P2 | 已有修复但待验收 | 0.48.0 | 已交付 `bounding_box_status` `basis`/`query_code`、`compact_job` 巡检摘要、`creo_round`/`creo_chamfer` 参数示例与 `session_health` 连接/保存双子块拆分；Creo 10 实机与单测通过。剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-194](work-items/BUG-194.md) | P1 | 已有修复但待验收 | 0.47.0 | `auto` 求解器恢复将 `b_spline`/`arc`/`spline`/`ellipse` 路由到 `autodim`；失败回执补 `dimensioning='autodim'`/`geometry_tolerance_mm=<cap>` 自助提示；Creo 10 实机通过。剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-195](work-items/BUG-195.md) | P2 | 已有修复但待验收 | 0.47.0 | `bounding_box_status` 披露面细分内缩误差界；空件平面报错指向 `datum_plane`；边选择器歧义附 `adjacent_surfaces` 与新出口；Creo 10 实机通过。剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [FEAT-091](work-items/FEAT-091.md) | P3 | 已有修复但待验收 | 0.47.0 | `round` 增加 `expected_round_kind`/`expected_material_delta_sign` 期望断言；`sheetmetal_base_flange` 回执补 `envelope_mm`；Creo 10 实机通过。剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [FEAT-092](work-items/FEAT-092.md) | P3 | 已有修复但待验收 | 0.47.0 | 新增只读无锁工具 `creo_server_info`；`ExtrudeOp.region` 新增 `closed_chain` 封闭链选区；`closed_chain` Creo 10 实机与单测通过。剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [BUG-146](work-items/BUG-146.md) | P1 | 已有修复但待验收 | 未排期 | 0.35.6 已交付恢复通道交接修复，Creo 10 已验证重启后的基线恢复。核对 0.34.0 缺少 launched_by 的旧作业；worker_started=true 且缺少原生身份时仍保留保护。 |
| [BUG-148](work-items/BUG-148.md) | P1 | 已有修复但待验收 | 未排期 | 0.35.6 已交付多开放轮廓的拆分指引。逐轮廓拉伸后复验完整结果，并补 Creo 9/12 对照。 |
| [BUG-149](work-items/BUG-149.md) | P1 | 已有修复但待验收 | 未排期 | 0.35.7 已验证 Creo 10 的只读残留释放。补采真实客户端中途退出及通道占用时的释放时序；外部环境、Creo 9/12 与 WorkBuddy 待验。 |
| [BUG-132](work-items/BUG-132.md) | P1 | 已有修复但待验收 | 未排期 | 取得 Arm7 原模型后，优先在 Creo 10 核对两个半圆柱面的 ID、同轴约束及保存重载；Creo 12.4 等价夹具已通过。 |
| [BUG-192](work-items/BUG-192.md) | P1 | 已有修复但待验收 | 0.46.0 | 修正 `draft` 基准面/实体面方向说明并新增 `material_effect`，Creo 10 实机 8/8 通过。剩：Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [FEAT-090](work-items/FEAT-090.md) | P1 | 已有修复但待验收 | 0.46.0 | 暴露草图端点焊接参数并支持 `arc-arc` 近容差共点吸附，Creo 10 实机 40 弧微间隙拉伸通过。剩：外部原件 gear10.json、Creo 9/12.4 与 WorkBuddy 黑盒。 |
| [DEV-102](work-items/DEV-102.md) | P2 | 已有修复但待验收 | 0.46.0 | `creo_capabilities` 新增 `registered_but_unavailable_operations` 并补全 `region.interior_point_yz_mm` 文档。剩：WorkBuddy 黑盒。 |
| [BUG-036](work-items/BUG-036.md) | P1 | 已有修复但待验收 | 0.44.1 | 本版交付平面配合位姿校验。本机 Creo 10 复现约束写入成功而位姿未更新，冲突请求明确拒绝并验证回滚。外部 Creo 9 原案、Creo 12.4 与 WorkBuddy 待验证。 |
| [BUG-187](work-items/BUG-187.md) | P0 | 已有修复但待验收 | 0.47.1 | 0.47.1 交付主基准面偏移默认法线对齐 `frames.XY/XZ/YZ`、`plane_frame` 回执与字典草图 `frame_mismatch` 告警，本机 Creo 10 三组对照（`5600.0 mm³`、默认 `y∈[-37,-30]`、`flip` 告警与 `v_axis` 覆盖、保存重载）通过。剩：Creo 9/12.4、WorkBuddy 黑盒。 |
| [BUG-188](work-items/BUG-188.md) | P0 | 已有修复但待验收 | 0.44.0 | `coordinates` 放行 `PRO_2D_CONSTR_CIRCLE` 并标记 `construction=true`，本机 Creo 10（2 构造圆+3 构造线、`1000.0 mm³`、保存重载）通过。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-189](work-items/BUG-189.md) | P2 | 已有修复但待验收 | 0.44.0 | `ValidationMCPServer.call_tool` 按 schema 拒绝未知工具参数并附拼写建议；单测与 `test_mcp.py --offline` 通过。剩：WorkBuddy 黑盒。 |
| [BUG-190](work-items/BUG-190.md) | P2 | 已有修复但待验收 | 0.44.0 | `creo_get_job` 失败作业顶层透传 `failed_operation_index`/`failed_stage`/`failure_phase`/`native_result_path`/`round_failure_summary`，原生 `round_failure` 文案指明 `operations[<i>]`；单测通过。剩：WorkBuddy 黑盒。 |
| [FEAT-088](work-items/FEAT-088.md) | P1 | 已有修复但待验收 | 0.44.0 | 装配新增 `placement:"packaged"`（保留变换、0 约束）并回读 `constraint_count`，本机 Creo 10 3 实例装配（`3000.0 mm³`、重心吻合、保存重载）通过。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [FEAT-089](work-items/FEAT-089.md) | P2 | 已有修复但待验收 | 0.44.0 | 本机 Creo 10 实测 `SheetmetalFlangeOp` 连续两段附着已有壁自由端并控制方向/材料侧（`7233.98 mm³`、保存重载），确认现有能力覆盖。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [FEAT-085](work-items/FEAT-085.md) | P2 | 已有修复但待验收 | 0.44.0 | 当前面过滤、唯一最近点选边与等距拒绝，Creo 10 薄板、圆盘、保存重载及回滚通过。原 Arm7 拓扑映射待验。 |
| [BUG-186](work-items/BUG-186.md) | P1 | 已有修复但待验收 | 0.44.0 | 截面伸展与厚度分别控制，四组合在 Creo 10 实测和保存重载通过。其它角度与报告方环境待验。 |
| [FEAT-084](work-items/FEAT-084.md) | P1 | 已有修复但待验收 | 0.44.0 | 独立组合法兰支持字典平面与首壁厚度方向，Arm2 钣金毛坯 X 宽 20 mm，保存重载和负例回滚通过。完整零件与外部环境待验。 |
| [BUG-183](work-items/BUG-183.md) | P1 | 已有修复但待验收 | 0.43.0 | 原生 `section_profile_summary` 计算 `solved_section_area_mm2` 并随草图/零切/成功切除回执发布，闭合 B 样条草图附 `b_spline_cut_risk`，`cut_volume_check` 支持 `blind`/`symmetric` 并回落至 `solved_section_area_mm2`；本机 Creo 10 实机 `100.0 mm²` / `299.9997 mm³` 通过并保存重载。剩：Creo 9/12、原 Arm7 工程、WorkBuddy 黑盒。 |
| [FEAT-082](work-items/FEAT-082.md) | P1 | 已有修复但待验收 | 0.43.0 | `JpegOptions` 新增 `right`/`left`/`back`/`bottom` 正交视图与 3×3 右手正交 `view_matrix`；本机 Creo 10 实机 3 mm YZ 薄板四视角渲染 `view_matrix_matches=true`，`right` 呈完整 60×40 轮廓。剩：Creo 9/12、装配多视角、WorkBuddy 黑盒。 |
| [BUG-184](work-items/BUG-184.md) | P2 | 已有修复但待验收 | 0.43.0 | 草图 `geometry_deviation` 补逐点 `point`/`requested_mm`/`actual_mm`/`delta_mm`，compact 超阈保留前 5 条 `displaced_sample`，明确 `geometry_tolerance_mm` 在 `autodim` 同样硬拒绝；单测与原生编译通过。剩：原 Arm7 `a7_s5` 实机复现、Creo 9/12、WorkBuddy 黑盒。 |
| [FEAT-083](work-items/FEAT-083.md) | P3 | 已有修复但待验收 | 0.43.0 | `ExtrudeOp.region` 新增曲线感知 `interior_point_yz_mm` 内点选区（支持圆弧与 B 样条，无需顶点对签名）；本机 Creo 10 实机 B 样条子区域切除精确 `800.0024 mm³` 并保存重载。剩：Creo 9/12、原 Arm7 工程、WorkBuddy 黑盒。 |
| [BUG-185](work-items/BUG-185.md) | P3 | 已有修复但待验收 | 0.43.0 | `creo_get_job` 参数 schema 标明 `section`/`cursor` 要求 `detail="full"`、`sections` 要求 `detail="compact"` 并补充报错指引；单测与离线 stdio 检查通过。剩：WorkBuddy 黑盒。 |
| [BUG-179](work-items/BUG-179.md) | P1 | 已有修复但待验收 | 0.42.0 | `ChamferOp` 新增 `propagate:"single"|"chain"`、倒角回执新增 `chamfered_edge_length_mm`/`created_surface_count`/`created_surface_area_mm2`、`chamfer_type` 补注说明；本机 Creo 10 实机 `single`(97.14 mm) vs `chain`(155.71 mm) 均通过并保存重载。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-180](work-items/BUG-180.md) | P1 | 已有修复但待验收 | 0.42.0 | 单/多边 `round`/`chamfer` 失败均返回 `round_failure.edge_diagnostics`（相邻面/二面角/端点邻边），`round` 回执新增有符号 `volume_delta_mm3` 与 `round_kind`；本机 Creo 10 实机凸/凹圆角与超限失败均通过。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [FEAT-080](work-items/FEAT-080.md) | P2 | 已有修复但待验收 | 0.42.0 | `ShellOp`/`creo_shell` 新增精确 `body_id` 单实体抽壳、`MirrorOp` 补替代指引、`creo_inspect_model` 分页新增 `total_count`/`page_count`；本机 Creo 10 实机两实体仅抽体 B（78752.0 mm³ 精确吻合）并保存重载。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-181](work-items/BUG-181.md) | P1 | 已有修复但待验收 | 0.42.0 | `ExtrudeOp.region` 新增交点分割与精确 Boehm B 样条节点插入及零命中 `closest_loop` 诊断；本机 Creo 10 实机含两相交三次 B 样条 YZ 草图子区域切除（300.0 mm³）通过并保存重载。剩：Creo 9/12、原 Arm7 完整工程、WorkBuddy 黑盒。 |
| [FEAT-081](work-items/FEAT-081.md) | P2 | 已有修复但待验收 | 0.42.0 | G2 圆角新增几何级 `g2_verification`（沿相切边界边求法向夹角与跨边界法曲率差）；本机 Creo 10 实机 R10 G2 圆角实测 `max_curvature_gap_inv_mm=0.0`、`verdict="pass"` 并保存重载。剩：Creo 9/12、非解析面 G2、WorkBuddy 黑盒。 |
| [BUG-182](work-items/BUG-182.md) | P1 | 已有修复但待验收 | 0.42.0 | 装配面/边选择器零命中每条候选新增 `suggested_reference`、报错直出最近候选、`assembly` 空间标注 `nearest_coordinate_space="component"` 与 `assembly_origin_mm`/`assembly_normal`；本机 Creo 10 实机验证通过。剩：Creo 9/12、全量 60 配合装配、WorkBuddy 黑盒。 |
| [BUG-176](work-items/BUG-176.md) | P1 | 已有修复但待验收 | 0.41.0 | Creo 10 三组用例已验。0.47.0 外部 Creo 9 在临时圆柱上复验整圆选择通过；仍缺发动机原件及接缝点、单点选弧的完整黑盒覆盖，Creo 12 待验。 |
| [FEAT-079](work-items/FEAT-079.md) | P1 | 已有修复但待验收 | 0.41.0 | 多引用 `round`/`chamfer` 失败时逐集探测定位 `failed_reference_index`/`failed_reference`/`round_failure` 并保持回滚；本机 Creo 10 实机精准定位索引 1 并完整回滚。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-177](work-items/BUG-177.md) | P2 | 已有修复但待验收 | 0.41.0 | 草图 `Arc.sweep_deg`（本机 Creo 10 实机 270° 优弧体积精确吻合）、`spline` 数值面积、`coordinates` 超差 `shifted_sample` 与 `XY`/`XZ`/`YZ` 基准面文档。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-178](work-items/BUG-178.md) | P2 | 已有修复但待验收 | 0.41.0 | `feature_state` 依赖展开 `include_dependencies=true` 与 `suggested_targets`、`component_changes` 1e-12 浮点噪声过滤、`creo_execute_plan` 空装配 `ToolError` 指引；本机 Creo 10 实机删除与装配插入均通过并保存重载。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-171](work-items/BUG-171.md) | P0 | 已有修复但待验收 | 0.40.0 | 恢复阶段超时写出结构化 `native_result.json`（`recovery_phase_timeout`）、消除 `restore_baseline` 重复二次 `inspection()`、恢复预算扩至 1800 s 并按 edges/features/surfaces 自适应、终态 `recovery_pending` 返回 `terminal_unconfirmed` 解锁指引；本机 Creo 10 实机 `restore_baseline` 一次完成（`INSPECT_SUMMARY=1`）并保存重载。剩：原始 53 特征 `carrier_v2`、Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-172](work-items/BUG-172.md) | P1 | 已有修复但待验收 | 0.40.0 | 消除草图/基准/拉伸流程 10+ 次冗余全量 `inspection()` 与逐半边 `fflush()` 刷盘，补 `INSPECT_PROGRESS`/`INSPECT_SUMMARY` 与遍历上限；本机 Creo 10 实机 B045 同等价 6 步作业全量快照由 15 次降至 3 次（9.1 s 完成）并保存重载。剩：原始 53 特征 `carrier_v2`、Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-173](work-items/BUG-173.md) | P1 | 已有修复但待验收 | 0.40.0 | 单轴倾斜三点基准面草图自动创建并复用正交辅助锚定平面（`SKETCH_ANCHOR_HELPER=1`），`coordinates` 求解失败同时报告 `ProSectionSolve` 与救援 `ProSectionAutodim` 返回码及 `section_references`；本机 Creo 10 实机 B045/B104 倾斜草图拉伸与切除精确匹配体积并保存重载。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-174](work-items/BUG-174.md) | P1 | 已有修复但待验收 | 0.40.0 | `dump_plan_operations` 保留显式 `chamfer_type`、盲孔切除新增 `cut_volume_check` 低去料告警、`spawn_detached_runner` 尝试 `CREATE_BREAKAWAY_FROM_JOB` 并披露 `runner_detached_from_job`；本机 Creo 10 实机内联 `d1_d2` 倒角与低去料告警通过并保存重载。剩：客户端退出脱离实测、Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-170](work-items/BUG-170.md) | P0 | 部分交付，剩余待验收 | 0.45.0 | 交付启动暂态诊断与共用截止时间。Creo 10 冷启动复现 `-4 → 0`，查找持续失败和探针超时通过对照。Creo 9 历史升级现场及 WorkBuddy 待验。 |
| [BUG-166](work-items/BUG-166.md) | P1 | 已有修复但待验收 | 0.39.0 | 跨会话 `restore_baseline`/`abandon_new` 解死锁、新增 `abandon_unknown_recovery`、单次 `budget_seconds` 与高边数自适应下限（6428 边 548 s）、`blocking_operation="recovery_pending"`；本机 Creo 10 实机 3/3 通过并保存重载。剩：原始 6428 边 M113 P05 模型、Creo 9/12、WorkBuddy 黑盒。 |
| [FEAT-076](work-items/FEAT-076.md) | P1 | 已有修复但待验收 | 0.39.0 | 边 `geometry_selector` 支持 `feature` 标签过滤、`creo_inspect_model` 新增 `near`/`max_distance_mm` 近邻查询与 `creo_round`/`creo_chamfer` 说明同步；本机 Creo 10 实机 `near` 定位 + 按特征边圆角精确去料并保存重载。剩：原始 6428 边件、Creo 9/12、WorkBuddy 黑盒。 |
| [FEAT-077](work-items/FEAT-077.md) | P2 | 已有修复但待验收 | 0.39.0 | 零件 JPEG 预览隐藏并恢复四项基准显示选项（不写 `config.pro`）；更新检查默认预算 5 s→15 s 且带 `advisory=true`；本机 Creo 10 实机零件预览/JPEG 导出隐藏与恢复全过。剩：Creo 9/12、WorkBuddy 黑盒。 |
| [BUG-169](work-items/BUG-169.md) | P1 | 已有修复但待验收 | 0.38.0 | `extrude` 等操作回执补齐 `feature_id`（全量+compact）；`linear_pattern` 双层拒绝非实体/零面 leader 与别名类型冲突并输出 `leader_kind`/`leader_surface_count`；本机 Creo 10 实机 4/4 + `test_linear_pattern` 3/3 通过并保存重载。剩：原案 B025 原始请求/模型快照、Creo 9/12 实机、WorkBuddy 黑盒。 |
| [FEAT-075](work-items/FEAT-075.md) | P1 | 已有修复但待验收 | 0.38.0 | `extrude mode="cut"` 开放单实体 `scope` 与 `through_all` 组合；本机 Creo 10 实机双体正交、三体双向对称、`-5778` 初始体及未知 ID 回滚 4/4 通过并保存重载。剩：Creo 9/12 实机、WorkBuddy 黑盒。 |
| [BUG-150](work-items/BUG-150.md) | P1 | 已有修复但待验收 | 0.35.8（初始实体作用域） | Creo 10 实机明确 `-5778` 是初始实体 ID，有无作用域均去料 800 mm³，保存重载通过。原护卫舰无作用域零去料待原件复现。 |
| [BUG-152](work-items/BUG-152.md) | P1 | 已有修复但待验收 | 0.36.0（恢复与保存修复）；原现场待原件 | 受管独立零件按目标目录原地保存，重载核对确切版本，MCP 支持客户端空 pending。原现场 Backup -1 根因待原件。 |
| [BUG-153](work-items/BUG-153.md) | P1 | 已有修复但待验收 | 0.36.0（显式近似与诊断）；精确切除待调查 | Creo 10 实机复现闭合 B 样条零去料。显式 21 段折线近似去料与手工折线一致，保存重载通过。精确切除仍有内核边界。 |
| [BUG-154](work-items/BUG-154.md) | P1 | 已有修复但待验收 | 0.36.0（准入披露与种子校验）；外部七截面待样件 | 回调依赖在能力摘要披露，种子读取实际截面父特征与重载几何。Creo 10 两截面三种轮廓通过，外部七截面现场待样件。 |
| [BUG-155](work-items/BUG-155.md) | P0 | 已有修复但待验收 | 0.37.0 | 边选择器写入 `target=edge` 并按类型校验 id；选择器与显式 id 圆角实机通过、保存重载。剩：曲面选择器回归、Creo 9 实机、WorkBuddy。 |
| [BUG-156](work-items/BUG-156.md) | P0 | 已有修复但待验收 | 0.37.0 | 装配源走 `ProMdlnameCopy` 快照，三级嵌套实机通过、源子装配 SHA/revision 不变。剩：原始 P05、Creo 9 实机、WorkBuddy。 |
| [BUG-157](work-items/BUG-157.md) | P0 | 已有修复但待验收 | 0.37.0 | 看门狗观察 `native.log`；装配 `restore_baseline` 走 identity（500 mm³ 基线实机恢复）。剩：6428 边 identity、269 组件现场、Creo 9、WorkBuddy。 |
| [BUG-158](work-items/BUG-158.md) | P0 | 已有修复但待验收 | 0.37.0 | 回执/运行态/compact 同源披露作业与停滞预算；实机 600/600 一致。剩：真实长作业试探、Creo 9。 |
| [BUG-159](work-items/BUG-159.md) | P0 | 部分交付 0.37.0（Python 准入已修复；内核拉伸转 BUG-165） | 0.37.0（部分交付）；内核共享顶点未排期 | 1e-6 mm 弧接点不再误拒，40 段弧轮廓准入通过；内核仍拒绝拉伸，共享顶点转 BUG-165。剩：Creo 9、原始 40 段输入。 |
| [BUG-160](work-items/BUG-160.md) | P0 | 已有修复但待验收 | 0.37.0 | 坐标尺寸接受精确 B 样条；不完整分析面积返回 null 并带 `area_status`。实机 4 条闭合 B 样条通过并保存重载。剩：原始模型、Creo 9。 |
| [BUG-161](work-items/BUG-161.md) | P0 | 已有修复但待验收 | 0.37.0 | 同圆重复边在建特征前明确拒绝（72/90），单边 72 成功并保存重载。剩：原始垫板 116/174、Creo 9。 |
| [BUG-145](work-items/BUG-145.md) | P1 | 已有修复但待验收 | 0.35.6（修复已交付）；Creo Toolkit 探针与外部宿主未排期 | 真实 Explorer 的 Unicode 路径、清理异常和探针诊断离线验证通过；剩 Creo Toolkit 探针及外部宿主验收。 |
| [DEV-078](work-items/DEV-078.md) | P2 | 离线完成；实机待样件 | 未排期 | 四边双方向填充、独立角释放/quilt成形、多段flange全部门禁已在 2026-11-08 离线交付并冻结，3031单测与SDK12.4编译通过；2026-11-17 复核无离线剩余。剩余全是真实样件/实机：Offset/PunchDie、格栅实测、保存重载/回滚、Creo9/10、非mm、WorkBuddy。 |
| [BUG-010](BACKLOG_COMPLETED.md#legacy-bug-010) | P1 | 已有修复但待验收 | 未排期 | 视图 scale=2 已有成功证据；位置更新、图纸保存重载/revision 仍未验。 |
| [BUG-013](work-items/BUG-013.md) | P1 | 已有修复但待验收 | 未排期 | 摘要/分页已有；模型查询精确32KiB及单项超限未验，不能复用 capabilities 结论。 |
| [BUG-019](work-items/BUG-019.md) | P2 | 部分交付 0.32.0（边与面引用结构预检已实施；公开终验仍缺） | 0.32.0（子项已交付） | 引用语法主线已验；计划/三入口公开终验仍缺，先核真实请求和部署。 |
| [BUG-028](work-items/BUG-028.md) | P2 | 已有修复但待验收 | 未排期 | 计划入口整数/字符串/混合草图引用的建模/重载待验，校验通过不等于成功。 |
| [BUG-029](work-items/BUG-029.md) | P1 | 已有修复但待验收 | 未排期 | 重排主矩阵及 no-op 已验；原模型重建/复杂多特征树仍待验证。 |
| [BUG-030](work-items/BUG-030.md) | P1 | 已有修复但待验收 | 未排期 | 尺寸编辑主线已验；原报告失败例与受影响回归仍需原件/实机。 |
| [BUG-040](work-items/BUG-040.md) | P2 | 已有修复但待验收 | 未排期 | 补扫掠后状态变化、compact/full、异常查询；保留非活动记录；依赖：原始 sweep job/native JSON；受控 Creo 会话。 |
| [BUG-047](work-items/BUG-047.md) | P1 | 已有修复但待验收 | 未排期 | 两向单折边、四壁建成和无效边回滚已有实机记录；待核壁顶内外缘及连续折边的 flip 方向，并在回滚后复验合法折边。 |
| [BUG-057](work-items/BUG-057.md) | P1 | 已有修复但待验收 | 未排期 | 统一锁及本机三状态60轮已过；双进程200轮与 Win10/Python3.13 原环境待验。 |
| [BUG-062](work-items/BUG-062.md) | P1 | 已有修复但待验收 | 未排期 | centerline 核心两入口已验；保存重载全矩阵及其它构型按原卡保留。 |
| [BUG-072](work-items/BUG-072.md) | P2 | 已有修复但待验收 | 未排期 | 非毫米保护本机已验；公开复核待补，继续毫米准入与原件字节保护。 |
| [BUG-074](work-items/BUG-074.md) | P1 | 已有修复但待验收 | 未排期 | 历史身份停止证明已修；Windows 跨启动四动作与公开验收未齐，同次启动/未知仍拒绝。 |
| [BUG-079](work-items/BUG-079.md) | P1 | 已有修复但待验收 | 未排期 | 就地改弧半径已修；非主平面/外部完整编辑矩阵仍未验。 |
| [BUG-082](work-items/BUG-082.md) | P1 | 已有修复但待验收 | 未排期 | 主修复/外部 Creo 9 编辑已过；非主平面 autodim、贴轴基线及失败 revision 未齐。 |
| [BUG-083](work-items/BUG-083.md) | P2 | 已有修复但待验收 | 未排期 | Python 非法轴准入已修；原生 validate_revolve_axis 分支与外部原环境未验。 |
| [BUG-090](work-items/BUG-090.md) | P1 | 已有修复但待验收 | 未排期 | 0.10.0 已交付函数门控与实读回退，报告方已验证 Creo 10 SDK 零补丁编译。剩原环境下回退分支的板厚实读与建模验收。 |
| [BUG-098](work-items/BUG-098.md) | P1 | 已有修复但待验收 | 未排期 | 三点面阻塞已修并实机8/8；约束引用逐条核对仍未验证，保留数量校验安全边界。 |
| [BUG-101](work-items/BUG-101.md) | P1 | 已有修复但待验收 | 未排期 | 0.46.0 已支持近容差 arc-arc 端点焊接并在 Creo 10 验证等价夹具；取得外部 gear10.json 后回放原案。 |
| [BUG-105](work-items/BUG-105.md) | P1 | 已有修复但待验收 | 未排期 | 回滚成功保持 ready 已验；派发前零变更及 ack_no_mutation 恢复失败态仍未实机。 |
| [BUG-107](work-items/BUG-107.md) | P1 | 已有修复但待验收 | 未排期 | 0.11.4 已修复生成器的缺头构建错误。外部报告记载 Creo 10 SDK 上 0.21.0 官方包零补丁编译成功；Creo 9 SDK 与原案运行期验收仍待对应证据。 |
| [BUG-110](work-items/BUG-110.md) | P1 | 已有修复但待验收 | 未排期 | ack_failure 已实现；11/07 仍 guard_only，零件/装配成功确认分支未触发，待健康失败态夹具。 |
| [BUG-114](work-items/BUG-114.md) | P1 | 已有修复但待验收 | 未排期 | 0.16.1 在 Creo 12.4 已验新零件、新装配失败清理、同名复建及已保存件回滚。剩 Creo 10 原案中清理后的事务效果核对。 |
| [BUG-116](work-items/BUG-116.md) | P1 | 已有修复但待验收 | 未排期 | 0.19.3反馈P1/P5：draft 中性面示例改几何平面形式并说明两种解析语义，原生失败带 `failed_reference` 与候选数/ID；实机文案与建模效果未验。 |
| [BUG-117](work-items/BUG-117.md) | P2 | 已有修复但待验收 | 未排期 | 0.19.3反馈P4：targets 对象形式改单条可读拒绝并给合法示例，依赖列表加重提提示；自动基准面合并开关未设计与实现。 |
| [BUG-135](work-items/BUG-135.md) | P2 | 已有修复但待验收 | 0.33.0（候选） | 0.31.1 反馈：element_tree 路线 `create_code=0` 但 `ProFeatureElemtreeExtract` 返回 -18 时直接回滚。离线新增显式 `accept_unverified_completion`（默认未设置不改旧计划字节），仅在无边界条件/模板时按几何验证继续并标注 `completion_verified_by=geometry`；panel 路线与带条件计划仍拒绝。**2026-11-20 Creo 10 实测：该宿主无法补全**——`ProFeatureElemtreeCreate` 仍 -18、用创建树 redefine 返回 -1、`ProSolidRegenerate` 后 `feature_incomplete=true` 且 quilt 0，作业 `21535fea…` 以 `SURFACE_LOFT_ACCEPT_INCOMPLETE` 失败并清理新模型；Creo 10 只能走 resident_panel。剩：Creo 12.4 成功路径。 |
| [BUG-136](work-items/BUG-136.md) | P2 | 已有修复但待验收 | 0.33.0（候选） | 0.31.1 反馈：`mate_offset`/`align` 被当圆柱面要求、文案不写实际约束类型。离线按 mate/mate_offset/align/align_offset 要求平面、insert 要求圆柱、csys 跳过，并输出实际类型。**2026-11-20 本机 Creo 10 实机通过**：`test_t09_assembly_replay --live` 六类约束全通过（`mate_offset` 偏移 25→40 被观察到）；圆柱面 `mate_offset` 被拒并写 `mate_offset needs a real plane`（`7e748410…`）；平面 `insert` 仍要求 `PRO_SRF_CYL`（`d7ddf3cb…`）；`csys` succeeded + 保存重载 true（`54ab2895…`）。剩：Creo 12.4 与 Arm7 原模型 60 条配合全量。 |
| [DEV-096](work-items/DEV-096.md) | P2 | 已有修复但待验收 | 0.33.0（候选） | 发布记录门禁此前只校验 `previous_release_commit` 的 40-hex 形状。离线新增与 `RELEASE-<ver>.md`“上一版本”行提交号的交叉校验，并在存在 `.git` 时用 `rev-parse v<previous>^{commit}` 核对标签指向；剩对现存发布记录回归与负例复核。 |

## 观察中

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-005](work-items/BUG-005.md) | P1 | 观察中 | 未排期 | 新现场再查；依赖：新现场。 |
| [BUG-021](work-items/BUG-021.md) | P1 | 观察中 | 未排期 | 朋友新反馈再查；依赖：新现场。 |
| [BUG-088](work-items/BUG-088.md) | P2 | 观察中 | 未排期 | Creo 10 原案再查；依赖：原始日志。 |

## 其它 agent 处理范围

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-003](BACKLOG_COMPLETED.md#legacy-bug-003) | P1 | 其它 agent 处理范围 | 未排期 | 与 FEAT-010 及反馈批对账；依赖：实机/原件。 |
| [BUG-032](work-items/BUG-032.md) | P1 | 其它 agent 处理范围 | 未排期 | green/white 面距、外部差异；依赖：外部环境。 |
| [BUG-045](work-items/BUG-045.md) | P2 | 其它 agent 处理范围 | 未排期 | 内核阈值扫描、外部 -2；依赖：健康会话/原报文。 |
| [BUG-046](work-items/BUG-046.md) | P1 | 其它 agent 处理范围 | 未排期 | revolve 与一体增料路线；依赖：原生方案。 |
| [BUG-050](work-items/BUG-050.md) | P1 | 其它 agent 处理范围 | 未排期 | 原切线闭环/53 mm 混合轮廓；依赖：原输入。 |
| [BUG-051](work-items/BUG-051.md) | P1 | 其它 agent 处理范围 | 未排期 | 完整原案与 coordinates 对照；依赖：原输入/日志。 |
| [BUG-064](work-items/BUG-064.md) | P1 | 其它 agent 处理范围 | 未排期 | surface 引用、无第二参照、外部原案；依赖：原件/实机。 |
| [BUG-084](work-items/BUG-084.md) | P1 | 其它 agent 处理范围 | 未排期 | 三引用等价与外部原案；依赖：原件/实机。 |
| [BUG-095](work-items/BUG-095.md) | P2 | 其它 agent 处理范围 | 未排期 | 本机已验，待原负责人交付裁定；报告方同面/同模型仍缺 request.json；依赖：request.json。 |
| [BUG-103](work-items/BUG-103.md) | P1 | 其它 agent 处理范围 | 未排期 | 四壁矩阵、UI 对照、外部差异；依赖：Creo 10 环境。 |
| [BUG-113](work-items/BUG-113.md) | P1 | 其它 agent 处理范围 | 未排期 | 外部 Backup/回滚原案；依赖：MCP/job/native/检查点。2026-11-21 受控对照：干净会话连续 10 次保存成功、30 s 延迟仍失败、Restart Manager 无持有者、锁 latest/next/verify 均未复现 -1，判定与前一会话状态相关而非外部文件锁；新增失败瞬间可读性诊断（`source_checkpoint_readable`/`candidate_readability`），随 0.35.3 发布。 |
| [BUG-115](work-items/BUG-115.md) | P2 | 其它 agent 处理范围（已交付 0.18.4 H12 回执复验子项） | 0.18.4（H12 子项已交付）；剩余未排期 | 原生 -4 根因、其它组合；依赖：原生机制。0.19.3 B 批只补诊断：`ProFeatureGeomitemVisit` 失败时回执带 ProError 数值、标签与「引用原始 target 或用 quilt 几何 ID」的替代方式，未改解析语义。 |
| [DEV-054](work-items/DEV-054.md) | P2 | 其它 agent 处理范围 | 未排期 | 原负责人仍有本地维护记录未提交；分支/归档与发布状态核对由其继续，本批只对账。 |
| [DEV-067](work-items/DEV-067.md) | P2 | 其它 agent 处理范围 | 未排期 | A01/A03/B01/D02 已进入本地集成，A02 已交付；协调原负责人验收/发布，其它组未全实现。 |
| [DEV-069](work-items/DEV-069.md) | P1 | 其它 agent 处理范围 | 未排期 | chatgpt/0.17.1 反馈归原批负责人；保真、钣金增料/角部、原现场与发布后核对未闭环。 |
| [DEV-072](work-items/DEV-072.md) | P1 | 其它 agent 处理范围 | 未排期 | 代码及组合编译已有；原生诊断实机/保存重载、真实附件下载与 0.17.4 发布核对归原负责人。 |
| [FEAT-035](work-items/FEAT-035.md) | P2 | 其它 agent 处理范围 | 未排期 | 标准孔实现已进入本地集成；孔表/深度和扩展原生矩阵由原负责人收口。 |
| [FEAT-057](work-items/FEAT-057.md) | P2 | 部分交付 0.35.6 子项（装配路径与扫描证据）；缺材料/抑制/嵌套与混合密度真实质量、主惯量未排期 | 0.18.1（已发布）；0.35.6（装配路径已交付）；余项未排期 | 质量属性已随 0.18.0 集成；0.18.1 补 `mass_unavailable_reason` 回执契约与单位口径。2026-11-22 放开装配：体积/面积/几何重心与质量重心、只读 occurrence 扫描（缺材料/未解析/截断即拒绝质量）、有效平均密度标记；Creo 10 三实例装配体积 2200 mm³、面积 1680 mm²、重心与解析值一致。剩：缺材料组件、抑制/嵌套、混合密度真实质量（Creo 10 材料密度查询 -1）、主惯量。 |
| [FEAT-059](work-items/FEAT-059.md) | P2 | 其它 agent 处理范围（已交付 0.18.0 事务日志底座子项） | 未排期（剩余范围） | 事务日志底座随 0.18.0 集成；原生骨架创建、受管身份/依赖、完整多模型事务未实现，未排期。 |
| [FEAT-063](work-items/FEAT-063.md) | P2 | 其它 agent 处理范围 | 未排期 | 只读 box_frame 规划器软件完成并进入本地集成；模板原生/保存重载仍未验。 |

## 开发中

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |

## 部分交付，剩余待验收

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [DEV-002](work-items/DEV-002.md) | P2 | 部分交付，剩余待验收 | 0.45.2（第四、五批） | Python 服务包化、新旧 MCP 入口、离线协议和独立安装验收完成。第三批 T5 实机及其余测试布局仍开放。 |
| [DEV-077](work-items/DEV-077.md) | P1 | R01—R04 已随 0.19.2 交付；实机/黑盒/远端余项待接手 | 0.19.2 | 0.18.2四份反馈对比归档、RELEASING/POSTCHECK回填、台账计数门禁、质量属性诊断与阶段计时回退；R01可配rotation_tolerance、R02质量属性提示/get_job 300s/known_limitations/plan_examples已在0.19.1交付；0.19.2新增草图closure_tolerance/snap_endpoints/偏差断言、mirror feature引用与回执、session_health降级策略、quilt_merge消耗回执；余项见DEV-077-HANDOFF R01—R08。 |
| [DEV-100](work-items/DEV-100.md) | P1 | 部分交付，剩余待验收 | 0.44.0（子项已交付）；剩余未排期 | 0.44.0 已交付 BUG-186/FEAT-084/FEAT-085/草图闭合与旋转轴弧度等子项；剩余项及跨环境验收按各子卡跟踪。 |
| [DEV-091](work-items/DEV-091.md) | P1 | 部分交付，剩余待验收 | 未排期 | 四原件归档、源码对照与分批计划已完成；R/M1/A0/A1/G1 已实现，原生构建成功，M1/A0/A1 实机通过并保存重载。A2（61条）与 G1 原生选区仍待输入/查证，Arm2 完整装配未逐条对照。 |
| [BUG-193](work-items/BUG-193.md) | P1 | 部分交付 | 未排期 | 0.46.1 已交付提交前零锁预检并通过 Creo 10 保存重载。剩余为 Creo 9/12.4 实机及本版提交后的 WorkBuddy 黑盒复验。 |
| [FEAT-078](work-items/FEAT-078.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.45.0 已交付实体面包围盒修正，Creo 10 已验三种零件及旋转装配。待外部原计划、Creo 9/12 与 WorkBuddy 复验。 |
| [DEV-076](work-items/DEV-076.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.19.1 已交付 H13/H15/H16，Creo 12.4 已验。H14 交线诊断、H17 原件、H18 同载荷与 H19 旧输入继续按工作卡跟踪。 |
| [BUG-076](work-items/BUG-076.md) | P1 | 部分交付 0.32.0（组件列表分页已实施；真实零件全链路复核仍待） | 未排期 | 0.32.0 已交付组件列表分页。待真实零件全链路及公开接口复核；阻断修复由 BUG-077 跟踪。 |
| [BUG-094](work-items/BUG-094.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.45.0 已交付有向轴角度约定并验证位置与重载。用同一有向轴对照两个历史 MCP 版本的结果。 |
| [BUG-119](work-items/BUG-119.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.23.1 已交付已有实体上的曲面放样修正，Creo 12.4 已验。待 Creo 9/10 原场景、非毫米单位及 WorkBuddy 复验。 |
| [BUG-134](work-items/BUG-134.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.33.0 已交付面板模型定位修正，Creo 10 主场景通过。待 Creo 12.4、PANEL_MODEL_UNAVAILABLE 失败路径和 WorkBuddy 黑盒。 |
| [DEV-095](work-items/DEV-095.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.33.0 已交付模型名、host_release 与 payload_sha256 披露，Creo 10 已验。待 Creo 12.4、运行中 DLL 与认证 payload 的绑定证明及 WorkBuddy 黑盒。 |
| [BUG-129](work-items/BUG-129.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.27.0 已交付宽度方向映射说明。取得 Arm2 原模型与 placement 输入，逐项核对装配位置，并在 Creo 12.4/10 复测。 |
| [BUG-102](work-items/BUG-102.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.45.0 已交付拔模方向修正。取得原倒角、圆角夹具，在 Creo 10 核实历史返回码 -1。 |
| [BUG-108](work-items/BUG-108.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.45.0 已交付默认草图保真修正。复验原长链的 0.004 mm 漂移，并采集显式 coordinates 模式下的 accepted_rigid 实例。 |
| [BUG-130](work-items/BUG-130.md) | P1 | 部分交付，剩余待验收 | 未排期 | 先复验旧样件 bulb_verified_03989988，再核对装配 STL、Creo 9／12.4 及完整曲面偏差上界。0.45.1 的精度结论限于已测样件的抽样。 |
| [BUG-191](work-items/BUG-191.md) | P1 | 部分交付，剩余待验收 | 0.45.0 | 交付保存前加料净体积保护，整单回滚、revision 和重载几何通过。原始摆杆同输入复现与定因待验。 |
| [FEAT-074](work-items/FEAT-074.md) | P2 | 部分交付，剩余待验收 | 0.36.0（选面、预览与回执）；面角色组待验收 | 同计划拔模按特征标签限定面，支持 JPEG 视图与像素规格，清理输入可复制，会报共享边与端点间隙。面角色组与原弧线仍无证据。 |
| [BUG-143](work-items/BUG-143.md) | P1 | 部分交付 0.35.6 子项；闭合锥面 trim 与其他非圆柱形态未排期 | 0.35.0（子项已交付）；0.35.2（镜像防护与标签实机已交付）；0.35.3（非圆柱链路与保存闭环证据已交付）；0.35.6（固体镜像根因与创建前拒绝已交付）；余项未排期 | 闭合锥面 trim 受面积测量限制；待验其他非圆柱形态及外部报告环境。 |
| [FEAT-071](work-items/FEAT-071.md) | P2 | 部分交付 0.35.0，剩余待验收 | 0.35.0（子项已交付）；剩余未排期 | `d1_d2` 与独立 `creo_chamfer` 契约已落地；Creo 10 实机 2/5 与 5/2 各去除 250 mm³，D1 落在非 `reference_surface` 相邻面，已随 v0.35.0 发布。剩：其他参考面组合、曲面边与其他 Creo 版本。 |
| [BUG-140](work-items/BUG-140.md) | P1 | 部分交付 0.35.0，剩余待验收 | 0.35.0（子项已交付）；剩余未排期 | legacy 候选惰性求值并设 8 依赖上限（10 依赖 0.415647 s/1024 → 1.8 µs/0），已随 v0.35.0 发布。剩：真实构建缓存端到端启动计时。 |
| [BUG-141](work-items/BUG-141.md) | P1 | 部分交付 0.35.0，剩余待验收 | 0.35.0（子项已交付）；剩余未排期 | 仅忽略可确认退出的进程，`selection_required` 不再被 `force_ready` 绕过，已随 v0.35.0 发布。剩：真实僵尸进程现场。 |
| [BUG-139](work-items/BUG-139.md) | P1 | 部分交付 0.34.0，剩余待验收 | 0.34.0（子项已交付）；剩余未排期 | 启动协调器探测超时可配、成功探测循环外落地、`connecting` 相位、预算分段、recent-connected/`force_ready` 降级、身份归因与错误上下文已交付；26 项定向单测通过，本机 Creo 10 冷启动→ready→FEAT-070 建模及保存重载通过，已随 v0.34.0 发布。剩：`force_ready` 与失败路径文案的实机夹具，其他环境按反馈补录。 |
| [FEAT-070](work-items/FEAT-070.md) | P2 | 部分交付 0.34.0，剩余待验收 | 0.34.0（子项已交付）；剩余未排期 | `creo_redefine_solidify_body` 已公开（109→110），`strategy=new` 在本机 Creo 10 解除实体化主体自锁，redefine/regenerate=0、体积 55087038135.823044 mm³ 不变、保存重载 true；非实体化目标按 phase/原始码失败并回滚，已随 v0.34.0 发布。剩：`strategy=existing` 在该几何的 Creo 模态稳定性、本轮 quilt 142 G1 复测、真实船体非圆剖面与其他环境。 |
| [BUG-121](work-items/BUG-121.md) | P2 | 部分交付，剩余待验收 | 0.24.0（子项）；剩余未排期 | 只读型计划（`export`/`dump_tree`/`mass_properties`/`surface_group_measure`/`surface_curvature`/`udf_inspect`）在 Python 侧自动按只读准入并记 `readonly_source`，不再被 GUI 保存造成的基线漂移挡住；写计划的 `model_reconciliation_required` 失败消息追加 `creo_reconcile_model` 动作指引，原生原文保留在 `native_message`。离线 11 项单测通过；Creo 12.4 实机多轮导出均成功（最新 `...T160310` 作业 `7b7ec1450490427598a2dbe72b99941c`，`...T150422`/`...T145133` 同结论），`job.json` 记 `readonly=true`/`readonly_source=inspection_only_plan`；GUI 保存造成的漂移与 Creo 10 未验。 |
| [BUG-122](work-items/BUG-122.md) | P1 | 部分交付，剩余待验收 | 0.27.0（准入接线修复）；Creo 10 未验 | 2026-11-17离线修复：提交使用同worker实测观测的身份副本，与能力披露一致；真实parser/观测落盘/读取/submit回归通过，同worker已知-18在lock/job前拒绝，跨worker及supported/unknown不误拒。模板XML仍需Extract，不再作为免抽取建议。Creo10第二次拒绝无空壳、WorkBuddy黑盒待验；未来panel按路线准入仍随BUG-120推进。保护修复不等于成型。 |
| [FEAT-067](work-items/FEAT-067.md) | P2 | 部分交付，剩余待验收 | 0.24.0（子项）；剩余未排期 | 补验包围盒与总面积断言在装配、英寸或未知单位、空面及单面测量失败时的回执。 |
| [BUG-124](work-items/BUG-124.md) | P2 | 部分交付，剩余待验收 | 0.24.0（子项）；剩余未排期 | 补验 Creo 10 导入与重载、纯曲面样本、英寸模型回滚，以及导入面组能否用于合并或镜像。 |
| [DEV-027](work-items/DEV-027.md) | P2 | 部分交付，剩余待验收 | 未排期 | 真实世代回收、二进制可复现性及副本外部改动/登记不一致分支待验。 |
| [DEV-044](work-items/DEV-044.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.4.7 五组已有后续证据；保留 DEV-027 等整计划关联余项，避免按旧末段重复安排迁移。 |
| [DEV-051](work-items/DEV-051.md) | P1 | 部分交付，剩余待验收 | 未排期 | 历史离线批已交付；四壁后续、嵌套回导、原件缺项及公开预算契约按子卡对账。 |
| [DEV-053](work-items/DEV-053.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.11.1 已完成 Q01 对 P07/P08/P11 的实机覆盖。P13 性能后续按新问题启动，P16 原 TXT 完整场景与缺件验收仍开放。 |
| [DEV-070](work-items/DEV-070.md) | P2 | 部分交付，剩余待验收 | 未排期 | 四附件校验及 API 回退已写；真实远端回退和旧附件/摘要冲突外置核对待原负责人完成。 |
| [DEV-071](work-items/DEV-071.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.17.3 离线修复已合主干；原生阶段码/miter 回执实机观察待补，53mm 根因归 BUG-050/051。 |
| [DEV-083](work-items/DEV-083.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.23.1/0.23.2 记录/状态/链接门禁已交付；0.25.0 续项已随 0.26.0 交付（部分子项）：交付快照与ID完备性、交付版本/实际Release列、差异说明收窄、完成档案覆盖、发布前后证据与前版基线、审定TXT白名单；专项单测通过，未实机。 |
| [DEV-074](work-items/DEV-074.md) | P1 | 已交付 0.18.3/0.18.4/0.19.0 子项；Creo 9/10 未排期 | 0.19.0（子项已交付） | 0.19.0 交付 H03 `creo_quilt_merge` 公开（两片 400→800 mm²）、H08 `creo_surface_round` 与 `creo_measure_surface_curvature` 实机、H10 五爪整瓶整链 63 项检查；H05 钣金附着增料、H07 独立 quilt 偏置、钣金成形类与任意非平面 fill 为不可用或未取证，门禁保持；仍开放：百叶/格栅/凸台/铰链/耳、格栅 cut 定因、Creo 9/10 与 WorkBuddy。 |
| [FEAT-004](work-items/FEAT-004.md) | P2 | 部分交付，剩余待验收 | 未排期 | rebase 后 18/18 实机已补；装配/骨架/族表尺寸、分类和同计划先后语义仍未验。 |
| [FEAT-005](BACKLOG_COMPLETED.md#legacy-feat-005) | P2 | 部分交付，剩余待验收 | 未排期 | 过期 revision 错误上下文已实现；公开 stdio 验收未记录，继续保持入队前拒绝。 |
| [FEAT-006](work-items/FEAT-006.md) | P2 | 部分交付，剩余待验收 | 未排期 | 接管/收养主线已验；卡内既有剩余范围继续保留，异常所有权不以健康夹具替代。 |
| [FEAT-007](work-items/FEAT-007.md) | P2 | 部分交付，剩余待验收 | 未排期 | 长轮询已实现且实机六项通过；真实长任务/stdin 取消与公开进度细分仍开放。 |
| [FEAT-008](work-items/FEAT-008.md) | P2 | 部分交付 0.32.0（边与面引用槽位预检已实施；首批其余范围仍缺） | 0.32.0（子项已交付） | entity_ids/中心线计数及重建配套已验；其余首批范围与真多中心线原件仍缺。 |
| [FEAT-012](work-items/FEAT-012.md) | P2 | 部分交付 0.30.0，剩余待验收 | 未排期 | 矩阵放置已验；显式源件更新/嵌套及内核精度扫描待补，阈值不改。 |
| [FEAT-014](work-items/FEAT-014.md) | P2 | 已交付 0.18.4/0.19.0 反证子项（附着增料与成形类均不可用，门禁保持）；其余未排期 | 0.19.0（反证子项已交付） | 四壁基础/origin/选边已有；附着增料经 Creo 12.4 反证不可用（直接 add −1、union 吞并钣金体）；成形类 corner relief/草图成形 create 失败或再生失败，hem/jog 无 API，格栅 cut 未取证；连续多边折边、格栅孔、凸台/铰链/耳未排期。 |
| [FEAT-018](work-items/FEAT-018.md) | P1 | 部分交付，剩余待验收 | 未排期 | 补四动作的 revision、凭证/过期、幂等、owner、再次中断与后续编辑矩阵。0.19.3 B 批新增只读 `completion_review`（五档 verdict + signals，明确不授权重放/改 revision）；恢复状态机与令牌未改。 |
| [FEAT-020](work-items/FEAT-020.md) | P2 | 部分交付，剩余待验收 | 未排期 | 更新预算/force 已实现；真实断网/限流及失败期间继续建模待验。 |
| [FEAT-022](work-items/FEAT-022.md) | P2 | 部分交付，剩余待验收 | 未排期 | 真实连接器升级前后核对路径、启动身份和工具版本；本地部署指纹已实现。 |
| [FEAT-023](work-items/FEAT-023.md) | P2 | 部分交付 0.32.0（精简回执与组件列表分页已实施；实机与真实 stdio 字节未验） | 0.32.0（子项已交付） | 剩余 jobs 日志、复杂请求/union 错误体量及规范化回执实机；capabilities 分页已闭环。 |
| [FEAT-029](work-items/FEAT-029.md) | P1 | 部分交付，剩余待验收 | 未排期 | 剩余跨代兼容升级/回退、多目录与公开验收，自动注册/签名另评估。 |
| [FEAT-030](work-items/FEAT-030.md) | P2 | 部分交付，剩余待验收 | 未排期 | 15+2 种子本机矩阵已验；生产版本可追溯与 Creo 9 加载/重生仍缺环境和来源。 |
| [FEAT-031](work-items/FEAT-031.md) | P2 | 部分交付，剩余待验收 | 未排期 | 两件装配导出/隔离回导已验；嵌套、外部引用与跨机重建边界仍开放。 |
| [FEAT-036](work-items/FEAT-036.md) | P2 | 部分交付，剩余待验收 | 未排期 | delete/suppress/resume 主线已验；组/阵列头随动仍未闭环。 |
| [FEAT-042](work-items/FEAT-042.md) | P1 | 部分交付，剩余待验收 | 未排期 | 接管、同模型并发编辑、真实再生失败及钣金语义仍需证据；通道 busy 不代替。 |
| [FEAT-043](work-items/FEAT-043.md) | P2 | 部分交付，剩余待验收 | 未排期 | 会话枚举主线已验；unknown、其它类型及真实并发枚举待补。 |
| [FEAT-044](work-items/FEAT-044.md) | P1 | 部分交付，剩余待验收 | 未排期 | 0.4.6 外部 Creo 10 已验证清场后打开 asm_mx.asm.16 并加载 8 个组件。显示失败、unknown、真实并发与新增字段的 WorkBuddy 专项复核仍待验。 |
| [FEAT-045](work-items/FEAT-045.md) | P2 | 部分交付，剩余待验收 | 未排期 | 只读装配检查主线已验；受限场景/外部原环境与公开黑盒保留。2026-11-19 DEV-092/T3 已完成 SDK 测量语义查证（member→owner 而非 root、outline 需排除基准、面积走 contour），逐实例 `bbox_world_mm` 与逐面面积字段尚未实现。 |
| [FEAT-046](work-items/FEAT-046.md) | P1 | 部分交付，剩余待验收 | 未排期 | erase 主线已有外部证据；本机矩阵、阻断分支与公开黑盒仍未齐。 |
| [FEAT-047](work-items/FEAT-047.md) | P1 | 部分交付，剩余待验收 | 未排期 | health 正常/异常分页主线已验；外部异常数据还原及原始响应字节核对按卡保留。 |
| [FEAT-048](work-items/FEAT-048.md) | P1 | 部分交付，剩余待验收 | 未排期 | 按路径/批量收养已有实机；准入分支泛化及卡内保留项待补，不重做首批。 |
| [FEAT-051](work-items/FEAT-051.md) | P2 | 部分交付 0.32.0（切除体积变化分型已实施；外部 -1 定因与实机矩阵仍缺） | 0.32.0（子项已交付） | requested/effective_flip 与 draft_failure 当前代码已有；外部 -1 定因、单位实机矩阵及回执补证仍开放。 |
| [FEAT-052](work-items/FEAT-052.md) | P2 | 部分交付，剩余待验收 | 未排期 | 分族上色主线已实机通过；真实 busy 并发与其余卡内矩阵未验，random/标签键归 FEAT-056。 |
| [FEAT-053](work-items/FEAT-053.md) | P2 | 部分交付，剩余待验收 | 未排期 | 三点定面与斜面草图已验；约束引用逐条核对未验证，关联 BUG-098 保留。 |
| [FEAT-058](work-items/FEAT-058.md) | P2 | 已交付 0.12.0/0.15.0/0.16.1/0.17.0/0.18.3 子项；坐标换参/扩展 frame 未排期 | 0.18.3（子项已交付） | H01 非零 `origin` 大跨度 resize 已修复（Creo 12.4 实机 14/14）；坐标换参、板厚回执新诊断、扩展 frame 与非矩形截面留原批未排期。 |

## 部分交付，剩余待规划

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [FEAT-094](work-items/FEAT-094.md) | P2 | 部分交付，剩余待规划 | 0.50.0（范围边界与前置拦截）；剩余未排期 | 已界定 `creo_new_loft_part`（`new_part_only`）与已有零件 `creo_loft`（需已加载常驻回调）的契约边界；剩：交互桌面手动启动回调后 `creo_loft` 同 `model_id` 追加实机复验，以及免回调追加与 7 截面/导线能力后续规划。 |
| [DEV-080](work-items/DEV-080.md) | P1 | 首批离线收口已随 0.19.3 交付；原生/实机余项待接手 | 0.19.3 | 接手0.19.0三份报告复核后仍未闭环的H01—H09及未编号缺口；首批交付手写TU头门控契约测试、COMPATIBILITY缺头降级说明、计数自检进CI；原生解耦/等价元素树、开放弧trim、残留quilt、原生截面面积、大作业compact、连续顶边选边、entities_file、native_bundle、负origin resize待Creo10 SDK或实机；解压单测发布前阻断与verify_stages优先留后续。 |
| [DEV-082](work-items/DEV-082.md) | P1 | 部分交付，剩余待规划 | 0.23.0（门禁已交付）；H01 未排期 | 0.19.3反馈P1-1/P1-2 的跨TU符号门控已交付；0.21.0反馈P1 把 `surface_loft`/`surface_boundary_fill` 从 `__has_include(<Probbl.h>)` 改为 `MECHDOG_HAS_BNBLN_TREE`（`ProElemId.h` 五个 `PRO_E_BNBLN_*`），worker/能力文案同步，随 0.23.0 发布，Creo 12.4 实机放样回归全 PASS。H01抽 `element_tree_json.h`、单一真值源、真实Creo10 SDK整包编译与运行期元素树再生仍开放。 |
| [DEV-101](work-items/DEV-101.md) | P1 | 部分交付，剩余待规划 | 0.44.0/0.47.1（已交付子项）；剩余未排期 | BUG-187..190、FEAT-088/089 已交付；剩余 FEAT-086/FEAT-087/DEV-092 待规划及跨环境验收。 |
| [DEV-030](work-items/DEV-030.md) | P1 | 部分交付，剩余待规划 | 未排期 | 推进 G2 底板/编辑、G3 履带/性能、G4 阵列；`vcvars64_env` 已随 0.4.4 交付，已放宽三键不重复调查。 |
| [FEAT-010](work-items/FEAT-010.md) | P2 | 部分交付，剩余待规划 | 0.11.1/0.17.3（子项已交付）；剩余未排期 | Right ±Z 与显式容差已交付；倾斜 frame、保真/原53mm输入、编辑重载和投影驱动仍开放。 |
| [DEV-046](work-items/DEV-046.md) | P1 | 部分交付，剩余待规划 | 未排期 | 前两批随 0.5.2、0.6.0 交付。第三批 FEAT-049 约束克隆、FEAT-050 结果比对待规划；源件更新/嵌套与世代回收仍见 FEAT-012、DEV-027。 |
| [FEAT-039](work-items/FEAT-039.md) | P1 | 部分交付，剩余待规划 | 未排期 | 0.32.0 已交付焊接准入判据，已支持的多截面放样见 FEAT-065。其余边界混合、独立 quilt 偏置、任意非平面 fill、trim 偏置语义与真实交线诊断仍待规划。H17/H18 原始输入及对照沿 DEV-076 跟踪。 |
| [BUG-123](work-items/BUG-123.md) | P1 | 部分交付，剩余待规划 | 0.24.0（子项）；剩余未排期 | 在 Creo 10 复测模板解析、创建后提取（原码 -18）；当前仅覆盖 3 截面＋3 导线。 |
| [FEAT-027](BACKLOG_COMPLETED.md#legacy-feat-027) | P3 | 部分交付，剩余待规划 | 未排期 | 墓碑与旧别名拒绝已交付；显式释放/重绑定接口和跨版本历史核对待规划。 |
| [DEV-066](work-items/DEV-066.md) | P2 | 部分交付，剩余待规划 | 未排期 | 0.18.2已交付来源降级子项；当前分支8def1e4已补齐其余Git读取、报告字段、负例捕获和runtime日志取消跟踪，未发布增量及H08—H09见DEV-075-HANDOFF。 |
| [FEAT-033](work-items/FEAT-033.md) | P1 | 部分交付，剩余待规划 | 未排期（0.19.3 B 批 opt-in 已交付） | small/large 基准已有；`execute_plan(timeout_seconds)` 受控覆盖（60—7200，默认=服务配置）与 job 回执 `timeout_seconds`/`timeout_source`、看门狗按作业预算判定已交付；自动预算公式、阶段耗时公开契约与到期动作仍待规划，不以取消保存重载缩时。 |
| [FEAT-066](work-items/FEAT-066.md) | P1 | 部分交付，剩余待规划 | 0.23.0（已交付子项） | `b_spline` 精确 NURBS 实体随 0.23.0 发布，Creo 12.4 实机控制点回读偏差 2.6e-31 mm、两截面面积 1058.017278 mm² 对齐独立 de Boor oracle、保存重载一致，`surface_loft` 回归 PASS。剩余 `closed`、`dimensioning="coordinates"`、页面编辑未排期；Creo 10 运行期未验。 |
| [BUG-120](work-items/BUG-120.md) | P1 | 部分交付 0.31.0（任务 1–4 已交付，任务 5 接缝几何已验） | 0.31.0（本版子项） | 接缝 G1 已达标；实体化主体引用失效，健康相切实体尚未保存。Creo 10 单特征“末端点＋导线”再生失败，真实非圆船体截面映射待验。 |

<a id="未来能力候选"></a>
<a id="当前优先功能"></a>
| [DEV-081](work-items/DEV-081.md) | P1 | B1/B2/B3/B4 已随 0.20.0 实机验收交付；B5/B6 与 C 批黑盒待做 | 0.20.0 | B5 着色预览、B6 锥台/拔模及 WorkBuddy C0—C5 待做；前置条件、各批证据与黑盒提示词见卡。 |
| [FEAT-001](work-items/FEAT-001.md) | P1 | 部分交付 0.15.0，剩余待规划 | 未排期 | 启动/重连/多会话状态检测及普通 retry、损坏通道恢复完整验收仍开放。 |
| [FEAT-009](work-items/FEAT-009.md) | P2 | 已交付 0.18.3 子项；动态准入已补；多截面/导线已由 FEAT-065 M1/M2 随 0.21.0 交付；闭合/连续性/非平面未排期 | 0.18.3（子项已交付） | 两截面直纹曲面放样 `creo_surface_loft` 在Creo12.4已实机验收（quilt 800 mm²、trim 两侧各 400、2 mm 加厚 1600 mm³）；H13 worker构建身份/动态准入与提交前拒绝已实现并在Creo12.4核验，Creo10缺Probbl.h实机与完整放样路线仍未验。2026-11-11 更正：多截面已由 [FEAT-065](work-items/FEAT-065.md) M1/M2 随 0.21.0 发布并在 Creo 12.4 实机验收——2—32 截面（两截面 straight 直纹，3 截面以上必须 smooth）、可选 2—8 条第二方向导线；闭合曲面、相切/曲率连续性、非平行/扭转/任意正交平面截面、圆弧截面、端点收敛仍不公开或未测，Creo 9/10 未验。 |
| [FEAT-055](work-items/FEAT-055.md) | P2 | 已交付 0.18.4/0.19.0 子项（H08 曲面边圆角与数值曲率/G1 已公开并实机）；其余未排期 | 0.19.0（H08 子项已交付）；剩余未排期 | `creo_surface_round` 与 `creo_measure_surface_curvature` 已公开，公开工具 107；edge-chain、变半径/过渡、斑马/曲率梳图像无 API；重拟曲面操作链、merge/放样及原生查询补证未排期。 |

## 待规划

| ID / 工作卡 | 优先级 | 当前状态 | 目标版本 | 简短剩余工作 / 依赖 |
| --- | --- | --- | --- | --- |
| [BUG-162](work-items/BUG-162.md) | P1 | 待规划 | 未排期 | 显式 `orthonormalize` 修正六位小数旋转矩阵，默认仍严格 1e-7。 |
| [BUG-163](work-items/BUG-163.md) | P2 | 待规划 | 未排期 | 圆角前置读取引用边弧半径，`size >= radius` 时给出排除建议。 |
| [BUG-164](work-items/BUG-164.md) | P2 | 待规划 | 未排期 | 装配阵列/刚性组，替代 269 个独立实例展开。 |
| [BUG-165](work-items/BUG-165.md) | P1 | 待规划 | 未排期 | 多实体 B 样条共享顶点或合并，解决内核判未闭合。 |
| [BUG-167](work-items/BUG-167.md) | P1 | 待规划 | 未排期 | 新增 `creo_replace_component`，换版保留约束并核验体积/重载。 |
| [BUG-168](work-items/BUG-168.md) | P1 | 待规划 | 未排期 | 统一会话真相源、`open_file` 冲突出口、只读导出不占写锁。 |
| [FEAT-072](work-items/FEAT-072.md) | P1 | 部分交付 0.35.6；真实 ID A→A 与 Creo 9/12 未排期 | 0.35.6（选定与候选列表已交付）；余项未排期 | 只读候选列表（进程级、明确标注不可识别）+ 进程内 `session_id` 选定（无需重启、不写 config）+ 失效 ID 不回落，已随两个状态工具发布；实机已验证单会话基线、错误 ID、清除、候选列表，以及双 Creo 现场的 -36/`selection_required` 与关闭多余会话后自动恢复。剩：真实 ID 的 A→A、Creo 9/12。 |
| [FEAT-073](work-items/FEAT-073.md) | P2 | 已交付 0.35.6 | 0.35.6（已交付）；WorkBuddy 黑盒与 Creo 9/12 未排期 | 有界批量只读质量属性，沿用单通道。2026-11-22 新增 `creo_get_mass_properties_batch`（工具 110→111）：1–16 模型、10–600 s 预算、逐项回执与 `error_kind`、坏 id/查询失败不吞掉其它项、busy/超时停止后续项；Creo 10 实机 15/15（两件 4000/1000 mm³ 一次批量、混入两个坏 id 仍保留两个好读数、17 项与重复项提交前拒绝、what-if 31.4/7.85 g、revision 不变），补验 11/11（16 项满批 131.188 s/180 s、真实 `toolkit_busy`、真实在飞超时且作业随后自行完成）。剩：120 s 全窗口超时、WorkBuddy 黑盒、Creo 9/12。 |
| [DEV-094](work-items/DEV-094.md) | P1 | 部分交付 0.32.0（六项离线子项与 `revolve_axis_plane_relation` 已实施；同圆多弧段、容差对照、双 R20 与回转轴四档已实机回归） | 0.32.0（子项已交付） | 其余实机回归、圆弧保形、Arm7 区域切除、G2 几何证据、实体边链与嵌套子装配 |
| [DEV-092](work-items/DEV-092.md) | P1 | 部分交付 0.30.0（T0/T1/T2/T4 软件层完成；T3 查证；T5 待输入） | 未排期 | Creo 13.4/0.26.0 装配反馈已对照 0.27.0；SDK 原包/433 头文件逐项校验通过。T1 容差贯通（见 BUG-133）、T2 列约定、T4 约束整组替换说明与阶段化诊断已实现并通过离线回归。剩：T3 逐实例 bbox/逐面面积需实现并实机测量；T5 缺说明书 8.2/8.5、9 件模型与 22 条引用；产品执行器构建与 Creo 实机均未授权。 |
| [DEV-090](work-items/DEV-090.md) | P1 | 部分交付，剩余待验收 | 0.27.0（G2 实机子项）；其余未排期 | 0.25.0 已交付T1/T2/T3组合首壁/T4/T5/T6a/T6b/T8与T7诊断措辞；新反馈的方向偏差、锚点与选区分别归BUG-129、FEAT-068/069（签名已补，完整草图/API未核）。本卡续多约束求解/保存重载、parallel/distance、T7实测及黑盒，见DEV-091计划；G2 已实机验证（2026-11-17 本机 Creo 12.4：R5 圆弧 `107.3015`→G2 `80.0793 mm³`，R30 `3862.8331`→`2883.2442 mm³`，四条均 `committed` 且保存重载通过，G2 表面非圆柱、相对圆弧少 25.37%，排除静默退化），`RoundOp` 增可选 `curvature_continuous`；曲率连续性未测，Arm7 实体边与 Creo10/9 未验，Creo10不外推。 |
| [FEAT-068](work-items/FEAT-068.md) | P1 | 部分交付 0.32.0（同圆多弧段文案与判据已实机验收；倒角邻面与多约束组合仍待验收） | 0.32.0（子项已交付） | 已接通单点直边、圆边（含角度过滤）、装配选择器与解析后平面/圆柱校验；实机直边/圆边圆角、coincident+concentric 与保存重载通过。倒角邻面、61条可解性与多约束组合仍待验收。 |
| [FEAT-065](work-items/FEAT-065.md) | P1 | 已交付 0.21.0（M1/M2）、0.22.0（M3/M4）与 0.23.1（补充）子项；剩余未排期 | 未排期 | `curvature`、`normal` 及导线边界仍拒绝。待查 `ADV_VIA_CRV` 和 compact 裁剪，补验非平面邻面、两端异向相切、Creo 9/10 及 WorkBuddy 黑盒。球鼻艏外形与接船体见卡。 |
| [DEV-003](BACKLOG_COMPLETED.md#legacy-dev-003) | P2 | 待规划 | 未排期 | 整理 C++ 的执行上下文、模块接口和资源由谁创建、释放，再用受影响的 SDK 构建并运行原生测试。 |
| [DEV-004](BACKLOG_COMPLETED.md#legacy-dev-004) | P2 | 待规划 | 未排期 | 在 DEV-003 完成后，让各模块可以独立编译，并整理原生测试目录。检查构建缓存、安装、保存重载和失败回滚。 |
| [DEV-005](BACKLOG_COMPLETED.md#legacy-dev-005) | P2 | 待规划 | 未排期 | 按工具和参数用法记录本机哪些测过、哪些没测，并注明真实环境，同步安装和能力说明。其他环境收到具体反馈再补；不要求双版本验收，也不能拿“82 工具测过”的汇总代替每种用法的兼容性测试。 |
| [DEV-006](BACKLOG_COMPLETED.md#legacy-dev-006) | P2 | 待规划 | 未排期 | 按工具分支补成功/非法输入、真并发与保存重载；需对应 SDK/种子/UDF 环境，黑盒单列。 |
| [DEV-007](BACKLOG_COMPLETED.md#legacy-dev-007) | P2 | 待规划 | 未排期 | 复用 DEV-006 的发布回归清单，按环境记录；模拟/本地直调不代替公开 MCP。 |
| [DEV-008](BACKLOG_COMPLETED.md#legacy-dev-008) | P3 | 待规划 | 未排期 | 查清旧清单第 5/6/7/9 项分别来自哪里、现在归哪个任务，补上对照关系。来源是 NEXT_STEPS_025 的“完善建议 5”。 |
| [DEV-009](BACKLOG_COMPLETED.md#legacy-dev-009) | P2 | 待规划 | 未排期 | 按模块分别整理代码格式，每批完成后做回归检查，不自动增加历史问题的豁免项。2026-10-14 的历史统计为 67 条 Ruff 问题、36 个 Python 和 14 个 C++ 文件，见历史记录。 |
| [DEV-031](work-items/DEV-031.md) | P2 | 待规划 | 未排期 | 先澄清履带TXT的相位、闭合、近似与容差，再分步安排63站/90凸台、性能和恢复；报告−1.46%偏差仍未满足±1%，本条不直接建模。 |
| [DEV-056](work-items/DEV-056.md) | P2 | 待规划 | 未排期 | job/驱动统一记录 worker SHA256 与 build stamp；已有 service/loader 指纹不重复开发。 |
| [DEV-057](work-items/DEV-057.md) | P3 | 待规划 | 未排期 | 原 BCG 输入仍缺；凹圆棱替代例已验，补原案及超薄几何规则裁定。 |
| [DEV-058](work-items/DEV-058.md) | P3 | 待规划 | 未排期 | WorkBuddy 提示词需按当前契约更新，公开 MCP 黑盒尚未执行；不以开发者证据替代。 |
| [DEV-059](work-items/DEV-059.md) | P3 | 待规划 | 未排期 | 核实旧 22 项环境 errors 是否仍存在；余下统计校验与计划状态规范，历史清理已完成。 |
| [DEV-063](work-items/DEV-063.md) | P3 | 待规划 | 未排期 | compact erase 摘要和预览矩阵 false 的说明待补；full 字段不裁剪。 |
| [FEAT-002](BACKLOG_COMPLETED.md#legacy-feat-002) | P2 | 待规划 | 未排期 | 遇到 DLL 提示等需要人工处理的情况时，说明正在等什么。测试等待超时后，任务上下文是否保留、相关模块能否清理。 |
| [FEAT-003](BACKLOG_COMPLETED.md#legacy-feat-003) | P2 | 待规划 | 未排期 | 支持并测试带单位的关系式，例如 `8[mm]`。确认它能真实驱动尺寸、带动相关参数变化，并保留用户对单位的检查设置。 |
| [FEAT-011](BACKLOG_COMPLETED.md#legacy-feat-011) | P2 | 待规划 | 未排期 | 增加复合轨迹、可变截面和螺旋扫掠，分别明确范围并测试。 |
| [FEAT-013](BACKLOG_COMPLETED.md#legacy-feat-013) | P2 | 待规划 | 未排期 | 增加剖视、局部放大、装配图和 BOM（物料清单），逐项检查模型变化后图纸能否同步更新。 |
| [FEAT-015](BACKLOG_COMPLETED.md#legacy-feat-015) | P3 | 待规划 | 未排期 | 评估模具、NC 加工和仿真能力，先选一个最小场景做完整流程，暂不承诺支持全部模块。 |
| [FEAT-016](BACKLOG_COMPLETED.md#legacy-feat-016) | P2 | 待规划 | 未排期 | 增加翼型凸度和 NACA 四位数系列，检查能否通过原生参数编辑，并验证实际几何。 |
| [FEAT-017](BACKLOG_COMPLETED.md#legacy-feat-017) | P2 | 待规划 | 未排期 | 分别复现并测试布尔、曲面和拔模中尚未测过的用法，再决定扩大哪些支持范围。 |
| [FEAT-021](BACKLOG_COMPLETED.md#legacy-feat-021) | P1 | 待规划 | 未排期 | 设计受控取消任务，先说明 queued、running、unknown_outcome 各能否取消，再检查执行器和模型状态。不能安全中断时说明原因。取消后要检查最终状态、保存点、revision、锁和下一次任务是否正常；不能把杀 worker 或清 pending_job 当作取消成功。与未知结果恢复分别验收，任务状态名称不表示当前已有排队能力。 |
| [FEAT-024](BACKLOG_COMPLETED.md#legacy-feat-024) | P3 | 待规划 | 未排期 | lookup_constants 没找到结果时，说明没有匹配，并提示可用前缀。测试不存在的前缀、空条件、合法前缀及旧返回规则；保留正常命中的行为。当前按体验改进处理，不直接把空字典认定为缺陷。 |
| [FEAT-025](BACKLOG_COMPLETED.md#legacy-feat-025) | P2 | 待规划 | 未排期 | 评估 creo_loft 在回调未就绪时，能否用 2～6 截面种子完成部分操作。先说明支持哪些截面和模式、怎样保留模型身份，再检查已有特征、编辑、revision、保存重载和失败恢复。种子能新建零件，不代表能追加到已有零件；不自动加载 DLL 或改变策略，也不预先承诺实现成本低。 |
| [FEAT-026](BACKLOG_COMPLETED.md#legacy-feat-026) | P3 | 待规划 | 未排期 | 提供 create_feature_tree 能运行的最小 dict 示例，说明 dump XML 能否转换或导入。先让示例建模、参数、几何和重载通过，非法树能指出问题元素，再评估导出后重新导入。无效示例失败不能证明工具不可用。 |
| [FEAT-028](BACKLOG_COMPLETED.md#legacy-feat-028) | P3 | 待规划 | 未排期 | 评估一次性 create_plate 的注册/后续编辑范围；不能把无 model_id 产物当受管源件。 |
| [FEAT-032](work-items/FEAT-032.md) | P2 | 待规划 | 未排期 | 评估原生沿曲线阵列：先简单平面，再闭环弧长、相位、切向、种子计数和跳站，最后履带63站与多特征；多次切除不算原生阵列验收。 |
| [FEAT-037](work-items/FEAT-037.md) | P3 | 待规划 | 未排期 | 先补参数误写的最小输入，再明确模型/特征参数目标与同名规则，评估少量建议；不自动猜改，验证关系、revision及重载。 |
| [FEAT-038](BACKLOG_COMPLETED.md#legacy-feat-038) | P2 | 待规划 | 未排期 | 提供不建立 Toolkit 连接的安装自检路径：校验部署产物与配置一致性（常量表、执行器与源码指纹、种子哈希与清单、protk/loader 注册文件），让按约束停止 Toolkit 连接的受限环境也能确认安装正确性，不必冒卡死风险连 Creo。先确定自检覆盖哪些项、怎样判定"一致"，以及自检通过与实机就绪的关系（自检通过不等于通道可用）。来源见Creo 10 反馈，关联 FEAT-022。 |
| [FEAT-040](work-items/FEAT-040.md) | P2 | 待规划 | 未排期 | 核对SDK后评估变半径表与收尾控制，补真实冲突边/可行半径诊断；恒定半径行为及回滚保持，与 FEAT-039 联动。 |
| [FEAT-041](work-items/FEAT-041.md) | P3 | 待规划 | 未排期 | 评估可选输出目录与预览/导出视角、正交投影；保持默认行为，输出目录不开放任意写路径。 |
| [FEAT-049](work-items/FEAT-049.md) | P1 | 待规划 | 未排期 | 显式目标参考约束克隆；核现有六类回放，不重复实现；完整快照/映射尚未交付。 |
| [FEAT-050](work-items/FEAT-050.md) | P2 | 待规划 | 未排期 | 冻结基准和显式映射后比对组件集、位姿、约束、包络/体积，缺数据标未验证。 |
| [FEAT-054](work-items/FEAT-054.md) | P2 | 待规划 | 未排期 | 待裁定四带几何偏差与求解路线，再推进全叶片/轮毂阵列；缺原始四带输入。 |
| [FEAT-060](work-items/FEAT-060.md) | P2 | 待规划 | 未排期 | 骨架驱动首壁参数；依赖 FEAT-059 真实骨架，先冻结日志/依赖闭包与 revision 契约。 |
| [FEAT-061](work-items/FEAT-061.md) | P2 | 待规划 | 未排期 | 单层受管装配配置切换/抑制恢复；保留身份、约束和位姿，尚未实施。 |
| [FEAT-062](work-items/FEAT-062.md) | P2 | 待规划 | 未排期 | 独立零件 rename/derive；统一名称冲突、身份与检查点恢复，尚未实施。 |
| [FEAT-064](work-items/FEAT-064.md) | P3 | 待规划 | 未排期 | 受管世代清理 inspect/apply；冻结证据/幂等与引用保护后实施，不自动删除。 |
| [FEAT-086](work-items/FEAT-086.md) | P1 | 待规划 | 未排期 | surface_loft 截面/导线接受 `curve_chain`；先查 SDK 合成接口，不可行则交付明确拒绝。 |
| [FEAT-087](work-items/FEAT-087.md) | P1 | 待规划 | 未排期 | 按重建镜像特征的一等操作，公开反射帧规则；保留 `PRO_FEATURE` 挂死拒绝。 |

## 近期动态

2026-11-28（0.50.0 MINOR，公开工具 112）：基于 v0.49.0 回填基线解决[三份 0.48.3 外部反馈](validation/feedback-0.48.3-2026-11-28/SOURCE_MANIFEST.json)，交付 [BUG-202](work-items/BUG-202.md)–[BUG-209](work-items/BUG-209.md)、[DEV-113](work-items/DEV-113.md)、[FEAT-094](work-items/FEAT-094.md) 与 [FEAT-095](work-items/FEAT-095.md)，并完成 [BUG-153](work-items/BUG-153.md) 精确 B 样条去料基准与 [FEAT-082](work-items/FEAT-082.md) 多视角预览复验。本机 Creo 10.0.0.0 完成第一/三批、四项回归对照与第二批冷启动/前置拒绝/种子矩阵实机验收；交互桌面手动启动回调后三项（已加载最小 `creo_loft`、`resident_panel` 100 mm² 曲面与已有零件追加）、外部 `scripts/gear10.json`、Creo 9/12.4 与 WorkBuddy 黑盒单列未测。[版本说明](release-notes/RELEASE_NOTES_0.50.0.md) · [发布记录](validation/RELEASE-0.50.0.md)

2026-11-28（0.49.0 MINOR，公开工具 112）：逐字节归档 0.47.1 / 0.48.3 两份反馈原件至 [feedback-0.47.1-0.48.3-2026-11-27](validation/feedback-0.47.1-0.48.3-2026-11-27/SOURCE_MANIFEST.json)，交付 [BUG-198](work-items/BUG-198.md)（Windows JSON 原子替换瞬时 WinError 5 重试与 `.tmp` 清理）、[BUG-199](work-items/BUG-199.md)（runner Job Object 实测与 Explorer 脱离、`owner_liveness`、`cancel_job` PID/128、`confirm_panel_closed` 死所有者解锁及模态框观测）、[BUG-200](work-items/BUG-200.md)（可配自适应 `utility_worker_timeout_seconds` 及超时强杀证据）、[BUG-201](work-items/BUG-201.md)（`direct_blend_callback.readiness` 口径统一、`startup_in_progress` 消歧、UTF-8 stderr 与提示补全）与 [FEAT-093](work-items/FEAT-093.md)（`ExtrudeOp.depth2` 双向不等深拉伸、`datum_planes[].name` 与 `cut_scope` 实体级边界说明）；本机 Creo 10.0.0.0 实机与离线门禁全通过。 [版本说明](release-notes/RELEASE_NOTES_0.49.0.md) · [发布记录](validation/RELEASE-0.49.0.md)

2026-11-28（0.48.4 PATCH）：[DEV-112](work-items/DEV-112.md) 精简开发入口及七条台账摘要，统一 Toolkit 授权与发布后核对入口。[版本说明](release-notes/RELEASE_NOTES_0.48.4.md)

2026-11-27（0.48.3 PATCH，公开工具 112）：交付 [DEV-108](work-items/DEV-108.md)（修复 Windows CI 同刻度 `retry_id` 重复与旧快照误采用）、[DEV-109](work-items/DEV-109.md)（台账逐组计数校验）、[DEV-110](work-items/DEV-110.md)（校正本机 MCP 联调路径 `D:\my\MCP_CREO_MechDog` 与运行期核查指引）、[DEV-111](work-items/DEV-111.md)（台账近期动态去重与活跃非冻结文档链接/锚点 CI 门禁），并在 Creo 10.0.0.0 补齐 [BUG-131](work-items/BUG-131.md) `revision == 0` 新装配收尾（`abandon_new` / `ack_failure` / `revision == 1` 拒绝负对照）实机验收；`BUG-017`/`BUG-034` 与 `BUG-131` 23 组件 `hom_1` 挂死原案仍因缺少外部材料保留在 `仍需修复`。 [版本说明](release-notes/RELEASE_NOTES_0.48.3.md) · [发布记录](validation/RELEASE-0.48.3.md)

2026-11-27（0.48.2 PATCH）：[DEV-107](work-items/DEV-107.md) Windows CI 在整个 Python 作业中启用 UTF-8，使离线检查能输出中文 JSON 并继续运行全量单测。 [发布记录](validation/RELEASE-0.48.2.md)

2026-11-27（0.48.1 PATCH，公开工具 112）：复核 0.47.0 反馈原件补修 [BUG-196](work-items/BUG-196.md) 两处快照边界（分拆 `inspection_ref` 零件快照的 `surfaces[].area_mm2` 过期检出与装配体 `merged_counts` 误报），并合入交付 [DEV-106](work-items/DEV-106.md)（三批台账分类整理与 115 份活跃非冻结文档 364 处迁移断链修复，归档 `DEV-052`/`DEV-065`/`BUG-175`/`DEV-079` 并将 `开发中` 存量清零转入完成档案，活跃 ID 280→276）。 [版本说明](release-notes/RELEASE_NOTES_0.48.1.md) · [发布记录](validation/RELEASE-0.48.1.md)

2026-11-27（0.48.0 MINOR，公开工具 112）：归档 0.47.0 / 0.47.1 两份外部反馈原件至 [feedback-0.47.0-0.47.1-2026-11-26](validation/feedback-0.47.0-0.47.1-2026-11-26/SOURCE_MANIFEST.json)，交付 [BUG-196](work-items/BUG-196.md)（`creo_refresh_model(write_back_snapshot=True)` 无版本破坏只读回填历史模型快照与 `model_summary` `stale_fields`/`refresh_hint`）、[BUG-197](work-items/BUG-197.md)（`bounding_box_status.basis="tessellated_solid_union"` 与真实 `query_code`、`compact_job` 巡检摘要填充、`round`/`chamfer` 参数示例及 `session_health` 连接/保存双子块），并将 [DEV-105](work-items/DEV-105.md)（`v0.47.0`/`v0.47.1` 发布后核对实证回填与 `check_release_records.py --post-release` 门禁）随版收口转入完成档案（活跃 ID 281→280）；同步随主干合并合入 [DEV-103](work-items/DEV-103.md) 校验冷数据归档剥离（提交 `bc794edd`，14 份大体积文件共 18.40 MB 转存归档 Release `archive-validation-2026-11`）。Creo 10.0.0.0 MCP stdio 实机与离线门禁全通过。 [版本说明](release-notes/RELEASE_NOTES_0.48.0.md) · [发布记录](validation/RELEASE-0.48.0.md)

2026-11-26（0.47.1 PATCH，公开工具 112）：归档 0.46.1 外部反馈原件至 [feedback-0.46.1-2026-11-26](validation/feedback-0.46.1-2026-11-26/SOURCE_MANIFEST.json)，追加交付 [BUG-187](work-items/BUG-187.md)（主基准面偏移默认法线对齐 `frames.XY/XZ/YZ`、`datum_plane` 新增 `plane_frame` 回执、字典草图反向法线输出 `frame_warning` 与 `frames_note` 文档，本机 Creo 10 三组实机保存重载通过）并随版收口 [DEV-104](work-items/DEV-104.md)（转入完成档案，活跃 ID 279→278）。 [版本说明](release-notes/RELEASE_NOTES_0.47.1.md) · [发布记录](validation/RELEASE-0.47.1.md)

2026-11-26（0.47.0 MINOR，公开工具 112）：交付 [BUG-194](work-items/BUG-194.md)（`auto` 求解器恢复将 `b_spline`/`arc`/`spline`/`ellipse` 路由到 `autodim`，失败回执补 `dimensioning='autodim'`/`geometry_tolerance_mm=<cap>` 自助提示）、[BUG-195](work-items/BUG-195.md)（`bounding_box_status` 披露面细分内缩误差界、空件平面报错指向 `datum_plane`、边选择器歧义附 `adjacent_surfaces` 与新出口）、[FEAT-091](work-items/FEAT-091.md)（`round` 期望凹凸/加减料断言与 `sheetmetal_base_flange` `envelope_mm`）与 [FEAT-092](work-items/FEAT-092.md)（只读 `creo_server_info` 与 `region.closed_chain`）；Creo 10.0.0.0 10 项实机与 4548 项单测全过。 [版本说明](release-notes/RELEASE_NOTES_0.47.0.md) · [发布记录](validation/RELEASE-0.47.0.md)

2026-11-26（0.46.1 PATCH，公开工具 111）：交付 [BUG-193](work-items/BUG-193.md) 的提交前零锁 callback 预检——`callback_admission_status()` 零锁判定 `loft` / `surface_loft` 准入，未就绪时在建 job 与取 Toolkit 锁之前直接拒绝；Creo 10.0.0.0（`release_numeric=42`）未加载零锁/零作业拦截、启动回调自动准入与加载态建模保存重载全链路实机通过。另交付 [DEV-103](work-items/DEV-103.md) 文档目录治理。 [版本说明](release-notes/RELEASE_NOTES_0.46.1.md) · [发布记录](validation/RELEASE-0.46.1.md)

2026-11-26（Creo 10 / MCP 0.45.2，外部 WorkBuddy）：补录[独立曲面回归](validation/CREO10-PANEL-LOFT-JOIN-0.45.2-2026-11-26.md)。两段放样、合并、保存重载通过；X=80 共享边 G1 负对照为 22.4332°，合并前 0.01 mm 间隙未验收。另见 [BUG-193](work-items/BUG-193.md) 的 [0.46.0 黑盒补验](validation/BUG-193-CREO10-WORKBUDDY-0.46.0-2026-11-26.md)：未加载态两入口前置拒绝，加载后 resident_panel 成功并重载；Creo 9 / 12.4、加载态普通放样建模与瞬时通道锁未测。

2026-11-26（0.46.0 MINOR，台账 272→276，公开工具 111）：逐字节归档 0.45.1 外部反馈原件至 [feedback-0.45.1-2026-11-26](validation/feedback-0.45.1-2026-11-26/SOURCE_MANIFEST.json)，交付 [BUG-192](work-items/BUG-192.md)（`draft` 基准面/实体面方向说明与 `material_effect`）、[FEAT-090](work-items/FEAT-090.md)（近容差 `arc-arc` 端点焊接与草图公开工具参数）、[BUG-193](work-items/BUG-193.md)（`loft`/`surface_loft` 统一 `runtime_ready` 披露与 before-job callback 预检）、[DEV-102](work-items/DEV-102.md)（`creo_capabilities` 操作列表口径与 `region.interior_point_yz_mm` 文档）。 [版本说明](release-notes/RELEASE_NOTES_0.46.0.md) · [发布记录](validation/RELEASE-0.46.0.md)

2026-11-26（0.45.2 PATCH，公开工具 111）。[DEV-002](work-items/DEV-002.md) 第四、五批交付 Python 服务包化、新安装入口与 AI Agent 兼容说明。 [版本说明](release-notes/RELEASE_NOTES_0.45.2.md) · [发布记录](validation/RELEASE-0.45.2.md)

2026-11-25（BUG-130 / 0.45.1）：复核 14 m 球鼻艏 STL 的细化、闭合和偏差。保留只读导出及六轮默认上限，补齐导出网格诊断、源件 SHA/revision 对照和偏差采样，另以十二轮诊断验证深细分边界。使用本机可用的 Creo 10.0.0.0 和匹配 SDK，按实际结果记录 0.1 mm 目标及未测平台。见 [BUG-130](work-items/BUG-130.md)。

2026-11-25（0.45.0 MINOR，公开工具仍 111）。同一候选在 Creo 10 复跑六项反馈修复，共 57 个几何作业和四种启动场景。三项按预期拒绝的几何作业完成回滚，其余几何作业成功。台账 272 项，历史未测范围见各卡。 [版本说明](release-notes/RELEASE_NOTES_0.45.0.md) · [验收记录](validation/RELEASE-0.45.0.md)

2026-11-25：[BUG-170](work-items/BUG-170.md#2026-11-25-启动探针暂态复核) 修正启动 `-4` 错误释义与暂态诊断，直连与复核共用截止时间。Creo 10 冷启动自然复现 `-4 → 0`，受控用例覆盖持续不可达及单次失败后超时。

2026-11-25：[BUG-094](work-items/BUG-094.md#2026-11-25-基准面角度与位置复核) 在 Creo 10 验证 RIGHT 面绕实际 `+Z` 和 `−Z` 的 ±54° 法向、偏移位置和重载结果，并记录 0.9.0 与 0.44.0 反馈中的角度符号差异。

2026-11-25：[BUG-102](work-items/BUG-102.md#2026-11-25-拔模方向回归) 修正拔模方向映射与回执。Creo 10 复现 Ø6×3 凸台默认加料，修正后正负角和反向组合以及显式基准轴均通过保存重载和实体锥度核验。

2026-11-25：[BUG-108](work-items/BUG-108.md#2026-11-25-默认草图漂移回归) 默认草图坐标修正。Creo 10 复现 R12 单圆平移 0.002 mm，`auto` 优先坐标标注，超差回滚。创建、原位替换与保存重载通过。

2026-11-25：[FEAT-078](work-items/FEAT-078.md) 新反馈修正。Creo 10 复现切齿、贯穿槽、回转壳的旧轮廓失真，改用实际实体面测量装配坐标系包围盒。

2026-11-25：登记 [BUG-191](work-items/BUG-191.md)。Creo 10 用原生关系夹具复现加料净体积下降仍保存，并验证保存前保护、整单回滚、revision 不变及重载原几何。外部摆杆原案仍待同输入复现。

2026-11-24 及更早历史动态已归档至 [历史时间线](archive/BACKLOG_TIMELINE_2026.md)。

## 历史资料

<a id="workbuddy-030-全量实测问题映射"></a>

[完成档案与来源索引](BACKLOG_COMPLETED.md)、[开发规则](DEVELOPMENT.md)。历史版本说明和 docs/validation 原件保持路径；日期交接快照不承担当前待办维护。
