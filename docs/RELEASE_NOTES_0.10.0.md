# MCP_CREO_MechDog 0.10.0

0.10.0 交付 [DEV-052](work-items/DEV-052.md) 的 N01—N13 分窗批次（0.9.0 之后的七份 0.8.x 反馈接续、离线修复与两轮实机复测）。按版本规则属 **MINOR**，依据是新增公开结果字段与拒绝语义：

- [FEAT-051](work-items/FEAT-051.md)：`creo_round` / `creo_chamfer` / `creo_draft` 逐操作体积差（`volume_before_mm3`/`volume_after_mm3`/`material_delta_mm3`/`material_measurement`）与方向、引用应用回报（`draft_geometry`、`reference_application`）；
- [FEAT-008](work-items/FEAT-008.md)：草图结果发布 `entity_ids`（可与 `revolve_axis.id` 对账）；
- [FEAT-014](work-items/FEAT-014.md)：折边邻接折弯端的明确拒绝语义（`failure_reason=adjacent_bend_ends`，创建前拒绝）。

同时含行为修复：[FEAT-035](work-items/FEAT-035.md)/T12 盲孔 `depth` 改为钻尖（tip）口径（对齐冻结契约的 overall 语义）、[FEAT-034](work-items/FEAT-034.md)/T02 编辑后弧回显修复（`named_ids` 再快照）、[FEAT-008](work-items/FEAT-008.md)/T09B 中心线按用户线计数、[BUG-049](work-items/BUG-049.md)/N03 端点诊断可观测性（`max_endpoint_gap_mm` 等）。无新增公开工具，公开工具仍为 **94** 个。0.9.0 及更早的提交、标签、Release 和附件均保持原样。

## 升级必读

- **圆角/倒角/拔模结果可观测（FEAT-051）**：`round` / `chamfer` / `draft` 的每个已执行操作记录（`result.operations[]`）新增实测材料块与读回块；`not_executed` 与旧版遗留记录不带任何读数（不伪造）。Python 侧纯透传不推导，compact/full 一致。

  | 字段 | 语义 |
  | --- | --- |
  | `volume_before_mm3` / `volume_after_mm3` | number \| null，操作前/后模型体积（mm³，按长度单位比例³换算）；任一未建立为 null |
  | `material_delta_mm3` | number \| null，= after − before，两端均非 null 才非 null；**零是合法报告值** |
  | `material_measurement` | `{status, before_query_code, after_query_code}`；`status` ∈ `measured` / `unknown` / `not_applicable`（无实体），查询码为原始 ProError（未执行侧为 null） |
  | `draft_geometry`（仅 draft，特征树读回） | `{source, query_code, neutral_plane, pull_direction, flip, angle_deg, pull_vector}`；不能回读的字段为 null，`pull_vector` 只给引用几何自身可证向量（平面法向/轴向），不做 flip 合成推导 |
  | `reference_application` | `{requested_set_count, applied_set_count, source, query_code}`；应用数只由创建后特征树证实（round/chamfer 数 `PRO_E_RNDCH_SET`、draft 数表面集合指令），不能证实时 null |

  本机实机（Creo 12.4，run2 七夹具）：凸圆角 −38.62833848818991 mm³、凹圆角 +38.628301733198896 mm³（解析 ±38.628330588459306）、三组 face-pair 倒角 −120.00000000000364 mm³（applied=requested=3）；拔模 flip=false **+17.556230361033258**、flip=true **−15.41961220323752** mm³（解析 −15.419612203499526 / +17.556230360737217，符号相反、幅度精确），`pull_vector` 缺省 pull 回读中性面法向 `[0,0,1]`、显式 pull 回读轴向 `[0,0,1]`。外部 0.8.5 报告"拔模取反静默加料 +17.564 mm³ 而照样 succeeded"的形态，现在由带符号 `material_delta_mm3` 自证方向。
