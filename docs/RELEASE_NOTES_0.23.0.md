# MCP_CREO_MechDog 0.23.0

日期：2026-11-12。类型：MINOR（新增草图实体与可选 NURBS 参数，旧调用行为不变）。公开工具：107（无新增工具）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.23.0 交付两件事：一是 [FEAT-066](work-items/FEAT-066.md) 的精确 NURBS 草图实体 `b_spline`，让 `sketch` / `creo_create_sketch` 能把 TXT 的 `degree`、`control_points`、`knots`、`weights` 原样写进 Creo，而不是像 `spline` 那样只给插值点、由内核拟合；二是 [DEV-082](work-items/DEV-082.md) 的 boundary-blend 门禁修复，`surface_loft` / `surface_boundary_fill` 不再因为 SDK 没有 `Probbl.h` 而整段被剔除。

## 本版变化

### 精确 NURBS 实体 `b_spline`（FEAT-066）

```json
{"type": "b_spline", "name": "side_guide", "degree": 3,
 "control_points": [[0, 0], [10, 8], [30, 9], [45, 2], [50, 0]],
 "knots": [0, 0, 0, 0, 0.595088181, 1, 1, 1, 1],
 "weights": [1, 1, 1, 1, 1]}
```

- 原生映射 SDK `Pro2dBSplinedef`（`PRO_2D_B_SPLINE`）：`degree`、`num_knots`/`params`、`num_c_points`/`c_pnts`、可选 `weights`。
- `knots` 省略时生成 clamped uniform 节点；给出时必须满足 `len(knots) == len(control_points) + degree + 1`、非降、首尾各 `degree+1` 个值相等。节点与权重按原值直传，不做归一化。
- `degree` 默认 3，范围 1—10 且小于控制点数；`weights` 长度等于控制点数且全部大于 0。
- 不支持 `closed`；`dimensioning="coordinates"` 仍只接受 line/centerline/rectangle/polyline/circle/arc，`b_spline` 走 autodim。
- `b_spline` 仅支持创建；`update_sketch_geometry` 不能改写其 degree/knots/weights，需要变更时重建草图。
- 截面分析、坐标回读/偏差、编辑只读探针均识别该类型；`geometry_deviation` 对 `b_spline` 使用 `measurement="control_points"`。

### boundary-blend 门禁改为元素 ID（DEV-082，0.21.0 反馈 P1）

- `native/surface_loft.cpp` / `native/surface_boundary_fill.cpp` 的门禁从 `__has_include(<Probbl.h>)` 改为 `MECHDOG_HAS_BNBLN_TREE`：检查 `ProElemId.h` 的 `PRO_E_BNBLN_CURVES`、`1DIR`、`2DIR`、`DIR_CURVES`、`TAN_COND` 五个元素 ID。
- `Probbl.h` 全文只有注释和 `PRO_E_DTM_SRF_TYPE_BND_BLEND 11`；缺该头时用文档值 11 兜底，不再决定功能可用性。
- worker build-info 的 `sdk_requirements` / `missing_sdk_requirements` 与 `capabilities.py` 的拒绝文案同步改为元素 ID；`surface_loft` 未编译状态为 `bnbln_element_ids_missing`。

## 验证

环境：Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可。

- 离线：`tools\dev_check.py --work-item FEAT-066` → `success=true`，3429 项单测 0 失败 0 错误；风格无新增。`tools\check_backlog_counts.py` → 178 / BUG 77 / FEAT 63 / DEV 38 一致。
- 编译：`bridge.py build` 成功；`surface_loft` build-info 为 `compiled`，五个元素 ID 全在 `sdk_requirements`。
- 实机（用户 2026-11-12 当次授权）`tools\test_b_spline.py --live --confirm-session-usable`：离线 8 + 实机 12 项全 PASS，报告 `build/b_spline/20261112-113339.json`。
  - 草图 job `348ea9e0…`（model `8e384ad1…`，rev 1）成功并保存重载；控制点回读最大偏差 **2.6484335973398527e-31 mm**。
  - 两截面放样 job `f7c65101…`（model `a42da209…`，rev 1）：面积 **1058.0172783981307 mm²**，独立 de Boor oracle **1058.017813744952 mm²**（差 0.000535 mm²，相对 5.1e-7）；`section_count=2`、单张开放 quilt、无实体、重载后面积一致。
- 实机回归 `tools\test_surface_loft_guides.py --live --confirm-session-usable`：全 PASS，报告 `build/surface_loft_guides/20261112-113434.json`（3 截面 + 2 导线 1599.9999999999995 mm²），门禁改动未回归既有放样。
- 证据汇总：[feat066-b-spline-2026-11-12](../validation/feat066-b-spline-2026-11-12/EVIDENCE.md)。

## 未测范围与已知限制

- Creo 9/10：本机无对应 SDK，未编译、未建模；0.21.0 报告的 Creo 10 零补丁编译为报告方实测，未在本机复现。门禁修复后 Creo 10 **运行期**元素树再生仍未验证。
- `b_spline` 的 `closed`、`dimensioning="coordinates"`、`update_sketch_geometry` 改写未开放；autodim 的刚性平移问题留待后续条目。
- 非 mm 单位、非 XY 平面上的精确面积断言未做；WorkBuddy 黑盒未执行。
- 0.22.0 已披露的 `boundary_conditions` compact 裁剪、`ADV_VIA_CRV`、非平面相邻面相切等限制不变。
