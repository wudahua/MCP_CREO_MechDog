# 2026-11-26 / MCP_CREO_MechDog 0.46.1 / 默认 XZ 偏移面法线仍与 capabilities 矛盾（新增 flip/v_axis 可规避，但默认路径仍静默做错）

> **反馈对象**：MCP_CREO_MechDog **0.46.1**（本机运行版本，`server_version=0.46.1`；检查更新时上游已有 0.47.0，本机未安装。本报告全部证据来自 0.46.1）
> **宿主**：Creo Parametric 9.0.0.0（`release_numeric=41`），Windows，`D:\CREO\Creo 9.0.0.0`
> **性质**：对 2026-11-24 那份 `0.43.1` 反馈的**复验**（原文档：`2026-11-24_CREO_0.43.1_偏移基准面法线方向静默翻转致XZ草图整体反号.md`）
> **任务**：以 TXT 为唯一几何来源建成的 Step / Belt / Box / Part 1 + 15 实例装配，在 0.46.1 下复验几何 + 逐条复测上次的 10 项问题。

---

## 0. 一句话结论

上次 10 项反馈中，**3 项真的修好了**（构造圆、packaged、显式 v_axis/flip 开关），**4 项仍未修复**（默认法线矛盾、坐标容差不可配、特征镜像、模型名空格）。其中 **P0 只修了一半**：新增了 `flip` / `v_axis` 让用户能规避，但**默认路径的法线仍与 capabilities 声明相反，且仍无任何 warning——用户照文档默认值写，零件照样静默做反**。这就是本次的核心问题（§1）。

已交付成果在 0.46.1 下几何完好：五个受管模型体积/面积/重心与 0.43.1 建造时**逐位一致**（见 §0.2）。

---

## 0.1 复验结论速览

| 上次条目 | 0.46.1 状态 | 证据 |
|---|---|---|
| §1 P0 默认 XZ 偏移面法线与文档相反、静默做错 | **部分修复**（新增规避开关，默认仍错） | job `871315544bf14d0d97f2edb405c5e3a8` |
| §2 coordinates 拒绝构造圆 | ✅ **已修复** | job `4ba9b1052d8b44e8a7694dda91b4cbbc` |
| §3 coordinates 容差不可配 | ❌ 未修复 | `deviation_tolerance_mm` → Extra inputs not permitted |
| §4 mirror 不能镜像特征 | ❌ 未修复 | 准入校验原样拒绝 |
| §5 装配缺 packaged | ✅ **已修复** | job `26272f816ef44e0e8f2090ce9b4f0369` |
| §6 多会话处置 | ⚠️ 部分改进（新增 `session_id` 选择，PID 仍不可推） | capabilities / session_status |
| §7 模型名空格/大写 | ❌ 未修复（大写转小写、空格仍拒） | 准入校验 |
| §8 bbox 精度 | ⚠️ 新增来源与弦高标注，精度未变 | receipt `bounding_box_source` |
| §9 面数口径 | ✅ 保持（counts_convention / merged_counts） | 各 job receipt |

## 0.2 已交付成果复验（几何零回归）

`creo_get_mass_properties_batch` 读回上次建成的五个受管模型，与 0.43.1 建造记录逐位一致：

| 模型 | V (mm³) 0.46.1 读回 | A (mm²) | 重心 (mm) |
|---|---|---|---|
| Step | 2227.500000 | 3312.0000 | (0.750, 1.001, 0.000) |
| Belt | 237426.309566 | 321364.9038 | (0.000, 119.944, −334.864) |
| Box | 89495.661510 | 12930.4268 | (12.500, 0.000, 0.000) |
| Part 1 | 621563.689953 | 249363.0313 | (−50.000, 74.930, −339.820) |
| 装配 15 实例 | 975215.661029 | 623402.3618 | (568.668, 384.840, 139.521) |

---

## 1. 【核心 · 高】默认 XZ 偏移面法线仍与 capabilities 矛盾 —— 新增开关可规避，但默认路径照文档写仍静默做反

### 现象（0.46.1 实测，最小复现）

三个对照作业，同一张 XZ 平行偏移面 `datum_plane(axis=y, offset=-30)`，同样的矩形草图 + `extrude(direction="positive", depth=7)`，只改 `flip` / `v_axis`：

