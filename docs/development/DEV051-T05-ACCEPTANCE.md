# DEV-051 T05 验收卡：四壁折边失败定位（FEAT-014 / BUG-047，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线调查完成 / 未复现 / 根因未定**。分支：`codex/dev051-feedback070`；工作区：`E:/Projects/MCP_CREO_MechDog`。本次未连接 Creo、未提交任何 Toolkit 作业、未改版本、未合 main、未推标签、未 push、未发布、未实施 T11。本卡不得读作“折边缺陷已修复”或“四壁能力已具备”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T05 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（T05 节）、[T00 验收](DEV051-T00-ACCEPTANCE.md)、[T03 验收](DEV051-T03-ACCEPTANCE.md)、[T04 验收](DEV051-T04-ACCEPTANCE.md)、[FEAT-014 工作卡](../work-items/FEAT-014.md)、[BUG-047 工作卡](../work-items/BUG-047.md)。
- 反馈证据（原件只读，本次未重取、未重放）：0.7.0 R1 S3，job `f45415a90a0544bfad24fe1225c18f50`，模型 `0fdb2601c11e4471a3352f6254c59ef4`（`acc70_sm2`）：185×232×1 底板，一次计划挂 4 道折边（h=80、R2.54、Y=0.5，边 104/105/106/107）；`f_px`、`f_nx` 成功，`f_ny` 失败（`ProFeatureWithoptionsCreate=-1`），`f_py` = `not_executed`。报告 S10 的逐项结果为 index 2 `f_px` succeeded、index 4 `f_ny` failed、index 5 `f_py` not_executed，成功项均为 `effect_status: rolled_back`。
- 基体采用 T03 已确认薄底板契约（`sheetmetal_wall(depth=1, thickness=232)`，185×232×1 = 42 920 mm³）。T02 的弧方向契约未读写。
- 受派范围仅 T05 离线阶段。工作区中其他会话的未提交改动（`.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`docs/work-items/BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、`0.7.2-FEEDBACK-*`、`docs/validation/feedback-0.7.2-2026-10-28/`）以及本机产物（`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`）未暂存、未改写、未删除。

## 结论摘要

| 项目 | 结果 |
| --- | --- |
| 是否复现 | **未复现**。离线阶段没有 Toolkit 会话，没有任何折边被创建 |
| 根因 | **未定**。四条假设均未解决，未选任何一条作为结论 |
| 是否为“已修复” | 否。无生产改动（`native/`、`src/creo_mechdog/`、`server.py` 均未改） |
| 可离线确定的事实 | 折边元素树只有一个公开方向控制；1 mm 板每侧有两条相隔 1 mm 的平行边界；四道折边合计 66 720 mm³；第三道在材料位于板内侧时与既有两壁各有 ≥77.46 mm³ 角部重叠；前两道之后垂直边界缩短 ≥2 mm |
| 交付物 | 可执行的离线诊断夹具与驱动（默认离线、`--live` 拒绝）、每道预期与判定字段、四条可反驳假设与判定表、T11 设计输入 |

## 离线可确定的事实（读码与几何，不含 Creo 行为）

### 1. 折边原生元素树（静态审计，`native/advanced.cpp` `generic_sheetmetal_flange`）

| 元素 | 当前值 | 含义 |
| --- | --- | --- |
| `PRO_E_FEATURE_TYPE` / `PRO_E_SMT_WALL_TYPE` / `PRO_E_SMT_FLANGE_TYPE` | `PRO_FEAT_WALL` / `PRO_SMT_WALL_TYPE_FLANGE` / `PRO_FLANGE_WALL_TYPE_2D_SWEPT` | 单一折边创建路径 |
| 轨迹 | `PRO_E_STD_CURVE_COLLECTION_APPL` + 一条边引用（`PRO_CURVCOLL_TAN_INSTR`） | 只接受一条边，无多边链 |
| **材料侧** | `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM = flip ? PRO_FLANGE_TRAJ_NORM_FLIP : ..._NO_FLIP` | **唯一**暴露给用户的侧向控制，且只翻转轨迹法向 |
| 壁厚侧 | `PRO_E_SMT_WALL_THICKNESS_FLIP = PRO_B_FALSE` | 固定，无参数 |
| 截面侧 | `PRO_E_SMT_FLANGE_SEC_FLIP = PRO_B_FALSE` | 固定，无参数 |
| 折弯释放 | `PRO_E_SMT_BEND_RELIEF` 两侧 `PRO_BEND_RLF_NONE` | 固定关闭，无 relief 能力 |
| 尖角转圆角 | `PRO_E_SMT_WALL_SHARPS_TO_BENDS = PRO_B_TRUE` | 尖角自动变为 R2.54 折弯 |
| 半径 | `PRO_E_SMT_FILLETS_USE_RAD = TRUE`、`PRO_BEND_RAD_INSIDE`、值 = `radius` | 内侧半径 |
| 展开 | `PRO_DVL_SRC_FEAT_YF_ONLY` + `y_factor` | 只影响展开长度，不影响体积 |
| 父体 | 创建树中**没有** `PRO_E_BODY` | 依附模型当前活动体，不是显式选择 |
| 父引用 | `ProFeatureWithoptionsCreate(模型选择, tree, PRO_FEAT_CR_NO_OPTS)` | 父引用是模型本身 |
| 收尾 | `ProSolidRegenerate(PRO_REGEN_NO_FLAGS)` 后 `remember(op, f, extra)`，`extra.section_path` 记录截面路径 | 每次折边后立即重生成 |

结论：公开参数能到达的只有轨迹法向（`flip`）、半径、高度、角度、`y_factor`；壁厚侧、截面侧、释放、目标体都不由请求控制。因此“第三道 -1”不能仅凭源码归因到某个公开参数，必须实机测量。

### 2. 1 mm 板的“实际边”不是唯一指定

185×232×1 的长方体有 12 条边，每个侧面在 z=0 与 z=1 各有一条**相隔 1 mm 的平行边界边**。按几何选边时若不指明顶/底边界，`+x` 会同时命中两条（夹具实测报错原文：`side +x has 2 parallel boundary edges 1.000 mm apart (bottom, top); pass face='top' or face='bottom'`）。报告只记录了 104—107 四个整数，没有记录端点、相邻面或所在 z 边界，因此**原实验的边选择在记录层面不可重建**，只能按几何重新选择并显式声明 `face`。本任务的夹具因此把 `face` 设为必填，并把 `edge_before_submit`（id/端点/跨度/相邻面/所在边界）列为每道折边的必录判定字段。

### 3. 四壁的几何量（独立 oracle，不用生产代码）

| 项 | 值 |
| --- | --- |
| 底板 | 185 × 232 × 1 = 42 920 mm³ |
| `f_px` / `f_nx` 壁 | 232 × 80 × 1 = 每道 18 560 mm³ |
| `f_ny` / `f_py` 壁 | 185 × 80 × 1 = 每道 14 800 mm³ |
| 四道合计新增 | 66 720 mm³（与 R、Y 因子无关：等厚板体积 = 中性层展开长 × 高 × 厚） |
| 每个角部的重叠下界 | `(h − R) × t² = (80 − 2.54) × 1 = 77.46 mm³` |
| 第三道 `f_ny` 的共享角部 | 2 个（分别与 `f_px`、`f_nx`），重叠下界 **154.92 mm³** |
| 第四道 `f_py` 的共享角部 | 2 个（永远未执行） |

“材料在板足迹内侧”时，`f_px` 占 x∈[184,185]，`f_ny` 占 y∈[0,1]，两者在 x∈[184,185]、y∈[0,1]、z∈[0,80] 相交；“材料在外侧”时两者只共边。这就是把材料侧与角部冲突联系起来的可测量差别：箱体 bbox 在对应轴上相差恰好一个板厚（1 mm，远大于 0.01 mm 容差）。这是**几何预测**，不是已观察到的失败原因。

