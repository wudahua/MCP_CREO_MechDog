# MCP_CREO_MechDog 0.47.1 反馈：作业无法到达终态（stdio 断开致 runner 即死 / 面板路线 Done 不返回），并连带锁死模型与会话

> 文件名沿用首次交付时的核心问题（`runner随stdio会话断开即死…`）。本轮补录了同一根因下的第二种形态：**resident_panel 路线 Done 永不返回，作业永久 `running`，并由会话级面板锁把整条工具链锁成死循环**——见 §6.6。

- 反馈日期：2026-11-27
- MCP 版本：**0.47.1**（`creo_server_info.version = "0.47.1"`，`tool_count = 112`）
- 原生 worker：`build/creo_worker.exe` **12,093,440 字节**，`sha256 = 7ad76c08d75c7b2492aa5e8ad652719633867c6b80491d9c1a62eeb6c5ea9bce`
- Creo：Parametric **10.0.0.0**，`release_numeric = 42`，`parametric.exe` pid 15104 / `xtop.exe` pid 19976
- 客户端：Python `mcp` SDK，stdio 传输（`server.py` via `.venv\Scripts\python.exe`）
- 被测模型：`frigate_v4`，`model_id = df7f74bf5e424dbeb00605e218be89ad`，`revision = 106`

---

## §0 结论摘要

| 编号 | 问题 | 严重度 | 本轮判定 |
|---|---|---|---|
| **A** | `creo_execute_plan` 的 detached runner 随 stdio 会话断开一起死掉，作业永久停在 `status=queued / stage=waiting_for_channel` | **阻断** | **新增，100% 复现（A/B 对照）** |
| **B** | A 的结果无出口：`creo_cancel_job` 不置终态，`creo_reconcile_model` 9 个 action 全拒，最后只剩 `previous_boot_evidence()` 要求作业时间戳早于 Windows 启动 → **只能重启 Windows** | **阻断** | **新增** |
| **C** | `ExtrudeOp` 只有单一 `depth` + `symmetric`，**没有双向不等深**；IR 里 `depth1 ≠ depth2` 极常见，导致本工程 Boss-Extrude35 少建一半厚度 | 高 | **新增**（并据此给 D19 定性） |
| **C2** | `creo_adopt_file` / `creo_open_file` 的 native worker 超时**硬编码 115 s**，本工程 589 特征 / 6 MB 的零件必然超时 → `unknown_outcome` → 模型永久 `adopt_pending` | **阻断** | **新增**（`adoption.py:29`、`open_file.py:23`） |
| **C3** | 切除缺少「特征级范围」：`ExtrudeScope` 只支持 `kind:"bodies"`，单 body 模型无法复现「只作用于指定对象」，实测多切 ≈4 570 mm³ | 中 | **新增** |
| **D** | `surface_boundary_fill` 已被显式列入 `registered_but_unavailable_operations` | — | **正面改进，已闭环** |
| **E** | N3 复测：实时巡检已给出 `measurement_method="tessellated"`、`method_error_bound_mm=0.001`、`bounding_box_source="solid_face_tessellation"`，**实测通过** | — | **已修（实测）** |
| **F** | N4 复测：`surface_loft` 的 `element_tree` −18 与「non-composite curves」截面契约**一字未改**；改进只在准入层。**但**：人工 Start 辅助应用程序后 `resident_panel` 实测可建曲面（两截面 + 三截面，面积吻合 2.2e-7） | 高 | **−18 未修；`resident_panel` 已实测可用** |
| **J** | 同一份 `creo_capabilities` 回执里 `direct_blend_callback.readiness="unknown"` 与 `families.loft.runtime_admission.callback_readiness="ready"` **互相矛盾**，而 `creo_callback_status` 报 `ready` | 中 | **新增** |
| **K** | `resident_panel` 路线真实形态（7 截面 + 尖点 + 3 导线）实测：21/21 交叉对通过、11/11 位置选中，但内核构建失败弹**模态框**，Done 括号只有 `entering:1` → 作业永久 `running`，`timeout_seconds=1500` 与 `stall_watchdog_seconds=600` **都不生效**（执行它们的 worker 已死） | **阻断** | **新增（§6.6）** |
| **L** | 由 K 引发的**会话级锁死**：`panel_session_guard.blocks_toolkit=true`，全工具链返 `PanelSessionLocked`；唯一解锁动作 `confirm_panel_closed` 又要求作业已终态 → **死循环，无工具出口**，只剩人工删 guard 文件 | **阻断** | **新增（§6.6.5）** |
| **G** | `creo_callback_status.readiness="unknown"` 同时表示「正在启动」和「不知道」，语义重载 | 低 | **新增** |
| **H** | 服务端 stderr 输出非 UTF-8（GBK）字节，Python `mcp` 客户端读线程抛 `UnicodeDecodeError` | 低 | **新增** |
| **I** | `creo_inspect_model` 的 `datum_planes[]` 无 `name`，无法按基准面名反查 | 低 | **新增** |
| **N1** | 未知参数在调用边界被拒 | — | **已修（复测通过）** |
| **N2** | `creo_get_job` 顶层透传失败字段 | — | **源码确认，本轮无失败作业可复现** |

---

## §1 问题 A：runner 随客户端断开即死，作业永久 `queued`

### 1.1 现象

`creo_execute_plan` 返回 `status="queued"` 的排队回执（这是设计如此），随后客户端按回执提示「Poll creo_get_job」去轮询。但**只要提交它的那个 stdio 会话在拿到回执后断开**，作业就再也不会前进：

```
status = "queued"
stage  = "waiting_for_channel"
```

等 8 分钟仍是这个状态，**没有任何错误码、没有任何 `failure_phase`、`worker_started` 字段始终不存在**。

### 1.2 A/B 对照（同一台机器、同一个 plan 文件、同一个 Creo 会话）

| | 提交方式 | 结果 |
|---|---|---|
| 作业 `51972da20b5543b0b2aa7d7d3df1ca3b` | 客户端拿到回执后**立即断开** | 永久 `queued / waiting_for_channel` |
| 作业 `abb08f90a9ec44138ad0945a08a0e92c` | 同上，另起一次 | 永久 `queued / waiting_for_channel` |
| 作业 `c448593ab0fb46ec8f01f8aa76f5631a` | 同一会话**保持连接并每 4 s 轮询** | `succeeded / verified`，`volume_mm3 = 60000.0`（100×60×10 ✓） |

最后一条的阶段序列是完整的：

```
queued → running/building_worker → running/connect → running/save_and_reload
       → running/result_delivery_complete → succeeded/verified
```

### 1.3 磁盘证据：成功的作业多了 6 个文件

| 文件 | `51972da2`（卡死） | `abb08f90`（卡死） | `c448593`（成功） |
|---|---|---|---|
| `job.json` | 1507 B | 2001 B | 22900 B |
| `request.json` | 4717 B | 1784 B | 1785 B |
| `runner.log` | **0 B** | **0 B** | 0 B |
| `worker.log` | **不存在** | **不存在** | 存在 |
| `native.log` | **不存在** | **不存在** | 16070 B |
| `native_owner.json` | **不存在** | **不存在** | 100 B |
| `native_checkpoint.json` | **不存在** | **不存在** | 49846 B |
| `native_result.json` | **不存在** | **不存在** | 49840 B |

两个卡死作业的 `runner.log` 都是 **0 字节**，`worker.log` / `native.log` / `native_owner.json` / `native_checkpoint.json` **一个都没产生**。也就是说 runner 进程确实起来了（`job.json` 里写了 `runner_identity`），写完 `stage="waiting_for_channel"` 之后就死了，**从未走到 `worker_started` 那一步**。

`job.json` 里对应字段：

```json
{"status": "queued", "stage": "waiting_for_channel",
 "runner_identity": {"pid": 31572, "created": 134402135661345989, "alive": true},
 "runner_detached_from_job": true,
 "worker_started": null}
```

