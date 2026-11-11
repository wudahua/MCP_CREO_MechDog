# FEAT-065：多截面 + 纵向导线的 boundary blend（球鼻艏/船体类放样）

## 当前摘要（2026-11-11）

分类：**开发中**（M1/M2 已随 0.21.0 发布；M3/M4 已在开发分支 `codex/FEAT-065-m3-m4-surface-loft` 完成实机验收，待合入发布）。类型：功能。优先级：P1。

- **已发布**：M1 同方向 2—32 截面（两截面直纹，三截面以上单张光滑面）、M2 第二方向导线 2—8 条，均在 Creo 12.4.0.0 实机验收（见下文 2026-11-11 两节）。0.21.1 修复了 compact 回执裁掉测量值的问题（BUG-118）。
- **本轮（2026-11-11）已在开发分支交付，Creo 12.4.0.0 实机验收通过**，未合 main、未发布。范围、验收与分派见[计划](../superpowers/plans/2026-11-11-feat065-m3-m4-surface-loft.md)：
  - **M3**：`sections`/`guides` 除草图外，再接受已有曲线 `{kind:'curve'}`、边 `{kind:'edge'}`，首末截面还可以是收敛点。四种来源都已实机验证，包括 YZ 截面沿 X 排列和收敛点。
  - **quilt 边 ID 通道（T1b）**：`creo_measure_surface_group` 回执的 `group.open_edge_records` 给出开放边的 ID 与端点，已实机验证。
  - **M4**：`boundary_conditions` 只开放首/末截面上的 `tangent`，且该截面来源必须是边。实现为 `TAN_COND_TYPE` 2，`STRETCH` 首截面 -1、末截面 +1；这组值是用试值法在实机上测出来的（T2b）。两条接缝实测 G1 都是 0.0°。`curvature`、`normal` 和导线边界没有实测依据，在提交前拒绝。
  - 证据：下文「T3 实机验收与 T2b 试值取证」与「最终代码实机复核」两节，以及 [T2b 证据](../validation/feat065-t2b-tangency-2026-11-11/EVIDENCE.md)。
- **验收环境**：本机 Creo 12.4.0.0 + 匹配 SDK，用户当次授权。Creo 9/10 未测。
- **交接**：合入与发布步骤、当天过程与方法见 [FEAT-065-HANDOFF-2026-11-11](../development/FEAT-065-HANDOFF-2026-11-11.md)。
- **仍开放**：
  - `curvature`、`normal` 和导线边界上的连续条件：没找到有实测依据的值。
  - 非平面相邻面（如圆柱）上的相切，以及两端相邻面朝向不同的情形，都没有测。
  - 模型里已有实体时 `surface_loft` 一律失败：原生 `has_solid` 检查看的是整个模型。
  - `boundary_conditions` 不在 compact 保护集合内，回执超过 32 KiB 时可能被裁掉。
  - `ADV_VIA_CRV`、导线形状的可视化核对；曲线导线 600 mm² 与场景 E 799.94 mm² 的关系未核对。
  - Creo 9/10 差异（DEV-080 H01）；WorkBuddy 黑盒未做。

## 登记时摘要（2026-11-10，历史）

分类：**待规划**。类型：功能。优先级：P1（文本到三维任务的核心能力缺口）。

来源：2026-11-10 下载目录 `0.19.3` 第三份报告（球鼻艏导线曲面放样缺失与真机复测），并第二份报告 P12 互证。映射见 [归档 MAPPING](../validation/feedback-0.19.3-2026-11-10/MAPPING.md)。

结论：**未实现、未设计**。本轮只登记需求与验收口径，未改 `native/*.cpp`、未新增公开参数。

现有边界（不重复认领）：

- [FEAT-009](FEAT-009.md)：两截面直纹 `creo_surface_loft`（Creo 12.4 实机通过）；≥3 截面、smooth/闭合、非平行/扭转截面未公开。
- [FEAT-039](FEAT-039.md)：`project_curve` / `surface_trim` / quilt 链。
- [DEV-082](DEV-082.md)：缺 `Probbl.h` 时的聚合编译门控（本卡的前置之一）。
- [DEV-081](DEV-081.md) B1：seed 路线与无 callback 预检。

## 需求（报告方按价值排序）

1. **N≥2 个闭合截面 + M 条纵向导线**的 boundary blend：截面可位于任意正交平面，导线沿放样方向控制截面间过渡；最小可用形态「3 截面 + 2 导线」。
2. **端点收敛**：支持独立点作为收敛截面（球鼻艏艏尖点 `Sketch69`），或支持以导线的端点收束。
3. **任意正交平面截面**：球鼻艏截面在 YZ 平面按 X 排列，现有 `loft`/`surface_loft` 要求 XY + Z 递增，几何框架不适配。
4. **平滑插值与连续性**：至少 smooth 插值；G1/G2 与闭合曲面可另列。
5. **和既有链的衔接**：结果 quilt 能被 `quilt_merge` / `solidify` / `thicken` 消费；注意 [BUG-115](BUG-115.md) 的链式引用缺陷，验收时按当前 workaround 引用原始 target label。

## 设计前置（实施前必须裁定）

| 前置 | 内容 | 缺失后果 |
| --- | --- | --- |
| `Probbl.h` 可用性 | Creo 10.0.0.0 SDK 是否真无该头；有无 `ProSurfacedata`/legacy blend tree 等价入口 | 无结论时不得声称「Creo 10 可用」；需在 `creo_capabilities` 顶层给「Creo 版本 → surface_loft/blend 可用性」速查 |
| 元素树契约 | 多方向（`PRO_E_BNBLN_1DIR`/`PRO_E_BNBLN_2DIR`）与导线集合的元素路径、数量上限、失败诊断 | 无契约则只能试错建树，回执不可解释 |
| 公开参数冻结 | 新工具名（`surface_blend`？）或 `surface_loft` 扩展；截面/导线字段、点收敛形态、默认插值；向后兼容 | 未冻结不得改公开签名 |
| 几何框架 | 任意正交平面截面的坐标系与截面方向解析 | 框架不适配时球鼻艏无法按 TXT 原方案重建 |

