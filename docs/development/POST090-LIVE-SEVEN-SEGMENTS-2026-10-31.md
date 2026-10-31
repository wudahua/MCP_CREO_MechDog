# Post-0.9.0 七段实机复测（2026-10-30～31）

分支 `codex/dev051-feedback070`，执行前 `git log -1` 为 `7288f2f61f3fb5e2d3d041ed94edccfef50d6327`。执行前已有他人未提交内容；本轮未改源码、未切分支、未构建、未清 unknown、未重启或结束 Creo。`build/source.sha256` 的记录值为 `47a6591d17b8ef6b81530963ea2096e2b424892be3e4b1dba378c64cd93a1d8b`（文件时间 2026-10-30 23:11:04，副本在本轮 build 根目录）。各驱动自带的 `provenance.source_fingerprint` 算法及取样时间不完全相同，以原始 JSON 为准；不要把此单一文件哈希解释成七段期间动态工作区完全相同。

环境：Windows x64、Creo 12.4.0.0，现有会话；本机开发服务。执行时 `parametric` PID 25596 与 `xtop` PID 21968 各段前后均显示 `Responding=True`，驱动确认会话可连接。此进程检查只说明 Windows 响应，不替代原生作业终态。报告根目录：`build/post090_live_20261030T234952/`。所有命令串行，均带 `--live --confirm-session-usable --output`，具体命令和 stdout/stderr 见各段 `console.log`。原始报告包含逐次工具调用、请求、job/model ID、revision、几何、重载及错误。未检测到 `unknown` 或 `busy` 终态，也未触发 180 秒未终态停止条件。失败后没有重放已受理作业。

| 段 | 本轮结论 | 已执行 / 未执行 |
| --- | --- | --- |
| N07 T02 | 失败 | 5 创建例通过；首个方向编辑因 native 弧回显未知失败；其余编辑、非法编辑与恢复未执行 |
| N08 T09B | 失败 | 内部单中心线失败；显式轴与无中心线负例通过；外部真多线夹具未提供，未验 |
| N09 T09A | 失败（驱动异常） | 双组件创建通过；重载关联比较抛 TypeError；删除重插与 ID 重排未执行 |
| N10 T12 | 失败 | 3 盲孔例均未通过严格 oracle；方向例前因模型名过长中断，余下 3 例未执行 |
| N01 BUG-090 | 部分通过 | contract 5/5 通过，relief 失败；Creo 10 SDK 定向编译仍未验 |
| N04 FEAT-051 | 失败（驱动异常） | 首例创建后读取缺失 `revision` 抛 KeyError；矩阵未执行 |
| N11 BUG-088 | 部分完成 | 空件缺图复现，实体和 3 个盘体阶段文件写出；钣金对照提交被拒，图像内容待人工复核 |

## 逐段证据与边界

**N07**：创建例 `legacy_0_to_90`、`legacy_90_to_0`、`dir_minus1_90_to_0`、`dir_minus1_0_to_90`、`tilted_xz_dir_minus1_0_to_90` 均有 native 弧回显、独立体积及 `result.saved_file_reloaded_and_verified=true`。首个编辑 `job=e676db6877724808b3e67cd826cea9be`、`model=61c12d7b10dd48f6aa2c3f9be450b5f8`，revision 1→2、体积 `1428.0972451017303` 对 oracle `1428.0972450961724` mm³、重载 true，但 `arc_echo.source=unknown`、`query_code=-2`，原始判定 `native_arc_echo_not_measured`。不能据体积与成功终态代替原生弧读回。五例创建及编辑的完整 ID 与数值在原报告；编辑后续未执行。

**N08**：内部中心线 `job=1c1370927c384cd28d3bbb3534149b34`、`model=66edf63c0b5847cc85e3f20e8a865b89`、rev 1，succeeded、体积 `9424.777960769377` mm³，保存重载 true、重载后 rev 2；原生 `section_centerline_count=3`（预期 1），`entity_ids` 无 `spin_centerline`，故真实 ID 来源未证实。显式基准轴 `job=fae86b3105904e32aa484d70bfc31705`、`model=d4dad2268c894618b2d9dc1121d66d71`、rev 1，passed；无中心线负例 `job=8da0c6468aef44079bf49bb579fdbca8`、`model=57c3cc8d5f1c4523b48c9a7358a15ef8`、rev 0，预期 failed、判定 passed。轴帧及重载明细见原报告；真多线未验。