进程实测：

```
pid 31572  DEAD       (作业 51972da2 的 runner)
pid 26608  DEAD       (作业 abb08f90 的 runner)
```

### 1.4 机制定位

- `runner_detached_from_job: true` 写在回执里（`generic_bridge.py:1836`），但从实测看**它并没有真正 detach**：客户端进程一退、服务端进程随之退出，runner 也一起消失。
- `manifest.update(runner_identity=..., stage="waiting_for_channel")` 在 `bridge.py:1975`，是 runner 的**第一件持久化动作**；`worker_started` 要等到 `generic_bridge.py:1945`（拿到 `toolkit_lock` 之后）才写。
- 组合结果：**runner 在「已经证明自己存在」和「证明自己要不要启 worker」之间死掉，留下一个既不能算「活着」也不能算「没启动」的中间态。**

> 诚实边界：A/B 两条路径的差异只有「会话是否保持」，因此「runner 生命期绑在 stdio 会话上」是强相关；「服务端析构时 `terminate()` 掉子进程」这一具体机制我无法只从外部观测证实，交由作者确认。

### 1.5 影响

这不是「一个作业失败」，而是**整条原生建模通道在当前客户端形态下不可用**：所有 `creo_execute_plan` 都会走进同一个死法。批量重建脚本、CI、任何「提交后异步跑、稍后回收结果」的调用方式全部命中。

### 1.6 建议

1. runner 启动后的**第一条**持久化写入就应该是 `worker_started = false`（占位），在任何早退路径（拿不到通道、构建 worker 失败、异常）都把作业写成终态 `failed` + `failure_phase`，**不要把作业留在 `queued`**。
2. 要么真正 detach（不再随父进程退出），要么把 `runner_detached_from_job` 改成 `false`，并在排队回执的 `message` 里明确写「保持会话直到作业终态」，让调用方能照做。
3. 若坚持依赖父进程，至少应在服务端退出前把「自己还有未完成作业」这件事写进作业记录，让下一次会话能把它们判成 `failed(runner_lost)` 而不是无限 `queued`。

---

## §2 问题 B：`queued` 且 runner 已死，没有任何出口

问题 A 产生的作业**无法清理**，而且会把模型一起锁死。

### 2.1 `creo_cancel_job` 不置终态

```
creo_cancel_job(51972da2…) →
  {"status": "queued",
   "cancelled": false,
   "stage": "cancel_requested",
   "termination": {"attempted": true, "pid": 28164, "returncode": 128}}
```

三个问题：

1. 只把 `stage` 改成 `cancel_requested`，`status` 仍是 `queued`，**永远进不了终态**，`creo_list_jobs` 里会永久挂着一条假作业。
2. `termination.pid = 28164` 是**另一个进程**（本次启动的 coordinator），不是该作业记录的 runner `31572`。杀错对象。
3. `returncode: 128` 没有映射成任何可读原因。

### 2.2 `creo_reconcile_model` 九个 action 全部拒绝

`mode="inspect"` 的判定：

```
status         = "ready"
pending_job    = "51972da20b5543b0b2aa7d7d3df1ca3b"
recovery_pending = null
baseline.verified = true        (frigate_v4.prt.109, sha256 0c893f47…, 6 051 648 B)

owners[0].runner = {"recorded": {"pid": 31572, "alive": true},
                    "observed": {"pid": 31572, "alive": false},
                    "stopped": true}
owners[0].worker = {"stopped": false,
                    "reason": "Native owner identity is unavailable"}

actions = {restore_baseline: false, accept_saved: false, accept_live: false,
           abandon_new: false, ack_no_mutation: false, ack_failure: false,
           abandon_stalled_recovery: false, abandon_unknown_recovery: false, …}
理由全部同一句：
  "Previous runner/worker is active or cannot be proven stopped"
```

即：**runner 已被证明确实死了，但 worker 因为「没有任何身份记录」被当成「无法证明已停止」，于是九个出口全部关闭。**

### 2.3 根因在 `_owners()` 的一个分支

`reconciliation.py:500-535`：

```python
if job.get("worker_started") is False and runner["stopped"]:
    worker = {"stopped": True, "reason": "Runner ended before native worker started"}
elif checkpoint.get("native_pid"):
    worker = _stopped({"pid": checkpoint["native_pid"]})
else:
    # A runner without native ownership evidence may have died between
    # spawning a legacy worker and persisting its PID. Do not guess.
    worker = {"stopped": False, "reason": "Native owner identity is unavailable"}
```

这里第一条分支**正是本次的情形**（runner 确实在 worker 启动前就死了），但因为 `worker_started` 是 `null` 而不是 `false`（runner 没来得及写），代码掉进了 `else`。

注释说的顾虑是「runner 可能在 spawn worker 与持久化 PID 之间死掉」，所以不敢猜。但本次有更多可判据的事实可以排除这个顾虑，建议加一条兜底：

> `worker_started is None` 且 `native_owner.json` / `native_checkpoint.json` / `worker.log` / `native.log` **四者全不存在** 且 `runner.observed.alive = false`
> → 判定 `worker = stopped`，理由 `"Runner died before starting any native worker (no ownership artifact)"`。

### 2.4 唯一剩余路径要求重启 Windows

`reconciliation.py:556` 在 `eligible` 时回退到 `previous_boot_evidence()`，而 `legacy_recovery.py:37` 是硬的：

```python
for name in ("created_at", "updated_at", "started_at", "finished_at"):
    if name in job:
        timestamp = datetime.fromisoformat(job[name])
        if timestamp.tzinfo is None or int(timestamp.timestamp() * 1e9) >= cutoff:
            raise ValueError("Job timestamps do not predate the verified Windows boot")
```

本次实测报错原文：

```
"reason": "Job timestamps do not predate the verified Windows boot"
```

一个几分钟前刚创建的作业，**永远不可能早于本次启动时刻**，所以这条兜底对本题无解。`guidance` 里也写着：

> After an operator-controlled restart, inspect again; no action can bypass uncertain ownership.

结论：**唯一出路是重启 Windows。** 这一条请作者评估是否需要这么重。

### 2.5 模型被 `pending_job` 硬锁

在锁解除前，对 `frige_v4` 的任何写操作都被拒：

```json
{"status": "busy", "code": "toolkit_busy", "accepted": false,
 "blocking_job_id": "51972da20b5543b0b2aa7d7d3df1ca3b",
 "blocking_model_id": "df7f74bf5e424dbeb00605e218be89ad",
 "blocking_operation": "pending_job"}
```

而同时 `creo_session_status.live_probe.busy = false`、`queued = false`——**原生通道明明是空的**。`snapshot.mutation_pending` 也变成 `true`。

### 2.6 建议

1. `creo_cancel_job` 对 `queued` 且 runner 已死的作业，应能**metadata-only 直接置 `cancelled`** 并释放 `pending_job`（这正是 `ack_no_mutation` 的语义，只是它现在只认 `failed`）。
2. 给 `creo_reconcile_model` 增加一个针对本形态的 action（例如 `abandon_dead_runner`，条件：`runner.observed.alive=false` + 四类 worker 证据全无 + baseline hash 一致），不要逼用户重启机器。
3. 修 `creo_cancel_job` 杀错 pid 的问题，并把 `returncode` 映射成可读原因。
4. `busy` 回执里既然已经给了 `blocking_job_id`，建议同时给出「该 job 的 runner 是否已死」和「可用的清理入口」，否则调用方只能读到 `pending_job` 三个字，无处下手。

---

## §3 问题 C：`ExtrudeOp` 缺双向不等深，直接把 B103 建成了半厚

### 3.1 能力缺口

`creo_capabilities`：

```
extrude_directions = ["positive", "negative", "symmetric"]
extrude_depth_types = ["blind", "through_all"]
```

`ExtrudeOp` 的字段（`schema.py`）只有 `depth` + `direction`。于是：