## 验收口径（实施时执行）

- 成功路径：球鼻艏三椭圆截面（YZ 按 X 排列）+ 3 条纵向导线，产出单张 quilt；体积/面积与解析近似值对照并记录误差来源；`saved_file_reloaded_and_verified=true`；revision 前进；单实体、0 异常。
- 收敛路径：以艏尖点（独立点）作为收敛端，几何闭合、无自交；或明确记为不支持并保留分段柱面近似。
- 下游链：blend quilt → `quilt_merge`（按 BUG-115 workaround）→ `solidify` → 体积 = 截面长度 × 面积类解析值；失败时 `rollback_succeeded=true`、体积复原精确。
- 负例：导线与截面不相交、截面不闭合、导线少于 2 条时给出结构化拒绝且模型不变。
- 实机环境：本机 Creo 12.4.0.0 + 匹配 SDK（主验收）；Creo 10 由报告方或后续用户在**当次确认**后复测，不作为本仓发布门槛。

## 当前状态

- 2026-11-10：登记。仅静态核对（`native/surface_loft.cpp` 仅两截面、无导线；`loft_mode.cpp`/`loft_seed.cpp` 为 XY+Z 框架）。未实现、未编译、未连接 Creo。

## 2026-11-10 SDK 事实核对（本地 Creo 12.4.0.0 Toolkit）

`ProElemId.h` 已声明边界混合元素，说明元素树存在、只是没有文档化父子关系：

| 常量 | 值 | 用途推断 |
| --- | ---: | --- |
| `PRO_E_BLEND_TYPE` | 646 | 混合类型 |
| `PRO_E_BNBLN_1DIR` | 651 | 第一方向截面列表 |
| `PRO_E_BNBLN_2DIR` | 652 | 第二方向（导线）列表 |
| `PRO_E_BNBLN_DIR_CURVES` | 657 | 单方向的曲线持有容器 |
| `PRO_E_BNBLN_CURVES` | 661 | 两个方向的父容器 |
| `PRO_E_BNBLN_ADV_VIA_CRV` | 471 | 高级：经导线 |
| `PRO_E_BNBLN_ADV_INN_EDGS` 471/512/513 | — | 高级：内部边 |
| `PRO_E_BNBLN_ADV_GHST_2DIR` | 473 | 高级：第二方向鬼影 |
| `PRO_E_BNBLN_TAN_COND*` / `PRO_E_BNBLN_TAN_FLD*` | 459—468、666—675 | 切线条件与相切场 |

与现有代码的关系（关键）：`native/surface_loft.cpp` 已在用
`PRO_E_DTM_SRF_TYPE_BND_BLEND` + `PRO_E_BNBLN_CURVES` → `PRO_E_BNBLN_1DIR` → `PRO_E_BNBLN_DIR_CURVES` → 每个 `PRO_E_STD_CHAIN_HOLDER` 的树形骨架，先建 INCOMPLETE 骨架再由内核补全，再用 `ProFeatureWithoptionsRedefine` 回读。**多截面（同方向加截面）是在 `PRO_E_BNBLN_DIR_CURVES` 下增加 holder**，不需要新树；导线（第二方向）才需要 `2DIR`/`ADV_VIA_CRV`。

因此拆成两个里程碑：

- **M1（多截面，无导线）**：`surface_loft` 接受 ≥3 个截面曲线（仍单方向、straight 插值），球鼻艏的「3 椭圆截面」可先成型，再配 `surface_boundary_fill`/`thicken` 走实体。风险较低（复用现有树），但仍须实机确认内核接受 3 个以上 holder 及截面方向一致性。
- **M2（导线 + 任意正交平面）**：`2DIR`/`ADV_VIA_CRV` 与截面坐标系改造；无任何树文档，必须先在 Creo 里做元素树实验（建完用 `ProFeatureWithoptionsRedefine` 回读真实树），否则无法保证不是猜测。

前置与风险（未变）：

- `surface_loft` 依赖 `Probbl.h`，Creo 10 构建被剔除（见 [DEV-080](DEV-080.md) H01、[DEV-082](DEV-082.md)）；M1/M2 必须与「Creo 版本 → 可用性」速查一起交付，否则在 Creo 10 上仍然是「提交后才被拒绝」。
- 上述常量在 Creo 9/10 SDK 的可用性未核对（本机只有 12.4）。
- 公开参数仍冻结中：M1 可以只在现有 `surface_loft` 上放宽 `sections` 数量（向后兼容），M2 需要新工具名或新字段，须先冻结。

本轮未实施 M1/M2，未新增参数，未编译新代码。

## 2026-11-11 M1 实施与实机验收

用户当次确认可以使用 Creo 测试后，按上文路线实施 M1（同方向 2—32 截面：两截面直纹、三截面以上单张光滑面，不加导线）：

- `src/creo_mechdog/surface_ops.py`：`SurfaceLoftOp.sections` 由 `min_length=2, max_length=2` 放宽为 `min_length=2, max_length=32`，重复截面校验改名 `distinct_sections` 并改为「每个截面必须是不同草图」；文档字符串说明同一 `PRO_E_BNBLN_1DIR` 树承载 N 个截面、导线仍不发布。
- `native/surface_loft.cpp`：新增 `SURFACE_LOFT_SECTION_LIMIT=32`；按顺序解析每个截面曲线并拒绝重复（报「section N repeats curve X」）；holder 循环改为遍历全部曲线；回执新增 `section_count`，`section_curve_ids` 为全部曲线；create 失败信息列出全部曲线 id 与截面数。
- `src/creo_mechdog/capabilities.py`：`surface_loft` 的 `scope` 改为「2-32 sections」，`limits` 写明单方向、每截面一条非复合曲线、不得重复、导线（第二方向）与 smooth/closed 仍不发布；家族说明与 `creo_loft.surface_mode` 同步（后者原先还写着「没有 creo_surface_loft 工具」，属过期描述，一并更正）。
- 测试：`tests/unit/test_surface_loft_schema.py` 改为「接受 3 截面 / 拒绝 33 截面」；`tests/unit/test_feedback0190_loft_limits.py` 期望文案更新为 `2-32 sections`。
- 验收驱动：新增 `tools/test_surface_loft_multisection.py`，离线部分校验 2/33/重复/smooth 的准入与能力文案；实机部分（`--live --confirm-session-usable`）检查 40/60/40 mm 三截面 20 mm 间距 → 面积 2000.0 mm²、单张开放 quilt、`section_count=3`、保存重载后 quilt id 与面积稳定、thicken 2 mm → 4000.0 mm³，并用两面 800.0 mm² 回归旧路径。

