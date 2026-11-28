# MCP_CREO_MechDog 0.48.3 验收问题汇总

## 0. 验收环境与版本口径

- 日期：2026-11-28
- 实际运行版本：**0.48.3**
  - `creo_session_status.server_version = 0.48.3`
  - `creo_capabilities.version = 0.48.3`
  - `creo_session_status.toolkit_code = 0`，`connected = true`
- 服务公告：`creo_capabilities.update.status = update_available`，`latest_version = 0.48.4`。
  **0.48.4 本轮未安装、未实测，本文所有结论只针对 0.48.3。**
- CAD：Creo Parametric 10.0.0.0，`release_numeric = 42`，单位 mm。
- 验收方式：只通过 MCP 新建临时托管零件做最小算例；没有引用工作空间外模型输入，没有导入实体。
- 总体结论：
  - 上一轮重点问题中的 `draft` flip 语义、capability 把不可调用 operation 混入 `registered_operations`，在 0.48.3 已明显改善。
  - `extrude add` 静默抹实体、bbox 含刀具包络、`dimensioning:auto` 挪圆心，本轮最小回归未复现。
  - **但仍有 3 类需要作者处理的问题**：新增的端点焊接参数实际空转；`surface_loft` 在 Creo 10 仍开箱不可用；`creo_new_loft_part` 声明支持 2–20 段而实际种子只到 6 段，且不能向已有零件追加放样。

---

## 1. P1：新增的 `endpoint_policy:"weld"` / `weld_pairs` 基本空转，真正能用的只有 `snap_endpoints`

### 1.1 复现

回归件仍是历史文件 `scripts/gear10.json`（40 段圆弧、10 个近闭合轮廓，最大端点簇扩散 `8.21534268e-07 mm`）。

| 调用方式 | 作业 | 结果 |
|---|---|---|
| 默认（原 `v0451_gear10_plan.json`） | `b09f6b46f80548d1bb7584e24461ecf4` | 失败：`ProFeatureWithoptionsCreate=-1`；10 contours / 40 entities / 0 open ends，但端点簇扩散 `8.21534268e-07 mm` |
| `endpoint_policy:"weld"`, `snap_endpoints:false`, `max_endpoint_move_mm:0.01` | 由服务端内部拒绝后改为下列显式对测试 | — |
| `endpoint_policy:"weld"`, `snap_endpoints:false`, 显式 20 对 `weld_pairs` | `f407d36c9e60470891f2c64660e9d576` | 仍失败；`candidate_pairs=0`、`accepted_pairs=0`、`welded_pairs=0`、`refused_pairs=0`、`applied=false`，且无任何失败原因 |
| `endpoint_policy:"weld"`, `snap_endpoints:true`, `max_endpoint_move_mm:0.01` | `b61a2da251584e44b67b01e76c5d976c` | **成功**；V=`184.9802956051309 mm³`，保存重载通过 |
| 调用方预先吸附的 `gear10_snapped.json` | `0459184eba324b87bd2199692e619904` | 成功；V=`184.9802853252888 mm³` |

成功作业的收据细节：

```json
"endpoint_weld": {
  "policy": "weld",
  "applied": true,
  "applied_by": "python_request_rewrite",
  "native_applied": false,
  "candidate_pairs": 40,
  "accepted_pairs": 0,
  "welded_pairs": 0,
  "refused_pairs": 40,
  "snap": {
    "applied": true,
    "rule": "arc_intersection",
    "applied_pair_count": 20,
    "max_shift_mm": 8.564314460318268e-07,
    "residual_max_mm": 0.0
  }
}
"endpoint_weld_native": {
  "applied": false,
  "applied_pairs": 0,
  "max_move_mm": 0.0
}
```

### 1.2 问题

1. **`endpoint_policy:"weld"` 本身没有焊接这 20 对近容差圆弧端点。**它给出 `accepted_pairs=0`，随后仍把未焊接的截面交给 `extrude`，结果失败。真正把几何修好的是 `snap_endpoints:true`，即 Python 侧改写请求坐标，而不是 weld 策略或内核焊接。
2. **`weld_pairs` 作为公开输入字段是空转的。**我按收据自身输出的 pair 形状（`entity_a`/`entity_b`/`end_a`/`end_b`）显式传了 20 对，服务端收据仍是 `candidate_pairs=0`、`applied=false`。检查随版本附带的源码 `src/creo_mechdog/endpoint_welding.py:995` 可见：

   ```python
   operation["weld_pairs"] = receipt.get("weld_plan") or []
   ```

   即 `weld_pairs` 是**服务端输出字段**，但 public schema 把它暴露成可写输入；调用方传什么都会被覆盖，而且覆盖发生在 admission 之后，不会提示“你的 weld_pairs 被忽略”。
3. **收据字段互相矛盾。**顶层 `endpoint_weld.applied=true`，但 `endpoint_weld_native.applied=false`、`applied_pairs=0`；如果不读 `applied_by`，很容易误判为内核已焊接。

