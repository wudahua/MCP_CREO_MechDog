# 2026-11-13 0.23.2 球鼻艏反馈批实施计划（A/B 批已实施，C 批未实施）

关联：反馈包 `C:\Users\Administrator\Downloads\反馈包-球鼻艏-20261112\反馈包-球鼻艏-20261112`（README 主报告 + `01_TXT依据-球鼻艏B030.md` + 10 组作业回执 + 6 份历史文档）· [BUG-120](../work-items/BUG-120.md) · [统一台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md)

基线：`main` 提交 `8a08118`（`version.py` = 0.23.2；工作树另有未提交的文档改动：`AGENTS.md`、`docs/BACKLOG*.md`、`docs/DEVELOPMENT.md` 与未跟踪的 `docs/development/CREO_TOOLKIT_*.md`、`docs/work-items/DEV-084/085.md`）。编号已核对：BUG 至 120、FEAT 至 066、DEV 至 085，本轮新占用 BUG-121～124、FEAT-067。

## 0. 本文件的性质

这是**计划 + 本批执行记录**。A 批（离线 + Creo 12.4 实机回执）、B 批（模板 XML，Creo 12.4 实机）与 C1（STEP/IGES 导入，Creo 12.4 实机）已于 2026-11-13 执行完毕并附证据；C2（Creo 10 跨版本复测）仍未实施，交接步骤见[复测交接包](../development/CREO10-RETEST-0232-2026-11-13.md)。各批实机均在用户当次确认下连接 Creo 12.4；未清锁/unknown 保护、未改用户模型、未重发版本；`bridge.py build` 为本地编译。

不支持据此声称：Creo 10 上曲面能力已可用、模板 XML 跨版本可读、Creo 10 的导入已过许可验收、WorkBuddy 黑盒结论。12.4 上的导入验收（440.0 mm² 与 1540.0 mm² 两例）只属 12.4。所有跨版本结论只能由外部 Creo 10 复测给出。

## 1. 反馈核对结论

主问题（`create_code=0` → `feature_incomplete=true` → 几何项/面/quilt 全 0 → `elemtree_extract=-18`）与 [BUG-120](../work-items/BUG-120.md) 已记录的现象一致，**本轮不重复调查根因**；0.23.2 的诊断字段与能力披露已在报告 E9 中确认生效。下面只记录本轮新增或需要修正的判断。