离线证据：`bridge.py build` 成功；`tools/test_surface_loft_multisection.py`（离线）全部 PASS；`tools/dev_check.py --work-item FEAT-065` → `success=true`、`Ran 3307 tests ... OK`、无新增回归。

实机状态：**已验收**（2026-11-11 10:47，Creo 12.4.0.0 + 匹配 SDK，用户当次确认后执行；报告 `build/surface_loft_multisection/20261111-104718.json`，30 项检查全 PASS）。

- 三截面（40/60/40 mm，间距 20 mm）：`job bd976c4c…` 成功、`saved_file_reloaded_and_verified=true`、revision 1、单张 **开放** quilt、`section_count=3`、`section_curve_ids` 3 条、无实体；测得面积 **2101.2524427513217 mm²**，保存重载后 quilt id 与面积**完全一致**。
- thicken 2 mm（`job f40d0a73…`，revision 2）：体积 **4202.507981502071 mm³** = 实测面积 × 2（4202.504885502643，差 0.003 mm³，远小于 0.5 容差）。
- 两截面回归（`job 7c6c80a4…`，模型 `52d39f1c…`）：面积 **800.0 mm²**，`piecewise_ruled=true`、`section_count=2`，旧路径未变。

**实机发现（已并入公开契约）**：`interpolation="straight"` 只在**两截面**时成立。三截面按下述配置交给内核时，内核并没有建分段直纹面，而是**通过全部截面拟合一张光滑面**：实测 2101.25 mm²，而分段直纹应为 2000.00 mm²（差的 101.25 mm² 来自中段外鼓）。因此：

- `SurfaceLoftOp.interpolation` 扩为 `"straight" | "smooth"`，默认 `straight`；
- **3 截面及以上必须显式 `smooth`**，写 `straight` 在提交前拒绝并提示改 `smooth`（原生侧同样校验，防止手写计划绕过）；
- 回执新增 `section_count`、`piecewise_ruled`，`interpolation` 回显请求值；
- 能力文案改为「两截面 = 直纹，3 截面以上 = 单张光滑面」，并把实测数值写进 `limits`（截断到 `limits_note` 时仍保留这条结论）。

仍开放（M1 之后的边界，M2 见下节）：`ADV_VIA_CRV` 变体、任意正交平面截面、端点收敛、G1/G2 连续性；截面顺序/方向不一致时的失败形态未测；Creo 9/10 未测；`Probbl.h` 不可用时该操作仍整条不可用（DEV-080 H01）。

## 2026-11-11 M2 导线（第二方向 2DIR）实施与实机验收

同一轮先按 M2 路线试做了一版最小导线分支（`guides` 字段 + 2DIR 建树 + 单个导线草图），实机提交后整体回滚；随后按下面的过程重做并交付。回滚那版的探针只有一次未落盘的提交，单导线本身也不满足 `Probbl.h` 的「2DIR 至少 2 条曲线」，不作为结论。

### 元素树实验（先取证，再改契约）

- 场景 A（两截面 + 2 条 XZ 直导线，导线端点落在两截面端点）：`create_code=0`、激活、单张开放 quilt、`surface_area_mm2=800.0`，与无导线直纹面一致——导线正好落在两截面已确定的面上，属恒等情形。
- 场景 B（导线 v 方向取反）：再生失败（`feature_status=6`、`quilt_count=0`），据此确定本机 XZ 草图 `v` 轴为 **+Z**。
- 场景 C（只给 1 条导线）：同样再生失败，证实 `Probbl.h`「`PRO_E_BNBLN_2DIR` 至少 2 条曲线」不是纸面约定；单导线必须在校验层拒绝。
- 场景 D（圆弧导线，端点切线与截面平行）：再生失败，说明导线必须在交点处横穿截面，端点相切不行。
- 场景 E（圆弧导线，端点切线与截面成 45°）：成功，面积 799.94 mm²、包围盒 x 达 44.24 mm（截面止于 40 mm）——2DIR 确实参与成面。
- 场景 F（3 截面 + 2 直导线）：成功，说明导线可与多截面共存。
- 抽取树（作业 `e97f6df51779470ab1bf6ba504ad72a1` 的 `SURFACE_LOFT_TREE`）读到 `PRO_E_BNBLN_1DIR` 与 `PRO_E_BNBLN_2DIR` 各一个、`PRO_E_BNBLN_DIR_CURVES` 三个（两方向各一，另一个在 `PRO_E_BNBLN_CURVES` 下）、每条曲线一组 4 份链元素，`PRO_E_BBL_ADD_CLOSED` 由内核补齐为 3 个——即 2DIR 节点被内核保留而不是丢弃。

### 实现（schema / 投影 / 原生三处一致）

- `src/creo_mechdog/surface_ops.py`：`SurfaceLoftOp.guides`（`list[str|int]`，最多 8 个）；数字字符串归一为整数；**少于 2 条拒绝**（消息说明单导线不会再生）、重复草图拒绝、与 `sections` 重复拒绝；文档字符串写明导线是第二方向、交点由内核判定。
- `src/creo_mechdog/job_projection.py`：`SURFACE_LOFT_KEYS` 增加 `guides`、`guide_count`、`guide_curve_ids`。
- `native/surface_loft.cpp`：解析 `guides`（空数组=无第二方向，避免 schema 默认值被误判为单导线请求）；`guides.size()<2` 拒绝；每条导线必须恰好拥有 1 条非复合曲线、不得重复草图、不得复用截面曲线；在 `PRO_E_BNBLN_CURVES` 下增建 `PRO_E_BNBLN_2DIR` → `PRO_E_BNBLN_DIR_CURVES` → 每导线一个 `PRO_E_STD_CHAIN_HOLDER` + `PRO_E_STD_CURVE_COLLECTION_APPL`；回执回显 `guides`/`guide_count`/`guide_curve_ids`。
- `server.py`：`creo_surface_loft` 增参 `guides`（最多 8），`sections` 加 2—32 约束，`interpolation` 放为 `straight|smooth`，文档字符串同步；空列表不写入计划。
- 能力文案（`capabilities.py` 的 `surface_loft`/`surface_chain`/`loft` 与 `references.py`）：由「导线不发布」改为「2-8 条导线、单导线不发布、是否穿过截面由内核判定、不穿过则再生失败」。

