# MCP_CREO_MechDog 问题反馈（Creo 9.0.0.0 / MCP 0.47.0）

- 反馈日期：2026-11-26
- MCP 版本：**0.47.0**（`creo_server_info.version`，公开工具 112，`server_name=MCP_CREO_MechDog`）
- 目标 CAD：Creo 9.0.0.0（`release_numeric = 41`，`parametric.exe` + `xtop.exe`）
- 验收对象：2026-11-23 由 MCP 0.39.0 重建的「直列四缸发动机曲柄活塞机构」= 6 个零件 + 1 个 29 实例装配体
- 验收方式：**全程黑盒、只读为主**，用 0.47.0 重新打开历史模型、对每个模型 `creo_refresh_model` 取 live 测量，对照 TXT v1.7 的权威基准；另建一个临时圆柱件复现上轮头号阻断。
- 核心结论：**几何成果完好，上轮 9 项反馈大部分已修且在 Creo 9 上生效；但新能力存在一个"增量升级死角"——新验收字段对历史模型不可见，恰恰让最需要它的"复核旧模型"场景失效。**

---

## 1.（核心问题）新增的验收字段只写入"新版本保存过"的快照，历史模型读不到

**严重度：高。这是 0.41.0 号称"补齐面积/包围盒缺口"后仍留下的死角，直接卡住"升级后复核既有模型"这一最常见的验收场景。**

### 现象（可复现）

对 0.39.0 时代保存的 P01 活塞（`p01_piston.prt.6`，快照时间 2026-11-23T15:29:07）：

| 步骤 | 调用 | 结果 |
|---|---|---|
| ① 直接读 | `creo_inspect_model(p01, detail="compact")` | `inspection` 里**没有** `total_surface_area_mm2` / `bounding_box_mm` / `merged_counts` |
| ② 实时测 | `creo_refresh_model(p01)` → job `d049c305…` → `creo_get_job(detail="full")` | `result.inspection_summary` **有**全部新字段：`total_surface_area_mm2=58171.597`、`bounding_box_mm.size=[85,95,85]`、`merged_counts={surfaces:29,edges:94,...}` |
| ③ 再读 | 再次 `creo_inspect_model(p01, detail="full", section="surfaces")` | 仍读回 **2026-11-23 的旧快照**，`inspection` 依旧无新字段；`surfaces[]` 每条只有 `bbox/radius/axis/origin/type`，**没有 0.41.0 承诺的 `area_mm2`** |

对照实验：用 0.47.0 新建并保存的测试件 `verify_fullcircle_c9`（revision 3），`creo_inspect_model(detail="full", section="surfaces")` 里 `total_surface_area_mm2=7430.172`、`bounding_box_mm`、`merged_counts` 和每条 `surfaces[].area_mm2` **全部齐备**。

### 根因判断

- 0.41.0 把新字段写进了 `inspection()` 的**快照生成路径**，而不是**读取路径**。快照是"保存时冻结"的：旧版 `.prt` 被 0.39.0 保存后，其 `snapshot` 里根本没有这些键。
- `creo_refresh_model` 被明确定义为 `readonly=true`，它把 live 测量结果只写进 job 的 `inspection-verified-*.json`，**不回写模型快照**（回读的 `last_query_at` 更新了，`snapshot.at` 和 `snapshot.source=saved_verified` 没变）。
- 工具说明里写的是"Query refresh_model for a new live bounding box **or save_model to update the saved snapshot**"——也就是说，唯一能让 `creo_inspect_model` 看到新字段的办法是**再保存一次模型**（升 revision、改文件哈希）。对"只想复核、不想改动成果"的验收场景，这是不可接受的副作用。

### 影响

- TXT 把面积列为**硬闸**：「P01 面积闸 A 落在 58171.1 ±1%」「P04 方向闸 A 落在 20317.9 ±1%，**V 不是充分判据**」。这些正是本次要复核的旧模型。
- 使用者打开旧模型、用最自然的 `creo_inspect_model` 入口，**看不到面积**，很容易得出"这个版本根本没做面积功能"的错误结论（我一开始就是这样）。
- 唯一绕行路径是 `refresh_model → get_job(detail="full") → result.inspection_summary`，这条路径**不在 `creo_inspect_model` 的说明里**，且每个模型要起一次 live job（约 8–15 s + 连接开销），无法在一次 inspect 里批量读完。

### 建议

