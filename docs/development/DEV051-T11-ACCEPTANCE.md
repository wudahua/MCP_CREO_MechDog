# DEV-051 T11 验收卡：四壁释放完整能力（FEAT-014，离线实现阶段）

日期：2026-10-29 离线 + 多轮实机（Asia/Shanghai）。阶段：**折边已是真实 90° 折弯且方向可控（默认向外、`flip=true` 反向，两例均重载通过）；四壁 2/4 成功，第三道 `f_ny` 创建后回滚；1×1 矩形释放体积差 0.000000、无缺口面，释放能力仍未验收通过**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次实机未启动/关闭/重启 Creo、未注入故障、未清 unknown 保护、未重提已受理 job；未改版本、未合 main、未推标签、未 push、未发布，未实施 T12/T13。本卡不得读作“四壁能力已具备”或“释放能力已实现”。

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

### 本批交付检查（2026-10-29，三份驱动共用一次门禁）

- `.venv\Scripts\python.exe -m ruff format tools/sheetmetal_live.py tools/test_sheetmetal_contract.py tools/test_sheetmetal_overlap.py tools/test_sheetmetal_relief.py` → `4 files already formatted`（无待改）。
- `.venv\Scripts\python.exe -m ruff check`（同上四个文件） → `All checks passed!`。
- `.venv\Scripts\python.exe tools\dev_check.py` → exit 0；`success=true`、`unit_tests=passed`（1343 tests、0 failure、0 error，261 s）；style `lint_findings=30`、`unformatted_files=16`（与 T03 前基线一致，本批无新增）；`source.commit=4598a1b`、`dirty=true`（本机会话数据未提交）；报告 `build/development_check.json`。

## 2026-10-29 第二轮实机：两轮底板建成，第一道折边仍报 `-1`

环境与前置同 [T03 卡](DEV051-T03-ACCEPTANCE.md)：手动打开的 Creo 12.4.0.0、`auto_start_creo=false`、唯一 dev 服务、服务 0.8.3、`ready/connected=true`；先按 T03 修复重建执行器（`build/creo_worker.exe` 2026-10-29 16:10:23），再用同一驱动原样重跑，期望值与两档 relief 均未改。

```text
.\.venv\Scripts\python.exe tools\test_sheetmetal_relief.py --live --confirm-session-usable
```

报告：`build/sheetmetal_relief/20261029T161528_cc1fda94/report.json`（SHA256 `4a3a30c9630fbc96f6c70520888269a7aca7a05aa54817f096e10891070d018b`）；驱动退出码 1，`stopped=null`。

| 轮 | relief 请求 | 底板 job / model_id（名称） | 底板终态 / revision / 体积 | bbox | 折边进度 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 省略（兼容默认 none） | `7f921a1f198c4ac79e99a8272c73707b` / `84a49cc6527b4f6f92f51322cf72647d`（t11_relief_none_74fcbf） | succeeded / 1 / 42 920 mm³ | `[0,-116,0]`–`[185,116,1]` | 1/4 道失败（第 1 道 `f_px`） | 未通过 |
| 2 | `{type:rectangular, ends:both, width:1, depth:1}` | `a41050e44cf44cf2901b2d95d248b042` / `f14dff681cb04edca9e4a6d632477005`（t11_relief_rect_1x1_3ff0ef） | succeeded / 1 / 42 920 mm³ | 同上 | 1/4 道失败（第 1 道 `f_px`） | 未通过 |

第一壁不再是阻断点：两块 185×232×1 底板都建成，`42 920 mm³` 与 T03 契约一致。

### 第一道折边（`f_px`）原始结果

| 项 | 第 1 轮（none） | 第 2 轮（rect 1×1） |
| --- | --- | --- |
| job_id | `ef7341d546b34fa28a145771b543b1a4` | `4c172764b29f4a0d850cfd6a38b73125` |
| 边（`creo_inspect_model` 选边） | id 125，+X 侧，top 面，`[185,-116,1]`→`[185,116,1]`，跨度 232 mm | 同左 |
| 期望增量 | 18 560 mm³（232×80×1） | 18 558 mm³（扣 2×1×1 缺口） |
| 终态 | failed | failed |
| 原码 | `toolkit_code=-1`、`failed_stage=execute_sheetmetal_flange`、`failed_toolkit_call=ProFeatureWithoptionsCreate` | 同左 |
| 消息（原文） | `Toolkit call ProFeatureWithoptionsCreate failed with code -1 during execute_sheetmetal_flange` | 同左 |
| 回滚 | `rollback_succeeded=true`；快照 rev 1→1、体积 42 920→42 920（`rolled_back=true`） | 同左 |
| `relief` 回显 | 无（特征未创建） | 无 |

因此本轮**没有创建任何折边**：四壁真实创建、每道体积增量、`relief` 回显（`sides[]`/`part_thickness_mm`/`corner_overlap_run_mm`）、`width×depth×t` 与缺口距离、第三道 `f_ny` 是否再现 `-1`、展开/折回、`height` 编辑、保存重载全部未取证。也没有用四个普通拉伸块替代折边。

### 与 T05 原件的关键差异（记为需解释的事实，不当结论）

- 0.7.0 R1 S3 原件（job `f45415a90a0544bfad24fe1225c18f50`）里**前两道 ±X 折边成功、第三道 `f_ny` 才 -1**；本轮同一几何（185×232×1 + h80/R2.54/Y0.5）**第一道 `f_px` 就 -1**。
- 说明当前实现的折边元素树在这块底板上比原件更早被拒。T05 的“第三道角部重叠 ≥77.46 mm³”假设**不能**用来解释本轮的第一道失败（此时还没有任何相邻壁、无角部）；角部假设仍悬置，本轮不给结论。
- 也说明 `relief` 两档（none / rect 1×1）当前无法比较——失败发生在创建期，早于任何释放几何生效。

### 下一步

1. 折边定因（建议按 sweep 已有的做法）：先用 `PRO_FEAT_CR_INCOMPLETE_FEAT` 建不完整壁特征，`ProFeatureElemtreeExtract` 取回 Creo 自己补齐的元素树，与本实现写入的树逐项比对（重点：`PRO_E_SMT_FLANGE_TYPE` 与 2D 扫掠截面是否必须成对、`PRO_E_SMT_WALL_HEIGHT` 取 NONE 时是否仍需要高度元素、`PRO_E_SMT_FLANGE_TRAJ_CRV_NORM`/曲线集合的 TAN 指令在“转换型壁”的边是否合法、`PRO_E_SMT_FLANGE_DEPTH=SIDE1/SIDE2 TO_END` 的组合）。
2. 定因后再谈 relief 是否被接受；本轮不对 `PRO_E_BEND_RELIEF_LENGTH_TYPE/LENGTH/ANGLE` 的待验风险下结论。
3. 底板几何已确认（bbox `[0,-116,0]`–`[185,116,1]`），后续 `corner_run`（宽 1、深 77.46）与 `ends=side1/side2` 对照可在此基体上直接跑，不必再等第一壁。

## 2026-10-29 第三轮实机：元素树取证 → 第一道折边 `-1` 根因，以及"能创建但不折弯"

