# DEV-051 T11 验收卡：四壁释放完整能力（FEAT-014，离线实现阶段）

日期：2026-10-29（Asia/Shanghai）。阶段：**离线实现完成 / 四壁与释放能力待原生验收**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业、未建模、未改版本、未合 main、未推标签、未 push、未发布，未实施 T12/T13。本卡不得读作“四壁能力已具备”或“折边缺陷已修复”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约与 T11 节）、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)（FEAT-014 节）、[T05 验收](DEV051-T05-ACCEPTANCE.md)（真实失败候选、边选择、角部重叠下界、T11 设计输入）、[T03 验收](DEV051-T03-ACCEPTANCE.md)（185×232×1 = 42 920 mm³ 有效薄底板）、[T09B 验收](DEV051-T09B-ACCEPTANCE.md)（只增不改、实测与请求分离的回显先例）、[FEAT-014 工作卡](../work-items/FEAT-014.md)。
- 真实失败候选（外部原件，本次未重取）：0.7.0 R1 S3，job `f45415a90a0544bfad24fe1225c18f50`，模型 `0fdb2601c11e4471a3352f6254c59ef4`（`acc70_sm2`），185×232×1 底板 + 4 道 h80/R2.54/Y0.5 折边，第三道 `f_ny` 返回 `ProFeatureWithoptionsCreate=-1`，第四道未执行。
- 受派范围仅 T11 离线阶段。工作区中其他会话的未提交改动（`.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`docs/work-items/BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、untracked 的 `0.7.2-FEEDBACK-*` 与 `docs/validation/feedback-0.7.2-2026-10-28/`）与本机产物（`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`）未暂存、未改写、未删除。

## SDK 能力核对（以本机 Creo 12.4.0.0 头文件为准）

头文件：`C:\Program Files\PTC\Creo 12.4.0.0\Common Files\protoolkit\includes\ProSmtFlangeWall.h`（驱动在存在 `config.json` 的 `creo_root` 时实际解析该文件，本次 `status=parsed`、`matches_transcription=true`）。

| 事实 | 头文件证据 | 本次结论 |
| --- | --- | --- |
| 折边每个弯端各有一个释放复合元素 | `PRO_E_SMT_BEND_RELIEF` → `PRO_E_SMT_BEND_RELIEF_SIDE1`/`SIDE2`（元素表 209—211 行） | 单端/双端可分别控制，无需新建特征 |
| 释放类型枚举 | `ProBendRlfType`（357 行）：NONE=0、RIP=1、STRETCH=2、RECTANGULAR=3、OBROUND=4、PARAM=5 | 只有 NONE 与 RECTANGULAR 进入本次契约 |
| 深度类型枚举 | `ProBendRlfDepthType`（507—511 行）：NOT_USED=-1、BLIND=-4、UP_TO_BEND=-7、TAN_TO_BEND=-8、PARAM=-25 | 固定 BLIND，深度由调用方给数值 |
| 宽度/深度/长度约束 | `ProSmtEditBendRelief.h` Note-4~9（163—179 行）：宽度在非 RIP 类型必填且 >0；深度类型在非 RIP 类型必填；TAN_TO_BEND 仅对 OBROUND 有效；BLIND 时深度必填、正或零，且从折弯边量起 | 宽度 >0、深度 ≥0、BLIND：与 SDK 一致 |
| 角部/斜接/边撕裂也存在 | `PRO_E_SMT_CORNER_RELIEF`（221 行起，`ProCornerRelType` 423 行：V_NOTCH/CIRCULAR/RECTANGULAR/OBROUND/NO/PARAM/SQUARE/NORMAL）、`PRO_E_SMT_MTR_CUTS`（229 行）、`PRO_E_SMT_EDGE_RIP`（241 行起，437 行枚举） | **不实现**；未做任何自动角部推断 |

## 选定形状与规则（最小可交付）

单一新增形状：**`rectangular`（矩形释放）**，加兼容默认 `none`。理由：它是 SDK 中唯一能用两个显式数值（宽、深）完全控制几何的释放类型；RIP 没有宽深，STRETCH/OBROUND 对盒角无额外必要，PARAM 会退回零件级默认参数而不受本特征控制。

字段落点：`sheetmetal_flange` 操作的可选 `relief` 对象（新增，缺省即旧行为）。

