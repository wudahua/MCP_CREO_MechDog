# 发布记录 v0.49.0

2026-11-28 MINOR，公开工具数 112。上一版本：0.48.4（`v0.48.4`，提交 `48eb2586e8592fd20fb79df54ac4f7e6e3125d4b`）。

## 验收范围

交付 0.47.1 / 0.48.3 两份外部反馈原件（已逐字节归档至 [feedback-0.47.1-0.48.3-2026-11-27](feedback-0.47.1-0.48.3-2026-11-27/SOURCE_MANIFEST.json)）对应的 [BUG-198](../work-items/BUG-198.md)、[BUG-199](../work-items/BUG-199.md)、[BUG-200](../work-items/BUG-200.md)、[BUG-201](../work-items/BUG-201.md) 与 [FEAT-093](../work-items/FEAT-093.md)。

本机 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK 实机验证通过（`worker_sha256=73354279ce7016b3573f37a50213dc55439078d6f40dc7c96b83f0a0b07073c1`）：

- **FEAT-093 双向不等深拉伸与基准面名称**（模型 `0c347e63075942eba0f290462c903df7`、`part_sha256=32fcdc1d6698f3f5d4897178c7bedb3684835ed067a0621a9307044882511a91`）：增料 `depth=10.0, depth2=3.0` 实测 `volume_mm3=2600.0`、`bounding_box_mm.z=[-3.0, 10.0]`、`extrude_depth`（`effective_depth_mm=10.0`、`effective_depth2_mm=3.0`、`effective_total_depth_mm=13.0`）；`creo_inspect_model` `datum_planes[]` 返回 `PL_TEST_NAME`（`feature_id=78, id=79`）与 `RIGHT`/`TOP`/`FRONT`；后续双向切除 `depth=8.4, depth2=1.0` 实测终体积 `2449.6 mm³`（`material_removed_mm3=150.4`、`cut_volume_check.effective_depth_mm=9.4`），`saved_file_reloaded_and_verified=true`。
- **BUG-199 MCP stdio 生命周期、失联诊断与 cancel_job**：在隔离桌面 `WinSta0\exebox-*` Job Object 下，真实 `mcp` SDK `stdio_client` 提交作业 `3b515eb80f7b4b65a919d1ed91c344c1` 如实上报 `runner_detached_from_job=false` 与保持连接提示并完成 `succeeded/verified`（模型 `281310daa0894bb6bcf79ad1f5bda51e`）；客户端立即断开导致 runner 死亡的作业 `5ba519a99d06490a9f962823e026141b` 被 `creo_get_job` 识别为 `owner_liveness.all_recorded_owners_dead=true`，调用 `cancel_job`（`returncode=128`, `reason="process_not_found"`）清空 `pending_job` 与通道锁。
- **BUG-200 / BUG-201 能力与接口契约**：公开工具维持 112 个，`creo_open_file` / `creo_adopt_file` / `creo_adopt_current_model` 暴露 `timeout_seconds`，`creo_extrude` 暴露 `depth2`，`creo_capabilities(detail="compact")` 中 `direct_blend_callback.readiness` 与 `families.loft.runtime_admission.callback_readiness` 同构一致。

与直接前版 `0.48.4` 对照：`native/third_party/**` 与第三方许可及种子 PRT 原字节均未变化（仅更新兼容版本号为 `0.49.0`）；`native/generic.cpp`、`native/geometry.cpp`、`native/panel_run.h` 有更新并重编 `creo_worker.exe`；回调 loader 与 payload 源码及构建指纹不变，既有已注册回调无需重新注册。

制作源码包的条件是本轮全量单测通过，打包时核验报告、运行 ID 及提交对应的源码指纹。另执行 `tools/dev_check.py --skip-unit`、链接与计数检查，并在源码 ZIP 解包后独立运行 `tools/test_unit.py`。最终受测提交、命令、运行标识及结果见 Release 正文和[发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md)。

未测范围：交互桌面 `WinSta0\Default` 经 `explorer.exe` 脱离 Job Object（`runner_detached_from_job=true`）后的跨客户断连实机存活（已由单元测试覆盖）、`native/panel_run.h` 真实模态框卡死现场、真实 Windows 杀软/索引器并发文件锁、约 6 MB / 589 特征级超大外部零件实机加载超时、Creo 9 / 12.4 与外部 WorkBuddy 黑盒验收。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.49.0.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-198 | 0.49.0 | v0.49.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 修复 Windows JSON 原子替换瞬时 WinError 5 误判与 `.tmp` 清理重试，单测全过；真实索引器/杀软锁与 WorkBuddy 黑盒未测。 |
| BUG-199 | 0.49.0 | v0.49.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 交付 Job Object 实测与 Explorer 脱离、`tid==0` 防护、`owner_liveness`、`cancel_job` PID/128、`confirm_panel_closed` 死所有者解锁及模态框日志，Creo 10 断连清锁通过；`WinSta0\Default` 断连保活、模态框现场、Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| BUG-200 | 0.49.0 | v0.49.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 移除 115 s 硬超时，落地可配自适应 `utility_worker_timeout_seconds`（300–3600 s）与超时强杀证据，单测与 112 工具 schema 核对通过；大模型实机与 WorkBuddy 黑盒未测。 |
| BUG-201 | 0.49.0 | v0.49.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 统一 `direct_blend_callback.readiness` 口径、消歧 `startup_in_progress`、UTF-8 stderr 与提示完善，单测与契约通过；Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| FEAT-093 | 0.49.0 | v0.49.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 交付 `ExtrudeOp.depth2` 双向不等深拉伸、`datum_planes[].name` 及 `cut_scope` 边界说明，Creo 10 增/切与重载验收通过；Creo 9/12.4 与 WorkBuddy 黑盒未测。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.49.0-source.zip`
- `MCP_CREO_MechDog-0.49.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.49.0-seed-library.zip`
- `MCP_CREO_MechDog-0.49.0-seed-library.zip.sha256`

种子包 SHA256 为 `5d9a92e4162c2580cd2f173d56818cea50c46657e1b85cf842f998ca76cf0eaa`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.49.0)