### 4. 单计划与逐道刷新的差别（夹具推演，非实机）

方向一致的两道（`f_px`、`f_nx`）不共享角部，互不影响；从第三道起，垂直边界在两端各被吃掉一个板厚（折弯半径会吃掉更多，1 mm 是下界）：

| 折边 | 单计划引用跨度 | 逐道刷新后跨度 | 差值 |
| --- | --- | --- | --- |
| `f_px` | 232 | 232 | 0 |
| `f_nx` | 232 | 232 | 0 |
| `f_ny` | 185 | 183 | 缩短 2.0 mm |
| `f_py` | 185 | 183 | 缩短 2.0 mm |

即“一次取四条边 ID”的做法，在第三道执行时引用的已经不是当初那条全长度边界。这只是**引用漂移的必要条件推演**；Creo 是否保留同一 ID、是否因此失败，必须实机判定。

## 夹具与驱动（默认离线）

- `tests/unit/test_sheetmetal_flange.py`（单一来源，33 个用例）：箱体检查载荷（bodies/surfaces/edges，含端点与相邻面）、按几何选边、逐道刷新（边被吃掉、邻边缩短、ID 重编号）、四壁单计划与逐道计划、独立体积/角部重叠/bbox oracle、方向与材料侧分类、判定字段模板、四条假设与判定表、原始证据。
- `tools/test_sheetmetal_flange.py`：执行上述检查并落盘报告。默认严格离线：不实例化 MCP 客户端、不连 Creo、不提交作业；`--live` 在缺少 `--confirm-session-usable` 时返回 2，带该开关仍返回 2，并指向唯一 dev 服务 `MCP_CREO_MechDog_dev`。
- 选边规则只用几何：`side`（+x/-x/+y/-y）+ `face`（top/bottom）+ 当前检查的端点、跨度、边界平面；报告中的 104—107 只在证据区引用，夹具目录里不存在这些 ID（单测断言）。
- 刷新规则取最坏情况（ID 会变、边会被吃掉），因此流程不依赖 ID 稳定性；`assert_edge_current` 在边消失或端点移动时拒绝提交。

## 每道预期与判定字段

驱动为每道折边生成一条记录（`checks.plan_contract.flanges[]`），请求回声与实测字段分开，实测项离线一律为 `null`：

`@text
label, index, side,
flip_input, height_input, radius_input, angle_input, y_factor_input,
edge_before_submit, edge_span_mm, edge_shortfall_mm,
parent_body_before, parent_body_after, new_body,
body_bbox_before, body_bbox_after,
direction, material_side, added_volume_mm3,
feature_health, native_tree,
execution_status, effect_status, toolkit_code, last_feature_errors,
revision_before, revision_after,
saved_file_reloaded_and_verified, rolled_back_rebuild_required
`@

| 折边 | index | 期望新增体积 | 共享角部 | 角部重叠下界 | 判断方向（bbox） | 判断材料侧（bbox） |
| --- | --- | --- | --- | --- | --- | --- |
| `f_px` | 2 | 18 560 | 0 | 0 | `bbox.z_max ≥ 1+40` → up | `bbox.x_max−185 = 0` → inside；`1` → outside |
| `f_nx` | 3 | 18 560 | 0 | 0 | 同上 | `0−bbox.x_min`：0 → inside；1 → outside |
| `f_ny` | 4 | 14 800（全长度）/ 14 640（缩短后 183） | 2 | 154.92 | 同上 | `0−bbox.y_min`：0 → inside；1 → outside |
| `f_py` | 5 | 14 800 / 14 640 | 2 | 154.92 | 同上 | `bbox.y_max−232`：0 → inside；1 → outside |

方向的第三类签名是 `in_plane`：若 bbox 在 x 或 y 上增长约 80 mm 而 z 不变，说明折弯未生效（截面被当成平面延伸）。其余为 `ambiguous`。

## 四条假设与判定表（均未解决）

| ID | 假设 | 探针 | 若成立 | 反驳条件 | 判定字段 |
| --- | --- | --- | --- | --- | --- |
| H1 | 四条边在折边前一次取得；前两道吃掉边并缩短垂直边界，第三道引用已不是全长度边 | 每道前重新检查并比较 id/端点/跨度；逐道单作业；另跑未改动的单计划 | 第三道前 id 消失或跨度每端缩短 ≥1 mm；刷新后提交的失败模式不同或成功但更短 | 第三道前边完全不变 | `edge_before_submit`、`edge_span_mm`、`edge_shortfall_mm`、`execution_status`、`toolkit_code` |
| H2 | 材料在板内侧时第三道与两壁实体干涉；钣金壁不能并体 | 从 bbox 读材料侧；再用“距两角各留 20 mm”的短边尝试第三道 | 内侧失败、短边或外侧成功 | 短边同样失败且预测重叠为 0 | `material_side`、`body_bbox_after`、`added_volume_mm3`、`execution_status`、`toolkit_code` |
| H3 | `flip` 只翻轨迹法向；边切向由面环决定，同一 `flip` 在 +X/-X/垂直边不必是同一材料侧 | 同边、同 h/R/Y，只切 `flip` | 两次落在板的两侧（相差约一个板厚），且 ±X 同 `flip` 不一致 | 同边切 `flip` 仍在同一侧 | `flip_input`、`material_side`、`body_bbox_after`、`direction` |
| H4 | 折边树无 `PRO_E_BODY`，依附活动体；报告的 `bodies=2` 使 body 列表本身不可作证据 | 每道前后记录 bodies（id/state/has_geometry） | 新增体或活动体变化，或出现 body 相关元素错误 | 始终一个活动体且无 body 元素错误 | `parent_body_before`、`parent_body_after`、`new_body`、`feature_health`、`native_tree` |

判定表（驱动 `checks.hypotheses.decision_table`）把观察映射到结论，含“修剪后仍失败 → H2 被反驳”“短边成功 → H2 成立、需 T11 释放”“四壁全部成功但 bbox 方向不对 → 仍不构成能力完成”等分支。离线阶段**没有任何一条被记为成立或根因**。

## 厚底板首道（只记录，不下结论）

基体 `sheetmetal_wall(depth=232, thickness=1)` = 185×1×232；首道折边仍为 h80/R2.54/Y0.5，若落在 185 mm 顶边则体积 oracle 为 14 800 mm³。T03 明确把 bbox 摆放与轴符号列为实机待核项，因此该分支的 `direction`、`material_side`、`body_bbox_before` 均为未知，状态 `pending_t03_live_contract`，本卡不设几何结论。

## T11 设计输入（不在本任务实现）

- 触发条件：实机证明第三道在全长度边上失败、在距两角各留 20 mm 的短边上成功；或实测角部重叠与本文预测一致。
- 能力：壁端折弯释放（bend relief）+ 垂直壁的角部规则。
- 待定参数：释放类型（none/矩形/扯裂/圆形）、宽与深相对板厚、单端或双端及是否可选、角部规则（仅释放/斜接/显式重叠策略）、字段落点（`sheetmetal_flange` 字段或模型级规则）、兼容默认必须保持 `none`。
- 禁止：在调查任务中顺手加未登记的 relief 默认值；在四壁 + 展开/折回 + 编辑 + 重载 + 回滚闭环前宣称四壁能力完成。

## 实际修改文件