| IR/TXT 里的形态 | 能否表达 |
|---|---|
| 单向 8.4 | ✓ `depth=8.4, direction=positive` |
| 两向**等深**各 100 | ✓ `depth=200, direction=symmetric` |
| 两向**不等深** 8.4 / 1.0 | ✗ **无法用一个 op 表达** |

而「方向一深度 X + 方向二沿上述向量反向，深度 Y」且 `X ≠ Y` 在这份 TXT 里非常常见（B104 就是 0.084 / 0.01），只能拆成两个 op 手写，且两个 op 在特征树里是**两条独立特征**，与源模型的单条双向拉伸不对应。

### 3.2 由此产生的实际建模错误

B103 `Boss-Extrude35`，TXT 原文：

> 斜置细条的中面 Z=-8.1，两方向各 1 米，形成名义 2 米高竖片。
> 方向一深度 1。方向二沿上述向量反向，为 给定距离，深度 1。

`spec.json` 对应：`depth1 = 1`、`depth2 = 1`、`dir = [0,0,1]`，`Sketch192.point = [0,0,-8.1]`。

当时为了走「单 depth」这条路，载荷写成了单向：

```json
{"op":"extrude","label":"boss_extrude35","sketch":"sketch192",
 "depth":100.0,"mode":"add","direction":"positive"}
```

**结果：斜撑只长了 Z −810…−710 这 100 mm 半边，缺了 Z −910…−810 那半边（应为总厚 200 mm）。**

实测佐证（rev106 面数据）：

| 面 id | 面积 mm² | bbox Z |
|---|---|---|
| 6675 | 3147.0 | **−788.1 … −712.7** |
| 6671 | 3227.2 | **−780.9 … −712.7** |

若斜撑是 200 mm 厚（−910…−710），这两个大侧面应覆盖 −910…−710；实际最低只到 −788（更低处被 B105 切掉了）。而 `creo_inspect_model` 的 `legacy_regeneration_outline_mm.min[2] = −910.0` 说明模型里确实有到 −910 的几何，但那不是这根斜撑。

### 3.3 连带解释了上一版遗留的 D19

| 特征 | 轮廓所在 Z | 斜撑实际 Z | 去料 | 解析 |
|---|---|---|---|---|
| B104 `Cut-Extrude16` | **−910 … −810** | −810 … −710 | **38.055 mm³** | 13,902（0.27%） |
| B105 `Cut-Extrude17` | **−810 … −710** | −810 … −710 | 5,683.687 mm³ | 10,492.3（54.17%） |

B104 的轮廓（`spec.json` 里 2 条椭圆弧 + Z=−9.1 的 3 条直线 + 1 条样条）整块落在**下半片**，而斜撑只建了上半片，所以那一刀基本切在空气里；B105 的轮廓正好落在上半片，才切掉了 54%。

> **D19 定性：不是切除方向错，也不是草图坐标系错，而是父特征（B103）少建了一半厚度。** 补齐下半片后，B104 应能切掉接近解析值 13,902 mm³。

### 3.4 建议

给 `ExtrudeOp` 增加二选一：

- `depth2: Positive | None`（沿 `direction` 反向的独立深度）；或
- `depth_forward` / `depth_reverse`（`mode` 与 `direction` 语义不变，`symmetric` 保留为 `forward == reverse` 的语法糖）。

若都不加，请至少在 `creo_capabilities` 的 `extrude_directions` 旁边写一句「两向不等深需拆成两个 extrude op，会生成两条特征」，让调用方知道这是个**已知的表达能力缺口**而不是自己写错了。

---

## §3.5 问题 C2：`creo_adopt_file` / `creo_open_file` 的 worker 硬编码 115 s，大模型必然超时

为了绕开 §2 的模型锁，我把已保存的 `frigate_v4.prt.109`（6 051 648 B、`sha256 0c893f47…`、589 特征、`volume_mm3 = 5 389 687 300.838182`）复制成新文件 `frigate_v4c.prt` 并用 `creo_adopt_file` 接管。`inspect` 阶段一切正常：

```
items[0].status = "eligible"
source.healthy = true, millimeter_units = true, feature_count = 589, dependency_free = true
inspection_warnings = [{"stage":"live","reason_code":"native_sidecar_write_failed",
                        "fallback_status":"verified",
                        "message":"Native sidecar write failed; Python fallback was verified"}]
```

但 `apply` 的子作业最后是：

```json
{"status": "unknown_outcome",
 "stage": "adopting_native_model",
 "worker_started": true,
 "message": "Command '[…\\build\\creo_worker.exe', 'generic', '…\\jobs\\276bd0e1…'] timed out after 115 seconds"}
```

**115 秒是源码里的模块常量，不是参数也不是配置项：**

| 文件 | 行 | 内容 |
|---|---|---|
| `src/creo_mechdog/adoption.py` | 29 | `WORKER_SECONDS = 115` |
| `src/creo_mechdog/adoption.py` | 224 | `timeout=WORKER_SECONDS` |
| `src/creo_mechdog/open_file.py` | 23 | `WORKER_SECONDS = 115` |
| `src/creo_mechdog/reconciliation.py` | 43 | `WORKER_SECONDS = 115` |
| `src/creo_mechdog/session_models.py` | 89 | `timeout=115` |
| `src/creo_mechdog/session_assembly.py` | 53 | `timeout=115` |

对比同一版本里的 `creo_execute_plan`：`timeout_seconds` 可传 60–7200，默认 1500（本工程实测回执 `timeout_seconds = 1500, timeout_source = "server"`）。**同一条原生命令，走 execute_plan 有 1500 s，走 adopt_file 只有 115 s。**

本工程这个零件从磁盘 `打开 → 保存一份托管副本 → 重载 → 校验`，在 0.40.0 时代实测就要 2 分半以上（见状态文档里 `verify_model_start` 从 220 s 推到 533–571 s 的那段）。115 s 对它必然不够。

**后果是二级锁**：作业 `unknown_outcome` 之后，模型停在

```
status = "adopt_pending", revision = 0, pending_job = "276bd0e194c94dddb1c9b63c65dfe982"
creo_reconcile_model(mode="inspect") → owners[0].reason = "Job timestamps do not predate the verified Windows boot"
                                     → 九个 action 全部 available=false
```

也就是 **§2 的锁换了个入口又来一次**：想绕开第一条死作业，结果造出第二条死作业。本次一共留下三个不可写模型：`df7f74bf…`（原整船）、`6ebaef10…`（第一次 adopt 被我的 `timeout` 掐断）、`b38bef6c…`（第二次 adopt 撞 115 s）。

另外 `inspection_warnings` 里那条 `native_sidecar_write_failed`（"Native sidecar write failed; Python fallback was verified"）也值得看一眼：它在 inspect 阶段就出现了，虽然降级到 Python 后仍然 `verified`，但和后面的 `adopting_native_model` 超时是否同源，我这边判断不了。

### 建议

1. `WORKER_SECONDS` 改成可配置（`config.json`）+ 可传参，并与 `execute_plan` 的 1500 s 默认对齐；至少要按模型的 `feature_count` / 文件大小做一次自适应下限——0.40.0 已经给恢复预算做过同样的事（`max(120+edges//15, 120+features//2, 120+surfaces//4)`），这里可以直接复用。
2. worker 超时后不要留 `adopt_pending` + `pending_job`，应直接落成 `failed(worker_timeout)` 并释放 pending；否则一次超时就把「换副本继续干活」这条**唯一的自救路径**也堵死。
3. `inspection_warnings` 的 `native_sidecar_write_failed` 若确实会影响后续 commit，请在 inspect 阶段就把它升级成 refusal，而不是先 `eligible` 再在 apply 阶段超时。

---

## §3.6 问题 C3：切除缺少「特征级范围」，单 body 上无法复现「只作用于指定对象」

修 B103 斜撑厚度时发现的第二个表达能力缺口。