### 实机验收（2026-11-11，Creo 12.4.0.0 + 匹配 SDK，用户当次确认后执行）

驱动 `tools/test_surface_loft_guides.py --live --confirm-session-usable`，报告 `build/surface_loft_guides/20261111-120758.json`，离线 10 项 + 实机 17 项全 PASS：

- 单导线计划在提交前被拒绝，未产生作业。
- 直导线基线（`job 900fa9b3092541e681deeae0e2bf9ba6`，模型 `4b4b19c5…`，revision 1）：`saved_file_reloaded_and_verified=true`、`guide_count=2`、单张开放 quilt、无实体，面积 **800.0 mm²**，包围盒 x 止于 40.0 mm——加第二方向不改变它已经描述的曲面。
- 曲线导线（`job 4d0f3e10b1f54c14b794f3ecd7e8760a`，模型 `332b574d…`，revision 1）：`saved_file_reloaded_and_verified=true`、`guide_count=2`、`guide_curve_ids` 2 条、单张开放 quilt、无实体，面积 **600.0 mm²**，保存重载后面积一致，包围盒 x 达 **44.24 mm**（截面止于 40 mm，圆弧导线外鼓 4.142 mm）。
- 解释与限定：两组数值一起才构成「第二方向生效」的证据——面积与包围盒都偏离无导线基线；**曲面的实际形状未在 GUI 或等价可视化中核对**，本记录只声明可测数值，不声明形状正确性。

### 3 截面 + 导线的驱动复跑（2026-11-11 14:57，随 0.21.1）

用户重启 Creo 后重跑同一驱动（报告 `build/surface_loft_guides/20261111-135731.json`，离线 12 项 + 实机 22 项全 PASS），补上了 0.21.0 版本说明里「3 截面用例未复跑」的缺口：

- 直导线 job `baad63b6ceef414cbbd0a4c03e0ee254`：800.0 mm²、bbox x 止 40.0 mm。
- 曲线导线 job `e2646c3a789d454db601069184838b7b`：600.0 mm²、bbox x 达 44.24 mm。
- **3 截面 + 2 导线 job `2a2ee086273b40bc81a5edab6b1f01a5`**：`section_count=3`、`guide_count=2`、面积 1599.9999999999995 mm²、单张开放 quilt、无实体、bbox 40.12/40.12 mm、保存重载 verified。

首次复跑（`job 6510998c…`）暴露了一个回执缺陷：compact 视图把整条放样记录裁成只剩 `detail_truncated`，面积/闭合/计数全丢，导致该用例两项 FAIL；`detail=full` 分页里数值齐全。根因是 `enforce_compact_budget` 自最后一条记录倒序剥字段，而放样恰好是计划最后一条、测量字段又不在保护集合内。已按 [BUG-118](BUG-118.md) 修复并复跑通过。

### 仍开放

- 曲线导线下面积为何是 600.0 mm²（直线基准 800.0）未做几何解释；导线与截面的交点/端点约束只测了「端点相交、切线 45°」与「端点相切被拒」两态。
- `PRO_E_BNBLN_ADV_VIA_CRV`、`PRO_E_CTRL_PTS`/`PRO_E_BLEND_TYPE`、G1/G2 连续性、端点收敛、任意正交平面截面未测。
- 导线草图拥有 2 条曲线（闭合轮廓）被明确拒绝，未验证内核是否接受。
- Creo 9/10 未测；`Probbl.h` 不可用时该操作仍整条不可用（DEV-080 H01）。

## 2026-11-11 M3 离线实现（T1）

范围：`surface_loft` 的 `sections`/`guides` 除 MCP 草图外接受已有曲线、边，以及首末截面上的一个收敛点。本节只有离线证据：**未编译执行器、未连接 Creo/Toolkit、未运行任何 `--live`**，新形态一律为「Creo 12.4 实机未验收」，等 T3 用户当次确认后实测。

### 改动