**N09**：双组件 `assembly_job=2034f58774764b6ebbd6e2ce1a067c60`、`model=fb732f48879d4255b136b61d38fc6a8f`、rev 1，两个 label 分别解到 feature ID 40/43，源 revision 均 1。其后驱动在 `sorted(map(identity_of, rows))` 对字典排序，报 `TypeError: '<' not supported between instances of 'dict' and 'dict'`。报告内暂时的 `passed=true` 是截断前状态，不能作为整段通过；重载关联、删除墓碑/重插及 ID 重排未证实。

**N10**：`blind_straight`、`blind_counterbore`、`blind_countersink` 的 hole job 分别为 `e6c5b1639404444d9dacc79c6c09e577`、`3d425e823e1f450ba2ee03b0d8d17541`、`5ac1ce55851b4cf6a6ba898e942dbafb`，model 分别为 `5facf286a4db44d88c17c43b75f5746a`、`a1b03ab063e84f188bb29779d9d5df94`、`78f7b284c7d44ec9adef12103c8692b5`，均 succeeded、rev 2、重载 true。直孔去料 `197.92033717615413` 对主 oracle `197.92033717615698` mm³，但面数与圆柱轴不符；沉孔去料 `343.7145697324486` 对主 oracle `326.7256359733385`，锥孔 `289.26029707022826` 对 `272.2713633111154`，后二者只命中 `drill_tip_118_below_depth` 备选，不能判通过。下一例创建前 `ValueError: Model name 't12_direction_side_normal_193146' violates the 31-character name rule`；方向、真实 dimension ID 编辑及翻向回滚未执行。

**N01**：contract 五例 job/model/revision 逐例在 `contract.json`；五例均 succeeded、rev 1、重载 true、体积误差 0.0，`wall_contract.part_thickness_mm` 与该例请求厚度一致并由 native 实读。五例请求厚度并非全为 1.0：分别为 232、1、1、1、1 mm；1 mm 的四例实读 1.0。relief 的 `relief_none`、`relief_rect_1x1` 底件 succeeded，各到第三个折边失败；例如 `relief_none` 的第三折边 `job=530a8258b23c409ca149e69960fee463`，原始错误 `Regeneration produced a failed, suppressed or incomplete feature`、`toolkit_code=-1`、`failed_stage=execute_sheetmetal_flange`、`rollback_succeeded=true`，revision 保持 3、体积保持 `78970.58246810423` mm³。材料矩阵 `mat_baseline` 底件 failed，后五组未执行；完整原始错误及每个 job 在 `relief.json`。

**N04**：首次 `creo_execute_plan` 后的创建结果没有驱动预期的 `result.revision`，驱动 `KeyError: 'revision'`。报告未形成完整案例行，调用与原始错误在 JSON/console。凸凹圆角、三组倒角、11° 拔模、flip、应用集数、批回滚和重载均未取得可判定证据；不填通过。

**N11**：空件 `job=edd3d790817b44c6a0ff4868e70b3033`、`model=79da44e584ec49c79c6b50d7852866c3`、rev 1，作业 succeeded、重载 true，但预览 `failed_step=output_file`、`failed_code=-4`，`raster=0`、`file_check.exists=false`、系统 `error_code=2`、`FileNotFoundError`；空件缺图按记录为预期复现，不能判文件通过。同模型续建实体 `job=103d543adbda4b809fa2c60701879655`、rev 2、体积 `60318.578948924034` mm³、重载 true，JPEG 写出 16245 B。盘体、切除、阵列三阶段 job 分别为 `3682b82b770b49b2873898c0f40a0046`、`339532537b60489c8e1b524d892b2f69`、`ff5a967b7a9041e39d9e586480948eff`，同 model `079f2c7541bc423b89a2572612609810`，rev 1/2/3、各重载 true，JPEG 分别 16245/16621/17794 B。钣金对照 `creo_execute_plan` 在提交时返回 `Sheetmetal operations require an MCP sheetmetal model`，未产生作业。四幅图像在 `n11/images/`，文件写出成立；图像内容仍 `human_review_pending`，原案原件未齐，不作原案回放通过结论。

