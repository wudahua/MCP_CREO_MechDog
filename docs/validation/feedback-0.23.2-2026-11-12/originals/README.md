# 反馈包：球鼻艏无法用 MCP 曲面能力完成自动建模（Creo 10 + MCP_CREO_MechDog 0.23.2）

> 报告日期：2026-11-12
> 报告方环境：Creo Parametric **10.0.0.0**（`release_numeric = 42`），MCP_CREO_MechDog **0.23.2**
> 用途：提交给 MCP_CREO_MechDog 作者，用于修复低版本宿主上的曲面建模能力
> 结论定性：**不是"没有 API"，而是"Creo 10 上没有拼出完整元素树的任何途径"，且唯一的曲面入口因此完全不可用**

---

## 0. 这个包里有什么，建议按什么顺序读

```
README.md                      ← 本文件，主报告（问题 / 证据 / 已排除项 / 修复建议 / 验收标准）
01_TXT依据-球鼻艏B030.md        ← 任务的权威源数据摘录（3 截面 + 3 导线 + 后续封闭链）
源数据/
  简易护卫舰_跨软件三维建模自然语言说明.txt   ← 完整原文（135 KB），球鼻艏在第五节与附录 A18-A23 / B030-B038
  _bulb_sections.json                        ← 6 条样条的精确控制点/节点/权重（已按 1m→100mm 换算）
证据-作业回执/
  <job_id>.job.json / <job_id>.native_result.json  ← 10 个作业的原始输入与原始回执（未删改）
历史反馈文档/                  ← 前 6 份反馈（0.22.0 → 0.23.2），记录了每轮修复与被否证的假设
```

阅读顺序建议：**第 1 节（一句话问题）→ 第 5 节（最小复现）→ 第 11 节（修复路线）**。第 6~9 节是支撑证据，需要时再查。

---

## 1. 一句话问题

在 Creo 10 上，`surface_loft` 能把边界混合特征**建出来**（`create_code = 0`），但该特征恒为 `ProFeatureIsIncomplete = true`、几何项 0；随后 `ProFeatureElemtreeExtract` 以 `-18 (PRO_TK_INVALID_TYPE)` 拒绝，导致"不完整创建 → 提取 → 补全 → redefine"这条唯一的闭环在中途断开，作业必然回滚。

而 `surface_loft` 是 **Creo 10 上唯一能建出曲面（quilt）的 MCP 工具**：`surface_boundary_fill` 被能力表屏蔽，MCP 也没有任何几何导入操作。因此"用 MCP 曲面能力自动建一个过曲线的曲面"在本机**没有任何可用入口**。

---

## 2. 环境与版本

| 项 | 值 |
|---|---|
| Creo | Parametric 10.0.0.0，`release_numeric = 42`（`creo_release_query_code = 0`） |
| MCP 版本（最终验收） | `server_version = 0.23.2` |
| worker（0.23.2） | `worker_sha256 = b95cd7c2655b0799bb8efb6f68e21ac891157af970b42d78c135f53e5326864a` |
| worker（0.23.1） | `worker_sha256 = a50fd90b5697dd3a9006254c64849fb944580ffef4316420b9a6036bd5ee52e6` |
| 连库方式 | `explicit_live`，`single_channel_busy_rejects_immediately` |
| 测试模型 | `bulb_l030`，`model_id = 806b9d5336354515986d9776bafff46f`，rev4，单位 mm，无实体 |

**作者基线是 Creo 12.4.0.0（`release_numeric = 44`）。本包所有结论只针对 42，不外推到 44，也不反过来否定 44。**

### 2.1 关于"诊断构建"的诚信声明

第 6 节中标注为 **[诊断构建]** 的证据，来自报告方在 0.23.0 源码基础上做的**本地探针构建**。该构建只增加了以下内容，**没有改动官方的判定逻辑**：

- 把建树函数参数化（form 取值、`PRO_E_DTM_SRF_TYPE` 写/不写、`PRO_E_BBL_ADD_CLOSED`、`PRO_E_BNBLN_RULED`、几个未写入元素、元素顺序）；
- 在一次作业内循环尝试多个候选，记录每个候选的 `create_code` / `extract_code` / `ProFeatureIsIncomplete` / 几何项数 / 面数 / quilt 数，失败即删除该候选特征；
- 增加 `ProElemtreeVerify` + `ProElementDiagnosticsCollect` 的诊断遍历。

标注为 **[官方 0.23.1]** / **[官方 0.23.2]** 的证据来自未修改的官方发布物。**结论性判断以官方版本证据（E8、E9、E10）为准**，诊断构建只用于定位"到底哪一维是决定性的"。

---

## 3. 任务目标与源数据（TXT 附录 B030）

源文档：`源数据/简易护卫舰_跨软件三维建模自然语言说明.txt`（完整原文已随包提供）。球鼻艏相关位置：第五节（第 77~91 行）、附录 A18~A23、附录 B030~B038。

### 3.1 要建的东西

X 向延伸、前端圆尖、横向圆鼓的水下球鼻艏半体（另一半按 Y=0 镜像）：

- 范围：X = 64.094736 ~ 78.098843 m，Z = −6.600046 ~ −4.599998 m，半体 Y = −1.818679 ~ 0
- 中心高度 Z = −5.6 m

### 3.2 B030 原文（这是本次失败的**唯一**断点）

