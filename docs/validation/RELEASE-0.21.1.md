# 发布记录 0.21.1（2026-11-11）

本文件是 0.21.1 的发布记录。结论以 [GitHub Release v0.21.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.21.1) 正文与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.21.1`（PATCH），源码版本以 [version.py](../version.py) 为准。
- 公开工具：107（与 0.21.0 相同；无新增工具、无新增参数）。
- 交付内容：[BUG-118](../work-items/BUG-118.md)（compact 预算裁剪丢曲面放样测量值）修复与回归；0.21.0 遗留的 3 截面 + 导线实机用例跑通；0.21.0 发布记录与复核段回填。

## 缺陷与修复

- 现象：3 截面 + 2 导线放样（job `6510998c…`，Creo 12.4.0.0）在 `detail=compact` 下整条 `surface_loft` 记录只剩 `detail_truncated=true`；同一作业 `detail=full` 分页含 `section_count=3`、`guide_count=2`、`quilt_count=1`、`quilt_closed_native="open"`、`surface_area_mm2=1599.9999999999995`。
- 根因：`enforce_compact_budget` 第 2 阶段自最后一条记录倒序剥字段，放样是计划最后一条，且其测量字段不在保护集合内。
- 修复：`OUTCOME_OPERATION_KEYS`（面积/闭合/计数/曲线与夸特 ID 等标量）并入保护集合；大块 `profile`/`surface_group`/`native_section` 仍可被裁，预算上限不变。

## 验证

- 单元：`tests/unit/test_large_plan_result_budget.py` 30 项 OK（含新增 `test_a_trimmed_surface_receipt_keeps_its_measurements`）；全量 `Ran 3314 tests ... OK`。
- 实机（用户 2026-11-11 重启 Creo 并当次确认后执行）：`tools\test_surface_loft_guides.py --live --confirm-session-usable` → 离线 12 项 + 实机 22 项全 PASS，报告 `build/surface_loft_guides/20261111-135731.json`。
  - 直导线 job `baad63b6ceef414cbbd0a4c03e0ee254`：800.0 mm²、bbox x 止 40.0 mm。
  - 曲线导线 job `e2646c3a789d454db601069184838b7b`：600.0 mm²、bbox x 达 44.24 mm。
  - 3 截面 + 2 导线 job `2a2ee086273b40bc81a5edab6b1f01a5`：`section_count=3`、`guide_count=2`、1599.9999999999995 mm²、单张开放 quilt、无实体、bbox 40.12/40.12 mm、保存重载 verified。
- 风格与语言：`tools\dev_check.py --work-item BUG-118` 结果见 Release 正文（`success=true`、未新增诊断）。

## 打包

- 种子包确定性构建（回填 `docs/seed_package.json` 前后各一次）摘要一致，源码包由公共 allowlist 构建，四附件闸门（两个 ZIP + 两个 sidecar）本地自检通过。
- 两个包的 SHA256 以 Release 正文与本文件「发布核对」段为准：本记录本身在源码包内，把摘要写进本文件会改变包内容，故不在此处固化。

## 未测范围

- 其他可能被整体剥掉的 op 类型未逐项核对；保护标量后的极端预算压测未做。
- 曲线导线曲面形状仍未可视化核对，600.0 mm² 与 800.0 mm² 的差异未做几何解释。
- `ADV_VIA_CRV`、控制点、G1/G2、端点收敛、任意正交平面截面、导线含 2 条曲线的形态未测；Creo 9/10 未测；WorkBuddy 黑盒未执行。

## 发布核对

发布后在此段回填：标签指向的主干提交、Release 链接、四附件清单与 `tools\check_release_assets.py --tag v0.21.1` 的核对结果。
