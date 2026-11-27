# FEAT-068：TXT 几何锚点与装配引用接通

## 当前摘要（2026-11-16）

分类：**部分交付 0.32.0**（同圆多弧段文案与判据已实机验收；倒角邻面与多约束组合仍待验收）。类型：功能 / 引用契约接通。优先级：P1。目标版本：0.32.0（子项已交付）。

本批：0.26.0 交付子项（部分交付）加单点有限直边、圆边 center/radius/axis（+圆弧角度点）、装配选择器准入与解析后平面/圆柱校验。实机：单点直边圆角 id 137、R10 圆边在 4 段圆弧中唯一定位 id 55 并圆角、coincident+concentric 销 z=10.0，均保存重载；见 [实机验收](../archive/development/LIVE-ACCEPTANCE-0250-2026-11-16.md)。倒角邻面与 61 条完整集未验。2026-11-16 追加：6 条边锚点中 4 条圆角可准入（Arm2 n4 R3、Arm3 n3 R3、Arm6 n3 R40、Lateral n7 R90）；`Hom n7/n8` 8 mm @ 70° 缺 `angle_reference` 仍拒绝。见 [A2/A0 数据准入](../archive/development/A2-A0-ADMISSION-2026-11-16.md)。

来源：[0.25.0装配反馈原件](../validation/feedback-0.25.0-2026-11-16/assembly.md)，关联 DEV-090 T1/T5、BUG-036、FEAT-049；范围见[分批计划A0/A1](../archive/superpowers/plans/2026-11-16-feedback-0250.md)。

当前已有原生装配resolve与几何选择器；coincident/concentric在Python关系白名单拒绝geometry_selector。报告的假面ID失败只证明到达原生路径，不证明真实配合成功。先接平面/圆柱面唯一解析，之后有依据地扩点/草图点/特征面引用。

## 范围

复用现有选择器、模型/装配坐标和实例路径，解析后验证真实对象类型；不新建调度或TXT全格式导入器。circle:near单点缺语义时不得猜轴、半径、最近面；零/多匹配拒绝并保留候选。

独立A0子包覆盖4条圆角/2条倒角的单点边锚点与圆边定位。Hom角度倒角缺angle_reference，须给真实邻面候选并按源条件唯一确定；仅有角度不能任选两邻面之一。选边成功与圆角/倒角几何验收分别记录，未知曲线或缺参考面保持拒绝。

61条含24共面、26同心、6平行、4距离、1齿轮；前50条也只是待逐条核对的候选，不能承诺接通后全可解。原始TXT和完整61条未随附。多约束完整集合、parallel/distance、gear分别归DEV-090剩余范围。

## 验收

离线覆盖有限边单点/圆边/歧义、倒角缺面、关系准入、实际类型拒绝和compact/full诊断。获准后先用独立边/邻面算例核圆角与倒角尺寸，再用已知平面/圆柱面双零件，含旋转平移、同源双实例和共面歧义，验证约束类型/引用、实际位姿、保存重载、失败回滚与revision。独立位姿目标不由underconstrained标志代替。

当前仅规划，未实施或本次实机验收。

## 2026-11-20 追加：同圆多弧段拒绝文案（0.27.0 反馈，已实机验证）

现象：一条物理圆边（rim）被 Creo 拆成多段同圆心、同半径的圆弧，圆形 edge 选择器的圆心+半径过滤会全部命中，旧文案统一建议“use a smaller tolerance_mm or an anchor that belongs to exactly one edge”。这类弧段按构造就都通过过滤，缩小公差在数学上不可能收敛到一条。

改动（`native/geometry_selectors.cpp`）：`selector_edge_error` 增加 `bool same_circle = false` 形参；`match_geometry_edge_selector` 对每个命中弧段保留实测圆心与半径，只有全部命中落在同一圆（半径差与圆心分量差均 `<= 1e-6 mm`）时才判 `same_circle`。同圆情形改报 `... matched <n> arcs of one circle (ids ...)`，并给出两条可行路径——`point_mm` 指定目标跨度上的点，或 `{kind:'edge',id:N}` 直接选一段。**未把 `circular` 标志直接当作同圆判据**：圆心/半径过滤生效但命中两个不同圆（容差过宽）时，缩小公差仍然有效，仍保留原建议。

离线验证：`python bridge.py build` 编译通过（`build/creo_worker.exe`）；`tests/unit/test_geometry_selectors.py::FEAT068SameCircleRemedySourceTests` 2 例锁定文案、几何判据与调用点，`tools/dev_check.py` 全绿（`unit_tests=passed`，4129 例；lint 0、unformatted 0，clang-format 已按 `.clang-format` 格式化该文件）。