TXT 对 B104 明写：

> 作用对象名称：Boss-Extrude35。这些名称表示前述操作生成的本机几何…
> **此操作是减料切除，只作用于指定对象**；合并字段不表示添加并集。

`ExtrudeOp.scope` 的形状是：

```python
class ExtrudeScope(StrictModel):
    kind: Literal["bodies"]
    body_ids: Annotated[list[int], Field(min_length=1, max_length=100)]
```

**只能按 body 限定。** 本模型是 `bodies = 1`，所以 scope 用不上，`cut` 会切掉路径上的一切。

实测后果（rev109 重切 B104）：

| | 源模型（特征级范围） | 本工程（无范围） |
|---|---|---|
| 斜撑自身横截面 | 400.6 mm²（下半片底面实测 400.7） | 同 |
| 9.4 mm 深最多能切 | ≈ 3,766 mm³ | 同 |
| 实际去料 | — | **8,333.103 mm³** |

多出来的约 **4,570 mm³** 切进了相邻的 B102 板。位置在船底斜撑内侧，视觉影响小，但体积账对不上源模型。

这不是孤立问题，和已知的三条同族：

| 已有缺口 | 表现 |
|---|---|
| `thin` 只有 `thin: 5.0` | 无法指定单侧偏置方向（D26） |
| `ShellOp` 只有 `thickness/remove_surfaces/outward/body_id` | 单 body 无法只抽塔桅（P4，B064 仍做不了） |
| `ExtrudeOp.scope` 只有 `bodies` | 无法只切某个特征生成的实体（本条） |
| `MirrorOp` 允许集无 `feature` | 无法镜像特征（P3） |

**共同点：MCP 的特征图是「模型 → 面/边」，缺少「特征 → 它生成的那块材料」这一层。** 源模型（SolidWorks/Creo 原生）里这层是显式存在的（feature scope、merge scope、body 拆分）。

### 建议

最小改动是让 `ExtrudeScope` 支持 `kind: "features"` + `feature_ids`，在 worker 侧用 `ProSolidFeatVisit` 取该特征生成的 quilt/surface 集合做布尔限定；若短期做不到，请至少：

1. 在 `creo_capabilities` 里明写「cut 总是作用于整个 body，无法复现源模型的 feature scope」；
2. 在 `cut` 的结果里报 `removed_mm3` 与「按当前 body 拓扑估算的路径内总体积」两个数，让调用方能判断是否越界切割；
3. 提供 `new_body` 之外的另一条路：允许把目标特征先 `split` 成独立 body（配合 `scope.body_ids`），这样现有 `bodies` 语义也能表达「只切它」。

---

## §4 问题 D：`surface_boundary_fill` 已显式标记不可调用（正面）

```
registered_but_unavailable_operations = [
  "sheetmetal_flange_profile", "sheetmetal_corner_relief",
  "sheetmetal_quilt_form", "surface_boundary_fill"]
operations_note = "operations lists currently callable operations; registered_operations
                   also includes registered_but_unavailable_operations which cannot be invoked."
```

上一版反馈里 B031/B032（TXT：平面封闭曲面）只能靠猜能不能调，现在 `creo_capabilities` 直接给出白名单，**不用再浪费一次失败作业确认**。这一条闭环，谢谢。

---

## §5 N3 复测：**已修，实测通过**

### 5.1 老快照仍然只能读历史口径（合理）

`creo_inspect_model` 读 rev106 的**存档快照**（`inspection_source="saved_reloaded"`，快照时间 2026-11-24 11:26 UTC，0.43.0 时代）：

```json
"bounding_box_mm": null,
"bounding_box_status": {"state": "unavailable", "reason": "legacy_snapshot"},
"bounding_box_source": "legacy_regeneration_outline",
"legacy_regeneration_outline_mm": {
  "min": [-0.1, -690.1, -910.0],
  "max": [8149.6, 690.1, 1920.0],
  "size": [8149.7, 1380.2, 2830.0]}
```

`legacy_regeneration_outline_mm` 确实可读，0.45.0/FEAT-078 说的历史路径通了。

### 5.2 实时巡检给出新口径（已修实锤）

同一次会话里对源文件做 **live** 巡检（0.47.1 现算），`bounding_box_mm` 不再是 null：

```json
"bounding_box_mm": {                                  // tessellated
  "min":  [0.0,    -690.0, -885.0],
  "max":  [8149.5,  690.0, 1920.0],
  "size": [8149.5, 1380.0, 2805.0]},
"bounding_box_source":   "solid_face_tessellation",
"measurement_method":    "tessellated",
"method_error_bound_mm": 0.001,
"error_bound_direction": "inward"
```

与历史口径的差异（正好对上 BUG-195 说的「tessellated 是内向界」）：

| | 历史 `legacy_regeneration_outline` | 新 `solid_face_tessellation` | 差 |
|---|---|---|---|
| X | −0.1 … 8149.6 | 0.0 … 8149.5 | 各收 0.1 |
| Y | −690.1 … 690.1 | −690.0 … 690.0 | 各收 0.1 |
| Z | **−910.0** … 1920.0 | **−885.0** … 1920.0 | 底部收 **25.0** |
| size | [8149.7, 1380.2, **2830.0**] | [8149.5, 1380.0, **2805.0**] | 高差 25 |

**N3 判定：已修。** `measurement_method` / `method_error_bound_mm` / `error_bound_direction` 三个字段都出现且取值合理，历史快照走 `legacy_regeneration_outline_mm` 的降级也成立。

> 顺带一个对建模有用的发现：真实最低点是 **Z = −885**，不是历史轮廓给的 −910。而 B104 的轮廓压在 Z −910…−832，**底边比模型本身还低 25 mm** —— 这与 §3 的结论互相印证：那条切除的落位从一开始就不在斜撑上。

建议：`bounding_box_status.reason="legacy_snapshot"` 时补一句「再做一次巡检/保存即可获得 tessellated 口径」，并把两种口径的**预期差值方向**（inward）写进 `frames_note` 同级的位置，免得调用方以为两个数其中一个是错的。

---

## §6 问题 F（N4 复测）：`surface_loft` 的 −18 与截面契约未变，改进只在准入层

### 6.1 准入层：确实改好了

```json
"families": {
  "surface_loft": {
    "enabled": true,
    "runtime_ready": false,
    "runtime_admission": {
      "status": "not_ready",
      "element_tree_status": "known_release_extract_unsupported",
      "resident_panel_callback_readiness": "unknown",
      "check_tool": "creo_callback_status",
      "reason": "resident callback readiness is 'unknown'; query creo_callback_status and
                 start the registered auxiliary application in Creo before calling resident_panel"
    }
  },
  "loft": {
    "runtime_ready": false,
    "runtime_admission": {"status": "requires_ready_callback",
                          "callback_free_tool": "creo_new_loft_part",
                          "callback_readiness": "unknown",
                          "reason": "callback_observation_required"}
  }
}
```

`element_tree_status = "known_release_extract_unsupported"` 这一行是本轮最实质的改进：**把 Creo 10 release 42 的 −18 从「静默失败」变成了「平台已知限制」**，并且在 `creation_route="resident_panel"` 时提交前拒绝，不再占通道、不再生成失败作业。

### 6.2 能力本体：未变

`native/surface_loft.cpp:214` 仍是：

```
" non-composite curves"
```

截面契约仍是「一条曲线，或两条合成一个闭合轮廓」。本工程球鼻艏的 3 截面 + 3 导线形态依然无法用 `surface_loft` 表达。

### 6.3 `resident_panel` 路线：本轮起点是「一次都没 Start」

```
creo_callback_status →
  readiness = "not_loaded"
  next_action = "start_or_register_application_manually"
  reason = "recorded_application_not_active"
  manual_setup_when_not_loaded = true
  command = "MechDogPanel_02eac3e096261e383ba0f0d6_3a7d9bd8"
  dll_sha256 = "02eac3e096261e383ba0f0d6065d990e20e7a6efd4d7a3729ea0bbb5da4cd0bc"
  artifact_status = "prepared"
```