这仍属于长期反馈的“能诊断、不能原生焊接，只能靠调用方/服务端脚本预吸附”的问题，只是这次换了新参数名。

### 1.3 影响与建议

- 影响：按字段名直觉选择 `endpoint_policy:"weld"` 的用户会得到失败作业；即使显式给出 `weld_pairs`，也不会生效且没有诊断。
- 建议：
  1. 把 `weld_pairs` 从 public 输入 schema 中移除，或明确标记为 `output_only` / `ignored_on_input`，并在收到非空输入时直接报错说明会被覆盖。
  2. `endpoint_policy:"weld"` 若无法把 `8.2e-07 mm` 级圆弧端点交给内核焊接，应在提交前给出明确拒绝信息，并在错误里直接告诉用户改用 `snap_endpoints:true`。
  3. 统一顶层 `applied` 与 `endpoint_weld_native.applied` 的口径，例如增加 `effective_method="python_request_rewrite"`，不要让两者同时看起来像成功/失败。
  4. 建议把 `EXACT_TOLERANCE_MM=1e-09` 与诊断聚类阈值 `1e-04` 的差距写进工具说明，否则用户无法理解为什么“看起来闭合、诊断可焊、weld 却一对都不接受”。

---

## 2. P1：`surface_loft` 在 Creo 10 上仍无开箱可用路径，`accept_unverified_completion` 也救不了

### 2.1 实测

新建零件 `71c8ab98d5a64369acdfd6e127c4bc11`，两个 XY 开直线草图 `sl_a` / `sl_b`（`(0,0)→(10,0)`，z=0 与 z=10；作业 `c9e1b8df1db34248b3dcc6db8ce7b53b`）。

调用：

```json
{
  "creation_route": "element_tree",
  "sections": ["sl_a", "sl_b"],
  "interpolation": "straight",
  "accept_unverified_completion": true
}
```

作业 `61e70694d20546e59db72a38debb1eaa` 失败，消息原文关键段：

> `surface_loft created the blend (create_code=0) but this Creo release refused its element tree (code -18), the redefine with the creation tree failed (code -1) and regeneration left feature_incomplete=true (SURFACE_LOFT_ACCEPT_INCOMPLETE); the retained feature owns no geometry and the job was rolled back; use the resident_panel route on this release`

- `rollback_status = succeeded`，没有留下曲面。
- 另一条 `resident_panel` 路径仍要求人工注册并启动 `blend_callback_protk.dat`；`creo_callback_status` 当前 `readiness=not_loaded`、`reason=recorded_application_not_active`。

### 2.2 问题与建议

0.48.3 的优点是 capability 已新增 `runtime_admission`、`runtime_ready=false`，不再只在 compact 页面显示 `enabled=true`。但工具本身仍不能在 Creo 10 上创建任何曲面：element_tree 被 `ProFeatureElemtreeExtract=-18` 卡死，resident_panel 需要手工 GUI 注册，而 `accept_unverified_completion` 在本机也明确保证不了可用特征。

建议：

1. 在 `creo_surface_loft` 的 before-job 准入里，若检测到 Creo 10 且 callback 未 ready，直接拒绝并给出两条可行路径，而不是占一个 native job 通道后回滚。
2. 为曲面放样提供类似 `creo_new_loft_part` 的 callback-free seed 路径；否则在能力页把 `surface_loft` 的 `enabled` 改成 `implemented_but_unavailable_on_this_release`。
3. 工具说明中对 `accept_unverified_completion` 的警告应置顶：当前文案虽然写了 Creo 10 仍失败，但 compact capability 页仍容易让客户端误判可用。

---

## 3. P2：无回调放样路径 `creo_new_loft_part` 可用，但段数声明与实际能力不符，且不能改已有零件

### 3.1 通过的部分

用两个矩形截面（z=0 的 10×10，z=10 的 6×6，straight）调用 `creo_new_loft_part`，作业 `7c875451b67844c7acebdcc6977bf5f7` 成功：

- V = `653.3333333333331 mm³`
- 解析圆台体积 `10/3 × (100 + 36 + √(100×36)) = 653.3333... mm³`，完全吻合
- bbox = `[-5,5]×[-5,5]×[0,10]`，保存重载验证通过
- seed：`two_straight`，SHA256 `7d2dbeb4f3bea4839b6501e311105753bfc752a0033f72039f8230b6aa61f5f2`
- 不需要 resident callback。这是相对 0.45.1 的实质进步。

### 3.2 问题 A：声明 2–20 段，实际只到 6 段

工具说明写 `sections must contain 2 to 20 sketch ops`，schema 也是 `maxItems:20`。但 `creo_list_seeds` 只提供 2/3/4/5/6 段种子（straight 与 smooth 各一套，共 9 个）。

提交 7 段 straight 时被 before-job 拒绝：

> `No verified local seed matches 7 sections/straight. Installed choices: two_straight (2/straight), two_smooth (2/smooth), five_smooth (5/smooth), three_straight (3/straight), three_smooth (3/smooth), four_straight (4/straight), four_smooth (4/smooth), six_straight (6/straight), six_smooth (6/smooth). Use creo_install_seed_library or supply an explicit compatible seed.`