> **B030．Surface-Loft2：导线曲面放样。**
> 截面按艏尖点 Sketch69、X=72.094736 的 Sketch70、X=64.094736 的 Sketch72 排列；上、侧、下三条纵向导线分别来自 Sketch64、Sketch67 的样条、Sketch65。
> 草图/曲线组：Sketch69、Sketch70、Sketch72、Sketch64、Sketch65、Sketch67。

即：**1 个收敛点 + 2 个截面 + 3 条导线**，正是 `surface_loft` 的 `sections` + `guides` 参数形态。

### 3.3 B030 之后整条链（**MCP 在 Creo 10 上全都支持**）

| TXT 条目 | 含义 | MCP 对应能力 | Creo 10 可用性 |
|---|---|---|---|
| B031 Surface-Plane1 | 中心纵向侧面（平面封闭） | `surface_fill`（`PRO_FLAT` 数据面） | ✅ 已实测可建（见 E4 的 29 元素平面树） |
| B032 Surface-Plane2 | X=64.094736 后截面封闭 | 同上 | ✅ |
| B033 Surface-Knit1 | 曲面缝合为封闭实体 | `quilt_merge` | ✅ 工具存在 |
| B034 Mirror4 | 以 Y=0 镜像 | `mirror` | ✅ 工具存在 |
| B035 Fillet1 | R1 圆角 | `round` | ✅ 工具存在 |
| B036 Combine1 | 与船体布尔并 | `boolean_bodies` | ✅ 工具存在 |

**这一点很重要：整条球鼻艏链上只有 B030 一步不可用，其余 6 步都有现成工具。** 换句话说，只要能建出 B030 那一张曲面，整个球鼻艏就能全自动做完。

### 3.4 建模输入的精确坐标（供作者复现，单位 mm，1 m → 100 mm）

| 条目 | 类型 | 关键数据 |
|---|---|---|
| A18 Sketch64 | XZ 平面（法线 −Y），上导线 | 直线 (7209.4736,0,−460)→(6409.4736,0,−460)；三次 NURBS CP (7809.4736,0,−560),(7809.4736,0,−480),(7316.1403,0,−460),(7209.4736,0,−460)，knots [0,0,0,0,1,1,1,1]，w 全 1 |
| A19 Sketch65 | XZ 平面，下导线 | 直线 (7389.4736,0,−660)→(6409.4736,0,−660)；三次 NURBS CP (7809.4736,0,−560),(7813.3655,0,−616.6486),(7465.0051,0,−654.8108),(7389.4736,0,−660) |
| A20 Sketch67 | XY@Z=−560 平面，侧导线 | 三次 NURBS CP (6409.4736,180,−560),(6509.4736,180,−560),(7006.7197,204.7741,−560),(7809.4736,33.3333,−560),(7809.4736,0,−560)；knots [0,0,0,0,0.595088181,1,1,1,1] |
| A21 Sketch69 | YZ@X=7809.4736，**收敛点** | 单点 (7809.4736,0,−560) |
| A22 Sketch70 | YZ@X=7209.4736，中截面 | 三次 NURBS 6 CP：(7209.4736,0,−460),(7209.4736,36,−460),(7209.4736,140.7116,−509.6870),(7209.4736,141.0725,−610.6863),(7209.4736,30,−660),(7209.4736,0,−660)；knots [0,0,0,0,0.448628655,0.548628655,1,1,1,1] |
| A23 Sketch72 | YZ@X=6409.4736，后截面 | 三次 NURBS 6 CP：(6409.4736,0,−460),(6409.4736,60,−460),(6409.4736,180.725,−469.1667),(6409.4736,181.325,−650.8333),(6409.4736,54,−660),(6409.4736,0,−660)；knots [0,0,0,0,0.45,0.55,1,1,1,1] |

可直接读取的机器可读版本：`源数据/_bulb_sections.json`。

**注意：TXT 原文第五节末尾有一句"建议近似：如果软件不容易进行导线曲面放样，可用……多截面放样代替"。本项目已明确禁用该近似替代**，理由：3 条导线是源模型的真实约束，去掉导线后曲面形状不可控，无法与源模型比对。这条约束是本次报告的背景，不是 MCP 的问题。

---

## 4. 期望 vs 实际

| | 期望 | 实际（Creo 10 / 0.23.2） |
|---|---|---|
| `creo_surface_loft(sections=[A21,A22,A23], guides=[A18,A20,A19])` | 返回 1 张开放 quilt，含 `quilt_id` / `surface_area_mm2` / `quilt_closed_native=open` | 作业回滚，`message` 为 `... SURFACE_LOFT_EXTRACT_UNSUPPORTED ...` |
| 特征是否创建 | 是 | **是**（`create_code = 0`） |
| 特征是否有几何 | 是 | **否**（几何项 0 / 面 0 / quilt 0，`feature_incomplete = true`） |
| 能否回读该特征 | 是 | **否**（`extract_code = -18`） |
| 后续 B031~B036 | 全自动 | 无法开始，因为没有第一张曲面 |

---

## 5. 最小复现（3 步，约 1 分钟）

前提：Creo 10 + MCP 0.23.2，模型中已存在两张截面草图与（可选）导线草图。任何两张**开放**曲线草图即可复现，不需要球鼻艏的真实几何。

```
1) 建一个 part，画两个开放样条草图（不需要闭合、不需要相切）
2) 调用 creo_surface_loft(model_id, expected_revision, label="x", sections=[<s1>,<s2>])
3) 观察回执
```

**实测回执（官方 0.23.2，job `be450d6a74bb4868acc1ddd3d897cd63`）：**