- `src/creo_mechdog/surface_ops.py`：元素类型由 `str | int` 扩为 `str | int | dict`；字符串/整数仍是草图，归一与旧校验不变。新增 `loft_input_problem`/`loft_input_key`：接受 `{kind:'curve',id}`、`{kind:'edge',id}`，点 `{kind:'point',id}` / `{kind:'datum_point_feature',label}` 只能在 `sections` 首项或末项、最多一个、不能作导线；几何 kind 带 `label`、多余字段、非 32 位 id、`quilt`/`surface` 等非链 kind、重复引用、同一引用既作截面又作导线都在提交前拒绝，消息带 `sections[i]`/`guides[i]` 与可用写法。
- `src/creo_mechdog/schema.py`：计划级补一条——收敛点标签若由同一计划创建，必须是更早的单点 `datum_points`，否则拒绝；来自旧计划的标签交给原生判定。
- `native/surface_loft.cpp`（全部在 `MECHDOG_HAS_PROBBL_HEADER` 门控内）：新增 `SurfaceLoftInput`、`surface_loft_input`（来源解析）、`surface_loft_probe`（`ProModelitemInit` + 类型专属 Init/查询的存在性核验）、`surface_loft_kind_hint`、`surface_loft_reject`、`surface_loft_point_chain`、`surface_loft_chain`。草图来源仍走 `surface_loft_curves`，元素树与报错文字和 M1/M2 逐字一致；curve/edge 直接交给 `generic.cpp` 的 `curve_collection`；点用 `ProCrvcollection.h` 文档化的 `PRO_CURVCOLL_ADD_POINT_INSTR`。截面与导线共用一个 (类型, id) 去重集合。创建或再生失败时，若用到新形态，消息追加 `unverified input forms: ...`。
- 回执：新增 `section_source_kinds`/`guide_source_kinds`、`section_geometry_ids`/`guide_geometry_ids`（每个链容器实际装入的几何 id）、`section_sources`/`guide_sources`（逐项记录：草图的 `feature_id`；曲线的 `curve_type`/`composite`；边的 `edge_type`、`adjacent_surface_ids`、`neighbors_query_code`；点的 `point_mm`、`chain_instruction`；每项 `live_verified`）、`convergence_point`、`unverified_input_forms`；原生拒绝时暂存 `failed_loft_input`（`role`/`index`/`slot`/`request`/`reason`/`query_code`/`use_instead`），消息前缀 `SURFACE_LOFT_INPUT_REJECTED`。`section_curve_ids`/`guide_curve_ids` 保持原义（只含 PRO_CURVE id）。
- 投影与保护：`job_projection.SURFACE_LOFT_KEYS` 纳入上述字段；`operation_results.OUTCOME_OPERATION_KEYS` 加入来源种类、几何 id 与 `unverified_input_forms`（BUG-118 方式，compact 裁剪不丢）；`FAILED_EVIDENCE_KEYS` 加入 `failed_loft_input`。
- 公开面：`server.py` 的 `creo_surface_loft` 签名改为 `list[str | int | dict[str, Any]]`，文档字符串注明「live acceptance pending」与拒绝码；`capabilities.py` 的 `surface_loft` scope/limits（前 160 字符不变）与 `surface_chain` 文案；`references.py` 新增 `by_tool.creo_surface_loft`；`docs/REFERENCE_SYNTAX.md` 增段与表行。
- 测试与驱动：新增 `tests/unit/test_surface_loft_inputs.py`（41 项）与 `tools/test_surface_loft_inputs.py`（离线默认，`--live --confirm-session-usable` 含 (a)—(d)）。`tools/test_surface_loft_guides.py` 只改一处签名字符串检查（签名变了，旧字符串必然不再出现）。

### 设计决定

- 公开字段沿用仓库既有裸引用写法，不新造 `chain`/`reference` 包装：一个元素一个链容器、一个几何项。多条边拼成的闭合截面暂不支持；草图截面仍可是两条曲线的闭合轮廓。
- 收敛点：`Probbl.h` 只说链容器装 curve collection，没写点；`ProCrvcollection.h` 有文档化的 `PRO_CURVCOLL_ADD_POINT_INSTR`（"Add selected point or points to the collection"）。因此实现了这条路，但回执 `convergence_point.live_verified=false`、`unverified_input_forms` 含 `point`，能力文案写明「undocumented for a chain holder, so it is an experiment」。链构建每步的返回码存进 `convergence_point.chain_codes`，被拒时以 `SURFACE_LOFT_POINT_CHAIN_REFUSED` 失败，且发生在创建特征之前。
- 首版每个放样只允许一个收敛点（两端都收敛属另一种未测形态）；点仍计入截面数，3 段以上照旧要求 `smooth`。
- 复合曲线：`Probbl.h` 写明集合里的曲线可以是复合曲线，所以显式 `{kind:'curve'}` 不拒绝复合曲线，只在回执标 `composite`；草图来源保持 M1 的「拒绝复合」规则。
- 原生 id 类型核验：先用 `ProModelitemInit`（头文件写明找不到会报错），再用类型专属 Init 与查询；id 实际是另一种几何时，消息直接给出 `{kind:'edge',id:N}` 等可用写法。

### 离线证据（2026-11-11，基于 `5ba2cf5`，工作区未提交）

- 定向单测：`python -m unittest tests.unit.test_surface_loft_inputs tests.unit.test_surface_loft_schema tests.unit.test_feedback0190_loft_limits tests.unit.test_native_aggregate_compile -v` → `Ran 74 tests ... OK`；受影响模块合跑（含 `test_large_plan_result_budget`、`test_reference_contract`、`test_job_projection`、`test_compact_sections`、`test_optional_loft_header`、`test_native_header_gate` 等 42 个模块）→ `Ran 537 tests ... OK`。
- 离线驱动：`tools/test_surface_loft_inputs.py` 28 项 PASS；`tools/test_surface_loft_guides.py`、`tools/test_surface_loft_multisection.py` 离线全 PASS。
- 语法检查：按 `bridge.py` 编译 `creo_worker.exe` 的参数对 `native/worker.cpp` 跑 `cl /Zs`（SDK 头含 `Probbl.h`，门控代码参与检查），退出 0，只有既有的 C4819 代码页警告；未产出执行器，临时文件在 `.tmp/`。
- 格式：Ruff check/format 通过；`native/surface_loft.cpp` 的 clang-format 干跑无差异（HEAD 版本本就干净，只格式化了新增段落）。
- 源码摘要（LF 归一 SHA256 前 16 位）：`native/surface_loft.cpp` `964cf7034610c9f5`，`src/creo_mechdog/surface_ops.py` `3a04b926cdbc7b34`。

### 未验证范围与已知问题

- 全部新形态未上实机：curve/edge 链容器能否创建与再生、点链容器是否被内核接受、YZ 截面沿 X 的光滑放样（驱动 c0）、收敛点放样（驱动 c）、`failed_loft_input` 的真实返回码，均待 T3。
- quilt 边没有公开的 id 发现通道：`creo_inspect_model` 的 `edges` 只枚举实体面上的边。驱动 (a) 因此从 `feature_geometry` 读两条曲面带的 PRO_EDGE id 并逐对试探（只有顶边与两条导线端点相接，其余组合预期再生失败并回滚），也可用 `--bridge-edges` 直接指定；`feature_geometry` 是否列出 quilt 的边本身未经实机确认。
- `surface_loft` 在模型已有实体时一律失败（`has_solid` 判的是整模型，不是本特征新增的材料），所以「用实体边补面」目前走不通；本轮未改这条既有规则。
- 旧驱动 `tools/test_surface_loft.py` 离线检查 `schema_rejects_smooth` 失败：它仍要求两截面拒绝 `smooth`，而 M1（0.21.0）起两截面允许 `smooth`（`test_two_sections_still_accept_smooth`）。这是 M1 遗留，与本轮无关，未改。
- `docs/development/G5-NATIVE-CONTRACT.md` §4.2 仍写「首版长度必须为 2」等 M1 前口径，未在本轮修改。