日期：2026-10-29。分支 `codex/dev051-feedback070`。本轮不改版本、不合 main、不推标签、不 push、不发布；未启动/关闭/重启 Creo，未注入故障，未清 unknown 保护，未重提已受理 job。**不得读作"四壁能力已具备"**：两道折边能创建但几何是平铺延伸（无折弯），第三道在 `ProFeatureWithoptionsCreate` 内挂起。

### 3.1 取证手段（原生，失败路径专用）

`native/advanced.cpp` 的折边失败路径新增两块诊断，只在 `create(root)` 抛错后执行，原始 Toolkit 错误原样重抛：

- `flange_tree_evidence()`：把**本实现写入的树**写成 `output/flange_attempt.xml`；再用最小树（`PRO_FEAT_WALL` + `PRO_SMT_WALL_TYPE_FLANGE` + `PRO_FLANGE_WALL_TYPE_2D_SWEPT` + 名称）以 `PRO_FEAT_CR_INCOMPLETE_FEAT` 创建不完全特征，`ProFeatureElemtreeExtract` 取回 Creo 补全的树写成 `output/flange_expected.xml`，随后 `ProFeatureWithoptionsDelete` 删除该探针特征。
- `flange_attachment_evidence()`：记录所选边的 `ProSmtedgeContourGet` 返回码与轮廓边数，并逐个面调用 `ProSmtSurfaceTypeGet`（0 NON_SMT / 1 SIDE / 2 FACE-green / 3 OFFSET-white）。
- 两份 XML 的路径、探针 id、每个原始返回码都 `stage_operation_result` 进失败操作记录，因此 `creo_get_job` 的结果里直接可见；`native.log` 另有 `FLANGE_TREE_*`、`FLANGE_ATTACH_EDGE`、`FLANGE_BODY_SURFACE` 行。

### 3.2 元素差异清单（job `2ca158056a3f4590b23e43cbaab8a4ed`，模型 `49e509e02c5e47eebdb2411ce33cc453`）

| 元素 | 本实现 `flange_attempt.xml` | Creo 补全 `flange_expected.xml` | 判定 |
| --- | --- | --- | --- |
| `PRO_E_FEATURE_TYPE` | `PRO_FEAT_WALL` | `PRO_FEAT_WALL` | 一致（没有 `PRO_FEAT_FLANGE`，折边就是 wall+flange type） |
| `PRO_E_SMT_WALL_TYPE` | 17 | 17 | 一致 |
| `PRO_E_SMT_FLANGE_TYPE` | 1（2D_SWEPT） | 1 | 一致 |
| `PRO_E_STD_CURVE_COLLECTION_APPL` | TAN 指令 102 + 边 125 引用 | 空集合（不完全特征不接受输入） | 无法据此判定 |
| `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM` | 1 | 1 | 一致 |
| `PRO_E_STD_SECTION.PRO_E_STD_SEC_METHOD` | 25（`PRO_SEC_SKETCH`，`ProStdSection.h` 唯一受支持值） | 0（未初始化模板） | 本实现取值符合 SDK |
| `PRO_E_STD_SEC_SETUP_PLANE` | 无 | 有（引用全空） | 用户自定义截面按文档不需要 |
| `PRO_E_SKETCHER` | pointer `**` | pointer `0x0` | — |
| `PRO_E_SMT_FLANGE_DEPTH` side1/side2 `DEPTH_TYPE` | 4 / 4（`PRO_WALL_LEN_TYPE_TO_END`） | 4 / 4 | 一致，与官方样例相同 |
| `PRO_E_SMT_FILLETS_VALUE` | 2.54（请求 R） | 3.71（会话默认） | 本实现按请求 |
| `PRO_E_SMT_WALL_HEIGHT_TYPE` | 0（`PRO_SMT_WALL_HEIGHT_NONE`） | 0 | 一致 |
| `PRO_E_SMT_BEND_RELIEF` 两端类型 | 0（`PRO_BEND_RLF_NONE`） | 5（`PRO_BEND_RLF_PARAM`） | 本实现默认关闭，T11 契约内 |
| `PRO_E_SMT_DEV_LEN_SOURCE` | -6（`PRO_DVL_SRC_FEAT_YF_ONLY`） | -2 | 本实现按 y_factor 契约 |
| 角部释放 / 斜接 / 边撕裂 / `CORNERS_ARR` / `DEV_LEN_BEND_TABLE` / `WALL_DIM_SCHEME` | 无 | 有默认值 | 本实现不支持，已在准入拒绝 |

结论：**请求侧元素与 Creo 自己的默认模板逐项一致**（wall type 17、flange type 1、depth type 4/4、height 0、sharps→bends 1、sec flip 0、thickness flip 0），差异只在 Creo 会补的释放/角部/斜接默认值；Creo 的 `ProErrorlist` 为空。因此 `-1` 不能用"元素缺失或取值错误"解释。

### 3.3 定位到承载对象：所选边不在壁面上

同一棵树（去掉截面）能创建**不完全**折边（`ProFeatureWithoptionsCreate=0`），说明结构本身可接受。承载对象的证据：

```text
FLANGE_ATTACH_EDGE id=125 smt_contour_code=-8 contour=0
FLANGE_BODY_SURFACE id=101 smt_type=2   (FACE, green)
FLANGE_BODY_SURFACE id=111 smt_type=3   (OFFSET, white)
FLANGE_BODY_SURFACE id=122/124/126/127 smt_type=1 (SIDE)
```

`ProSmtedgeContourGet=-8` 是 `PRO_TK_BAD_CONTEXT`，SDK 原文即"该边不在 green/white 面上"。查该基体：green(101) 在 y=-116、white(111) 在 y=+116，相距 **232 mm**；四块 185×232 大面全是 `SIDE`。即验收基体不是 1 mm 板，而是**板厚 232 mm 的钣金件**，只有 185×1 的壁面，所选 `z=1` 边是厚度侧（rim）边。

根因：`tests/unit/test_sheetmetal_flange.py` 的 `wall_base_op()` 传了 `depth=1, thickness=232`。`sheetmetal_wall` 的 `thickness` 写进 `PRO_E_STD_SMT_THICKNESS`（板厚）、`depth` 是拉伸深度，所以体积与 bbox 仍是 185×232×1、42 920 mm³（历次 T03/T04/T11 验收只核这两个数），但钣金语义是 232 mm 厚板；R=2.54 折弯 232 mm 厚板几何上不可能。

### 3.4 修复（两处，均有上节证据）

1. **基体契约**（`tests/unit/test_sheetmetal_flange.py`、`tests/unit/test_sheetmetal_overlap.py`）：草图改 `plane="XZ"`、`sheetmetal_wall(depth=232, thickness=1)`。XZ 让 1 mm 薄宽落在 Z、232 mm 拉伸落在 Y，得到真正的 185×232×1 板（green/white 相距 1 mm，185×232 面是壁面）。
2. **贴边面准入**（`native/advanced.cpp` `generic_sheetmetal_flange`）：建树前用 `ProSmtedgeContourGet` 检查所选边，`PRO_TK_BAD_CONTEXT` 时直接拒绝，消息带原始码与可行做法。实测回显（job `ec93d1b14bf741c2918c39e63b96b26f`、`dd0cc5db45514470b41f7c71a7f0d194`）：

   `sheetmetal_flange cannot attach to edge 125: ProSmtedgeContourGet returned PRO_TK_BAD_CONTEXT (-8), so this edge is not on a sheetmetal wall face (green/white contour). ...`