```json
{
  "success": false,
  "failed_stage": "execute_surface_loft",
  "message": "surface_loft created the feature (create_code=0) but this Creo release cannot extract its element tree (code -18, SURFACE_LOFT_EXTRACT_UNSUPPORTED); feature_incomplete=true, release_numeric=42; the job was rolled back",
  "operations": [{
    "create_code": 0,
    "extract_code": -18,
    "extract_unsupported": true,
    "kernel_completion": "unsupported",
    "feature_incomplete": true,
    "kernel_evidence": { "release_numeric": 42, "create_code": 0, "extract_code": -18, "feature_incomplete": true },
    "rollback_succeeded": true
  }]
}
```

同一现象在官方 0.23.1（job `654f237ab7bf4850a9f3a55fa70778c1`）和官方 0.23.0（历史文档记录）上完全一致，**跨三个补丁版本未变**。

---

## 6. 证据链

### E8 **[官方 0.23.1]** — 现象确认

- job `654f237ab7bf4850a9f3a55fa70778c1`，`surface_loft`，sections=[40,48]
- `create_code = 0` / `extract_code = -18` / `failed_stage = execute_surface_loft`
- 结论：0.23.1 修的 `has_solid` 增量判断位于提取之后，**在 Creo 10 上永远执行不到**

### E9 **[官方 0.23.2]** — 诊断字段到位后的同一现象

- job `be450d6a74bb4868acc1ddd3d897cd63`
- 新增字段全部按预期出现（`extract_unsupported` / `kernel_completion` / `kernel_evidence` / `feature_incomplete`）
- **请求 A、B 已确认落地**；现象本身未变

### E10 **[官方 0.23.2]** — 连只读导出也被拦住

- job `7d38c7c2b8d14f589fee876e875f9bd7`，`export format=step`，model `bulb_guide_0200`
- 结果：`BUILD_FAILED: model_reconciliation_required: Saved feature/body count changed`
- 结论：GUI 手工保存后 `model.json` 基线计数漂移，**连不修改模型的 `export` 也被前置拒绝**（见第 12 节次要问题）

### E1 **[诊断构建]** — form × `PRO_E_DTM_SRF_TYPE` 两轴

job `523ad12fdbb84309a31a7132f1b4bcfa`

| form | 名称 | 写 DTM | `create_code` | quilt |
|---|---|---|---|---|
| 512 | `PRO_USE_SURFS` | 是 | **0** | 0 |
| 512 | `PRO_USE_SURFS` | **否** | **-1** | — |
| 1024 | `PRO_FLAT` | 是 | 0 | 0 |
| 16384 | `PRO_ADV_SURF` | 是 | **-1** | — |
| 16384 | `PRO_ADV_SURF` | 否 | **-1** | — |

结论：**`PRO_E_DTM_SRF_TYPE` 是必填元素**（不写即 -1）；`PRO_ADV_SURF` **不是**边界混合的 form。

### E2 **[诊断构建]** — `PRO_E_BBL_ADD_CLOSED` / `PRO_E_BNBLN_RULED`

job `12dfb03cdc95424c986dbc4fcb36720f`，6 组候选，**全部 `create_code = 0` 且 quilt = 0**。
结论：这两个元素不是缺口。

### E3 **[诊断构建]** — 几何判据复核（避免"quilt=0 所以没几何"的误判）

job `033cd32dbe634b5da16183c4cfbe22ee`。对每个创建成功的特征同时统计 quilt / 全部几何项 / 面：

| 候选 | `create_code` | `ProFeatureIsIncomplete` | 几何项 | 面 | quilt |
|---|---|---|---|---|---|
| 512 + DTM | 0 | **true** | 0 | 0 | 0 |
| 1024 + DTM | 0 | **true** | 0 | 0 | 0 |
| 262144 + DTM | 0 | **true** | 0 | 0 | 0 |
| 2097152 + DTM | 0 | **true** | 0 | 0 | 0 |

结论：**不是"quilt 计数口径错"，是真的一个几何项都没有**，特征确为空壳。同时证明 `ProFeatureIsIncomplete` 是一个**有效且廉价**的判据（这也是向作者建议 A 的依据）。

### E4 **[诊断构建]** — 两个提取器对照（本包最关键的一条）

job `893500e0d1ad47b0b9796d4e5a76485e`

| 候选 | `extract_code`（提取） | `ProFeatureElemtreeCreate`（WF5 前老接口） | 结果 |
|---|---|---|---|
| 512 `PRO_USE_SURFS` + DTM | **-18** | **-18** | 无树可读 |
| 1024 `PRO_FLAT` + DTM | **0** | **0** | 读到 **29 个元素** |

上表四个 `extract_code` 全部取自回执 `893500e0….native_result.json` 的 `operations[0].form_candidates[*]`，字段名为 `extract_code_in_loop` 与 `legacy_elemtree_create_code`；"29"这个数取自同处的 `legacy_tree_elements`。**即上表逐列可由回执复算，无需信任本报告的转述。**

1024 读出的那棵树是**平面数据面**，结构为（**元素 ID 明细来自诊断构建的会话终端输出，未单独存盘；元素总数 29 有回执背书，明细若需原件可由作者用 job `893500e0…` 同参数复跑取得**）：

```
386 PRO_E_FEATURE_TREE
├ 387 PRO_E_FEATURE_TYPE = 942 (PRO_FEAT_DATUM_SURF)
├ 388 PRO_E_FEATURE_FORM = 1024 (PRO_FLAT)
├ 447 PRO_E_STD_SECTION  … 725/2195/726/450(SETUP_PLANE)/458(SKETCHER)
├ 458 PRO_E_SKETCHER
├ 1964 PRO_E_STD_FEATURE_NAME
└ 436 / 3332 / 3333 / 5104 / 6711 …
```

