# MCP_CREO_MechDog 0.50.0 版本说明

2026-11-28 MINOR，公开工具数 112。上一版本：0.49.0（`v0.49.0`，提交 `a98aff2969e0d1430319f6141a08ba33587d09a4`）。

- **BUG-202**：完善面板锁与无会话恢复准入。`creo_startup_status` 与 `creo_session_status` 在未知 `model_id` 起点均可返还 `model_id` 与先 `inspect` 后 `confirm_panel_closed` 步骤；活动持有者运行期间保留锁定并拒绝退役，持有者退出且作业入终态后可正常清理；Creo 未运行时 `restore_baseline`/`accept_live` 于 `before_native` 拒绝且保持原模型状态、`revision` 与 `pending_job`。
- **DEV-113**：重构 `tests/unit/test_startup_retry.py` 的 `test_new_retry_gets_new_id_even_within_same_clock_tick`，以显式 `threading.Event` 握手替换盲等 `join(2)`，消除并发负载下偶发线程未退出与重复探测；隔离 `2×60` 与双负载并发 `3×120` 压测均为 `0` 失败。
- **BUG-203**：分离草图公开 `weld_pairs` 与内部 `weld_plan`，提交前拒绝调用方传入非空 `weld_pairs`（不再静默覆盖）；`endpoint_weld` 回执分别上报 `snap_applied_pairs`、`welded_pairs` 与拒绝计数。Creo 10 上 40 弧 10 轮廓等价夹具验证 `weld+snap` 挤出 `184.9802 mm³` 并保存重载。
- **BUG-204**：定位 Creo 10 冷启动 `not_loaded` 根因为 `protkdat` `delay_start true`；`creo_startup_status`/`creo_session_status` 补充非阻塞 `callback_advisory`，`creo_callback_status` 在未加载态明确列出 `affected_operations`、`unaffected_alternatives` 与可执行 `recovery_steps`，与 `creo_capabilities` 及提交前准入一致。
- **BUG-205**：`capabilities.require_kernel_completion` 对 Creo 10（`release_numeric=42`）默认拒绝 `surface_loft` `creation_route="element_tree"`（含 `accept_unverified_completion=true`），零作业拦截并引导改用 `creation_route="resident_panel"`，同步在 `creo_capabilities` compact 口径清晰展示 `runtime_ready` 与阻断原因。
- **BUG-206 / FEAT-094**：`creo_list_seeds` 新增 `verified_combinations`、`missing_bundled_combinations`（明确列出 `5/straight` 缺失）与 `target_scope="new_part_only"`，保留 2–20 段显式种子入口；`FEAT-094` 划定 `creo_new_loft_part`（`new_part_only`）与已有零件 `creo_loft`（需已加载回调）边界并单列 7 截面/导线后续演进。
- **BUG-207**：修正草图 `profile_dimensioning_choice` 曲率实体 `selection_reason`，新增无约束轮廓 `autodim→coordinates` 失败清晰回退，并补齐 `coordinates` 下 `PRO_2D_ELLIPSE`（主轴半径/中心标注、`row["radii"]` 偏差快照与 Python schema）；Creo 10 混合圆弧三路与偏置椭圆（`max_deviation_mm=0.0`）全部保存重载通过。
- **BUG-208**：`BooleanOp` 与 `native/surfaces.cpp` `generic_boolean` 放行并核验 Creo 初始活动实体 `-5778`（`PRO_BODY_STATE_ACTIVE` 校验，拒绝空 `-5778` 与其他负数 ID），Creo 10 实机通过 `-5778 + 正 ID`、空 `-5778` 拒绝及 `正 + 正` 对照。
- **BUG-209**：在 `known_limitations` 前置披露单草图相切/分叉/相交限制（`sketch_tangent_or_intersecting_contours`），共享边/点接触/自交提交前拒绝并报冲突实体与位置，合法嵌套方环在 Creo 10 通过并重载。
- **FEAT-095**：新增 `creo_startup_status`、`creo_session_status` 与 `creo_callback_status` 的 `detail="compact"` 精简输出（实机缩减 90.7%–92.9%），并完成 20 操作计划序列化字节量化；默认仍保持 `"full"` 以向后兼容。
- **既有缺陷/增强实机复验（BUG-153 / FEAT-082）**：Creo 10 实机对比通用闭环 B 样条切除精确去除 `1049.9832 mm³`（理论 `1050.000 mm³`，误差显著小于 16/32/64 折线近似）；在 `creo_get_job` 文档补充多视角 `creo_export_model(format="jpeg", jpeg_options={"view": ...})` 指引并在 `120×60×30` 偏置特征件上验证 `top`/`right`/`back` 视图方向可辨。

验收环境为 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）。未测范围：隔离执行桌面无法交互操作 Creo GUI `Tools → Auxiliary Applications → Start`，故回调已加载态下 3 项（最小 `creo_loft`、`resident_panel` 100 mm² 曲面与同 `model_id` 已有零件追加）需在交互桌面手动启动回调后补验；原外部 `scripts/gear10.json`（仓库未附带）、Creo 9 / 12.4 与外部 WorkBuddy 黑盒验收单列未测。[发布记录](../validation/RELEASE-0.50.0.md)

## 附件

- `MCP_CREO_MechDog-0.50.0-source.zip`
- `MCP_CREO_MechDog-0.50.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.50.0-seed-library.zip`
- `MCP_CREO_MechDog-0.50.0-seed-library.zip.sha256`

种子包 SHA256 为 `b0f87bb3eac0240f66147d417c84e3e34661b283c0b1e8e8e3e3c0a6c85dc6da`。源码包和种子包的摘要分别记录在同名 sidecar。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.50.0)