- **草图结果 `entity_ids`（FEAT-008/T09B）**：草图操作结果发布 `entity_ids`（含 `spin_centerline` 等实体 id），`revolve_axis.id` 可与所画中心线实体 id 对账（本机 N08 实机：`revolve_axis.id=9` = `sketch_entity_ids.spin_centerline=9`，`id_source={entity:"spin_centerline", sketch_entity_id:9}`）；`section_centerline_count` 改为按草图别名记录只计**用户中心线**（此前一条用户线被系统投影参考计成 3），真实多线仍 `id=null` 不猜第一条。
- **折边邻接折弯端明确拒绝（FEAT-014/N06）**：`creo_sheetmetal_flange` 的附着边**端部与既有折弯相邻**时，现在在**创建前**拒绝（fast-fail）：`failure_reason=adjacent_bend_ends`，并逐端给出 `flange_failure_evidence`（邻接弧边、半径、退让界限、折弯面等）；revision 不变、无残留特征。自由边与首壁行为不变。**四壁仍不支持**：`four_walls_complete=false`，corner relief / miter 未实现，`end_trim_mm` 两轮实机实测为 `trim_ignored`、不能用于角部让位（语义仍未定，属诊断参数）。本机 N06 终验（RUN PASSED）：`ny_first` 自由壁建成（42920.0 → 57293.61585482106 mm³、重载 true）；`px_then_ny` / `px_nx_then_ny` 的 `f_ny` 均 fast-fail `adjacent_bend_ends_rejected`（附着边 197 / 296，端部邻接弧边半径 2.54 mm，退让界限 7.081 mm，revision 2→2 / 3→3 不变、回滚成功）。
- **盲孔 `depth` 口径变更（FEAT-035/T12）**：custom 孔（沉孔/沉头）的盲孔 `depth` 原先按"到沉台/座面（shoulder）"写入（`PRO_HLE_DEP_SHOULDER_DIM_SCHEME`），118° 钻尖再向下超出一个钻尖高度；本版改为**量到钻尖顶点**（`PRO_HLE_DEP_TIP_DIM_SCHEME`，overall 口径，与冻结契约一致）。**对既有模型语义的影响**：旧版建出的 custom 盲孔总深 = `depth` + 钻尖高（118° 约 0.3×基本径），同输入在本版重放会得到更浅的孔（总深恰为 `depth`、全径段止于锥底上方一个钻尖高），去料体积随之变化——这是口径修正，不是回归；需要旧几何的既有模型不被改动，但同请求重放结果不再相同。直孔（straight）分支本就是 overall 口径，不受影响。判定侧将"到肩/座面起量"读数列为永不通过的 defect 形态（`defect_till_shoulder_below_tip` / `defect_seat_measured_drilldepth`）。本机 N10 六例实机全过：直孔 197.92033717615413、沉孔 292.7477684551013、沉头 238.293495792881 mm³（均 `contract_*_overall`，无 defect 形态）、侧面法向孔 197.92033717615777、翻向守卫拒绝+回滚+恢复孔 197.92033717615413、真实 dimension ID 编辑 292.7477684551013 → 374.0864038721993（rev 2→3、误差 3.4e-12、重载 true）。

## 行为修复

- **T02 编辑后弧回显（FEAT-034/N07）**：`named_ids` 原在就地重建循环前快照，方向翻转替换弧实体后回显用已删除 id 查询、退化为 `source=unknown`/`query_code=-2`；改为循环后再快照。本机第二轮实机 3 编辑例回显 native、query_code=0、rev 1→2、重载 true。
- **T09B 中心线计数（FEAT-008/N08）**：拷贝截面上系统投影参考不再报 projection，单靠投影过滤把一条用户线计成 3；改为按草图别名记录（`entity_ids` 中 type=centerline 的实体）分类用户中心线，探针只作回退。本机实机 `section_centerline_count=1` 与 `spin_centerline` id 对账通过。
- **N05/N06 折边失败取证传播**：失败路径的 `flange_failure_evidence` 原先挂在扁平块上，复测轮读到 null；改为嵌套挂到 `operations[]` 下，原生日志取证行（`stage`/`feature_status`/邻接面型等）进入报告汇总。
- **驱动判定补严（N07—N10/N12 离线预检）**：实机驱动不再以体积或成功终态单独判过——要求 job succeeded ∧ 实测体积对上独立 oracle ∧ 原生回显 ∧ `result.saved_file_reloaded_and_verified is True`；重载标志只认 `result` 块；T12 以 tip 口径 oracle 判定并把备选算式列为 defect；N09 组件镜像比较改 canonical sort key（修复 `dict` 排序 TypeError）；N04 取 revision 改读 job manifest 顶层（缺省清晰报错而非 KeyError）；N05 选边改相对基线板 bbox 并排除 rim 边（`driver_edge_selection_error` 判驱动错而非 Creo 失败）。N12 基准驱动补 30 项判定单元与等价口径。
- **种子包校验摘要随版回填（修复 0.9.0 遗留缺陷）**：0.9.0 发布时未把种子包 SHA256 回填进 `seeds.py` 的 `expected_digest`（仍指向 0.8.5 包），导致其已发布源码包经 `creo_install_seed_library` 按 archive 安装时拒绝配套的 0.9.0 种子包；本版重建 0.10.0 种子包并将 `expected_digest` 回填为该包实测 SHA256（校验逻辑不变，9 枚种子原字节不变，两份 `seed_manifest.json` 的 `compatible_server_version` 随版 0.10.0）。

