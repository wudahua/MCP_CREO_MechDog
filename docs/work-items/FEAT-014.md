# FEAT-014：钣金折弯释放与四壁能力

日期：2026-10-28（Asia/Shanghai）补工作卡，沿用既有 ID。类型：功能。优先级：P2（既有台账）；状态：**折弯与方向已实机成立，四壁仍止于第二道，释放无可观测几何**（2026-10-29 第三轮：第一道 `-1` 的根因已定——验收基体实为 232 mm 厚板、所选边不在壁面上——已改基体并在准入层拒绝该类边；修正后两道折边 succeeded 但几何是平铺延伸而非折弯，第三道挂起；四壁与释放能力未完成。2026-10-29 第四轮：截面已按库存 `flange_shapes` 重建（单线、无 centerline、腿在父壁法向）并重建执行器，但实机被会话消失阻塞，折弯仍**未验证**。2026-10-29 第六轮：`direction` 开关从 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM` 改到 `PRO_E_SMT_FLANGE_SEC_FLIP` 后，`tools/test_flange_direction.py --live` 两例均 `saved_file_reloaded_and_verified=true`、rev 2，默认向外（+X 顶边 +Z 79 mm）、`flip=true` 反向（−Z 79 mm），报告 `passed=true`；四壁在第二道后仍于 `f_ny` 回滚（rev 不变、原码保留），1×1 矩形释放体积差 0.000000、无缺口面）。目标版本：未排期。

来源：[统一台账](../BACKLOG.md)既有 FEAT-014 行、[0.7.0 R1 S3](../validation/feedback-0.7.0-2026-10-28/2026-10-27_CREO_0.7.0_钣金增料与四壁折边仍未修复验收报告.md)、[逐章映射](../validation/feedback-0.7.0-2026-10-28/MAPPING.md)。关联 [BUG-047](BUG-047.md) 的折边方向/材料侧缺陷与 [BUG-032](BUG-032.md) 的有效薄底板契约。

## 目标与阶段边界

既有目标包含钣金止裂槽、成形、折边及过渡；本批先将“四壁盒失败定位”和“新增释放/角部能力”拆为两阶段。T05 使用经 BUG-032/T03 确认的 185×232×1 mm 底板、h80/R2.54/Y0.5，按真实几何重新选择边，逐道与同一计划对照，核对方向、材料侧、父体、元素树、失败原码、revision 与回滚。报告中前两道 ±X 成功、第三道 −Y `-1`；角部冲突是报告人的推测，不能先定为根因。`rolled_back` 的前项须重建，不能仅续跑后半段。

若 T05 证据表明需新增 relief/角部规则，T11 才设计最小支持类型及宽深、端部、厚度和兼容默认值，贯通 schema/原生/编辑。若是既有引用或参数缺陷，按 BUG-047/T05 的证据最小修复，不借 FEAT-014 扩成无来源的新功能。更广的止裂槽、成形和过渡仍开放，不因四壁子项完成而全卡关闭。

## 验收与环境

T05 可交付可复现/未复现结论与根因证据，但只有四壁原生特征全成功、角部几何独立核对、展开/折回、尺寸编辑、revision、保存重载及失败回滚均通过，才可宣称四壁能力完成。报告样本的边 104—107 不能硬编码为通用 ID；厚底板失败与独立 flip 问题分开。环境：离线 Windows x64 / Python 3.12+ / C++17；实机为本机 Creo 12.4.0.0 / 匹配 SDK，须另获指派且先确认 BUG-001 会话条件。本次 T00 只补卡，未连接 Creo 或验证几何。

## 2026-10-28：T05 离线阶段（DEV-051）

- 状态：**T05 离线调查完成 / 未复现 / 根因未定**；四壁能力仍未完成。本次未连接 Creo、未创建任何特征、无生产改动。
- 已就绪：按几何选边的四壁夹具（185×232×1 + h80/R2.54/Y0.5，`face` 显式）、逐道刷新与单计划对照、每道预期与 29 个判定字段、四条可反驳假设与判定表、厚底板首道待验分支、`--live` 拒绝的离线驱动（`tools/test_sheetmetal_flange.py`、`tests/unit/test_sheetmetal_flange.py`，单测 33/33）。
- 可离线确定的几何：四道合计新增 66 720 mm³；材料在板内侧时第三道与两条既有壁各有 ≥77.46 mm³ 角部重叠（第三道 2 个角部，下界 154.92 mm³）；前两道之后垂直边界在两端各缩短 ≥1 mm（合计 183 mm）。这些是几何预测，不是已观察到的失败原因，根因仍未定。
- T11 设计输入（未实现）：壁端折弯释放（none/矩形/扯裂/圆形、宽深、单双端）+ 垂直壁角部规则（仅释放/斜接/显式重叠）、字段落点与兼容默认；仍须在四壁 + 角部几何 + 展开/折回 + 编辑 + 重载 + 回滚闭环后才可宣称能力完成。
- 待验清单（实机）：四壁逐道创建与失败原码；材料侧/方向/父体/边有效性/原生树；单计划与逐道刷新对照；`flip` 正交；剪短 20 mm 的第三道探针；厚底板首道（依赖 T03）；展开/折回、编辑、重载与回滚。
- 验收记录见 `docs/development/DEV051-T05-ACCEPTANCE.md`。

## 2026-10-29：T11 离线实现（DEV-051）

- 状态：**离线实现完成 / 四壁与释放能力待原生验收**。本次未连接 Creo、未创建折边或释放、未展开/折回、未编辑或重载；四壁能力仍未完成。
- SDK 核对（本机 Creo 12.4 `ProSmtFlangeWall.h`）：每个弯端有独立释放复合元素 `PRO_E_SMT_BEND_RELIEF_SIDE1/SIDE2`，类型 NONE/RIP/STRETCH/RECTANGULAR/OBROUND/PARAM；深度类型含 BLIND(-4)；角部释放 `PRO_E_SMT_CORNER_RELIEF`、斜接 `PRO_E_SMT_MTR_CUTS`、边撕裂 `PRO_E_SMT_EDGE_RIP` 同在特征树中。
- 已实现（最小形状）：`sheetmetal_flange.relief` 可选对象，`type` 仅 `none`（默认，保持旧行为：两端 `PRO_BEND_RLF_NONE`）与 `rectangular`；`ends` 取 both/side1/side2；`width>0`、`depth>=0` 为绝对模型单位并固定 BLIND，不按板厚缩放；别名记录带实测板厚与 `height-radius` 角部走向算术。schema/独立工具/execute_plan/原生纵深防御与创建期编辑路径说明均已补齐。
- 明确未支持：rip、stretch、obround、param、角部释放全系、斜接、边撕裂、释放长度/角度，以及任何按几何自动选角部规则；这些组合在准入处拒绝而不是降级为 none。
- 未测（实机）：四壁真实创建与释放元素树被接受、体积增量与 `width×depth×t` 的关系、缺口相对折弯边的实际位置、单端释放、`depth ≥ h−R` 档对第三道失败的影响、展开/折回、`height` 尺寸编辑、删除重建改释放、revision、保存重载与失败回滚。
- T05 静态断言已按新事实同步（`bend_relief_none_both_sides` → 默认 NONE + rectangular opt-in 一组断言），不是回退或删除。
- 验收记录见 `docs/development/DEV051-T11-ACCEPTANCE.md`。

## 2026-10-29：T11 实机被第一壁阻断（未创建任何折边）

按 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md)，在手动打开的 Creo 12.4.0.0 上跑两轮四壁（§relief§ 省略 与 §rectangular/both/1x1§）：

- 第 1 轮底板作业 §796092e2085b49a7903787406c9d8879§（模型 §c34f02bd6046425caa45dc50f2762a52§，t11_relief_none_de867f）在 op index 1 就失败：§toolkit_code=-1§、§failed_stage=execute_sheetmetal_wall§，消息 “the section has 2 drawing entities (1 straight lines)”；与 BUG-032 的 T03 实机阻断同一根因（准入把草图 §PRO_2D_COORD_SYS§ 计成第二条曲线）。
- 第 2 轮未提交：同一阻断点，不重复占用通道。
- 因此四壁真实创建、每道体积增量、§relief§ 回显、第三道 §f_ny§ 是否再现 §-1§、失败回滚与 §revision§ 均未取证；也没有用四个普通拉伸块替代折边。报告 §build/sheetmetal_relief/20261029T155905_bb490653/report.json§。

下一轮：先修第一壁准入并重编译执行器，再用同一驱动原样重跑；之后再补 §corner_run§（宽 1、深 77.46）与 §ends=side1/side2§ 对照。


## 2026-10-29 第二轮实机：底板建成，第一道折边即 `-1`

第一壁准入修复后重跑 T11 两轮（relief 省略 / rect 1×1 both 1×1）：两块 185×232×1 底板都建成（42 920 mm³、rev 1、bbox `[0,-116,0]`–`[185,116,1]`），但第一道折边 `f_px`（边 id 125，+X 上边，跨度 232 mm）在两轮都失败：

- job `ef7341d546b34fa28a145771b543b1a4`（none）/ `4c172764b29f4a0d850cfd6a38b73125`（rect 1×1）；
- `toolkit_code=-1`、`failed_stage=execute_sheetmetal_flange`、`failed_toolkit_call=ProFeatureWithoptionsCreate`，消息 “Toolkit call ProFeatureWithoptionsCreate failed with code -1 during execute_sheetmetal_flange”；
- `rollback_succeeded=true`，两轮快照 rev 1→1、体积 42 920→42 920（`rolled_back=true`），无 `relief` 回显。

与 0.7.0 R1 S3 原件的关键差异：原件前两道 ±X 成功、第三道 `f_ny` 才 -1；本轮**第一道**就 -1，此时还没有相邻壁、没有角部。因此 T05 的角部重叠假设不能解释本轮失败，四壁能力仍未完成，`relief` 两档也无法比较（失败早于释放生效）。报告 `build/sheetmetal_relief/20261029T161528_cc1fda94/report.json`。

下一步：用 `PRO_FEAT_CR_INCOMPLETE_FEAT` + `ProFeatureElemtreeExtract` 取回 Creo 补齐的折边元素树，与写入的树比对（flange 类型与 2D 扫掠截面的配对、`PRO_E_SMT_WALL_HEIGHT=NONE`、TAN 曲线集合在转换型壁边上的合法性、SIDE1/SIDE2 TO_END 组合）。

## 2026-10-29 第三轮实机：第一道折边 `-1` 根因（已定）与无折弯（未定）

按 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md) 与 [T05 验收卡](../development/DEV051-T05-ACCEPTANCE.md) 的实机记录：

- **`-1` 根因已定**：折边失败路径取回本实现写入的树与 Creo 用 `PRO_FEAT_CR_INCOMPLETE_FEAT` 补全的树，两者在 `PRO_FEAT_WALL`、`PRO_E_SMT_WALL_TYPE=17`、`PRO_E_SMT_FLANGE_TYPE=1`、`DEPTH_TYPE=4/4`（TO_END）、`WALL_HEIGHT_TYPE=0`（NONE）、`SHARPS_TO_BENDS`、`SEC_FLIP`、`THICKNESS_FLIP` 上逐项一致；Creo 的 `ProErrorlist` 为空。真正原因是承载对象：`ProSmtedgeContourGet(edge 125)=-8`（`PRO_TK_BAD_CONTEXT`，边不在 green/white 壁面），因为验收基体 `sheetmetal_wall(depth=1, thickness=232)` 实际是 **232 mm 厚的钣金件**（green/white 相距 232 mm、185×232 大面全是 `SIDE`）。R=2.54 折弯 232 mm 厚板不可能。
- **已改**：① 夹具基体改 `plane="XZ"` + `sheetmetal_wall(depth=232, thickness=1)`（真正的 1 mm 板，体积/bbox 不变）；② 折边入口用 `ProSmtedgeContourGet` 拒绝不在壁面上的边，消息带 `-8` 原始码与可行做法（不再以裸 `-1` 失败）；③ 截面腿按"中心线=对齐线、坐标系=贴附点"量取角度（原 `(90-angle)` 让 90° 请求得到与中心线共线的零折弯腿）；④ 失败路径保留元素树与面类型取证。
- **实机（1 mm 板）**：底板 42 920（rev 1）→ `f_px` 61 480（+18 560，rev 2）→ `f_nx` 80 040（+18 560，rev 3），两次 `saved_file_reloaded_and_verified=true`、`ProSmtedgeContourGet=0`（4 条轮廓边）。
- **未定（关键）**：两道折边是**平铺延伸**：bbox 只在 X 增长 80 mm（185→265、0→-80），Z 仍 ±0.5；体积 232×80×1 与折弯同值，体积断言无法区分。截面如何让 Creo 形成折弯仍未定；候选探针见 T11 卡"仍未决项"。
- **新阻塞**：第三道 `f_ny` 在 `ProFeatureWithoptionsCreate` 内挂起（job `bb5543fb3c66404e95172876fa1ac9aa` 仍 running、`toolkit.lock` 被占用），驱动按规则停止；四壁与释放仍未验证。

状态口径：FEAT-014 = **第一道折边可创建（根因已定并修复准入），折弯几何未定，第三道挂起，四壁与释放未完成**。不得表述为"折边已修复"或"四壁能力已具备"。

## 2026-10-29 第四轮：截面按库存形状重建，实机被会话消失阻塞

- **实机未执行**：交接前提的"新会话"不存在。2026-10-29 19:51:03 Windows 事件日志记录 `xtop.exe` `AppHangB1` 并已关闭；19:53/20:06 两次 `tasklist` 均无 `parametric.exe`/`xtop.exe`；`creo_session_status` 为 `connected=false`、`toolkit_code=-4`、`creo_process_snapshot.processes=[]`。按规则不启动/不重启 Creo、不重提、不清锁，全部实机步骤暂停（现场见 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md) §4.1）。
- **离线结论（新增）**：本机 `Common Files\text\smt\flange_shapes` 9 个库存截面全部是"1 条 line + 1 个 coord_sys + 1 个尺寸、无 centerline"；弯弧只出现在 hem 类，`i_wall` 的尺寸是腿长 `5.00` + 角度 `90.00`，即"90° 直腿 = 直壁/平铺延伸"。
- **方向约定（离线，接上一轮现象）**：上一轮 `LINE_wall 0,0 → 0,80`（草图 +y）实机得到 bbox 只增 X、Z 不变 ⇒ 草图 +y = 父壁平面内、草图 +x = 父壁法向；90° 折边必须把腿放在草图 +x。
- **已改**：`generic_sheetmetal_flange` 的截面改为单条线 `(0,0) → (h·sinA, h·cosA)` + `height` 长度尺寸、去掉 centerline，其余元素树不动；`bridge.py build` 已重建执行器，`clang-format` 通过。
- **新增驱动**：`tools/test_flange_direction.py`（单模型单折边、bbox 判定、180 s 挂起预算）与其单测；离线报告 `build/flange_direction/offline_20261029.json`。
- 状态口径：FEAT-014 = **第一道折边可创建（根因已定），折弯几何未定（第四轮改了截面但未实机验证），第三道挂起未复现，四壁与释放未完成**。不得表述为"折边已修复"。

## 2026-10-29 第六轮：方向开关落在截面侧，折弯与反向均实机成立；四壁仍止于第二道，1×1 释放无可观测几何

分支 `codex/dev051-feedback070`，HEAD `cce1922`；手动打开的 Creo 12.4.0.0 会话（PID 15156，22:05:41 由协调器拉起），`creo_startup_status` → `ready/connected=true`，`session_health=no_failure_observed`。本轮未启动/关闭/重启 Creo、未重提已受理 job、未清保护。

### A. 方向（BUG-047）

- **机制定案**：`flip` 原先写 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM`。22:06 的对照（`flip=false`→1、`flip=true`→−1）bbox、体积、方向完全相同，说明该元素不是方向开关；`ProSmtFlangeWall.h` 对该元素只列 `PRO_B_TRUE/PRO_B_FALSE`，−1 不是可用的第二个值。真正的开关是 `PRO_E_SMT_FLANGE_SEC_FLIP`（元素表："Flip Section Side"）。
- **2×2 实测**（同边、h80/R2.54/Y0.5，一次只改一个变量）：

