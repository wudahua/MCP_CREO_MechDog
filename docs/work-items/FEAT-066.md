# FEAT-066：精确 NURBS 草图实体（b_spline）

## 当前摘要（2026-11-12）

分类：**部分交付 0.23.0**（剩余范围未排期）。类型：功能。优先级：P1。

发布：0.23.0（2026-11-12，标签 `v0.23.0`），见[版本说明](../RELEASE_NOTES_0.23.0.md)与[发布记录](../validation/RELEASE-0.23.0.md)。

来源：

- 2026-11-10 下载目录 `0.20.0` 报告「NURBS 样条精确复现缺失」。
- 2026-11-11 下载目录 `0.21.0` 报告 §8-4「让 `sketch` 支持更细的样条参数（次数、节点、权重）」。
- 原件与映射见 [feedback-0.21.0-2026-11-11](../validation/feedback-0.21.0-2026-11-11/MAPPING.md)。

目标：在现有 `sketch`/`create_sketch` 里新增 `type="b_spline"`，把 TXT 的
`degree`、`control_points`、`knots`、`weights` 原样写入 Creo 草图，避免
`spline` 只能给插值点、由内核拟合导致控制点与节点不可复现。

## 公开契约

```json
{"type": "b_spline", "name": "side_guide", "degree": 3,
 "control_points": [[0, 0], [10, 8], [30, 9], [45, 2], [50, 0]],
 "knots": [0, 0, 0, 0, 0.595088181, 1, 1, 1, 1],
 "weights": [1, 1, 1, 1, 1]}
```

- `degree` 默认 3，1—10，且小于控制点数。
- `knots` 省略时生成 clamped uniform；给出时必须
  `len(knots) == len(control_points) + degree + 1`、非降、首尾各 `degree+1`
  个相等。值原样传给 Creo，不做归一化。
- `weights` 省略时按非有理写出；给出时长度等于控制点数且全部大于 0。
- 不支持 `closed`；需要闭合请用 `spline` 的 `closed=true`。
- `dimensioning="coordinates"` 仍不接受 `b_spline`，走 autodim。
- 创建后可被 `surface_loft` 作为截面/导线消费；`update_sketch_geometry`
  不能改写其 degree/knots/weights，需要变更时重建草图。

## 实现

- 源码：[schema.py](../../src/creo_mechdog/schema.py) 新增 `BSpline` 与
  `clamped_knots()`，并入 `Entity` 判别联合；[profile_checks.py](../../src/creo_mechdog/profile_checks.py)
  按 clamped 端点参与闭合预检。
- 原生：`native/generic.cpp` 创建与替换两条实体写入循环都映射
  `Pro2dBSplinedef`（`PRO_2D_B_SPLINE`）；截面轮廓分析、`sketch_coordinates.cpp`
  回读/偏差、`sketch_edit.cpp` 只读探针均识别该类型。
- SDK 依据：`Pro2dEntdef.h` 的 `Pro2dBSplinedef` 字段
  `degree`/`num_knots`/`params`/`num_c_points`/`c_pnts`/`weights`。
- 文档：[REFERENCE_SYNTAX.md](../REFERENCE_SYNTAX.md) 新增「精确 NURBS 草图实体」。

## 验证记录

### 离线与编译（2026-11-12）

- `tests/unit/test_b_spline_schema.py` 16 项：默认/显式节点、节点数量、clamped、
  非降、权重数量与正值、degree 边界、bool 拒绝、closed 拒绝、联合判别、
  coordinates 拒绝、闭合预检。
- `tests/unit/test_b_spline_native_contract.py`：写入器、截面分析、坐标回读与
  偏差、编辑探针的静态契约。
- `bridge.py build` 成功产出 `build/creo_worker.exe`。
- 全量 `python -m unittest discover -s tests`：`Ran 3429 tests ... OK`。

### Creo 12.4 实机（2026-11-12，用户当次授权）

报告 `build/b_spline/20261112-113339.json`，离线 8 + 实机 12 项全 PASS：

- 草图 `job 348ea9e0…`（`model 8e384ad1…`，revision 1）成功并保存重载；
  `geometry_deviation.measurement=control_points`，最大偏差
  **2.6484335973398527e-31 mm**，即 degree/knots/控制点在 Creo 内原样保留。
- 两截面放样 `job f7c65101…`（`model a42da209…`，revision 1）：面积
  **1058.0172783981307 mm²**，与同一 degree/knots/控制点的独立 de Boor
  arc-length oracle **1058.017813744952 mm²** 相差 0.000535 mm²（相对
  5.1e-7）；`section_count=2`、单张开放 quilt、无实体、保存重载后面积一致。
- `tools/test_surface_loft_guides.py --live --confirm-session-usable` 全 PASS，
  门禁改动未回归既有放样。
- 首次实机运行的面积 oracle FAIL 是驱动 de Boor 下标错误（弧长 80.9 mm 超过
  控制多边形 54.77 mm），修正驱动后重跑；非产品回归。详见
  [EVIDENCE](../validation/feat066-b-spline-2026-11-12/EVIDENCE.md)。

## 未开放 / 未验证

- `closed`（周期 B 样条）不支持。
- `dimensioning="coordinates"` 不支持 `b_spline`；autodim 的刚性平移问题
  留待后续条目。
- 页面编辑不支持改写 `b_spline`。
- Creo 10 运行期未验证；本机无 Creo 10 SDK。