即 7–20 段是“工具接受参数但一定调用不了”的区间。建议把 schema 上限改为 `maxItems:6`，或在说明首句明示“默认种子只覆盖 2–6 段，7 段以上必须自带兼容 seed”。

### 3.3 问题 B：只能新建零件，不能给已有零件追加放样

直接 `creo_loft` 在本次会话仍被 before-job 拒绝：

```json
{
  "error": "BLEND_CALLBACK_SETUP_REQUIRED (before-job preflight)",
  "readiness": "not_loaded",
  "reason": "recorded_application_not_active",
  "callback_free_route": "creo_new_loft_part"
}
```

而 `creo_new_loft_part` 只创建新零件。也就是说，“已有零件上追加原生 Blend”这条常见需求在 callback 未启动时仍完全无路可走；文档虽然写了 callback_free_route，但没有说明它只能新建。建议在 `BLEND_CALLBACK_SETUP_REQUIRED` 的 `callback_free_route` 里加 `scope: new_part_only`，避免用户以为可以直接替换现有调用。

---

## 4. 本轮回归通过 / 已修复项

| 项目 | 证据 | 实测 |
|---|---|---|
| `draft` flip 语义与 `material_effect` | `c8d98400a3824d50a862ab2f7ca2f97f` | 圆柱凸台 + XY 基准面 +5°：`flip=false` 体积 `56.5486677646 → 59.9110369070`，`material_delta=+3.3623691424`，`material_effect="added"`。工具说明现已明确写出 datum_plane 与 solid face 两种中性面的相反行为，并新增 `material_effect` 字段。**上一轮 P1 已修复。** |
| `extrude add` 静默抹实体 | `7706cd1d3c4a4feca8cbfa74cbd7c09d` | 10×10×5 实体重复 add：V 500 → 500，`material_delta=0`，`material_effect="unchanged"`，两次 `add_volume_check.status=passed`。`known_limitations` 也已把 `add_volume_check` 写成一等约束。 |
| bbox 包含刀具/草图包络 | `7c875451b67844c7acebdcc6977bf5f7`、`7706cd1d3c4a4feca8cbfa74cbd7c09d` | 放样 bbox 精确为 `[-5,5]×[-5,5]×[0,10]`；方块 bbox `[0,10]²×[0,5]`，`bounding_box_source=solid_face_tessellation`。未复现 v0.44.0 问题。 |
| `dimensioning:auto` 挪圆心 | `7f4839fa6c7640449e16298261b9d977` | 圆 `(0,-0.092)` R3 拉伸 2 mm，重心 y=`-0.09200000000000001`，未挪动。 |
| capability 混淆 registered_operations | `creo_capabilities(compact)` | 新增 `registered_but_unavailable_operations` 与 `operations_note`，明确 operations 才是当前可调用集合。**上一轮 P5 已改善**；但 `unavailable_tools` / `unavailable_operations` 旧字段仍并存，建议后续版本统一。 |
| 工具面规模 | `creo_server_info` / `creo_capabilities` | `tool_count=112`、`enabled_tool_count=112`。 |
| 会话歧义 / startup -4 | `creo_session_status` | 本轮多作业连续运行，`toolkit_code=0`，未触发 -36 或 startup -4。 |

---

## 5. 建议优先级

1. **高**：修正 `endpoint_policy:"weld"` / `weld_pairs` 的输入输出口径；当前字段可用但无效，是最容易误导自动化脚本的新增能力。
2. **高**：让 `surface_loft` 在 Creo 10 上至少有一条不依赖手工注册 callback 的可用路径；否则 compact 页不要显示 `enabled=true`。
3. **中**：把 `creo_new_loft_part` 的段数上限从 20 收敛到实际种子能力 6，并在 `callback_free_route` 中标注 `new_part_only`。
4. **中**：统一 `endpoint_weld.applied` 与 `endpoint_weld_native.applied` 的语义，增加 `effective_method`。
5. **低**：清理 `unavailable_tools` / `unavailable_operations` / `registered_but_unavailable_operations` 三套并列字段。

---

## 6. 附：本轮主要作业 ID

- `b09f6b46f80548d1bb7584e24461ecf4` — gear10 默认焊接策略，失败
- `f407d36c9e60470891f2c64660e9d576` — gear10 显式 weld_pairs，失败
- `b61a2da251584e44b67b01e76c5d976c` — gear10 snap_endpoints，成功
- `0459184eba324b87bd2199692e619904` — gear10 调用方预吸附对照，成功
- `c8d98400a3824d50a862ab2f7ca2f97f` — draft flip 回归
- `7706cd1d3c4a4feca8cbfa74cbd7c09d` — add_volume_check 回归
- `7f4839fa6c7640449e16298261b9d977` — auto dimensioning 回归
- `7c875451b67844c7acebdcc6977bf5f7` — creo_new_loft_part 成功
- `61e70694d20546e59db72a38debb1eaa` — surface_loft element_tree 失败