| 作业 | datum_plane | sketch plane | 回读 normal | 回读 v_axis | 拉伸落点 y |
|---|---|---|---|---|---|
| `871315544bf14d0d97f2edb405c5e3a8` | 无 flip | 无 v_axis（**默认**） | **(0, +1, 0)** | **(0, 0, −1)** | −30 → **−23**（向 +Y）|
| `47812e4ef2264454bc21441558a59b15` | 无 flip | `v_axis=[0,0,1]` | (0, −1, 0) | (0, 0, 1) | −30 → −37（向 −Y）|
| `4ba9b1052d8b44e8a7694dda91b4cbbc` | `flip=true` | 无 v_axis | (0, −1, 0) | (0, 0, 1) | −30 → −37（向 −Y）|

默认作业 `8713155…` 的回执原文：

```
"plane": {"reference":{"kind":"datum_feature","label":"pl_def"},
          "origin":[0,-30,0],"u_axis":[1,0,0]}
→ "normal":[0,1,0], "u_axis":[1,0,0], "v_axis":[0,0,-1]
```

而 capabilities 的 `frames.XZ` 仍声明：

```
"XZ": "u=+X,v=+Z,normal=-Y"
```

**文档说 normal=−Y / v=+Z，默认建出来是 normal=+Y / v=−Z**，与 0.43.1 时完全一致，且所有特征仍 `succeeded / committed`、作业 `status=succeeded`、无任何 warning。用户按 capabilities 的 XZ 框架写草图坐标，就会静默把 z 反号、把 `extrude.direction` 的 +/− 全反——**这正是上次报告的核心缺陷，0.46.1 默认路径上并未消除**。

### 这次确实新增的东西（要肯定）

- `PlaneOp.flip`（schema.py 1508）：`datum_plane` 可显式翻法线；
- `SketchOp.plane` 的 dict 现支持 `v_axis` 与 `flip`（schema.py 497-503）：`v_axis` 显式给出时，MCP 会把 normal 翻到满足 u×v=normal 的右手系（作业 `47812e4e` 回读 normal 由 +Y 变 −Y）。

这两条让**知情的用户可以规避**，值得肯定。但它们只是"给了工具"，没有堵住默认路径的坑。

### 为什么这仍算高优先级

1. **默认值与文档冲突，且无任何提示**。用户读 capabilities 得到的承诺是 `XZ normal=−Y, v=+Z`；照此写的草图在最常见路径（不显式给 v_axis/flip）上必然反号。
2. **反号后几何仍"合法"**：本例三种写法体积都是 5600 mm³，只有位置（y=−23 还是 −37）和 z 方向不同——**靠体积查不出来**，只能靠包围盒/重心，和上次一样隐蔽。
3. `flip=true` 的语义不直观：翻的是支持面法线，连带反转 `extrude.direction` 的含义。用户即使知道要用 flip，也很难一次选对。

### 建议

1. **让默认 XZ 偏移面法线等于 `frames.XZ` 声明的 (0,−1,0)**，或反过来把 `frames.XZ` 改成默认实测值——二者必须一致，这是根因。
2. 在 `sketch` 回执里，当**实际法线/v_axis 与该平面框架声明不一致**时，输出一条 `warning`（例如 `frame_mismatch`），而不是静默接受。
3. 在 capabilities 的 `frames.XZ` 条目补一句"偏移基准面的法线取决于支持面，建模前请回读或显式指定 `v_axis`/`flip`"。
4. 提供 `plane={kind:'plane', normal, offset}` 自动合成支持面（上次的 §1.4 建议），让用户不必手工铺基准面，也就不会踩到默认法线。

### 最小复现片段

```json
[
 {"op":"datum_plane","label":"pl_def",
  "reference":{"kind":"datum_plane","axis":"y","offset":0},"offset":-30},
 {"op":"sketch","label":"s_def","dimensioning":"coordinates",
  "plane":{"reference":{"kind":"datum_feature","label":"pl_def"},
           "origin":[0,-30,0],"u_axis":[1,0,0]},
  "entities":[{"type":"rectangle","name":"rb","min":[-20,-10],"max":[20,10]}]},
 {"op":"extrude","label":"x_def","sketch":"s_def","depth":7,"direction":"positive","mode":"add"}
]
```
预期（按文档）：实体在 y∈[−37,−30]（沿 −Y 拉）；
实测：实体在 y∈[−30,−23]（沿 +Y 拉），回执 `normal=[0,1,0], v_axis=[0,0,-1]`。