## 报告 SHA256

| 文件（均相对上述根目录） | SHA256 |
| --- | --- |
| `n07/report.json` | `01367c6c5b91ad757e9c376a7a93e457985d14484b7595aa116a1a99df561f8a` |
| `n08/report.json` | `639e412dba5a43830a4d80a33a0b5633f7eac64afeca1d25b11b05a0338abf94` |
| `n09/report.json` | `95c214d2177a4ce91b7dcc32beda648ca5f831eed619c5ba1217f318cd15c3e4` |
| `n10/report.json` | `88c92f96605bccc8cf2ea1d637d78ec8514eb9badfe4810f86073d94460da074` |
| `n01/contract.json` | `931093ebb41ab9806690626e1f51e99c59bbc587711ab535b62379132ba371b0` |
| `n01/relief.json` | `d18e17fc15230bd0306f7937e6a430027c22dbfdf8b6e44399f5a351f9aeae4b` |
| `n04/report.json` | `15d6b79f4cb90f02091f30de81e94f0bc30b840428e3dc34b2b89859f501ee9f` |
| `n11/report.json` | `bc0ffa662dc729bf991c10f3ae0be8e45bfd5732396ed6f79293ec20772d51c9` |

受测源码指纹另见各报告 `provenance`（有该字段的驱动）；本轮现场未执行源码构建。全程保持 Creo 会话运行，结束时两个进程仍显示响应。没有真实并行调用，并发未验证。

## 第二轮复测（编排方串行）总表

本节记录**第二轮**实机复测：编排方亲自串行执行，基线提交 `b5dce10`。报告根目录 `build/post090_live2_20261031T115830/`（N07 为该根下 `n07/`，其余为各段 `run1`/`run2` 子目录），N06 终验单独位于 `build/post090_n06_live_20261031T142644/`。各段原始 JSON 留在 `build/` 下未入库；受测源码指纹见各报告 `provenance`（有该字段者）与 `build/source.sha256`（记录值 `993a4380…c6ff57`）。本节只追加，不改写上方首轮记录。

| 段 | 卡片 / 验收卡 | 本轮结论 | 已执行 / 未执行 |
| --- | --- | --- | --- |
| N07 T02 | FEAT-034 / DEV051-T02 | **部分通过** | 5 创建例与 3 编辑例全过（编辑回显 native、query_code=0、rev 1→2、重载 true，named_ids 修复实机生效）；**非法编辑反例判定未过待查**（`illegal_dir_zero` `passed=false`），其余 4 非法例与恢复编辑未执行 |
| N08 T09B | FEAT-008 / DEV051-T09B | **通过** | 内部单中心线 count=1 且 id 来源=草图实体 `spin_centerline`（id 9）；显式基准轴 id=52；无中心线负例；真多线仍未验 |
| N09 T09A | FEAT-023 / DEV051-T09A | **通过** | 双组件、跨作业重载（`identity_mirrors_unchanged=true`）、删除重插不误指、未知 label 拒绝全过；`id_renumbering` 半场景限制保持 |
| N10 T12 | FEAT-035 / DEV051-T12 | **通过** | 六例全过且均首次执行（tip 口径生产修复 `0f1844a` 实机验证成立） |
| N01 relief | BUG-090 / DEV051-T11 | **部分通过** | `relief_none`/`relief_rect_1x1` 判 `known_t05_boundary`（passed=true）；`mat_baseline`+四组 `mat_rect_*` 均 `known_t05_boundary`（释放几何不可观测如实记录）；`free_rect_both_4x4` 自由端真实建成通过 |
| N04 FEAT-051 | FEAT-051 | **通过** | run1 因夹具硬编码 surface id=1 失败（ProModelitemInit=-23），修复为默认基准面 2/4 构造 Z 轴（`b5dce10`）；run2 七夹具全过（圆角/倒角/拔模/pull/批回滚），`zero_delta` 离线专属 |
| N11 BUG-088 | BUG-088 | **通过（含人工图像复核）** | 空件缺图按记录复现；实体与三盘体阶段写出；`sheetmetal_wall` 在新建钣金模型上成功并独立写出 12381 B 图像；全场景图像经编排方人工看图与体积仲裁核对 |
| N06 FEAT-014 | FEAT-014 / DEV051-T11 | **通过（已知边界按设计生效）** | `ny_first` 自由壁建成重载 true；`px_then_ny`、`px_nx_then_ny` 的 `f_ny` 均 fast-fail `adjacent_bend_ends_rejected`（创建前拒绝、revision 不变）；`trim_probe` 仍 `trim_ignored`；四壁仍不支持 |