DLL 已就位、契约版本 `resident-panel-selection-v4-ticketed-mm`、`protocol=4`，但 Creo 会话里没有 Start 这个辅助应用程序。**这一步必须人工在 Creo 的「辅助应用程序」里点 Start**，`creo_callback_status` 明确写了 `manual_setup_when_not_loaded = true`，且没有任何工具能代劳。

### 6.4 准入闸实测：真的在提交前就拒绝了（BUG-193 已修，实锤）

用一个全新的探针零件 `loft_probe_0471`（`model_id = adb51c281ab7485b9dd6349d4a1d3b7e`，两个单线草图 `s1`/`s2`）直接调 `creo_surface_loft(creation_route="resident_panel")`，准入链是**逐级前置**的，三次都在建作业之前就返回，`Toolkit` 通道一次没碰：

第 1 次（section 给裸 id `40`）：

```
creation_route='resident_panel' sections[0] is a bare feature id: the panel route resolves
each section from an MCP-owned sketch label, so pass the sketch label (a string),
{label:'...',open_confirmed:true}, or at a convergence end {kind:'datum_point_feature',label:'...'}.
Curve, edge and bare-id forms stay on the element_tree route
```

第 2 次（section 给裸 label `"s1"`）：

```
creation_route='resident_panel' sections[0] is the bare label 's1': this build cannot read
whether a standalone curve is closed, so the route needs the caller's explicit openness proof
instead of assuming it. Pass {"label":"s1","open_confirmed":true} …
No job was created and the Toolkit channel was not touched; the element_tree route still
accepts the bare label.
```

第 3 次（section 给 `{"label":"s1","open_confirmed":true}`）：

```
BLEND_CALLBACK_SETUP_REQUIRED (before-job preflight):
readiness='not_loaded', reason='recorded_application_not_active',
next_action='start_or_register_application_manually',
registry_file='…\build\blend_callback_protk.dat'
```

**这一条完全达到 0.46.0/BUG-193 的承诺**：错误码可判别、`next_action` 直接告诉你该干什么、`before-job preflight` 明写未建作业、还附了要注册的 `registry_file`。和 0.19–0.26 时期「提交 → 静默 −18 → 失败作业 → 模型进 unknown_outcome」相比是质变。

顺带记两条 `resident_panel` 路线的隐含契约（文档里没集中写，实测才知道）：

1. section 必须是 **MCP 自己的 sketch label**，不能是裸 feature id，也不能是 `{kind:'curve'|'edge'}`（那两种只在 `element_tree` 路线上有效）；
2. 必须由调用方显式声明曲线开口（`open_confirmed: true`），因为当前 build **读不出**独立曲线是否闭合。

建议：既然 `manual_setup_when_not_loaded=true` 是常态，`creo_callback_status` 或 `creo_capabilities` 里最好给一句「Start 之后如何验证」（例如 Start 成功后 `readiness` 会变成什么值），否则调用方无法判断自己点对了没有。

### 6.5 后续进展：人工 Start 之后，`resident_panel` 真的建出了曲面

本文档初稿写到这里时，Creo 里的辅助应用程序尚未 Start，所以只能记「准入闸好用、路线本身没跑到」。此后在本机上**人工 Start 了一次** `MechDogPanel_02eac3e096261e383ba0f0d6_3a7d9bd8`，整条路线当场翻绿，并成功建出曲面。以下为实测补录。

#### 6.5.1 Start 之后，准入层全部翻绿

`creo_callback_status`：

```
readiness        = "ready"
reason           = "live_identity_verified"
command          = "MechDogPanel_02eac3e096261e383ba0f0d6_3a7d9bd8"
artifact_status  = "prepared"
```

`creo_capabilities` 对照（同一进程、同一零件）：

| 字段 | Start 前 | Start 后 |
|---|---|---|
| `families.surface_loft.runtime_ready` | `false` | **`true`** |
| `families.surface_loft.runtime_admission` | `{"status":"not_ready","element_tree_status":"known_release_extract_unsupported","resident_panel_callback_readiness":"unknown",…}` | **`null`** |
| `families.loft.runtime_admission.status` | `"requires_ready_callback"` | **`"ready"`** |
| `families.loft.runtime_admission.callback_readiness` | `"unknown"` | **`"ready"`** |

`runtime_admission` 从「一个带 reason 的 not_ready 对象」直接变成 `null`，语义是「无保留意见，可以走」。这一点比 `runtime_ready=true` 更有信息量——**建议在文档里把 `runtime_admission = null` 明确定义为「已通过全部准入」**，否则调用方看到 `null` 会怀疑字段丢了。

#### 6.5.2 两截面直纹面：面积与手算吻合到 2.2e-7

在探针零件 `loft_probe_0471`（`model_id = adb51c281ab7485b9dd6349d4a1d3b7e`）上，用两个单线草图 `s1`/`s2` 走 `creation_route="resident_panel"`：

job `a1bad61759714602801ad6e20ad10314` → `succeeded / verified`

```
panel.slots                    = 2
feature_id                     = 92
quilt_id                       = 99
quilt_count                    = 1
face_count                     = 1
quilt_is_new                   = true
panel_geometry_postop.unique_new_quilt = true
inspection_source              = "saved_reloaded"
measured_after_reload          = true
area_mm2                       = 5923.681287847949
bbox                           = min [0,0,0] → max [120,20,50]
```

手算：四边形 A(0,0,0) B(100,0,0) C(120,20,50) D(0,20,50)，两条对边 A→B（长 100）与 D→C（长 120）平行、间距 20，直纹面虽为双线性曲面但为可展的平面梯形，面积 = (100+120)/2 × √(20² + 50²) = 110 × 53.8516… = **5923.68**。与 MCP 实测值相对误差 **2.2e-7**。

这条数字值得单独记：它不是「建出来了」这种定性判断，而是**曲面面积与解析值对上了 7 位有效数字**，且 `inspection_source="saved_reloaded"` + `measured_after_reload=true` 说明测量发生在**存盘重开之后**，排除了「内存里算了个数」。

#### 6.5.3 三截面平滑面：`slots=3`、`face_count=1`

job `ff88246ac3ba4c0494b07e27cf5e2e00` → `succeeded / verified`

```
panel.slots   = 3
feature_id    = 113
quilt_id      = 119
face_count    = 1
quilt_count   = 1
area_mm2      = 13198.469846071788
```

三截面仍是**一张面**（`face_count=1`），没有被切成三段拼接。两张作业的 `jobs/<job_id>/output/preview.jpg`（13 019 B / 12 938 B）目视确认曲面干净、无破面、无折叠。

#### 6.5.4 结论的准确边界（不越界声明）

本轮**能**说的：

- `resident_panel` 路线在 **Creo 10 release 42** 上实测可用，两截面直纹面与三截面平滑面均 `succeeded / verified`；
- 面积、`face_count`、`quilt_is_new`、存盘重开后的测量源，四项独立证据一致；
- 0.47.1 的准入前置（BUG-193）与 Start 后的自动翻绿配合，形成了一条「未 Start → 明确报错 → Start → 直接可用」的闭环。

本轮**不能**说的（沿用本工程一贯的判定纪律）：

- **不能**说「Creo 10 球鼻艏 MCP 已修复」。理由有两条，都不因上述成功而消失：
  1. `native/surface_loft.cpp:214` 的 `" non-composite curves"` 未变，**3 截面 + 3 导线**（`guides`）形态仍无表达入口；
  2. 球鼻艏需要的是**曲率截面、非共面、带导线**的边界混合，本轮实测的是**直纹/平滑、无导线**的对照件。对照件通过只证明「面板通道打通」，不证明「球鼻艏形态可表达」。