新增：`tests/unit/test_sheetmetal_flange.py`、`tools/test_sheetmetal_flange.py`、本卡；更新：`docs/work-items/FEAT-014.md`、`docs/work-items/BUG-047.md`。**未改**：`native/`（无生产改动）、`src/creo_mechdog/`、`server.py`、根兼容包装、`version.py`、台账、README、其他任务的共享契约文件。提交仅按这些精确路径暂存；并发会话的改动与本机产物未暂存、未改写。

## 依赖提交、受测身份与指纹

- 依赖提交：`2726ca54715d547c71c7de61c24fb214ac7f6864`（T00）→ `a3c1f4b3e05668aa57d7225dc16394dd272abec9`（T02）→ `601b4bca` / `f10bee750d6c9d582839306b2ffc029997bfb339`（T03）→ `ffbffaad7d4d315fa3c7da37d32a5aaf447fc57b`（T04，本卡基线）。
- 实现提交：`71210e074f31574f72a8b5c2090882809b4b970a`（本卡首次提交；本节的指纹与报告为其后的同任务提交补正）。
- 受测 commit：`71210e074f31574f72a8b5c2090882809b4b970a`；`dirty=true`（工作区仍有其他会话未提交的文档改动与本机产物，未纳入本批）。提交前同内容运行（HEAD=`ffbffaa` + 未提交本批新增）与提交后运行的源码指纹一致，说明指纹按文件内容计算，可跨提交比对。
- `source_fingerprint`：`667ad6af8ef39b402519b1d9a347c58cbb286869065b44e8e828c144f7d8214b`（`tools/test_sheetmetal_flange.py` 的 provenance 算法，与 T03/T04 驱动同实现：全部已跟踪 `*.py` 与 `native/*.h|*.hpp|*.cpp` 的 CRLF 归一化 SHA256 清单哈希，另加本任务两个新增文件的显式路径；本次清单 264 个文件）。对应提交后报告 `build/sheetmetal_flange/20261028T221337_5ede0851/report.json`，SHA256 `1afa34b492a9032641a524efb7c99d9f7d12d9118e216c292fec3c4bd649db7c`。换指纹后不得混用旧结论。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；pydantic 2.13；ruff 0.17.0（requirements-dev 锁定）。全程未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业；服务版本入口仍为 0.7.2，未改动。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `./.venv/Scripts/python.exe -m unittest tests.unit.test_sheetmetal_flange -v` | exit 0，Ran 33 tests，OK（PowerShell 直接调用时 unittest 写 stderr 会被包装成 NativeCommandError，属调用伪影，以退出码为准） |
| 2 | `./.venv/Scripts/python.exe tools/test_sheetmetal_flange.py` | exit 0；提交后报告 `build/sheetmetal_flange/20261028T221337_5ede0851/report.json`，SHA256 `1afa34b492a9032641a524efb7c99d9f7d12d9118e216c292fec3c4bd649db7c`（另有同名 `report.sha256`）；`provenance.commit=71210e0…`、`dirty=true`、指纹 `667ad6af…`；`status=not_reproduced_offline / undetermined`；内置复跑 33/33 OK。提交前同内容运行 `20261028T221132_793b8ff3`（SHA256 `f0589590…`）指纹相同，不覆盖、不复用其结论 |
| 3 | `.venv\Scripts\python.exe tools/test_sheetmetal_flange.py --live` 与 `--live --confirm-session-usable` | 均 exit 2；第二条打印 `LIVE_REFUSAL`，指向唯一 dev 服务并要求在集成步骤中使用 |
| 4 | `./.venv/Scripts/python.exe -m unittest discover -s tests` | exit 0，`Ran 1226 tests`，OK（259.5 s） |
| 5 | `./.venv/Scripts/python.exe -m ruff format` / `-m ruff check`（两个新增文件） | 格式化后 `All checks passed!`，无新增诊断 |
| 6 | `./.venv/Scripts/python.exe tools/dev_check.py` | exit 0；`success=true`、`unit_tests=passed`；style `lint_findings=30`、`unformatted_files=16`（与 T03/T04 基线一致，本批未新增）；`source.checked_source_sha256=fe4d0dcbadb2a723b2fed21980fb2adc5de443c5ba0a41bb7b1f5be0dbf194b7`，`dirty=true`；报告 `build/development_check.json` |
| 7 | `bridge.py build` | **未执行**：本批无原生改动，执行器源码未变（沿用 T03 生成的 `build/creo_worker.exe`，`build/source.sha256` 未变） |

## 未测项与下一步

- 未测（需实机，按共同契约另行指派并在唯一 dev 服务串行执行，先确认会话可操作与 BUG-001 条件）：底板与四道折边的真实创建；第三道是否重现 `ProFeatureWithoptionsCreate=-1`；每道的 `material_side`/`direction`/`parent_body`/`feature_health`/`native_tree`/`revision`；失败的真实回滚与 `effect_status`；成功后的 `saved_file_reloaded_and_verified`。
- 未测：单计划与逐道刷新的实机对照（本卡只推演了引用漂移的必要条件）；`flip` 正交对照；剪短 20 mm 的第三道探针；厚底板首道（依赖 T03 实机契约）；展开/折回、尺寸编辑；WorkBuddy 黑盒验收；Creo 9/10。
- 缺材料：原始 4 条边的端点/相邻面/所在 z 边界、各道 `flip`、`acc70_sm2` 的 PRT、失败时的元素错误详情均未随报告提供，因此原实验不可逐字节重放；本卡只按几何重建同形场景。
- 下一步：集成人按“给集成人的冲突文件与接口变化”合并；实机阶段按 `live_checklist` 逐道填字段，失败即整件重建（成功项为 `rolled_back`，不能续跑第四道）；结论只按判定表给出，未满足条件时保持“根因未定”；若确认角部干涉，转 T11 设计释放/角部规则。
- 状态口径：本卡可用于“离线调查完成 / 未复现 / 根因未定”；不可写成“已修复”；只有四壁 + 角部几何 + 展开/折回 + 编辑 + 重载 + 回滚全部通过，才可宣称四壁能力完成。

## 给 T01 的公共文档变更需求

1. `creo_sheetmetal_flange` 工具描述补充：`edge` 必须是检查返回的裸边引用；1 mm 薄壁的同一侧有顶/底两条平行边，调用方必须记录实际选中的边界与端点；`flip` 只切轨迹法向，不等同于“材料侧”开关。
2. 能力页注明：折边释放当前固定为 `PRO_BEND_RLF_NONE`，四壁闭合角部没有释放能力；四壁能力未完成，需 T11。
3. 勘误：不要把“第三道 -1”表述为已定位的角部冲突；当前状态是“有失败报告、离线有可反驳假设、实机未复现”。

## 给集成人的冲突文件与接口变化

- 共享冲突面：本批**未改** `native/advanced.cpp`（T05/T11/T12 共用）、`src/creo_mechdog/schema.py`（T02/T03/T05 共用）、`native/generic.cpp`。仅在读码中引用它们，无合并冲突风险。
- 新增文件：`tests/unit/test_sheetmetal_flange.py`、`tools/test_sheetmetal_flange.py`，均为默认离线、`--live` 拒绝、指向唯一 dev 服务的独立夹具；与 T03 的 `test_sheetmetal_contract.py`、T04 的 `test_sheetmetal_overlap.py` 并列，不复制其报告或 oracle 约定。
- 接口变化：无（无工具、字段、错误码变化）。
- 静态断言是变更检测：`check_native_source` 把当前元素值（无 `PRO_E_BODY`、`PRO_BEND_RLF_NONE`、壁厚侧/截面侧固定 FALSE）记为事实。T11 引入 relief 或开放壁厚侧时这些断言会按设计失败，须随 T11 同步更新断言与本卡，不得据此判定回退。
- 文档冲突面：`docs/work-items/FEAT-014.md`、`docs/work-items/BUG-047.md` 由本任务更新；如其他会话也要改同两文件，以先读后追加为准，不要覆盖。

