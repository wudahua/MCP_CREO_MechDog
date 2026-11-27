# FEAT-073 有界批量质量属性查询

分类：**已交付 0.35.6**（满批、真实占用、真实超时均已验证）

类型：功能。优先级：P2。目标版本：0.35.6（已交付）；WorkBuddy 黑盒与 Creo 9/12 未排期。

并发读操作触发 busy 符合 BUG-009。评估一次准入内有界串行、逐实例结果、单项失败与时间预算，保留现有独立请求 busy 语义。先用 mock 验证数量上限、单项失败和混合有效/无效输入，再用 Creo 实机和 WorkBuddy 验收。依赖 FEAT-057 公共口径。

来源：[本批反馈计划](../archive/development/0.35.0-FEEDBACK-PLAN-2026-11-21.md)。

## 目标与范围

一次调用读取多个受管模型的质量属性，同时保持单 Toolkit 通道的既有语义：不加并发、不排队、不改写独立的 busy 拒绝。调用方拿到的仍是 FEAT-057 的逐项回执，而不是一锅端的总和，因此一个坏模型不会抹掉已经测到的读数。

## 2026-11-22 实现（0.35.0 反馈 T10）

分支 `codex/bug-144-release-evidence-plan`（基线 `98c598f`）。新增公开工具 `creo_get_mass_properties_batch`，公开工具数 110→111。

- **边界在提交前**：`model_ids` 1–16 项，超出或重复在创建任何作业前拒绝（`model_ids accepts at most 16 models per call`、`model_ids repeats <id>`）；`time_budget_seconds` 10–600，缺省 180。上限与 `capabilities.families().mass_properties.batch.limits` 同源，单测比对两者。
- **串行、一项一作业**：每项仍走一次只读 `mass_properties` 作业（`submit(..., readonly=True)`），逐项轮询到终态后返回。调用内不并发，外部请求照旧得到声明过的 busy 错误（BUG-009），没有引入 FIFO 或容量承诺。
- **逐项回执**：成功项与单模型工具同形（`job_id`/`model_id`/`revision` 加归一化读数），另带 `status=succeeded`；失败项为 `status=failed` 加 `error_kind`（`invalid_request`/`query_failed`/`toolkit_busy`/`timeout`）、`error` 原文与 `blocking_job_id`（仅 busy 时非空）；未执行项为 `status=skipped` 加 `reason`。汇总给出 `requested`/`succeeded`/`failed`/`skipped`/`all_succeeded`/`time_budget_seconds`/`elapsed_seconds`。
- **单项失败不吞掉其它项**：无效或未知 model id、原生查询失败只影响该项，后面的模型继续读取；`all_succeeded` 保持 false，部分结果不会被当成完整成功。
- **时间预算**：剩余预算不足 5 s 时不再启动新项，剩余项标 `time_budget_exhausted`；单项等待取 `min(120 s, 剩余预算)`。通道被占用时该项失败为 `toolkit_busy` 并停止后续项（不反复撞 busy）；等待被预算截断时按 `time_budget_exhausted` 记，而不是冒充单项超时——被截断的作业可能仍在运行，继续提交只会撞 busy。
- **只读**：`density_g_cm3` 是逐项显式 what-if，每项回执仍自报 `density_source`；批处理不改 revision、不写源文件。
- 能力清单补 `mass_properties.batch`（工具、逐项形态、上限、部分失败口径、并发口径）；`server.invoke` 对批处理先做一次就绪检查，避免未就绪时把同一错误重复 16 次。

## 验收与证据

