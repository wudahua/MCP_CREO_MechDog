# 模型引用格式（BUG-006）

模型引用首先区分**几何对象**和**特征标签**，再区分单条引用与参数外层容器。`creo_capabilities.references` 保留原有示例键，新增 `syntax` 与 `by_tool`，应按具体工具和参数选用示例。工具列表中的 schema 和描述也给出轴、边、倒圆集合和草图支撑面的格式。

示例中的 ID 只说明 JSON 类型，实际值必须从当前模型巡检取得；几何 ID 和特征 ID 不能互换。标签必须是该模型已有的 MCP 别名。原生几何是否符合要求仍需实际解析、再生和保存重载验证。

## 轴阵列

`creo_axis_pattern.axis` 接受以下三种裸对象，不增加 `reference` 或 `edge` 包装：

```json
{"kind": "axis", "id": 83}
{"kind": "datum_axis_feature", "label": "t82_da1"}
{"kind": "datum_feature", "label": "t82_da1"}
```

第一种是几何轴 ID；第二种是明确的轴特征标签，推荐使用。第三种是为报告 §7-N1 增加的兼容写法：**仅在 axis_pattern.axis 中**按轴参数上下文转换为 datum_axis_feature。它不会把一个实际基准平面变成轴；标签指向的特征仍必须包含一根可解析的轴。

其它参数中的 datum_feature 继续代表基准平面。`{"kind":"datum_plane","axis":"z"}` 的 axis 表示平面法向，不能用作旋转轴。阵列轴必须先于 leader；必要时创建独立基准轴，再用 creo_reorder_features 调整顺序。高层工具和 execute_plan 使用同一规范化逻辑，非法轴类型、缺少 ID/标签会在入队前返回可操作示例，revision 防护保持有效。

## 方向（线性）阵列

计划操作 `linear_pattern` 用模型坐标单位向量表达方向，不接收轴引用：

```json
{"op": "linear_pattern", "label": "rows", "leader": "hole", "direction": [1, 0, 0], "spacing": 42, "count": 2, "flip": false}
```

`leader` 必须指向拥有实体几何的特征（例如 `extrude`、`hole`、`sweep` 或 `feature_group`）。指向草图或基准特征会在提交前（或原生建特征前）以 `LINEAR_PATTERN_NON_SOLID_LEADER` 拒绝，避免静默生成 ΔV=0 的空转阵列；成功回执返回 `feature_id`、`leader_id`、`leader_kind`、`leader_surface_count` 与 `member_count`（[BUG-169](work-items/BUG-169.md)）。

`direction` 必须是长度 1 的 `[x,y,z]`（容差 1e-6），`spacing` 为大于 0 的毫米中心距，`count` 含首例且至少 2，`flip` 只反转方向。Creo 仍需要一个真实方向参考，因此原生把向量绑定到与其平行（余弦 1-1e-9）的第一条直边（按 id 升序），没有直边时绑定到法向平行的第一个平面；参考自身的朝向决定元素树 flip，`flip` 不依赖假设的边方向。绑不到任何参考时明确拒绝并给出候选数，不发明基准轴。2026-11-15 Creo 12.4 实机：100×30×10 板上 Ø4 通孔沿 +X、间距 42、数量 2，两孔中心 x=10/52；`flip=true` 时同一 leader 从 x=52 得到 x=52/10，均保存重载通过。

## 距离+角度倒角

`chamfer` 保持 `size`/`distance`（等距腿）不变；新增 `chamfer_type="distance_angle"`，同时要求 `angle_deg`（0–180，不含端点）与 `angle_reference`（角度所依据、并量取腿距的面）：

```json
{"op": "chamfer", "label": "bevel", "size": 3, "references": [{"edge": {"kind": "geometry_selector", "target": "edge", "endpoints_mm": [[0,0,10],[50,0,10]], "tolerance_mm": 0.001}}], "chamfer_type": "distance_angle", "angle_deg": 70, "angle_reference": {"kind": "geometry_selector", "target": "surface", "axis": [0,0,1], "points_mm": [[25,15,10]], "tolerance_mm": 0.001}}
```

2026-11-15 Creo 12.4 实机测量（50×30×10 块、70°、腿距 3 mm）：`PRO_CHM_ANG_X_D` 的 `PRO_E_RNDCH_LEG1` 是线性腿距、`LEG2` 是角度（写反时特征 status=6）；腿距量在 `angle_reference` 指定的面上，另一面腿长为 3·tan70°=8.2424 mm，去除体积与 0.5·3·8.2424·50 一致，保存重载通过。`chamfer_type` 只是准入别名，native 载荷仍靠 `angle_deg`/`angle_reference` 存在与否区分，等距倒角载荷与旧版一致。

## 两距离不等距倒角（FEAT-071）

`chamfer_type="d1_d2"` 表示两个相邻面分别退距：必须同时给出 `distance_1`、`distance_2`（正数，mm）与 `reference_surface`（显式面引用），并拒绝 `size`/`distance` 及 `angle_deg`/`angle_reference`。原生据此写 `PRO_CHM_D1_X_D2`，`LEG1` 取 `distance_1`、`LEG2` 取 `distance_2`，同时写 SDK 要求的 `PRO_E_RNDCH_REFERENCE_SURFACE`。

```json
{"op": "chamfer", "label": "bevel", "references": [{"edge": {"kind": "geometry_selector", "target": "edge", "endpoints_mm": [[0,0,10],[50,0,10]], "tolerance_mm": 0.001}}], "chamfer_type": "d1_d2", "distance_1": 2, "distance_2": 5, "reference_surface": {"kind": "geometry_selector", "target": "surface", "axis": [0,0,1], "points_mm": [[25,15,10]], "tolerance_mm": 0.001}}
```

SDK 依据：本机 `ProChamfer.h` 声明 `PRO_CHM_D1_X_D2 = 603`，该 schema 要求 `PRO_E_RNDCH_LEG1`、`PRO_E_RNDCH_LEG2` 与 `PRO_E_RNDCH_REFERENCE_SURFACE`。

2026-11-21 本机 Creo 10.0.0.0（release 42）实机（50×30×10 块，顶边 y=0/z=10，`reference_surface`=顶面）：`distance_1`/`distance_2` 分别为 2/5 时，前侧面腿 2.0 mm、顶面腿 5.0 mm；对调为 5/2 时前侧面 5.0 mm、顶面 2.0 mm。即在该参考面组合下 **D1 落在未在 `reference_surface` 指定的相邻面，D2 落在 `reference_surface` 指定的面**，两次去除体积均为 0.5·2·5·50 = 250 mm³，保存重载通过。其他参考面组合、曲面边与其他 Creo 版本未验，本实现仍不从边/面集合顺序或法向推断方向。

独立工具 `creo_chamfer` 与计划操作共用同一契约：`distance`（或 `size`）对应等距，`chamfer_type`/`angle_deg`/`angle_reference` 对应距离+角度，`distance_1`/`distance_2`/`reference_surface` 对应 `d1_d2`；等距与距离+角度的旧载荷与行为不变。


## 显式平面几何 ID（BUG-084 / T03）

`datum_plane.id` 使用当前模型 `creo_inspect_model(section="datum_planes")` 返回的**基准平面几何 ID**；`plane.id` 使用当前模型中经验证为平面的几何 ID；`surface.id` 沿用面几何 ID，草图支撑面仍须确实平面。特征标签使用 `datum_feature`。特征 ID 与几何 ID 不互换，同一个数字也不能靠类型猜测重解释。

```json
{"kind":"datum_plane","id":163}
{"kind":"plane","id":163}
{"kind":"surface","id":163}
{"kind":"datum_feature","label":"right_plane"}
```

前三个 ID 只是格式示例，调用前须从**目标模型本次巡检**选取。显式 `plane`/`datum_plane` ID 与同一引用对象的 `axis`、`normal`、`offset` 互斥，连默认 `axis:"z"` 或 `offset:0` 同现也拒绝；不带 ID 时保留几何筛选模式。`creo_create_sketch.plane` 的字典把上述一个裸引用放在 `reference` 内，可另给 `origin`、`u_axis` 帧字段。支撑面缺失、非平面或不唯一时明确失败，不能回退默认 XY。结果 `operations[]` 的 `surface_id`、`origin`、`normal`、`u_axis`、`v_axis` 来自原生解析；`u_axis` 必须非零且在真实支撑面内有非零投影。无新 Toolkit 连接的离线验证不能替代这些几何数值的实机核验。

## 平面 axis/normal 筛选器（匹配已有面，P05）

不带 ID 的平面引用是**已有面筛选器**，合法形状例如：

```json
{"kind": "plane", "axis": "z"}
{"kind": "plane", "normal": [0, 0, 1], "offset": 10}
```

语义是在**当前模型中**按法向（`axis` 是 `x/y/z` 的简写，`normal` 是任意非零 3D 向量）和偏置匹配一张已有的平面支撑面；候选不唯一或不存在时明确失败。它**不是**"按法向创建新基准面"的输入，服务也没有按法向建面的入口；需要新基准面时用 `creo_datum_plane`（其 `reference` 内部的筛选 offset 与操作自身的 offset 是分开的两个值）。缺 `kind` 的引用、未知标签在入口即拒绝，不透出 JSON 缺键异常。字典 offset 旧摘要（0.9.0 反馈 F4 S6）指的就是该筛选器的 `offset` 字段：它是匹配条件，不是新建偏移距离。

**两种平面形式的取舍（BUG-116，0.19.3 反馈）**：`{kind:"plane",normal,offset}` 按几何位置在**面集合**里找面，`{kind:"datum_plane",axis,offset}` 只在**基准面集合**里找。真实模型同一高度常有多张平行基准面（草图支撑面会被自动创建为 `no_name` 基准面），此时 `datum_plane` 形式会被拒绝。拔模 `neutral_plane` 等"取某个高度的平面"场景优先用几何形式，或直接用巡检返回的 `plane`/`surface` ID；被拒绝时回执会给出匹配到的候选数、候选 ID 列表，并用 `failed_reference field=...` 指名是哪个参数解析失败。

## 加料体积保护与实体包围盒（0.45.0）

`extrude`、`revolve`、`sweep`、`loft` 的 `mode="add"` 会在再生后、保存前核对总体积。允许零净增量。下降超过 `max(1e-6 mm³, 加料前体积 × 1e-12)` 时返回 `add_reduced_volume`，可靠测量无法建立时返回 `add_volume_unverified`。写作业按原检查点整单回滚。`volume_before_mm3`、`volume_after_mm3`、`material_delta_mm3` 和 `add_volume_check` 提供测量和判据。 [BUG-191](work-items/BUG-191.md)

