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
