# 发布记录 v0.50.0

2026-11-28 MINOR，公开工具数 112。上一版本：0.49.0（`v0.49.0`，提交 `a98aff2969e0d1430319f6141a08ba33587d09a4`）。

## 验收范围

交付三份 0.48.3 外部反馈原件（已逐字节归档至 [feedback-0.48.3-2026-11-28](feedback-0.48.3-2026-11-28/SOURCE_MANIFEST.json)）对应的 [BUG-202](../work-items/BUG-202.md)–[BUG-209](../work-items/BUG-209.md)、[DEV-113](../work-items/DEV-113.md)、[FEAT-094](../work-items/FEAT-094.md) 与 [FEAT-095](../work-items/FEAT-095.md)，并完成 [BUG-153](../work-items/BUG-153.md)、[FEAT-082](../work-items/FEAT-082.md) 与四项回归对照实机验证。

本机 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK 实机验证（最终原生 `worker_sha256=3b96c175d735941e804c2444db005eb177edcd57c55fc0f495b0ce6aeb6e4469`）：

- **第一批（崩溃恢复 / 重试单测 / 端点焊接）**：
  - **BUG-202**：面板锁场景（模型 `835c261b854b476a971401a5373d40be`）从未知 `model_id` 起点调用 `creo_startup_status` 与 `creo_session_status` 均提示 `panel_session_locked`、`model_id` 与恢复步骤；活动 PID 持有期间 `confirm_panel_closed` 被拒，退出后成功退役保护；停止 `xtop.exe` 且零 worker 下 `restore_baseline`/`accept_live` 均在启动恢复 worker 前拒绝（`before_native` / `no_creo_session`），原状态、`revision=1` 与 `pending_job` 完整保留。
  - **DEV-113**：`tests/unit/test_startup_retry.py` 改为显式 `threading.Event` 同步，干净隔离 `2×60`（120 次）与并发双负载 `3×120`（360 次）压测两类失败均为 `0`。
  - **BUG-203**：40 弧 10 轮廓等价夹具（深度 `0.353352 mm`）实机验证显式 `weld_pairs` 提交前报错、仅 `endpoint_policy="weld"` 拒绝、`weld + snap_endpoints=true + max_endpoint_move_mm=0.01` 成功（`snap_applied_pairs=40`、`welded_pairs=0`、`volume_mm3=184.9802`、`saved_file_reloaded_and_verified=true`）。
- **第二批（Creo 10 放样专项预加载与种子矩阵）**：
  - **BUG-204**：核对 `config.pro`（已持久化 `protkdat`）与 `build/blend_callback_protk.dat`（含 `delay_start true`），重启冷启动 Creo 10 实测 `creo_startup_status`/`creo_session_status` 的 `callback_advisory`、`creo_callback_status`（`readiness="not_loaded"`, `affected_operations`, `unaffected_alternatives`, `recovery_steps`）、`creo_capabilities(compact)`（`runtime_ready=false`）及 `creo_loft` 提交前拦截（`BLEND_CALLBACK_SETUP_REQUIRED`）完全一致。
  - **BUG-205**：Creo 10 上 `creo_surface_loft` 指定 `creation_route="element_tree"` 时，`accept_unverified_completion=false` 与 `true` 均在队列前直接拒绝并指向 `resident_panel`。
  - **BUG-206 / FEAT-094**：`creo_list_seeds` 返回精确 9 组 `verified_combinations`、`missing_bundled_combinations=[{"section_count": 5, "interpolation": "straight"}]` 与 `target_scope="new_part_only"`；`5/straight` 提交前拒绝、`2/straight` 新建件（`5b2f628c3dcb404ab32d586131144424`）实测 `3500.0 mm³` 并重载通过。
- **第三批与回归对照**：
  - **BUG-207**：混合圆弧槽口在 `auto`（`autodim_preferred_for_curved_entity`）、`coordinates` 与 `autodim` 三路均通过并重载（`1392.6991 mm³`）；偏置椭圆（`center=[18, -12], x_radius=24, y_radius=11, depth=8`）在 `coordinates` 下 `SKETCH_SOLVE=0`、`SectionRegenerate=0`、`max_deviation_mm=0.0`，体积 `6635.0333 mm³`、重载通过；`(0, -0.092)` R3 自动圆心回归实测 `282.7433 mm³`、重载通过。
  - **BUG-153**：闭环 B 样条切除对比理论去料 `1049.9997 mm³`，精确 `b_spline` 去料 `1049.9832 mm³`（误差 `-0.0165 mm³`，`saved_file_reloaded_and_verified=true`），优于 `poly_16`/`32`/`64`（误差 `-4.88` / `-1.22` / `-0.30 mm³`）。
  - **BUG-208**：活动 `-5778` + `id=135` 并集成功（`feature_id=161`，体积 `5750.0 → 4625.0 mm³`，1 实体，重载通过）；空 `-5778` 按 `BOOLEAN_BODY_NOT_FOUND` 拒绝；`正 + 正` 并集（`12000.0 mm³`）重载通过。
  - **BUG-209**：共享边、仅点接触、自交领结三例均于提交前报错并指出冲突实体；嵌套方环挤出 `1680.0 mm³` 重载通过。
  - **FEAT-095**：实测状态工具 `detail="compact"` 字节从 `15384/17205/21709 B` 降至 `1432/1216/1863 B`（-90.7%～-92.9%），20 操作计划 `submit compact=1196 B`、`get_job compact=21926 B`（< 32 KiB）。
  - **FEAT-082 与其余回归**：`120×60×30` 偏置零件 `top`/`right`/`back` JPEG（800×600）方向可辨、`solid_face_tessellation` 包围盒 `[120, 60, 45]`、重复加料 `5000.0 mm³` 及 5° `draft` `flip=false/true`（`12174.98`/`11825.02 mm³`、`added`/`removed`）全部保存重载通过。