- **不能**说「`element_tree` 的 −18 已修」。它仍在，只是 `resident_panel` 绕开了它。

#### 6.5.5 顺带发现：同一份回执里 `readiness` 自相矛盾

Start 之后同一次 `creo_capabilities` 调用里：

```
direct_blend_callback.readiness                        = "unknown"
families.loft.runtime_admission.callback_readiness     = "ready"
```

一个是 `unknown`，一个是 `ready`，而 `creo_callback_status` 自身报 `ready / live_identity_verified`。三者本应同源。怀疑 `direct_blend_callback` 这一支走的是与 `resident_panel` 不同的探测路径（或根本没被刷新），属于遗留物。建议统一到同一个观测源，或在 `direct_blend_callback` 里注明它探测的是另一条通道。

这一条的危害是实质的：调用方若以 `direct_blend_callback.readiness` 作判断依据，会在**明明已 Start 的情况下**误以为自己没点对，从而反复去 Start 或放弃路线。§6.3 末尾我建议「给一句 Start 之后如何验证」，现在有了更具体的落点：**统一这个字段**。

### 6.6 真实形态实测：7 截面 + 1 收敛点 + 3 导线 → 选中全部成功，Done 永不返回

§6.5 的两截面 / 三截面只是「通道能不能用」。本节是把 TXT 里球鼻艏**真实形态**（7 个 X 截面 + 前端尖点 + 3 条纵向导线）原样喂进去的结果。结论分两半：**准入与选择全绿，Done 与收尾全黑**。

#### 6.6.1 建面准备：47 个 op 全成，截面是 TXT 样条的精确复现

新零件 `bulb0471`，`model_id = dcc9eaf5f5cc45e9800548f7b1aba9fb`。一个 plan 47 个 op、`succeeded / verified`：

```
27 × datum_points（单点）
 9 × datum_plane（through_points）
10 × sketch（7 截面 + 3 导线）
```

7 个截面不是「拟合」出来的，是用 `b_spline` 把 TXT 附录 A22/A23/A23a~A23e 的 **degree=3 + 控制点 + 节点向量 + 权重** 原样写进去：

| 截面 | X（mm） | 控制点 | 节点 | 最大半宽（曲线，非控制多边形） |
|---|---|---|---|---|
| A23 | 6409.4736 | 6 | 10 | 1.800 |
| A23a | 6600 | 28 | 32 | **1.818** |
| A23b | 6800 | 28 | 32 | 1.770 |
| A23c | 7000 | 28 | 32 | 1.635 |
| A22 | 7209.4736 | 6 | 10 | 1.400 |
| A23d | 7400 | 28 | 32 | 1.105 |
| A23e | 7600 | 28 | 32 | 0.714 |

三根导线的「直线段 + 三次 Bezier」复合曲线，也各写成**一条** `b_spline`：把直线段补成等距共线三次 Bezier，用重节点 `0.5×3` 在拼接点做 C0 接合，几何与原复合曲线一致，从而满足「每根导线一条曲线」的契约。

> **一条建议（小）**：第一次提交被拒，报错是
> `through_points label 'pp_s_a23_6409_p0' must be created by a datum_points operation earlier in the same plan`。
> 真实原因不是「没在本 plan 里创建」，而是我把 3 个点塞进了同一个 `datum_points` op——`schema.py:3651` 要求的是**单点** `datum_points` 特征。报错文案若补一句「through_points 需要一个单点 datum_points 特征」，就不用去翻源码。

#### 6.6.2 交叉校验：21/21 全部实测通过（本轮最正面的结果）

native.log 第一段就是：

```
PANEL_FIT_SUMMARY={"crossing_pairs":21,"guides":3,"measured_pairs":21,
                   "pairs":21,"sections":7,"unverified_pairs":0}
```

7 截面 × 3 导线 = 21 对交叉，**measured 21、unverified 0**。说明 MCP 在开面板之前自己先算了一遍「每根导线是否真的穿过每个截面」，而这套纯 TXT 推导出来的几何是**真的通**。

这一点值得单独肯定：它把「几何本身不成立」和「面板/内核建不出来」这两类失败彻底分开了。没有这条摘要，我在 6.6.4 里就无法排除「21 对里有 6 对其实没交上」。

#### 6.6.3 11 个位置全部被面板吃下

`callback_result.json`：

```json
{"codes":[0,0,0,0,0,0,0,0,0,0,0],
 "panel":{"action":"toggle","direction":1,"slot":10,"slots":11,"stage":"prepared"},
 "prepared":true,"selected":11}
```

11 个位置（7 截面 + 1 点 + 3 导线）、11 个回调、11 个 0。宏里 `Curves2DirRep` 的第二方向切换也真的进了第二方向收集器（`second_direction_start: 8`）：

```
~ Command `ProCmdFtBndBlend`;
~ Command `MechDogPanel_...`;          × 8   ← 8 个截面（含收敛点）
~ Trigger `main_dlg_cur` `maindashInst0.Curves2DirRep` `0`;
~ Focus   `main_dlg_cur` `maindashInst0.Curves2DirRep`;
~ Select  `main_dlg_cur` `maindashInst0.Curves2DirRep` 0;
~ Trigger `main_dlg_cur` `maindashInst0.Curves2DirRep` ``;
~ Command `MechDogPanel_...`;          × 3   ← 3 条导线
~ Activate `main_dlg_cur` `dashInst0.Done`;
```

`PANEL_POSITION_LIMIT = 11` 正好用满，**位置数上限不是问题**。

#### 6.6.4 Done 不返回：Creo 弹「特征构建失败」，作业永久 `running`

`panel_exit.json` 只有进入括号，没有退出括号：

```json
{"at_epoch_ms":1795794995556,"command":"ProCmdFtBndBlend","entering":1, ...}
```

native.log 最后一行是 `PANEL_ROUTE=resident_panel selected=11`，此后 **25 分钟零输出**（`log_bytes` 一直 7031）。用户目视确认：Creo 弹出的是**「特征构建失败」类**模态对话框。

也就是说：**内核建不出这张面，Creo 用模态框报告，而 MCP 完全观测不到这个框。**

此时的作业状态：

```
status           = running
stage            = panel_macro_submit
log_age_seconds  = 1460（且继续增长）
timeout_seconds  = 1500   ← 已过，未生效
stall_watchdog_seconds = 600  ← 早过，未生效
owners[0].runner = pid 18972, alive=false, stopped=true
owners[0].worker = pid 14872, alive=false, stopped=true
```

**超时和看门狗都不生效的原因很直接：执行它们的那个进程（worker 14872）已经死了。** 一个已经死掉的 worker 无法报告自己超时。

#### 6.6.5 会话级面板锁：整条工具链被锁，且被锁成一个死循环

面板路线在开 UI 之前写了 `panel_session_guard.json`，`creo_reconcile_model(inspect)` 读到：

```
panel_session_guard = {"state":"active","job_id":"c6772cdc…","blocks_toolkit":true, ...}
```

于是之后每一次调用都变成：

```
WARNING:creo_mechdog.creo_startup:Creo startup failed (PanelSessionLocked)
```

（顺带把「每个入口都先过启动闸」的副作用暴露出来：连 `creo_get_job` 这种纯读工具，客户端若按常规先等 `creo_startup_status`，也会永远等不到。）

唯一能解锁的动作被拒：

```
confirm_panel_closed.available = false
reason = "The panel job has not reached a terminal status, so the dialog may still be
          driven; retry after the job ends"
```

**这就闭合成了一个死循环**：

| 要做的事 | 需要的前提 | 前提为什么不成立 |
|---|---|---|
| 解锁会话（`confirm_panel_closed`） | 作业到达终态 | 作业永远不会到终态 |
| 作业到终态 | worker 活着跑完 / 看门狗 / 超时 | worker 已死，超时与看门狗都不执行 |
| `creo_cancel_job` 把它置终态 | 能杀掉 runner | 又杀错 pid（`pid 20248`、`returncode 128`、`cancelled:false`） |