**`PRO_E_BNBLN_CURVES` 子树在这棵树里根本不存在** —— 说明 form=1024 时内核把整棵 BNBLN 子树丢弃，当成平面曲面建。这解释了为什么 1024 可提取却也没有几何。

### E5 **[诊断构建]** — 12 个 `ProFeatFormType` 全扫

job `cbab995400184a989529f6be94943551`

| form 值 | 名称 | `create_code` | `extract_code` | 几何 |
|---|---|---|---|---|
| 省略 | — | -1 | — | — |
| 0 | `PRO_NOTYPE` | -1 | — | — |
| 8 | `PRO_BLEND` | -1 | — | — |
| 128 | `PRO_THIN` | -1 | — | — |
| **512** | **`PRO_USE_SURFS`** | **0** | **-18** | 0 |
| 1024 | `PRO_FLAT` | 0 | 0 | 0 |
| 4096 | `PRO_COPY` | **-2** | — | — |
| 16384 | `PRO_ADV_SURF` | -1 | — | — |
| 262144 | `PRO_SHUT` | 0 | 0 | 0 |
| 524288 | `PRO_SKIRT_EXT` | -2 | — | — |
| 1048576 | `PRO_SKIRT_FILL` | -2 | — | — |
| 2097152 | `PRO_PRTSPLIT` | 0 | 0 | 0 |

**核心发现：只有 512 保留 `PRO_E_BNBLN_CURVES` 子树，而 512 恰好是唯一提取失败的那个取值。** 四个"创建成功"的取值里，另三个都把 BNBLN 子树丢掉了。

### E6 **[诊断构建]** — 补入 SDK 声明过、`surface_loft` 从未写的 14 组元素

job `948f49e0d85e41d8b6a705d65b8b3644`。覆盖 `PRO_E_BLEND_TYPE`∈{0,1,2}、`PRO_E_CTRL_TYPE`∈{0,1}、`PRO_E_BBL_APPENDIX`、`PRO_E_CTRL_PTS`、`PRO_E_REFERENCE_CURVES`、`PRO_E_CHAIN_CURVES`、`PRO_E_BNBLN_ADVANCED`、`PRO_E_BNBLN_TAN_COND`，以及"全部同时加"。

结果：14 组 `create_code` 全为 `-1`（该轮用 `PRO_FEAT_CR_NO_OPTS`）。

**但这一轮的判据后来被自己否证（见 E7），因此本节不作为结论使用，只保留两条副产品：**

- `PRO_E_BLEND_TYPE`、`PRO_E_CTRL_TYPE`、`PRO_E_BBL_ADD_CLOSED`、`PRO_E_BNBLN_RULED` 是**整型**元素（写入成功）；
- **`PRO_E_BNBLN_TAN_COND` 不是整型元素**：`ProElementIntegerSet(...)` 返回 `-18`。这解释了为什么 `surface_loft_apply_conditions` 必须走"提取后补写"的路径——而那条路径在 Creo 10 上根本到不了。

### E7 **[诊断构建]** — 判据自检（把 E6 的结论作废）

job `93aead46b7794f0a9693f23c5b01bdff`，同时测元素顺序与**对照组**：

| 候选 | `create_code` |
|---|---|
| 1024（已知能建成、且可提取）`NO_OPTS` | **-1** ← 对照组 |
| 262144 `NO_OPTS` | -1 |
| 2097152 `NO_OPTS` | -1 |
| 512 `NO_OPTS` | -1 |
| 512 `name` 移到曲线后 | -1 |
| 512 不写 `name` | -1 |
| 512 `DTM_SRF_TYPE` 移到曲线后 | -1 |
| 512 `INCOMPLETE`（控制） | **0** |

**对照组（已知合法的平面树）在 `NO_OPTS` 下也是 -1**，说明 `PRO_FEAT_CR_NO_OPTS` 对数据面类特征**恒返回 -1**，与树是否完整无关 → **E6 的"全 -1"不能证明"缺元素"**。此更正已写入历史反馈文档，本节在此重申，以免误导作者。

同时得出：**元素顺序不是原因**（四种布局无差异）。

---

## 7. 内核行为矩阵（汇总）

```
Creo 10 (release_numeric=42) 上，边界混合元素树的行为：

FORM=512 (PRO_USE_SURFS) + PRO_E_DTM_SRF_TYPE=11
  ├── 保留 PRO_E_BNBLN_CURVES 子树 ......... 是（唯一）
  ├── ProFeatureWithoptionsCreate(INCOMPLETE) ... 0（成功，但为不完整特征）
  ├── ProFeatureWithoptionsCreate(NO_OPTS) ..... -1（无 element_errors 归因）
  ├── ProFeatureIsIncomplete ................... true
  ├── 几何项 / 面 / quilt ...................... 0 / 0 / 0
  ├── ProFeatureElemtreeExtract ................ -18 PRO_TK_INVALID_TYPE
  ├── ProFeatureElemtreeCreate（老接口） ....... -18 PRO_TK_INVALID_TYPE
  ├── ProElemtreeVerify(solid, NULL, tree) ..... -2 PRO_TK_BAD_INPUTS
  └── ProElementDiagnosticsCollect ............. 0 条（诊断只由 verify 挂载）

FORM=1024 / 262144 / 2097152
  ├── 保留 BNBLN 子树 ......................... 否（子树被丢弃）
  ├── create ................................. 0，但仍是 incomplete 空壳
  └── extract ................................ 0（读到的是另一类曲面的树）
```