### 逐段要点与原始证据

**N07**（`n07/report.json`，SHA256 `b9942a89…dde4de`，`provenance.commit=49decae`、`source_fingerprint=734d2c1c…b901`）：创建例 `legacy_0_to_90`/`legacy_90_to_0`/`dir_minus1_90_to_0`/`dir_minus1_0_to_90`/`tilted_xz_dir_minus1_0_to_90` 全 passed，`arc_echo.source="native"`、`query_code=0`、误差 ≤5.6e-9 mm³。编辑例 `edit_switch_dir_0_to_90`/`edit_switch_dir_cross_zero`/`edit_switch_dir_tilted_xz` 全 passed，rev 1→2、`preserved_feature_id=40` 保持、重载 true，**首轮的 `unknown`/`query_code=-2` 回显缺失已消失**。**非法编辑 `illegal_dir_zero` 的 `passed=false`（`failures=["volume_missing"]`）**：入参被 schema 层 pydantic `value_error` 显式拒绝（"Arc dir must be the strict integer +1 (counterclockwise) or -1 (clockwise) … input_value=0"），**未产生作业**（`job_id`/`terminal_status`/`rollback` 全 null），revision 3→3 未变、基线体积 1428.0972451017303 保持；缺的是拒绝之后的同源实测体积（`measured_volume_mm3=null`），驱动在 `tools/test_arc_direction_live.py:719` 以 `AssertionError(row)` 终止，其余 4 非法例与恢复阶段未执行。**判定未过，待查；不得写成通过。**

**N08**（`n08/run2/report.json`，SHA256 `a4b4d2e3…c769`，`passed=true`）：`internal_centerline`（job `12cfeaa39583457f941ebf695e3c0528`、model `9d2e4ba7227240ab8ae4adbf533fa2ed`、rev 1、体积 9424.777960769377）`section_centerline_count=1`、`revolve_axis.id=9` 与 `sketch_entity_ids.spin_centerline=9` 一致、`id_source={entity:"spin_centerline", sketch_entity_id:9}`，重载 job `92785620d5e14c54b36d4a4843051665` true、重载后 rev 2；`explicit_datum_axis`（job `5b7cadaede754a58adbdea5677800056`、rev 1、785.3981633974481）`revolve_axis.id=52`＝`datum_axes[0].id`；`no_centerline`（job `459f8132d2f64df7b517bb815d2de9da`、rev 0）按预期 failed 且无 `revolve_axis` 块。同根首轮 `n08/report.json`（SHA256 `49211164…f0dbd`）在提交任何作业前因 Toolkit 未就绪停止（`cases=[]`），不作几何结论。真多线外部夹具仍未提供。

**N09**（`n09/run1/report.json`，SHA256 `d2fe2233…ec4ef`，`passed=true`）：`two_components` 装配 job `a272ed6046ea4d6aae60d9c5c772fcad`、model `15e103e217d14c5f879a17084839c345`、rev 1（`part_alpha`→40、`part_beta`→43）；`cross_job` 保存 job `5328f322486446c5a14d842b19d7ad59` succeeded、重载 true、rev→2、`identity_mirrors_unchanged=true`（首轮 `TypeError` 不再出现）；`rename_reinsert` 删除 `442b6fa5502a4639b264d8a826d46879`/重插 `16d90da61d3d440190dcacef4f79bbb7` 均 succeeded、rev 2→4、旧 label 未落到新 ID 46 上；`unknown_label` job `3f55cef59a374cf59ba8e027be8795a0` failed、`toolkit_code=-1`、回滚成功、rev 4→4。

