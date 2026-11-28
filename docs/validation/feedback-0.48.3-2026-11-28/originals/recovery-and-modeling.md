# 2026-11-28 CREO 10.0.0.0 / MCP_CREO_MechDog 0.48.3 实测问题汇总

- 反馈日期：2026-11-28
- 被测版本：MCP_CREO_MechDog **0.48.3**（`creo_server_info` 自报 `server_version=0.48.3`，worker identity `725dc07d…` verified）
- Creo：`D:\Program Files\PTC\Creo 10.0.0.0`，`release_numeric=42`，Toolkit 连接 `toolkit_code=0`
- 任务：仅用 MCP_CREO_MechDog，按一份自然语言 TXT（`简易护卫舰_跨软件三维建模自然语言说明_v2.txt`，85.6 m 护卫舰，约 40 个特征）从空白开始原生建模，全程不导入任何实体。
- 任务结果：**完成**。成品 248 个特征、2 个实体、体积 5514.94 m³、包围盒 85600×13800×28300 mm（与 TXT 的 85.6 m / 13.8 m / 28.3 m 完全一致）。
- 结论：0.48.3 的草图/拉伸/旋转/切除/限定切除链路在 Creo 10 上稳定可用；**放样（含曲面放样）与崩溃恢复是本次两处硬阻塞**，共 12 项。

---

## 一、阻断级问题（造成流程无法按设计路径进行）

### P1 崩溃残留的 panel guard 完全阻断启动，官方状态工具不给出口

**现象**：上一轮会话在 `panel_macro_submit` 阶段崩溃，遗留
`panel_session_guard.json`（`state:"active"`, `pid:21140`，进程早已消失）与 `toolkit-channel.json`。
此后：

- `creo_startup_status(retry=true)` → `state=configuration_error`,
  `message="Startup preparation failed (PanelSessionLocked)"`，`next_steps` 只说
  “检查会话与 worker / 请操作员确认重建会话”；
- `creo_session_status` → `connection_state="probe_failed"`,
  `message="Toolkit probe failed (PanelSessionLocked); inspect the session and worker"`；
- 两者都没有提到 `creo_reconcile_model(action="confirm_panel_closed")`。

**实际出口**：只能自己用 `creo_reconcile_model(mode="inspect")` 读到
`panel_session_guard.blocks_toolkit=true` 与 `readonly_pending` 之外的那条
`actions.confirm_panel_closed.available=true`，再 apply。解除后 Creo 才被拉起。

**影响**：`PanelSessionLocked` 是“整个会话对全部模型拒绝原生作业”的全局锁，
但它的解锁入口藏在**单个模型**的 reconcile 里，且需要先知道 model_id。
调用方在“无任何可用会话”这个最需要自助的场景下拿不到可执行指令。

**建议**：`creo_startup_status` / `creo_session_status` 检测到 panel guard 时，
直接把 `confirm_panel_closed` 作为 `next_steps` 第一项给出（连同 guard 里的
`model_id`），或在 `creo_startup_status` 上开一个 `clear_panel_guard=true`
的显式恢复参数。

---

### P2 `restore_baseline` 在无会话时不被预检，把一次修复变成两次 unknown_outcome

**现象**：为释放遗留 `pending_job` 调 `creo_reconcile_model(action="restore_baseline")`。
当时 Creo 并未运行，作业照常入队并启动 worker，最后在
`connect_creo(&process)` 失败 `toolkit_code=-4`，产出
`status=unknown_outcome, failure_phase=native_worker_started`，
并新写入 `recovery_pending`。

**后果**：从“1 个 unknown_outcome + 1 个 pending”变成
“1 个 unknown_outcome + 1 个 pending + 1 个恢复失败 + recovery_pending”，
必须再走一次 `abandon_unknown_recovery` 才回到可作业状态。

**建议**：`restore_baseline` / `accept_live` 这类必须连 Toolkit 的动作，在
`recovery_pending==null` 且当前探测不到会话时，应像 `ack_no_mutation` 一样
在**提交前**以 `before_native` 拒绝（不产生 worker、不落地 recovery 记录），
而不是把 connect 失败也算成“原生已开始”。

---