三条路全断。剩下唯一的动作是**人工删掉 `panel_session_guard.json`**——但源码里只对「guard 文件不可读」这种情况明说了可以删，`state=active` 的情况没有给人工出口。

建议（按优先级）：

1. **`confirm_panel_closed` 不要只认「作业终态」**。它真正的语义是「人已确认 Creo 里没有面板了」。只要 `owners` 全部 `stopped:true`（本例 runner/worker 双双 `alive:false`），再加一个人工确认标志，就应当放行——这时候没有任何进程还能驱动那个对话框。
2. **超时与看门狗挪到活着的进程里执行**。现在它们由 worker 自己算，worker 一死就全失效；server 侧完全有能力按 `job.json` 的 `created_at + timeout_seconds` 判终态。
3. **`creo_cancel_job` 要真的按 `runner_identity.pid` 杀**。本轮记录的 runner 是 18972，它去杀 20248。
4. **面板失败要在 native.log 里留判别点**。现在 `panel_exit.json` 只有 `entering:1` 就是全部证据，建议在提交 Done 之后再写一条 `PANEL_DONE_SUBMITTED`，把「Done 未返回」变成一个可判别的失败阶段，而不是让调用方靠 600 s 的静默去猜。
5. **模态错误框至少要能被观测到**。面板路线已经在 Creo 里跑真 UI 了，理论上可以顺带读一次窗口标题/对话框文本；哪怕只是在超时后把「当前是否有模态框」写进回执，也比现在完全黑洞要好。

#### 6.6.6 本轮**不能**下的结论

- **不能**说「球鼻艏 MCP 建不出来」：几何交叉 21/21 通过、11 个位置全部选中，失败点在**内核构建**与**错误上报**，不在 MCP 的选择逻辑。
- **不能**说「球鼻艏 MCP 已经能建」：本轮的 7 截面 + 3 导线形态**一张面都没生成**（`has_solid=false`、`quilts=0`）。
- 下一步该做的是**对照实验**（截面数与导线数分开变量）：先 7 截面 + 尖点、**不带导线**；再 3 截面 + 3 导线。哪一档先失败，就定位到「截面数」还是「第二方向」。这一步要等 Creo 重启、会话锁清掉之后再做。

---

## §7 问题 G：`creo_callback_status.readiness="unknown"` 语义重载

同一个 `readiness` 字段两种含义，实测两次：

| 时机 | readiness | reason |
|---|---|---|
| `creo_startup_status.state = "building_worker"` 时 | `"unknown"` | `"startup_in_progress"` |
| 就绪后 | `"not_loaded"` | `"recorded_application_not_active"` |

`reason` 已经区分开了，但**顶层 `readiness` 没有**。调用方若只看 `readiness`，会分不清该「再等一会儿」还是「该去人工 Start」。

建议把 `readiness` 的取值域改成互斥枚举，例如 `starting | not_loaded | loading | ready | unknown`，让「正在启动」不再落进 `unknown`。

---

## §8 问题 H：服务端 stderr 输出非 UTF-8

