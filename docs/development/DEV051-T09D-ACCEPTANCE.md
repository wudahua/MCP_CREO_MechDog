# DEV-051 T09D 性能调查 — 离线准备记录

日期：2026-10-30。归属：DEV-051 / T09D（P3，顺序在 T13 之后）；性能基准工作沿用 FEAT-008/033、DEV-006/007，不新增工作 ID。对应派发表：[DEV051-CONTINUATION-TASKS-2026-10-30.md](DEV051-CONTINUATION-TASKS-2026-10-30.md)「T09D 性能调查」；对应计划：[2026-10-30-feedback-072-to-085.md](../superpowers/plans/2026-10-30-feedback-072-to-085.md) 任务 6。

**本文只记录离线准备（测量设计），不包含任何实测性能数据，不包含任何性能已改善的结论，不承诺提速比例。**

## 已知事实（全部为外部观测）

- 一个大模型（**约 1408 条边——是边的条数，不是零件数**）单 job 约 50–60 秒。来源为报告方的外部观感，未经分段计时。
- 目前**没有任何分段数据**：无法区分时间花在提交/查询、原生求解、检查还是保存重载。+9.78% 目标体积残差与旧装配快照属于报告方模型任务，不属于本条目（见计划比较基线行）。
- 通过 MCP 可观察的边界（由源码核对，2026-10-30）：generic job 清单只携带 `created_at` 与 `finished_at`（`generic_bridge.py` 提交时写入；`compact_job` 的 `started_at` 键对 generic 计划作业不会出现）；`native.log` 的 `PHASE=` 标记不带时间戳。

## 本次交付（离线阶段）

| 文件 | 内容 |
| --- | --- |
| `tools/test_plan_performance.py` | 默认离线的基准驱动：夹具定义、等价性校验、计时记录器、live 入口（双开关） |
| `tests/unit/test_plan_performance.py` | 驱动判定单元 30 例：布局、schema、等价、计时记录、摘要统计、不重提、拒绝覆盖 |
| 本文件 | 事实、口径、报告结构、实机待验步骤、未测范围 |

本次未修改任何生产逻辑、`native/`、`src/creo_mechdog/schema.py`；未构建执行器；未连接 MCP/Toolkit；未启动 Creo；未执行任何改动 git index 的命令。

### 离线自检输出

```
命令：.\.venv\Scripts\python.exe -m unittest tests.unit.test_plan_performance
结果：Ran 30 tests ... OK，退出码 0

命令：.\.venv\Scripts\python.exe tools\test_plan_performance.py
结果：OFFLINE ONLY ... offline_classes=2 validated
     synthetic_data=true not_a_benchmark=true (timing recorder check only)
     report=build\t09d_performance\20261030T080713_3f1d8c97\report.json
     LIVE NOT RUN: no performance measurement was produced or claimed.

命令：.\.venv\Scripts\python.exe -m ruff check tools\test_plan_performance.py tests\unit\test_plan_performance.py
结果：All checks passed!
```

离线报告中的计时记录器校验使用**构造的假时间戳**，报告内已标注 `synthetic_data=true`、`not_a_benchmark=true`；该部分只证明记录器算术与不可观测标注正确，不是任何测量。

## 输入层级定义（等价控制）

两组模型类 × 两种交付方式，共四类基准，每类独立重复 ≥3 次：

| 类别 | 夹具 | single（单操作计划） | batch（批量计划） |
| --- | --- | --- | --- |
| small | 60×60×5 mm 板 + 2 个 10×10×2.5 mm 矩形槽 | 2 个独立 job，各含 1 组 sketch+cut | 1 个 job，计划含 2 组 sketch+cut |
| large | 240×240×8 mm 板 + 96 个 12×12×3 mm 矩形槽（12 列×8 行，间距 20 mm） | 8 个独立 job，各切一行 12 槽 | 1 个 job，计划含 8 组 sketch+cut |

large 夹具以 96 个矩形槽瞄准外部观测的 ~1408 条边的**同一数量级**；实际边数是原生几何，离线不可知，live 时用 `creo_inspect_model` 的 `counts.edges` 实测记录，离线一律写 `measured_at_live_time`，不预测。

等价契约（两条同时成立该组计时才可比，否则该组判失败）：

- single 与 batch 对**同一几何规格**各建一个全新独立模型，终态体积都等于解析期望（small 17 500 mm³，large 419 328 mm³，容差 0.01 mm³），cut 特征增量相同（2 或 8），`counts.edges` 相同；
- 每个 job 都必须 `status=succeeded` 且 `saved_file_reloaded_and_verified=true`。保存重载与保护校验不放松、不减少。

**save/reload 事件次数在两种方式间天然不同**（single 为 N 次、batch 为 1 次），这是两条交付路径的组成部分，报告按 case 记录 `save_reload_events`，不做隐藏也不做抵扣。槽位开口方向：从 XY 草图面正向盲切，槽开在 z=0 底面；体积口径不受影响。

## 报告 json 结构说明

live 运行写入唯一时间戳目录 `build/t09d_performance/<run_id>/report.json`（run_id = 时间戳 + 8 位随机后缀），拒绝覆盖已存在报告；离线运行同目录结构。顶层字段：