此外保留 3.1 的取证代码，并修正截面腿方向：中心线是与贴附壁的对齐线、坐标系是贴附点，因此 `angle` 应从对齐线量起；原 `(90 - angle)` 让每个 90° 请求得到与中心线共线的腿（`LINE_wall 0,0 -> 80,0`，零折弯截面）。

### 3.5 修正后的实机结果（job/model/revision/体积/误差/回显）

| 步骤 | job | 模型 | 结果 |
| --- | --- | --- | --- |
| 底板 | `579dc118e3354f838297cea5fd4758c1` | `6512c820cf674516912024ac5855610a` | succeeded，42 920 mm³，rev 1，bbox `[0,-232,-0.5]`–`[185,0,0.5]` |
| `f_px`（边 105，+X 上边，232） | `07b5ec2570c84dd6b5ce295653d2e5f1` | 同上 | succeeded，61 480 mm³（+18 560，误差 0），rev 2，bbox `[0,-232,-0.5]`–`[265,0,0.5]` |
| `f_nx`（边 104，-X 上边，232） | `b57c115d72a14686895c4332874a16e5` | 同上 | succeeded，80 040 mm³（+18 560，误差 0），rev 3，bbox `[-80,-232,-0.5]`–`[265,0,0.5]` |
| `f_ny`（边 103，-Y 上边，185） | `bb5543fb3c66404e95172876fa1ac9aa` | 同上 | **挂起**：job 仍 `running`、`stage=executing_feature_plan`，`native.log` 停在 `ProFeatureWithoptionsCreate` 前的最后一次 `ProArrayAlloc`，>420 s 无输出；驱动抛 `LiveStop` 并停止 |

- 两个成功的折边都 `ProSmtedgeContourGet=0`（`smt_contour=4`）、`saved_file_reloaded_and_verified=true`（`inspection_source=saved_reloaded`），revision 逐次 +1。
- **但几何是平铺延伸，不是折弯**：两次之后 bbox 只在 X 增长 80 mm（`185→265`、`0→-80`），Z 仍是 ±0.5。体积 +18 560 = 232×80×1 对"折弯"和"平铺"同值，体积断言无法区分，因此驱动成功分支已改为记录 `body_bbox_after`/`direction`/`material_side`，并要求 `direction=="up"` 才算通过。
- 第三道挂起是 0.7.0 时代"第三道 `-1`"的新形态（`-1` → 挂起）。按交接规则不重提、不清保护、不动 Creo；`toolkit.lock` 仍被该作业持有，本轮后续实机（含 T04 的 BUG-046 隔离）因此全部无法执行。

报告：`build/sheetmetal_relief/20261029T165319_74073f09/report.json`（SHA256 `D80E018E582C37B8B72D42AB4AF810BD4E53ADB0FDEB8225F27C7F7107829505`；`stopped=LiveStop`、`cases=[]`，因为挂起发生在第一个 profile 的第一道折边之后；作业序列可从 `calls` 还原）。

### 3.6 结论

| 项目 | 结论 |
| --- | --- |
| 第一道折边 `-1` 的根因 | **已定**：验收基体是 232 mm 厚板（`sheetmetal_wall` 的 `thickness`/`depth` 用反），所选边不在壁面上（`ProSmtedgeContourGet=-8`）。已修基体 + 加准入拒绝 |
| 折边能否创建 | 在真正的 1 mm 板上**能**：两道折边 succeeded，体积/重载/revision 全部正确 |
| 折边几何是否正确 | **否 / 未定**：两道都是平铺延伸（bbox 只在 X 增长），没有折弯；根因未定 |
| 四壁能力 | 仍未完成：第三道挂起，第四道未执行 |
| 释放（relief） | 仍未验证：只有第一个 profile 到达折边，第二个 profile 未开始 |

### 3.7 仍未决项与下一步

1. **折边无折弯（P1）**：需在同一个 1 mm 板上确定"截面如何让 Creo 形成折弯"。候选探针（未执行，因会话挂起）：① 只读加载 `<creo>/Common Files/text/smt/flange_shapes/i_wall.sec` 作对照截面，比较其实体构成（是否含弯弧/短水平段）；② `PRO_FLANGE_WALL_TYPE_3D_SWEPT` + 显式方向/起点；③ `PRO_E_SMT_FLANGE_SEC_FLIP=TRUE` 正交对照；④ `PRO_E_SMT_WALL_HEIGHT` 由 NONE 改成 `PRO_SMT_WALL_HEIGHT_AUTO` 对照。每项都必须 bbox 在 Z 增长 80 mm 才判通过，体积相同不算通过。
2. **第三道挂起（P0，新）**：等会话恢复后先确认 `ProFeatureWithoptionsCreate` 是否弹出对话框；拿到根因前不得重试该边。建议登记为独立缺陷（挂起 + 占用通道），与 BUG-001 会话恢复记录一并核对。
3. **未验证**：`relief` 两档（none / rectangular 1×1）在真实折弯几何下的体积与缺口位置、单端释放、展开/折回、`height` 编辑、删除重建、四壁角部。
4. 本轮原生有改动，已 `bridge.py build` 重建执行器；`native/advanced.cpp` 通过 `clang-format --dry-run --Werror`，改动的 Python 文件通过 `ruff format/check`，`tools/dev_check.py` 为 `success=true`。

### 3.8 构建身份

- 实机作业使用的执行器由本轮 16:53 的源码构建；之后只有 `clang-format` 重排与注释整理，语义未变。
- 本轮共 `bridge.py build` 6 次（取证版、腿方向、不完全特征试验、贴边面准入、格式化后、注释整理后）；最终 `build/source.sha256` = `541a9657d24055c80763b47985c5b37a18a094216ef97d44ace8e28f39118f13`，`build/creo_worker.exe` 已按该源码重建。
- 最终 `tools/dev_check.py`：`success=true`、`unit_tests=passed`（详见本卡"`docs/development`"之外的 `build/development_check.json`）。

## 2026-10-29 第四轮：库存截面比对、截面重建与探针待命（实机被会话消失阻塞）

日期：2026-10-29（Asia/Shanghai）。分支 `codex/dev051-feedback070`，本批起点 HEAD `e5fe021`。本轮不合 main、不推标签、不 push、不发布；**未启动、未重启、未关闭 Creo**，未注入故障，未清 unknown 保护，未重提任何已受理 job。**本轮没有新增实机证据**，因此折边是否形成 90° 折弯仍未定，四壁与释放能力仍未完成。

## 2026-10-30：释放有效场景离线阶段（实现与回归完成，实机未验）

日期：2026-10-30（Asia/Shanghai）。分支 `codex/dev051-feedback070`，基线提交 `760aa9b`（T03 板厚同步）。按 [DEV-051 派发表](DEV051-CONTINUATION-TASKS-2026-10-30.md) 的 FEAT-014/T11 离线指派执行：只做离线定位、实现、单元/离线驱动与离线构建。未连接 MCP/Toolkit、未启动或操作 Creo、未改 `version.py`、未合 main、未 push、未发布。工作区其他会话的未提交改动未触碰。

### 定位：自由端负结果与"参数未生效"仍是两个未分开的假设