| 规则 | 定稿 |
| --- | --- |
| 兼容默认 | 省略 `relief` 与 `{"type":"none"}` 完全等价：两个弯端仍写 `PRO_BEND_RLF_NONE`，旧调用/旧计划 payload 不新增键、不改变几何 |
| 类型 | 仅 `none`、`rectangular`；rip/stretch/obround/param 与 `auto`/任意未知值在准入处拒绝，绝不静默降级为 none |
| 宽度 | `width > 0`，模型单位（mm），非 RIP 类型必填；不接受 `"1t"` 之类厚度倍数 |
| 深度 | `depth >= 0`，模型单位（mm），固定 `PRO_BEND_RLF_DEPTH_BLIND`，从折弯边量起；不可省略、不走 UP_TO_BEND/TAN_TO_BEND |
| 端部 | `ends` ∈ `both`（默认）/ `side1` / `side2`；未选中的端保持 NONE |
| 厚度规则 | 宽深是**绝对模型单位**，不按板厚缩放、不提供 1×t 之类默认；原生在特征创建后查询 `ProSmtPartThicknessValueGet`，把实测板厚与两项请求算术（`width_at_least_thickness`、`depth_covers_corner_run`）写入别名记录 |
| 材料侧 | 未改：仍只由既有 `flip` 控制轨迹法向，relief 不引入任何材料侧或 `auto` 字段；两参数互不影响（单测断言） |
| 角部规则 | 只做释放，不做斜接/角部释放/边撕裂，也不按边或角几何猜测规则 |
| 编辑路径 | relief 是**创建期属性**：执行器没有特征重定义；命名尺寸 `height` 仍由 `creo_set_dimensions` 编辑。修改 relief 的受支持路径是 `creo_feature_state` 删除/抑制折边后重新创建（并重建依赖该边的后续折边），本次未执行 |
| 非法组合 | `none` 带 width/depth 或 ends≠both、`rectangular` 缺宽或缺深、宽 ≤0、深 <0、bool/inf/超界、未知端部、未知键、`auto` 一律在建模前拒绝 |

未支持（明确列出，不提供替代路径）：`rip`、`stretch`、`obround`、`param`；角部释放（`ProCornerRelType` 全系）、斜接（`PRO_E_SMT_MTR_CUTS`）、边撕裂（`PRO_E_SMT_EDGE_RIP`）、释放长度/角度（`PRO_E_BEND_RELIEF_LENGTH*`/`ANGLE` 保持未设置）、按几何自动选角部规则。

## 实现

1. `src/creo_mechdog/schema.py`：新增 `FlangeRelief`（`type`/`ends`/`width`/`depth`，bool 维度显式拒绝）并作为 `SheetmetalFlangeOp.relief` 可选字段；`validate_operations` 既有有限性与引用扫描自动覆盖新块，独立工具与 execute_plan 同享准入。
2. `native/advanced.cpp`：新增 `FlangeReliefRequest`、`flange_relief_request(op)`（在建任何元素前校验，未知类型/端部抛错）、`flange_relief_side(...)`（每端写 TYPE；启用端再写 WIDTH/DEPTH_TYPE=BLIND/DEPTH）、`flange_relief_record(...)`（请求端部、实测板厚、`corner_overlap_run_mm = max(0, height - radius)`、两项请求算术）。`generic_sheetmetal_flange` 用两处 `flange_relief_side` 取代原来的固定 NONE 循环，仅在请求里带 `relief` 时写 `extra["relief"]` 别名记录；`PRO_E_BODY`、`PRO_E_SMT_FLANGE_SEC_FLIP`、`PRO_E_SMT_WALL_THICKNESS_FLIP`、父引用、重生成与 `section_path` 全部保持原样。
3. `server.py`：`creo_sheetmetal_flange` 增加可选 `relief` 参数（带契约描述），仅在非 None 时写入操作体，旧调用 payload 不变。
4. 测试：新增 `tests/unit/test_sheetmetal_relief.py`（41 项）、`tools/test_sheetmetal_relief.py`（默认离线、`--live` 拒绝）。
5. T05 静态断言随已核事实同步更新（见下节）。

## T05 静态断言的按设计失败与同步

`tools/test_sheetmetal_flange.py` 的 `check_native_source` 以“函数体内出现的元素值”作为变更检测。relief 逻辑移入 `flange_relief_side` 后，旧断言按设计失败：