| # | 反馈项 | 判定 | 依据 |
| --- | --- | --- | --- |
| 1 | 路线 C：12.4 导出模板 XML + `ProElemtreeFromXMLCreate` | **声明层成立，可做；最大风险是跨版本 XML 可移植性** | 本机 Creo 12.4 SDK `ProElement.h:3187`（`ProElemtreeWrite`）、`:3230`（`ProElemtreeFromXMLCreate`，注释明确产物可作 `ProFeatureWithoptionsCreate/Redefine` 输入）、`:3282`（错误表释放）；`generic.cpp:4875-4883` 的 `dump_tree` 已有"导出"半条链，缺"读入 + 换引用"半条 |
| 2 | 路线 D：`import_geometry`（STEP/IGES） | **声明层成立，可做；许可与"导入后是否为 quilt"必须实测** | `ProIntfimport.h:176`（`ProIntfimportModelWithOptionsMdlnameCreate`）、`:15/:20`（`PRO_INTF_IMPORT_IGES/STEP`）、`:82`（`SourceTypeGet` 预判）、`:125` 旧入口已 `DEPRECATED: Since Creo 1`、`:171` `PRO_TK_NO_LICENSE` 为声明的失败码 |
| 3 | 12.1「`kernel_completion=unsupported` 仍建空壳」 | **确认，可离线修**；但不得用 `release_numeric` 推断能力 | 创建点在 `native/surface_loft.cpp:988`，`PRO_FEAT_CR_INCOMPLETE_FEAT` 于 `:985` 传入；`unsupported` 分支只在创建后计算（`:1031-1051`），全文件无提前拒绝。现有唯一提前门禁是编译期 SDK 常量探测（`surface_loft.cpp:35-40`、`:1202-1210`；Python `capabilities.py:315-325`） |
| 4 | 12.2「`export`/`inspect` 被基线漂移拦」 | **现象确认，但根因位置需修正**：不是 Python 门禁 | `generic_bridge.py:536-539` 的 `validate_baseline` 只在 `not readonly` 时调用；报告的回执文案带 `model_reconciliation_required: Saved feature/body count changed`，实为**原生**准入比对：`generic.cpp:7827` 调 `verify_saved`，严格比对在 `:5062-5066`（feature/body 数量）与 `:5118-5121`（体积），前缀加在 `:7829`。只读请求也走这条路径，故 export 被杀 |
| 5 | 12.3「低版本 `boundary_conditions` 无法验证」 | **维持不可用，本轮不排期** | `PRO_E_BNBLN_TAN_COND` 非整型（报告 E6），补写路径依赖提取；提取不可用即无路径。模板路线也不解决"相切条件必须由调用方覆盖模板值"以外的问题 |
| 6 | 报告 9#6「`PRO_E_BNBLN_TAN_COND` 正确形态未定」 | **接受"未定"，不猜** | 本机 12.4 有 BNBLN 树常量；Creo 10 侧缺 `Probbl.h`（DEV-082 门控已记录）。模板路线会把 12.4 的真实形态一次性固定下来，是本轮唯一能收敛该问题的路径 |
| 7 | 13.2 建议"包围盒可作自动断言" | **当前不支持，值得补** | `schema.py:1908-1917` 的 `Assertions` 只有 `require_solid`/`volume_mm3`/`geometry_deviation`，无 bbox 与曲面面积断言 |

两条硬约束本轮继续有效：**不得**用"多截面近似/椭圆截面"替代 B030（源项目禁用近似）；**不得**把 Creo 12.4 的通过外推为 Creo 10 可用。

## 2. 任务总表

状态：`已交付` / `待分派` / `需用户当次确认`。批次：A 离线可验、B 需 Creo 12.4 实机、C 需实机+导入许可。