**N10**（`n10/run1/report.json`，SHA256 `6056a097…76119`，`passed=true`）：`blind_straight` 197.92033717615413（`contract_flat_overall`/`overall_flat`）、`blind_counterbore` 292.7477684551013、`blind_countersink` 238.293495792881（后二者均 `contract_tip_overall`/`overall_tip`）、`direction_side_normal` 197.92033717615777、`direction_flip_guard` 翻向作业按设计失败并回滚后恢复孔 197.92033717615413、`edit_dimension_values` 292.7477684551013→374.0864038721993（rev 2→3，真实 dimension ID 14/13）——六例**均首次执行**并通过，未落任何 defect 变体。

**N01 relief**（`n01relief/run1/report.json`，SHA256 `cefce8ed…643a`，`passed=true`、`material_scenario_passed=true`）：`relief_none`/`relief_rect_1x1` 两自由端墙各 +18025.291234 mm³、重载 true，第三墙 `f_ny` 失败并归 `known_t05_boundary`（`relief_geometry_unverified=["f_ny","f_py"]`）；`mat_baseline` 与 `mat_rect_both_1x1`/`mat_rect_both_4x4`/`mat_rect_side1_1x1`/`mat_rect_side2_1x1` 五案底件全部 succeeded（`wall_contract.part_thickness_mm=1.0`）、`f_px` 建成、目标 `f_ny` 全部 `known_t05_boundary`（`relief_geometry_verified=false`，释放几何不可观测）；`free_rect_both_4x4` 自由端 `f_px` job `71ef2f4526324dbfbcb86bf31f3e2361` 真实建成、rev 1→2、+18025.291234051932、`relief_element_echo` 齐全、重载 true。

**N04**（`n04/run2/report.json`，SHA256 `714db02d…9fc2`）：`round_convex` −38.62833848818991、`round_concave` +38.628301733198896、`chamfer_three_face_pairs` −120.00000000000364（applied=requested=3）、`draft_flip_false` +17.556230361033258、`draft_flip_true` −15.41961220323752、`draft_default_pull` −15.41961220323752（`pull_verdict=pass`）、`draft_explicit_pull` −15.41961220323752（`pull_verdict=pass`）全过；`batch_mid_failure` 按设计验证（首操作保留读数 −38.62833848818991 且 `rolled_back`、失败操作 after 侧读数 null、后续 `not_executed`）；`zero_delta` 为 `not_applicable_live`（离线专属）。run1（SHA256 `eb7622d0…79abc`）在 `draft_explicit_pull` 底件因夹具硬编码 `{"kind":"surface","id":1}` 以 `ProModelitemInit=-23` 失败，由 `b5dce10` 改为默认基准面 2/4 构造 Z 轴后 run2 全过。

**N11**（`n11/run1/report.json`，SHA256 `9423057e…f17`）：`empty_part` job `adb0d134e623403282aa6e49ff6f3dac` rev 1 —— raster=0 但 `failed_step="output_file"`、`failed_code=-4`、`file_check.exists=false`、`error_code=2`、`FileNotFoundError`，**空件缺图按记录复现**；`empty_part_solid`（同 model `0a756bb1b1b94053824d457d0caabaf3` rev 2，60318.578948924034）、`disk`（rev 1）、`disk_cut`（rev 2，56548.667764616286）、`disk_cut_pattern`（rev 3，45238.93421169304）四例图像写出 16245/16245/16621/17794 B；`sheetmetal_wall`（新建钣金模型 `e31117a8dec44e56917692b482a32f22`，job `57bcea5aa1164d08a76e2c489642179a` rev 2，42920.0）**不再被拒**，独立写出 12381 B 图像；`explicit_jpeg_export` 17794 B 与 `disk_cut_pattern.jpg` 同 sha256。编排方人工图像复核结论已记入 [BUG-088 卡](../work-items/BUG-088.md)：四幅盘体图与空件续建图逐幅与夹具定义一致、渲染清晰，4×90° 阵列孔经体积仲裁 45238.934 = 60318.579 − 4×3769.911 证实，两幅字节相同者系同几何夹具；新增 `sheetmetal_wall.jpg` 呈薄壁平板 + 折弯轴中心线，与夹具一致。

