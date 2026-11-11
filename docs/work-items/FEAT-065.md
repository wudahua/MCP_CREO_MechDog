# FEAT-065：多截面 + 纵向导线的 boundary blend（球鼻艏/船体类放样）

## 当前摘要（2026-11-10）

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