| 依附边 | `SEC_FLIP=FALSE` | `SEC_FLIP=TRUE` |
| --- | --- | --- |
| +X 顶边（z=+0.5） | down，bbox z `[-79.5, 0.5]` | up，bbox z `[-0.5, 79.5]` |
| +X 底边（z=−0.5） | up，bbox z `[-0.5, 79.5]` | down，bbox z `[-79.5, 0.5]` |

  即侧向相对依附面：`TRUE` = 从选中面法向向外，`FALSE` = 材料侧。据此定口径：**默认（`flip=false`）= 向外**，`flip=true` = 反向（材料侧）；轨迹法向固定 `NO_FLIP`（与库存 `UgSmtFlgWallCreate.c` 一致）。证据目录 `build/flange_side_probe/`（`sec_true/20261029T221644_c9ae6ece`、`bottom_default/20261029T221859_a54aec71`、`bottom_sec_true/20261029T221934_470617ee` 等）。
- **收口实机**：`tools/test_flange_direction.py --live --confirm-session-usable` → `passed=true`，报告 `build/flange_direction/20261029T222510_9cebd5e1/report.json`（SHA256 `9464933eb94bdee351361fc2265777bfe8f58145f1882af45c3fcf3c2b5f3745`）。
  - `angle90_outward`：模型 `fe7096c0f0444283bf8482979ee6866d`，base job `41454fd240d349f78955512df154378b`，flange job `f20a09ec980e4d4a8c31a0d840d4c0de`，rev 1→2，42 920→60 945.291234，+18 025.291234 mm³，bbox z `[-0.5, 79.5]`，`direction=up`，回显 `bend_side=outward/sec_flip_element=1`，`saved_file_reloaded_and_verified=true`。
  - `angle90_inward`：模型 `c72271209fa44fa7ba8921590c4834eb`，flange job `bb0cdab24f67453d8c0979781a2a8a41`，rev 1→2，+18 025.291153 mm³，bbox z `[-79.5, 0.5]`，`direction=down`，回显 `inward/0`，重载 true。
  - 驱动 oracle 已改：`|z 增长| ≥ 72 mm` 判折弯、方向必须等于该例显式期望（默认 up、`flip=true` down），不再"只认向上"。