---

## 2. ✅ 已修复：`dimensioning="coordinates"` 现在接受构造圆

上次 §2 的报错 `Coordinate dimensioning accepts lines, polylines, rectangles, circles, arcs and exact B-splines only` 不再出现。

作业 `4ba9b1052d8b44e8a7694dda91b4cbbc`：草图含 1 个 `construction=true` 的圆 `c01` + 1 个矩形，coordinates 模式一次通过：

```
native_section.construction_entities = 1
geometry_deviation.sample[0] = {"entity":"c01","kind":"construction_circle",
                                "measurement":"center_radius","deviation_mm":5.8e-48}
solved_section_area_mm2 = 800.0     ← 构造圆不计入轮廓面积（正确）
V = 5600.000000                    ← 800 × 7，精确
```

源码可见 `sketch_coordinates.cpp` 的 BUG-188 修复：构造实体进 `section_target_snapshot` 并打 `construction` 标记，参与求解但不进轮廓。请保持这个行为。

---

## 3. ✅ 已修复：`placement:"packaged"` 可用（装配语义补齐）

上次 §5 请求的能力已实现。作业 `26272f816ef44e0e8f2090ce9b4f0369` 在同一装配里放两个同源实例：

| 组件 | placement | 回读 constraint_count | 回读变换平移 | 回读 packaged |
|---|---|---|---|---|
| a_fixed | fixed | **1** | (100, 0, 0) | — |
| a_pack | packaged | **0** | (200, 0, 0) | 变换原样保留 |

装配重心 (150, −33.5, 0) = (100+200)/2，体积 11200 = 2×5600。**packaged 变换保留、零约束**，正是上次要求的"已定位但无约束"，可以表达源件"唯一固定件"的语义了。

---

## 4. ❌ 未修复：`dimensioning="coordinates"` 的几何变化容差仍不可配

上次 §3 请求暴露 `deviation_tolerance_mm`。0.46.1 传该参数：

```
Error: operations[0].deviation_tolerance_mm: Extra inputs are not permitted
```

`geometry_deviation.warning_threshold_mm=0.00001` 仍是只读回显；`tolerance_source="default_coordinates"` 仍写死。当圆弧心被求解器挪动 1.2e−5 mm（上次 Part 1 四个长圆槽的真实场景）时，whole-sketch 仍会被"几何不得改变"闸门拒绝，用户无法放行，只能整张草图退回 autodim、丢掉 6 位小数精度。

建议：给 `SketchOp` 增加可选 `deviation_tolerance_mm`（默认维持严格值），并让 `auto` 策略先试解，避免"选了 coordinates 又自己拒绝"。

---

## 5. ❌ 未修复：`mirror` 仍不能镜像实体特征

准入校验原样返回上次那段报错：

```
Toolkit mirror accepts curves, axes, quilts, datum planes, coordinate systems,
points or the whole part; a feature reference is not a mirror item and hangs Creo …
```

`MirrorOp.references` 的 allowed 集合仍不含 `feature`（schema.py 1778-1789）。本次 TXT 的 3 组镜像（MIR01–03，5 个特征）仍只能按坐标展开重建，特征树里没有镜像节点，参数化语义与源件不等价。

说明：这个限制写得很清楚、也有绕行方案，比静默错误好得多；但它确实是硬能力缺口。建议增加"镜像已创建的实体特征"独立 op（内部按 body + feature 列表镜像并合并）。

---

## 6. ❌ 未修复：模型名空格仍被拒

```
model_name="Part 1" →
model_name must be 1-31 characters of lowercase letters, digits and underscores;
' ' cannot be used (uppercase is lowercased)
```

大写现在会自动转小写（比上次友好），但空格仍拒。TXT 的源件名就是 `Part 1`，无法在 MCP 里保留原名。建议提供 display name 与 session name 分离；或至少允许空格内部映射。

---

## 7. ⚠️ 部分改进 / 信息项

