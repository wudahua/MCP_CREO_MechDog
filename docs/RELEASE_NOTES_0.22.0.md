# MCP_CREO_MechDog 0.22.0

日期：2026-11-11。类型：MINOR（新增公开参数与输入形态，旧调用行为不变）。公开工具：107（与 0.21.1 相同，无新增工具）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.22.0 交付 [FEAT-065](work-items/FEAT-065.md) 的 M3/M4 两项：`creo_surface_loft` 的截面与导线不再只吃 MCP 自建草图，还可以用模型里已有的曲线和 quilt 边，首末截面可以用收敛点；同一条放样还能在边来源的首/末截面上声明 `tangent`，让补面与相邻面相切。为了让「边作截面」可用，`creo_measure_surface_group` 的回执补上了开放边清单 `open_edge_records`，这是从公开接口拿 quilt 边 ID 的唯一渠道。

M1（2—32 截面）与 M2（2—8 条第二方向导线）已在 0.21.0 发布，本版不改它们的口径；两截面直纹、trim 与加厚路径在最终代码上已实机复跑。

## 本版变化

### M3：截面与导线接受已有几何

- `sections` / `guides` 的每一项除草图标签外，再接受已有曲线 `{kind:'curve',id}` 与 quilt 边 `{kind:'edge',id}`；`sections` 的首末项还可以是收敛点 `{kind:'point',id}` 或单点 `datum_points` 标签。
- 提交前的校验仍按原有顺序执行：截面 2—32 项、导线 2—8 项、重复引用与导线复用截面照旧拒绝；3 截面以上仍要求 `interpolation="smooth"`。
- 回执新增 `section_source_kinds`、`section_geometry_ids`、`section_sources` 与 `guide_*` 同名字段、`convergence_point`，用来说明每一项实际解析成了什么；`unverified_input_forms` 保留但恒为空。

### M4：边界条件（只开放边来源的相切）

- `creo_surface_loft` 新增 `boundary_conditions`，目前只接受首/末截面来源为边时的 `tangent`。
- 实测实现值：`BNBLN_TAN_COND` 的 `TAN_COND_TYPE` = 2，`STRETCH` 首截面 -1、末截面 +1；回执给出 `tan_cond_type`、`stretch` 与只读的 `tan_cond_tree`。
- `curvature`、`normal`、导线边界上的条件在提交前拒绝，并给出实测原因——本轮没有找到有实测依据的取值，不做猜测。
- 实机形状：两张平行竖直曲面带之间补面，自由时为平面；开相切后成拱形，补面 982.5888 mm²，两条接缝 G1 均为 0.0°。

### quilt 边的公开 ID 通道

- `creo_measure_surface_group` 回执新增 `group.open_edge_records`：每条开放边的 ID、所属面与 quilt、长度、两个端点，最多 32 条，并附 `open_edge_records_total`、`open_edge_records_truncated` 与逐项失败计数。单位未知时 mm 值为 null，ID 照常给出。

## 验证

环境：Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可。

会话处置：本轮开始时机器上已有一个 22:42 由用户启动的 Creo 会话，但它未注册到名字服务器——只读探测为 `not_found_or_unreadable`、`toolkit_code=-4`、`name_read_code=0`，实机驱动在 `session_ready` 停止且未提交任何几何。经用户 2026-11-11 当次明确授权后，关闭该会话并按 `creo_startup.launch_creo`（Explorer + `parametric.psf`，工作目录 `build/creo_session`）重启，连接恢复后开始下述回归。未做故障注入、未清 `toolkit.lock` 或 unknown 保护、未结束 nmsd、未改用户模型与历史证据。