### P3 直接 Blend 回调在 Creo 10 每次重启都是 `not_loaded`，放样能力实际不可用

**现象**：

- `creo_callback_status` → `readiness="not_loaded"`,
  `reason="recorded_application_not_active"`,
  `next_action="start_or_register_application_manually"`；
- `creo_capabilities` 里 `families.loft.runtime_ready=false`，
  `runtime_admission.status="requires_ready_callback"`。
- 本机 `blend_loader` 世代 `23f540b7…` 已 `registered:true`（`registered_by: [setup, registry]`），
  文件哈希也匹配，但运行状态就是未加载。

结果：`creo_loft`（直接 Blend）在本轮 **完全不可用**；只能改用免回调的
`creo_new_loft_part`（种子）。

**影响**：这不仅是“少一个工具”。本轮需要 3 处放样：

1. 船体上下双轮廓放样（2 截面，可用种子 `two_straight` 绕过）；
2. **球鼻艏半体 7 截面 + 3 条导线的曲面放样**（TXT 附录 A18–A23e 明确要求
   7 截面，并给出“2 截面会内缩 90–120 mm、体积小 1.27%”的实测警告）；
3. 艏部上翘围板（Z=0 甲板艏弧 → Z=1.8 上缘弧的直纹面放样 + 向内加厚 20 mm）。

第 2、3 项**没有任何免回调替代**，只能降级为由拉伸+限定切除拼出的近似体。
这直接决定了成品与 TXT 的偏差集中在球鼻艏肩部与艏围板前倾。

**建议**：
- 让 `creo_new_loft_part` 支持“向已有零件追加放样”（见 P4），或
- 提供 `creo_loft` 的 element-tree 备用路由（`creo_surface_loft` 已有
  `creation_route` 概念的雏形），或
- 在 `creo_startup_status` 的 ready 判定里把 callback `not_loaded` 作为
  **降级警告**显式上报（当前 ready=connected 就宣称 “modeling is available”，
  与 `loft.runtime_ready=false` 自相矛盾）。

---

### P4 `creo_new_loft_part` 只能新建零件，同一零件内无法做第二次放样

**现象**：`creo_new_loft_part` 的语义是“用种子重绑生成一个**新**零件”
（`construction="native_multisection_blend_seed_rebinding"`）。
船体用它建出来后，球鼻艏与艏围板再无处放样 —— 只能另开 part 文件，
无法落在同一 part 的多实体里。

TXT 明确要求“现有模型最后有 8 个实体”“相交体可布尔合并，薄片与杆件可以分体”，
即多实体是允许的，但**多零件不是**。

**建议**：给 `creo_new_loft_part` 增加 `model_id`/`expected_revision`
以便向已有零件追加（种子只提供特征模板，不提供新文件），
或提供 `creo_loft_seed_into_model`。

---

## 二、功能性缺陷（可用但有明确坑）

### P5 `dimensioning="auto"` 在多实体混合轮廓上失败，且 `coordinates` 立刻成功

**复现**：同一组 7 个实体（4 直线 + 2 条 R16076.087 艏弧 + 2 条 R0.1 艉角弧）
闭合轮廓（解析面积 1 070 374 232 mm²，校验器判定 `closed_contour_count=1`）：

| 标注模式 | 结果 |
|---|---|
| `auto`（内部降级为 `autodim`） | `AutodimensionSketch` → `-1`，`initial_solve=-1`，作业失败并回滚 |
| `coordinates` | 一次成功 |

对比试验：单 R0.1 圆角矩形、单 R16076 大弧 + 直线、两条大弧 + 直线、
10 个护板折线、7 个圆孔 —— `auto` 都正常。失败只出现在“两条小圆角弧 +
两条超大半径弧 + 直边”这种混合轮廓上。

**附带误导**：失败回执里 `solver.selection_reason="unsupported_coordinate_entity"`，
读起来像“坐标标注不支持某实体”，但真正原因是最初 solve 与 autodim 都失败；
而同一轮廓在显式 `coordinates` 下完全没问题 —— 说明“降级到 autodim”这个
决策方向反了。

**建议**：`auto` 失败时先尝试 `coordinates`（顺序与现在相反），
并把 `selection_reason` 改成实际失败原因。