| 任务 | 反馈项 | 台账 ID | 批次 | 状态 | 交付物 / 验收 |
| --- | --- | --- | --- | --- | --- |
| A1 只读操作不再被基线漂移拒绝 | 12.2 | [BUG-121](../work-items/BUG-121.md) | A | **已交付（离线）** | 复核修正：原生准入的 `verify_saved` 本就被 `!readonly` 包住，故改为 Python 侧只读型计划自动按只读准入（`readonly_source="inspection_only_plan"`），并对写计划失败消息追加 `creo_reconcile_model` 动作指引。11 项单测；12.4 实机只读导出通过并记 `readonly_source`（`build/live_acceptance_20261113T150422`） |
| A2 已知内核不支持时不建空壳 | 12.1 | [BUG-122](../work-items/BUG-122.md) | A | **已交付（离线）** | 准入条件用**同一 worker 的实测签名**（`kernel_completion=unsupported` + `create_code=0` + `extract_code=-18`）替代 `release_numeric` 推断；提交前拒绝、不建作业，能力表加 `runtime_admission`。10 项单测；12.4 实机同一模型连续两次放样不误拒（`build/live_acceptance_20261113T150422`） |
| A3 曲面断言：bbox 与面积 | 13.2 | [FEAT-067](../work-items/FEAT-067.md) | A | **已交付（12.4 实机两态）** | `assertions.bbox_mm` 已交付（原生用 inspection 的每实体 bbox 求并集并换算 mm，未知单位失败）；12.4 实机通过/失败两态回执已验证（`build/live_acceptance_20261113T150422`）；`assertions.surface_area_mm2` 于同日补齐（`ProSolidSurfaceVisit` 逐面求和后平方换算 mm²，任一面失败即不可用，绝对容差），23 项单测 + `bridge.py build` + `dev_check` 3548 项通过；12.4 实机两态回执均已取得（`build/live_acceptance_20261113T160310`，14 项全 PASS） |
| B1 模板 XML 导出（12.4 侧） | 11.1 | [BUG-123](../work-items/BUG-123.md) | B | **已交付（12.4 实机）** | 3 截面 + 3 导线实测 `create_code=0 / extract_code=0 / incomplete=false / 1600.0 mm2 / tree_elements_read=111`；两次独立 dump 同 SHA256 `4ef01eed…`；`templates/elemtree/` + `manifest.json`；驱动 `tools/export_elemtree_template.py`（`--from-job` 可复用已验证特征）；结构确认"仅 6 条曲线引用模型相关" |
| B2 原生 loader：XML → 特征 | 11.1 | BUG-123 | B | **已交付（12.4 实机）** | `ProElemtreeFromXMLCreate` + 结构校验 + 按 1DIR/2DIR 顺序替换曲线集合 + `ProFeatureWithoptionsCreate`；回执 `tree_source="template_xml"`、`template.file/sha256/sections/guides/load_code/element_errors`；数量不符即 `TEMPLATE_SHAPE_MISMATCH`，解析失败即 `TEMPLATE_TREE_LOAD_FAILED` |
| B3 模板路径与现有树路径一致性 | 11.1 | BUG-123 | B | **已交付（12.4 实机）** | `tools/test_loft_template.py --live` 11 项全 PASS：手写树 1600.0 mm² vs 模板 1600.0 mm²，相对差 0.0 ≤ 1e-6；两个负例（形状不匹配、坏 XML）均被拒且未留特征 |
| C1 `import_geometry` 操作 | 11.2 | [BUG-124](../work-items/BUG-124.md) | C | **已交付（12.4 实机）** | 新 op 走"新建独立 part"分支；显式 profile 并记录 SHA256；回执 `created_model_name`、`create_code`、`surface_count`、`area_mm2`、`quilt_closure`、`profile_path/sha256`；许可失败必须回 `PRO_TK_NO_LICENSE` 原码。12.4 实机两例全 PASS（STEP 440.0 mm²、IGES 1540.0 mm²，均保存重载），门禁已删除并登记 `geometry_import`；Creo 10 与许可失败原码未验（交接包场景 4） |
| C2 Creo 10 跨版本复测 | 全文 | BUG-123、BUG-124 | C | 需外部环境（交接包已备） | 步骤与判据见[复测交接包](../development/CREO10-RETEST-0232-2026-11-13.md)：五个场景（只读导出、误拒回归、模板路线、导入路线、计划级断言）与四态报告要求；由报告方在 42 上执行，本轮不得代替 |

## 3. A 批实现要点

### A1 BUG-121（实现修正：Python 侧，风险低）

执行时复核发现：原生准入的 `verify_saved` 调用已被 `!request.value("readonly", false)` 包住，`export` 工具本身也以 `readonly=True` 提交，所以"只读被拦"只发生在**计划路线**（`creo_execute_plan` 直接写 `{op:'export'}`，计划按可写提交）。因此不改原生比对，改为：

- `generic_bridge.py` 新增 `INSPECTION_ONLY_OPERATIONS` 并复用到只读白名单；既有模型 + 非空 + 全部只读操作的计划自动降级为只读，`request.json`/`job.json` 记 `readonly_source`。
- `src/creo_mechdog/reconciliation.py` 新增 `admission_failure_message()`：写计划被拦时在原生的 `model_reconciliation_required: ...` 之后追加 `creo_reconcile_model` 的动作指引，原生原文保留在 `native_message`。
- 回归：`tests/unit/test_inspection_only_admission.py`（11 项）。不再新增 `baseline_drift` 回执块——原生侧本来就没拦只读，凭空加字段只会制造未验证的语义。

### A2 BUG-122（Python 为主，风险低）