**用户 GUI 手工建的同类特征同样 `-18`**（`bulb_guide_0200` 中的手工边界混合），所以这不是"MCP 造的树不合法"，而是**这一类特征在 Creo 10 上一律不可提取**。

---

## 8. SDK 事实清单（Creo 10.0.0.0，路径 `D:\Program Files\PTC\Creo 10.0.0.0\Common Files\protoolkit\includes`）

### 8.1 错误码（`ProToolkitErrors.h`）

| 值 | 名称 | 行 |
|---|---|---|
| -1 | `PRO_TK_GENERAL_ERROR` | 13 |
| -2 | `PRO_TK_BAD_INPUTS` | 14 |
| -4 | `PRO_TK_E_NOT_FOUND` | 16 |
| **-18** | **`PRO_TK_INVALID_TYPE`** | **30** |

`ProFeature.h:1418` 对该返回值的释义：`Extraction of the element tree is not supported for this feature type`。

### 8.2 边界混合元素（`ProElemId.h`）

| 元素 | ID | 行 | 说明 |
|---|---|---|---|
| `PRO_E_BNBLN_CURVES` | 661 | 753 | 曲线根 |
| `PRO_E_BNBLN_1DIR` | 651 | 743 | 第一方向 |
| `PRO_E_BNBLN_2DIR` | 652 | 744 | 第二方向（导线） |
| `PRO_E_BNBLN_DIR_CURVES` | 657 | 749 | 方向内的曲线组 |
| `PRO_E_BNBLN_TAN_COND` | 459 | 516 | 相切条件（**非整型**） |
| `PRO_E_BNBLN_TNC_BNDRY` / `TAN_COND_TYPE` / `TAN_REF_TYPE` | 460 / 461 / 462 | 517~519 | 相切子元素 |
| `PRO_E_BNBLN_ADVANCED` | 469 | 526 | 高级选项 |
| `PRO_E_BNBLN_RULED` | 1206 | 1296 | 直纹开关 |
| `PRO_E_BBL_ADD_CLOSED` | 3175 | 2440 | 每方向闭合开关 |
| `PRO_E_BBL_APPENDIX` | 3170 | 2433 | 附录块 |
| `PRO_E_BLEND_TYPE` | 646 | — | 混合类型（整型，取值域无文档） |
| `PRO_E_CTRL_TYPE` | 639 | — | 控制点类型（整型，取值域无文档） |
| `PRO_E_DTM_SRF_TYPE` | 1131 | 1204 | **注释原文 `/* Non redef dtm srf type */`** |

### 8.3 `ProFeatForm.h` 全量枚举（`Pro_FeatFormType`）

```
PRO_NOTYPE=0, PRO_EXTRUDE=1, PRO_REVOLVE=2, PRO_SWEEP=4, PRO_BLEND=8,
PRO_THIN=128, PRO_USE_SURFS=512, PRO_FLAT=1024, PRO_COPY=4096,
PRO_ADV_SURF=1<<14, PRO_SHUT=1<<18, PRO_SKIRT_EXT=1<<19,
PRO_SKIRT_FILL=1<<20, PRO_PRTSPLIT=1<<21
```

**该枚举里没有"边界混合"成员**。边界混合只能通过 `PRO_E_DTM_SRF_TYPE = 11` 表达，而该元素的注释明写它是"非重定义"类型 —— 这与 E5 的实测完全吻合。

### 8.4 元素树接口（`ProElement.h` / `ProFeature.h`）

| 接口 | 位置 | Creo 10 实测 |
|---|---|---|
| `ProElementDiagnosticsCollect` | `ProElement.h:3036` | 可用，但恒 0 条（诊断由 verify 挂载） |
| `ProElemtreeVerify` | `ProElement.h:3127` | **-2 BAD_INPUTS**（传 NULL 路径） |
| `ProElemtreeWrite` | `ProElement.h:3166` | 声明存在 |
| `ProElemtreeFromXMLCreate` | `ProElement.h:3207` | 声明存在 |
| `ProFeatureElemtreeCreate`（WF5 前） | `ProFeature.h:1332` | **-18** |
| `ProFeatureElemtreeExtract` | `ProFeature.h:1410` | **-18** |
| `ProFeatureWithoptionsCreate` | `ProFeature.h:462` | 可用（512 返回 0） |
| `ProFeatureWithoptionsRedefine` | `ProFeature.h:514` | 无法验证（没有可用的树） |

`ProFeatureElemtreeExtractOptions` 只有一个值 `PRO_FEAT_EXTRACT_NO_OPTS = 0`（`ProFeature.h:123`），**没有"换一种提取方式"的选项**。

### 8.5 曲面创建接口

```
grep -n "extern ProError" ProSurface.h    → 无任何创建函数（只有 Init/DataGet/Eval/TypeGet/Tessellation…）
grep -n "extern ProError" ProSurfReg.h    → 0 个
grep -n "extern ProError" ProUnifySurf.h  → 0 个
grep -n "extern ProError" ProFlatSrf.h    → 0 个
```

即：**Creo 10 没有任何"非元素树"的曲面创建 API**。边界混合的唯一入口就是元素树，而元素树在 42 上无法补全。

### 8.6 关于 `Probbl.h`