### B. T05 四壁（`build/sheetmetal_relief/20261029T222754_44e6ab6a/report.json`，SHA256 `d2de17487469f10fba9859a0459cfeb64e593537105c8d5a6df5be9bf829d58f`）

模型 `fc04dfaf7e9a4d6eb17b900d5276da33`（t11_relief_none_2b54bc），底板 42 920、rev 1；逐道一 job、每道重新取边：

| 道 | job | rev | 体积增量 | bbox | direction | 重载 |
| --- | --- | --- | --- | --- | --- | --- |
| `f_px`（+x） | `c09759e7d25341d3a98874291273be15` | 1→2 | +18 025.291234 | `[0,-232,-0.5]`–`[185,0,79.5]` | up | true |
| `f_nx`（−x） | `fc097f17478a4d48a8a64deb2a6effef` | 2→3 | +18 025.291234 | 同上 | up | true |
| `f_ny`（−y） | `1a2b487ce90b486fb358494ba6afcc22` | 3→3 | 无（回滚） | 不变 | — | — |

- 第三道**未重提**：`f_ny` 边跨度 177.92 mm（两端各被已有折弯占去 3.54 mm），`toolkit_code=-1`、`message="Regeneration produced a failed, suppressed or incomplete feature"`、`rollback_succeeded=true`、`effect_status=rolled_back`，rev 与体积回到第三道之前。原生日志显示 `F_NY` 创建成功但 `status=6`、`geometry_items=[]`，随后的健康检查判定整件失败并回滚。
- 结论：四壁仍**未完成**；失败点从第一道推进到第三道、且已有真实折弯几何，与前两轮"平铺延伸/第一道 −1"不同。失败边保留 job 与原始码，按规则不再提交该边、也不再续跑第四道。