- 复用 `capabilities.py:199` 的 `WORKER_CONDITIONAL_OPERATIONS` 与 `:265-280` 的观测投影，把"仅披露"升级为"可拒绝"：`surface_loft_runtime` 为 `unsupported` 且 `worker_sha256`/`release_numeric` 与当前 worker 一致时才拒绝。
- 拒绝文案需同时给出三条出路：升级宿主、改用模板路线（B 批交付后）、改用导入路线（C 批交付后）。
- 不得把该判断写进 `release_numeric` 分支逻辑；不得改动 12.4 上 `supported` 的现状。
- 回归：`tests/unit/test_surface_loft_runtime_observation.py` 扩展（一致才拒、跨 worker 不拒、缺观测不拒、12.4 不拒）。

### A3 FEAT-067（bbox 首轮交付，面积同日补齐）

- `schema.py` 新增 `AssertionBbox` 与 `Assertions.bbox_mm`；原生 `verify_assertions` 用 inspection 已记录的每实体 `bbox` 求并集并按 `length_scale_to_mm` 换算 mm，未知单位直接失败。
- 断言失败走既有"末次操作后、保存前判定 + 回滚"路径，不新增软失败。
- `surface_area_mm2` 于同日补齐：新增 `total_surface_area_native()` 用 `ProSolidSurfaceVisit` 逐面调 `surface_area_native` 求和（回调传 `nullptr` 过滤器），`measured_surface_area_mm2(state)` 按 `scale.scale * scale.scale` 换算 mm²；任一面测不出、遍历失败、空模型或非 part 都返回不可用，绝不以 0 冒充。不像 `quilt_area_native` 只覆盖单个 quilt。
- 用途：让反馈 13.2 的 `X∈[6409.4736,7809.4736] / Y∈[0,181.325] / Z∈[-660,-460]`（tolerance 1e-3）可直接写成断言。

## 4. B/C 批实现要点

### B 批：模板 XML（BUG-123）

1. **模板形态**：现有 `surface_loft` 的树骨架是 `FORM=PRO_USE_SURFS` + `PRO_E_DTM_SRF_TYPE=11` + `PRO_E_BNBLN_CURVES`（`native/surface_loft.cpp:957-973`）。模板必须是同一形态且在两方向均有曲线，否则"减少数量"时无法裁剪。建议先只支持 **固定规模** 模板（例如 3 截面 + 3 导线，正好覆盖球鼻艏 B030），超出规模回退到现有手写树路径。
2. **替换点**：`PRO_E_STD_CHAIN_HOLDER` → `PRO_E_STD_CURVE_COLLECTION_APPL`（`surface_loft.cpp:526-537` 的 `surface_loft_chain` 是手写树里同位置的实现）。loader 需按 role 顺序枚举两个方向的 holder，逐个数对后替换 `kind/id`，数量不一致即 `TEMPLATE_SHAPE_MISMATCH` 并列出模板与请求的数量。
3. **失败语义**：`ProElemtreeFromXMLCreate` 返回 `PRO_TK_BAD_CONTEXT` 时必须把 `ProXMLErrorlist`（`ProElement.h:3222-3228`）里的 `line_number`/`column_number`/`message` 投影到回执 —— 这正是"低版本缺哪个元素"目前唯一可能的机器答案，比报告 §9#6 的终端输出可靠。
4. **门控**：新路径必须挂在 worker 编译期常量下（沿用 `MECHDOG_HAS_BNBLN_TREE`），并由 Python 能力表声明 `surface_loft.tree_source` 取值域；12.4 默认仍走手写树，避免回归面扩大。
5. **不承诺**：模板 `create` 成功不等于 Creo 10 上 `ProFeatureIsIncomplete=false`；这条只能由 B2 之后的外部复测（C2）判定。

### C 批：导入通道（BUG-124）