**N06**（`build/post090_n06_live_20261031T142644/report.json`，SHA256 `5fd12b29…fe768`，`passed=true`）：`ny_first` 自由壁 job `40aae64263a24e65b9e3d360bf435360` succeeded、rev 1→2、42920.0→57293.61585482106、重载 true；`px_then_ny` 与 `px_nx_then_ny` 的 `f_ny` 分别 job `f706af6a78f1483c9a6ce20586605c15`、`94ea4ea25c5b42e3887aafe9688e41aa`，均 **fast-fail `adjacent_bend_ends_rejected`**——`stage="before_create"`、附着边 197（181.46 mm，end1 命中）/296（177.92 mm，两端命中）、邻接弧边半径 2.54 mm、退让界限 7.081 mm、折弯面 [193]/[292]，revision 2→2 与 3→3 均不变、回滚成功；`trim_probe` 仍 `trim_ignored`（trim 与无 trim 增量同为 18025.291234051932 mm³、`setback_confirmed=false`）。`capability_claim.four_walls_complete=false`——邻接明确拒绝已实机生效，四壁仍不支持、corner relief/miter 仍未实现。迭代历史：预检两轮修复（`ProEdgeNeighborsGet` 轮廓邻边不保证分属两端 → 改 `ProEdgeVertexdataGet` 按端扇区，`582c1a3`；端点行被后续直边邻边覆盖致 summary 空值崩溃 → 保留首个命中行 + summary 判空，`b5dce10`），此前两次实机（`post090_n06_live_20261031T134730/`、`…T142121/`）的第三墙仍是 `trigger_reproduced`。

### 本轮未测与边界

- N07：其余 4 个非法例、stage 5 恢复编辑与保存重载未执行；非法编辑反例判定未过待查。
- N08：真多线（真多用户中心线）外部夹具仍未提供；`axis_relocation_after_reload` 仍记 `not_observable_via_inspection`。
- N09：`id_renumbering` 半场景限制保持（原生拒绝保存，只能观察拒绝，不得整体记为实机通过）。
- N10：通孔口径、出口沉头与双端沉孔、螺纹/标准孔未验。
- N01 relief：材料端释放几何本轮仍不可观测；四壁不支持、corner relief/miter 未实现。
- N04：`zero_delta` 为离线专属；单位矩阵 mm/in/混合/未知仅离线覆盖。
- N11：原案回放不可执行（缺原 Part1/Part2 模型、原图与外部同作业 JSON），替代夹具不得当作原案通过。
- N06：四壁仍不支持；`end_trim_mm` 语义仍未定，trim 不能用于角部让位。
- 全程无真实并行调用，并发未验证；没有结束或重启 Creo，未清 unknown 保护，未重放已受理作业。

## 第二轮遗留项登记（待编排方核号）

以下三项为 2026-10-31 实机与执行环境观察到的遗留问题，**未登记固定 ID，待编排方核号后另行开卡**；本节只记录事实与所需处置方向，不在本节判定根因、不改生产代码。

1. **`server.py` 子进程残留**：live 驱动结束后其派生的 MCP stdio server 子进程不退出，继续占用 stdout 管道，导致外层执行器挂起。2026-10-31 两次实机观察到。处置方向：需要 daemon 线程 / EOF 退出路径，使驱动结束即触发 server 进程退出。
2. **codex 沙箱执行管道挂起与两次 workspace routing discovery 超时**：基础设施层现象，2026-10-31 记录。**不判根因**，不与仓库内任何条目合并。
3. **N07 `illegal_dir_zero` 反例判定未过**：见 N07 段与 [FEAT-034 卡](../work-items/FEAT-034.md) / [T02 验收卡](../development/DEV051-T02-ACCEPTANCE.md)。缺的是 schema 拒绝之后的同源实测体积证据；需查驱动取体积路径后重跑全部非法例与恢复阶段。