### 7.1 多会话（上次 §6）
0.46.1 新增 `creo_startup_status(retry=true, session_id=...)`（FEAT-072），可显式选择会话；`session_candidates` 给出 PID 与指纹作诊断。但 `session_id` 仍**不能从 PID 推出**（页里明写 `selectable_by_pid=false`、`process_to_session_id=unsupported`），多会话时仍要人工去 Creo 里查 Session Info，或关掉多余会话。本次会话无 `-36`，未触发。

### 7.2 bbox 精度（上次 §8）
receipt 新增 `bounding_box_source="solid_face_tessellation"` 与 `target_chord_height_mm=0.001`，来源透明了（值得肯定）。但 tessellation 的 0.001 弦高仍会给曲面 bbox 带来系统偏差，做 0.001 mm 级比对仍需谨慎——建议 capabilities 明确"bbox 为离散弦高测量，非解析包围盒"。

### 7.3 mass 始终不可用（非回归，但影响使用）
五个受管模型全部 `material_assigned=true` 但 `mass_g=null`、`mass_unavailable_reason="material_query_failed"`：`ProSolidMassPropertyWithDensityGet (PRO_MP_DENS_DEFAULT)` 返回 −1。体积/面积/重心都准，只有质量取不到。若 `mass_properties` 工具已声明可回退到 `density_g_cm3`，建议在材料无密度时**自动**按提示回退（或明确写进 capabilities），否则用户每次都要手动补密度。

### 7.4 单通道并发读取诊断
并发发起 4 个 `creo_get_mass_properties` 时，3 个返回 `toolkit_busy`，但 `blocking_job_id=null`、`blocking_model_id=null`、`owner_determined=false`——无法知道是谁占用。自带 `creo_get_mass_properties_batch` 可正常串行完成（4/4，53.6 s）。建议在 busy 回复里尽量回填占用者，或让文档明确"批量读取请用 batch 工具"。

---

## 8. 值得肯定（别改坏）

1. **BUG-188 构造圆修复**干净利落：构造实体进快照、进求解、不进轮廓，`geometry_deviation` 里逐条标 `construction_circle`，是本次最实质的进步。
2. **`packaged` 放置**回读完整（constraint_count / transform / packaged 标志），装配重心可复算闭合。
3. **已有成果零回归**：0.46.1 读回的五个模型 V/A/重心与 0.43.1 逐位一致，说明版本升级没有破坏受管模型。
4. 新增 `v_axis` / `flip` / `rotation_convention` / `feature_state` / `component_constraints` 等一大批能力，方向正确。
5. `creo_get_mass_properties_batch`、`add_volume_check`、bbox 来源标注等可观测性改进，定位问题更快。

---

## 附：本次作业号索引

| 用途 | job_id | 结果 |
|---|---|---|
| flip + 构造圆复验 | `4ba9b1052d8b44e8a7694dda91b4cbbc` | 成功：构造圆被接受，V=5600 |
| packaged 复验 | `26272f816ef44e0e8f2090ce9b4f0369` | 成功：packaged 0 约束、变换保留 |
| 显式 v_axis 复验 | `47812e4ef2264454bc21441558a59b15` | 成功：normal 翻为 −Y，v=+Z |
| **默认路径（核心问题）** | `871315544bf14d0d97f2edb405c5e3a8` | **成功但几何反**：normal=+Y、v=−Z、拉到 −23 |
| 已交付成果复验 | `59e20fa248c14b37ba08e979cc51ec36` + `78cca59e…` / `de968be5…` / `72974267…` / `f1d5ecfd…` | 5/5 读回，几何逐位一致 |

---

## 附：修复优先级建议

| 优先级 | 条目 | 理由 |
|---|---|---|
| **P0** | §1 默认 XZ 偏移面法线与 `frames.XZ` 声明对齐；不一致时回执报 warning | 用户照文档写就静默做错，且体积查不出来 |
| P1 | §4 coordinates 容差可配 + auto 试解 | 堵死 6 位小数精度路线 |
| P1 | §5 特征级镜像 | 局部镜像是常见结构，特征树语义不等价 |
| P2 | §6 模型名允许空格 / display name 分离 | 影响可追溯性 |
| P2 | §7.3 mass 材料无密度时自动回退或写进文档 | 影响易用性 |
| P3 | §7.1 PID→session_id、§7.2 bbox 精度说明、§7.4 busy 占用者回填 | 可观测性 |
