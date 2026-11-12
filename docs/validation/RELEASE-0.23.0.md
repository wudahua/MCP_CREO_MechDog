# 发布记录 0.23.0（2026-11-12）

本文件是 0.23.0 的发布记录。发布后结论以 GitHub Release `v0.23.0` 正文、[统一 POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md#v02302026-11-12) 与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.23.0`（MINOR），源码版本以 [version.py](../version.py) 为准。
- 公开工具：107（无新增工具；`sketch` / `creo_create_sketch` 新增 `b_spline` 实体形态）。
- 交付内容：[FEAT-066](../work-items/FEAT-066.md) 精确 NURBS `b_spline`；[DEV-082](../work-items/DEV-082.md) boundary-blend 门禁从 `Probbl.h` 改为 `PRO_E_BNBLN_*` 元素 ID。
- 反馈来源：`C:\Users\Administrator\Downloads\0.21.0` 三份原件，已逐字节归档到 [feedback-0.21.0-2026-11-11](feedback-0.21.0-2026-11-11/MAPPING.md)。

## 版本号说明

- 仓库存在历史标签 `v0.22` 与 `docs/RELEASE_NOTES_0.22.md`（旧编号体系），本版不动；新版本用 `v0.23.0`、版本说明为 `docs/RELEASE_NOTES_0.23.0.md`。
- `src/creo_mechdog/update_check.py` 只接受三段式 SemVer，历史 `v0.22` 不参与比较。

## 验证

### 离线与编译

- `bridge.py build` 成功；worker `source_digest=722652b527227f7767f421911494161c22e92e0ca84659eed7afce3aba945edb`、`worker_sha256=a6dec2bda6fc3d8fe39a76aa84a85aee060b2a9662a9c2a5761794eaed0b8c06`，`surface_loft` 状态 `compiled`。
- `tools\dev_check.py --work-item FEAT-066`：`success=true`，3429 项单测 0 失败 0 错误；风格无新增（lint 21、未格式化 9，均在 `docs/development/style-baseline.json` 内）。
- `tools\check_backlog_counts.py`：178 / BUG 77 / FEAT 63 / DEV 38，声明行、表行与分类表一致。
- 台账分类调整：FEAT-066 由「开发中」移入「部分交付，剩余待规划」（已交付 0.23.0 子项），开发中 8→7、部分交付剩余待规划 3→4，总数仍 178。

### 实机（Creo 12.4.0.0，用户 2026-11-12 当次授权）

- `tools\test_b_spline.py --live --confirm-session-usable`：离线 8 + 实机 12 项全 PASS，报告 `build/b_spline/20261112-113339.json`。
  - 草图 job `348ea9e0bf264d2097012913b691dba9`、model `8e384ad19e234927adc13cb439b45318`、rev 1；保存重载 verified；控制点回读最大偏差 2.6484335973398527e-31 mm。
  - 放样 job `f7c651016cac41c4b98a1af5f72d075b`、model `a42da209f9884b5eb43b477c2052f238`、rev 1；面积 1058.0172783981307 mm²，独立 de Boor oracle 1058.017813744952 mm²（差 0.000535 mm²，相对 5.1e-7）；`section_count=2`、单张开放 quilt、无实体、重载后面积一致。
  - 首次运行 `build/b_spline/20261112-113247.json` 仅面积 oracle FAIL，原因是驱动 de Boor 初始下标错误；修正驱动后产品侧全 PASS，非产品回归。
- `tools\test_surface_loft_guides.py --live --confirm-session-usable`：全 PASS，报告 `build/surface_loft_guides/20261112-113434.json`；3 截面 + 2 导线 1599.9999999999995 mm²，门禁改动未回归既有放样。
- 证据汇总：[feat066-b-spline-2026-11-12](feat066-b-spline-2026-11-12/EVIDENCE.md)。

## 打包

- 顺序：`tools\package_seeds.py --output build\release-0.23.0\MCP_CREO_MechDog-0.23.0-seed-library.zip` → 回填 `docs/seed_package.json` → 重建确认哈希 `5394664c…` 不变 → `tools\package.py --seed-archive <seed.zip> --output <source.zip>` → 解压源码包跑全量单测。
- 源码包 SHA256 `a8abb957acd5f6989276ff4d5be426e14cc128050566f8507ec3be0656393e7a`（9 694 983 字节）；种子包 SHA256 `5394664c98f0f10777820dda8dd6ab07abf890b8324ec64ff59d662b1f978c0e`（493 442 字节）。
- 源码包解压到 `E:\r023\MCP_CREO_MechDog`（无 `.git`）后 `pip install --no-deps -e .`，全量单测 `Ran 3429 tests ... OK (skipped=6)`。首次在深层路径运行有 1 项 blackbox 夹具因 Windows 260 字符路径限制报 `Errno 2`，换短路径后通过，非产品缺陷。

## 未测范围

- Creo 9/10 运行期（本机无对应 SDK）；0.21.0 报告的 Creo 10 零补丁编译为报告方实测，未在本机复现。
- `b_spline` 的 `closed`、`dimensioning="coordinates"`、`update_sketch_geometry` 改写。
- 非 mm 单位、非 XY 平面的精确面积断言；WorkBuddy 黑盒。
- 0.22.0 已披露的限制不变：`boundary_conditions` compact 裁剪、`ADV_VIA_CRV`、非平面相邻面相切、已有实体模型中的 `surface_loft`。

## 发布核对

- 核对时间：2026-11-12 12:27（+08:00）/ 2026-11-12T04:27Z。`main` = `origin/main` = `0cfd42909f822dda7863f6d5a4c8dcb677f3dfb9`；附注标签对象 `1962224cb99e2f860ca9e67b3cf4223ab03f43a3`（`v0.23.0`，指向上述提交）。
- Release：[v0.23.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.0)，id `442495969`，非 draft、非 prerelease，`created_at=2026-11-12T04:25:37Z`，`published_at=2026-11-12T04:26:54Z`，target `main`。
- 远端四附件（未用通配）；远端 `sha256:` digest、本地实算与 sidecar 内容逐一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.23.0-source.zip` | 9 694 983 | `a8abb957acd5f6989276ff4d5be426e14cc128050566f8507ec3be0656393e7a` |
| `MCP_CREO_MechDog-0.23.0-source.zip.sha256` | 101 | `6a8ac323bd30184acf288c5547fa7217c21782da796f57ba30c22be9989d30ca` |
| `MCP_CREO_MechDog-0.23.0-seed-library.zip` | 493 442 | `5394664c98f0f10777820dda8dd6ab07abf890b8324ec64ff59d662b1f978c0e` |
| `MCP_CREO_MechDog-0.23.0-seed-library.zip.sha256` | 107 | `ffcd1695bb04001a6adbf23556a0167d2ff63dae961cca6b78865482c317f0b5` |

- 核对命令：`tools/check_release_assets.py --tag v0.23.0` → exit 0，「v0.23.0: four assets downloaded and verified; both sidecars match」。
- 源码包内本文件是打包时点快照；发布后的核对结论以本节、[统一 POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md#v02302026-11-12) 与 Release 正文为准。

## 逐 ID 状态核对

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [FEAT-066](../work-items/FEAT-066.md) | 已实现并实机验收 | 0.23.0 | `closed`、coordinates、页面编辑未排期；Creo 10 未验 | 已交付 0.23.0 | 部分交付，剩余待规划 | 已列入 | 已列入 | `v0.23.0`（已发布） |
| [DEV-082](../work-items/DEV-082.md) | 门禁修复已实现并实机回归 | 0.23.0 | H01 抽头、单一真值源、Creo 10 运行期 | 开发中 | 开发中 | 已列入 | 已列入 | `v0.23.0`（已发布） |

## 相对上一正式包核对（上一版本：0.22.0）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party` 原字节（含 `json.hpp`、第三方许可） | 0.22.0 源码包 | 未改动（`git diff` 为空） | 无需重新注册 |
| 回调指纹（`sha256-repo-lf-v1`） | 0.22.0 源码包 | 未改动（回调源未修改） | 无需重新注册 |
| loader DLL SHA256 | 0.22.0 未单独留存 | 未单独留存 | 本版未改 loader；安装后随 worker 重建 |
| callback DLL SHA256 | 0.22.0 未单独留存 | 未单独留存 | 本版未改 callback；安装后随 worker 重建 |
| worker SHA256 | `a7408483…`（0.20.0 记录） | `a6dec2bd…` | 本版 worker 不同，升级后必须重建 |
| `protk.dat` / 注册表路径 | 0.22.0 | 未改动 | 无需迁移 |
| 实际注册影响 | — | — | 需重新编译并重启 worker；DLL 注册路径不变 |