1. 让 `creo_inspect_model` 支持 `live=true`（或 `refresh=true`）：只读触发一次 live `inspection()` 并把新字段并入返回，**不改快照、不升 revision、不改文件**。这是验收场景的刚需。
2. 或让 `creo_refresh_model` 支持 `write_back_snapshot=true`（默认 false）：把 live 测量补进快照的新字段，但保持 `revision` 和几何字节不变（元数据级更新）。
3. 或提供 `creo_migrate_snapshot`：批量为存量模型补齐 0.41.0+ 的新字段，不触碰 `.prt`。
4. 最低限度：在 `creo_inspect_model` 的说明里明确写"旧版保存的模型快照不含新字段；需 `save_model` 或走 `refresh_model → get_job(full)`"，并在 `detail=compact` 返回里加一个 `snapshot_schema_version` 或 `stale_fields` 提示。

---

## 2.（验收发现，非 MCP 缺陷）面积闸首次可用，即检出 P04 连杆盖超出 TXT 硬闸

0.39.0 时代没有面积工具，这个偏差一直无法发现；0.47.0 补上面积后立刻暴露：

| 零件 | A 实测 (mm²) | TXT 硬闸 | 偏差 | 判定 |
|---|---|---|---|---|
| P04 连杆盖 | **20535.512** | 20317.9 ±1%（上界 20521.18） | **+1.07%** | **超闸** |
| P01 活塞 | 58171.597 | 58171.1 ±1% | +0.0009% | 通过 |

P04 的 V 偏差仅 −0.054%、包围盒 90×60×38 全等、重心 x=−0.1723（TXT −0.153±0.03）——**四项里三项通过，唯独面积超闸**。这正好印证了 TXT 反复强调的"V 不是充分判据"。这项归为**既有模型的几何问题**（P04 凸台/孔细节），不是 0.47.0 的 bug，但说明新面积闸确有价值、且应纳入常规验收。

---

## 3.（口径问题，建议文档说明）装配包围盒与 TXT"紧包络"相差约 11 mm / 7 mm

- 0.47.0 实测装配 `bounding_box_mm.size = [589.0, 391.196, 392.526]`
  - min `[-638.173, 68.707, -299.449]`，max `[-49.173, 459.902, 93.077]`
- TXT v1.7：保守上界 `589.0 × 405.4 × 403.2`，紧包络 `589.0 × 402.4 × 399.8`
- X 完全一致（589.0，曲轴总长）；**Y 比紧包络小 11.2 mm，Z 小 7.27 mm**。

### 分析

MCP 的 `bounding_box_source=solid_face_tessellation`、`state=measured`、`error_bound_direction=inward`、`method_error_bound_mm=0.001`——0.001 mm 的误差界解释不了 11 mm 的差。真实原因是**口径不同**：

- TXT 的"紧包络"= 各件实几何点云按 29 条变换采样后求并集；"保守上界"= 各件 BodyBox 的 8 角点合成。
- MCP 的装配包围盒 = 对装配内实体面做 tessellation 后的并集，是"实际渲染几何"的 inward 近似。
- 两者本就不必相等；而且本次差 11 mm 也可能含有上次装配变换与 TXT 29 条变换的细节差异。

### 建议

在 `bounding_box_mm` 旁补一个 `basis` 字段（`tessellated_solid_union` / `component_bodybox_corners` / `point_cloud_union`），并在 `creo_inspect_model` 文档里给出与 CAD 软件 `BodyBox` 口径的换算说明，避免用户拿"紧包络"直接判定 MCP 测量错误。

---

## 4.（小问题集合）

| # | 问题 | 复现 | 建议 |
|---|---|---|---|
| 4.1 | `bounding_box_status.query_code` 恒为 `null`（即使 `state="measured"`） | 7 个模型的 live 测量全部如此 | 填入 `ProSolidOutlineGet` 的真实返回码，或说明该字段保留 |
| 4.2 | `geometry_selector` 的 `tolerance_mm` 虽在 describe 里说明必填，但首次调用易漏 | 本次 `creo_round` 首次不带该字段被拒，提示信息被截断在 `...split full circl` | 在 `creo_round`/`creo_chamfer` 的 `references` 字段描述里给出含 `tolerance_mm` 的完整可复制示例 |
| 4.3 | `creo_get_job(detail="compact")` 默认省略 `inspection_summary` | refresh 后用 compact 轮询拿不到面积 | 增加 `sections=["inspection_summary"]` 的显式支持，或在 compact 里保留核心新字段 |
| 4.4 | `creo_session_status` 的 `session_health.status=unknown`（`no_recent_verified_save`），但同一次调用 `connected=true` 且 live 探针刚通过 | 本次会话快照里 `recorded session identity` 超过 600 s freshness 窗口 | 属预期保守策略，但建议把"连接健康"与"保存健康"分成两个独立字段，避免误读为连接不可靠 |

---

## 5. 上轮（0.39.0）9 项反馈的修复核对