作者源码注释多处引用 `Probbl.h`（"Probbl.h documents…"）。**Creo 10 的 includes 目录里没有这个文件**（`ls Probbl.h` → No such file）。作者随包的三个副本均为测试夹具，内容是单行 `// fixture`：

```
.tmp/tmp1g6tg9qy/Creo with spaces/Common Files/protoolkit/includes/Probbl.h → "// fixture"
```

因此**低版本侧既没有文档、也没有接口能告知"缺哪些元素"**。

### 8.7 导入接口（`ProIntfimport.h`，见第 11.2 节路线 D）

| 接口 | 行 | 说明 |
|---|---|---|
| `ProIntfimportSourceTypeGet` | 82 | 导入前判定会建成什么模型类型 |
| `ProIntfimportModelWithOptionsMdlnameCreate` | 176 | **推荐入口**（旧 `ProIntfimportModelWithProfileCreate` 已 `DEPRECATED: Since Creo 1`） |
| `PRO_INTF_IMPORT_STEP` = 6 / `PRO_INTF_IMPORT_IGES` = 1 | 12~33 | 枚举齐备 |

---

## 9. 已排除的假设（含报告方自我否证）

| # | 假设 | 结论 | 依据 |
|---|---|---|---|
| 1 | `PRO_E_DTM_SRF_TYPE` 不写也行 | **否**，必填 | E1（512 不写即 -1） |
| 2 | 高级曲面应该用 `PRO_ADV_SURF = 1<<14` | **否**，create 直接 -1 | E1、E5（**这是报告方上一轮提出的假设，已自我否证**） |
| 3 | 缺 `PRO_E_BBL_ADD_CLOSED` | 否，无差异 | E2 |
| 4 | 缺 `PRO_E_BNBLN_RULED` | 否，无差异 | E2 |
| 5 | 是"quilt 计数口径"错了，其实有几何 | **否**，几何项/面也为 0 | E3 |
| 6 | 补上 `BLEND_TYPE` / `CTRL_TYPE` / `APPENDIX` / `ADVANCED` / `REFERENCE_CURVES` / `CHAIN_CURVES` / `CTRL_PTS` / `TAN_COND` 就能完整 | **未能证明**（判据失效，见 #7） | E6 |
| 7 | `PRO_FEAT_CR_NO_OPTS` 返回 -1 = 树缺必填元素 | **否**，已知合法平面树也是 -1 | E7（**报告方自我否证**） |
| 8 | 元素顺序问题（`name` / `DTM_SRF_TYPE` 位置） | 否，四种布局无差异 | E7 |
| 9 | 是 MCP 造的树不合法 | **否**，GUI 手工建的同类特征同样 -18 | 第 7 节末 |
| 10 | 换用已废弃的 `ProFeatureElemtreeCreate` 能读到树 | 否，同样 -18 | E4 |

**关于第 6 条必须说清楚**：它既没被证实也没被证伪。`PRO_E_BNBLN_TAN_COND` 的正确数据类型/父级在本机无法确定（整型写入即 -18），而相切条件是 GUI 里每一条边界都会出现的元素。**如果作者有 Creo 12 环境，导出真实树即可一次性回答这一条** —— 这正是路线 C 的价值。

---

## 10. 为什么这不是"调用方式不对"

报告方逐一排除了以下可能，供作者快速判断：

1. **树结构与官方同类实现一致**：`native/surface_boundary_fill.cpp` 写的树（TYPE=942 / FORM=512 / DTM=11 / BNBLN_CURVES / 1DIR+2DIR / 每方向 `PRO_E_BBL_ADD_CLOSED`）与 `surface_loft` 几乎相同，两者在 Creo 10 上表现一致（都无法完成）。
2. **`create` 确实返回 0**，特征对象存在、`ProFeatureStatusGet = PRO_FEAT_ACTIVE`，说明内核接受了这棵树，不是语法错误。
3. **GUI 手工建的同类型特征也无法提取**，排除"树内容不合法"。
4. **两个独立提取器同时 -18**，排除"用错接口"。
5. **`element_errors.total` 恒为 0**，内核拒绝但不归因 —— 不是参数值越界，而是缺元素/不支持。
6. **12 个 form 全扫**，排除"只是 form 选错"。

---

## 11. 两条可行修复路线（按性价比排序）

### 11.1 路线 C：由 Creo 12.4 导出一次模板 XML（最省事、最彻底）

**原理**：Creo 12.4 上提取是通的（作者 FEAT-065 已 live-verified）。用 `ProElemtreeWrite` 把一次真实边界混合的元素树导出为 XML，作为模板随包发布。低版本用 `ProElemtreeFromXMLCreate` 读入，只替换曲线引用再 `ProFeatureWithoptionsCreate`——**完全绕开提取**，因为树是外部提供的完整树，不需要内核补全。

**为什么这条路成立**：`ProElemtreeWrite` / `ProElemtreeFromXMLCreate` 在 Creo 10 SDK 中都有声明（`ProElement.h:3166 / 3207`），`ProElemtreeFromXMLCreate` 的文档原文就说它的产物"can be used as an input to ProFeatureWithoptionsCreate or ProFeatureWithoptionsRedefine"。缺的**只有那棵树**。

**实现骨架**：

