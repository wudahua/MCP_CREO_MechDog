# 0.23.2 版本说明（2026-11-13）

PATCH 版本。Creo 10 运行期 `surface_loft` 创建成功但元素树不可提取的问题改为明确诊断；同样的内核观测进入能力表但只披露、不改变准入；发布记录门禁补逐 ID 状态一致性与发布文档本地链接检查。公开工具仍 107，无新增工具或参数。

## 诊断（BUG-120）

- 现象（报告方 Creo 10.0.0.0 + 匹配 SDK）：`surface_loft` 的 `ProFeatureWithoptionsCreate` 返回 0，随后 `ProFeatureElemtreeExtract` 返回 `-18`、`feature_incomplete=true`，`ProElemtreeVerify=-2`；两个提取器与 GUI 手工创建的同类特征同样失败。
- 本轮处理：`native/surface_loft.cpp` 在创建成功后、提取之前读取 `ProFeatureIsIncomplete`；提取失败时回执新增 `extract_unsupported=true`、`kernel_completion="unsupported"`、`kernel_evidence`（`release_numeric`、`create_code`、`extract_code`、`feature_incomplete`），错误文案带 `SURFACE_LOFT_EXTRACT_UNSUPPORTED` 与 `release_numeric`，作业照旧回滚。成功分支写 `extract_unsupported=false`、`kernel_completion="supported"`。
- 能力披露：`bridge.py` 按当前 worker SHA 把最近一次 `surface_loft` 观测写入 `build/toolkit_health.json`；`creo_session_status` 与 `creo_capabilities` 的 `worker_build_identity.features.surface_loft` 显示 `kernel_completion`，没有观测或 worker 不匹配时为 `unknown`。`available`/`enabled` 不变，提交前不因此预拒绝。
- 未做：模板 XML/`FromXMLCreate`、STEP/IGES 导入，以及任何让 Creo 10 回读该特征的新通道。

## 发布记录门禁（DEV-083）

- 状态归一化为 `delivered / partial / developing / unplanned / other`；工作卡只读首页 `分类：` 行的粗体状态。
- 逐 ID 表检查「技术状态」「卡首页」「主台账」与工作卡状态；「主台账」列必须与真实台账单元格逐字一致；允许「差异说明」列显式记录保守措辞差异。
- 扫描主台账所有 `work-items/` 活动行中状态类为 `partial`/`delivered` 的 ID，不只检查发布记录表；归档行跳过。
- 新增发布说明、发布记录与 POSTCHECK 的本地相对链接检查，根模式与源码 ZIP 模式都执行；外链、纯锚点与站点绝对路径跳过，逃出包根的链接直接拒绝。
- `tests/unit/test_release_records.py` 扩到 15 项，覆盖部分交付+已交付卡、差异说明放行、主台账列不一致、发布表外全表扫描、断链与 ZIP 内断链。

## 反馈归档

`docs/validation/feedback-0.23.0-2026-11-12/` 保存 0.23.0 目录四份报告的原件副本、字节与 SHA256 清单及逐项映射，原件逐字节不变。

## 验证

### 离线与编译

- `bridge.py build` 成功，`surface_loft` 为 `compiled`。
- `tests/unit/test_surface_loft_extract_diagnostic.py` 5 项通过：完整性读取位于创建之后、提取之前，提取前不提前拒绝，失败回执字段与回滚文案、成功字段。
- `tests/unit/test_surface_loft_runtime_observation.py` 9 项通过：观测写入与保留、worker 不匹配、匹配、缺观测、非 `surface_loft` 回执忽略、能力投影披露与默认 `unknown`。
- `tests/unit/test_release_records.py` 15 项通过；真实历史文档 `tools/check_release_records.py --version 0.23.1` exit 0。
- `tools/dev_check.py --work-item BUG-120`：`success=true`，`Ran 3463 tests in 472.553s`、`OK`；风格 `lint_findings=21`、`unformatted_files=9`，与基线一致，无新增回归。
- `tools/check_release_records.py --version 0.23.2` exit 0；`tools/check_backlog_counts.py` 为 180 / BUG 79 / FEAT 63 / DEV 38，声明、表行与分类表一致。
- 源码包解压到短路径后切换 editable 安装并运行 `python -m unittest discover -s tests`：`Ran 3463 tests in 479.169s`、`OK (skipped=6)`、exit 0；随后恢复本机 venv 安装。

### 实机

本批未连接 Creo、未执行实机回归（未取得本轮当次授权），按离线批次发布。Creo 12.4.0.0 上 `kernel_completion="supported"` 的实际观测与几何/保存重载结论未在本版重新取得；0.23.1 的实机结果只属于 0.23.1，不外推为本版通过。

## 未测范围

- 本批未连接 Creo：Creo 12.4.0.0 实机回归（含 `kernel_completion="supported"` 观测）、几何与保存重载均未执行；0.23.1 实机结论不外推。
- Creo 10 运行期成功路径（本机无 Creo 10 SDK）；报告方的零补丁编译与运行期 `-18` 为报告方实测，本机未复现。
- 模板 XML/`FromXMLCreate`、STEP/IGES 导入与新提取通道。
- Creo 9 仍只有编译探测，无运行期证据。
- 非毫米单位、WorkBuddy 黑盒。

## 附件

- `MCP_CREO_MechDog-0.23.2-source.zip` 与 `MCP_CREO_MechDog-0.23.2-source.zip.sha256`
- `MCP_CREO_MechDog-0.23.2-seed-library.zip` 与 `MCP_CREO_MechDog-0.23.2-seed-library.zip.sha256`

种子包 SHA256：`4a47a58293f773d530c7ab2a771db075f3557222a207fb5dcff853594e66861a`。`source.zip` 的摘要见同名 sidecar 与 Release 正文，不写入包内文件。发布记录见 [RELEASE-0.23.2](validation/RELEASE-0.23.2.md)。