与直接前版 `0.49.0` 对照：`native/third_party/**`、第三方许可与种子 `.prt` 原字节均未变化（仅更新 `compatible_server_version` 为 `0.50.0`）；更新了 `native/blend_create.cpp`、`native/generic.cpp`、`native/sketch_coordinates.cpp`、`native/sketch_solver.cpp` 与 `native/surfaces.cpp` 并重编 `creo_worker.exe`；新增 `src/creo_mechdog/status_projection.py` 与 `tests/unit/test_v0500_feedback_0483.py`。

制作源码包的条件是本轮全量单测通过，打包时核验报告、运行 ID 及提交对应的源码指纹。另执行完整 `tools/dev_check.py`（含风格、链接、计数、契约门禁），并在源码 ZIP 解包后独立运行 `tools/test_unit.py`。最终受测提交、命令、运行标识及结果见 Release 正文和[发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md)。

未测范围：1）隔离执行桌面（`EnumWindows count=0`）无法操作交互式 Creo GUI `Auxiliary Applications → Start`，因此 `BUG-204` 回调已加载后最小 `creo_loft`、`BUG-205` `resident_panel` 100.0 mm² 新增曲面、以及 `FEAT-094` 同 `model_id` 已有零件 `creo_loft` 追加与失败回滚需在交互桌面启动回调后补验；2）原外部 `scripts/gear10.json`（仓库未附带）；3）Creo 9 / 12.4 实机、真实 `autodim→coordinates` 运行期失败样本与外部 WorkBuddy 黑盒验收。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.50.0.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-202 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 完成未知 `model_id` 面板锁提示、活动持有者防护/退役及无 Creo `restore_baseline`/`accept_live` 拒绝且状态保留实机；Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| BUG-203 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 分离公开 `weld_pairs` 与内部 `weld_plan`，40 弧等价夹具三组实机通过；原外部 `scripts/gear10.json`、Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| BUG-204 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 定位 `delay_start true` 根因并完成冷启动 `not_loaded` 全链路一致性与引导字段实机；交互桌面启动回调后最小 `creo_loft`、Creo 9/12.4 与 WorkBuddy 未测。 |
| BUG-205 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 完成 Creo 10 `element_tree`（含 `accept_unverified_completion=true`）零作业前置拒绝与能力页披露；交互桌面启动回调后 `resident_panel` 100 mm² 实机、Creo 9/12.4 与 WorkBuddy 未测。 |
| BUG-206 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 完成精确 9 组合与 `5/straight` 缺失披露、`new_part_only` 标注及 `2/straight` 实机；Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| BUG-207 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 修正混合弧提示、补 `autodim→coordinates` 回退及 `coordinates` 椭圆标注与 `row["radii"]` 偏差快照并 Creo 10 通过；运行期真实失败回退样本、Creo 9/12.4 与 WorkBuddy 未测。 |
| BUG-208 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 完成活动 `-5778` 并集（`4625.0 mm³`）、空 `-5778` 拒绝及正+正并集实机；Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| BUG-209 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 完成 `known_limitations` 披露、3 组冲突轮廓前置拒绝与嵌套方环 Creo 10 实机；Creo 9/12.4 与 WorkBuddy 黑盒未测。 |
| DEV-113 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 改用显式事件握手消除 `test_startup_retry.py` `join(2)` 竞态，隔离 `2×60` 与并发 `3×120` 压测 `0` 失败；待托管 CI 复核。 |
| FEAT-094 | 0.50.0 | v0.50.0 | 部分交付，剩余待规划 | 部分交付，剩余待规划 | 部分交付，剩余待规划 | 已划定 `new_part_only` 与已有零件 `creo_loft` 边界，单列后续免回调追加与 7 截面/导线能力；已加载回调下同 `model_id` 追加实机需在交互桌面补验。 |
| FEAT-095 | 0.50.0 | v0.50.0 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 新增三状态工具 `detail="compact"`（体量缩减 90.7%–92.9%）与 20 操作计划体量量化；WorkBuddy 黑盒与默认值切换评估未测。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.50.0-source.zip`
- `MCP_CREO_MechDog-0.50.0-source.zip.sha256`
- `MCP_CREO_MechDog-0.50.0-seed-library.zip`
- `MCP_CREO_MechDog-0.50.0-seed-library.zip.sha256`

种子包 SHA256 为 `b0f87bb3eac0240f66147d417c84e3e34661b283c0b1e8e8e3e3c0a6c85dc6da`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.50.0)