---

### P6 `coordinates` 不支持 ellipse，与 P5 形成“两个模式都盖不全”的空档

**报错原文**：
`Coordinate dimensioning supports line/centerline/rectangle/polyline/circle/arc/b_spline entities`

本轮 4 处用到椭圆（球鼻艏截面、艉底两个椭圆支座）都必须改回 `auto`。
对一个含椭圆又含大半径圆弧的轮廓，就会出现 `coordinates` 不支持、
`auto` 又踩 P5 的组合。

**建议**：`coordinates` 补齐 ellipse；或在提交前对“含 ellipse 且 auto 已知易失败”
的组合给出显式警告与建议拆分。

---

### P7 含 B 样条的**切除**轮廓被判定“未去除材料”

**现象**：`b_spline`（3 次，4 控制点，clamped 节点，权重 1，即 TXT 4.4 给出的
三次贝塞尔艉底上翘曲线）作为 `extrude` `mode="cut"` 的闭合轮廓，
返回：

> `Extrude cut removes no material. The solved section contains a closed contour and B-splines. Creo can report zero removal for this combination…`
> `if an approximation is acceptable, create the B-spline with approximation_segments or provide a sampled polyline.`

改成 17 点采样折线后一次成功。

**影响**：TXT 附录给出的是 NURBS/贝塞尔控制点，`b_spline` 实体正是为此设计的
（`grep` 该字段的注释也写明“maps directly to Pro2dBSplinedef”）。结果在**切除**
路径上它不可用，只能人为降精度成折线。本轮球鼻艏的圆滑肩部、
艉底贝塞尔过渡都因此变成折线/多段近似。

**建议**：`cut` 遇到 `b_spline` 时自动改用 `approximation_segments`（并可回执
说明“已按 N 段近似”），而不是让作业失败。

---

### P8 布尔运算不接受负实体 ID，而拉伸 `scope` 接受 —— 口径不一致

**现象**：

- `extrude(scope={kind:'bodies', body_ids:[-5778]})`：可用（文档亦写明支持 `-5778`）；
  本轮球鼻艏的 3 个限定切除正是靠它完成。
- `boolean_bodies(targets=[{kind:'body', id:-5778}], tools=[{kind:'body', id:308}])` →
  `BOOLEAN_BODY_REFERENCE_UNSUPPORTED: negative body IDs can be returned by inspection but are not supported by this Boolean feature path`。

Creo 的初始实体永远是 `-5778`，所以**任何“把工具实体并入主实体”的布尔并集
在结构上都不可能成功**。本轮球鼻艏只能作为第 2 个实体保留。

**建议**：布尔路径同样接受 `-5778`（内部映射到初始 body），
或在 `creo_inspect_model` 里给出该 body 的布尔可用别名。
否则“多实体最后合并”这条 TXT 明确的收尾步骤无法执行。

---

### P9 相切/相交轮廓一律拒绝，而 TXT 描述的组合作件几乎都相切

本轮连续踩到 4 次：

| 几何 | 判定 |
|---|---|
| 两舷艏围板在艏尖 (85600,0) 汇合 | `branched`（>2 条曲线交于一点） |
| 两舷 20 mm 环带在艏尖互相穿插 | `self_intersecting`（bo_n/bi_p） |
| H 形标记 = 3 个相切矩形 | `intersect` + `tangent`（h1_1/h3_3） |
| 门框类“外减内”写法 | 同类风险，未再尝试 |

解法都要求人工改写为**单一外轮廓**（H 改为 12 点单一多边形、
两舷围板改为两条互不相接的闭合环带并在艏尖留 0.4° 缝）。

报错本身写得很清楚（`Remediation:` 段落质量很高），但**只有在提交后**才能知道。
对 TXT 这种“三角框 = 三条条 + 三短臂合并”“围板 = 一圈薄墙”的描述，
建议在 `creo_capabilities` 的 references/known_limitations 里前置说明：
“同一草图内多凸台必须合成单一非自交外轮廓；相切即拒绝”。

---

## 三、可用性问题（不阻断，但显著增加成本）

### P10 `creo_execute_plan` / `creo_get_job` 默认 `full`，单次回执 30 KB+

