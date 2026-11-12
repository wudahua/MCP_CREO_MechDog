# 0.23.1 版本说明（2026-11-12）

PATCH 版本。修正已有实体的模型上 `surface_loft` 被误判为“创建实体”而回滚的问题，补两组正交平面截面的实机证据，并把发布记录回填前移为机器门禁。公开工具仍 107，无新增工具或参数。

## 修复

### BUG-119：已有实体模型上的 `surface_loft` 误判

- 现象：模型里已有实体时，即使两张截面都是开放曲面、结果也是开放 quilt，`surface_loft` 仍返回 `surface_loft created solid material; a surface loft must not` 并回滚。
- 根因：`native/surface_loft.cpp` 把模型级 `inspection(false)["has_solid"]` 当成“本次特征是否创建实体”。该字段描述整个模型，已有实体时恒为 `true`。
- 修复：创建前后分别读取 `has_solid`、`body_counts.with_material` 与 `volume_mm3`，只有本次真正新增实体材料（`has_solid` false→true、带材料实体数增加或体积增加超过 `1e-6 mm³`）才失败。回执新增 `has_solid_before`、`has_solid_after`、`created_solid_material`、`material_bodies_before`、`material_bodies_after`、`volume_mm3_before`、`volume_mm3_after`。

## 验证

### 离线与编译

- `bridge.py build` 成功，`surface_loft` 为 `compiled`。
- `tests/unit/test_surface_loft_solid_delta.py` 5 项通过；`tests/unit/test_release_records.py` 9 项通过。
- `tools/test_surface_loft_existing_solid.py` 离线 2 项、`tools/test_surface_loft_planes.py` 离线 2 项通过。

### 实机（Creo 12.4.0.0，用户 2026-11-12 当次授权）

- `tools/test_surface_loft_existing_solid.py --live --confirm-session-usable`：8 项全 PASS，报告 `build/surface_loft_existing_solid/20261112-135103.json`。
  - 100×60×10 拉伸实体 + 两个 R20 圆截面（Z=20/60）的 `surface_loft`：job `76d69c9c033c4710b5c301bbdb7d49e3`、model `a12c7089eb2b421c9ccfb696d9b7ba11`、revision 1。
  - `has_solid_before=true`、`has_solid_after=true`、`created_solid_material=false`、材料体 1→1、体积 60000.0→60000.0 mm³。
  - 面积 5026.548245743668 mm²（2π×20×40），单张开放 quilt，保存重载 verified。
- `tools/test_surface_loft_planes.py --live --confirm-session-usable`：13 项全 PASS，报告 `build/surface_loft_planes/20261112-135216.json`。
  - YZ@X=0/50：job `e6889d8be4d9486a90db7b30775a6b71`、model `3163a41320584db198ac7ef6c48b13e4`，面积 6283.185307179587 mm²（2π×20×50）。
  - XZ@Y=0/40：job `5205b78d2b6d452fbfc10000259cf957`、model `344c674a929a4b2daee1d65ad7af0250`，面积 5026.548245743668 mm²（2π×20×40）。
  - 两组均单张开放 quilt、无实体、保存重载 verified。
- `tools/test_surface_loft_guides.py --live --confirm-session-usable`：离线 12 + 实机 26 项全 PASS，报告 `build/surface_loft_guides/20261112-135312.json`；3 截面 + 2 导线 1599.9999999999995 mm²，门禁改动未回归既有放样。

## 发布流程门禁（DEV-083）

0.22.0 与 0.23.0 都是在标签之后才回填 POSTCHECK/发布记录，已发布 `source.zip` 内因此留下准备态快照。0.23.1 起：

- `src/creo_mechdog/release_integrity.py` 新增 `RECORDS_ENFORCED_FROM = (0, 23, 1)` 与 `validate_release_records()`，检查 POSTCHECK 的 `## v<version>` 段、Release URL、四个附件名、种子包 SHA256、两份 sidecar 说明、占位词、`docs/validation/RELEASE-<version>.md`、包内版本声明，以及逐 ID 的主台账/工作卡状态。
- `tools/package.py` 在四附件门禁后运行同一检查；失败返回 1 并保留 ZIP 供排查。
- `tools/check_release_assets.py` 下载并校验四附件后，对版本 ≥ 0.23.1 的源码包再跑记录门禁。
- `tools/check_release_records.py` 供打包前单独预检。
- 低于 0.23.1 的历史 tag 跳过记录门禁，仍只做四附件校验。

包内不写 `source.zip` 自身 SHA256（ZIP 不能包含自身摘要），也不写打包时还不存在的 Release id/发布时间；这些由 sidecar 与 Release 正文承担，包内文档写明“摘要见同名 sidecar”。

## 历史补记

- `docs/development/RELEASE-POSTCHECK-2026-11-07.md` 增加 `## v0.21.1` 段。
- `docs/validation/RELEASE-0.22.0.md`、`docs/validation/RELEASE-0.23.0.md` 顶部各加一条补记，说明包内为回填前快照；历史附件不重传。
- [DEV-082](../work-items/DEV-082.md)：Creo 10 整包零补丁编译改记外部报告方已验证，H01 与运行期仍开放。

## 未测范围

- Creo 9/10 运行期（本机无对应 SDK）；0.21.0/0.22.0 报告的 Creo 10 零补丁编译为报告方实测，未在本机复现。
- 非毫米单位、WorkBuddy 黑盒。
- `b_spline` 的 `closed`、`dimensioning="coordinates"`、页面编辑；`boundary_conditions` compact 裁剪与 `ADV_VIA_CRV`。
- 非平面相邻面相切、导线边界连续条件、曲线导线形状可视化。

## 附件

- `MCP_CREO_MechDog-0.23.1-source.zip` 与 `MCP_CREO_MechDog-0.23.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.23.1-seed-library.zip` 与 `MCP_CREO_MechDog-0.23.1-seed-library.zip.sha256`

种子包 SHA256：`46d8d1f5024a05c4585f051bab1243791a7a9149a9eb90e1764a5ec9afb6a926`。`source.zip` 的摘要见同名 sidecar 与 Release 正文，不写入包内文件。发布记录见 [RELEASE-0.23.1](validation/RELEASE-0.23.1.md)。
