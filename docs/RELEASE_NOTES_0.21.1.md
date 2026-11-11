# MCP_CREO_MechDog 0.21.1

日期：2026-11-11。类型：PATCH。公开工具：107（与 0.21.0 相同，无新增工具、无新增参数）。源码版本以 [version.py](../version.py) 为准。

## 概览

0.21.1 修复 [BUG-118](work-items/BUG-118.md)：compact 视图在超预算时会把曲面放样回执裁成只剩 `detail_truncated`，3 截面以上的导线放样因此在轮询里看不到面积、闭合状态和导线计数。同批把 0.21.0 遗留的「3 截面 + 导线」实机用例跑通，并回填 0.21.0 的发布记录。

## 本版变化

### BUG-118 compact 预算裁剪不再丢测量值

- 新增 `OUTCOME_OPERATION_KEYS` 并入 `enforce_compact_budget` 的保护集合：`quilt_id`/`quilt_ids`/`quilt_count`/`quilt_closed_native`/`has_solid`/`surface_area_mm2`/`surface_area_status`/`section_count`/`section_curve_ids`/`guide_count`/`guide_curve_ids`/`piecewise_ruled`/`interpolation`/`volume_mm3`/`curve_id`/`length_mm`/`surface_id`。
- 被裁掉的仍是大块：`profile`、`surface_group`、`native_section` 等；预算上限不变（`RESPONSE_BUDGET` 32 KiB），保护证据本身超预算时依旧用 `result_budget` 如实报告。
- 回归用例 `tests/unit/test_large_plan_result_budget.py::test_a_trimmed_surface_receipt_keeps_its_measurements` 锁定该行为。

### 0.21.0 遗留项的收尾

- `tools/test_surface_loft_guides.py` 的 3 截面 + 2 导线用例由「compact 回执为空导致 2 项 FAIL」变为全 PASS；0.21.0 版本说明里「驱动 3 截面用例未复跑」的已知限制由此关闭。
- [0.21.0 发布记录](validation/RELEASE-0.21.0.md) 与发布后核对段回填，`docs/BACKLOG.md` 的 FEAT-065 行标注随 0.21.0 交付。

## 验证

环境：Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可。实机执行经用户 2026-11-11 当次明确确认（用户重启 Creo 后执行）；未结束或重启 Creo/nmsd、未清 `toolkit.lock` 或 unknown 保护、未做故障注入、未改用户模型与历史证据。

- 实机驱动 `tools\test_surface_loft_guides.py --live --confirm-session-usable`：离线 12 项 + 实机 22 项全 PASS（报告 `build/surface_loft_guides/20261111-135731.json`）。
  - 直导线 job `baad63b6ceef414cbbd0a4c03e0ee254`：800.0 mm²、bbox x 止 40.0 mm、`guide_count=2`、保存重载 verified。
  - 曲线导线 job `e2646c3a789d454db601069184838b7b`：600.0 mm²、bbox x 达 44.24 mm。
  - 3 截面 + 2 导线 job `2a2ee086273b40bc81a5edab6b1f01a5`：`section_count=3`、`guide_count=2`、面积 1599.9999999999995 mm²、单张开放 quilt、无实体、bbox 40.12/40.12 mm、保存重载 verified——修复前同一几何的 compact 回执只剩 `detail_truncated`（job `6510998c…`）。
- 缺陷复现与定位：同一 manifest 的 compact/full 对比，full 分页含全部测量值，compact 仅 `detail_truncated=true`。
- 全量单元测试：`Ran 3314 tests ... OK`（工作树，含新增用例）。
- 种子包确定性构建多次一致并回填 `docs/seed_package.json`；源码包与种子包各自生成 `.zip.sha256` sidecar；提交号、受测源码指纹与两个包的 SHA256 见 Release 正文与[发布记录](validation/RELEASE-0.21.1.md)。

## 未测范围与已知限制

- 只验证了 `surface_loft` 的记录形态；其他同样不在保护集合内、又可能被整体剥掉的 op 类型未逐项核对。
- 预算边界未重测；保护标量后单条放样记录大约多出 200—400 字节，未做长计划下的极端预算压测。
- 曲线导线曲面**形状仍未在 GUI 或等价可视化中核对**；600.0 mm² 与直纹基线 800.0 mm² 的差异仍无几何解释。
- `PRO_E_BNBLN_ADV_VIA_CRV`、`PRO_E_CTRL_PTS`/`PRO_E_BLEND_TYPE`、G1/G2、端点收敛、任意正交平面截面、导线草图内含 2 条曲线均未测；Creo 9/10 无 SDK 未测；WorkBuddy 黑盒未执行。