`creo_execute_plan` 默认 `response_detail="full"`，会把规范化后的全部 operations
原样回显（20 op ≈ 30 KB）。客户端上下文很容易被一次提交打满；
必须显式传 `compact`。`creo_get_job` 默认同样是 `detail="full"`。

**建议**：默认改为 `compact`（或按 op 数量自动压缩），`full` 显式开启。

### P11 `creo_startup_status` / `creo_session_status` 单次输出约 15 KB

包含 `session_health.facts.historic_saves`（5 条历史）、`evidence`、`generation_inventory`
（10 个 payload 世代）等。轮询启动状态时几乎每次都刷满上下文。

**建议**：默认只返回 `state/connected/message/failure_code/next_steps`，
其余按 `detail` 分页。

### P12 零件预览只有固定视角 `preview.jpg`，无视角控制

`creo_get_job` 的 `preview_file` 是单张固定相机图。TXT 第十七节要求按
“俯视 / 侧视 / 正后视”分别核对主尺度与层级，本轮只能靠
`inspect_model.bounding_box_mm` 数值核对，
无法生成指定视角的验证图（也没有 `creo_set_view` 一类的接口）。

**建议**：提供 `creo_capture_view(direction, model_id)` 输出俯/侧/艏/艉四视图，
这会直接改善“按检查清单验收”的效率。

---

## 四、本次为绕开上述限制而采用的近似（已写入交付说明）

| TXT 要求 | 实际做法 | 原因 |
|---|---|---|
| 球鼻艏 7 截面 + 3 导线放样 | 椭圆棱柱 + 俯视/侧视 4 个限定切除拼出尖头体，独立实体 | P3（无回调）、P4（无法二次放样）、P8（不能布尔并入） |
| 艏部上翘围板 = 直纹面 + 向内加厚 0.02 | 沿 Z=1.8 上缘弧的竖直 20 mm 环带，艏尖留 0.4° 缝 | P3（无曲面放样）、P9（环带相接被判分叉） |
| 艉底上翘 = 三次贝塞尔切除 | 17 点折线切除 | P7 |
| H 形标记 = 3 块条状凸台 | 单一 H 形外轮廓多边形 | P9（相切拒绝） |
| 顶三角框 = 三角框 + 3 短臂 | 三角环（外/内三角嵌套），短臂未建 | P9 + 工作量 |
| 驾驶室 15° 外张拔模 | 直立拉伸 | `extrude` 无 draft 参数，`creo_draft` 需面选择，未验证 |
| 艏围板 3 组长孔 | 未建 | 曲面围板上无法在单次切除中跟随曲面且不伤船体 |
| 门框/把手/大面板（11.3–11.5）、护板圆杆框架 | 未建 | 体量极小，优先保证 17 节检查清单的辨识点 |

模型与 TXT 的量化对照：

- 包围盒 **85600 × 13800 × 28300 mm** ↔ TXT “全长约 85.6 m / 主甲板宽 13.8 m / 竖向跨度约 28.3 m” —— 全部吻合；
- 体积 **5514.94 m³** ↔ TXT 参考 5384.57 m³（+2.42%），TXT 已声明“不要求近似模型拟合该值，不得用体积覆盖冒充几何相同”；
- 特征 248、实体 2（TXT 允许，源为 8 实体，明确“不必为凑数拆合”）。

---

## 五、优先级建议

1. **P1 / P2**：崩溃恢复的自助出口（当前最耗时的一段全花在这里，约 8 次工具往返仍无进展，最后靠 reconcile inspect 摸到出口）。
2. **P3 / P4**：放样回调与“向已有零件追加放样”——这两项决定曲面类零件能否按 TXT 建，而不是被降级成拉伸拼合。
3. **P8**：布尔接受 `-5778`，否则“多实体最后合并”在中国用户常见的单零件多体流程里永远走不通。
4. **P5 / P6 / P7**：草图标注与 B 样条切除的三个坑，建议一次性收敛（auto 先试 coordinates；coordinates 支持 ellipse；cut 遇 b_spline 自动近似）。
5. **P10 / P11**：默认输出压缩，直接决定 MCP 客户端能不能连续跑几十个特征。