- 离线检查：`tools\dev_check.py`（合入后、发布提交前）`success=true`，3413 项单测 0 失败 0 错误；风格无新增（存量 lint 21、未格式化 9，均在 `docs/development/style-baseline.json` 内）。源码指纹 `75d861d7…`，工作区 dirty 仅来自未跟踪的 `.trae/` 与 `reference_parts/`（未提交）。
- 本版新功能（由 FEAT-065 分支在最终代码上完成，见工作卡）：`tools\test_surface_loft_inputs.py --live` 实机 40 项全 PASS；`tools\test_surface_loft_continuity.py --live` 实机 59 项全 PASS。
- 旧驱动在最终代码上的复跑（本轮，用户当次授权）：
  - `tools\test_surface_loft_multisection.py --live --confirm-session-usable`：离线 9 + 实机 21 项全 PASS，报告 `build/surface_loft_multisection/20261111-233717.json`。三截面 job `aab69abd…`（模型 `4297e326…`，rev 1）2101.2524427513217 mm²（分段直纹会是 2000.0）、单张开放 quilt、`section_count=3`、曲线 ID 45/53/61、无实体、保存重载后面积一致；thicken job `be91e9cd…`（rev 2）4202.507981502071 mm³；两截面回归 job `78b15dee…` 800.0 mm²、`piecewise_ruled=true`。
  - `tools\test_surface_loft_guides.py --live --confirm-session-usable`：离线 12 + 实机 22 项全 PASS，报告 `build/surface_loft_guides/20261111-233833.json`。直导线 job `721abe7e…` 800.0 mm²；曲线导线 job `87091137…` 600.0 mm²（包围盒 x 达 44.24 mm）；3 截面 + 2 导线 job `fef6b032…` 1599.9999999999995 mm²、`section_count=3`、`guide_count=2`。
  - `tools\test_surface_loft.py --live --confirm-session-usable`：22 项全 PASS，报告 `build/surface_loft/20261111-234006-0c1b15/report.json`。800.0 mm²、`surface_trim` 两侧各 400.0 mm²、2 mm 加厚 1599.9999999999995 mm³、保存重载 verified。
  - `tools\test_multi_quilt_group.py --live --confirm-session-usable`：45 项中 44 项 PASS，报告 `build/multi_quilt_group/20261111-234225-eebf80/report.json`。唯一 FAIL 是 `group_with_thickened_member_is_refused`：该断言要求「拒绝且没有 job_id」，而 `surface_group_measure` 自 0.19.0（`0947d48` DEV-074 把它并入作业计划）起就是先建作业、再由原生失败，回执因此带 `job_id`/`model_id`。原生错误文本 `surface_group_measure could not visit the group boundary: contour_edge_visit_failed` 与 0.18.4 的实机证据（`docs/validation/feat039-h10-multi-quilt-2026-11-07/live_multi_quilt_report.json`）逐字相同，能力行为未变，**不是本版的回归**；该项断言自 0.19.0 起过时，未在本版改测试语义。同次其余组级读数全部通过：`state=closed`、`open_edges=6`、`boundary_edges=8`、`joined_edges=2`、gap ≈ 0，0.3 mm 与 2 mm 逐片加厚均成功。
  - `tools\test_five_claw_bottle.py --live --confirm-session-usable`：63 项全 PASS、46 个作业，报告 `build/five_claw_bottle/20261112-000424-513355/report.json`。闭合 quilt 7858.298125230911 mm²、0.3/2 mm 加厚与 solidify 体积 56799.99517675038 mm³ 均与解析值一致。

## 未测范围与已知限制

- Creo 9/10：本机无 SDK，未编译、未建模；SDK 缺 `Probbl.h` 时该操作明确不可用。
- 相切只验证了平面相邻面；非平面相邻面（圆柱、曲面）与两端相邻面朝向不同的情形未测。
- `curvature`、`normal` 与导线边界上的连续条件没有实测依据，仍在提交前拒绝。
- 模型里已有实体时 `surface_loft` 一律失败（原生 `has_solid` 看整个模型），是旧限制，本版未改。
- `boundary_conditions` 不在 compact 保护集合内，回执超过 32 KiB 时可能被裁掉。
- `PRO_E_BNBLN_ADV_VIA_CRV`、导线形状的可视化核对、曲线导线 600 mm² 与 799.94 mm² 的关系未核对；非 mm 单位未测。
- 多 quilt 组驱动的一条断言过时（见上），未在本版修测试语义；WorkBuddy 黑盒未执行。