零件和装配的 `bounding_box_mm` 在当前模型坐标系内从裁剪后的实体面网格取边界。旋转装配先把实体面网格变换至装配坐标系再求极值。`bounding_box_source="solid_face_tessellation"`，`bounding_box_status` 披露采样目标弦高，以及 `measured`、`no_solid` 或 `unavailable`。旧快照的历史轮廓保存在 `legacy_regeneration_outline_mm`，用 `creo_refresh_model` 可重新测量。 [FEAT-078](work-items/FEAT-078.md)

## 启动未就绪与持续不可达（0.45.0）

自动发现会话时，已观察到 Creo 进程且 Toolkit 返回 `-4`（`PRO_TK_E_NOT_FOUND`），`waiting_for_connection` 与 `diagnosis=session_not_ready` 表示协调器会在原连接截止时间内再查。`probe_attempts` 统计已经返回的连接探针。现有进程在原预算内持续查询失败时，`timeout` 附 `stale_session_needs_restart` 和 `last_lookup_failure`。探针自身超时通过 `native.connection_state=probe_timeout` 表示。 [BUG-170](work-items/BUG-170.md)

## 基准面角度的正负与位置

`creo_datum_plane` 和计划中的 `datum_plane` 使用带符号的度数。`angle` 的正向按 `axis` 所引用的**实际有向轴**应用右手定则。沿轴从正端朝负端看，正角为逆时针。用 `creo_inspect_model(detail="full", section="datum_axes")` 读取轴的 `direction` 和 `origin`。用 `creo_inspect_model(detail="full", section="datum_planes")` 复核已保存平面的 `normal` 和 `origin`，并按 `feature_geometry` 将特征 ID 对应到平面几何 ID。

Creo 10.0.0.0 实测，默认 `flip=false`，`RIGHT` 面起始法向为 `(1, 0, 0)`。绕过模型原点的 Z 轴旋转后，两种有向轴下生成的纯旋转面均通过该轴，`origin` 在测量精度内为 `(0, 0, 0)`。保存重载后的法向如下。

| 实测轴方向 | `angle=+54` 的法向 | `angle=-54` 的法向 |
| --- | --- | --- |
| `+Z` | `(0.587785, 0.809017, 0)` | `(0.587785, −0.809017, 0)` |
| `−Z` | `(0.587785, −0.809017, 0)` | `(0.587785, 0.809017, 0)` |

需要通过 `(−5.090109, −7.005933, 0)` 的平面时，先绕 `+Z` 转 `+54°`，再用第二个 `datum_plane` 沿旋转后的法向偏移 `−8.65981 mm`。把第一步角度换为 `−54°` 并使用相同偏移，得到镜像点 `(−5.090109, +7.005933, 0)`。