1. 接线点（只列位置，未改）：`native/generic.cpp:4832` 前的 op 分派链与兜底 `:4886`、再生排除名单 `:4888-4890`、外部输出判定 `:4952-4954`；`schema.py`（`ExportOp:1936` 附近新增模型、`Operation` 联合体 `:2219`、`validate_operations:2320`）；`capabilities.py:9`（`REGISTERED_OPERATIONS`）与能力家族；`server.py:2539-2563`（工具注册范式）；`generic_bridge.py:486-506`（新建模型分支）。
2. 语义按反馈建议定为"导入到独立 part"：与 `assemble_component` 组合，不写主模型，回滚不牵连导入件。
3. `profile` 显式传入并记录 SHA256（默认 profile 会成为会话级副作用，`ProIntfimport.h:190` 已明写）。
4. 失败码必须原样透出：`PRO_TK_NO_LICENSE`、`PRO_TK_UNSUPPORTED`、`PRO_TK_INVALID_FILE`（`:165-172`）。

## 5. 依赖与执行顺序

```
A2（BUG-122 准入） ──┐
A1（BUG-121 只读）  ──┼─→ 0.24.0 一批（离线可发布）
A3（FEAT-067 断言） ──┘

B1（导出模板，需实机） ──→ B2（loader） ──→ B3（一致性） ──→ BUG-123 剩余：Creo 10 复测
                                                  └─→ C2 外部 Creo 10 复测（交接包已备）

C1（import_geometry，12.4 实机已验） ──→ C2（许可 + 几何复测） ──→ BUG-124 完成
```

不可逆顺序三条：

1. A2 先落地，B/C 才有"不建空壳"的统一入口；否则模板失败仍会在模型里留空壳。
2. B1 未取得模板前不得写 B2 的曲线替换逻辑（否则只能猜结构）。
3. 任何实机步骤（B1/B3/C1 实机、C2）都要用户当次确认，确认不延续到下一次会话。

## 6. 验收口径

最小通过（任意两张开放曲线）沿用反馈 13.1：`create_code=0`、`extract_code=0`、`feature_incomplete=false`、`quilt_count=1`、`quilt_closure=open`、`surface_area_mm2` 为有限正数、`kernel_completion="supported"`。

球鼻艏专项（13.2）用反馈包 `源数据/_bulb_sections.json` 建 6 张草图，`sections=[A21 点, A22, A23]`、`guides=[A18, A20, A19]`，断言 bbox `X∈[6409.4736,7809.4736]`、`Y∈[0,181.325]`、`Z∈[-660,-460]`（tolerance 1e-3），保存重载 `saved_file_reloaded_and_verified=true`，随后 `surface_fill`×2 → `quilt_merge` → `mirror` → `boolean_bodies` 连续可跑。

本轮 A 批自身证据只到"单元测试 + `bridge.py build` + `dev_check`"，2026-11-13 已补 Creo 12.4 实机回执，见第 8 节「A 批实机证据」；GUI 保存造成的漂移、Creo 10 复跑与「先失败一次再成功」序列仍未验。

## 7. 第 0 步（登记与归档，已执行）

1. 已归档 30 个原件到 [feedback-0.23.2-2026-11-12](../../validation/feedback-0.23.2-2026-11-12/MAPPING.md)，SHA256 与包内 `MANIFEST-SHA256.txt` 逐条一致；`manifest.json` 与 `MAPPING.md` 已写。
2. 已在 `docs/BACKLOG.md` 登记 BUG-121/122/123/124 与 FEAT-067，工作卡新建于 `docs/work-items/`；表行 180→185（BUG 83 / FEAT 64 / DEV 38）。
3. 已在 `docs/DEVELOPMENT.md` 顶部加本批记录。
4. `tools/check_backlog_counts.py` 复核通过（见第 8 节证据）。

## 8. 本批证据（2026-11-13）