调用 `creo_cancel_job` 时，Python `mcp` 客户端的 stdio 读线程抛：

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb4 in position 0: invalid start byte
```

0xb4 是 GBK 编码里的首字节（`´` 一类），说明服务端（或其子进程）往 stderr 写了本地代码页字节。协议层是 UTF-8，这会让客户端**直接丢掉一整段 stderr**，正好是排查问题最需要的那段。

建议：服务端所有 stderr 输出统一 `encoding="utf-8"`（或至少 `errors="replace"`）。

---

## §9 问题 I：`creo_inspect_model` 的两个小不便

1. **`datum_planes[]` 没有 `name`**，只有 `id` / `normal` / `origin`。本工程要按名字找 `PL_B104`，只能先去 `features[]` 拿 id，再按 `origin` 精确匹配反查（同一 origin 命中 7 条记录）。建议 `datum_planes[]` 补 `name`。
2. **`detail` 只有 `compact` / `full` 两档**，但回执里同时给了 `detail_available`、`sections_available`、`complete` 三个字段，容易让人以为还有别的档位。实测传 `detail="summary"` 被拒：`Input should be 'compact' or 'full'`（**这条也顺便证明 N1 修好了**，见 §10）。

---

## §10 N1 / N2 复测结论

### N1：已修 ✓

0.44.0/BUG-189 在 MCP 调用边界按 schema 拒绝未知参数。实测：

```
rectangle.corner1 → "Extra inputs are not permitted"
rectangle.corner2 → "Extra inputs are not permitted"
rectangle.min     → "Field required"
rectangle.max     → "Field required"
```

四个字段一次列全，不用试一次改一个。**但**：`corner1/corner2 → min/max` 这种**改名**没有给出拼写建议（0.44.0 的说明里写了「附拼写建议」）。字面相近的能建议，语义改名建议不出来，可以理解；若能在 `rectangle` 的报错里加一句「this entity uses min/max」，就更省事。

### N2：源码确认，本轮未复现

0.44.0/BUG-190 在 `creo_get_job` 顶层透传 `failed_operation_index` / `failed_stage` / `failure_phase` / `native_result_path` / `round_failure_summary`。本轮唯一一次失败是**准入阶段**（`corner1` 拼错 + `detail="summary"`），都没生成作业，因此没有失败作业可查。本轮**不对 N2 打勾**。

---

## §11 复现清单

| 用途 | job_id / 对象 |
|---|---|
| 卡死（客户端提交后断开）#1 | `51972da20b5543b0b2aa7d7d3df1ca3b`（runner pid 31572，已死） |
| 卡死（客户端提交后断开）#2 | `abb08f90a9ec44138ad0945a08a0e92c`（runner pid 26608，已死） |
| 成功对照（同会话轮询） | `c448593ab0fb46ec8f01f8aa76f5631a`（`succeeded/verified`，60 000 mm³） |
| 被锁模型 #1 | `df7f74bf5e424dbeb00605e218be89ad`（`frigate_v4`，rev106） |
| `cancel_job` 杀错 pid | 作业 `51972da2`，`termination.pid = 28164`、`returncode = 128` |
| `reconcile` 九拒（#1） | 模型 `df7f74bf…`，`evidence_token = df68859973034885b25fc6ecc8d4eca8` |
| adopt 被我方 `timeout` 掐断 | 作业 `c4330b0997e94a00a3709a9769721be2` → 模型 `6ebaef107025429fba2847f24a685e22`（`adopt_pending`） |
| **adopt 撞 115 s 硬超时** | 子作业 `276bd0e194c94dddb1c9b63c65dfe982`、父作业 `600b02eeb24b41448e122d5c79bea1d9` → 模型 `b38bef6c2a664599a1693866dc1f3cc8`（`adopt_pending`） |
| **新口径包围盒实测** | 巡检子作业 `ee8b425cbd724443a38795fbca7b2a8b`（`bounding_box_mm.min[2] = -885.0`） |
| **`resident_panel` 两截面成功** | 作业 `a1bad61759714602801ad6e20ad10314`（`area_mm2 = 5923.681287847949`，探针 `adb51c281ab7485b9dd6349d4a1d3b7e`） |
| **`resident_panel` 三截面成功** | 作业 `ff88246ac3ba4c0494b07e27cf5e2e00`（`slots=3`、`face_count=1`） |
| **面板真实形态（7 截面 + 尖点 + 3 导线）卡死** | 作业 `c6772cdc07c54a52ac853db91b8f3964`（模型 `dcc9eaf5f5cc45e9800548f7b1aba9fb` / `bulb0471`），`stage=panel_macro_submit`，runner 18972 / worker 14872 均已死 |
| **会话级面板锁** | `panel_session_guard.json` → `state=active`、`blocks_toolkit=true`（`2026-11-27T23:56:12+08:00` 起） |
| **`cancel_job` 第二次杀错 pid** | 作业 `c6772cdc…`，`termination.pid = 20248`、`returncode = 128`、`cancelled = false` |

环境：`creo_server_info` → `0.47.1` / `tool_count 112` / `creo_root D:\Program Files\PTC\Creo 10.0.0.0`。

---

## §12 需要 MCP 作者回答的九个问题

1. `runner_detached_from_job: true` 的语义到底是什么？如果 runner 的生命期确实绑在 stdio 会话上，请把回执里的 `message` 改成明确要求「保持会话直到终态」，并把 `runner_detached_from_job` 置 `false`。
2. 对于「runner 已死、`worker_started` 缺失、四类 worker 证据全无」的作业，能否像 §2.3 那样直接判定 worker 未启动，从而放开 `creo_reconcile_model`，而不是把用户逼到重启 Windows？
3. `ExtrudeOp` 能否增加双向不等深（§3.4）？如果短期内不加，请把「需拆两个 op、会生成两条特征」写进 `creo_capabilities`。
4. `creo_adopt_file` / `creo_open_file` 的 `WORKER_SECONDS = 115` 能否改成可配置并按模型规模自适应（§3.5）？现在这条硬编码把「换副本自救」这条唯一退路也堵死了。
5. `creo_callback_status` 在辅助应用程序 Start 成功后，`readiness` 会变成什么值？给一个可判定的期望值，调用方才能确认人工那一步是否点对。
   —— **本轮已自行测出答案**：`readiness = "ready"`、`reason = "live_identity_verified"`（§6.5.1）。建议直接写进文档与回执的 `next_action` 文案里。另请回答 §6.5.5：为什么 `direct_blend_callback.readiness` 在同一时刻仍是 `"unknown"`。
6. **`confirm_panel_closed` 能不能不再要求「作业已终态」？**（§6.6.5）现在的判据会自锁：解锁要终态，终态要 worker 活着，而 worker 恰恰是死的那一个。建议改成「`owners` 全部 `stopped:true` + 人工确认」即可放行。
7. **超时与看门狗为什么要由被监控的进程自己执行？**（§6.6.4）`timeout_seconds=1500` 已过、`stall_watchdog_seconds=600` 早过，作业仍是 `running`。把它们挪到 server 侧按 `job.json` 时间戳判定，这一整类死锁就不存在了。
8. **`creo_cancel_job` 杀的是哪个 pid？**（§2 与 §6.6.5 两次复现）本轮记录的 `runner_identity.pid = 18972`，它去杀 `20248`，`returncode = 128`，`cancelled:false`。
9. **面板路线上，Creo 的模态错误框有没有办法被观测到？**（§6.6.4）本轮是「内核建不出来 → Creo 弹框 → MCP 一无所知」。哪怕只在超时回执里写一句「检测到 N 个模态窗口、标题为 …」，也能把「几何不成立」和「内核拒绝」区分开。

---

## §13 本工程侧处置

> **更新（重启 Windows 之后）**：本轮实际完成了 **rev106 → rev110** 四次提交，见 §13.1。§13 前半段记录的「零几何进展」是重启前的状态，保留以说明锁定过程。

### 13.1 重启后完成的部分（0.47.1 下的实证）

| rev | 内容 | ΔV（mm³） | 复核 |
|---|---|---|---|
| 107 | B106 斜撑下半片（`sketch=12995`，−100 mm） | **+34,157.717** | 棱柱理论 40,060（横截面 400.6 × 100），与既有实体重叠 ≈5,900；新增侧面覆盖 Z −910…−832，底面 400.7 mm² = 草图面积 |
| 108 | B103 斜撑下半片（原件 `sketch=6647`） | **+28,874.160** | +Y 侧吸收更多 B102 板，故小于 107；两个侧面 5287.7 / 5284.6 mm² 覆盖 Z −910…−831.9 |
| 109 | B104 重切（`sketch=9909`，8.4 + 反向 1.0） | **−8,333.103** | 原切除只掉 38.055 → **219 倍**，**D19 的诊断成立** |
| 110 | B106 的 Cut-Extrude16/17 关于 Y=0 镜像（13 ops） | **−14,990.349** | 反射坐标系 `u'×v' = R(n)` 自校验 1.0e-10；bbox 精确镜像 `X 720.6…784.6、Y ∓[114.5…150.3]` |

最终模型：**rev110 / 619 特征 / 1165 面 / 3639 边 / 1 body / 4 quilt / 5,389,727,009.263087 mm³**，`part_sha256 = a4d99bd9…`，`healthy = true`，`pending_job = null`。

**B106 Mirror11 至此 3/3 齐**（Boss-Extrude35 于 rev105、Cut-Extrude16/17 于 rev110）。镜像账：**11 条里 10 条落地**，只剩 B004 Mirror1 / B034 Mirror4 两条吊在曲面链上。

### 13.2 仍未完成 / 新增偏离

- **D27**：切除无特征级范围（§3.6），rev109 多切 ≈4 570 mm³ 进相邻 B102 板。
- **D28**：斜撑厚度只能靠「反向再拉一次」补齐（两个特征），因为 `ExtrudeOp` 无 `depth2`。
- **D29**：两侧斜撑面面积不相等（+Y 被 rev109 的切带劈成两块 5287.7 + 3147.0，−Y 连续一块 9810.3）；**bbox 精确镜像，但不做点对点对称宣称**。
- **B064 Shell1**：`ShellOp` 仍无 region 限定，单 body 无法只抽塔桅。
- **B002/B030/B031/B032/B004/B034**：曲面链，`element_tree` −18 未修。
- **球鼻艏 `resident_panel`**：准入闸全通（§6.4），两截面 / 三截面上的对照件实测成立（§6.5），真实形态的 21 对交叉与 11 个位置也全部通过（§6.6.2、§6.6.3）。但内核在 7 截面 + 3 导线上**构建失败**，且该失败把作业打成永久 `running` 并锁死整个会话（§6.6.4、§6.6.5）。因此**仍不宣称球鼻艏可自动建模**。

### 13.3 曲面通道打通后的实测（本轮新增，与整船模型无关）

曲面侧另起探针零件 `loft_probe_0471` 做了两轮对照，用于回答「`resident_panel` 到底能不能建面」，**不写回 `frigate_v4`**：

| 用途 | job_id | 结果 |
|---|---|---|
| 准入闸三次前置拒绝（未建作业） | 无 job | §6.4 |
| 两截面直纹面成功 | `a1bad61759714602801ad6e20ad10314` | `succeeded/verified`，`area_mm2 = 5923.681287847949` |
| 三截面平滑面成功 | `ff88246ac3ba4c0494b07e27cf5e2e00` | `succeeded/verified`，`slots=3`、`face_count=1`、`area_mm2 = 13198.469846071788` |
| **球鼻艏真实形态（7 截面 + 尖点 + 3 导线）** | `c6772cdc07c54a52ac853db91b8f3964` | **永久 `running`**：21/21 交叉对通过、11/11 位置选中，内核构建失败弹模态框，Done 不返回（§6.6） |

球鼻艏的准备工作全部落盘且可复用（`_bulb_data.py` 存 TXT 原始米制数据并自校验节点数；`_gen_bulb_sketches.py` 生成 47 op 的建面 plan；`_bulb_run.py` 是「同会话提交 + 轮询」的分阶段执行器）。47 个 op 建出的 7 截面 + 3 导线零件 `bulb0471`（`dcc9eaf5…`）已保存为 `bulb0471.prt.3`，61 个特征，可作下一轮对照实验的起点。

下一步是**分离变量的对照实验**（等会话锁清掉再做）：
1. 7 截面 + 尖点，**不带导线**（TXT 明确写的退让方案）；
2. 3 截面 + 3 导线（固定导线数、把截面数降到已验证过的档位）；
3. 若 2 成功而 1 失败 → 问题在截面数；若 1 成功而 2 失败 → 问题在第二方向。