- 新增 `tests/unit/test_feat073_batch_mass.py` 14 项：一模型一作业与归一化回执、无密度时不带 what-if、17 项与重复项提交前拒绝、空/非字符串输入、预算范围、混合有效/无效输入、单项查询失败后继续、busy 停止并带 `blocking_job_id`、单项超时跳过其余、预算耗尽跳过、被截断等待记为预算结束、汇总计数、能力清单边界与代码一致。
- 公开工具数 110→111：`test_t01_capability_contracts`、`test_reference_contract`、`test_callback_admission`、`test_surface_boundary_fill_contract`、`test_surface_curvature_contract`、`test_surface_round_contract`、`test_update_check`、`test_modeling_candidate_gates` 同步；README 的静态工具数改为以 `creo_capabilities.tool_count` 为准。
- 全量离线单测 `build/unit_test_t10_clean.json`：4,360 项、0 失败、0 错误、6 跳过，受测源码指纹 `69ce420b…`（654 个文件）；`tools/dev_check.py --skip-unit --work-item FEAT-073` `success=true`，Ruff 0 发现、0 文件待格式化（573 个 Python、69 个 C++），两项离线 stdio 验收通过。
- 实机 Creo 10.0.0.0（`build/live_t10_batch_mass.py`，15/15）：两件已知体积零件（4000 mm³、1000 mm³）一次批量 `requested=2/succeeded=2`、`all_succeeded=true`、`elapsed_seconds=16.172`、预算 180 s，两个 `job_id` 不同，体积 `3999.9999999999995` 与 `999.9999999999999`，面积 2200/700；`creo_get_job` 能按项取回同一作业（`succeeded`、模型与 revision 相符）。
- 同一现场混入坏输入：`[A, "not-a-model", "0"*32, B]` 得 `succeeded=2/failed=2/skipped=0`、`all_succeeded=false`，顺序保持，两条失败分别为 `invalid_request`「Invalid model_id」与「Unknown model_id; use creo_new_part or creo_execute_plan」，两个好模型仍有完整读数。
- 上限与重复在公开工具层即被拒：17 项返回「List should have at most 16 items after validation, not 17」；重复项返回「model_ids repeats …; one receipt per model keeps the batch unambiguous」。
- 只读：`density_g_cm3=7.85` 的批量得 31.399999999999995 g 与 7.849999999999999 g、`density_source=request`、几何不变；两件零件在全部四次批量前后 revision 均为 2。
- 未验证：WorkBuddy 黑盒、Creo 9/12；单项等待耗尽**完整** 120 s 窗口的分支仍只有离线覆盖（本机造不出超过 120 s 的查询）。

## 2026-11-22 实机补验：满批、真实占用、真实超时

同一现场（Creo 10.0.0.0，`build/live_t10a_full_batch.py`，11/11 检查通过）：新建 16 个已知体积零件（宽 10–25 mm、高 10 mm、深 5 mm，体积 500–1,250 mm³）。

- **满批 16 项**：`requested=16/succeeded=16/failed=0/skipped=0`、`all_succeeded=true`、`elapsed_seconds=131.188`，默认预算 180 s 下**余量 48.812 s**，16 个 `job_id` 互不相同，16 项体积逐项与各自盒体一致。本机单项目均 8.199 s（含提交与轮询），即默认预算按 16 项小零件估算够用，但余量只有 27%；更大装配或更慢机器应显式提高预算。
- **真实通道占用**：一个 6 项批量正在跑时并发第二个 2 项批量。占用方 6/6 成功；被拒方的第一项 `error_kind=toolkit_busy`，`blocking_job_id=7dc54191…`，该记录查回为 `succeeded` 且模型属于占用方，第二项 `skipped/toolkit_busy`——占用与停止后续项都是真实通道行为，不是 mock。
- **真实在飞超时**：预算 14 s、3 项。第一项 8.36 s 成功后剩余 5.6 s（≥5 s 最小项窗口），第二项等待被截断为 5.6 s 而查询未完成 → 该项 `error_kind=timeout`、`Mass properties query did not finish: job 07e6f30d…`，第三项 `skipped/time_budget_exhausted`，客户端总耗时 14.188 s。判定当时该作业记录确为 `running`。
- **超时作业本身可完成**（`build/live_t10a_timeout_followup.py`）：同预算复跑，被判超时的作业在等待结束后 **3.06 s** 自行到达 `succeeded`，体积 700 mm³（14×10×5），revision 1——证明超时是「窗口不够」而不是查询坏掉。
- **新发现 → 已立 [BUG-149](BUG-149.md)（P1，修复已随 0.35.7 发布并取得 Creo 10 实机闭环）**：客户端在作业未终结时退出，会留下 `unknown_outcome` 的只读作业记录（`termination.attempted=false`、`reason=no_runner_pid`）；该模型随后的质量查询被以 `toolkit_busy`「Model has a pending job」拒绝，`creo_cancel_job` 因作业已终态无法清除。只读查询本不该需要模型级恢复：修复后只读作业在所有不确定出口都不写 `pending_job`，`creo_cancel_job` 以元数据方式释放历史占用，inspect 报 `readonly_pending`。
