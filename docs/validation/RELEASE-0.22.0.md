# 发布记录 0.22.0（2026-11-11）

本文件是 0.22.0 的发布记录。结论以 [GitHub Release v0.22.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.22.0) 正文与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.22.0`（MINOR），源码版本以 [version.py](../version.py) 为准。
- 公开工具：107（与 0.21.1 相同；新增 `sections`/`guides` 的输入形态与 `boundary_conditions` 参数，不新增工具）。
- 交付内容：[FEAT-065](../work-items/FEAT-065.md) M3（截面/导线接受已有曲线、边与首末收敛点）与 M4（边界相切）；`creo_measure_surface_group` 的 `open_edge_records`。
- 合入方式：`codex/FEAT-065-m3-m4-surface-loft`（12 个提交）快进合入 `main`，基点 `ea753be`（0.21.1）。

## 版本号说明

- 仓库存在历史标签 `v0.22` 与 `docs/RELEASE_NOTES_0.22.md`（旧编号体系），本版一律不动；新版本用 `v0.22.0`、版本说明为 `docs/RELEASE_NOTES_0.22.0.md`。
- `src/creo_mechdog/update_check.py` 只接受三段式 SemVer，`v0.22` 不参与比较，两者不冲突。

## 验证

### 离线

- `tools\dev_check.py`：`success=true`，3413 项单测 0 失败 0 错误；风格无新增（lint 21、未格式化 9，均在基线内），源码指纹 `75d861d7…`。
- `tools\check_backlog_counts.py`：声明行、表行与分类表三方一致。
- 台账分类调整：FEAT-065 由「开发中」移入「待规划」（已交付 0.22.0 子项，剩余未排期），开发中 8→7、待规划 41→42，总数仍 177。

### 实机（Creo 12.4.0.0，用户 2026-11-11 当次授权）

会话前置：机器上原有的 22:42 会话未注册名字服务器（`not_found_or_unreadable`、`toolkit_code=-4`、`name_read_code=0`），驱动在 `session_ready` 停止、未提交几何。经用户当次授权关闭该会话，并用 `creo_startup.launch_creo`（Explorer + `parametric.psf`）重启，`connected=true`、`release_numeric=44` 后开始回归。未做故障注入、未清锁、未结束 nmsd、未改用户模型。

| 驱动 | 结果 | 报告 |
| --- | --- | --- |
| `test_surface_loft_multisection.py --live` | 离线 9 + 实机 21 项全 PASS | `build/surface_loft_multisection/20261111-233717.json` |
| `test_surface_loft_guides.py --live` | 离线 12 + 实机 22 项全 PASS | `build/surface_loft_guides/20261111-233833.json` |
| `test_surface_loft.py --live` | 22 项全 PASS | `build/surface_loft/20261111-234006-0c1b15/report.json` |
| `test_multi_quilt_group.py --live` | 44/45 PASS（1 项断言过时，见下） | `build/multi_quilt_group/20261111-234225-eebf80/report.json` |
| `test_five_claw_bottle.py --live` | 63 项全 PASS、46 个作业 | `build/five_claw_bottle/20261112-000424-513355/report.json` |

关键几何：

- 三截面 40/60/40 mm、间距 20 mm：2101.2524427513217 mm²、单张开放 quilt、`section_count=3`、无实体、保存重载后面积一致；2 mm 加厚 4202.507981502071 mm³。
- 两截面回归：800.0 mm²、`piecewise_ruled=true`；trim 两侧各 400.0 mm²；2 mm 加厚 1599.9999999999995 mm³。
- 直导线 800.0 mm²；曲线导线 600.0 mm²（bbox x 达 44.24 mm）；3 截面 + 2 导线 1599.9999999999995 mm²。
- 五爪整瓶：闭合 quilt 7858.298125230911 mm²、solidify 56799.99517675038 mm³。

`test_multi_quilt_group.py` 的唯一 FAIL：

- 断言 `group_with_thickened_member_is_refused` 要求「拒绝且无 `job_id`」。
- 实际：`surface_group_measure` 自 0.19.0（`0947d48` DEV-074 并入作业计划）起先建作业再由原生失败，回执带 `job_id`/`model_id`，`error` 文本与 0.18.4 实机证据 `docs/validation/feat039-h10-multi-quilt-2026-11-07/live_multi_quilt_report.json` 逐字相同（`contour_edge_visit_failed`）。
- 判定：能力行为未变，属 0.19.0 起就过时的断言，不是本版回归；本版不改测试语义，留待后续条目处理。

## 打包

- 顺序：`tools\package_seeds.py --output <seed.zip>` → 回填 `docs/seed_package.json` → 重建确认哈希不变 → `tools\package.py --seed-archive <seed.zip> --output <source.zip>` → 解压源码包跑全量单测。
- 附件固定为四个：两个 ZIP 与各自的 `.zip.sha256`，逐个列出上传，不使用通配。
- 两个包的 SHA256 以 Release 正文与本文件「发布核对」段为准：本记录在源码包内，把摘要写进本文件会改变包内容，因此不在此处固化。

## 未测范围

- Creo 9/10（本机无 SDK，未编译、未建模）；非平面相邻面与两端朝向不同的相切；`curvature`/`normal`/导线边界条件；已有实体模型中的 `surface_loft`；非 mm 单位。
- `boundary_conditions` 不在 compact 保护集合内；`ADV_VIA_CRV`；导线曲面形状未可视化核对。
- WorkBuddy 黑盒未执行。

## 发布核对

待发布后回填（标签指向、Release id/时间、四附件名称与摘要、`tools\check_release_assets.py --tag v0.22.0` 结果、源码包解压单测）。