```text
AssertionError: native source guard missing: ['bend_relief_none_both_sides']
```

处理方式是**更新为新的已核事实**，不是回退或删除：

| 旧断言 | 新断言 |
| --- | --- |
| `bend_relief_none_both_sides`（flange 体内出现 `PRO_BEND_RLF_NONE`） | `bend_relief_compound_both_ends`（flange 体内有 SIDE1/SIDE2 复合元素）+ `bend_relief_default_none_both_ends`（`enabled ? RECTANGULAR : NONE` 在 relief 体内）+ `bend_relief_rectangular_opt_in`（WIDTH/DEPTH_TYPE/BLIND/DEPTH）+ `bend_relief_other_shapes_absent`（RIP/OBROUND/STRETCH/PARAM 不出现）+ `corner_miter_rip_absent` + `relief_validated_before_create` |
| `parent_is_the_model_not_a_body_element`（flange 体内无 `PRO_E_BODY`） | 保留（仍为事实），并在元素树说明中补“父体仍隐式、relief 不引入 body 选择” |
| 元素树 `fixed_not_exposed` 中的“relief 固定 NONE” | 改为“side1/side2 默认 NONE，rectangular 为 opt-in；角部/斜接/边撕裂仍未暴露” |

T05 的 `t11_design_input()` 增加 `t11_status`，说明该设计已离线实现、原生验收未做，四壁能力仍开放。

## 入口覆盖

| 入口 | 路径 | relief 准入 | 旧行为 | 本次证据 |
| --- | --- | --- | --- | --- |
| 独立工具 `creo_sheetmetal_flange` | `server.py` → `general.submit` → `validate_operations` → 原生 | schema 统一校验 | 不传 `relief` 时操作体不含该键 | 单测（工具签名/描述断言）+ 驱动矩阵 |
| 计划 `creo_execute_plan` | 同一 `validate_operations` | 同上（含同计划 4 道折边） | 旧四壁计划 payload 不变 | 单测 `FourWallReliefPlanTest`、驱动 `default_compatibility` |
| 原生纵深防御 | `flange_relief_request` 在建树前 | 未知类型/端部/缺宽深抛错 | 无 relief 时两个端点仍是 NONE | 静态断言 + `bridge.py build` |
| 编辑 | `creo_set_dimensions`（`height`）、`creo_feature_state` 删除/抑制后重建 | 不适用 | `height` 尺寸名与 `section_path` 未改 | 单测 `EditPathTest`（静态）；实机未验 |

## 几何期望（独立算术，不是实机测量）

| 项 | 值 |
| --- | --- |
| 底板 | 185×232×1 = 42 920 mm³ |
| 四道墙（span×h×t） | 18 560 + 18 560 + 14 800 + 14 800 = 66 720 mm³ |
| 矩形释放每端移除 | `width × depth × thickness`；两端 = 2× |
| thickness_scale 档（1×1，两端） | 每道移除 2 mm³；四道合计 66 712 mm³；体总量期望 109 632 mm³ |
| corner_run 档（宽 1、深 77.46） | 第三道移除 154.92 mm³，等于 T05 的双角部重叠下界 |
| 共享角部走向长度 | `height − radius = 77.46 mm`（T05 下界 `(h−R)·t²` 的同一来源） |

结论口径：1×1 的“厚度尺度”释放**够不到** 77.46 mm 的共享角部走向；能贯穿该走向的只有 `depth ≥ h−R` 一档。两档都写进驱动，供实机对照第三道失败；离线不宣称任何一档会消除失败。

## 实际修改文件

新增：`tests/unit/test_sheetmetal_relief.py`、`tools/test_sheetmetal_relief.py`、本卡；更新：`src/creo_mechdog/schema.py`、`native/advanced.cpp`、`server.py`、`tools/test_sheetmetal_flange.py`、`docs/work-items/FEAT-014.md`（只追加）。未改：`version.py`、`capabilities.py`（工具数量不变，仍 94）、`native/generic.cpp`、`native/sketch_edit.cpp`、根兼容包装、台账、README、其他任务共享契约文件、并发会话文件。提交仅按这些精确路径暂存（`git diff --cached --name-only` 逐次确认）。

## 依赖提交、受测身份与指纹

