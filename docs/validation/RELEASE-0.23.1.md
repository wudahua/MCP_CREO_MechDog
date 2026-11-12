# 发布记录 0.23.1（2026-11-12）

本文件是 0.23.1 的发布记录。发布后结论以 [GitHub Release v0.23.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.1) 正文、[统一 POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md) 与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.23.1`（PATCH），源码版本以 [version.py](../version.py) 为准。
- 公开工具：107（与 0.23.0 相同；无新增工具、无新增参数）。
- 交付内容：[BUG-119](../work-items/BUG-119.md) `surface_loft` 实体增量判定；YZ@X 与 XZ@Y 正交平面截面实机补充；[DEV-083](../work-items/DEV-083.md) 发布记录机器门禁与 POSTCHECK `## v0.21.1` 回填。
- 反馈来源：`C:\Users\Administrator\Downloads\0.22.0` 两份报告；P1 门禁与 P5 样条参数已在 0.23.0 交付，本轮不重复；P7 非平面边界曲面与 callback 不在本轮。

## 修复与门禁

- `native/surface_loft.cpp`：创建前后分别读取 `has_solid`、`body_counts.with_material` 与 `volume_mm3`，只有本次真正新增实体材料才失败；回执新增 `has_solid_before`/`has_solid_after`/`created_solid_material`/`material_bodies_before`/`material_bodies_after`/`volume_mm3_before`/`volume_mm3_after`。
- `src/creo_mechdog/job_projection.py` 与 `operation_results.py`：上述字段加入 `surface_loft` 投影与 compact 保护集合，轮询 compact 回执不再丢失前后快照。
- `src/creo_mechdog/release_integrity.py` 新增 `validate_release_records()`；`tools/package.py`、`tools/check_release_assets.py` 接入，`tools/check_release_records.py` 供预检；0.23.0 及更早版本跳过记录门禁。

## 验证

### 离线与编译

- `bridge.py build` 成功，`surface_loft` 为 `compiled`。
- `tests/unit/test_surface_loft_solid_delta.py` 5 项、`tests/unit/test_release_records.py` 9 项通过；两个新驱动离线各 2 项通过。
- `tools/dev_check.py --work-item BUG-119` 结果见下方「发布前检查」。

### 实机（Creo 12.4.0.0，用户 2026-11-12 当次授权）

- `tools/test_surface_loft_existing_solid.py --live --confirm-session-usable`：8 项全 PASS，报告 `build/surface_loft_existing_solid/20261112-135103.json`。
  - job `76d69c9c033c4710b5c301bbdb7d49e3`、model `a12c7089eb2b421c9ccfb696d9b7ba11`、revision 1。
  - `has_solid_before=true`、`has_solid_after=true`、`created_solid_material=false`、材料体 1→1、体积 60000.0→60000.0 mm³。
  - 面积 5026.548245743668 mm²（2π×20×40）、单张开放 quilt、保存重载 verified。
- `tools/test_surface_loft_planes.py --live --confirm-session-usable`：13 项全 PASS，报告 `build/surface_loft_planes/20261112-135216.json`。
  - YZ@X=0/50：job `e6889d8be4d9486a90db7b30775a6b71`、model `3163a41320584db198ac7ef6c48b13e4`，面积 6283.185307179587 mm²。
  - XZ@Y=0/40：job `5205b78d2b6d452fbfc10000259cf957`、model `344c674a929a4b2daee1d65ad7af0250`，面积 5026.548245743668 mm²。
  - 两组均单张开放 quilt、无实体、保存重载 verified。
- `tools/test_surface_loft_guides.py --live --confirm-session-usable`：离线 12 + 实机 26 项全 PASS，报告 `build/surface_loft_guides/20261112-135312.json`；3 截面 + 2 导线 job `c85a9ccfda9941f380cbb920520a93d0`、1599.9999999999995 mm²、单张开放 quilt、保存重载 verified，门禁改动未回归既有放样。

### 发布前检查

- `tools/dev_check.py --work-item BUG-119`：`success=true`，`Ran 3443 tests ... OK`；风格 `lint_findings=21`、`unformatted_files=9`，均在 `docs/development/style-baseline.json` 内，无新增回归。
- `tools/check_backlog_counts.py`：179 / BUG 78 / FEAT 63 / DEV 38，声明行、表行与分类表一致。
- `tools/check_release_records.py --version 0.23.1`：打包前记录门禁通过。