## 诊断增强

- **BUG-049/N03 端点诊断**：`profile` 投影新增 `max_endpoint_gap_mm` 与有界 `near_tolerance_pairs{total, truncated, sample≤20}`，弧回显两侧补 `center_uv`/`radius_mm`；原生 `native_section` 新增 `max_cluster_spread_mm`、`max_endpoint_gap_mm` 与有界 `open_end_samples`（≤20），切除失败消息在 `open_ends>0` 时附最大开端 gap。缺原生查询保持 null，不填成功。**内核焊接容差仍未知**，不做宣称。
- **BUG-088/N11 预览场景补齐**：驱动补空件（`creo_new_part` 零操作）与钣金对照覆盖；空件缺图按记录复现（`raster=0` 后 `output_file=-4`、`file_check.exists=false`、`error_code=2`），同模型续建实体即写出图像；钣金件在新建钣金模型上成功并独立写出 12381 B 图像；全场景图像经人工看图与体积仲裁核对通过。

## 本轮验证范围

- **单元/语言检查**：`tools/dev_check.py` exit 0（`success=true`），单元 **1710/1710 通过**（`build/unit_test_report.json`，2026-10-31）；风格基线沿用，不宣称全库严格格式通过。
- **实机七段第二轮（编排方串行，Creo 12.4.0.0）**：N08 T09B 通过、N09 T09A 通过、N10 T12 六例通过、N04 FEAT-051 通过（run2 七夹具，run1 夹具硬编码 surface id 失败后修复重跑）、N11 BUG-088 通过（含人工图像复核）、N06 FEAT-014 通过（已知边界按设计生效）；N07 T02 部分通过（创建 5/5 + 编辑 3/3 通过，`illegal_dir_zero` 反例判定未过待查）；N01 relief 部分通过（第三壁按 `known_t05_boundary` 归类，释放几何不可观测如实记录）。逐段 job/model/revision、几何与 SHA256 见[七段实机总报告](development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)。
- **N06 终验**：`build/post090_n06_live_20261031T142644/report.json` `passed=true`（详见升级必读）。
- **性能基准（N12）**：small 单操作中位 22.937 s / 批量 14.406 s（n=3）；large 单操作中位 341.2345 s / 批量 184.4375 s，等价校验全过（边数 36/36、1164/1164，体积相等）；large 样本状态见发布记录。
- **N10 六例、N04 矩阵**：数值见升级必读各条。

## 仍开放与未测

- Creo 9 / Creo 10 的 SDK 编译与建模运行时均未验（本机无 Creo 9/10 SDK）；[BUG-090](work-items/BUG-090.md) 的函数门控离线修复已交付，**Creo 10 定向编译未验**，保持开放。
- [BUG-091](work-items/BUG-091.md) 根因未定，2026-10-31 两次通道死亡/连接失效新样本（详见 BUG-091 卡与七段总报告）；不重开 BUG-001/BUG-085，不清 unknown 保护。
- [BUG-049](work-items/BUG-049.md) 原件（`gear10.json` 等）缺失，替代夹具不得当作原案回放通过；内核焊接容差未定。
- T05/T11：四壁不支持（`four_walls_complete=false`），第三壁/角部内部机理未定，`relief` 材料端释放几何不可观测，`end_trim_mm` 语义未定（`trim_ignored`）。
- N07 `illegal_dir_zero` 非法编辑反例判定未过（schema 拒绝后同源体积证据缺失），其余 4 非法例与恢复编辑未执行，待查（[BUG-093](work-items/BUG-093.md)）。
- [BUG-088](work-items/BUG-088.md) 空件缺图的 I/O 根因未定（文件级判别量已定），原案回放缺原件未执行，保持观察。
- N12 large 样本状态见发布记录。
- N08 真多中心线（真多用户线）外部夹具未提供；N09 `id_renumbering` 半场景限制保持；N04 `zero_delta` 为离线专属、单位矩阵 mm/in/混合/未知仅离线覆盖。
- 全程无真实并行调用，**并发未验证**；WorkBuddy 黑盒未执行。

## 环境

Windows x64 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 Toolkit SDK / MSVC x64 / Python 3.12。

详细命令、源码身份与发布核验见 [0.10.0 发布记录](validation/RELEASE-0.10.0.md)。