- `tools/check_backlog_counts.py`：`consistent: true`，declared = actual = 185（BUG 83 / FEAT 64 / DEV 38），无重复 ID。
- `bridge.py build`：exit 0，`build\creo_worker.exe` 已重编。
- `tools/dev_check.py --work-item BUG-122`：3494 项通过，`success: true`。
- 新增单测：`test_inspection_only_admission.py` 11 项、`test_surface_loft_kernel_admission.py` 10 项、`test_bbox_assertion.py` 10 项。
- 过程中修正的两处既有契约：`test_surface_group_measure.py`、`test_surface_curvature_contract.py` 原本断言只读白名单的字面量列表，改为断言 `INSPECTION_ONLY_OPERATIONS` 内容 + 只读分支引用该常量；发布记录门禁要求工作卡"分类"与台账状态一致，三张卡已对齐为"部分交付，剩余待验收"。
- 未做：WorkBuddy 黑盒、版本发布、Git 提交。

### B1 实机证据（2026-11-13，Creo 12.4.0.0，`release_numeric=44`，用户当次确认）

- `tools/export_elemtree_template.py --live --confirm-session-usable`：建模作业 `cb65f609b5c1492cb2040e809f998ccc`（模型 `e1c69a8cba5c40c5aa025f586af928d6`），`surface_loft` 实测 `create_code=0 / extract_code=0 / feature_incomplete=false / kernel_completion=supported / section_count=3 / guide_count=3 / surface_area_mm2=1600.0 / quilt_count=1 / tree_elements_read=111`，特征 id 80。
- 两次独立 dump（`aaeadf86194f4c3995b665551a6e5fdc`、`c1d4789cf588423f9fbe69165c5c0856`，均 `effect_status=no_effect`）产出字节相同的 `templates/elemtree/loft_s3g3_creo12.4.xml`（14898 B，SHA256 `4ef01eed521c43c491f2ba788da93780d1a8729496e796e1bd15f11979a7508b`）。
- 结构解析：`PRO_E_FEATURE_FORM=PRO_USE_SURFS`、`PRO_E_DTM_SRF_TYPE=11`、1DIR/2DIR 各 3 个 holder、每 holder 一条 `PRO_XML_REFERENCE`（owner/id/type，id 45/53/61 为截面、67/79/73 为导线；`PRO_XML_COLLECTION_INSTRUCTION_TYPE=101`）；`PRO_E_BNBLN_TAN_COND` 4 条均为 `TAN_COND_TYPE=1` 且 `PRO_E_SURF_CHAIN_REF` 空选择 → **无他模型曲面引用**。
- 回归：`tests/unit/test_elemtree_template.py` 8 项通过。

### B2/B3 实机证据（2026-11-13，Creo 12.4.0.0，用户当次确认）

- 驱动：`tools/test_loft_template.py --live --confirm-session-usable`，报告 `build/loft_template_20261113T110627/report.json`，模型 `ccc34db1ffd74b3aaab04b3a2f28cd52`，11 项检查全 PASS。
- 正例：手写树作业 `ea2ac5993a1944c084a6c5a78ba46328`（特征 80，`surface_area_mm2=1600.0`）；模板路线作业 `d590b87b1648433f9f4a8d76e515953e`（特征 92，`tree_source=template_xml`、`create_code=0`、`extract_code=0`、`feature_incomplete=false`、`surface_area_mm2=1600.0`、`template.sections=3`、`template.guides=3`、`load_code=0`、`element_errors.total=0`）。B3 判据 `relative_difference=0.0`。
- 负例：作业 `49a9b0653e9545a79e739485579626b8` → `TEMPLATE_SHAPE_MISMATCH`（模板 0 截面 + 3 导线 vs 请求 3 + 3，不裁剪），`feature_id=null`；作业 `6fb40ac197d54276a3bef8b0146da9c0` → `TEMPLATE_TREE_LOAD_FAILED`（`ProElemtreeFromXMLCreate=-1`，元素错误 `unexpected end of input`），`feature_id=null`。
- 契约：`LoftTemplate` 校验 `.xml` 后缀/文件存在/`sha256` 与磁盘一致；`template` + `boundary_conditions` 在 Python（`SurfaceLoftOp.template_route_limits`）与原生（`TEMPLATE_BOUNDARY_CONDITIONS_UNSUPPORTED`）双侧拒绝。
- 回归：`tools/test_loft_template.py` 离线 5 项、`python -m unittest tests.unit.test_elemtree_template tests.unit.test_surface_loft_kernel_admission` 19 项通过。
- BUG-123 剩余：Creo 10 解析与创建后 `ProFeatureElemtreeExtract` 未复测（模板只换输入树）；模板仅 3 + 3 一种形态。打包已于同日补齐（`release_integrity.template_library_files()` 按清单逐项校验，`tools/package.py` 的 `source_files()` 含模板与清单，`tests/unit/test_template_packaging.py` 10 项）。

