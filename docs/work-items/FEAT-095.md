# FEAT-095 状态轮询工具精简输出与回执体量量化

分类：**已有修复但待验收**。功能，P2，目标版本 `0.50.0`。基线为 v0.49.0 发布后回填提交 `949c7f6b`（衔接 `BUG-197`）。

来源：[0.48.3 反馈原件](../validation/feedback-0.48.3-2026-11-28/originals/recovery-and-modeling.md)（P10、P11）。

## 范围

- 为 `creo_startup_status`、`creo_session_status`、`creo_callback_status` 新增可选 `detail: "full" | "compact"` 参数（默认保持 `"full"` 以兼容既有调用方；是否切换默认值另作兼容性评估），新增 `src/creo_mechdog/status_projection.py`。
- `detail="compact"` 裁剪历史记录、`generation_inventory` 与冗长进程名单，始终保留 `state`/`readiness`、作业 ID、失败码、阻塞方、`panel_session_guard` 与下一步指引。

## 验收

- **实机体量量化（2026-11-28 Creo 10.0.0.0）**：
  - `creo_startup_status`：`15384 B → 1432 B`（缩减 90.7%）。
  - `creo_session_status`：`17205 B → 1216 B`（缩减 92.9%）。
  - `creo_callback_status`：`21709 B → 1863 B`（缩减 91.4%）。
  - 20 操作实机计划：`creo_execute_plan(response_detail="compact")` 返回 `1196 B`；`creo_get_job(detail="compact")`（含全量 20 个操作摘要与检验汇总）为 `21926 B`（控制在 32 KiB 预算内），`creo_get_job(detail="full")` 第 1 页为 `13729 B`（分页续取）。
- 单测：`tests/unit/test_v0500_feedback_0483.py::Feat095StatusCompactAndPlanBytesTests` 覆盖 `ready`、`busy`、`panel_session_locked`、`timeout` 与 `not_loaded` 五态并通过。
- 未测范围：WorkBuddy 外部客户端集成验收及默认参数变更兼容性评估。