## 2026-10-29 第三轮实机：元素树取证、根因定位与基体契约修正

本节补充 T05 的实机阶段。详细证据、job/model 与命令见 [T11 验收卡](DEV051-T11-ACCEPTANCE.md)"第 3 轮"；结论如下。

- **第一道折边 `-1` 的根因已定**（不再是"未定"）。失败路径取回的两份元素树（本实现 `flange_attempt.xml`、Creo 用 `PRO_FEAT_CR_INCOMPLETE_FEAT` 补全的 `flange_expected.xml`）逐项一致：`PRO_FEAT_WALL`、`PRO_E_SMT_WALL_TYPE=17`、`PRO_E_SMT_FLANGE_TYPE=1`、`PRO_E_SMT_FLANGE_DEPTH` 两侧 `DEPTH_TYPE=4`（TO_END）、`PRO_E_SMT_WALL_HEIGHT_TYPE=0`（NONE）、`SHARPS_TO_BENDS=1`、`SEC_FLIP=0`、`THICKNESS_FLIP=0`；Creo 多出的只是角部释放/斜接/边撕裂/弯表等默认值。没有元素缺失或取值错误能解释 `-1`，Creo 的 `ProErrorlist` 也是空的。
- **承载对象才是原因**：`ProSmtedgeContourGet(edge 125)=-8`（`PRO_TK_BAD_CONTEXT`，"该边不在 green/white 壁面上"），`ProSmtSurfaceTypeGet` 显示 green(101)/white(111) 相距 **232 mm**、四块 185×232 大面全是 `SIDE`。即 T03 以来的"185×232×1 底板"实际是 **232 mm 厚的钣金件**：`sheetmetal_wall(depth=1, thickness=232)` 把板厚写成了 232。体积 42 920 与 bbox 相同，历次验收只核这两个数，因此没被发现。
- **修复**：夹具改为 `plane="XZ"` + `sheetmetal_wall(depth=232, thickness=1)`（真正的 1 mm 板）；折边入口在建树前用 `ProSmtedgeContourGet` 拒绝不在壁面上的边（带 `-8` 原始码与可行做法）。
- **修正后的实机**：底板 42 920（rev 1）→ `f_px` 61 480（+18 560，rev 2）→ `f_nx` 80 040（+18 560，rev 3），两次都 `saved_file_reloaded_and_verified=true`、`smt_contour=4`。
- **仍未定**：两道折边的 bbox 只在 X 增长 80 mm、Z 不变，说明是平铺延伸而不是折弯；体积 232×80×1 与折弯同值，所以 T05 原"体积 oracle"无法区分这两种几何。第三道 `f_ny` 在 `ProFeatureWithoptionsCreate` 内挂起（job `bb5543fb3c66404e95172876fa1ac9aa` 仍 running、`toolkit.lock` 被占用），按规则停止实机。
- **T05 假设表的状态更新**：H1（引用漂移）与 H2（角部重叠）**在本轮均未成立/未验证**——失败发生在第一道，既无边漂移也无相邻壁；H3/H4 未验证。新增结论是"失败可以来自基体不是薄板 / 边不在壁面"，这一条已写进准入错误。

## 2026-10-29 第四轮：四壁未执行（无 Creo 会话）

- 本轮未能执行四壁：Creo 会话在 2026-10-29 19:51:03 由 Windows 关闭（`xtop.exe` `AppHangB1`），`creo_session_status` 返回 `connected=false`、`toolkit_code=-4`，`creo_process_snapshot.processes=[]`；现场见 [T11 验收卡](DEV051-T11-ACCEPTANCE.md) §4.1。
- 折边截面已按库存 `flange_shapes` 重建（单线、无 centerline、腿放在父壁法向）并重建执行器，但**没有实机结果**；四道折边、每道体积增量、角部干涉、H1–H4 假设表全部保持未验证（不得读作通过）。
- 新增 `tools/test_flange_direction.py`：单模型单折边、只看 bbox（Z 增长 ≥72 mm 且向上）、180 s 挂起预算。四壁之前必须先用它确认"折边真的折弯"，否则四壁的体积增量没有判别力（平铺与折弯体积同为 232×80×1 = 18 560 mm³）。
- 下一步：会话恢复 → `tools/test_flange_direction.py --live --confirm-session-usable` 通过 → 再跑四壁。

## 2026-10-29 第六轮：方向实机通过，四壁止于第二道（`f_ny` 回滚）

分支 `codex/dev051-feedback070`，HEAD `cce1922`；手动打开的 Creo 12.4.0.0（PID 15156），`creo_startup_status` → `ready/connected=true`，`session_health=no_failure_observed`。未启动/关闭/重启 Creo、未重提已受理 job、未清保护。

### 方向（A，BUG-047）：`flip` 改到截面侧