- 依赖链：`2726ca5`（T00）→ `a3c1f4b`（T02）→ `601b4bc`/`f10bee7`（T03）→ `ffbffaa`（T04）→ `71210e0`（T05）→ … → `9db34c1`（T09B，本卡基线）。
- 实现提交：`3f7d3ddaedd518e7081d3a20fb6876871c67e582`（T11 代码与测试；本卡为其后同任务的文档提交）。
- 受测 commit：`3f7d3dd`；`dirty=true`（工作区仍有另一会话的未提交文档与本机运行数据，未纳入本批）。
- `source_fingerprint`：`22bd8a5fc8ce039fab76c1a0a13c7af7ebc1613b5334ab4a28c27c5d4e03f7cb`（与 T03/T04/T05 同算法：全部已跟踪 `*.py` 与 `native/*.h|*.hpp|*.cpp` 的 CRLF 归一化 SHA256 清单哈希，另加本任务两个新增文件；本次清单 273 个文件）。两个驱动在同一份源码上得到同一指纹。
- `bridge.py build`：成功；`build/build.log` 仅 3 条存量 C4819（`assembly_units.h`、`assembly_walk.h`、`generic.cpp`，代码页 936 警告），无错误；`build/creo_worker.exe` 重新生成（2026-10-29 09:34:52），`build/source.sha256` = `1a2afb3ff7509b2b753fd7f6df6f7ff99432f5fac294476279acb858104d4dea`。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；pydantic 2.13；ruff 0.17.0、clang-format 23.1.3（requirements-dev 锁定）；MSVC x64 与 Creo 12.4.0.0 匹配 Toolkit SDK（仅用于离线编译与读取头文件）。全程未连接 Creo、未启动 MCP/Creo、未提交 Toolkit 作业；服务版本入口仍为 0.7.2。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_sheetmetal_relief -v` | exit 0，Ran 41 tests，OK（PowerShell 直接调用时 unittest 写 stderr 会被包装成 NativeCommandError，属调用伪影，以退出码为准） |
| 2 | `.venv\Scripts\python.exe tools\test_sheetmetal_relief.py` | exit 0；提交后报告 `build/sheetmetal_relief/20261029T095714_6b055574/report.json`，SHA256 `13d5b4beab50a00b96bdd2d73ee9b8f4f1904f7400afea6bbb474697e0412dd0`（另有 `report.sha256`）；`provenance.commit=3f7d3dd`、`dirty=true`、指纹 `22bd8a5f…`；`status=complete / pending_native_acceptance`；内置复跑 41/41 OK；`sdk_contract.installed_header.status=parsed`、`matches_transcription=true` |
| 3 | `.venv\Scripts\python.exe tools\test_sheetmetal_flange.py` | exit 0；提交后报告 `build/sheetmetal_flange/20261029T095714_05bbc9a7/report.json`，SHA256 `0762c1421e06f6e6b144140acdebd9afd3d012b8ae000650eef9102b99ac363e`；`status=not_reproduced_offline / undetermined`；内置 33/33 OK（更新断言后） |
| 4 | 两个驱动 `--live` / `--live --confirm-session-usable` | 均 exit 2：缺开关时提示需要 `--confirm-session-usable`，带开关时打印各自的 LIVE_REFUSAL，指向唯一 dev 服务 `MCP_CREO_MechDog_dev` |
| 5 | `-m unittest tests.unit.test_sheetmetal_flange / test_sheetmetal_contract / test_sheetmetal_overlap / test_arc_direction` | 四个模块均 exit 0，OK（提交后复跑） |
| 6 | `.venv\Scripts\python.exe -m unittest discover -s tests` | 提交后 exit 0，`Ran 1331 tests`，OK（251.2 s）。首次（提交前）运行有 1 个 error：`tests/test_installation_validation.py` 的安装器用例在 90 s 子进程超时处抛 `TimeoutExpired`；同一时刻在 `git archive HEAD` 的未改基线副本上同样复现（`Ran 1 test` 失败、109 s），确认与本批改动无关，属机器负载下的环境性超时；提交后全量通过 |
| 7 | `.venv\Scripts\python.exe tools\dev_check.py` | 提交后 exit 0；`success=true`、`unit_tests=passed`（`build/unit_test_report.json`：1331 run、0 failure、0 error）；style `lint_findings=30`、`unformatted_files=16`（与 T03/T04/T05 基线一致，本批未新增）；`source.commit=3f7d3dd`、`dirty=true`、`checked_source_sha256=62743c09f1242e2a0d2bd35a7d5f7525a98358fc6e88e4006ef7ac50a68bacd3`；报告 `build/development_check.json`。（提交前那次运行 `success=false`，唯一 error 即上条环境性超时） |
| 8 | `.venv\Scripts\python.exe bridge.py build` | 成功（见上节产物与日志） |
| 9 | `ruff format` / `ruff check`（本批 5 个 Python 文件）、`clang-format -i native/advanced.cpp` | `All checks passed!`；clang-format 后 `git diff` 仅含本批新增区域 |

## 未测项与下一步

- 未测（需实机，按共同契约另行指派并在唯一 dev 服务串行执行，先确认会话可操作与 BUG-001 条件）：**四壁真实创建**；relief 元素树是否被 Creo 接受（尤其 RECTANGULAR 下未设置的 `PRO_E_BEND_RELIEF_LENGTH_TYPE/LENGTH/ANGLE`）；实测体积增量与 `width × depth × t` 的关系；缺口面与折弯边的实际距离；`ends=side1/side2` 的单端移除；`depth ≥ h−R` 档能否改变第三道失败；`feature_health`、原生树、`revision`、失败回滚与 `saved_file_reloaded_and_verified`。
- 未测：**展开/折回**（`sheetmetal_unbend`/`flat_pattern`/`bend_back`）在 relief 存在时的行为与平铺态缺口；**尺寸编辑**（`height`）；删除/抑制后重建的 relief 修改路径；relief 记录在 `creo_get_model`/detail 的投影与 32 KiB 预算；材料侧（`flip`）与 relief 的实机正交对照；WorkBuddy 黑盒验收；Creo 9/10。
- 缺材料：原 `acc70_sm2` PRT 与四道 `flip`、边端点仍未随反馈提供，四壁场按 T05 几何重建；T11 不重放原件。
- 下一步：集成人合并本批；实机阶段按驱动 `live_checklist` 用两档 relief 各跑一遍四壁，先确认 relief 元素树被接受，再比较第三道行为、体积增量与角部几何；只有四壁 + 角部几何 + 展开/折回 + 编辑 + 重载 + 回滚全部通过，才可宣称四壁能力完成。若实机显示矩形释放无法消除角部干涉，按 “其他类型清楚列未支持” 的口径回到设计（角部释放/斜接），不擅自在本次实现里加规则。
- 状态口径：本卡可用于“离线实现完成 / 四壁与释放能力待原生验收”；不可写成“已修复”或“四壁已具备”。

## 给 T01 的公共文档变更需求

1. `creo_sheetmetal_flange` 工具描述补充：可选 `relief`（`none` 默认 / `rectangular` + 显式 width>0、depth≥0、ends）；宽深是绝对模型单位、不按板厚缩放；rip/stretch/obround/param 与角部释放/斜接/边撕裂不支持。
2. 能力页注明：四壁角部仍无角部规则能力；relief 为创建期属性，修改需删除/重建；四壁能力未完成，原生验收未做。
3. 勘误：不要把 T11 的矩形释放写成“已解决四壁折边失败”；当前状态是“离线实现完成、实机未验”。

## 给集成人的冲突文件与接口变化

- 共享冲突面：`native/advanced.cpp`（T05/T11/T12 共用，本批只加 `FlangeReliefRequest`/`flange_relief_request`/`flange_relief_side`/`flange_relief_record` 并替换原固定 NONE 循环）、`src/creo_mechdog/schema.py`（T02/T03/T05 共用，新增 `FlangeRelief` 与一个可选字段，未改 `dir`/`validate_operations` 既有分支）、`server.py`（仅 `creo_sheetmetal_flange` 签名与描述）。`native/generic.cpp`、`preview.h`、`capabilities.py` 未改。
- 接口变化（增量）：`sheetmetal_flange` 操作新增可选 `relief{type,ends,width,depth}`；原生别名记录在请求带 relief 时新增 `relief` 块（`type`/`ends`/`sides[]`/`part_thickness_mm`/`corner_overlap_run_mm`/`width_at_least_thickness`/`depth_covers_corner_run`）。缺省调用无任何新增键。
- 行为变化：`relief` 的非法组合从“不存在该字段”变为**建模前明确拒绝**；旧合法调用不变。
- 合并注意：若集成时保留旧的“两处固定 NONE”写法，`tools/test_sheetmetal_relief.py` 与 `tests/unit/test_sheetmetal_relief.py` 的 `NativeTreeTest` 会失败，可据此发现回退；T05 驱动已改为在 `flange_relief_side` 上断言，回退时同样报 `native source guard missing`。

## 2026-10-29 实机验收：两轮都在建第一壁时被阻断，未创建任何折边

环境与前置：手动打开的 Creo 12.4.0.0，§config.json§ 的 §auto_start_creo=false§，唯一 dev 服务指向本仓库，服务 0.8.3，§creo_startup_status§ 为 §ready/connected=true§，§session_health.status=no_failure_observed§。未启动/关闭/重启 Creo，未注入故障，未清 unknown 保护，未重提任何已受理 job。

§§§text
.\.venv\Scripts\python.exe tools\test_sheetmetal_relief.py --live --confirm-session-usable
§§§

报告：§build/sheetmetal_relief/20261029T155905_bb490653/report.json§（SHA256 §20e94f61512c3ecdee233e8b3fb579f260d160762ef53e4c0a5510d16eaf887f§），共 17 次 MCP 调用。

| 轮 | relief 请求 | 底板作业 | job_id | model_id（名称） | 基体终态 | 折边数 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 省略（兼容默认 none） | 草图 + §sheetmetal_wall(depth=1, thickness=232)§ | §796092e2085b49a7903787406c9d8879§ | §c34f02bd6046425caa45dc50f2762a52§（t11_relief_none_de867f） | failed | 0 | 阻断 |
| 2 | §{type:rectangular, ends:both, width:1, depth:1}§ | 同上 | 未提交 | 未创建 | not_executed | 0 | 未执行（同一阻断点，不重复占用通道） |

第 1 轮的原始失败（§creo_get_job§ 原文）：

§§§text
sheetmetal_wall creates the first wall from exactly one open straight line; the section has 2
drawing entities (1 straight lines). Closed contours, arcs, splines and multi-entity chains are
not supported for the first wall
§§§

§toolkit_code=-1§、§failed_stage=execute_sheetmetal_wall§；操作记录为 §[{index:0,wall_sketch,succeeded},{index:1,base_wall,failed}]§。与 [T03 卡](DEV051-T03-ACCEPTANCE.md) 的五个矩阵是同一根因：原生准入把草图构建器必写的 §PRO_2D_COORD_SYS§ 计成第二条曲线。

因此本次**没有创建任何折边**：四壁的真实创建、每道体积增量、§relief§ 回显（§sides[]§/§part_thickness_mm§/§corner_overlap_run_mm§）、§width × depth × t§ 的实测关系、第三道 §f_ny§ 的 §ProFeatureWithoptionsCreate=-1§ 是否复现、失败回滚与 §revision§，全部未取证。也没有用四个普通拉伸块替代折边——驱动只走 §creo_sheetmetal_flange§。矩形释放那个待验风险（§PRO_E_BEND_RELIEF_LENGTH_TYPE/LENGTH/ANGLE§ 未设置时 Creo 是否接受该元素树）同样仍在未验状态。

### 未测项

- 两轮各自四道折边的成功/失败、体积增量、缺口面与折弯边距离、§exists§ 单端（§side1§/§side2§）移除。
- §depth ≥ h−R = 77.46§ 的 corner_run 档能否改变第三道失败（本驱动当前只跑 §1×1§ 档；§PROFILES§ 里的 corner_run 仍需单独一轮）。
- §feature_health§、原生树、§revision§、失败回滚、§saved_file_reloaded_and_verified§。
- 展开/折回（§sheetmetal_unbend§/§flat_pattern§/§bend_back§）、§height§ 尺寸编辑、删除/抑制后重建。
- Creo 9/10；WorkBuddy 黑盒（本次禁用）。

### 下一步

1. 先修 T03 第一壁准入并重编译执行器，再原样重跑本驱动；届时自动覆盖两轮四壁。
2. 第一壁通过后，按需补跑 §corner_run§（宽 1、深 77.46）与 §ends=side1/side2§ 的对照，再判断矩形释放能否消除角部干涉；本轮不对该问题给结论。