```cpp
// 一次性的导出（作者在 12.4 上做）
ProElement tree = nullptr;
if (!ProFeatureElemtreeExtract(&feat, nullptr, PRO_FEAT_EXTRACT_NO_OPTS, &tree)) {
    ProElemtreeWrite(tree, PRO_ELEMTREE_XML, L"bulb_boundary_blend_template.xml");
    ProFeatureElemtreeFree(&feat, tree);
}

// 低版本消费（MechDog 侧）
ProElement tmpl = nullptr;
ProXMLErrorlist *errors = nullptr;
if (!ProElemtreeFromXMLCreate(template_path, &tmpl, &errors)) {
    replace_curve_collections(tmpl, resolved_curve_refs);   // 只替换 PRO_E_STD_CURVE_COLLECTION_APPL
    ProFeatureWithoptionsCreate(sel, tmpl, opts_no_opts, PRO_REGEN_NO_FLAGS, &feat, &es);
    ProElementFree(&tmpl);
}
```

**风险**：模板必须与输入曲线数量匹配（解引用后逐个数对上），否则会退化。建议模板按"方向 1 曲线数 × 方向 2 曲线数"参数化几份，或在替换后调用作者已有的一致性检查。

### 11.2 路线 D：增加 `import_geometry` 操作（低版本通用，且高版本也有用）

**原理**：Creo 10 SDK 自带导入接口，直接导入按精确 NURBS 数据生成的 STEP/IGES 曲面。导入结果是**由内核解析出来的原生曲面**，不是近似。

**接口**（`ProIntfimport.h:176`）：

```c
ProError ProIntfimportModelWithOptionsMdlnameCreate(
        ProPath                  import_file,
        ProPath                  profile,        /* 建议显式传受管 profile 并记录 SHA256 */
        ProIntfImportType        type,           /* PRO_INTF_IMPORT_STEP (=6) / _IGES (=1) */
        ProMdlType               create_type,    /* PRO_MDL_PART 或 PRO_MDL_UNUSED */
        ProImportRepType         rep_type,       /* PRO_IMPORTREP_MASTER */
        ProMdlName               new_model_name,
        ProIntfimportLayerFilter filter_func,    /* 可为 NULL */
        ProAppData               application_data,
        ProMdl*                  created_model);
```

**建议的操作形态**：

```json
{"op": "import_geometry", "label": "bulb_srf", "file": "<abs path>",
 "format": "step", "new_model_name": "bulb_srf_import"}
```

**回执建议字段**：`created_model_name`、`create_code`、`surface_count`、`area_mm2`、`quilt_closure`、`profile_path` + `profile_sha256`。

**两点设计注意**：

1. 它是**新建模型**，不是"在已有模型里加特征"。建议就设计成"导入到独立 part"，由调用方用现有 `assemble_component` 组合，语义更干净，也避免主模型回滚时把导入件一起卷走。
2. `profile` 传 NULL 会用会话默认，且文档写明"profile 一旦设定就在整个会话内有效"。要可复现就必须显式传并记录。

### 11.3 两条路线的差别（供选型）

| | 路线 C（模板 XML） | 路线 D（导入） |
|---|---|---|
| 得到的是什么 | **原生边界混合特征**（有特征树、可编辑定义） | 原生曲面（无该特征，可后续 solidify/mirror/boolean） |
| 低版本可编辑性 | 高（改曲线即改曲面） | 中（改形状要重新导入） |
| 对"项目要交付原生特征"的价值 | **高** | 中 |
| 作者实现成本 | 低（一次导出 + 一个 loader） | 中（一个约 40 行的原生操作 + profile 管理） |
| 高版本收益 | 无（本来就通） | **有**（能导入外部精确曲面做比对） |

**两条不冲突，建议都做。**

---

## 12. 次要问题（本轮附带发现，建议一并处理）

### 12.1 `kernel_completion="unsupported"` 时仍允许提交，仍会先建空壳

0.23.2 已在能力表披露 `kernel_completion`，但 `surface_loft` 仍会照常提交，在模型里真实创建一个 `PRO_FEAT_ACTIVE` 的不完整特征，再靠整作业回滚清掉。

建议：`kernel_completion == "unsupported"` 且 `release_numeric` 未变时直接拒绝，不建特征。现在的形态等于"用一个必然失败的作业去换一条已经知道的结论"。

### 12.2 `export` / `inspect` 被保存基线漂移拦住

job `7d38c7c2b8d14f589fee876e875f9bd7`：

```
BUILD_FAILED: model_reconciliation_required: Saved feature/body count changed
```

用户在 Creo 里手工加特征并直接保存后，`model.json` 记录的 feature/body 计数与重新加载后的实测不一致，**连只读的 `export` 也被前置拦截**。

这直接杀掉了"GUI 手工建 + MCP 验证"这条混合流程：即使愿意手工建一次，MCP 也会先把手工建的几何挡在门外，必须先人工走 `creo_reconcile_model`。

建议：(a) 不修改模型的操作（`export` / `inspect`）不受基线漂移影响；(b) 至少把"该用哪个 action"写进错误消息 —— 现在的 `model_reconciliation_required` 只说了现象。

### 12.3 `surface_loft` 的 `boundary_conditions` 在低版本无法验证

`PRO_E_BNBLN_TAN_COND` 不是整型元素（写入即 -18），而 `surface_loft_apply_conditions` 依赖"提取后补写"。提取不可用 → 相切条件在 Creo 10 上永远无法被验证，也无法作为"让特征变完整"的手段。

---

## 13. 验收标准（作者修完后如何判定通过）

建议用下面这组**客观、可复算**的判据，不需要主观判断"像不像"。

### 13.1 最小通过条件（任何两张开放曲线）