- 归因：`flip` 原先写 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM`。22:06 的对照（1 vs −1）bbox、体积、方向完全相同——它不是方向开关。实测 2×2：+X 顶边 `SEC_FLIP=FALSE`→down / `TRUE`→up；+X 底边 `FALSE`→up / `TRUE`→down。侧向相对依附面，`TRUE` = 从选中面法向向外。
- 定口径：默认（`flip=false`）= 向外，`flip=true` = 反向；轨迹法向固定 `NO_FLIP`（与库存 `UgSmtFlgWallCreate.c` 一致）。
- 实机：`tools/test_flange_direction.py --live --confirm-session-usable` → `passed=true`，`build/flange_direction/20261029T222510_9cebd5e1/report.json`（SHA256 `9464933eb94bdee351361fc2265777bfe8f58145f1882af45c3fcf3c2b5f3745`）。两例 rev 1→2、`saved_file_reloaded_and_verified=true`、+18 025.29 mm³；`angle90_outward` up（job `f20a09ec980e4d4a8c31a0d840d4c0de`，回显 `bend_side=outward`）、`angle90_inward` down（job `bb0cdab24f67453d8c0979781a2a8a41`，`inward`）。
- oracle 变更：`|z 增长| ≥ 0.9×height` 判折弯，方向必须等于该例显式期望；不再"只认向上"。

### 四壁（B）：前两道成功，第三道回滚

模型 `fc04dfaf7e9a4d6eb17b900d5276da33`（t11_relief_none_2b54bc），底板 42 920 mm³、rev 1；逐道一 job、每道重新取边：

| 道 | job | rev | 体积增量 | bbox | direction | 重载 |
| --- | --- | --- | --- | --- | --- | --- |
| `f_px`（+x） | `c09759e7d25341d3a98874291273be15` | 1→2 | +18 025.291234 mm³ | `[0,-232,-0.5]`–`[185,0,79.5]` | up | true |
| `f_nx`（−x） | `fc097f17478a4d48a8a64deb2a6effef` | 2→3 | +18 025.291234 mm³ | 同上 | up | true |
| `f_ny`（−y） | `1a2b487ce90b486fb358494ba6afcc22` | 3→3 | 无（回滚） | 不变 | — | — |

- `f_ny` 的边跨度 177.92 mm（两端各被已有折弯占去 3.54 mm），`toolkit_code=-1`、`message="Regeneration produced a failed, suppressed or incomplete feature"`、`rollback_succeeded=true`、`effect_status=rolled_back`；原生日志里 `F_NY` 创建成功但 `status=6`、`geometry_items=[]`。按规则未重提该边、未续跑第四道。
- 与前几轮的差别：失败点从第一道推进到第三道，且前两道是**真实折弯**（Z 增长 79 mm），不再是平铺延伸。四壁能力仍未完成；H2（角部重叠）仍只是候选，尚未被单独证明。
- 报告：`build/sheetmetal_relief/20261029T222754_44e6ab6a/report.json`（SHA256 `d2de17487469f10fba9859a0459cfeb64e593537105c8d5a6df5be9bf829d58f`）。
- 下一道探针（未执行，仍待指派）：把 `f_ny` 的边在两端各内缩 20 mm 后再提交，用于区分"短边可行=角部干涉"与"任何长度都失败=其它原因"；不要重提已回滚的原边。
- **勘误**：前文「给 T01 的公共文档变更需求」第 1 条"`flip` 只切轨迹法向、不等同于材料侧开关"已被本轮 2×2 实测推翻，现行口径为"`flip` = 从依附面向外 / 材料侧 两个方向的切换"。

## 2026-10-30：T05 离线阶段续做——第三壁对照设计冻结、`end_trim_mm` 契约贯通、驱动补齐

分支 `codex/dev051-feedback070`，HEAD `641edb3`（T09D 提交），工作区 dirty（含其他会话未提交改动）。本节为离线阶段续做：接续第六轮"四壁止于第二道、`f_ny` status=6 空几何回滚"的观察，把对照实验设计、夹具、驱动与最小原生修改补完。**未连接 Creo、未提交任何 Toolkit 作业、未改版本、未合 main、未 push、未发布。角部干涉仍为候选解释，未定因。**

### 继承的前序改动（上一窗口已写入工作区，本窗口确认并沿用，未回退、未重写）

| 文件 | 内容 | 本窗口核对结论 |
| --- | --- | --- |
| `native/advanced.cpp`（+43 行） | `generic_sheetmetal_flange` 新增 `end_trim_mm` 分支：两侧深度从 `TO_END` 改为 `BLIND` + `PRO_E_SMT_FLANGE_DEPTH_OFFSET`；无该字段时元素树与旧版逐字节一致（静态断言覆盖） | 完整、非半成品；`bridge.py build` 通过 |
| `server.py`（+13 行） | `creo_sheetmetal_flange` 新增可选参数 `end_trim_mm`，仅在非 None 时写入 operation | **端到端已接通**：server 写 op → `SheetmetalFlangeOp.end_trim_mm` 校验保留 → bridge 全量 JSON 提交 → `native/generic.cpp:2716` 分派 → `advanced.cpp:831` 读取。不是默默无效的参数 |
| `src/creo_mechdog/schema.py`（+14 行） | `SheetmetalFlangeOp.end_trim_mm` 可选正数字段 + 拒绝布尔校验 | 派发时标注为 T02 改动，但内容实为 T05 trim 契约（与 `native/`/`server.py` 同一设计）。按指令未触碰；静态断言 `contract_source` 确认其与本任务其余契约一致 |
| `tests/unit/test_sheetmetal_box_live.py`（新文件） | 三组对照夹具、trim 语义探针与分类器、失败壁五段记录、角部判定表、原生/契约静态守卫，27 用例 | 到位时即 27/27 通过，仅一处 ruff F841（未用变量）由本窗口移除 |

### 本窗口新增

- `tools/test_sheetmetal_box_live.py`（新驱动）：默认严格离线，落盘 `build/sheetmetal_box/<run_id>/report.json` + SHA256；`--live` 无 `--confirm-session-usable` 返回 2，带该开关仍返回 2（`LIVE_REFUSAL` 指向唯一 dev 服务 `MCP_CREO_MechDog_dev`）。检查项：对照设计（full_length / trimmed_20 / order_ny_first / order_ny_second，每 fresh 模型逐道一 job、每道重选边）、oracle 行（trim 行仅按 setback 读法）、trim 探针计划与语义分类自检、准入（全部组计划过 `validate_operations`）、原生 trim 分支静态守卫、契约静态守卫、失败壁五段记录夹具自检、角部判定表可达结论、第六轮证据登记、实机步骤清单。
- `tests/unit/test_sheetmetal_box_live.py`：仅移除 F841 未用变量，其余未改。
- 本卡、`docs/work-items/FEAT-014.md`、`docs/work-items/BUG-047.md` 各追加本节/对应记录。

### 对照实验设计（冻结，未运行）

三组对照 + 顺序梯度，全部在第六轮已验证的 185×232×1 底板与 h80/R2.54/Y0.5 折弯上：

| 组 | 顺序 | f_ny 材料角数 | 目的 |
| --- | --- | --- | --- |
| `full_length` | f_px → f_nx → f_ny | 2 | 复现第六轮形态（观察项） |
| `trimmed_20` | f_px → f_nx → f_ny(两端各缩 20 mm) | 2 | 修剪后成功=角部接触是承重差异（**须先确认 setback 语义**） |
| `order_ny_first` | f_ny → f_px → f_nx | 0 | 0 角失败 ⇒ 角部假设被反驳 |
| `order_ny_second` | f_px → f_ny | 1 | 单角失败 ⇒ 单邻即致命 |

判定表保证：角部干涉仅在「全长失败 + 低角位成功 + 修剪壁成功且 setback 语义被自由壁探针确认」三者齐备时升为 supported；其余一律 undetermined 并记录阻塞原因。**离线无任何观察，现状为 `undetermined_incomplete`，角部干涉 `candidate_only_no_contrast_run`。**

### `end_trim_mm` 语义边界（离线不可定，老实记录）

`ProSmtFlangeWall.h` 对 `PRO_E_SMT_FLANGE_DEPTH_OFFSET` 只记载为 double；Creo 把该偏移量读作「距链端各内缩 setback」还是「自截面起算的壁长」离线无法判定。驱动因此规定：先在自由首壁（f_px on +x，两端均为自由板角）上探测，用实测体积增量对四个候选（setback_from_ends / length_from_section / length_both_sides / trim_ignored）分类，仅 `setback_from_ends` 被确认后才允许提交修剪的第三壁；否则 trim 对照对"角部让位"无判别力，结论保持 undetermined。修剪组回显 `extra["depth_trim"]` 仅作记录，分类以实测体积为准。

### 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.\.venv\Scripts\python.exe -m unittest tests.unit.test_sheetmetal_box_live` | 27/27 OK（改动前即通过；F841 修复后复跑仍 OK） |
| 2 | `.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py` | exit 0；报告 `build/sheetmetal_box/20261030T082547_09fb8658/report.json`，SHA256 `366701e7b13e2c1d3cbef11877a931f07e3fffb15044a1810766f27c3e27a45b`；`status=not_run_offline / undetermined`；内置单测复跑 27/27 OK（首次运行 `20261030T082529_6d3569c7` 为 F841 修复前同内容运行，保留不覆盖） |
| 3 | 同驱动 `--live` 与 `--live --confirm-session-usable` | 均 exit 2；第二条打印 `LIVE_REFUSAL` 指向唯一 dev 服务 |
| 4 | `.\.venv\Scripts\python.exe -m ruff format` / `-m ruff check`（两个新文件） | 格式化后 `All checks passed!`，无新增诊断 |
| 5 | `.\.venv\Scripts\python.exe bridge.py build` | exit 0，执行器 `build/creo_worker.exe` 重建成功（含 `advanced.cpp` trim 分支）；未出现 `native/generic.cpp` 或 `tools/test_arc_direction_live.py` 相关错误 |
| 6 | `.\.venv\Scripts\python.exe -m unittest discover -s tests` | exit 0，`Ran 1449 tests`，OK（287.4 s；含本批 27 个新用例与 schema/server 改动） |

### 未测范围与实机待验步骤

