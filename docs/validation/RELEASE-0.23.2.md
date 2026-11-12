# 发布记录 0.23.2（2026-11-13）

本文件是 0.23.2 的发布记录。发布后结论以 [GitHub Release v0.23.2](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.23.2) 正文、[统一 POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md) 与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.23.2`（PATCH），源码版本以 [version.py](../../version.py) 为准。
- 公开工具：107（与 0.23.1 相同；无新增工具、无新增参数）。
- 交付内容：[BUG-120](../work-items/BUG-120.md) `surface_loft` 提取失败诊断字段、错误码与运行期观测披露；[DEV-083](../work-items/DEV-083.md) 逐 ID 状态一致性、主台账全表扫描与发布文档本地链接门禁。
- 反馈来源：`C:\Users\Administrator\Downloads\0.23.0` 四份报告，映射见 [归档 MAPPING](feedback-0.23.0-2026-11-12/MAPPING.md)；原件在 `originals/`，逐字节保留。

## 修复与门禁

- `native/surface_loft.cpp`：创建成功后、提取前调用 `ProFeatureIsIncomplete`；提取失败时写入 `extract_unsupported=true`、`kernel_completion="unsupported"`、`kernel_evidence`（`release_numeric`、`create_code`、`extract_code`、`feature_incomplete`），错误文案带 `SURFACE_LOFT_EXTRACT_UNSUPPORTED` 与 `release_numeric`，作业照旧回滚。成功分支写 `extract_unsupported=false`、`kernel_completion="supported"`。
- `bridge.py`：新增 `record_surface_loft_runtime()` 与 `surface_loft_runtime_observation()`，按当前 worker SHA 把最近观测写入 `build/toolkit_health.json`；状态探针刷新时保留该观测。
- `src/creo_mechdog/capabilities.py` 与 `server.py`：`worker_build_identity.features.surface_loft` 披露 `kernel_completion`（缺观测或 worker 不匹配为 `unknown`），`available`/`enabled` 不变，不预拒绝。
- `src/creo_mechdog/release_integrity.py`：状态归一化为 `delivered / partial / developing / unplanned / other`；工作卡只读 `分类：` 行粗体；逐 ID 表比对「技术状态」「卡首页」「主台账」并提供「差异说明」放行；扫描主台账全部 `work-items/` 活动行；新增 `_link_problems()` 检查发布说明、发布记录与 POSTCHECK 的本地相对链接（根模式与源码 ZIP 模式）。

## 验证

### 离线与编译

- `bridge.py build` 成功，`surface_loft` 为 `compiled`。
- `tests/unit/test_surface_loft_extract_diagnostic.py` 5 项通过。
- `tests/unit/test_surface_loft_runtime_observation.py` 9 项通过。
- `tests/unit/test_release_records.py` 15 项通过。
- `tools/check_release_records.py --version 0.23.1` exit 0（真实历史文档校验，新增门禁不误报）。
- `tools/check_backlog_counts.py` 通过：180 / BUG 79 / FEAT 63 / DEV 38。

### 实机

本批未连接 Creo、未执行实机回归：未取得本轮当次实机授权，按离线批次发布。`kernel_completion="supported"` 在 Creo 12.4.0.0 的实际观测、几何与保存重载结论均未在本版重新取得；0.23.1 的实机结果只属于 0.23.1，不外推为本版通过。Creo 12.4 实机回归命令仍为 `tools/test_surface_loft_existing_solid.py`、`test_surface_loft_planes.py` 与 `test_surface_loft_guides.py` 的 `--live`，留待后续批次补证。

### 发布前检查

- `tools/check_release_records.py --version 0.23.2`：打包前记录门禁通过。
- `tools/dev_check.py --work-item BUG-120`：`success=true`，`Ran 3463 tests in 472.553s`、`OK`；风格 `lint_findings=21`、`unformatted_files=9`，均在 `docs/development/style-baseline.json` 内，无新增回归。受测源码 `b9e0c7d` + 未提交改动，指纹见 `build/development_check.json`。
- `bridge.py build` exit 0，`build/creo_worker.exe` 由本批源码重新编译。

## 打包

- 顺序：`tools\package_seeds.py --output build\release-0.23.2\MCP_CREO_MechDog-0.23.2-seed-library.zip` → 回填 `docs/seed_package.json` → 重建确认摘要不变 → `tools/package.py --seed-archive <seed.zip> --output <source.zip>`。
- 种子包 SHA256 `4a47a58293f773d530c7ab2a771db075f3557222a207fb5dcff853594e66861a`（24 个文件、9 个种子、493 442 字节）；两次确定性构建摘要一致。
- 源码包 `MCP_CREO_MechDog-0.23.2-source.zip` 由本提交源码构建，`package.py` 的四附件门禁与发布记录门禁均通过；其摘要见同名 sidecar 与 Release 正文，字节数与 SHA256 不写入包内文件（ZIP 不能包含自身摘要）。

## 未测范围

- Creo 10 运行期成功路径（本机无 Creo 10 SDK）；报告方的零补丁编译与运行期 `-18` 为报告方实测，本机未复现。
- 模板 XML/`FromXMLCreate`、STEP/IGES 导入与新提取通道。
- Creo 9 只有编译探测，无运行期证据。
- 非毫米单位、WorkBuddy 黑盒。
- RELEASING 中按 commit SHA 固定永久链接的规则仍开放（DEV-083 剩余项）。

## 发布核对

- 标签、Release id 与发布时间在发布后补记于本段与统一 POSTCHECK `## v0.23.2` 段。
- 核对命令：`tools/check_release_assets.py --tag v0.23.2`；版本 ≥ 0.23.1 时该命令同时解压源码包运行记录门禁。
- 四附件（逐个上传，不用通配）：
  - `MCP_CREO_MechDog-0.23.2-source.zip`
  - `MCP_CREO_MechDog-0.23.2-source.zip.sha256`
  - `MCP_CREO_MechDog-0.23.2-seed-library.zip`
  - `MCP_CREO_MechDog-0.23.2-seed-library.zip.sha256`