### A 批实机证据（2026-11-13，Creo 12.4.0.0，`release_numeric=44`，用户当次确认）

- 驱动：`tools/test_0232_live_acceptance.py --live --confirm-session-usable`，报告 `build/live_acceptance_20261113T150422/report.json`，10 项检查全 PASS（`passed: true`）；同日 14:51 一轮 `build/live_acceptance_20261113T145133/report.json` 结论相同；16:03 一轮在驱动加入面积断言后为 `build/live_acceptance_20261113T160310/report.json`，14 项全 PASS。
- FEAT-067：40×40×10 实体作业 `841d50bb8ea54135bb2106cb80a61c4c` 通过 `bbox_mm`；同一模型叠加一块后仍用原期望，作业 `99e8a458cab3424ebb5d920a026f7841` 失败并报 `Bounding box assertion failed on Z: measured [0.000000, 15.000000] expected [0.000000, 10.000000] tolerance 0.001000 mm`，模型 `dd0716d399694b11841e97e57109d864` revision 保持 1。
- FEAT-067 面积（16:03 轮）：40×40×10 方块作业 `c7c20fd3544b453fb8731900b8fb68c3` 以 4800 mm² 断言通过（模型 `5344029b3e624c318ee69acc6c26f363`，revision 1）；同一模型再叠一块后仍用 4800，作业 `a759523eac444d4eb9914c0d8aa186fc` 失败并报 `Surface area assertion failed: measured 5600.000000 mm2 expected 4800.000000 mm2 tolerance 0.500000 mm2`，revision 保持 1。5600 = 顶/底各 1600 + 四周各 600，说明逐面求和只计外表面，内部叠合面未被重复计入。
- BUG-121：模型 `276044e4514343e3bb94bab9e75052da`（作业 `9864aedf7443421786625cad18cd1274` 新建）上提交 `[{op:'export',format:'step'}]`，作业 `a849fb7c0a7b4d5c86037a5f9ec3918e` 成功，`job.json` 记 `readonly=true` / `readonly_source=inspection_only_plan`；`creo_get_job` 的 compact 视图不披露这两个字段，判定必须读作业清单。16:03 轮同结论（作业 `7b7ec1450490427598a2dbe72b99941c`）。
- BUG-122：模型 `41ec492b29c446e2992b43868b7eedef` 连续两次 `surface_loft`（作业 `652f2c29516244109870dfe34225cf4c`、`6b98d824f5724d67bc308edc7e4af932`，revision 2）均成功，回执无 `refused before a job`。
- 当轮修掉的驱动缺陷：`build/live_acceptance_20261113T144932` 的 BUG-121 检查读 compact 视图，得到 `readonly_source=null` 而误判失败；改读作业清单后通过，`jobs/9a3333e812f041fcbb82e5ba2a6f2a10` 与 `jobs/565c1712eb1048baa718331cd30590a5` 两份清单实际都记录了该字段。
- 仍未验：GUI 保存造成的基线漂移、Creo 10 复跑、12.4 上「先失败一次再成功」的序列、未知单位模型的两条断言、`surface_area_mm2` 的空面与单面失败路径。