第六轮（2026-10-29）的 0.000000 体积差全部来自**自由端**折边（`f_px`/`f_nx` 两端都在板件自由角上），该处本来就不应有缺口，因此那一轮既不能证明也不能证伪释放生效。本轮离线核对：

1. **元素树转写正确**（`ProSmtFlangeWall.h` 70–102、209–219 行）：`PRO_E_SMT_BEND_RELIEF → SIDE1/SIDE2 → TYPE/WIDTH/DEPTH_TYPE/DEPTH` 与实现写入一致；取值 `PRO_BEND_RLF_RECTANGULAR=3`、`PRO_BEND_RLF_DEPTH_BLIND=PRO_DIM_ENTER=-4`、`PRO_BEND_RLF_NONE=0` 均对。
2. **关键未观察点**：Creo 会把未写的释放元素填成零件默认——失败探针树 `jobs/27c49456be824804a208b06660a4019b/output/flange_expected.xml` 显示默认是 `TYPE=5 (PARAM)`、宽/深/长度全 0。因此"写入的 TYPE=3/宽/深是否真的留在了创建出的特征里"此前从未被读过；若 Creo 静默重置，请求回显仍会说 rectangular。这只能靠**创建后回读特征树**回答。
3. 未写的 `PRO_E_BEND_RELIEF_LENGTH_TYPE/LENGTH/ANGLE` 的生效默认值仍是开放问题（对 RECTANGULAR 大概率 NOT_USED，但离线无法证实）。

### 实现（`native/advanced.cpp`，最小改动，几何行为不变）

创建+再生成功后（仅当请求了释放时）：`ProFeatureElemtreeExtract` 取回已建特征树 → 按路径读回两侧的 `TYPE/WIDTH/DEPTH_TYPE/DEPTH/LENGTH_TYPE/LENGTH/ANGLE` → 与请求逐项核对（启用侧 TYPE=3、BLIND、宽深 ≤1e-6；未启用侧 TYPE=0），**不一致即失败**（消息 `flange relief did not persist into the created feature: sideN recorded type=... requested ...`），失败走既有回滚路径 → 一致则记录 `relief_element_echo{side1,side2}` 进特征别名并写原生日志 `SHEETMETAL_FLANGE_RELIEF_ELEMS`。LENGTH_TYPE/LENGTH/ANGLE 只记录不断言——它们的生效默认值正是要靠实机读回答的问题。这是对"参数进了有效原生节点"的直接验证（真实回读并核对，不是把回显改成请求值）。

### 有效材料场景（可离线推导的独立 oracle）

第六轮体积模型被本轮精确复算并锚定：折边增量 = 直段（h−t−R）+ 净弯区（四分之一环 − t×(R+t) 板角矩形），232 mm 跨距算得 **18 025.291233 mm³**，与实测 18 025.291234 吻合到 1e-6——模型可信。

场景：底板 185×232×1 → `f_px`（+x，两端自由角，负对照）→ `f_ny`（−y，第二道；其 +x 链端撞上 `f_px` 折弯 = **1 个材料端**，−x 链端仍自由）。该场景不依赖已失败的第三壁四壁配置（`f_ny` 作为第二道壁尚未实测过，正是本轮要回答的）。每例新建模型，先建 base+f_px 计划，再单独提交 f_ny（重新取边）。

| 用例 | 期望体积差（对同几何 none 基线） |
| --- | --- |
| `f_ny` none | 基线（预测增量 181.46 mm 跨距 ≈ 14 098.6 mm³，含 −3.54 链端缩短） |
| `f_ny` rect both 1×1 | **−1 mm³**（1 个材料端 × 1×1×1） |
| `f_ny` rect both 4×4 | **−16 mm³** |
| `f_ny` rect side1 / side2 1×1 | 恰好一侧 −1、另一侧 0；由此确定 side1/side2 与材料端的映射 |
| `f_px` rect both 4×4（自由端对照） | **0**；不作为释放证据 |

判据（`relief_geometry_verdict`）：`relief_element_echo` 缺失或与请求不符 → 不通过；零件级板厚实测 ≠1.0 → 不通过（T03 规则）；材料端体积差 ≠ 期望（**含差为 0 的第六轮形状**）→ 不通过；体积差对但无缺口面 → 不通过；自由端对照差 0 → 记为对照通过、不计释放证据。单端对由 `single_end_pair_verdict` 判"恰好一端去料"。

### 回归

- `tests/unit/test_sheetmetal_relief.py`：68 项（旧 45 + 新 23）。新增：增量模型锚定第六轮实测（±1e-3）；材料场景计划与各变体校验；期望差表（0/−1/−16/单端 None）；verdict 全形状矩阵（第六轮形状被拒、回显缺失/偏离/重置 PARAM/板厚 3.71 均拒、一致则过）；单端对判定；原生回读的静态守卫（提取在 regenerate 之后、发散即抛、echo/log 入暂存、写路径仍不写 LENGTH/ANGLE）。
- `tools/test_sheetmetal_relief.py`：离线报告新增 `material_scenario`（计划校验+oracle 表）与 `relief_verdict_matrix`（第六轮形状 = 拒绝形状）；`native_source` 守卫新增 4 项回读检查；`run_profile`/`four_wall_plan`/`relief_comparison` 的绝对与差分 oracle 换成材料端感知模型（`f_px`/`f_nx` 期望 0 差、`f_ny`/`f_py` 期望 −2×w×d×t）；live 新增 `run_material_scenario`（6 模型：基线、1×1、4×4、side1、side2、自由端对照），每例记录 `relief_element_echo`、`wall_contract.part_thickness_mm`、缺口面、差值与判定；`live_checklist` 同步。

### 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_sheetmetal_relief` | 68 tests，OK |
| 2 | `-m unittest tests.unit.test_sheetmetal_contract tests.unit.test_sheetmetal_flange tests.unit.test_sheetmetal_overlap tests.unit.test_sheetmetal_relief` | 146 tests，OK（共享模块无回归） |
| 3 | `.venv\Scripts\python.exe tools\test_sheetmetal_relief.py` | exit 0；报告 `build/sheetmetal_relief/20261030T075103_5e2a84f2/report.json`（SHA256 `fd996b41cb8fe4f0454ab0996944611b5bf0870034dc6d26a63567744595e468`）；内置复跑 68/68 OK |
| 4 | `.venv\Scripts\python.exe tools\dev_check.py` | 见 `build/development_check.json`；结论记录于交接说明 |
| 5 | `.venv\Scripts\python.exe bridge.py build` | 成功×3（前两次暴露 API 误用并修复，最终一次以最终源码重建）；`build/build.log` 仅 3 条存量 C4819（`assembly_units.h`、`assembly_walk.h`、`generic.cpp`），无错误；`build/source.sha256 = 2bebcca1faafc1b3ed92e1272ce16a6c082356554f254fabd702435f16251b69` |
| 6 | `clang-format --dry-run --Werror native/advanced.cpp`；`ruff format` + `ruff check`（两个 Python 文件） | 全部通过 |

编译中修复的两处 API 误用（离线构建暴露）：`ProElementIntegerGet/ProElementDoubleGet` 需 `options=NULL` 三参形式；`ProFeatureElemtreeFree` 第二参是 `ProElement` 非指针。

### 实际修改文件