| 上轮问题 | 0.47.0 状态 | 本次 Creo 9 实测 |
|---|---|---|
| ①整圆边选择器无法唯一命中 | 0.41.0 加 `full_circle:true` / 接缝点消歧 / 单点选弧（BUG-176） | **通过**：R20×40 圆柱顶圆边 `full_circle:true` 做 R2，V 50265.482→50160.021、`matched_ids=[55,56], same_circle=true`，与作者 Creo 10 数字逐位一致 |
| ②多集 round 失败不定位 | 0.41.0 加 `failed_reference_index`（FEAT-079） | 未在本次触发失败；发布说明记为 Creo 10 已验、Creo 9 未验 |
| ③无面积/包围盒 | 0.41.0 加 `total_surface_area_mm2`/`bounding_box_mm`（FEAT-078） | **部分通过**：新建模型可读（见 §1），**历史模型读不到**（核心问题）；逐面 `area_mm2` 同样只对新建模型可见 |
| ④面/边计数跨内核不可比 | 0.41.0 加 `merged_counts` | **通过**：P03 由 6 面 12 边合并为 4 面 8 边（源件 4 面）；P01 38/116 → 29/94；首次可与 SolidWorks 口径对照 |
| ⑤草图容差/spline 面积/优弧 | 0.41.0 加 `sweep_deg`、spline 数值面积、`shifted_sample`（BUG-177） | 未在本次重建；文档核对无误 |
| ⑥基准面 (u,v)/法线文档 | 0.41.0 补对照表（BUG-177） | **通过**：本次圆柱草图回读 `XY normal=[0,0,1], u=[1,0,0], v=[0,1,0]` 与文档一致 |
| ⑦feature_state 依赖手工穷举 | 0.41.0 加 `include_dependencies` / `suggested_targets`（BUG-178） | 未在本次触发；文档核对无误 |
| ⑧装配插入扰动无关实例 | 0.41.0 加 1e-12 容差（BUG-178） | 本次上色 + 多次 refresh 均未出现无关 `moved` 回执 |
| ⑨空装配无法建 | 0.41.0 明确指引 | 未在本次触发；文档核对无误 |

> 值得肯定：`full_circle` 这个上轮的**头号硬阻断**，作者修得干净——在 Creo 9 上一次成功、数字与 Creo 10 逐位一致，并带 `geometry_selector_resolution` 诊断。§1 的问题是"修复的可见性"，不是"修复本身"。

---

## 6. 成果验收结论（0.47.0 复核，几何全部保留）

| 零件 | V 实测 | V 基准(TXT) | ΔV | A 实测 | 重心 | 包围盒(mm) | merged 面/边 |
|---|---|---|---|---|---|---|---|
| P01 活塞 | 155836.183 | 155790.0 | +0.0296% | 58171.597 ✓ | (0,23.663,0) | 85×95×85 | 29/94 |
| P02 曲轴 | 3221838.491 | 3221710 | +0.0040% | 352028.184 | (340.011,0,0) | 589×160×144 | 105/218 |
| P03 活塞环 | 3323.177 | 3323.18 | −0.0001% | 3761.115 | (0,2.15,0) | 85×4.3×85 | 4/8 |
| P04 连杆盖 | 120952.351 | 121018.0 | −0.0542% | **20535.512 超闸** | (−0.172,−35.184,19) | 90×60×38 | 16/46 |
| P05 活塞销 | 73168.175 | 73168.2 | −0.00003% | 10242.560 | (0,0,41) | 33.8×33.8×82 | 7/10 |
| P06 连杆 | 125197.655 | 128842.0 | −2.83%※ | 38102.959 | (0,91.958,19) | 90×223.7×38 | 35/109 |
| 装配 29 实例 | 5162334.064 | 5162334.065 | −0.0000002% | 905372.068 | (−303.05,213.26,−123.77) | 见 §3 | — |

> ※ P06 的 −2.83% 含 TXT 自身登记的 D056 不闭合，以及上轮"10 处 R3 只做出 4 处"的既有缺口；与本次 0.47.0 升级无关。

- 7 个模型（6 件 + 装配）在 0.47.0 下全部 `status=ready`、`healthy=true`、`has_solid=true`，`refresh_model` 全部 succeeded，无需恢复。
- 装配体彩色外观（6 类零件配色）在多次 refresh 后仍保留，几何哈希与 2026-11-24 上色完成时一致。

---

## 7. 给作者的一句话总结

> 修复本身到位（`full_circle` 在 Creo 9 上实测通过，`merged_counts` 让拓扑首次可比），但**新验收字段被绑死在"保存时生成快照"这条路径上**，历史模型读不到——请给 `creo_inspect_model` 或 `creo_refresh_model` 加一条"只读补字段/回写字段但不升 revision"的路，否则"升级 MCP 后复核旧模型"这一核心用途始终走不通。
