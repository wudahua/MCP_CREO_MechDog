# MCP_CREO_MechDog 0.49.0 版本说明

2026-11-28 MINOR，公开工具数 112。上一版本：0.48.4（`v0.48.4`，提交 `48eb2586e8592fd20fb79df54ac4f7e6e3125d4b`）。

- **BUG-198**：修复 Windows JSON 原子替换把缺失目标或瞬时 `stat` 锁误判为永久 WinError 5 的缺陷，`bridge.py` 与 `panel_session_guard.py` 增加只读属性精确判别、`4.0 s / 100` 次替换重试与 `.tmp` 重试清理。
- **BUG-199**：修复 `run-job` runner 生命周期与面板解锁自锁：`desktop_worker.py` / `bridge.py` 支持经 Explorer 脱离 Job Object 并以 `IsProcessInJob` 核验（同时防护 `tid == 0` 跨桌面句柄），无法脱离时诚实上报 `runner_detached_from_job=false` 与保持连接提示；`creo_get_job` 公开 `owner_liveness`，`creo_cancel_job` 按 `runner_identity.pid` 终止并处理 `returncode=128`，`reconciliation` 对启动前已死 runner 与全部所有者已停的面板作业开放恢复与 `confirm_panel_closed`，`CreoStartup` 单独分类 `PanelSessionLocked`，`native/panel_run.h` 等待 `Done` 超时后记录可读模态框观测。
- **BUG-200**：消除 `adopt` / `open_file` / `session_*` 硬编码 115 s 超时，改为可配且按模型体积与特征数自适应的 `utility_worker_timeout_seconds`（300–3600 s），为 `creo_adopt_current_model` / `creo_adopt_file` / `creo_open_file` 新增可选 `timeout_seconds` 并在超时后终止 worker 落盘证据。
- **BUG-201**：统一 `creo_capabilities` 中 `direct_blend_callback.readiness` 与 `families.loft` 观测口径，消歧 `creo_callback_status` 启动态（`startup_in_progress=True`），强制服务端 stderr 使用 UTF-8 容错编码，并补全 `Rectangle`（`corner1`/`corner2` → `min`/`max`）、`through_points` 与 `legacy_snapshot` `refresh_hint` 提示。
- **FEAT-093**：`ExtrudeOp` 与 `creo_extrude` 新增双向不等深 `depth2`（`PRO_EXT_DEPTH_FROM_BLIND` / `PRO_E_EXT_DEPTH_FROM_VALUE`），回读 `effective_depth2_mm` / `effective_total_depth_mm` 并纳入 `cut_volume_check`；`creo_inspect_model` `datum_planes[]` 新增输出 `name` 与 `feature_id`；`known_limitations.cut_scope` 补充实体级作用域说明。

验收环境为 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）。未测范围：交互桌面 `WinSta0\Default` 经 Explorer 脱离 Job Object 的真实客户端断连保活、`native/panel_run.h` 真实模态框卡死与真实杀软/索引器并发锁现场、6 MB / 589 特征级超大外部零件超时加载、Creo 9 / 12.4 及外部 WorkBuddy 黑盒验收。[发布记录](../validation/RELEASE-0.49.0.md)

## 附件

- `MCP_CREO_MechDog-0.49.0-source.zip`
- `MCP_CREO_MechDog-0.49.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.49.0-seed-library.zip`
- `MCP_CREO_MechDog-0.49.0-seed-library.zip.sha256`

种子包 SHA256 为 `5d9a92e4162c2580cd2f173d56818cea50c46657e1b85cf842f998ca76cf0eaa`。源码包和种子包的摘要分别记录在同名 sidecar。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.49.0)
