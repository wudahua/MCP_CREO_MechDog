# FEAT-066 B 样条实体实机证据（2026-11-12）

## 环境与身份

- Windows x64，Python 3.12.14，Creo 12.4.0.0（`release_numeric=44`），匹配 Toolkit SDK，单位 mm。
- 用户 2026-11-12 当次确认可做实机测试；本轮未结束或重启 Creo、未清 `toolkit.lock` 或 unknown 保护、未做故障注入、未改用户模型。
- 源码 `HEAD=c6eb7f74839d5a4d24b89116d997b35ba13d898e`，工作树 `dirty=true`。
- worker：`source_digest=722652b527227f7767f421911494161c22e92e0ca84659eed7afce3aba945edb`、`worker_sha256=a6dec2bda6fc3d8fe39a76aa84a85aee060b2a9662a9c2a5761794eaed0b8c06`、`identity_status=verified`。
- `surface_loft` 构建身份：`state=compiled`、`sdk_requirements=[PRO_E_BNBLN_CURVES, PRO_E_BNBLN_1DIR, PRO_E_BNBLN_2DIR, PRO_E_BNBLN_DIR_CURVES, PRO_E_BNBLN_TAN_COND]`、`missing_sdk_requirements=[]`。

## 测试数据

5 个控制点、3 次、clamped 非均匀节点、非有理：

```text
control_points = [(0,0), (10,8), (30,9), (45,2), (50,0)]
degree         = 3
knots          = [0,0,0,0,0.595088181,1,1,1,1]
weights        = [1,1,1,1,1]
```

独立 oracle：用同一 degree/knots/control points 做 de Boor 采样 800 段，弧长
**52.9008906872476 mm**；两截面间距 20 mm 的直纹面积应为 **1058.017813744952 mm²**。

## 命令与结果

### 离线 / 编译

- `bridge.py build` → `build/creo_worker.exe` 成功。
- `tools/dev_check.py --work-item FEAT-066` → `success=true`、`unit_tests=passed`（3429 项）、无新增 lint/格式回归（基线 21 lint / 9 未格式化文件）。
- `tools/check_backlog_counts.py` → `consistent=true`（178 / BUG 77 / FEAT 63 / DEV 38）。
- `tools/test_b_spline.py`（离线）→ 8 项全 PASS。

### 实机：`tools/test_b_spline.py --live --confirm-session-usable`

报告：`build/b_spline/20261112-113339.json`，离线 8 + 实机 12 项全 PASS。

| 项 | 结果 |
| --- | --- |
| 草图作业 | `job 348ea9e0bf264d2097012913b691dba9`，`model 8e384ad19e234927adc13cb439b45318`，revision 1，`succeeded` |
| 保存重载 | `saved_file_reloaded_and_verified=true` |
| 控制点回读 | `measurement=control_points`，最大偏差 **2.6484335973398527e-31 mm** |
| 放样作业 | `job f7c651016cac41c4b98a1af5f72d075b`，`model a42da209f9884b5eb43b477c2052f238`，revision 1，`succeeded` |
| 放样测量 | 面积 **1058.0172783981307 mm²**，独立 oracle **1058.017813744952 mm²**（差 0.000535 mm²，相对 5.1e-7）；`section_count=2`；单张开放 quilt；`has_solid=false` |
| 保存重载 | `saved_file_reloaded_and_verified=true`；重载后面积与首次读数完全相同 |

说明：首次实机运行（`20261112-113247.json`）只有面积 oracle 一项 FAIL，原因是驱动自身的 de Boor 初始下标写错，把弧长算成 80.9 mm（超过控制多边形长度 54.77 mm，几何上不可能）。修正驱动后重跑，产品侧 12 项全 PASS；该失败不是 `b_spline` 或 `surface_loft` 的回归。

### 实机回归：`tools/test_surface_loft_guides.py --live --confirm-session-usable`

报告：`build/surface_loft_guides/20261112-113434.json`，离线 + 实机全 PASS（含三截面 + 2 导线面积 1599.9999999999995 mm²、quilt 开放、保存重载 verified）。门禁从 `Probbl.h` 改为元素 ID 后，既有 `surface_loft` 行为未回归。

## 未验证

- Creo 9 / 10 的编译与运行期元素树再生（本机无对应 SDK；0.21.0 报告的 Creo 10 零补丁编译为报告方实测，未在本机复现）。
- `b_spline` 的 `closed`、`dimensioning="coordinates"`、`update_sketch_geometry` 改写。
- 非 mm 单位、非 XY 平面上的精确面积 oracle（截面本身可建，但本轮未做独立几何断言）。
- WorkBuddy 黑盒。