- `external_observation`：50–60 s 观感、1408 条边口径、`phase_split: "none available yet"`。
- `protocol`：重复数、warm/cold 规则（本驱动会话第 0 个 Toolkit job 记 `cold`，其余 `warm`，逐 job 记录）、等价规则。
- `fixtures`：夹具全参数与解析期望（见上表）。
- `cases[]`：每个 case 含 `requested_scale`、`fixture`（建板 job 的计时，单独标注为 fixture_preparation）、`jobs[]`、`result`（体积/边数/revision 与期望比对）、`summary`、`passed`。
- `cases[].jobs[]` 每条记录：`job_id`、`model_id`、`status`、`session_job_index`、`warm_cold`、`timing`、`saved_file_reloaded_and_verified`；失败时附 `raw_error`（message/reason/reason_details/native_log_tail 原文，不改写）。
- `cases[].jobs[].timing` 每阶段：
  - 可观测：`submit_round_trip_s`（提交调用往返）、`poll_count`/`poll_call_total_s`（查询开销）、`client_total_s`（客户端全程）、`server_accept_to_terminal_s`（终态清单 `finished_at − created_at`，服务端钟）；
  - 不可观测（`value: null` + `status: "unobservable"` + 原因）：`queue_wait`、`executor_startup`、`native_solve`、`native_checks`、`save_reload`、`result_registration`。**一律 null，不估算、不插值、不填空。**
- `equivalence[]`：同 rep 的 single/batch 对照（体积、边数、job 数、save/reload 事件数、`comparable`）。
- `summary[]`：按（模型类 × 方式）分组，`median_s`/`min_s`/`max_s`（n 次独立重复），区分 `client_total_s` 与 `server_window_sum_s`，附 cold job 计数与通过 case 数。
- `provenance`：版本、commit、分支、dirty、全部源文件 SHA256 与指纹、环境。
- 离线报告另有 `synthetic_data`/`not_a_benchmark` 标注与 `observability` 清单。

## 实机计时口径（待验步骤，可直接执行）

前置（全部满足才允许开始）：

1. 按根级规范完成 BUG-001 会话可操作核对；实机由唯一负责人通过指向 E 盘项目的 `MCP_CREO_MechDog_dev` 串行执行；不擅自启动/结束 Creo、清 unknown、故障注入。
2. 本轮受测源码即当前 checkout；先记录 commit、dirty 与 `provenance.source_fingerprint`。

执行：

```powershell
# 在仓库根目录；默认 3 次重复 × {small,large} × {single,batch}，全程串行
.\.venv\Scripts\python.exe tools\test_plan_performance.py --live --confirm-session-usable
```

口径与记录要求：

- 每类（small/large × single/batch）**至少 3 次独立运行**（独立新模型），报告自动给出中位数与范围；如用 `--reps` 降次数，输出会显式提示偏离协议最小值，验收仍要求 ≥3。
- 逐 job 记录 warm/cold（首个 job 为 cold）、边规模（`counts.edges` 实测）、特征规模（cut 操作数/槽数）、`submit_round_trip_s`、`server_accept_to_terminal_s`、`client_total_s`。
- 阶段区分按报告口径：提交/查询可观测；**原生求解、检查、保存重载当前不可观测**，报告写 `unobservable`，不得由总耗时倒推拆分。
- 任何一组等价失败（体积、边数、save/reload 不齐）该组计时作废，只记失败与原始错误。
- 首次 unknown/busy/挂起立即停止新提交，保留现场，按 BUG-001 约定交接，不重提作业。

校准步骤（第一次实机后执行一次）：

1. 读报告中 large 各 case 的 `result.final_counts.edges`；若与 1408 相差超过约一半到一个数量级，先调整驱动内 large 夹具的 grid/pocket 参数（只改 `tools/test_plan_performance.py` 的夹具常量，不改生产逻辑）并重跑，直至边规模同数量级。
2. 校准前后的边数、参数与两次报告路径都记入本文档补充节，旧报告不删除。

## 尚未测什么（当前全部未测）

- **一切实机耗时**：四类基准、3 次重复、warm/cold 差异、中位数与范围——全部未执行；50–60 s 仍是唯一数据点且无分段。
- **原生求解、检查、保存重载的单独成本**：当前 MCP 接口与 native 日志不提供分段时间戳，属结构性不可观测；只有未来在原生侧或 job 清单中登记计时字段后才可分解（属后续条目，不在本轮）。
- large 夹具的实际边数是否落在 1408 同数量级：待第一次实机校准。
- 其他 Creo 版本/环境：本机 Creo 12.4.0.0 之外的任何环境未测，不外推。
- 队列/并发行为：不在本轮范围，边界仍归 BUG-009；本驱动全程串行单 job，不测并发。

## 风险

- 报告中 large 观测边数若远离 1408，则该夹具对外部观测的代表性有限，需要校准后结论才可引用。
- `warm_cold` 只按本驱动会话内第几个 job 分类，不控制服务冷启动/Creo 会话历史；跨会话对比要结合 provenance 与会话状态记录。
- single/batch 的 save/reload 次数差异使两条路径的差值天然包含 (N−1) 次保存重载成本；解读差值时必须对照 `save_reload_events`，不能直接归因为"批量更快"。
- 驱动轮询间隔 1 s，`client_total_s` 含最多 1 s 轮询粒度误差；服务端 `server_accept_to_terminal_s` 不受影响，两者都记录以便对照。
- 驱动本身的 Python 开销（JSON、记录）计入 `submit_round_trip_s` 与查询往返，量级估计远小于被测对象，但未经实测证明。