`native/advanced.cpp`；`tools/test_sheetmetal_relief.py`；`tests/unit/test_sheetmetal_relief.py`；本卡；`docs/work-items/FEAT-014.md`。未改 schema（`FlangeRelief` 契约不变、默认 none 保持）、`server.py`、`version.py`、`native/generic.cpp`、`docs/validation/` 原件、`docs/BACKLOG.md`。

### 未验证（实机阶段待验，离线通过不等于整项验收通过）

1. `f_ny` 作为**第二道**壁（仅 `f_px` 存在）能否建成：这是有效材料场景的成立前提；若与第三道同样回滚，按驱动记录交接并换垂直壁端夹具，不得猜因。
2. `relief_element_echo` 是否与请求一致（即写入值是否留在创建特征中；若原生产生 "did not persist" 失败，记录原始读回值再定位，不得改回显绕过）。
3. 材料端缺口：位置（`f_ny` +x 端、`f_px` 折弯相接处）、尺寸（1×1 / 4×4）、缺口面、体积差 −1 / −16 mm³（±0.2）；`side1`/`side2` 与材料端的映射；`LENGTH_TYPE/LENGTH/ANGLE` 读回值（回答默认值问题）。
4. `wall_contract.part_thickness_mm=1.0`（T03 依赖）在所有场景成立；保存重载 true 且重载后差值保持。
5. 自由端对照（`f_px` rect 4×4）体积差 0；四壁 profile 复测按新 oracle 的 0/−2 期望重取差分。
6. 展开状态下的缺口形状、`height` 编辑、删除重建改释放、回滚——均未执行。

### 给实机窗口的交接

- 依赖：本批实现提交（见 git log，FEAT-014/T11 主题）+ `760aa9b`（T03 板厚同步）；受测执行器 `build/source.sha256 = 2bebcca1…`。
- 入口：`.\.venv\Scripts\python.exe tools\test_sheetmetal_relief.py --live --confirm-session-usable`（唯一 dev 服务 `MCP_CREO_MechDog_dev`，先满足 BUG-001 会话条件；180 s 挂起预算，首 unknown 即停）。
- 判读纪律：材料端差 0 = 释放未生效（失败），自由端差 0 = 预期行为（对照）；两者不得混用。任何"请求被接受且回显齐全"都不再构成释放证据。

### 4.1 阻塞现场（必须先读）

交接前提是"Creo 已重新启动、新会话可用"，实际探测到的是会话再次消失：

| 时间 | 证据 | 取值 |
| --- | --- | --- |
| 2026-10-29 19:51:03 | Windows 事件日志 Application / Windows Error Reporting 1001 | `AppHangB1`，`P1: xtop.exe`、`P2: 40.0.2025.111` |
| 2026-10-29 19:51:03 | Windows 事件日志 Application / Application Hang 1002 | "程序 xtop.exe 版本 40.0.2025.111 停止与 Windows 交互并已关闭" |
| 2026-10-29 19:53 / 20:06 | `tasklist /FI "IMAGENAME eq parametric.exe"`、`eq xtop.exe` | 两次均为"没有运行的任务匹配指定标准"；只剩 `nmsd`（pid 6504） |
| 2026-10-29 20:04 | `creo_startup_status`（只读快照，未提交作业） | `state=timeout`、`connected=false`、`auto_start_enabled=false`、`launch_attempt=48`、`launch_reserved=false` |
| 2026-10-29 20:04 | `creo_session_status`（9 秒只读探测） | `connected=false`、`connection_state=not_found_or_unreadable`、`toolkit_code=-4`、`worker_exit_code=20`、`creo_process_snapshot.processes=[]`（`uncertain=false`） |

即 MCP 侧枚举不到任何 Creo 进程，不是"IPC 端点坏了但有进程"的情况。上一轮挂起的第三道折边作业 `bb5543fb3c66404e95172876fa1ac9aa` 随该会话一起消失，已无法再读到终态或对话框证据；`jobs/bb5543fb3c66404e95172876fa1ac9aa/native.log` 保留在 `ProFeatureWithoptionsCreate` 之前的位置，作为最后一次现场。

处置：按交接规则"必须人工才能过"的条款，本轮**不启动 Creo**（服务侧 `auto_start_creo=false`、`automatic_launch_allowed=false`），不重提、不清锁、不动进程；依赖实机的步骤（A 探针、T05 四壁、T11 两档 relief、T04 隔离）全部暂停，转为离线部分。

### 4.2 离线：库存折边截面到底包含什么

读取本机 `C:\Program Files\PTC\Creo 12.4.0.0\Common Files\text\smt\flange_shapes\` 全部 9 个 `.sec`（`#UGC:2 SECTION` 段文件，实体表为二进制），按实体类型计数并取出尺寸文本（尺寸值以 ASCII 出现在 `text_value` 槽中）：

| 文件 | line | arc | coord_sys | point | dimen | 尺寸文本 | 读作 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `i_wall.sec` | 1 | 0 | 1 | 0 | 1 | `5.00`、`90.00` | 一条 90° 直腿（直壁） |
| `flushed_hem.sec` | 1 | 0 | 1 | 0 | 1 | `1.00` | 一条直腿（压平包边） |
| `c_hem.sec` | 1 | 1 | 1 | 0 | 1 | `0.50` | 直腿 + 1 段弯弧 |
| `open_hem.sec` | 1 | 1 | 1 | 1 | 1 | `0.50` | 直腿 + 弯弧 + 点 |
| `s_wall.sec` | 1 | 1 | 1 | 1 | 1 | `1.27` | 直腿 + 弯弧（S 形） |
| `arc_wall.sec` | 1 | 1 | 1 | 1 | 1 | `5.00` | 直腿 + 弯弧（圆弧壁） |
| `joggle_hem.sec` | 1 | 1 | 1 | 0 | 1 | `2.24` | 直腿 + 弯弧（错位） |
| `z_hem.sec` | 1 | 1 | 1 | 0 | 1 | `0.50` | 直腿 + 弯弧（Z 形） |
| `duck_hem.sec` | 1 | 1 | 1 | 0 | 1 | — | 直腿 + 弯弧（鸭嘴） |

可离线确定的结构事实：

- **每个库存截面都只有 1 条 line、1 个 `coord_sys`、1 个尺寸，且都没有 centerline**。此前实现写入的 `centerline(-10,0 → 10,0) + 腿线` 不是 Creo 库存截面的形状。
- **弯弧只出现在 hem 类**（C/open/S/Z/joggle/duck/arc），`i_wall` 与 `flushed_hem` 不含 arc：折弯弧由特征按半径生成，不需要画进截面，**截面只描述直腿**。
- `i_wall` 的尺寸是 `5.00`（腿长）与 `90.00`（角度），即**一条 90° 的直腿就是"平铺延伸/直壁"**的形状，而不是"折 90°"的形状——正好对应上一轮实测到的"能建出但是平的"。

### 4.3 离线：方向推断（把上一轮的现象接上）

上一轮 `native.log` 记录 `LINE_wall=0.000000000,0.000000000 -> 0.000000000,80.000000000`（腿在草图 +y、长 80），而实机 bbox 只在 +X 增长 80 mm、Z 仍 0..1。两者合起来只有一个解释：

- 折边截面的**草图 +y ⇒ 父壁平面内方向**（+X 外伸）；
- **草图 +x ⇒ 父壁法向**（板厚/竖直方向）。