## 2026-11-11 M4 离线候选（T2a）

范围：边界与相邻曲面的连续条件（相切/曲率/法向）。本节只有离线证据：**未编译执行器、未连接 Creo/Toolkit、未运行任何 `--live`**。字段已登记但提交前被门禁拒绝，原生代码在映射表为空时只会拒绝，不会写值。

### 设计

- 公开字段：`surface_loft.boundary_conditions: [{boundary, condition}]`，最多 4 项，每个 boundary 只能出现一次；缺省为 `None`，旧计划的落盘请求不变（不会多出空列表）。
  - `boundary` ∈ `first_section | last_section | first_guide | last_guide`，分别对应 `sections[0]`、`sections[-1]`、`guides[0]`、`guides[-1]`。导线边界要求计划里有导线，`free` 也一样。
  - `condition` ∈ `free | tangent | curvature | normal`。`free` 保留内核默认值，原生不改树；非 `free` 要求该边界来源是 `{kind:'edge',id:N}`。
  - `server.py` 的 `creo_surface_loft` 增加同名参数（`list[dict[str,str]]`，最多 4 项），文档字符串写明 NOT AVAILABLE 和 FEAT-065 T2b；`None` 和空列表都不写入计划。
- 原生候选（`native/surface_loft.cpp`，全部在 `MECHDOG_HAS_PROBBL_HEADER` 门控内）：
  - `surface_loft_conditions`：解析输入后、建创建树之前复核形状，把非 free 边界解析为（边 id，唯一相邻面 id）。相邻面取 T1 的 `adjacent_surface_ids`，不是恰好 1 个就拒绝（实体边、quilt 内部边有 2 个）。拒绝前缀 `SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED`，回执带 `failed_boundary_condition`（`index`/`slot`/`boundary`/`condition`/`reason`/`query_code`/`tracking`）。
  - 两张映射表 `SURFACE_LOFT_TAN_COND_TYPE_VALUES`（condition → `PRO_E_BNBLN_TAN_COND_TYPE` 整数）和 `SURFACE_LOFT_TNC_BOUNDARY_INDEX`（boundary → `PRO_E_BNBLN_TNC_BNDRY` 下标），**当前都为空**；`SURFACE_LOFT_CONNECT_CHAIN_METHOD = -1`（不写 `PRO_E_SURF_CHAIN_METHOD`）。
  - `surface_loft_apply_conditions` 在 `ProFeatureElemtreeExtract` 之后、`redefine` 之前执行。映射未知时以 `SURFACE_LOFT_BOUNDARY_CONDITION_UNMAPPED` 拒绝，不改树；catch 里写入 `tan_cond_tree`、释放抽取树、重新抛出，作业按现有失败路径回滚，INCOMPLETE 特征不留存（与「抽取失败」「再生失败」同一条路）。映射已知时：改写对应 `TNC_BNDRY` 的 `TAN_COND_TYPE`；删掉已有 `CONNECT_SURF_CHAIN` 后重建 `CONNECT_SURF_CHAIN → SURF_CHAIN_CMPND → SURF_CHAIN_REF_SURFS → SURF_CHAIN_SURF → SURF_CHAIN_REF(相邻面)`；每个 Toolkit 调用都检查返回码，选择对象用完即释放。`TAN_FLD_TYPE`、`STRETCH`、`TAN_REF_TYPE`、`ADV_VIA_CRV` 不改。
  - 创建树仍不含任何 `PRO_E_BNBLN_TAN_COND*`（2026-11-01 P1 反证）。
- 取证输出：新增 `tan_cond_tree`，即抽取树 `PRO_E_BNBLN_TAN_COND` 子树的单独样本（64 元素预算，带 `truncated`、`elements_read`；子树不存在时为 `available=false` 加 `query_code`）。写入条件：请求了 `boundary_conditions`；任一截面或导线来源是边；redefine 或再生失败。纯草图放样的成功回执不变。顺带修正：共享的 `extracted_tree` 样本此前 `truncated` 恒为 `false`，现在如实报告（`surface_boundary_fill.cpp` 的三参调用不受影响）。
- 投影：`job_projection.SURFACE_LOFT_KEYS` 加入 `boundary_conditions`、`failed_boundary_condition`、`tan_cond_tree`；`operation_results.FAILED_EVIDENCE_KEYS` 加入 `failed_boundary_condition`。
- 契约文档：`docs/development/G5-NATIVE-CONTRACT.md` 在 §3.1、§4.2、§9.4「未验证」三处之后各加一段 2026-11-11 更正（原文不动），新增 §2.1a 记录本候选路线、未知映射与 T2b 计划。

### 门禁位置与解除方法

- 位置：`src/creo_mechdog/capabilities.py` 的 `UNAVAILABLE_FIELDS = {"surface_loft.boundary_conditions": <原因>}`，由 `require_available` 检查（`generic_bridge.submit` 与 `modeling_recipes` 共用），非空即拒绝，消息 `Not available in the <版本> release; no native job was queued. surface_loft.boundary_conditions: ...`，发生在取 Toolkit 通道之前。`creo_capabilities` 的 `families.surface_loft.unavailable_fields` 由同一常量生成。
- 解除（T3，前提是 T2b 已回填原生映射表）：删除 `UNAVAILABLE_FIELDS` 中这一项即可，Python 侧没有第二处开关；同时按实机结果改写 `surface_loft` 的 limits、`creo_surface_loft` 文档字符串中的 NOT AVAILABLE 和本卡结论。原生侧在表为空时仍以 `SURFACE_LOFT_BOUNDARY_CONDITION_UNMAPPED` 拒绝，所以先删门禁、后填表也不会把猜测值写进内核。