- 未测（全部需实机，按共同契约另行指派、唯一 dev 服务串行、先满足 BUG-001 会话条件）：trim 语义探针及其分类；四组对照的真实创建/失败/回滚；`f_ny` 是否再现 status=6；每道 material_side/direction/revision/重载；`end_trim_mm` 在 Creo 中被接受后的真实几何（setback 还是长度读法）；角部干涉的成立或反驳。
- 实机步骤按驱动 `live_checklist`：探针先行 → 仅 setback 确认后跑 trimmed_20 → full_length/order 两组 → 失败壁按 `third_wall_stage_record` 五段取证（terminal、UNHEALTHY_FEATURES dump、健康检查消息、revision/体积恢复）→ `corner_decision` 映射结论；180 s 未终态即停，不重提、不清场。
- 状态口径：本轮可表述为"第三壁对照设计冻结、`end_trim_mm` 契约贯通、离线构建与回归通过、**根因未定**"；不可表述为"角部干涉已定因"或"四壁能力已具备"。

### 给集成人的冲突文件与接口变化

- 接口变化：`creo_sheetmetal_flange` 新增可选 `end_trim_mm`（>0，缺省行为不变）；`SheetmetalFlangeOp` 同名字段。无破坏性变化，旧计划不受影响（静态守卫 `default_to_end_both_sides` 断言缺省树不变）。
- 本批触碰：`native/advanced.cpp`、`server.py`、`tests/unit/test_sheetmetal_box_live.py`、`tools/test_sheetmetal_box_live.py`（新）、上述三份文档。`src/creo_mechdog/schema.py` 的 `end_trim_mm` 字段为继承的前序改动，本窗口未改。
- 共享冲突面：`native/advanced.cpp`（T03/T11/T05/T13/T12 共用）——本批仅 `generic_sheetmetal_flange` 内新增 trim 分支，与 T02/T09B 正在编辑的 `native/generic.cpp`、`tools/test_arc_direction_live.py` 无交集。`bridge.py build` 时未遇到这两文件的语法错误。

## 2026-10-30 实机对照（第三壁定因）

驱动的 `--live` 按设计拒绝执行（只做离线检查），因此本轮用一次性探针（`build/t05_probe.py`，不进仓库）在实机会话上做三组对照，每组新建模型：

| 对照 | 结果 |
| --- | --- |
| 只建 −y 折边（整条 185 mm 自由边，无相邻折弯） | **succeeded**，边 span 185.0 |
| 先建 +x 折边，再建 −y（−y 边被吃掉一端，span 181.46 = 185 − 3.54） | +x succeeded；−y **failed** |
| 先建 +x、−x，再建 −y（两端各被吃 3.54，span 177.92） | +x、−x succeeded；−y **failed** |

结论（有对照支撑，不再是 candidate）：**第三壁失败的触发条件是“目标边的端部已与既有折弯/折弯圆角相邻”，与边是否全长无关**；整条自由边可建，被吃掉一端就已经失败。先前“角部干涉”的猜测只对了一半——不是两个角同时干涉才失败，单端相邻就足以失败。

尚未定因的部分：失败发生在 `execute_sheetmetal_flange` 的特征再生（`Regeneration produced a failed, suppressed or incomplete feature`），但**具体是截面落在弯曲面外、还是相邻壁料重叠**，离线与日志都不足以下结论；需要在原生侧加几何诊断（截面边是否共面、与相邻 bend 面的最小距离）才能区分。

因此：
- 四壁 4/4 未达成（3/4 是上限，且第 3 壁已证明会失败）。
- 角部处理（corner relief / miter）**未实现**，不加限定地说“支持四壁”是错的。
- 本项保持开放，下一步是原生诊断而不是直接写规则：先证明失败机理，再决定是实现角部释放还是明确拒绝“端部相邻折弯”的组合。

## 2026-10-30：DEV-052 N05 离线阶段——正式探针入口、trim 量测契约与原生失败取证（实机未验）

分支 `codex/dev051-feedback070`，基线 `b10b9f7`（N00—N04/N11/预检已交付，含 N01 的 `79b02ed` 统一 `part_thickness_read`）。本窗口只做离线：未连接 Creo、未创建 MCP 客户端、未运行任何 `--live`、未改 `version.py`、未合 main、未 push。工作区其他窗口未提交改动（`docs/validation/RELEASE-0.8.5.md`、本机产物）未触碰。

### 已交付

1. **正式 live 探针入口**（`tools/test_sheetmetal_box_live.py`）：原“双开关仍 exit 2”的拒绝守卫被真实 live 实现取代（本卡此前各节记录的拒绝行为属于实现完成前的历史）。三组探针固化 10/30 一次性实机探针：`ny_first`（−Y 独立、整条自由边 185 mm）、`px_then_ny`（+X→−Y、一端相邻既有折弯）、`px_nx_then_ny`（+X→−X→−Y、两端相邻，第六轮形态）；加 trim 量测（同一 +x 自由首壁，无 trim 与 `end_trim_mm=20` 各一 fresh 模型，按实测增量分类语义）。每组新件、一墙一 job、每墙从最新 inspect 几何选边（显式 `face="top"`、允许缩短边）、180 s 挂起预算、不重提不重试、首个 unknown 即停（`tools/sheetmetal_live.py` 的 `LiveRunner`，未改动）。
2. **判定口径（纯函数，单元锁定）**：`wall_outcome` 忠实记录每墙 succeeded/failed/unknown（终态缺失或任一必需量测 `edge_span_mm`/`revision_after`/`volume_after_mm3` 缺失即 unknown，绝不判通过）；`probe_group_verdict` 对触发组两个终态都是有效诊断（`trigger_reproduced` / `third_wall_built_not_reproduced`），失败墙始终列在 `failed_walls` 且 **`four_walls_complete` 在一切分支为 False**；`trim_probe_verdict` 只按实测增量分类（setback_from_ends / length_from_section / length_both_sides / trim_ignored / unresolved），基线增量与独立 oracle 不符或测量缺失一律不通过、不喂角部归因。
3. **原生失败取证**（`native/advanced.cpp`，只走失败路径，成功路径行为不变）：`flange_edge_forensics` 记录依附边实测长度（`ProEdgeLengthEval`）、两端点（`ProEdgeXyzdataEval` 参数 0/1）、相邻两面（`ProEdgeNeighborsGet` + `ProSmtSurfaceTypeGet`）与相邻两条边，查询失败一律 null；`flange_created_feature_evidence` 在 regenerate 后立即查 `ProFeatureStatusGet`，非 `PRO_FEAT_ACTIVE`（第六轮即 `PRO_FEAT_UNREGENERATED=6`、geometry 0）时记录特征 id/status/geometry 计数 + 上述边取证 + 截面腿请求回显，经 `stage_operation_result` 进入失败操作记录并整块写 `FLANGE_FAILURE_EVIDENCE=<json>` 日志；表面类型访问封顶 `FLANGE_EVIDENCE_MAX_SURFACES=64`（全量仍在逐面日志）。`flange_tree_evidence`（create 失败路径）同样补入边取证。**给 N06 的字段语义**：`feature_status=6` = created but unregenerated；`geometry_item_count=0` 且 status 6 = 第六轮形态；`end0_mm/end1_mm` 是依附边两端实测坐标；`adjacent_faces[].smt_type` 是 Creo 钣金面型（1 SIDE / 2 FACE-green / 3 OFFSET-white）；`section_leg_sketch` 是请求回显，实测壁位置以驱动 inspect 为准。回滚证据仍由 job 结果（`rollback_succeeded`、revision/体积）与驱动 `third_wall_stage_record` 五段记录承担，原生不重复记录。
4. **回归锁定**（`tests/unit/test_sheetmetal_box_live.py`，49 用例）：缺一个开关 → exit 2 且不创建任何客户端；输出不覆盖（离线与 live 双路径、唯一 `--output`）；默认输出迁到 `build/post090_n05/<run_id>/report.json`；未知测量不判通过；第三壁失败永不记为成功、`four_walls_complete` 恒 False；`require_manual_start` 拒绝 `auto_start_creo≠false`；原生取证静态守卫 11 项 + trim 分支守卫保留。