所以 90° 请求必须把腿放在草图 +x；上一轮放在 +y 等于"沿父壁平铺 80 mm"，与 `i_wall`（90° 直腿 = 直壁）自洽。上一轮把 `(90-angle)` 判为"零折弯腿"并据 `-1` 反推不成立——那一轮 `-1` 的根因已由第三轮定为厚基体/边不在壁面，与腿方向无关。

### 4.4 代码改动（唯一原生改动，已重建执行器）

`native/advanced.cpp` 的 `generic_sheetmetal_flange`：

- 截面改为**单条线** `(0,0) → (h·sinA, h·cosA)` + 一个 `height` 长度尺寸（`PRO_TK_DIM_LINE`），**去掉 centerline**；坐标系仍在贴附点；角度按"从父壁平面量起"取值，90° ⇒ 腿落在草图 +x，0° ⇒ 沿父壁（等价旧行为）。
- 元素树其余部分一律不动（`PRO_E_SMT_FLANGE_SEC_FLIP=PRO_B_FALSE`、`PRO_E_SMT_WALL_HEIGHT=NONE`、两侧 `TO_END`、`FILLETS=R2.54 内侧`、`THICKNESS_FLIP=FALSE`、`y_factor=0.5`、relief 分支原样），本轮只改"截面构成 + 腿方向"一个变量。
- `bridge.py build` 已重建 `build/creo_worker.exe`（2026-10-29 19:58:15）；`clang-format --dry-run --Werror native/advanced.cpp` 通过。

### 4.5 新增探针驱动 `tools/test_flange_direction.py`

