# DEV-051 T11 验收卡：四壁释放完整能力（FEAT-014，离线实现阶段）

日期：2026-10-29 离线 + 两轮实机（Asia/Shanghai）。阶段：**两块底板已建成，第一道折边即报 `ProFeatureWithoptionsCreate=-1`；四壁与释放能力仍未验收通过**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次实机未启动/关闭/重启 Creo、未注入故障、未清 unknown 保护、未重提已受理 job；未改版本、未合 main、未推标签、未 push、未发布，未实施 T12/T13。本卡不得读作“四壁能力已具备”或“折边缺陷已修复”。

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