### C. T11 释放两档（同一报告；`relief_rect_1x1` 模型 `88dcd28eefb4459caf1480cb1803cfb9`）

| 档 | `f_px` job | 体积增量 | 与无释放之差 | 缺口面 | `relief` 回显 |
| --- | --- | --- | --- | --- | --- |
| 省略 | `c09759e7d25341d3a98874291273be15` | +18 025.291234 | — | 0 | 无 |
| rectangular both 1×1 | `e45404d4c09d441791626bb5eb369525` | +18 025.291234 | 0.000000 | 0 | type/ends/width/depth/板厚/两项比较齐全 |

- 差分 oracle（同边、同参数，只有释放不同）期望 −2 mm³；实测 **0.000000 mm³**，且模型上没有 1 mm 级小面（缺口面 0 个）。诊断性第 5 个 job（`6ddadf6487644504a1ebdfd6ef8bd7f4`，`build/relief_probe/w4_d4/20261029T223039_44c271f2/report.json`）把宽深提到 4×4（> 回显板厚 3.71）后体积差仍为 0，说明不是"1×1 太小被忽略"。
- 自由端解释与边界：这两道折边的弯端位于板件自由角，Creo 在该处不切释放缺口；真正需要释放的第三、四道在 `f_ny` 即回滚（有/无释放失败方式相同，job `2bc5bf3184d94d08b472a0cd179c242e`），因此**释放能力未获实机证实**，只是"请求被接受并回显"。
- 回显里的 `part_thickness_mm=3.71` 与 1 mm 薄壁不符（`ProSmtPartThicknessValueGet` 读到的是零件级默认板厚），已登记到 BUG-032 状态行：任何"宽 ≥ 板厚"的规则在修正前不可信。