- 实际发布结果只回填到 `main` 的 POSTCHECK `## v0.23.2` 段与本段，不回写包内快照。
- 源码包解压到 `E:\r0232\MCP_CREO_MechDog` 后，把该目录临时 editable 安装到本机 venv 并运行 `python -m unittest discover -s tests`：`Ran 3463 tests in 479.169s`、`OK (skipped=6)`、exit 0；随后已把 venv 恢复到 `E:\Projects\MCP_CREO_MechDog`。包内 `test_standard_install_supports_import_from_unrelated_working_directory` 等 5 项依赖“当前源码目录就是安装目录”，未切换安装前会失败，属测试环境约束而非产品缺陷。

## 逐 ID 状态核对

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 差异说明 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [BUG-120](../work-items/BUG-120.md) | 诊断与披露已编译、单测通过；Creo 10 运行期仍不可用 | 0.23.2（诊断子项） | 模板 XML/`FromXMLCreate`、STEP/IGES 导入 | 部分交付 0.23.2 | 部分交付，剩余待规划 | 无 | 已列入 | 已列入 | `v0.23.2` |
| [DEV-083](../work-items/DEV-083.md) | 状态一致性与链接门禁已接入打包/核对 | 0.23.2（子项） | RELEASING 永久链接规则 | 部分交付 0.23.2 | 部分交付，剩余待验收 | 无 | 已列入 | 已列入 | `v0.23.2` |

## 相对上一正式包核对（上一版本：0.23.1）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party` 原字节（含 `json.hpp`、第三方许可） | 0.23.1 源码包 | 未改动 | 无需重新注册 |
| 回调指纹（`sha256-repo-lf-v1`） | 0.23.1 源码包 | 未改动 | 无需重新注册 |
| loader DLL SHA256 | 未单独留存 | 未单独留存 | 本版未改 loader；安装后随 worker 重建 |
| callback DLL SHA256 | 未单独留存 | 未单独留存 | 本版未改 callback；安装后随 worker 重建 |
| worker SHA256 | 未单独留存（0.23.1 由源码重新编译） | 由本次源码重新编译 | 本版含 `native/surface_loft.cpp` 变更，升级后必须重建 |
| `protk.dat` / 注册表路径 | 0.23.1 | 未改动 | 无需迁移 |
| 实际注册影响 | — | — | 需重新编译并重启 worker；DLL 注册路径不变 |