### 命令与真实结果（本窗口，离线）

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.\.venv\Scripts\python.exe -m unittest tests.unit.test_sheetmetal_box_live` | exit 0，Ran 49 tests，OK |
| 2 | `.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --output build\post090_n05_20261030T231033\report.json` | exit 0；报告 SHA256 `aca0026717895f02187feb45e9105cc89ba7ac57e940f56f7dfc9451399bb387`；内置复跑 49/49 OK；`status=not_run_offline / undetermined` |
| 3 | `.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --live`（缺开关） | exit 2，未创建客户端 |
| 4 | `.\.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-014` | exit 0；`success=true`、单元 `passed`；style `lint_findings=30`、`unformatted_files=16`（与基线一致，本批无新增）；`source.commit=b10b9f7`、`dirty=true`、`checked_source_sha256=938f861531863b66c71d42b0de4e1991aedcd1da52a8bb97ec884024e31f274a` |
| 5 | `.\.venv\Scripts\python.exe bridge.py build` | exit 0 ×2（诊断代码与 clang-format 后各一次）；`build/source.sha256=47a6591d17b8ef6b81530963ea2096e2b424892be3e4b1dba378c64cd93a1d8b` |
| 6 | `ruff format` / `ruff check`（两个 Python 文件）、`clang-format -i native/advanced.cpp` | 全部通过 |

### 实机命令与判定口径（给实机负责人，本任务未执行）

前置：人工核对 BUG-001 会话条件可操作、`config.json` `auto_start_creo=false`、唯一 dev 服务 `MCP_CREO_MechDog_dev`、受测源码为含本批提交的执行器（`build/source.sha256=47a6591d…`）。命令（输出路径必须唯一新路径）：

```text
.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --live --confirm-session-usable --output build\post090_n05_live_<run_id>\report.json
```

判定口径：驱动先跑 trim 量测（无 trim 基线增量须贴合 `bent_wall_increment_mm3(span)`，再按 trimmed 增量给出语义分类；仅 `setback_from_ends` 确认后，离线设计里的 trimmed_20 对照才允许提交）；随后三组探针。每墙状态按记录忠实判读：`ny_first` 的 `f_ny` 期望建成且为真实折弯（bbox Z 增长 ≥72 mm）+ 保存重载 true；`px_then_ny` / `px_nx_then_ny` 的第三墙**失败是已证触发条件的复现**（记录 `trigger_reproduced` 与失败取证），成功则记 `third_wall_built_not_reproduced`——两者都不是四壁能力完成，报告 `four_walls_complete` 恒为 false。失败墙取 `native_failure_evidence`（边端点/相邻面/特征 status/geometry 计数）与 `stage_record` 五段，作为 N06 机理证据；180 s 未终态、busy、unknown 一律停止并保留现场，不重提、不清保护。

### 未测范围

- 全部实机项：trim 量测与语义分类、三组探针的真实创建/失败/取证、`f_ny` 是否再现 status=6、原生取证字段的实测值、失败回滚后继续合法操作。
- 离线设计中的 trimmed_20 / order 组仍冻结，等 trim 语义实测；corner relief / miter 未实现（N06 范围）。
- 本机产物（`build/post090_n05_20261030T231033/`）不入库；Creo 9/10、WorkBuddy 黑盒均未验。

## 2026-10-30：DEV-052 N05 实机预检中止（追加，不覆盖离线结论）

基线 `d2a6888`，分支 `codex/dev051-feedback070`，`build/source.sha256=47a6591d17b8ef6b81530963ea2096e2b424892be3e4b1dba378c64cd93a1d8b`；执行前工作区已有他人未提交内容。`config.json` 的 `auto_start_creo` 前后均为 `false`，dev 客户端指向 E 盘。执行前无 Creo 进程，使用 `creo_startup.py` 的受限 Explorer/PSF 启动函数仅请求一次；`parametric`、`xtop`、`nmsd`、`pro_comm_msg` 随后出现，`xtop` 有可见且未被 Windows 标为挂起的窗口。

GUI 控制接口不可用，无法确认菜单、视图和对话框可操作；另有两个既存 `unknown_outcome` 模型未处置。按 BUG-001 / BUG-091 停止，保留会话与保护，未做 Toolkit 连接、会话状态探测或 N05 live 提交。判定为**实机未验—会话不可用性未排除**，不把进程存在判为就绪。trim 四候选语义、三组折边、触发复现、原生失败字段、保存重载及 N06 内部机理均无本次实测结论；四壁能力仍未完成。完整原始错误、PID、未测字段与报告 SHA256 见 [本次预检记录](DEV052-N05-LIVE-PREFLIGHT-2026-10-30.md)。

## 2026-10-30：DEV-052 N05 首次正式实机探针（追加）

编排方 23:32 已截屏及 UI 自动化确认 Creo 12.4.0.0 GUI 可操作、无模态框；本轮 `tasklist` 核同一 `parametric`/`xtop` PID 25596/21968，`auto_start_creo=false`、dev 服务指向 E 盘。基线 `e094bf5`，`build/source.sha256=47a6591d17b8ef6b81530963ea2096e2b424892be3e4b1dba378c64cd93a1d8b`。两项历史 unknown 保护保持不动。

正式驱动唯一 run `20261030T233639_cb833e2b`：trim 无/有 `end_trim_mm=20` 两件的折边增量同为 18025.291234051932 mm³，实测分类 **`trim_ignored`**；未确认 `setback_from_ends`，`trimmed_20` 对照继续冻结。`ny_first` 的 −Y 自由壁成功，Z 增长 80 mm、保存重载 true。`px_then_ny` 驱动标 `trigger_reproduced`，但所选 −Y 边仅 1 mm、为 rim 边，原生 `ProSmtedgeContourGet` 返回 `PRO_TK_BAD_CONTEXT (-8)`；revision/体积回滚，`native_failure_evidence=null`，无 `FLANGE_FAILURE_EVIDENCE`。故本次不能认定此前的特征创建失败机理已复现。`px_nx_then_ny` 在成功的 +X 后因 `side -x has no top boundary edge` 选边异常停止，−X/−Y 均未提交。驱动 exit 1，未重跑；`four_walls_complete=false`。

完整 job/model ID、revision、几何、原始错误、停止范围、报告路径与 SHA256、N06 机理边界见 [N05 实机记录](DEV052-N05-LIVE-2026-10-30.md)。本次未改源码、未结束 Creo、未清保护；Creo 9/10 和 WorkBuddy 黑盒未测。



## 2026-10-31：N05 首跑结论更正——px_then_ny 的 trigger_reproduced 判定无效（追加，不改写上节）

对上节首跑（run `20261030T233639_cb833e2b`）的判定做如下更正，原记录保留不改写：

- **`px_then_ny` 的 `trigger_reproduced` 无效。** 驱动为 `f_ny` 选到的是 +X 墙端 1 mm rim 边（edge 211，span 1.0 mm，z=79.5），不是 185 mm 级的 −Y 顶部长边。根因在驱动选边：`submit_wall` 用折边后的整件 body bbox（Z 顶=79.5）做 `face="top"` 分类，真正的板顶边（z=0.5）被归为 other；`allow_shortened` 又无下限，1 mm 厚度尺度边被当作缩短边提交，Creo 以 `ProSmtedgeContourGet` 返回 `PRO_TK_BAD_CONTEXT (-8)` 拒绝附着。这是**输入附着失败（驱动缺陷）**，不是特征再生失败机理的复现；`FLANGE_FAILURE_EVIDENCE` 未取得，机理证据仍缺。
- **同根第二处：`px_nx_then_ny` 的停止也是驱动缺陷。** +X 成功后 −X 侧报 `side -x has no top boundary edge`，是同一 bbox 误分类把 −X 板顶边（z=0.5、span 232）排除所致；−X/−Y 未提交属选边异常中止，不构成该组判定。
- **不受更正影响的事实**：trim 两组实测与 `trim_ignored` 分类、`ny_first` 的 −Y 自由壁建成（Z 增长 80 mm、保存重载 true）、全部 job/model ID、revision、回滚证据与原始错误原文均维持原记录。
- **离线修复（随本次提交交付，未实机）**：选边改为相对基线板 bbox（base snapshot 冻结，fresh inspection 只供候选边与 revision）；排除厚度尺度 rim 边（span ≤ 2×板厚）；`allow_shortened` 加有界下限（超过两端 bend 消耗 2×(R+t) 即拒绝）；选边不唯一/不合格在驱动中记 `driver_edge_selection_error`（组判定 passed=false），永不记为 Creo 失败或触发复现。新增单元锁定：rim 边失败判驱动错误而非 `trigger_reproduced`、−X 侧选边确定性、body bbox 误用必失败。
- 实机需以新 runid 重跑正式驱动复验本修复；本更正只改判定有效性，"机理证据仍缺、四壁未完成"的现状不变。

## 2026-10-31：DEV-052 N05 修复后实机重跑预检中止（追加）

本轮为唯一实机负责人，分支 `codex/dev051-feedback070`；执行前 `git log -1` 为 `0f1844ac992821010f95c9adfa9a07295ea65112`（含选边修复 `a94139e`），`build/source.sha256=19036d6467e69320e3d10a999c06fd68a2e26aef824c8021399aae18dbb27ac6`。执行前工作区已有 `docs/validation/RELEASE-0.8.5.md`、`session_activity.json` 及本机未跟踪内容，本轮未修改。`tasklist` 见 `parametric.exe` PID 25596、`xtop.exe` PID 21968、`nmsd.exe` PID 11824、`pro_comm_msg.exe` PID 23448；`config.json` 的 `auto_start_creo=false`。沿用编排方已完成的 GUI 可操作核验，本轮未重启 Creo。

命令：`.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --live --confirm-session-usable --output build\post090_n05_live_20261031T113052_81f5a63d\report.json`。输出路径唯一新建；报告内部 `run_id=20261031T113053_97caa6aa`。驱动退出码 1，报告路径 `build/post090_n05_live_20261031T113052_81f5a63d/report.json`，SHA256 `C134417A5913DC6019D007A153676DA551B43088BA60FD74DDAB28D2C2B30C5F`。报告分阶段落盘，`cases=[]`，仅有 118 次 `creo_startup_status` 调用，无任何底板或折边提交；所有组的 job_id、model_id、revision、终态、几何量测、失败取证及保存重载均为**未产生/未验证**。历史两个 `unknown_outcome` 模型保持不动，未查询或清理。

停止原因：`LiveRunner.start` 抛出 `LiveStop: Toolkit is not ready; nothing submitted`。最后启动状态为 `state=timeout`、`connected=false`、`in_flight_phase=waiting_for_connection`、`coordinator_running=true`，原生连接观测为 `connection_state=not_found_or_unreadable`、`toolkit_code=-4`；只读健康摘要为 `status=unknown`、`reason=session_identity_stale`。当时通道 owner 记录为 `operation=session_status`，无 job_id/model_id；不能由此断定 Creo 本体已退出或连接超时的根因。退出后 `tasklist` 仍见原 `parametric`/`xtop` PID，协调进程 PID 23892 已不在任务表；未做第二次连接、重提、重启或清保护。报告顶层 `passed=true` 与 `stopped` 并存，且 `cases=[]`，因此该布尔值**不构成 N05 实机通过**；按实际停止原因判为**实机未验—会话不可用**。

本轮没有 trim 量测，`end_trim_mm` 语义仍仅有 10/30 首跑的 `trim_ignored` 观察；修复后的 `ny_first`、`px_then_ny`、`px_nx_then_ny` 均未执行，181.46 mm 与 232 mm 板顶边选择、触发条件复现、`FLANGE_FAILURE_EVIDENCE`、回滚和保存重载均未复验。**给 N06 的机理结论：**无新增附着边端部/邻接折弯、截面越界或相邻料重叠证据，内部机理仍未定；不据本次预检推断角部方案。会话保持运行；Creo 9/10、WorkBuddy 黑盒及四壁能力未验。

## 2026-10-31：N05 单次重启后正式重跑（追加，更新当前实测口径）

分支 `codex/dev051-feedback070`，执行前提交 `794ad07`，执行器 `build/source.sha256=19036d6467e69320e3d10a999c06fd68a2e26aef824c8021399aae18dbb27ac6`；其他工作区内容未触碰。按本次授权以 `creo_startup.py` 的 Explorer/PSF 路径只请求一次启动，新四进程出现；正式驱动确认 `startup=ready/connected=true`、`session.connected=true` 后提交。唯一命令 `.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --live --confirm-session-usable --output build\post090_n05_live_20261031T114634_restart\report.json`，run_id `20261031T114635_d85e4c3e`，exit 0；报告 SHA256 `F39DBCC161F18398FB2F8B62BC1DBAB876833079D964326C14B8D2F69A87346F`。此前 R1 连接失败与编排方旧进程处置见 BUG-091；本次没有再次重启、清保护或重提。

trim 先行：无 trim / `end_trim_mm=20` 的 fresh +X 折边均 succeeded、rev 1→2、增量同为 18025.291234051932 mm³、保存重载 true，故仍判 **`trim_ignored`**，`trimmed_20` 对照冻结。`ny_first` 的 −Y 自由顶边 185 mm，job `61a584f8a0b0413aaaa718cc846c90da` 成功、Z 增长 80 mm、重载 true。`px_then_ny` 的 `f_ny` job `36defb2ad3ca400abd7b65f5ef839cc7` 确实选中 181.46 mm 板顶 edge 197（此前的 1 mm rim 选边缺陷已排除），rev 2→2 failed、体积恢复、回滚 true；`px_nx_then_ny` 的 `f_nx` job `000c1f474c94415c96509afcf82e82b9` 确定性选中 232 mm 顶边并成功，随后 `f_ny` job `1e8f8ed96f6e4719874393a9f56f82d0` 选中 177.92 mm 板顶边，rev 3→3 failed、体积恢复、回滚 true。两组均为真实提交后的 `trigger_reproduced`，不是 `driver_edge_selection_error`；没有 busy、新 unknown 或 180 s 未终态。失败墙无成功保存重载，成功墙重载 true，`four_walls_complete=false`。

原生日志两处 `FLANGE_FAILURE_EVIDENCE` 均记录 `stage=after_regenerate`、`feature_status=6`、`geometry_item_count=0`，边长/端点与驱动检查一致，相邻面型 1 SIDE / 2 FACE-green；但报告汇总的 `native_failure_evidence=null`、`stage_feature_state.line_found=false` 漏取了这些原始行。给 N06 的结论仅到**真实板顶边上的端部邻接折弯触发特征未再生**；截面越界或相邻料重叠仍不能区分，角部方案不能据此定型。逐组 model/job ID、revision、体积、取证字段、原始日志 SHA256 与重启证据见 [N05 实机记录](DEV052-N05-LIVE-2026-10-30.md#2026-10-31单次重启后的-n05-修复复验追加)。本次 `passed=true` 表示探针完成且诊断成立，不表示四壁能力完成；新会话留在运行。