状态口径：FEAT-014 = **折弯与方向已实机成立（A 通过）；四壁止于第二道（第三道 `f_ny` 回滚，原码保留）；释放请求可接受但无可观测几何**。不得表述为"四壁能力已具备"或"释放已实现"。

## 2026-10-30：T11 释放有效场景离线阶段（实现与回归完成，实机未验）

分支 `codex/dev051-feedback070`，基线 `760aa9b`（T03 板厚同步）。离线定位、实现、回归与构建；未连接 Creo。详见 [T11 验收卡](../development/DEV051-T11-ACCEPTANCE.md) 2026-10-30 节。

- **定位**：第六轮的 0.000000 差全部来自自由端，不能区分"释放未实现"与"自由端无缺口"。SDK 核对确认元素树转写正确；关键未观察点是 Creo 会把未写的释放元素填成默认（探针树 `flange_expected.xml` 为 `TYPE=5 PARAM`、数值全 0），"写入值是否留在创建出的特征里"此前从未读过。
- **实现**：创建+再生成功后回读创建特征树的释放段（`ProFeatureElemtreeExtract` + 按元素路径取值），与请求逐项核对，不一致即失败并回滚；一致则把 `relief_element_echo` 记入别名并写日志 `SHEETMETAL_FLANGE_RELIEF_ELEMS`。`LENGTH_TYPE/LENGTH/ANGLE` 只记录不断言（默认值是实机待答问题）。写路径未变，默认 none 不变，schema 不变。
- **有效材料场景**：`f_px`（+x，自由端负对照）→ `f_ny`（−y 第二道，+x 链端撞 `f_px` 折弯 = 1 个材料端）；none/1×1/4×4/单端对照，去料期望按实际相交材料独立推导（−1/−16 mm³、自由端 0），体积模型锚定第六轮实测（18 025.291233 vs 实测 …234）。verdict 拒绝"参数写了但几何没去料"（第六轮形状）与板厚矛盾。
- **未测（实机）**：`f_ny` 作第二道能否建成、`relief_element_echo` 一致性、缺口位置/尺寸/面/差值、单端映射、LENGTH 三元素默认值、板厚 1.0、保存重载、四壁 profile 新期望（0/−2）复测。