| 项 | 要求 |
|---|---|
| `create_code` | 0 |
| `extract_code` | 0（若走路线 C，则要求能被 `ProFeatureElemtreeExtract` 读到，或明确声明"该模板树不需回读"） |
| `feature_incomplete` | **false** |
| `quilt_count` | 1 |
| `quilt_closed_native` | `open` |
| `surface_area_mm2` | 有限正数，且回执给出 |
| `kernel_completion` | `"supported"` |

### 13.2 球鼻艏专项条件（用本包 `源数据/` 的真实几何）

用 A18~A23 建 6 张草图 → `sections=[A21(点), A22, A23]`、`guides=[A18, A20, A19]`：

| 项 | 要求 |
|---|---|
| quilt 数量 | 1 |
| 包围盒（mm） | X ∈ [6409.4736, 7809.4736]，Y ∈ [0, 181.325]，Z ∈ [−660, −460]，各向容差 ≤ 1e-3 |
| 闭合性 | `open`（半体曲面，后续由 B031/B032 封面） |
| 保存 + 重载 | `saved_file_reloaded_and_verified = true` |
| 后续链 | B031/B032 `surface_fill` → B033 `quilt_merge` → B034 `mirror` → B036 `boolean_bodies` 能连续跑通 |

包围盒来自 TXT 原文（第五节）与附录控制点，**不是估计值**，可以直接作为自动断言。

### 13.3 建议随修复一起补的回归

- 同类树在 `release_numeric=42` 下必须命中"不支持"分支且**不建特征**（对应 12.1）；
- `export` 在基线漂移时仍可用（对应 12.2）。

---

## 14. 附件清单

| 文件 | 说明 |
|---|---|
| `01_TXT依据-球鼻艏B030.md` | B030 相关原文摘录 + 坐标表 |
| `源数据/简易护卫舰_跨软件三维建模自然语言说明.txt` | 完整原文（135,198 B） |
| `源数据/_bulb_sections.json` | 6 条样条精确数据（175,646 B） |
| `证据-作业回执/*.job.json` | 10 个作业的原始输入 |
| `证据-作业回执/*.native_result.json` | 10 个作业的原始回执（未删改） |
| `历史反馈文档/` | 0.22.0 ×2 / 0.23.0 ×2 / 0.23.1 / 0.23.2，共六份前序报告 |
| `MANIFEST-SHA256.txt` | 包内全部文件的 SHA256，用于确认附件未被改动（本文件自身不列入） |

### 作业 id 索引

| job_id | 版本 | 目的 |
|---|---|---|
| `523ad12fdbb84309a31a7132f1b4bcfa` | 诊断构建 | form × DTM 两轴 |
| `12dfb03cdc95424c986dbc4fcb36720f` | 诊断构建 | ADD_CLOSED / RULED |
| `033cd32dbe634b5da16183c4cfbe22ee` | 诊断构建 | 几何项 / incomplete |
| `893500e0d1ad47b0b9796d4e5a76485e` | 诊断构建 | 双提取器对照（关键） |
| `cbab995400184a989529f6be94943551` | 诊断构建 | 12 form 全扫（关键） |
| `948f49e0d85e41d8b6a705d65b8b3644` | 诊断构建 | 补 14 组元素（判据后作废） |
| `93aead46b7794f0a9693f23c5b01bdff` | 诊断构建 | 顺序 + 对照组（判据自检） |
| `654f237ab7bf4850a9f3a55fa70778c1` | **官方 0.23.1** | 现象确认 |
| `be450d6a74bb4868acc1ddd3d897cd63` | **官方 0.23.2** | A/B 落地 + 现象未变 |
| `7d38c7c2b8d14f589fee876e875f9bd7` | **官方 0.23.2** | export 被基线漂移拦住 |

---

## 15. Caveats（必须与结论一起读）

1. **全部结论限于 Creo 10.0.0.0（`release_numeric=42`）**，不外推到 11/12，也不否定作者在 44 上的实测。
2. E1~E7 来自**诊断构建**，只用于定位决定性维度；结论性判断以 E8~E10（官方版本）为准。
3. **"缺哪个必填元素"始终没有被内核告知过**：四次实验里 `element_errors.total` 恒为 0，`ProElemtreeVerify` 不可用，诊断恒空。这是本报告最大的信息缺口，只能靠路线 C（从 44 导出真实树比对）补齐。
4. E6 的负结果**不构成**"补这些元素无效"的结论（判据已自证失效）；`PRO_E_BNBLN_TAN_COND` 的正确形态仍未确定。
5. 第 8.7 节的导入接口只做了**声明层查证**（头文件 + 枚举），报告方未实际调用；`PRO_TK_NO_LICENSE` 是否会在纯曲面 STEP 上触发、`rep_type` 取 master 的实际表现，需要在有授权的环境实测。
6. 球鼻艏**没有**用折线/多段/多截面替代方案交付过任何"看起来像"的结果。按项目约束（不要近似方法），这一项停在"不可用"。
7. 主模型 `frigate_txt_rebuild`（`dd71e35bd0764c9f83bc1c91e7ba3d4b`）在本轮全部实验中**未被改动**：386 features / 1 active body / 体积 5,918,188,879.22325 mm³，`part_sha256 = 7626674ce0dc30d430e9816a54b88e6127d2d56a67b07d004aa72671f0e5e879`。
8. 本包内每一张表都能落到具体回执字段；**唯一不带原始文件的一处**是 E4 里 "29 元素" 这棵树的**元素 ID 明细**——元素总数（`legacy_tree_elements=29`）有回执背书，ID 列表只有会话终端输出。若作者需要该明细，用 job `893500e0…` 的同参数复跑一次即可，本报告不为它单独背书。