## 打包

- 顺序：`tools\package_seeds.py --output build\release-0.23.1\MCP_CREO_MechDog-0.23.1-seed-library.zip` → 回填 `docs/seed_package.json` → 重建确认摘要不变 → `tools/package.py --seed-archive <seed.zip> --output <source.zip>`。
- 种子包 SHA256 `46d8d1f5024a05c4585f051bab1243791a7a9149a9eb90e1764a5ec9afb6a926`（24 个文件、9 个种子）；两次确定性构建摘要一致。
- `source.zip` 的摘要见同名 sidecar；字节数与 SHA256 由 sidecar 与 Release 正文给出，不写入包内文件（ZIP 不能包含自身摘要）。

## 未测范围

- Creo 9/10 运行期（本机无对应 SDK）；0.21.0/0.22.0 报告的 Creo 10 零补丁编译为报告方实测，未在本机复现。
- 非毫米单位、WorkBuddy 黑盒。
- `b_spline` 的 `closed`、`dimensioning="coordinates"`、页面编辑；`boundary_conditions` compact 裁剪与 `ADV_VIA_CRV`。
- 非平面相邻面相切、导线边界连续条件、曲线导线形状可视化。

## 发布核对

- Release：[v0.23.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.1)。Release id 与发布时间由发布平台生成，以 Release 页面与 `main` 的 POSTCHECK 段为准；包内不预写。
- 四附件（逐个上传，不用通配）：

| 附件 | 摘要 |
| --- | --- |
| `MCP_CREO_MechDog-0.23.1-source.zip` | 摘要见同名 `MCP_CREO_MechDog-0.23.1-source.zip.sha256` sidecar 与 Release 正文 |
| `MCP_CREO_MechDog-0.23.1-source.zip.sha256` | 一行 `<64-hex SHA256>  <文件名>` |
| `MCP_CREO_MechDog-0.23.1-seed-library.zip` | `46d8d1f5024a05c4585f051bab1243791a7a9149a9eb90e1764a5ec9afb6a926` |
| `MCP_CREO_MechDog-0.23.1-seed-library.zip.sha256` | 一行 `<64-hex SHA256>  <文件名>` |

- 核对命令：`tools/check_release_assets.py --tag v0.23.1`（版本 ≥ 0.23.1 时会同时运行包内记录门禁）。
- 源码包解压后全量单测从短路径运行，结果回填到 `main` 的 POSTCHECK `## v0.23.1` 段，不回写包内快照。

## 逐 ID 状态核对

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [BUG-119](../work-items/BUG-119.md) | 已实现并实机验收 | 0.23.1 | Creo 9/10、非毫米、WorkBuddy | 已交付 0.23.1 | 已有修复但待验收 | 已列入 | 已列入 | `v0.23.1` |
| [DEV-083](../work-items/DEV-083.md) | 门禁已实现并接入打包/核对 | 0.23.1 | RELEASING 永久链接规则 | 已交付 0.23.1 | 部分交付，剩余待验收 | 已列入 | 已列入 | `v0.23.1` |
| [FEAT-065](../work-items/FEAT-065.md) | 补充项已实机验收 | 0.23.1 | 见工作卡「仍开放」 | 已交付 0.23.1 子项 | 部分交付，剩余待规划 | 已列入 | 已列入 | `v0.23.1` |

## 相对上一正式包核对（上一版本：0.23.0）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party` 原字节（含 `json.hpp`、第三方许可） | 0.23.0 源码包 | 未改动 | 无需重新注册 |
| 回调指纹（`sha256-repo-lf-v1`） | 0.23.0 源码包 | 未改动 | 无需重新注册 |
| loader DLL SHA256 | 未单独留存 | 未单独留存 | 本版未改 loader；安装后随 worker 重建 |
| callback DLL SHA256 | 未单独留存 | 未单独留存 | 本版未改 callback；安装后随 worker 重建 |
| worker SHA256 | `a6dec2bd…`（0.23.0） | 由本次源码重新编译 | 本版含 `native/surface_loft.cpp` 变更，升级后必须重建 |
| `protk.dat` / 注册表路径 | 0.23.0 | 未改动 | 无需迁移 |
| 实际注册影响 | — | — | 需重新编译并重启 worker；DLL 注册路径不变 |