### T2b 需要从参照树读取的元素

参照件建议：两张相邻曲面 + 一个边界混合，首截面设「相切」、末截面设「曲率」（两端条件不同，才能区分下标）；如能再做一个带两条第二方向导线、导线端设条件的版本，就能定出导线边界的下标；「法向」另建一例。

1. `PRO_E_BNBLN_TAN_COND`：`PRO_E_BNBLN_TNC_BNDRY` 的个数与顺序。
2. 每个 `TNC_BNDRY` 的 `PRO_E_BNBLN_TAN_COND_TYPE` 整数：自由端、相切端、曲率端、法向端各是多少（顺带判定 2026-11-07 默认值 1,1,0,0 里的 1 是否就是 free，0 是否表示「无此边界」）。回填 `SURFACE_LOFT_TAN_COND_TYPE_VALUES`。
3. 哪个下标对应首截面、末截面、首导线、末导线：按 GUI 中设了相切/曲率的边界反推。回填 `SURFACE_LOFT_TNC_BOUNDARY_INDEX`。
4. `PRO_E_BNBLN_CONNECT_SURF_CHAIN → PRO_E_SURF_CHAIN_CMPND → PRO_E_SURF_CHAIN_METHOD` 的值（对照 `ProSweep.h` 的 `ProSurfChainMethod`：DEFAULT1=1、DEFAULT2=2、SKETCH=4、SELECT=8、NONE=16）。回填 `SURFACE_LOFT_CONNECT_CHAIN_METHOD`。
5. `PRO_E_SURF_CHAIN_REF_SURFS` 下 `PRO_E_SURF_CHAIN_SURF` 的个数，以及 `PRO_E_SURF_CHAIN_REF` 引用的是不是边界边的相邻面（面 id）。
6. 约束端与自由端的 `PRO_E_BNBLN_TAN_FLD_TYPE`（Probbl.h 只写了 -1）；若约束端不是 -1，候选需要补写。
7. `PRO_E_BNBLN_STRETCH`（double）是否出现及取值。
8. `PRO_E_BNBLN_TAN_REF_TYPE`（Probbl.h 只在第一个 `TNC_BNDRY` 下列出）是否出现及取值；`PRO_E_BNBLN_ADV_VIA_CRV` 是否出现。
9. 参照件 1DIR 链容器里装的是不是边，作为 M3 边截面写法的旁证。
10. 对照 T3 驱动 (a)（两条曲面边作截面）回执里的 `tan_cond_tree`：内核对边来源的默认树是否已经自动填了 `CONNECT_SURF_CHAIN`。

### 离线证据（2026-11-11，基于 `b88721b`，工作区未提交；T1b 同时在改 `surface_group.cpp` 等文件）

- 新增 `tests/unit/test_surface_loft_boundary_conditions.py`（23 项）：门禁（非空即拒，含 `free` 单项；消息含原因与 FEAT-065 T2b；`generic_bridge.submit` 不取通道、不建目录；清空 `UNAVAILABLE_FIELDS` 即放行）、字段形态（boundary 不重复、取值、多余键、超过 4 项、非 free 只能落在边上、导线边界要求有导线）、旧行为（缺省时落盘请求键集合不变、空列表过门禁、服务端只转发非空列表、工具 schema 与说明）、投影与保护集合、原生静态契约（两张表为空、`TAN_COND_FREE` 不作为符号出现、UNMAPPED 拒绝在第一次写入之前、写入只发生在 extract 与 redefine 之间、拒绝时释放抽取树、`tan_cond_tree` 独立预算）。
- 改动的既有测试：`test_surface_loft_schema.test_native_route_is_the_documented_blend_tree` 与 `test_surface_loft_inputs.test_tangency_elements_stay_unwritten` 原先断言整份源码不出现 `PRO_E_BNBLN_TAN_COND`，现改为「创建树（`node(nullptr, PRO_E_FEATURE_TREE)` 到 `ProFeatureWithoptionsCreate(`）不出现」，`PRO_E_BBL_ADD_CLOSED` 仍是整份不出现。
- 定向单测：`test_surface_loft_boundary_conditions`、`test_surface_loft_inputs`、`test_surface_loft_schema`、`test_feedback0190_loft_limits`、`test_native_aggregate_compile`、`test_g5_native_contract` → `Ran 116 tests ... OK`；按关键字 grep 出的受影响模块（68 个，含 `test_capabilities_layout`、`test_capability_pages`、`test_t01_capability_contracts`、`test_large_plan_result_budget`、`test_job_projection`、`test_compact_sections`、`test_optional_loft_header`、`test_native_header_gate`、`test_surface_boundary_fill_contract` 等）合跑 → `Ran 1070 tests ... OK`。
- 离线驱动：`tools/test_surface_loft_inputs.py` 35 项、`test_surface_loft_guides.py` 12 项、`test_surface_loft_multisection.py` 9 项、`test_surface_loft.py` 14 项，全部 PASS（报告在 `.tmp/syntax_check_t2a/`）。
- 语法检查：按 `bridge.py` 编译 `creo_worker.exe` 的参数对 `native/worker.cpp` 跑 `cl /Zs`（SDK 头含 `Probbl.h`，门控代码参与检查），退出 0，只有既有的 C4819 代码页警告；未产出执行器。
- 格式：Ruff check/format 通过；`native/surface_loft.cpp` clang-format 干跑无差异（只有新增段落被重排）。
- 源码摘要（LF 归一 SHA256 前 16 位）：`native/surface_loft.cpp` `0b5d42eb695b53d4`，`src/creo_mechdog/surface_ops.py` `a13e36baea85057c`，`src/creo_mechdog/capabilities.py` `63cc111d6292f49d`（含 T1b 的并行改动）。

### 未验证范围