## 2026-10-30：T05 离线续做——第三壁对照设计冻结与 `end_trim_mm` 契约贯通（实机未验）

分支 `codex/dev051-feedback070`，HEAD `641edb3`。接续第六轮"`f_ny` status=6、空几何、回滚"的观察，离线补完对照实验；未连接 Creo。详见 [T05 验收卡](../development/DEV051-T05-ACCEPTANCE.md) 2026-10-30 节。

- **对照设计冻结**：full_length（复现第六轮）/ trimmed_20（第三壁两端各缩 20 mm）/ order_ny_first（0 材料角）/ order_ny_second（1 角）四组，每 fresh 模型逐道一 job、每道重选边；判定表规定角部干涉仅在全长失败 + 低角位成功 + 修剪壁成功且 setback 语义被自由壁探针确认三者齐备时升为 supported。**角部干涉仍是候选，未定因。**
- **`end_trim_mm` 贯通**：`sheetmetal_flange` 可选正数字段，两侧深度 `TO_END`→`BLIND`+offset（`advanced.cpp`），schema/server 同步；缺省时元素树逐字节不变（静态守卫断言）。语义（链端 setback 还是壁长）离线不可定，由自由首壁探针按实测体积分类，仅 setback 确认后才允许修剪第三壁提交。
- **驱动**：`tests/unit/test_sheetmetal_box_live.py`（27 用例）与 `tools/test_sheetmetal_box_live.py`（默认离线、`--live` 拒绝）；单测 27/27、全量 discover 通过、`bridge.py build` 成功。报告 `build/sheetmetal_box/20261030T082547_09fb8658/report.json`。
- **未测（实机）**：trim 语义探针、四组对照创建/失败/回滚、`f_ny` 是否再现 status=6、`end_trim_mm` 真实几何、角部干涉成立或反驳；四壁能力继续开放。
