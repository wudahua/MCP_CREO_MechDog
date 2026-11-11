# 发布记录 0.21.0（2026-11-11）

本文件是 0.21.0 的发布记录。结论以 [GitHub Release v0.21.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.21.0) 正文与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.21.0`（MINOR），源码版本以 [version.py](../version.py) 为准。
- 公开工具：107（与 0.20.0 相同；新增能力是 `surface_loft` 的 `guides` 参数与回执字段）。
- 交付内容：[FEAT-065](../work-items/FEAT-065.md) M2（曲面放样第二方向），以及 [DEV-081](../work-items/DEV-081.md) 入库的 0.20.0 之后积压工作（BUG-115/116/117、DEV-082/083、FEAT-039、FEAT-033、FEAT-018 与 0.20.0 发布记录回填）。各条目验收范围以对应工作条目文档为准。

## 环境

Windows x64 / Python 3.12.14 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / 本机许可。实机执行经用户 2026-11-11 当次明确确认；未结束或重启 Creo/nmsd、未清 `toolkit.lock` 或 unknown 保护、未做故障注入、未改用户模型与历史证据。

## 验证

- FEAT-065/M2 驱动 `tools\test_surface_loft_guides.py --live --confirm-session-usable` → 离线 10 项 + 实机 17 项全 PASS（报告 `build/surface_loft_guides/20261111-120758.json`）。
  - 直导线 job `900fa9b3092541e681deeae0e2bf9ba6`：800.0 mm²、bbox x 止 40.0 mm、`guide_count=2`、开放 quilt、无实体、保存重载 verified。
  - 曲线导线 job `4d0f3e10b1f54c14b794f3ecd7e8760a`：600.0 mm²、bbox x 达 44.24 mm、单张开放 quilt、保存重载后面积一致。
  - 单导线计划在准入阶段拒绝，无 `job_id`。
  - 3 截面 + 直导线 job `2fd4ab48c67e402ab4e8d0f5fa826091`：1600.0 mm²；此项来自一次性探针，驱动中的同几何用例未在发布前复跑。
- 全量单元测试：`Ran 3314 tests in 402.638s ... OK`（工作树）。
- `tools\dev_check.py --work-item FEAT-065 --unit-timeout-seconds 1800`：`success=true`、`unit_tests=passed`、`native_validation=not_run`；受测源码指纹 `c5eee4603aff7031852af796ce204c9b2c5fdaf9db638f94ae12b8a766cc3583`（提交 `4706286`、`dirty=true`，提交号仅作定位，发布前已按本记录内容重新打包）。
- 风格：未新增 lint 诊断与未格式化文件（`--strict` 下的存量项保持基线）。

## 打包

- 种子包确定性构建（含回填 `docs/seed_package.json` 后重建）三次，SHA256 一致：
  `MCP_CREO_MechDog-0.21.0-seed-library.zip` = `da2a2936afdc5c1afbc1c7ffd5c9d70390020ec41f3cdb2f086d2151259a0f46`（24 files / 9 seeds）。
- 源码包由公共 allowlist 构建，四附件闸门自检通过（两个 ZIP + 两个 sidecar 且 sidecar 与 ZIP 摘要一致）：约 1730 个文件、9.5 MB 量级。
- 源码包 SHA256 以 Release 正文与本文件「发布核对」段为准：本记录本身在源码包内，把摘要写进本文件会改变包内容，故不在此处固化。

## 未测范围

- 曲线导线曲面形状未在 GUI 或等价可视化中核对；600.0 mm² 与直纹基线 800.0 mm² 的差异未做几何解释。
- `PRO_E_BNBLN_ADV_VIA_CRV`、`PRO_E_CTRL_PTS`/`PRO_E_BLEND_TYPE`、G1/G2、端点收敛、任意正交平面截面、导线草图内含 2 条曲线的形态未测。
- Creo 9/10 无 SDK，未编译、未建模。
- WorkBuddy 黑盒验收未执行。

## 发布核对

- 标签对象：`v0.21.0` → annotated tag `1932c03b7842f04603a979393ffb607db2beaa7a` → 提交 `990c88a155be37ccf7c75b5c6268fb6352318899`（`main`，`074ea67..990c88a` 推送）。
- Release：[v0.21.0](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.21.0)，id `441266770`，非 draft、非 prerelease；`created_at=2026-11-11T05:14:44Z`，`published_at=2026-11-11T05:15:33Z`，`target_commitish=main`。
- 核对命令：`tools\check_release_assets.py --tag v0.21.0` → exit 0，「v0.21.0: four assets downloaded and verified; both sidecars match」。
- 四附件逐个列出（未用通配）；API `assets[].digest`、下载后本地实算 SHA256 与 sidecar 内容三者一致：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.21.0-source.zip` | 9 509 982 | `ff3ef09eb27409089375b61a61505c1a1fa359f16cd5507858325dcaac1be4ec` |
| `MCP_CREO_MechDog-0.21.0-source.zip.sha256` | 101 | `f7b66d0158c79272291a66adda430ab46bca8f74c4222bce791bb8d67b6bcaf0` |
| `MCP_CREO_MechDog-0.21.0-seed-library.zip` | 493 442 | `da2a2936afdc5c1afbc1c7ffd5c9d70390020ec41f3cdb2f086d2151259a0f46` |
| `MCP_CREO_MechDog-0.21.0-seed-library.zip.sha256` | 107 | `9309ac3dd750d0f720963ddb9ab31f5fcbdcc8a3945e7103ed613873f6014bfe` |

- 源码包解压门禁：解压后 `pip install --no-deps -e .` 并跑 `python -m unittest discover -s tests` → `Ran 3314 tests`，3313 通过、5 skipped、1 error。该 error 是解压路径过深触发 Windows MAX_PATH（`test_dev040_blackbox_fixture` 的 `.tmp` 重命名失败），把同一份解压内容放到短路径 `E:\u21` 复跑该模块 → 4 项 `OK`，确认与包内容无关。核完已把可编辑安装恢复回 `E:\Projects\MCP_CREO_MechDog`。