0.9.0 外部报告用 `−54°` 得到正 Y 法向，原报告也记录该轴实测方向为 `−Z`。0.44.0 外部报告用 `+54°` 得到相同法向。本机在 Creo 10 已用 `−Z` 和 `+Z` 分别复现两种结果。轴方向足以解释这组差异，同一有向轴下两个 MCP 历史版本是否存在行为差异尚未对跑。 [BUG-094 实机与历史记录](work-items/BUG-094.md#2026-11-25-基准面角度与位置复核)

## 钣金展开固定面（fixed_surface，P05）

`sheetmetal_unbend`/`sheetmetal_flat_pattern`/`sheetmetal_bend_back` 的 `fixed_surface` 是一个**裸面引用**（与其他引用同一解析语义），如：

```json
{"kind": "surface", "id": 11}
```

它指定展开/折回过程中保持固定的几何；`references` 省略时作用于全部折弯。选中的几何能否真正固定由原生执行器判定，Python 侧不预判。

## 任意平面 coordinates 标注（FEAT-010 / T04）

`dimensioning="auto"`（默认）在没有用户尺寸或约束且图元支持坐标标注时选择 `coordinates`，包括单圆和其他小轮廓。创建与替换都在求解后、完成特征后核对绝对偏差，整体平移计入偏差。默认上限为 `1e-5 mm`，显式 `geometry_tolerance_mm` 可设定上限。超差或无法完成测量会拒绝提交。样条插值 `spline`、椭圆及带用户尺寸或约束的创建请求继续走 `autodim`。

`dimensioning="coordinates"` 与 auto 路由的坐标标注不再限于主平面字符串：字典平面（任意有效支撑面）同样创建完整坐标尺寸，编辑路径（`creo_update_sketch_geometry`）不再因非主平面法向拒绝或强制退回 autodim。坐标尺寸在**原生 section 局部坐标**中创建并回读核验；草图 U 轴与 section 轴成任意角度时，输入 u/v 分量按主导 section 轴命名（日志 `COORDINATE_AXES`），不再报 "requires principal section axes"。

- 创建、就地编辑与同几何快捷路径共用同一坐标变换（T03 实际帧 `origin/u_axis/v_axis`）与 1e-5 mm 回读门槛；不放宽阈值、不改输入坐标、不静默降级，核验失败如实报错并回滚。
- 中心线按**直线身份核验**：比较方向与两端点到目标无限线的偏移（日志 `COORDINATE_CENTERLINE_IDENTITY`），不依赖可能被求解器滑动的端点。轴平行中心线仍用基准投影线偏移尺寸固定；斜中心线不生成已知不稳定的端点尺寸（日志 `COORDINATE_CENTERLINE_SKEW`），仅靠核验兜底。
- **共享顶点与轴对齐共坐标跳过（BUG-174 / P4）**：`dimensioning="coordinates"` 对已标注过的共享折线顶点（`COORDINATE_SHARED_VERTEX_SKIPPED`）以及轴对齐线段上与起点同轴的终点分量（`COORDINATE_AXIS_LINE_SHARED`）不重复落尺寸，以避免与内核推断的重合/水平/竖直约束冲突导致过约束。因此 4 条直线组成的轴对齐矩形只会生成 5 个独立坐标尺寸（加 2 个原点固定尺寸），**不能用原始尺寸个数判断轮廓是否完全约束**；坐标保真度一律由求解并再生后的 `geometry_deviation`（逐点最大偏差与去平移残差 ≤ 1e-5 mm）判定。
- **三点斜基准面自动垂直锚定参考（BUG-173 / P2）**：在 `datum_plane {kind:"through_points"}` 等斜基准面上创建草图时，`ProSectionEntityFromProjection` 对不垂直于草图平面的基准面返回 `-2`（`PRO_TK_BAD_INPUTS`）。当支撑面法向恰好与某一个已有基准面垂直（`orientation_exact=true`）但模型中缺少第二个同时垂直于支撑面与 orientation 面的基准面时，执行器会在创建草图前自动补建一个过轮廓形心、法向为 `cross(support_normal, orient_normal)` 的辅助基准面（日志 `SKETCH_ANCHOR_HELPER=1`），并在同支撑面的后续草图中自动复用；无需调用方手工预建锚定面。草图回执的 `section_references` 记录 `anchor_count`、`reference_incomplete`、`helper_anchor_created` 与 `origin_pin_available`；若 `ProSectionSolve` 仍失败，报错直接给出 `ProSectionSolve` 返回码、救援 `ProSectionAutodim` 返回码及 `section_references` 摘要。
- **盲切去料比例诊断（BUG-174 / P3）**：`extrude mode="cut"` 且 `depth_type="blind"` 成功去料时，回执附加只读的 `cut_volume_check`（`profile_area_mm2`、`effective_depth_mm`、`expected_prism_volume_mm3`、`actual_removed_mm3`、`removal_ratio`、`low_removal_warning`）。当实际去料低于解析棱柱体积 `area × depth` 的 5%（`low_removal_warning=true`）时提示核对切除 `direction` 或草图轮廓是否大部落在实体外；合法的部分交集切除仍正常提交，不因该告警回滚。
- 图元集合与互斥边界不变：line/centerline/rectangle/polyline/circle/arc/b_spline；显式 dimensions/constraints 与 coordinates 仍互斥；ellipse/spline 仍走 autodim，本项不扩展。

## 坐标容差与旋转范围（BUG-108 / BUG-111，R13）

**`geometry_tolerance_mm` 的含义**：它是**验收放行阈值**（判定求解结果是否可接受），不是求解精度设置，也不会让内核"解得更好"。缺省时 `coordinates` 按 1e-5 mm 判定形状、autodim 按 1e-3 mm 只告警不拒绝。

**显式 `dimensioning="coordinates"` 的形状与平移判据**：坐标求解可能整体移动截面（外部实测 1.6e-5 ~ 4e-3 mm）。显式选择该模式时，按既有的形状残差与平移上限分别验收：

```json
{"geometry_deviation": {"max_deviation_mm": 0.000016, "shape_deviation_mm": 0.0,
                        "residual_mm": 0.0, "rigid": true,
                        "translation_mm": {"u": 0.000016, "v": 0.0},
                        "accepted_rigid": true},
 "sketch_shifted": {"detected": true, "rigid": true, "accepted_rigid": true,
                    "translation_mm": {"u": 0.000016, "v": 0.0}, "residual_mm": 0.0}}
```

- 可证刚体平移且平移量 ≤ **1e-2 mm** → 放行，`accepted_rigid=true`，日志 `GEOMETRY_DEVIATION_RIGID_ACCEPTED`；
- 刚体平移超过 1e-2 mm → 拒绝，错误里同时给平移量与该上限；
- **真实变形（残差 > 1e-5 mm）仍拒绝**，默认阈值没有放宽；显式 `geometry_tolerance_mm` 仍是收紧/放宽验收的唯一手段。

**`rotation` 范围**：`geometry_transform` 与 `set_geometry_transform` 的每个 `rotation` 分量必须落在 **-180..180 度**。超范围在提交前拒绝并给等价值，例如：

```json
{"error": "rotation[2]=225 deg is outside the supported range of -180..180 deg; use the equivalent -135 deg"}
```

两种原生后端统一归一为 `(-180, 180]`，因此 `-135` 与 `225` 指向同一旋转（旧实现把负角 `+360`，两者走了不同路径）。失败回执带 `failed_transform`（`backend`、`rotation_deg`、`rotation_normalized_deg`、`translation_mm`、`keep_original`、`reference_count`、`reference_kinds`）。

**`keep_original` 批量复制（BUG-111，0.11.7 定因口径）**：`keep_original` 复制的是**整个当前体**，副本累积在**同一个 body** 内（特征数 +1/副本，不新增 body）。追加副本能否成功取决于"既有副本集合 × 该角度"，**不是副本数量上限**：本机 Creo 12.4 四个独立模型（C2/C3/C5 与 C6 批 B）同型失败于 `operation_index=4`（`failed_stage=execute_geometry_transform`，消息 `Regeneration produced a failed, suppressed or incomplete feature`，前序 op `effect_status=rolled_back`），而把 −135 放在首位的 C4 五个副本**全部成功**、拆成 4+3 两批的 C6 仍在批 B 首个 op 失败。**"单批 ≤4 个副本、下一批重新引用当前 body"的变通建议已作废**（拆批实测无效）：把副本集放在同一计划里提交即可；需要"固定原件"的副本时应另建模型。失败回执的 `failed_transform` 给出 `backend`、`rotation_deg`/`rotation_normalized_deg`、`keep_original`、`reference_count`，并附有界 `selection` 块（`requested_body_ids`、`selected_surface_count`、`model_counts_at_start`：`features`/`surfaces`/`bodies`/`active_bodies`，取自 op 开始时的巡检，巡检未提供的项记 `null`）；`failed_operation_index` 与 `failed_transform.label` 指明是哪一步失败。Creo 10 报告方在 `ProFeatureWithoptionsCreate` 上拿到裸 `-1`，位置相同，**Creo 10/9 行为仍未验证**。

## 回转轴（revolve.axis，BUG-083）

`creo_revolve.axis` 与 execute_plan 的 `revolve` 操作 `axis` 字段接受以下两种裸对象，不增加 `reference`/`entity`/`edge` 包装：

```json
{"kind": "datum_axis_feature", "label": "axis_label"}
{"kind": "axis", "id": 83}
```

第一种引用同一模型中**先创建**的基准轴特征（例如先用 `datum_axis` 操作或 `creo_datum_axis` 创建，再回转引用其标签），推荐使用；第二种是模型巡检取得的几何轴 ID。axis_pattern 专用的 `datum_feature` 兼容别名不适用于回转。

**省略 axis 或显式传 null**：回转轴取草图自身的构造中心线，此时草图必须恰含一条 centerline（示例 [examples/turned_part.json](../examples/turned_part.json)）。**空对象 `{}`、缺 `kind` 的结构（如 `{"entity":"ax"}`）、非轴 kind、缺失 id/label 会在入口被拒绝**：错误信息含字段路径与上述可用示例，且不派发原生作业；`{"entity":"ax"}` 不会被静默猜测为外部轴。原生执行器对同类非法结构保留第二道边界防御，作业以结构化错误结束（含失败阶段与操作序号），不再透出 nlohmann JSON 异常文本。高层工具与 execute_plan 使用同一规范化逻辑，revision 防护保持有效；显式外部轴示例见 [examples/revolve_external_axis.json](../examples/revolve_external_axis.json)。

## 曲面链引用（surface trim / project curve / surface offset，FEAT-039 / DEV-069）

三个已发布曲面工具都只接受**裸引用对象**，不增加 `reference`/`entity` 包装。几何对象用几何 ID，特征标签用 `quilt_feature`；`quilt`、`curve` 等几何 kind 不接受 `label`。下面的 ID 仅为类型示例，实际值须从目标模型本次巡检取得。

```json
// creo_surface_trim：target 是 quilt；tool 是 quilt、基准面标签或曲线几何 ID
{"target": {"kind": "quilt", "id": 21},
 "tool": {"kind": "quilt_feature", "label": "trim_fill"},
 "keep_side": "one"}

// tool 也可以是基准面标签或曲线 ID（曲线修剪走 use-curve 变体）
{"target": {"kind": "quilt_feature", "label": "blade_quilt"},
 "tool": {"kind": "datum_plane", "label": "FRONT"},
 "keep_side": "two"}
{"target": {"kind": "quilt", "id": 21}, "tool": {"kind": "curve", "id": 41}, "keep_side": "one"}
```

`keep_side` 只有 `one`/`two`，表示保留哪一侧，不是 GUI 视图名。终态 `kept_side_basis` 报告实际依据：quilt 或基准面工具为 `side_reference="tool_plane_normal"`，曲线工具为 `"curve_direction"`（反向曲线会交换保留区域）；`tool_normal` 只在基准面工具上是真实向量。`target` 与 `tool` 必须不同，且只接受一个 tool。

```json
// creo_project_curve：一张 quilt、一条曲线几何 ID、一个能读出真实方向的方向引用
{"target": {"kind": "quilt", "id": 21},
 "source": {"kind": "curve", "id": 7},
 "direction_ref": {"kind": "datum_feature", "label": "TOP"},
 "side": "positive"}
```

`direction_ref` 接受 `datum_feature`/`datum_axis_feature` 标签，或直的 `{"kind":"curve","id":N}`。`side` 只翻转该方向，只有 `positive`/`negative`。投影按“源草图沿方向扫掠 + 官方相交曲线”构造，模型会多一个辅助曲面特征，其 ID 由 `helper_feature_id` 返回；方向须平行于源草图平面法向，目标须在请求一侧，源曲线须属于曲线特征。`source` 只接受 `curve` 几何 ID，**不接受** `edge` 或 `axis`；`direction_ref` **不接受** `{"kind":"datum_plane","label":...}`（该解析器会丢掉标签并取默认平面）或裸向量。

```json
// creo_surface_offset：源 quilt，沿曲面法向偏移
{"reference": {"kind": "quilt_feature", "label": "fill_label"},
 "distance": 5.0,
 "side": "positive"}
```

`creo_surface_offset` 的结果是会增加实体体积的**偏置壁**，不是独立偏置 quilt。`target_quilt_id` 指向源 quilt，不代表新产生、可供下游修剪或合并的 quilt。只有单一平面源、偏置前体积近零等计量条件满足时才以体积÷面积发布实测距离；其他情况实测距离为 null，原因见 `offset_distance_status`。`creo_thicken`/`creo_solidify` 保留各自从 quilt 生成实体的独立契约。`side` 只回显请求侧，几何 z 符号不回读。该工具用 `distance`，不吃 `offset_mm`；`surface_trim` 的 `offset_mm` 是另一条被门禁的薄修剪路线，当前拒绝文案为：

> surface_trim offset_mm is not published: the documented Thin tree (PRO_SURF_TRIM_THIN with PRO_E_THICKNESS/PRO_E_SRF_OFFS_METHOD) only removes a band of that thickness when the tool is a quilt, keeps both sides instead of the requested keep_side, and offset_side has no observable effect (2026-11-06 six direction variants all produced the same band; negative thickness fails regeneration)

```json
// creo_surface_loft：2—32 个截面草图，可选 2—8 条第二方向导线
{"sections": ["sec_a", "sec_b"],
 "interpolation": "straight",
 "guides": ["guide_left", "guide_right"]}
```

`creo_surface_loft`（`surface_loft`）自 0.18.3 起公开，**取代**了「多截面放样未发布」的旧说法：2—32 个截面草图按提交顺序建一张边界混合曲面，两截面为直纹（`interpolation="straight"`），三截面及以上由内核拟合成一张光滑面，必须显式 `interpolation="smooth"`。`guides` 是可选第二方向：2—8 个草图、每条恰好一条非复合曲线、不得与截面重复；只给一条导线在校验层直接拒绝（实测单条 2DIR 曲线能建特征但不再生）。导线是否穿过截面由内核判定，不穿过就再生失败而不是被忽略。`creo_loft` 本身仍只接受 `mode="add"`，`mode="surface"`、`cut` 与 `new_body=true` 都在入队前拒绝，实体放样与曲面放样是两条独立路线。

**`creation_route`（BUG-120）**：省略或传 `element_tree` 时保持上面的 2—32 截面、2—8 导线与边界条件语义。`resident_panel` 是 Creo 10 / release 42 的独立后端。0.28.0 的认证 profile 是 `creo10-bbl-candidate-2`（仅第一方向 2—8 个草图标签）；2026-11-19 起公开认证 profile 为 `creo10-bbl-candidate-3`（candidate-2 的超集，后者保留为独立认证记录）：第一方向 **2—8 个 MCP 自有草图标签**（每个标签一条开放非复合曲线），或把一个只在首/末的收敛点 `{"kind":"datum_point_feature","label":"..."}` 作为端点（每个放样最多一个）；可选第二方向 **2—8 条导线**；单次最多 **11 个位置**（7 曲线 + 1 点 + 3 导线的上限；已分别验收 7 曲线 + 3 导线 = 10 与 7 曲线 + 1 点 = 8）；2 截面直纹，3 截面及以上需 `interpolation="smooth"`；不接受边界条件或模板。**点与导线不能同时出现在一个特征里**：Creo 10 在该组合上选择成功后再生失败，所以点收敛段要作为共享末截面的第二个放样提交（两段式球鼻艏实例见 [BUG-120](work-items/BUG-120.md) T-D）。它需要已部署并注册的 panel callback（protocol 4 / loader ABI 2），缺 profile、部署不匹配或形式超出认证范围时在**提交前**拒绝（profile 没有 `second_direction_macro` 时，带 `guides` 的请求不会建作业），**不回退** `element_tree`。`creo10-bbl-candidate-1` 仍是未认证录制件，仅供开发驱动 `CREO_MECHDOG_PANEL_CANDIDATE` 使用。

**截面/导线的已有几何引用（FEAT-065 M3；2026-11-11 Creo 12.4.0.0 实机验收通过）**：`sections`/`guides` 的元素除草图标签或特征 ID 外，还接受下列既有裸引用，不加 `reference`/`chain` 包装，每个元素对应一个链容器：

```json
// 截面：已有曲线（如 project_curve 回执的 curve_id）或边；首/末截面可为一个收敛点
{"sections": [{"kind": "edge", "id": 12}, {"kind": "edge", "id": 13}],
 "guides": ["guide_left", "guide_right"]}
{"sections": [{"kind": "curve", "id": 41}, "sec_b"]}
{"sections": ["sec_a", "sec_b", "sec_c", {"kind": "datum_point_feature", "label": "tip"}],
 "interpolation": "smooth"}
```

- `{"kind":"curve","id":N}`：一条 `PRO_CURVE` 几何 ID（`creo_inspect_model(section="feature_geometry")` 中 type 62，或 `project_curve` 的 `curve_id`）；复合曲线不拒绝，回执 `section_sources[i].composite` 标出。
- `{"kind":"edge","id":N}`：一条边的几何 ID；回执给出 `adjacent_surface_ids`（边两侧的面，quilt 边界边只有一侧）。`creo_inspect_model` 的 `edges` 只枚举实体面上的边；**quilt 边的 ID 从 `creo_measure_surface_group` 回执的 `group.open_edge_records` 取**（FEAT-065 T1b，2026-11-11 Creo 12.4.0.0 实机验证：两张曲面带的 8 条开放边全部列出，按端点取到两条顶边）：每条开放边给出 `edge_id`、`surface_id`、所属 `quilt_id`、`length_mm` 与两端点 `endpoints_mm`，按端点坐标挑边。最多列 32 条，`open_edge_records_total` 恒等于 `open_edges`，`open_edge_records_truncated=true` 表示有边没列出，减少一次测量的 quilt 数即可看到其余边；模型单位换算未知时 mm 值为 null、ID 照列。
- 收敛点 `{"kind":"point","id":N}` 或 `{"kind":"datum_point_feature","label":...}`（单点 `datum_points` 特征）：只能放在 `sections` 第一项或最后一项，每个放样最多一个，不能作导线。原生用 `ProCrvcollection.h` 文档化的 `PRO_CURVCOLL_ADD_POINT_INSTR` 把点放进链容器；`Probbl.h` 没有说明链容器能装点，这条路线由 2026-11-11 实机证明可用。
- 每个元素一个几何项：一个截面只装一条曲线或一条边，多条边拼成的闭合截面暂不支持（草图截面仍可是两条曲线的闭合轮廓）。
- 提交前拒绝：点出现在中间位置或导线里、两个点、几何 kind 带 `label`、多余字段、`quilt`/`surface` 等非链 kind、同一引用重复或既作截面又作导线。只有原生能判定的（ID 不存在、类型不对、标签不是单点基准点）在作业中以 `SURFACE_LOFT_INPUT_REJECTED` 失败并回滚，失败记录带 `failed_loft_input`（`role`、`index`、`slot`、`request`、`reason`、`query_code`、`use_instead`）；ID 实际是另一种几何时，消息直接给出可用写法。
- 回执新增 `section_source_kinds`/`guide_source_kinds`（`sketch`/`curve`/`edge`/`point`）、`section_geometry_ids`/`guide_geometry_ids`（每个链容器实际装入的几何 ID）、`section_sources`/`guide_sources`（逐项来源记录，曲线/边/点来源带 `live_verified=true`）与 `convergence_point`。`unverified_input_forms` 为兼容旧回执保留，四种形态均已实机验证，恒为 `[]`。`section_curve_ids`/`guide_curve_ids` 保持原义，只列曲线 ID。旧的纯草图计划行为与回执原有字段不变。
- 实机数值（2026-11-11，Creo 12.4.0.0，40 项检查全部通过）：两条曲面带顶边作截面、两条草图导线，补面 800 mm²，接缝 gap 0，截面边不再是开放边；`project_curve` 曲线作首截面，直纹面积 1131.37 mm²；三个 YZ 椭圆截面沿 X 排列 2075.38 mm²，末端加收敛点后 2415.05 mm²、x 延伸到 60 mm；不存在的边 ID 以 `SURFACE_LOFT_INPUT_REJECTED` 失败，中间位置的点在提交前拒绝。四个成功用例均通过保存重载核验。

**边界相切（FEAT-065 M4，`boundary_conditions`；2026-11-11 Creo 12.4.0.0 实机测定）**：截面来源是边时，可以让放样面在首、末截面处与该边所在的面相切。

```json
// 两张曲面带的顶边作首、末截面，两端都与各自曲面带相切
{"sections": [{"kind": "edge", "id": 53}, {"kind": "edge", "id": 85}],
 "boundary_conditions": [{"boundary": "first_section", "condition": "tangent"},
                         {"boundary": "last_section", "condition": "tangent"}]}
```

- 每项是 `{"boundary": ..., "condition": ...}`，最多 4 项，同一边界只能出现一次。
- 只公开 `condition="tangent"`，且只能用于 `first_section`/`last_section`；该截面必须是 `{"kind":"edge","id":N}`，且这条边只有一个相邻面（quilt 边界边，ID 从 `open_edge_records` 取）。相邻面由原生按边自动解析，不另给参数。
- 相切方向固定为「顺着相邻面延伸」，没有翻转或权重参数。方向由边界决定，与边的走向、面的法向无关：把其中一张曲面带的草图线反画（边方向和面法向都翻转），结果完全相同。
- `condition="free"` 可用于任何边界，不写入任何元素，等同于省略。
- 提交前拒绝：`curvature`（候选值实测把形状改成 915.99 mm²，但接缝仍是 90°，不是曲率连续）、`normal`（候选值在实测几何上与 `free` 一样仍是平面，无法区分）、`first_guide`/`last_guide` 上的非 `free` 条件（导线边界未测）、来源不是边的截面上的 `tangent`。原生在建特征之前再检查一次，手写计划绕过校验时以 `SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED`（`reason="not_available"`）拒绝；边有两个相邻面时以同一前缀、`reason="adjacent_face_count"` 失败，均不产生特征。
- 回执 `boundary_conditions[]` 逐项回显 `boundary`、`condition`、`edge_id`、`surface_id`；写入的项另有 `status="written"`、`tnc_index`、`tan_cond_type`、`stretch`、`connect_chain="kernel_default"`。
- 实测：两张 40×10 mm 竖直曲面带相距 20 mm，用两条顶边作截面、不加导线。自由时补面为 800 mm² 平面，与曲面带成 90°；两端 `tangent` 时补面成拱形，982.5888 mm²，包围盒 z 最高 15.12 mm，与两张曲面带分别 JOIN 后用 `creo_measure_surface_curvature` 测得接缝法向夹角均为 0.0°（`within_g1=true`）。

`extrude(mode="surface")`、`revolve(mode="surface")`（含局部角度）以及曲面特征上的 `axis_pattern` 已有 Creo 10 报告方实机正证据；它们不替代多截面放样或 quilt 合并。`creo_quilt_merge` 自 0.19.0（FEAT-039 H03）起已公开：只支持两片相接/相交 quilt 的 JOIN，在 `target` 上原地重剪（`result_quilt_source="retrimmed_target_quilt"`）。**merge/mirror/trim 的结果在 BUG-143 起可由特征标签重新引用**：原生把该标签解析为操作实测的结果 quilt（同计划内），回执同时给出 `quilt_id`；无法唯一定位结果 quilt 时明确拒绝并附候选，不按 bbox 或最近 quilt 猜测。2026-11-21 本机 Creo 10 实机：`quilt_merge` 结果标签被同计划的 `solidify` 消费，`target_quilt_id=71`、体积 785.3981633974481 mm³、保存重载通过；`surface_fill` 标签同样可被引用（开放 quilt 被正确拒绝）。标签别名按作业持有，**跨作业**应使用前一次回执发布的 `quilt_id`，或继续引用**原始 target** 的标签或几何 ID；旧版本解析 merge 特征标签会得到 `ProFeatureGeomitemVisit -4`（2026-11-10 Creo 10 上报，见 [BUG-115](work-items/BUG-115.md)）。修剪结果 quilt 通过特征标签再次引用、弯曲 quilt 的偏置距离读回与保留侧的几何判据仍未闭环；需要从当前模型的 `inspect_model(section="quilts")` 获取实际几何 ID，不能把请求值当成实测值。

## 各工具的外层形状

| 工具 / 参数 | 完整形状或规则 |
| --- | --- |
| datum_plane.reference | 裸平面/面引用，如 `{"kind":"datum_plane","id":163}`、`{"kind":"datum_plane","axis":"z"}` 或 `{"kind":"datum_feature","label":"plane_label"}`；操作自身的 offset 与引用内部的筛选 offset 分开 |
| revolve.axis | 裸轴引用（`datum_axis_feature`+label 或 `axis`+id）；省略或 null 用草图构造中心线，空对象/缺 kind 在入口拒绝 |
| datum_axis.references | 裸引用数组，如两张基准平面；圆柱面、直边或现有轴需满足实际几何要求 |
| datum_csys / datum_points.reference | 裸坐标系引用，如 `{"kind":"default_csys"}`、几何 csys ID 或 datum_csys_feature 标签 |
| hole.placement/reference1/reference2 | 各自直接传入裸引用，placement 为放置面，reference1/2 为定位参考；平面定位参考可用 `datum_plane.id` 几何 ID |
| hole.standard | `{"series":"ISO","size":"M6","thread_depth":8}`：按安装孔表建螺纹孔。此时 `diameter` 可省略（给了必须等于表内名义直径），`depth` 必填，`thread_depth` 必须严格小于钻尖深度且不超表内上限；回执给 `thread_metadata` 与 `thread_metadata_verified`（只有创建后特征树回读一致才为 true），非标准孔回执不变 |
| draft.surfaces/neutral_plane/pull_direction | surfaces 是裸面引用数组；neutral_plane 和 pull_direction 分别是裸单引用。neutral_plane 优先用 `{kind:"plane",normal,offset}` 或巡检的 `plane`/`surface` 几何 ID；`datum_plane` 的 axis+offset 只在候选唯一时成立，多张平行面会被拒绝并列出候选（BUG-116）。`pull_direction` 省略或为 null 时取中性面法向 |
| draft.angle/flip | `angle` 为带符号的度数。`flip=false`（默认）沿 Creo 的拔模引用方向，`flip=true` 反向。以底面为中性面且拔模方向指向自由端的外圆柱为例，正角缩小自由端，负角扩大自由端。改变 `flip` 或角度符号均反转锥度。`draft_geometry.effective_flip` 来自原生树，平面引用的 `applied_pull_vector` 给出应用反向设置后的模型坐标向量。基准轴的 `pull_vector` 为轴线几何方向，`applied_pull_vector` 为 null。 |
| boolean_bodies.targets/tools | 裸 body 引用数组，须明确不同 body ID；不能传特征 ID。巡检可能返回负 body ID，但当前布尔入口不支持把负 ID 作为目标或工具；这不表示巡检记录无效。正 ID 也不保证能把独立实体并入钣金主体：报告方在 Creo 10 对钣金体与实体做双向 union 均遇到原生 `-1` 并回滚，当前未提供钣金体融合能力 |
| 钣金模型的 extrude/revolve add | 普通 `extrude(mode="add", thin=null, new_body=false)` 在建模前以 `SHEETMETAL_SOLID_ADD_UNSUPPORTED` 拒绝；`new_body=true` 创建的是独立实体，不保证能与钣金主体融合。`thin` 增料与 `revolve` 增料未被该准入规则阻断，但目标 body 与合并结果尚无可靠契约，不能据此视为钣金主体增料 |
| solidify.reference | 裸平面/曲面参考，可用已验证平面的 `plane.id` 几何 ID；平面裁剪示例使用 mode=cut，quilt 分支按既有能力限制验收 |
| surface_fill.sketch | 草图特征标签或特征 ID（字符串或整数），无需 `{kind:...}` 对象 |
| thicken.reference | 裸 quilt 或 quilt_feature 引用 |
| surface_trim.target/tool | target 一个 quilt；tool 一个 quilt、基准面标签或曲线几何 ID；`keep_side` 只用 `one`/`two`，实际依据见 `kept_side_basis`；`offset_mm` 仍拒绝 |
| project_curve.target/source/direction_ref | target 一个 quilt；source 只接受 `{"kind":"curve","id":N}`（不接受 edge/axis 或曲线标签）；direction_ref 接受 `datum_feature`/`datum_axis_feature` 标签或曲线 ID，不接受 `datum_plane` 标签或裸向量 |
| surface_loft.sections/guides | 每个元素是草图标签/特征 ID，或裸引用 `{"kind":"curve","id":N}`、`{"kind":"edge","id":N}`；只有首/末截面可为一个收敛点 `{"kind":"point","id":N}` / `{"kind":"datum_point_feature","label":...}`。引用形态为 FEAT-065 M3，2026-11-11 Creo 12.4.0.0 实机验收通过 |
| surface_loft.boundary_conditions | 最多 4 个 `{"boundary","condition"}`，每个边界一次；只公开 `tangent`，限 `first_section`/`last_section` 且该截面是只有一个相邻面的 `{"kind":"edge","id":N}`，方向固定为顺着相邻面延伸；`free` 任意边界可用；`curvature`、`normal`、导线边界上的非 `free` 在提交前拒绝（FEAT-065 M4） |
| surface_offset.reference | 裸 quilt 或 quilt_feature 引用；距离字段是 `distance`，结果为会增加实体体积的偏置壁；源 quilt id 不是新结果 quilt，实测距离可用性见 offset_distance_status |
| sheetmetal_flange.edge | 裸引用（计划路径 `operations[i].edge`），两种形态：`{"kind":"edge","id":N}`，`id` 取当前 `creo_inspect_model` 的边 ID；或 `{"kind":"edge_geometry","endpoints_mm":[[x,y,z],[x,y,z]],"tolerance_mm":1e-6}`，用当前模型坐标毫米的两端点点名一条直线边，原生在执行每个 op 时重查当前几何、要求无向唯一匹配，因此计划可跨边 ID 重排。`tolerance_mm` 可省略（默认 1e-6，范围 1e-9..1000），不接受单位字段；0/多候选、非有限坐标、退化边或无法换算模型长度单位时明确拒绝。两种形态都不得再加 edge/reference 包装。首壁来源为 `native_planar` 时，报错只指向 `creo_sheetmetal_planar_wall` 的 frame/envelope；只有 `sheetmetal_wall` 转换首壁才引用 `wall_contract`；来源未知不给旧首壁配方 |
| sheetmetal_base_flange.section | 由两条直线组成的开口 90° 折线：`[{"type":"line","start":[u,v,0],"end":[u,v,0]}, {...}]`，必须按给定顺序 end-to-start 连续、两段互相垂直、条数恰为 2；其余条数、非 90° 折角、共线折返与断链在入口（schema）就拒绝。只取两段长度和 90° 折角：第一段是有标签的 `native_planar` 矩形平面壁（同时生成 `<label>_sk`），第二段挂在壁自由端的 90° 法兰（`<label>_leg2`）。因此这是**两个特征**，结果 `composed_features` 逐一列出两者的特征 ID 与参数，不声称单特征基体法兰，也不等价于 0.24.1 反馈里那个中面加厚的原生基体法兰（体积口径不同）。单侧加厚：板沿 +normal 占 0..thickness，折弯腿在板的另一侧；`second_leg_mm` 是自板外表面起算的自由腿长，故原生法兰高 = `second_leg + thickness`；包络为 `first_leg × width × (second_leg + thickness)`，体积上界 = `(first+second)×width×thickness − (1−π/4)((R+t)²−R²)×width`，实测偏离超过 1 mm³ 或 0.5% 即失败。`radius` 为内半径，`k_factor` ∈ (0,1] 且 Y = K·π/2；`origin=[u0,v0]` 与 `sheetmetal_planar_wall` 同义；label ≤ 22 字符（要留出两个后缀）。实测（Creo 12.4.0.0，2026-11-15）：腿 8/12、t=2、宽 20、R=0.7366、K=0.5 得到 770.1858 mm³、包络 8×20×14，与上界差 6.4e-6 mm³，保存重载核验通过 |
| sheetmetal_unbend/flat_pattern/bend_back.fixed_surface | 裸面引用，如 `{"kind":"surface","id":N}`，取自当前巡检；`references` 省略时作用全部折弯，能否固定由原生执行判定 |
| sheetmetal_flange.flip_thickness | 布尔值，缺省 false。独立于改变伸展方向的 `flip`，启用后在已实测的直边 90° 法兰上让板厚向首壁自由端以外延伸。以包络、弯曲半径、体积及保存重载回执验证几何。 |
| sheetmetal_flange.relief | 可选对象 `{type:"none"\|"rectangular", ends:"both"\|"side1"\|"side2", width:>0, depth:>=0}`；省略等于 `none`（两端保持 `PRO_BEND_RLF_NONE`）。宽深是**绝对模型单位**、不按板厚缩放；`rip`/`stretch`/`obround`/`param`、角部释放与边撕裂不支持。这是 **bend-end relief**，不是 corner relief 或斜接，当前未证明能解决角部重叠；传入它也不会跳过 `adjacent_bend_ends` 创建前拒绝。释放是创建期属性，改它要删除/抑制折边后重建，没有就地改释放的入口 |
| sheetmetal_flange.end_trim_mm | 可选正数（`>0`，上限 100000，布尔拒绝），模型单位；省略时元素树与旧行为逐字一致。**Creo 把它读作「距链端各内缩 setback」还是「自截面起算的壁长」尚未实机确认**，属诊断参数：先在自由壁上用实测体积分类再依赖修剪几何（开发分支未发布） |
| sheetmetal_flange.miter_cuts | 可选对象 `{width:>0, offset:>=0}`（模型单位，布尔拒绝；`offset` 省略时等于 `width`）。写入折边自身 `PRO_E_SMT_MTR_CUTS` 的 **BLIND（`PRO_DIM_ENTER`）数值**宽度/偏移，创建时由 Creo 切掉墙端与相邻折弯的重叠。**这是 `adjacent_bend_ends` 创建前拒绝的唯一放行方式**：不传 `miter_cuts` 的请求照旧被拒；传入后放行并回显 `miter_cuts` 与放行证据 `adjacent_bend_ends_allowed`。实测（2026-11-06）：GAP 型会被 Creo 重置为 PARAM 且值清 0，故改用 BLIND；四壁盒子四墙均建成并保存重载，但 1 mm 宽度/偏移在自由首壁探针上无可测体积变化，切角量尚未定标 |
| feature_state.action / targets | `action` ∈ `delete`/`suppress`/`resume`；`targets` 是特征标签或非负特征 ID 的数组，同一批目标必须互不相同。仅用于零件/钣金模型；装配组件走 `creo_remove_component` |
| component_placement.component / component_constraints 引用 | 组件**业务标签**（如 `part_alpha`）；标签是业务名不是身份，身份是模型身份 + feature_id，删除重插后旧标签不误指新组件 |
| round/chamfer.references | **集合对象数组**：`[{"edge":{"kind":"edge","id":N}}]`，或 `[{"surfaces":[{"kind":"surface","id":A},{"kind":"surface","id":B}]}]`；裸边数组不等于集合数组 |
| round/chamfer 尺寸字段 | 独立工具 `creo_round.radius`、`creo_chamfer.distance` 与计划操作 `size` 是同一数值（mm）：round 计划也接受 `radius`、chamfer 计划也接受 `distance` 作为 `size` 别名；别名与 `size` 同现或用于另一种操作时明确拒绝。任务提交回显 `operations[].size`，终态 `result.operations[].size` 回显原生应用值（compact 返回同样保留） |
| create_sketch.plane | 主平面字符串 `XY/XZ/YZ`；字典形式为 `{"reference":{"kind":"datum_plane","id":N},"origin":[x,y,z],"u_axis":[x,y,z]}`，reference 也可取已验证平面 `plane`/`surface` 几何 ID 或 `datum_feature` 标签；origin/u_axis 可省略，reference 容器必需 |

### 按特征标签选面（FEAT-074）

当同一个计划先拉伸出 `base`，再对它拔模时，可在 `surfaces` 与 `neutral_plane` 使用带 `feature:"base"` 的 model-space 面选择器。示例选择经过 `[20,0,5]`、法向与 X 轴平行的面。

```json
{"kind":"geometry_selector","target":"surface","feature":"base","points_mm":[[20,0,5]],"axis":[1,0,0],"tolerance_mm":0.001}
```

执行器先限定到该标签特征直接拥有的原生面，再按几何条件选取唯一匹配。使用当前仍存在的特征标签。需选择多张面时，在 `surfaces` 分别给出选择器。

### 钣金首壁的 width 作用轴（BUG-129）

`creo_sheetmetal_base_flange` 和计划均可使用字典 `plane` 为宽度选择真实支撑面、世界原点与 u 方向。宽度沿解析得到的 v 轴。若支撑法向为 +Y，取 `plane={"reference":{"kind":"datum_plane","axis":"y","offset":0},"origin":[10,0,12],"u_axis":[0,0,-1]}`，宽度沿 −X。首壁可传 `direction:"negative"` 沿 −Y 加厚，`flip_thickness:true` 将折弯厚度伸出首壁自由端。局部 u 包络比原第一腿多一个板厚，体积验收增加 `width × thickness²`。方向断言仍只检查方向，平行或反平行均可匹配。

`sheetmetal_base_flange.width` 固定沿草图 v 轴。命名字典平面的默认帧如下（u 为第一段长度方向，v 为宽度方向）：

| `plane` | u | v / `width` |
| --- | --- | --- |
| `XY` | +X | **+Y** |
| `XZ` | +X | **+Z** |
| `YZ` | +Y | **+Z** |

这是默认帧，不是旋转能力：作业回执的 `width_direction_world` 是原生实测的 v 轴，调用方应以此核对；`expected_width_direction_world` 只做断言并在不匹配时拒绝，**不会**旋转或投影矩形。若需要把 `width` 改到另一根世界轴，必须改变草图方位，属于独立 FEAT，不在本工具内静默改变。`plane="YZ"` 时 20 mm 宽度落在 **+Z**，不是 +Y 或 +X。

### 主平面 offset 与切除方向（DEV-081/F11）

`offset` 是 `plane_coordinate`：主平面在自身轴上的**全局坐标值，不是沿法向的位移**；`direction`（extrude/revolve）才是相对该法向的 `positive`/`negative`。

| plane | origin | normal | u_axis | v_axis | offset 所在的全局轴 |
| --- | --- | --- | --- | --- | --- |
| XY | `[0, 0, offset]` | `[0, 0, 1]` | `+X` | `+Y` | Z |
| YZ | `[offset, 0, 0]` | `[1, 0, 0]` | `+Y` | `+Z` | X |
| XZ | `[0, offset, 0]` | `[0, -1, 0]` | `+X` | `+Z` | Y（negative Y，`direction="negative"` 向 +Y） |

### 0.41.0 新增几何选择、巡检与可用性约定（BUG-176 / FEAT-078 / FEAT-079 / BUG-177 / BUG-178）

- **整圆棱边选择（BUG-176）**：Creo 将整圆拆分为两段半圆弧。在圆形边选择器（`center_mm` + `radius_mm` + 可选 `axis`）上设 `"full_circle": true` 可确定性选中该圆的最小边 ID（`round`/`chamfer` 会自动沿整圆传播）；若携带 `point_mm` 且点落在两段半圆弧的公共接缝/象限极值点上，同样确定性取最小边 ID（诊断输出 `seam_point_resolved=true`）；仅传 `point_mm` 的单点边选择器同时匹配有限直边与圆弧边。
- **巡检面积、包围盒与合并计数（FEAT-078）**：`creo_inspect_model` 摘要直接返回 `total_surface_area_mm2`、`bounding_box_mm`（`min`/`max`/`size`，零件与装配均支持）、`merged_counts`（将同轴拆半圆柱面与同圆拆半圆弧边分组计数）与 `counts_convention`；`detail="full", section="surfaces"` 逐面返回 `area_mm2`。
- **多集圆角/倒角失败定位（FEAT-079）**：多引用 `round`/`chamfer` 再生失败时，原生在安全上限（前 20 集）内逐集探测并清理探针，失败回执输出 `failed_reference_index`、`failed_reference` 与 `round_failure`，事务仍完整回滚。
- **优弧张角与样条面积（BUG-177）**：草图 `arc` 支持有符号 `sweep_deg`（`0 < |sweep_deg| < 360`）替代 `end_angle` 表达 >180° 优弧；含 `spline` 的闭合草图通过平滑插值采样给出数值 `material_area_mm2`；`coordinates` 模式超差拒绝消息附带 `shifted_sample`。
- **特征状态依赖展开（BUG-178）**：`feature_state` 支持显式 `"include_dependencies": true`（默认 `false` 不变），自动纳入非系统必需的受影响子特征/伴随基准并记录 `auto_included_dependencies`；默认 `false` 缺依赖拒绝时在回执与消息中给出可直接复制的 `suggested_targets`。

XZ 的法向是 negative Y，因此 `direction="positive"` 会让实体向更小的 Y 增长；切料方向与草图全局位置必须同时核对。字典引用内部的 `offset`（平面筛选条件，见上文）与本表的 `plane_coordinate` 不是同一个字段。

这些集合和坐标包装承载不同的参数含义，不能简单地给所有裸引用增加同一层包装。此修复兼容报告中的轴标签、补齐引用契约，不更改原生执行器或创建额外几何。

实现与当前验收范围见 [BUG-006](archive/work-items/BUG-006.md) 和 [本次证据](validation/BUG-006.md)。

## 选择性切除作用域（DEV-081/F08）

多实体零件的 `extrude` 切除可以只作用于一个实体：

| 字段 | 取值 |
| --- | --- |
| `scope.kind` | 只接受 `"bodies"` |
| `scope.body_ids` | 一个实体 ID，取自当前零件的 `creo_inspect_model` → `bodies[].id`。接受 32 位正整数及 Creo 初始实体 ID `-5778`（0.35.8，BUG-150）。 |

全量和分页巡检在 `bodies[]` 返回 `cut_scope_id_eligible`，表示原始 `id` 是否满足作用域的格式要求。选择目标时还需核对 `state_name="active"` 和 `material=true`。初始实体在有材料和空体状态下都可能保有 `-5778`，执行器会在目标零件内按该 ID 查找活动实体，并由特征树回读确认实际选中 ID。见 [BUG-150](work-items/BUG-150.md)。

省略 `scope` 时行为不变，切除对全部实体生效。自 0.38.0（[FEAT-075](work-items/FEAT-075.md)）起，单实体 `scope` 同时支持 `depth_type="blind"` 与 `depth_type="through_all"`（含 `positive`、`negative`、`symmetric` 与初始实体 ID `-5778`）。以下组合仍在提交前拒绝，不产生作业：多个实体 ID、`kind` 不是 `bodies`、非 `cut` 模式、`new_body=true`、`revolve` 带 scope。

切除体积口径说明：拉伸切除实际移除的体积为「扫掠体 ∩ 已有实体材料」，而不是无条件等于「草图面积 × 深度」。若草图平面位于实体外部（空切段）或切削穿过曲面壁面，实测 `material_removed_mm3` 只计真正与材料相交的体积。

多闭环实体拉伸边界：同一草图支持多个**互不相交或嵌套**的闭合轮廓（例如外框套内孔或多个独立岛），但 Creo 实体拉伸内核不接受彼此交叉（`intersecting`）或相切（`tangent`）的闭环。遇到相交/相切拒绝时，请修剪为单一无自交外轮廓，或拆分为多条 `extrude` 增料操作让 Creo 自动并入实体。

成功作业的该操作结果带 `scope_applied`：`requested_body_ids`、`applied_body_ids`（从创建后的特征树回读）、`source`、`query_code`、`non_target_bodies_unchanged`。`non_target_bodies_unchanged` 比较其余实体的面数与包围盒；任一侧查询无法完成时为 `null`，不会填 `true`。回读到的实体与请求不一致或特征中没有该选择时作业失败并回滚，错误码 `F08_SCOPE_RESOLVE_FAILED`；非目标实体发生变化时为 `F08_SCOPE_NON_TARGET_CHANGED`。

本机实机验收（Creo 12.4.0.0）：两实体零件只切 body 52，body 90 的面数与包围盒不变，总体积 39214.6018 mm³（40000 − 250π），保存重载通过。装配内切除、三个以上实体与回读不匹配路径尚未实机验证，见 [DEV-081](work-items/DEV-081.md)。

## 回转轴回显（revolve_axis）

`revolve` 操作结果带 `revolve_axis` 块（只增不改；旧作业与失败作业没有该块，不补）。字段与语义：

| 字段 | 含义 |
| --- | --- |
| `source` | `explicit`（请求显式轴）/ `internal_centerline`（省略或 null 轴）/ `unknown` |
| `kind` | `datum_axis`（无归属面的基准轴）/ `surface`（轴由几何面解析）/ `section_centerline`（草图内部中心线）/ `unknown`；按实测分类，不按请求文本 |
| `id` | 实际解析 id：基准轴/面轴为模型轴几何项 id（可用于 `{"kind":"axis","id":N}`），内部中心线为草图 section 实体 id；无法判定为 `null` |
| `origin` / `direction` | 只来自实际轴或 section 中心线查询；`frame="model"` 为模型坐标 3 元，`frame="sketch_local"` 为草图 (u,v) 2 元；未知为 `null`，**不回填请求值** |
| `frame` | `model` / `sketch_local` / `null`；实测优先 `model`（能取回转特征自身轴时），`sketch_local` 只是回退 |
| `length_unit` | 与基准轴同形的真实单位查询块（`name`/`query_code`/`scale_to_mm`…），失败为 `null` + 原码 |
| `geometry_known` | 严格布尔；仅当 frame 合法且 origin/direction 都是实测有效向量时为 `true` |
| `query_code` / `resolution` | 产出几何值的查询码与辅助证据（`feature_axis_query_code`、`axis_item_query_code`、`axis_surface_query_code`、`section_centerline_count`、`section_query_code`） |
| `section_centerline_count` | 实测**用户中心线**根数。2026-10-30 修正计数口径：草图构建器必写的两条系统投影参考不再计入（此前一条用户线被计成 3），修复后一条用户线计 1 并给出 id；真实多中心线仍保留 `id=null`，不武断选第一条 |

开发分支的该修正**尚未实机验收**；服务准入仍限一条草图中心线，因此「真实多用户中心线」夹具无法经本服务构造，需外部手工草绘模型。详见 [T09B 验收卡](archive/development/DEV051-T09B-ACCEPTANCE.md)。

## 组件身份查询（list_components）

`creo_list_components` 与 `creo_inspect_model` 的 components 节在组件记录上投影业务身份：每条带 `identity`（模型身份 + feature_id，即关联键本身）、`labels`、`label`（恰好一个绑定时为该值，否则 `null`）、`label_state`（`single`/`multi`/`unlabeled`）、`source_model_id`/`source_revision`（多标签或无绑定时为 `null`，不任选一个冒充）、`bindings`（每个绑定一条）。顶层另返回 `deleted_identities`（旧 feature_id 不在当前组件集时单独列出，绝不并入当前记录）与 `identity_key`。

label 永远不是身份：同名 label 可以存在于不同模型，删除重插后 label 不变但 feature_id 换新，因此求交只在同一模型身份内按 feature_id 进行。物理副本名 `c_<job>_<n>` 是原生身份，不做改写。保存重载后关联与删除重插不误指的开发分支回归**尚未实机复验**。

## 圆角/倒角尺寸字段对照与部署核对（BUG-019）

三个入口的尺寸数值是同一个值（mm），只是入口字段名不同：独立工具 `creo_round.radius`、`creo_chamfer.distance` 在提交时转换为计划操作的 `size`；`creo_execute_plan` 的 round/chamfer 操作以 `size` 为主字段，并分别接受 `radius`/`distance` 作为 `size` 的别名（别名与 `size` 同现、或用于另一种操作时明确拒绝，不做静默优先）。别名自 0.3.7（DEV-042）起可用。

三个入口的等价请求示例（同一 3 mm 圆角）：

```json
// 独立工具 creo_round（参数名 radius）
{"model_id":"<id>","expected_revision":7,"label":"fillet","radius":3.0,
 "references":[{"edge":{"kind":"edge","id":9}}]}

// execute_plan 旧式（主字段 size）
{"model_id":"<id>","expected_revision":7,
 "operations":[{"op":"round","label":"fillet","size":3.0,
               "references":[{"edge":{"kind":"edge","id":9}}]}]}

// execute_plan 别名（round 的 radius，与上一条等价；chamfer 对应别名是 distance）
{"model_id":"<id>","expected_revision":7,
 "operations":[{"op":"round","label":"fillet","radius":3.0,
               "references":[{"edge":{"kind":"edge","id":9}}]}]}
```

无论入口如何，任务提交回显 `operations[].size`，终态 `result.operations[].size` 回显原生特征实际应用的值（compact 返回同样保留），可与调用输入直接对照。

部署核对方法（仅用公开 MCP 接口，不读源码）：

1. 用 `creo_capabilities`（或 `creo_check_update`）读当前部署的 `version`/`current_version`：低于 0.3.7 的部署没有计划别名，独立工具的 `radius`/`distance` 参数一直可用。
2. 在客户端 `tools/list` 或 `creo_capabilities` 的 tools 分节核对 schema：`creo_round` 输入为 `radius`（无 `size`），`creo_chamfer` 以 `distance`（或 `size`）表示等距，并在 FEAT-071 之后同时接受 `chamfer_type`/`angle_deg`/`angle_reference` 与 `distance_1`/`distance_2`/`reference_surface`（见「两距离不等距倒角」），`creo_execute_plan` 的 round/chamfer 操作含 `size` 与别名字段。
3. 实测一条最小请求：任一入口提交成功后，提交返回与终态均出现 `operations[].size` 且数值等于输入；给 round 同时传 `size` 与 `radius`（或给 round 传 `distance`）应被明确拒绝。

外部 0.3.1/0.3.4/0.3.5 的参数名差异反馈来自别名引入前的部署；在核对真实请求与受测部署身份之前，不把这些旧反馈计为当前实现的回归。

## 待核对的补充契约

[FEAT-008 首批任务](work-items/FEAT-008.md)跟进专用底板holes的客户端传输形状、对称拉伸depth口径与“查当前可编辑尺寸再修改”的闭环；[BUG-031](work-items/BUG-031.md)核对共面多候选/默认基准选择，结合字符串plane+offset产生构造特征的可见性说明。[履带反馈补录](validation/TRACK-FEEDBACK-2026-10-16.md)仅提供外部来源。上述是待核对工作，不是已新增字段或已变更接口；仍须按当前工具schema和真实返回使用，不把报告中的建议引用/参数当作已支持形式。


## 产品规则只读规划（FEAT-063，开发分支未发布）

`creo_plan_product_variant(template_id="box_frame", parameters={})` 使用 READ 注解。
参数仅 length_mm/width_mm/height_mm/wall_mm，默认 100/60/40/2 mm；前三项范围
[10,1000]，壁厚 [0.5,20]，内腔每向至少 1 mm。拒绝 bool、字符串、非有限数、
未知字段和模板路径。服务从当前启用操作构造快照，不接受调用方能力声明。
返回 plan.operations、解析 expected_geometry 和 blocking_items；缺 sketch/extrude 时
executable=false、plan=null。完整 JSON 上限 32768 UTF-8 字节，超限拒绝而不截断。
executable 仅表示静态能力/schema 准入；native/saved_reload 恒为 not_run。
无连接、提交、job_id/model_id/revision；原生模板未验。详见 [产品规则](PRODUCT_RULES.md)。

## 2026-11-07 DEV-074 离线回执增量（开发分支）

- 平面钣金壁 `thickness_verified_effective` 与 resize 的 `thickness_loaded_verified_effective` 来自有来源、上下文正确且与请求厚度一致的验证块；缺块/缺请求尺寸为 null。旧 `thickness_verified` 等字段保留原生 API 读数语义。
- resize 缺少前后任一 feature ID 时，`feature_id_unchanged=null`；失败且未取得 ID 的 loaded 验证/来源字段显式 null。
- 几何选边零匹配的失败操作携带 `edge_geometry_diagnostic`，包含 `nearest_edges`（最多5项：`id`、`endpoints_mm`、`endpoint_errors_mm`）、`tolerance_mm`、`candidate_limit` 与 `straight_edge_count`。这些是诊断候选，不会自动吸附或放宽严格匹配；compact 保留该结构。
- `preview.status=skipped_no_geometry` 时 `path/bytes=null`，`empty_geometry_basis` 透传 `feature_visit_code` 与 `non_datum_feature_count`；未测或查询失败的计数为 null。
- startup `state/connected` 保持上次观测语义；`connection_verification=unverified_stale_snapshot` 与 `current_connected=null` 表示快照已过期，message 明确提示未验证。状态读取不会探测 Toolkit。
- 更新快照 `in_flight` 明示正在检查；`last_completed_status` 保留上次完成状态（未检查为null），与 `from_cache/stale` 分别解读。
- `native_progress.connect_timing` 保存日志头部连接阶段证据；尾部当前阶段没有时间则不填 `idle_seconds`，不能把早期连接时间归给回滚或其它阶段。

这些增量已作离线回归与原生编译；新原生字段的真实MCP/Creo/保存重载验证仍见[接手清单](development/DEV-074-HANDOFF.md)。

## JPEG 导出视图（FEAT-074）

`creo_export_model` 可选 `timeout_seconds`（整数 60–7200 秒）。作业预算与独立停滞预算见 `creo_get_job.budgets`。STL 执行阶段见 `native_progress.sub_stage`。网格通过校验后才发布，超时留下的未校验暂存文件不可作交付件。

零件和装配可用 `creo_export_model(format="jpeg", jpeg_options={"view":"top","width_px":1600,"height_px":900})` 单独导出预览。视图支持 `isometric`、`front` 和 `top`，每边可选 200–2400 像素。一次作业输出一张图，沿用当前模型 revision。

## 精确 NURBS 草图实体（b_spline，FEAT-066）

Creo 10 的部分闭合 B 样条轮廓会生成切除特征但量测去料为零。允许折线近似时，可在该草图实体显式传入 `"approximation_segments": 21`，取值 2–199。执行器在结点域等参数采样，保留端点，并按 `<name>_0` 等线段名创建草图。回执 `b_spline_approximations` 给出实际采用的段数。段数只规定采样密度，`geometry_deviation` 核查草图相对折线输入的求解偏移。需要控制曲线与折线之间的误差时，请按目标公差选取段数或提供已有误差界的折线。

`spline` 只接收插值点，由 Creo 拟合曲线，无法 1:1 复现 TXT 的次数/节点/权重。
`b_spline` 直接映射 Toolkit `Pro2dBSplinedef`（`PRO_2D_B_SPLINE`，见 SDK
`Pro2dEntdef.h`），把控制点、节点和可选权重按原值写入草图：

```json
{"type": "b_spline", "name": "side_guide", "degree": 3,
 "control_points": [[0, 0], [10, 8], [30, 9], [45, 2], [50, 0]],
 "knots": [0, 0, 0, 0, 0.595088181, 1, 1, 1, 1],
 "weights": [1, 1, 1, 1, 1]}
```

- 坐标是草图局部毫米；`degree` 默认 3，范围 1—10 且必须小于控制点数。
- `knots` 省略时生成 clamped uniform 节点；给出时必须满足
  `len(knots) == len(control_points) + degree + 1`、非降、首尾各 `degree+1`
  个值相等。节点值原样传给 Creo，不做归一化。
- `weights` 省略时按非有理曲线写出；给出时长度等于控制点数且全部大于 0。
- 不支持 `closed`：周期 B 样条需要周期节点，请改用 `spline` 的
  `closed=true`。`dimensioning="coordinates"` 仍只接受
  line/centerline/rectangle/polyline/circle/arc，`b_spline` 走 autodim。
- `b_spline` 会让草图的 `profile` 报告变成 `analysis="partial"`：该报告只展开
  line/arc/circle/rectangle/polyline，`b_spline`/`spline`/`ellipse` 只记入
  `categories.unsupported`，因此 `entity_count`/`contour_count`/
  `closed_contour_count` 是**下界**。两条首末相接的闭合 `b_spline` 可以同时出现
  `profile.entity_count=0` 与 `native_section.entities=2`，这不是内核丢轮廓，也不是
  草图没闭合：判断闭合看 `native_section`（`closed_contours`/`open_ends`）或只读
  `creo_measure_surface_group`。不要用 `profile` 计数否证一次已成功的草图提交。
- `b_spline` 仅支持创建；`update_sketch_geometry` 不能改写其 degree/knots/weights，
  需要变更时重建草图。
- 可用性不依赖 `Probbl.h`；草图实体写入只需要 `Pro2dEntdef.h` 的
  `PRO_2D_B_SPLINE` 定义。

## 零匹配边选择器的诊断范围（DEV-098）

`{"kind":"geometry_selector","target":"edge",...}` 零匹配时拒绝，多匹配按默认要求或显式消歧规则处理。失败回执给出 `candidate_count`、`matched_ids`、`tolerance_mm`；**零匹配**时 `geometry_selector_diagnostic.nearest_edges` 另列最多 5 条最近的可匹配边，按误差再按 id 升序：

- 端点/点形式：`id`、`endpoints_mm`（模型坐标换算后的毫米端点）、`error_mm`；端点形式另有 `endpoint_errors_mm`，带 `point_mm` 时另有 `point_error_mm`。
- 圆形式：`id`、`center_mm`、`radius_mm`、`radius_error_mm`、`center_error_mm`、`error_mm`；带 `axis` 过滤时另有 `axis_error_deg`。

零命中时的 `nearest_edges` 只供诊断。模型空间边选择器可传 `on_face:{"kind":"surface","id":N}`，使用本次巡检的面 ID，只保留与该面相邻的边。仅含单点锚 `point_mm` 的模型空间边选择器可显式传 `ambiguity:"nearest"`，按点到有限直线或圆弧的距离选取容差内的唯一最近边。第一与第二近的差不超过 1e-6 mm 则拒绝。成功回执 `geometry_selector_resolution` 给出选中的边及消歧信息，失败回执保留 `matched_ids`。特征重建可替换边或面；重新巡检当前几何，再提交当前面 ID 或边 ID。`sheetmetal_flange` 旧 `edge_geometry` 路径继续使用 `edge_geometry_diagnostic`（字段见上文 DEV-074 增量）。

`{"kind":"geometry_selector","target":"surface",...}` 零匹配时同样给出 `geometry_selector_diagnostic.nearest_surfaces`（最多 5 条，按误差再按 id 升序，只列可命名的 planar/cylindrical 面）：每条含 `id`、`type`（`plane`/`cylinder`）、`origin_mm`、`normal` 或 `axis`、`error_mm`；带 `axis` 过滤时另有 `axis_error_deg`，带 `radius_mm` 时另有 `radius_mm`/`radius_error_mm`，带 `center_mm` 时另有 `center_axis_distance_mm`，带 `points_mm` 时另有 `points_offset_mm`。`radius_mm`/`center_mm` 只适用于圆柱面，方向正确但类型不符的面仍只出现在 `type_rejected_ids`。该列表同样是诊断，不会自动选中。

装配坐标选择器：`coordinate_space="assembly"` 先按 occurrence 放置把端点/点/圆心/轴换算到组件模型坐标系，回执里的测量值都是**模型坐标**；失败回执额外给 `requested_coordinate_space="assembly"`，重试时应使用换算后的模型坐标或直接给当前巡检的 id。

## quilt closure 的三种含义（DEV-098）

`closure`（`creo_inspect_model(section="quilts")`、`quilt_merge`、`solidify` 回执）
来自原生 `ProQuiltVolumeEval`（`native/surface_measure.h`），只有三类结果：

| 回执 | 含义 | 不能推出 |
| --- | --- | --- |
| `available=true`、`query_code=0` | 内核返回了体积 | 边界拓扑闭合（单片封盖面也可返回体积） |
| `reason="quilt_is_open"`（内核码 `PRO_TK_INVALID_TYPE`） | 该 quilt 对体积求值开放 | 一定不能实体化 |
| `reason="quilt_volume_eval_failed"`（外部 Creo 10 实测 `-62`） | 体积求值失败 | 边界不闭合，或 `solidify` 一定失败 |
| 缺块 / `unit_scale_unknown` | 未知 | 任何 true/false |

已记录的实测（0.32.0 外部 Creo 10）：3 面壳体 `closure` 为 `-62`/
`quilt_volume_eval_failed`，同一 quilt 的**单步** `solidify` 仍 `succeeded` +
`committed`；单片封盖 `surface_fill` 报 `closed: true`，几何上并不是闭合壳体。
因此：

- **拓扑闭合**看只读 `creo_measure_surface_group`（`state`、`boundary_closed`、
  `open_edge_records`），不是 `closure`；
- **能否实体化**只看实际 `solidify` 记录的 `execution_status`/`effect_status`；
- 未知保持 `null`；`creo_mechdog.diagnostic_semantics.closure_semantics()` 与本文件
  都不把它折算成 true/false。

## 已验证的分步曲面路径：开放壳体封口并实体化（DEV-098 引用）

来源是 0.32.0 外部报告（Creo 10.0.0.0，`release_numeric=42`）的球鼻艏案例，
原件在 `docs/validation/feedback-0.33.0-2026-11-21/`；**本仓库本批未实机复验**，
不能当作本机或当前版本已验收。

`surface_boundary_fill` 仍不可用（见 `UNAVAILABLE_OPERATIONS`）；开放壳体封口用
「闭合双 `b_spline` 草图 + `surface_fill` + `quilt_merge`」绕行，且每步必须是**独立
作业**，等到 `saved_file_reloaded_and_verified=true` 再进入下一步。

| 步骤 | 工具 | 关键参数 | 该报告中的产出 |
| --- | --- | --- | --- |
| 1 | `creo_surface_loft`（`creation_route:"resident_panel"`） | 7 截面 + 末端点 | quilt 144 / 490,915.028962 mm² |
| 2 | `creo_mirror` | `target:{kind:"quilt",id:144}`、`plane:{id:4}` | quilt 155 |
| 3 | `creo_quilt_merge` | target 144 + tool 155 | quilt 144 → 2 面 / 981,830.165755 mm² |
| 4 | `creo_create_sketch` + `surface_fill` | 闭合双 `b_spline`（plane id 41） | quilt 196 / 59,827.268099 mm² |
| 5 | `creo_quilt_merge` | target 144 + tool 196 | quilt 144 → 3 面 / 1,041,657.460478 mm² |
| 6 | `solidify` | `reference:{kind:"quilt",id:144}`、`mode:"add"`、`new_body:true`、`side:"positive"` | 实体，54,905,286.63066032 mm³ |

三条规则（同一报告实测）：

1. `merge`/`mirror`/`trim` 的结果在 BUG-143 起可继续用 feature label 引用：原生把该 label 解析为操作实际测量到的结果 quilt，回执同时给出 `quilt_id`；无法唯一确定结果 quilt 时在提交前或执行中明确拒绝并附候选，不按 bbox/最近 quilt 猜测。该解析在目标 Creo 实机核对前，`{kind:"quilt",id:N}` 仍是唯一已证实的引用方式（旧版本解析 label 会 `ProFeatureGeomitemVisit -4`）；
2. 不要把这几步放进同一个 `operations` 数组；
3. 每次 `quilt_merge` 后重新 `creo_inspect_model(section="quilts")` 取当前
   `quilt_id`，不复用合并前的假设。

`creo_mirror` 的 `references` 只接受镜像项：`curve`、`axis`、`quilt`、`csys`、
`point`、`datum_plane`、`datum_feature`、`datum_axis_feature`，或单独一个
`part`。`{kind:"feature"}` 不在 `PRO_E_MIRROR_REF_ITEMS` 里（`ProMirror.h` 明确把
`PRO_FEATURE` 排除在镜像项之外），2026-11-21 在 Creo 10 上两次把主线程卡死：作业停在
`mirror:<label>` 330 s / 240 s、Creo CPU 不增长，随后 `toolkit_code=-38`、worker
退出码 20。现在契约与原生都在创建特征之前拒绝，并同时给出可行路线——整体镜像用
`{"kind":"part"}`（不能与其他引用混用），曲面特征改用 `creo_inspect_model(section="quilts")`
得到的 `{"kind":"quilt","id":N}`。

封盖草图在该报告中为两条闭合 `b_spline`，`native_section` 给出 `closed_contours=1`、
`open_ends=0`、端点偏差 2.84e-14 mm；其 `profile` 因 `b_spline` 不受支持而是
`partial`，计数不能用来反驳——见上文 b_spline 一节。

## 装配位姿矩阵与约束组（DEV-092 / BUG-133，开发分支）

`assemble_component` 与 `component_placement` 共用同一份位姿契约：

| 字段 | 规则 |
| --- | --- |
| `rotation_matrix` | 3×3 有限实数；与 `rotation`（XYZ Euler 度）互斥；原样写入，不转置、不重正交 |
| `rotation_convention` | `row`（缺省）或 `column`。`column` 表示 `p_parent(column) = R * p_local(column) + T`，原生入口只转置一次 |
| `rotation_tolerance` | 可选，`0 < t ≤ 1e-7`，缺省 `1e-7`。Python 与原生读取同一有效值 |

- 准入始终按**规范行向量矩阵**计算 `max |R*Rᵀ−I|` 与 `det`：`column` 输入先转置再判定，
  所以同一姿态无论用行还是列写法都得到相同结论。请求数组、`rotation_convention`
  与容差都按原值回显。
- 上限 `1e-7` 是 2026-11-21 在 Creo 10.0.0.0 / release 42 实测的内核边界：残差
  `4.5e-10`、`7.664e-9`、`4.755e-8` 可放置，`2.241e-7`、`4.890e-7`、`1.129e-6`
  都被 `ProAsmcompAssemble` 与 `ProAsmcompPositionSet` 以 `-2` 拒绝。更大的容差
  只会放行内核必拒的位姿，因此两层同时拒绝；此前传入更大值的调用现在是明确的输入
  错误（不会静默降级）。
- 上限与缺省值相同，所以显式容差只能严格收紧，不能“救回”六位小数矩阵；这类矩阵
  应改为精确正交值或从角度重建。
- 只有显式 `rotation_matrix` 能带 `rotation_convention` / `rotation_tolerance`；Euler
  输入带任一字段即拒绝，避免无效字段悄悄生效。
- 成功回执的 `rotation_convention` 仍描述解算变换（行向量），另加
  `input_rotation_convention` 与 `rotation_tolerance` 说明请求。放置失败时
  `failed_operation` 给出 `input_matrix`、`matrix_convention`、`admission_tolerance`、
  `determinant`、`orthogonality_residual`，均按同一有效门槛测量。

约束组（`component_constraints`）：

- 每次调用是**该组件的一整组替换**（原生 `ProAsmcompConstraintsSet`）：上次写入的约束
  不追加，已有的 FIX 放置也会被替换。因此“22 条拆两批”不能按同一组件累计。
- `max_length=20` 只作用于 `component_constraints.constraints`；`assemble_component`
  的初始约束数组没有该上限，不同组件本来也分别写入。22 条跨组件不是整组上限。
- 支持 `mate`/`align`/`mate_offset`/`align_offset`/`insert`/`csys`；`mate`/`align`/
  `insert`/`csys` 不接受非零 `offset`。`insert` 需要圆柱面引用，selector 形式还要
  `radius_mm`，`coaxial="any"` 只用于 insert/concentric。
- `parallel` 与轴/点 `distance` 仍是 named gap：面距离可用 `mate_offset`/`align_offset`
  加 `offset` 与 sides 表达；平行约束用 `align`/`align_offset` 近似，但两者并不等价
  （align 还约束面的位置）。
- 失败诊断：预解析错误给 `failed_constraint_index`（0 基）、`failed_constraint_type`、
  `constraint_stage`（`type`/`offset`/`self_reference`/`allocation`/`reference`/
  `surface_type`/`side`/`offset_write`）与 `constraint_reason="constraint_rejected"`；
  整组求解失败时索引为 null、`constraint_stage="solve"`、
  `constraint_reason="solver_failed"`，原始 Toolkit 码保留在
  `failed_toolkit_call`/`toolkit_code`，不推测具体哪条冲突。
- 以上为软件层契约与离线回归；Creo 13.4 实机几何、求解与保存重载未验收，本机
  12.4 结果也不外推。
