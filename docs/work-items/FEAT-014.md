# FEAT-014：钣金折弯释放与四壁能力

日期：2026-10-28（Asia/Shanghai）补工作卡，沿用既有 ID。类型：功能。优先级：P2（既有台账）；状态：**离线实现完成、实机未通过**（2026-10-29 两轮底板已建成，第一道折边报 `ProFeatureWithoptionsCreate=-1`；四壁与释放能力未完成，根因未定）。目标版本：未排期。

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