- 一个模型只建一条折边：底板 `185×232×1`（`plane="XZ"`、`sheetmetal_wall(depth=232, thickness=1)`）+ `f_px`（+X 上边，由 `creo_inspect_model` 现选，不硬编码 id）。两例各用新模型名：`angle90`（不翻）、`angle90_flip`（`flip=true`，即 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM` 取 FLIP）。
- **判定只看 bbox**：`z_growth ≥ 0.9 × height`（72 mm）且 `direction=="up"` 才算通过；包络按上下两向取大值，因此"往下折"记为"是折弯但不通过"（材料侧缺陷，BUG-047），体积相同明确不算通过。
- **挂起规则**：`wait_job(budget=180)`；超时或状态未知即 `LiveStop`，把 job/阶段/`native_log_tail` 写进报告并停止后续提交；不重提、不杀 Creo、不重启、不清锁。
- **离线守卫**：`native_section()` 直接读 `native/advanced.cpp` 的折边函数体，断言"腿在法向""无 centerline""单线""`WALL_HEIGHT_NONE`"；单测 `tests/unit/test_flange_direction.py`（6 项：结构守卫、上/下/平铺三种 bbox 判定、计划与 180 s 预算）。
- 离线运行：`build/flange_direction/offline_20261029.json`（SHA256 `79FA450740BF10B68567B24A0E9AFB4BEAEDCFD4B0CDF95BA9CEE8BAABCD1A36`），`mode=offline`、`not_executed` 明确写"无 MCP 客户端、无 Creo 连接"。

### 4.6 本轮结论

| 项目 | 结论 |
| --- | --- |
| A 折边形成 90° 折弯 | **未定**：截面已按库存形状重建并编译，但**没有实机结果**，不得读作已修复 |
| 截面构成（离线） | **已定**：库存 9 个截面均为"1 line + coord_sys + 尺寸、无 centerline"，弯弧由特征生成；`i_wall` 的 90° 直腿就是直壁 |
| 方向约定（离线） | **已定**（依据上一轮 `LINE_wall 0,0→0,80` 与 bbox 只增 X）：草图 +x = 父壁法向，+y = 壁面内 |
| 四壁（T05） | 未执行；无会话 |
| 释放（T11 两档） | 未执行；无会话 |
| 第三道挂起 | 会话已消失，无新增证据；该 job 不会再读到终态 |

### 4.7 下一步（会话恢复后按顺序）

1. 人工重开 Creo → `creo_startup_status` 到 `ready`、`creo_session_status` `connected=true`。
2. `.venv\Scripts\python.exe tools\test_flange_direction.py --live --confirm-session-usable`：先看 `angle90` 是否 `z_growth≈80` 且 `direction=="up"`。
   - 若向下折（`direction=="down"`）：下一变量是 `PRO_E_SMT_FLANGE_SEC_FLIP=TRUE`（需按新事实给该元素开口子），不是改角度。
   - 若仍是平铺（`direction=="in_plane"`）：按 §3.7 的顺序试 `WALL_HEIGHT` NONE→AUTO、`PRO_FLANGE_WALL_TYPE_3D_SWEPT`。
3. 折边成立后再跑四壁（`tools/test_sheetmetal_relief.py --live`，first profile 四道）与 T11 两档 `relief`（省略 / rectangular both 1×1），记录体积增量与缺口位置。
4. T04 隔离（`sheetmetal_add_offgroup` → `sheetmetal_add_new_body`）同一通道串行，一次只跑一条路线。

### 4.8 本批交付检查

- `clang-format --dry-run --Werror native/advanced.cpp` → 通过。
- `ruff format` → `2 files left unchanged`；`ruff check` → `All checks passed!`。
- `bridge.py build` → `build/creo_worker.exe`；`tests.unit.test_flange_direction` 6 项通过。
- `tools/dev_check.py` → `success=true`、`unit_tests=passed`（超时上限 900 s）、`style_summary` 为 `lint_findings=30`、`unformatted_files=16`（与本批前基线一致，本批无新增）、`cpp_files_checked=33`、`python_files_checked=249`；`source.commit=e5fe021`、`dirty=true`（本机会话数据未提交）；报告 `build/development_check.json`（SHA256 `CD69C6909234F711B12BEE5FC210E664C52E6001C5BBBE4036ABA0332CF94F85`）。

## 2026-10-29 第六轮实机：折弯成立、方向可控；四壁止于第三道；1×1 释放无可观测几何

日期：2026-10-29（Asia/Shanghai）。分支 `codex/dev051-feedback070`，HEAD `cce1922`。手动打开的 Creo 12.4.0.0（PID 15156，22:05:41 由协调器拉起），`creo_startup_status` → `ready/connected=true`（`native.toolkit_code=0`、`release_numeric=44`），`creo_session_status.session_health=no_failure_observed`。`config.json` 的 `auto_start_creo` 在确认 ready 后已改回 `false`。未启动/关闭/重启 Creo、未注入故障、未清保护、未重提已受理 job。

### 6.1 方向（A）：`flip` 落到 `PRO_E_SMT_FLANGE_SEC_FLIP`

`flip` 原先写 `PRO_E_SMT_FLANGE_TRAJ_CRV_NORM`，22:06 那轮 `false`→1 与 `true`→−1 的 bbox/体积/方向完全相同。本轮先用一组单变量探针确认真正的开关（`build/flange_side_probe/`）：

| 依附边 | `SEC_FLIP=FALSE` | `SEC_FLIP=TRUE` |
| --- | --- | --- |
| +X 顶边（z=+0.5） | down，z `[-79.5,0.5]` | up，z `[-0.5,79.5]` |
| +X 底边（z=−0.5） | up，z `[-0.5,79.5]` | down，z `[-79.5,0.5]` |

侧向相对依附面：`TRUE` = 从选中面法向向外。定口径：默认（`flip=false`）= 向外，`flip=true` = 反向；轨迹法向固定 `NO_FLIP`（与库存 `UgSmtFlgWallCreate.c` 一致）。收口实机 `tools/test_flange_direction.py --live --confirm-session-usable` → `passed=true`，见 [T05 卡](DEV051-T05-ACCEPTANCE.md) 第六轮。

### 6.2 四壁与两档释放（B/C）：`build/sheetmetal_relief/20261029T222754_44e6ab6a/report.json`

SHA256 `d2de17487469f10fba9859a0459cfeb64e593537105c8d5a6df5be9bf829d58f`，驱动退出码 1（两轮都未满四道），`stopped=null`、无挂起。

| 轮 | 模型 | 底板 | `f_px` | `f_nx` | `f_ny` |
| --- | --- | --- | --- | --- | --- |
| relief 省略 | `fc04dfaf7e9a4d6eb17b900d5276da33` | 42 920 / rev 1 | `c09759e7d25341d3a98874291273be15`，+18 025.291234，rev 2，up，重载 true | `fc097f17478a4d48a8a64deb2a6effef`，+18 025.291234，rev 3，up，重载 true | `1a2b487ce90b486fb358494ba6afcc22`，failed，rev 3→3，回滚 |
| rect both 1×1 | `88dcd28eefb4459caf1480cb1803cfb9` | 42 920 / rev 1 | `e45404d4c09d441791626bb5eb369525`，+18 025.291234，rev 2，up，重载 true | `c030c0cd245249a28dc964f8dd90c2c5`，+18 025.291234，rev 3，up，重载 true | `2bc5bf3184d94d08b472a0cd179c242e`，failed，rev 3→3，回滚 |

- 四壁 bbox 两道后为 `[0,-232,-0.5]`–`[185,0,79.5]`，两壁都向上（默认向外）。
- 第三道 `f_ny` 的边跨度 177.92 mm（两端各被已有折弯占去 3.54 mm）；`toolkit_code=-1`、`message="Regeneration produced a failed, suppressed or incomplete feature"`、`rollback_succeeded=true`、`effect_status=rolled_back`。原生日志显示 `F_NY` 创建成功但 `status=6`、`geometry_items=[]`，健康检查随后判定整件失败并回滚。按规则未重提该边、未续跑第四道。

### 6.3 释放的差分口径与结果（C）

差分 oracle：同边、同 h/R/Y，只有 `relief` 不同，体积差应等于两端缺口 `2 × width × depth × thickness` = **−2 mm³**。

| 侧 | 无释放 +mm³ | 1×1 释放 +mm³ | 实测差 | 缺口面（全部曲面中三向包围盒 ≤1.5 mm） |
| --- | --- | --- | --- | --- |
| `f_px` | 18 025.291234 | 18 025.291234 | 0.000000 | 0 |
| `f_nx` | 18 025.291234 | 18 025.291234 | 0.000000 | 0 |

- 回显完整（`type=rectangular`、`ends=both`、`sides[]` 宽/深/深度类型、`part_thickness_mm=3.71`、`corner_overlap_run_mm=77.46`、`width_at_least_thickness`、`depth_covers_corner_run`），但**几何没有任何变化**。
- 诊断性第 5 个 job（`6ddadf6487644504a1ebdfd6ef8bd7f4`，`build/relief_probe/w4_d4/20261029T223039_44c271f2/report.json`）把宽深提到 4×4（大于回显板厚 3.71）后体积差仍为 0.000000，排除"1×1 太小被忽略"。
- 判读：这两道折边的弯端在板件自由角上，Creo 不在自由端切释放缺口；需要释放的第三、四道在 `f_ny` 就回滚（有/无释放失败方式相同）。因此释放只能记为"请求被接受并回显"，**不能记为几何生效**。
- 顺带发现（已记 BUG-032）：`ProSmtPartThicknessValueGet` 在 1 mm 薄板上返回 **3.71 mm**（零件级默认板厚未随壁厚同步），回显里的两项板厚比较在修正前不可信。

### 6.4 本轮结论

| 项目 | 结论 |
| --- | --- |
| 折边是否 90° 折弯 | **是**：两道折边 bbox Z 增长 79 mm，体积增量 18 025.29 mm³，重载 true |
| 方向是否可控 | **是**：默认向外（+Z）、`flip=true` 反向（−Z），均 rev 2、重载 true |
| 四壁能力 | **未完成**：2/4 成功，第三道 `f_ny` 创建后回滚（原码与 job 保留） |
| 释放（1×1 both） | **无可观测几何**：体积差 0.000000、缺口面 0；自由端不切缺口，角部场景仍失败 |
| 挂起 | 无：两个 profile 的全部 job 都在 180 s 内到达终态 |

### 6.5 下一步

1. `f_ny` 两端各内缩 20 mm 的短边探针（新模型、新边），区分"角部干涉"与"其它原因"；不重提已回滚的边。
2. 若确认角部干涉，评估 `PRO_E_SMT_CORNER_RELIEF`/斜接（当前明确未支持）或 `depth ≥ h−R = 77.46` 的释放档，仍按"一次一个变量、失败即停"执行。
3. 释放是否真的不生效：在一个"弯端靠材料"的合法场景（第 2 道垂直于第 1 道的壁端）复测 4×4 与 1×1；并在修正零件级板厚参数后复测 `width_at_least_thickness` 口径。
4. 修正 BUG-032 的板厚参数同步后，重跑本卡两档，确认 `part_thickness_mm` 变为 1.0。

## 2026-10-30 实机阶段（Creo 12.4.0.0，唯一 dev 服务）

命令：`tools\test_sheetmetal_relief.py --live --confirm-session-usable` → 报告 `build/sheetmetal_relief/20261030T122856_2b3de3e1/report.json`（SHA256 `04f01b360740c996c1ec3a048dd6459dae50dcc09311d93870692ac9fbc08402`），整体 `passed=false`。

### 已经拿到的实机事实

1 mm 底板（185×232，零件厚度实机读数 1.0）：

| 折边 | 边 span | 状态 | 增量实测 / oracle (mm³) | 重载 |
| --- | --- | --- | --- | --- |
| f_px（+x 自由端） | 232.0 | succeeded | 18025.291234 / 18025.291233（误差 6.9e-7） | true |
| f_nx（−x 自由端） | 232.0 | succeeded | 18025.291234 / 18025.291233（误差 6.9e-7） | true |
| f_ny（−y，两端被前两道折边吃掉 7.08 mm） | 177.92 | **failed** | — | 回滚成功、模型与 revision 不变 |

即：**折边几何本身是对的**（两道自由端折边的增量与独立 oracle 差 7e-7，且保存重载通过）；失败的是**接在已被折弯吃掉端部的边上**再建折边。

### 材料场景为什么没能成立

材料场景需要一个“弯边靠材料”的第三道折边；第三道折边在本轮实机上 `Regeneration produced a failed, suppressed or incomplete feature`（`failed_stage=execute_sheetmetal_flange`，`rollback_succeeded=true`）。因此 none / 1×1 / 4×4 的释放对比**没有跑起来**，`material_scenario_passed=false`，不能据此判断释放是否生效。

根因已由 T05 的对照探针定位到“边端相邻折弯”这一类，见 `DEV051-T05-ACCEPTANCE.md` 同日节。T11 与 T05 须一起解，不能只改释放参数。

## 2026-10-31：N01 relief 定性与驱动修复（离线，未实机；追加不改写上节）

对七段实机 run（`20261030T234952`，`build/post090_live_20261030T234952/n01/relief.json`）
的 relief 证据做回归定性，结论与修复全文见 [BUG-090 卡](../work-items/BUG-090.md)
同日节，本节只记 T11 侧要点：

- **第三折边 f_ny 再次命中 T05 已证边界**（span 177.92、shortfall 7.08=2×(R+t)、
  `shared_corners=2`，再签名 `-1`），且 relief_none / relief_rect_1x1 两案一致：
  **已知边界命中，非 N01 回归，也不是 T11 释放实现的失败**——释放几何在被挡的
  f_ny/f_py 上无法观测，显式记 `relief_geometry_unverified`，不冒充已验。
- **材料矩阵的 mat_baseline 底件失败是驱动夹具缺陷**：一次性 plan 把离线合成夹具的
  边 ID 253 烘进实机请求，Creo 以 `PRO_TK_NOT_EXIST(-23)` 拒绝附着。已修——底件
  只建墙，f_px/f_ny 各自成 job 并从新快照重选边（顺带修掉折边后 bbox 误用作
  plate bounds 的隐患）。因此上节“材料场景没有跑起来”的旧因已除；**释放对比能否
  真正跑起来仍取决于 f_ny 在 T05 边界下能否建成（带释放是否豁免未证）**，只能实机
  观察，不预设。
- 驱动判定新增 `classify_flange_failure`（双侧正证据才归 `known_t05_boundary`，
  任一缺失保持 `failed`，回归不藏进边界标签）；案卷按 N05 `trigger_reproduced`
  同约定：边界命中是有效诊断、`passed=true`，`relief_geometry_verified` 另记。
  单元锁定 9 例；命令与退出码见 BUG-090 卡。实机重跑命令同卡（预期判定在卡内）。

## 2026-10-31：N01 relief 第二轮实机复测（编排方串行）

原始报告 `build/post090_live2_20261031T115830/n01relief/run1/report.json`，SHA256 `cefce8ed54488b0d860c7b587cd9dd35f48151b79d36098accc75fba5b5d643a`，`run_id=20261031T133009_e33744d9`，`mode=live`，`passed=true`，`stopped=null`，`material_scenario_passed=true`。

### 逐例判定

- **`relief_none`**（model `f5c640ff5bee4ebcae312f08a8443372`、底件 job `5ad732b693014902b5daa914a14d3479`、rev 1、42920.0 mm³）：`f_px`（job `87168b4503ad45459f9f36544fa408c5`）与 `f_nx`（job `a98d6447fab94e6fbf113df9ce7e3606`）自由端折边 succeeded，各 +18025.291234 mm³（误差 6.9e-7）、rev 1→2→3、重载 true；`f_ny` 失败并归 `known_t05_boundary`。案卷 `known_t05_boundary=["f_ny"]`、`relief_geometry_unverified=["f_ny","f_py"]`、`verdict="known_t05_boundary"`、`passed=true`。
- **`relief_rect_1x1`**（model `ceb6abdd9a414fca98200cf08a1af5de`、底件 job `c2fc07c8972144698d66ebbdbb463279`）：同上两自由端墙成功（`f_px` job `07f1634e4a0145a480fcf6272f8e213e`、`f_nx` job `7c9be326190f4fc49d5320b96f7a0f4f`），`relief_echo` 齐全（type=rectangular、ends=both、side1/side2 宽深 1.0 mm、blind、`part_thickness_mm=1.0`、`width_at_least_thickness=true`、`corner_overlap_run_mm=77.46`、`depth_covers_corner_run=false`）；`f_ny` 失败归 `known_t05_boundary`，`relief_removed_mm3=2.0`（该值取自已失败的请求回显，非实测去料）。
- **材料矩阵五案**：`mat_baseline`（`e248ffbafce84b89b4dd657960f0773b`）、`mat_rect_both_1x1`（`faca4b5e448744e39be2cafe9d5a17b3`）、`mat_rect_both_4x4`（`21fac055a70a4c87b15bcb9ef3fd1f6f`）、`mat_rect_side1_1x1`（`ae346760ce474692aaf4104941fac785`）、`mat_rect_side2_1x1`（`ac5ab90163744589aea7c6da8dbdaef9`）。五案底件均 succeeded、rev 1、42920.0 mm³，`wall_contract.part_thickness_mm=1.0`（`part_thickness_synced=true`），`f_px` 自由端建成（各 +18025.291234051932 mm³、重载 true），目标 `f_ny` 失败并归 `known_t05_boundary`，`verdict` 为 `{"status":"known_t05_boundary","passed":true,"evidence_class":"none","relief_geometry_verified":false}`，`reasons` 指明"目标折边被已证的 T05 边界挡住；此场景下释放几何不可观测"。矩阵的 `expected_delta_mm3`（0 / −1 / −16 / −1 / −1）全部未取得实测差（`measured_delta_vs_baseline_mm3=null`）。
- **`free_rect_both_4x4`**（model `b6845c6048cf49ce9aeb7e27554d294e`、底件 job `4ae4f30dc1154e808be8aec94e9d5099`）：目标为自由端 `f_px`（job `71ef2f4526324dbfbcb86bf31f3e2361`）——**真实建成通过**，rev 1→2、+18025.291234051932 mm³、`saved_file_reloaded_and_verified=true`，`relief_echo` 与 `relief_element_echo` 齐全（side1/side2 宽深各 4.0 mm、blind、`length_type=-31`、`type=3`），`verdict.scenario="free"`、`passed=true`、`reasons=[]`。

### T11 侧要点

- **自由端 vs 材料端必须分开读**：自由端（`f_px`/`f_nx`）差分 0.000000 mm³、缺口面 0 个是**口径内的预期行为**（`profile_comparison` 中 `f_px`/`f_nx` 的 `notch_faces_without_relief=0`、`notch_faces_with_relief=0`、`measured_delta_mm3=0.0`、`expected_delta_mm3=-0.0`，`all_within_tolerance=true`）；材料端（本轮全部被 T05 边界挡住）**没有可观测的释放几何**。
- 因此本轮**不构成"释放几何生效"的证据**。可确认的是：自由端释放请求被真实接受并建成、释放元素树回显与请求逐项一致（`relief_element_echo`）；不可确认的是材料端缺口是否被真实切出——`relief_geometry_verified=false`、`relief_geometry_unverified=["f_ny","f_py"]` 已如实记录。
- 上一节"材料场景没有跑起来"的旧因已除：夹具边 ID 泄漏修复后底件不再失败，`f_px` 自由端四组全部建成。剩余阻塞仍只有一条——**第三墙在 T05 边界内**，与释放实现无关。
- `end_trim_mm` 语义仍未定：N06 终验的 `trim_probe` 仍为 `trim_ignored`（完整墙与 20 mm 修剪墙增量同为 18025.291234051932 mm³，`setback_confirmed=false`），不能用于角部让位。
- 状态口径不变：四壁不支持、corner relief/miter 未实现、释放在材料端未取得可观测几何，**FEAT-014 保持开放**。