实机验证（2026-11-20，Creo 12.4.0.0，经用户确认后执行）：新驱动 `tools/test_feedback0270_same_circle.py` 用“XY 上 x=20..30、y=5..10 矩形绕 X 轴回转 360°”的圆管作夹具，圆管体积 2356.194490192345 mm³ 与分析值一致且保存重载通过；`creo_inspect_model` 显示四个圆边各被回执为 2 段弧（x=30 外圆 id 72/90、x=30 内圆 70/88、x=20 侧 68/86 与 74/92），即“同圆多弧段”可稳定复现。三次修改型提交都带 `expected_revision=1`（建型后 revision 1）。

- 只给 `radius_mm`+`center_mm`：job `failed`，回执为 `geometry_selector edge circular matched 2 arcs of one circle (ids 72, 90); the rim is reported as several arcs with the same centre and radius, so a smaller tolerance_mm cannot separate them - add point_mm on the span you want, or select one arc with {kind:'edge',id:N}`；两个 id 均列出，`saved_file_reloaded_and_verified=false`，revision 仍为 1、体积仍为 2356.194490192345 mm³，即失败回滚且几何未变。
- 加 `point_mm`（弧跨度中点）：job `succeeded`，`saved_file_reloaded_and_verified=true`，revision 2，体积 2304.668647961009 mm³（去掉 51.5258 mm³）。
- 直接用 `{kind:'edge',id:90}`：job `succeeded`，保存重载通过，revision 2，体积同为 2304.668647961009 mm³，与 `point_mm` 结果一致。

两份运行报告：`build/feedback0270_same_circle/20261120T093721_cfb2532c/`（首轮，未传 `expected_revision`）、`build/feedback0270_same_circle/20261120T094503_e6397ed5/`（修正 revision 取值后重跑，含 `expected_revision_sent=1`）。

环境与身份：Creo 12.4.0.0，执行器由本次源码通过 `bridge.py build` 重新编译；源码提交 `c21651262b8efc442602b50d1d6a09b01abe0b69` + dirty 工作区（未提交），`build/development_check.json` 记录 `checked_source_sha256`。行为边界：未启动/重启 Creo，未清 `toolkit.lock` 或保护状态，未改用户模型，未做故障注入。

异圆心对照（同日，`tools/test_feedback0270_task4.py`，报告 `build/feedback0270_task4/20261120T103150_7b111d87/`）：底板加两个 R20 凸台，顶圆边实测为 `[-40,0,20] r=20 → id 99/100` 与 `[40,0,20] r=20 → id 101/102`。这两组是**不同的圆**（圆心差 80 mm），命中两组时不会进入同圆分支；用 `center_mm+radius_mm+point_mm`（点取实测弧跨度中点）两次 R2 圆角都 `succeeded`/`committed`，体积 121132.74122871833 → 120921.81921275367 mm³，保存重载通过。这组数据同时说明：同圆判据只在同一圆内生效，异圆心消歧仍由圆心过滤 + 点锚定负责。

同圆判据的容差对照（同日，`tools/test_feedback0270_same_circle.py` 扩展，报告 `build/feedback0270_same_circle/20261120T105029_4af786ea/`）：夹具改为实心圆柱（草图 x 0..10、y 0..10 绕 X 轴回转），体积 3141.5926535897925 mm³ 与分析值一致；两端圆边实测为 `[10,0,0] r=10 → id 90/72` 与 `[0,0,0] r=10 → id 74/92`，即**同半径、异圆心**的两个圆。

- `tolerance_mm=20`（宽到两圆都进）：`matched 4 edges (ids 90, 72, 74, 92); use a smaller tolerance_mm or an anchor that belongs to exactly one edge`——仍是原建议，没有误报“同圆”。
- `tolerance_mm=0.01`（只命中 x=0 圆）：`matched 2 arcs of one circle (ids 74, 92); ... smaller tolerance_mm cannot separate them - add point_mm ...`——切到同圆专用文案。

两次失败都 rollback，体积保持 3141.5926535897925 mm³。这组对照证明判据不会把“容差过宽命中的两个不同圆”误判成同圆，而缩小公差在该场景仍是正确建议。

未验证：反馈方 266 实体回转件原件未随附，本夹具只证明“同圆多弧段”这一类，不外推到其他建模路径拆出的弧段；同圆判据取 `1e-6 mm` 绝对阈值，对“同一圆边两段弧因测量噪声出现微小差异”的方向未构造算例（现有数据里同圆两段弧的实测圆心与半径完全一致，取任何小阈值都成立）。报告原始 R220 位于 x=±54 的算例仍未复现，本轮用 R20 双凸台与 R10 圆柱等价覆盖“同半径异圆心 + 分段圆边”的组合。