- 全部为离线候选：映射已知分支从未执行过；`ProElemtreeElementGet` 以 `TNC_BNDRY` 为根取子元素、`ProElemtreeElementRemove` 删除 `CONNECT_SURF_CHAIN`、追加子元素的顺序是否被 redefine 接受，都没有实机证据。
- `TAN_COND_TYPE` 整数、`TNC_BNDRY` 顺序、`SURF_CHAIN_METHOD`、约束端是否需要改 `TAN_FLD_TYPE`/`STRETCH`，全部待 T2b。读不回来或 redefine 不接受时，M4 记为「实机反证，不发布」，门禁保持。
- `normal` 在 Creo 边界混合里可能需要的参照与「相邻面」不同，未核对；首版把它与 tangent/curvature 同样处理，由 T2b 结论决定是否保留。
- 实机验收标准仍按计划 §5：`creo_measure_surface_curvature` 在共享边上 `g1_max_angle_deg < 0.5` 且 `within_g1=true`，保存重载 verified（T3）。
- `references.py` / `docs/REFERENCE_SYNTAX.md` 未加 `boundary_conditions` 示例（不在 T2a 文件范围内；字段解除门禁前也不应给可执行示例）。

## 2026-11-11 T3 实机验收（M3）与 T2b 试值取证（M4）

用户当次确认授权实机测试，范围是：编译执行器、新建测试模型、试值实验。环境为 Windows x64、Creo 12.4.0.0 + 匹配 SDK；会话是机器上已在运行的 Creo，未结束或重启 Creo，未清锁，未做故障注入。BUG-001 卡死根因仍未定，这一事实照实保留。

### M3 实机验收（提交 `7b5c4ff` 的代码，未加改动）

`bridge.py build` 复用 17:16 的缓存。那次编译不是本会话发起的，但缓存指纹与 `7b5c4ff` 的原生源码一致。之后运行 `tools/test_surface_loft_inputs.py --live --confirm-session-usable`：离线与实机全 PASS，共 40 项实机检查，报告为 `build/surface_loft_inputs/20261111-200556.json`。

- (a) 边补面：`open_edge_records` 列出两张竖直曲面带的 8 条开放边，ID、端点和长度全部正确；按端点取到顶边 53/85，补面为 800 mm² 平面。补面后接缝 gap 0，截面边不再是开放边；保存重载 verified（作业 `3e08cb56…`，模型 `3fc7b219…`）。
- (b) 投影曲线作截面（截面依次为曲线、草图）：直纹面积符合预期（作业 `3a1a5872…`）。
- (c0) 3 个 YZ 椭圆截面沿 X 排列：2075.380558712057 mm²（作业 `c1fabc29…`）。
- (c) 再加收敛点：2415.049123545896 mm²，x 延伸到 60 mm，`convergence_point` 回报正确（作业 `78854815…`）。`PRO_CURVCOLL_ADD_POINT_INSTR` 放进链容器这条 Probbl.h 没有文档的路线，因此得到实机证明。
- (d) 负例：不存在的边 ID 给出结构化拒绝；点放在中间位置，提交前就被拒绝。

### M4 试值取证（T2b，不建参照件）

用户不熟悉 Creo 界面操作，所以没有建参照件，改为在测试模型上用临时实验钩子逐个试候选值，钩子没有提交。共 23 组试验，全部保存重载 verified。详见 [证据](../validation/feat065-t2b-tangency-2026-11-11/EVIDENCE.md) 与 G5 契约 §2.1a 的回填。结论：

- 相切 = `TAN_COND_TYPE` 2 加 `STRETCH`（首截面 -1、末截面 +1）。拱形面积 982.5887974169791 mm²，两条接缝 G1 都是 0.0°。曲面带反向画线后结果完全相同。
- 下标 0 = 首截面，1 = 末截面。面链沿用内核默认（方法 1），引用边的相邻面。
- 值 3：接缝 90°，不是曲率连续。值 4：与自由无法区分。导线边界没有测量。因此只开放首/末截面上的 `tangent`，其余条件在建特征之前以 `not_available` 拒绝。

实验结束后丢弃钩子，`native/surface_loft.cpp` 恢复到实验前版本，再写入实测映射与 `STRETCH`，并删除面链重建代码和 `SURFACE_LOFT_CONNECT_CHAIN_METHOD`。M3 回执的 `live_verified` 改为 true，`unverified_input_forms` 保留字段但恒为空。最终代码的实机复核见下一节。

### 最终代码实机复核（2026-11-11 21:00—21:10）

实验钩子丢弃后，原生代码定稿：写入实测映射与 `STRETCH`、沿用内核默认面链、在建特征前拒绝不可用条件。Python 层同步更新：schema 只放行边来源首/末截面上的 `tangent`；`UNAVAILABLE_FIELDS` 清空，机制保留；文案与测试按实测改写。`bridge.py build` 于 20:36:51 编译出最终执行器，之后依次运行：

- `tools/test_surface_loft_inputs.py --live --confirm-session-usable`：离线 37 项、实机 40 项全 PASS，报告 `build/surface_loft_inputs/20261111-210010.json`。回执中曲线、边、点三种来源 `live_verified=true`，`unverified_input_forms=[]`。
- 新驱动 `tools/test_surface_loft_continuity.py --live --confirm-session-usable`：离线 35 项、实机 59 项全 PASS，报告 `build/surface_loft_continuity/20261111-210431.json`。
  - 显式写 `free` 的基线：800.0 mm² 平面，接缝 A 90.0°，回执为 `status=kernel_default`（作业 `30e5facd…`，模型 `3795e087…`）。
  - 两端 `tangent`：4 个独立模型，分别量接缝 A、接缝 B，以及曲面带 A 反向画线后的 A、B。面积都是 982.5887974169791 mm²，z 最高 15.12 mm，四条接缝的 `g1_max_angle_deg` 都是 0.0、`within_g1=true`，保存重载全部 verified。回执写入 `tan_cond_type=2`、`stretch` 为 -1/+1、`connect_chain=kernel_default`。作业依次为 `5dcd8b2b…`、`9eda7612…`、`60c96476…`、`33b7aa67…`。
  - 负例：`curvature` 在提交前被拒，没有建作业。
  - 合并回执通过 `creo_get_job(detail="full")` 的 operations_result 读取。
