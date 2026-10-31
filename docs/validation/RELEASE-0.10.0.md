# 0.10.0 发布记录（DEV-052 N13 集成与发布批次）

版本与条目：0.10.0；FEAT-051 圆角/倒角/拔模结果可观测性、FEAT-008/T09B 中心线计数与 `entity_ids` 发布、FEAT-014/N06 邻接折弯端拒绝语义、FEAT-035/T12 盲孔 tip 口径、FEAT-034/T02 编辑弧回显、FEAT-023/T09A 组件身份、BUG-049/N03 端点诊断、BUG-088/N11 预览场景补齐、BUG-090/N01 板厚 API 函数门控、BUG-091/N02 离线调查；另登记 BUG-092、BUG-093 两个遗留项。汇总条目 [DEV-052](../work-items/DEV-052.md)。

提交、dirty 标志、受测源码指纹：分支 `codex/dev051-feedback070`；Phase A 基线 `4b4441f`（七段第二轮实机基线 `b5dce10`、N06 终验同基线、dev_check 于 `28de56e` dirty 树执行、性能基准 `20261031T142958` 于 `b5dce10` dirty 树执行，两次 large 补跑于 `4b4441f` dirty 树）；工作区存在他人未提交内容（`docs/validation/RELEASE-0.8.5.md`、`session_activity.json`、`session_erase/` 等），**均保留未触碰**，故各证据的 `provenance.dirty=true`，受测指纹以各报告 `provenance.source_fingerprint` 与 `build/source.sha256`（第二轮记录值 `993a4380…c6ff57`）为准。合入 main 的提交、打包受测指纹与标签在 Phase B 回填：**[Phase B 回填]**。

日期与 Windows/Python/Creo/SDK/MSVC 环境：2026-10-31；Windows 11 x64 / Python 3.12.14 venv / Creo 12.4.0.0（`release_numeric=44`）/ 本机匹配 Toolkit SDK / MSVC x64；`auto_start_creo=false`，会话由用户手工启动；当日 11:30 通道失效（BUG-091 新样本）后经一次受限重启（新进程 11:46—47）继续第二轮复测。

命令及结果（单元 / 原生 / 安装 / 源码包）：

| # | 命令 | 结果 |
| --- | --- | --- |
| 1 | `python tools/dev_check.py` | exit 0，`success=true`；单元 **1710/1710 通过**（`build/unit_test_report.json`，`tests_run=1710`、`failures=0`、`errors=0`，SHA256 `7c1075af…139c0`；`build/development_check.json` SHA256 `ad0c5c34…9edf3`，`unit_tests=passed`，风格基线沿用：lint_findings 30、unformatted 16，不宣称全库严格格式通过） |
| 2 | 实机七段第二轮（编排方串行，各段 `--live --confirm-session-usable --output`，总表见[七段实机总报告](../development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)） | N08/N09/N10/N04/N11/N06 **通过**、N07 **部分通过**（`illegal_dir_zero` 反例待查）、N01 relief **部分通过**（`known_t05_boundary`）；全程无 busy/unknown，无重放已受理作业 |
| 3 | N07 T02 `build/post090_live2_20261031T115830/n07/report.json`（SHA256 `b9942a89…dde4de`） | 创建 5/5（误差 ≤5.6e-9 mm³、`arc_echo.source=native`）、编辑 3/3（rev 1→2、重载 true）通过；`illegal_dir_zero` 判定未过（`volume_missing`，schema 拒绝后同源体积证据缺失），其余 4 非法例与恢复编辑未执行 |
| 4 | N08 T09B `n08/run2/report.json`（SHA256 `a4b4d2e3…c769`） | **通过**：`section_centerline_count=1`、`revolve_axis.id=9`=`spin_centerline` 9；显式轴 id 52；无中心线负例如预期 failed；真多线夹具未提供 |
| 5 | N09 T09A `n09/run1/report.json`（SHA256 `d2fe2233…ec4ef`） | **通过**：双组件、跨作业重载（`identity_mirrors_unchanged=true`）、删除重插不误指、未知 label 拒绝；`id_renumbering` 半场景限制保持 |
| 6 | N10 T12 `n10/run1/report.json`（SHA256 `6056a097…76119`） | **通过（六例均首次执行）**：直孔 197.92033717615413（flat/overall）、沉孔 292.7477684551013、沉头 238.293495792881（均 tip/overall）、侧法向 197.92033717615777、翻向守卫拒绝+回滚+恢复 197.92033717615413、尺寸编辑 292.7477684551013→374.0864038721993（rev 2→3，dimension ID 14/13，误差 3.4e-12）；`0f1844a` tip 口径修复实机成立，未落 defect 变体 |
| 7 | N04 FEAT-051 `n04/run2/report.json`（SHA256 `714db02d…9fc2`） | **通过**：凸圆角 −38.62833848818991、凹圆角 +38.628301733198896、倒角三组 −120.00000000000364（applied=requested=3）、draft flip 双向 +17.556230361033258 / −15.41961220323752（`flip_pair_opposite_signs=true`）、缺省/显式 pull 回读（`pull_verdict=pass`）、批中途失败（首操作读数保留 `rolled_back`、尾随 `not_executed`）全过；`zero_delta` 离线专属。run1 因夹具硬编码 surface id=1（`ProModelitemInit=-23`）失败，`b5dce10` 改默认基准面构造轴后 run2 全过 |
| 8 | N06 FEAT-014 终验 `build/post090_n06_live_20261031T142644/report.json`（SHA256 `5fd12b29…fe768`） | **RUN PASSED（`passed=true`）**：`ny_first` 自由壁 42920.0→57293.61585482106 mm³、重载 true；`px_then_ny`/`px_nx_then_ny` 的 `f_ny` fast-fail `adjacent_bend_ends_rejected`（stage=before_create，附着边 197/296，revision 不变、回滚成功）；`trim_probe` 仍 `trim_ignored`；`four_walls_complete=false` |
| 9 | N01 relief `n01relief/run1/report.json`（SHA256 `cefce8ed…5d643a`） | **部分通过**：`relief_none`/`relief_rect_1x1` 自由端墙 +18025.291234 mm³、重载 true，第三墙按 `known_t05_boundary` 归类（释放几何不可观测如实记录）；`mat_*` 五案底件 succeeded（`part_thickness_mm=1.0`）、目标 `f_ny` 全部 `known_t05_boundary`；`free_rect_both_4x4` 真实建成 |
| 10 | N11 BUG-088 `n11/run1/report.json`（SHA256 `9423057e…33f17`） | **通过（含人工图像复核）**：空件缺图按记录复现（`file_check.exists=false`、`error_code=2`）；实体与盘体三阶段 JPEG 16245/16621/17794 B；钣金件 12381 B 独立写出；图像经编排方人工看图与体积仲裁核对 |
| 11 | 性能基准 `tools/test_plan_performance.py --live`（`build/post090_perf_20261031T142958/report.json`，SHA256 `20e41bbd…890a6`，run `20261031T142958_84895977`） | small 单操作中位 **22.937 s**（n=3，22.563—23.687）/ 批量 **14.406 s**（n=3，13.375—15.422）；large 单操作中位 **341.2345 s**（n=2，339.937—342.532）/ 批量 **184.4375 s**（n=2，169.937—198.938）；等价校验全过（边数 36/36、1164/1164，体积相等）。large 两次补跑（`145548` 启动预算过期、`150211` 连接就绪）均 0 用例，**large 未达 3 次重复**（N12 large 样本状态：见本记录） |
| 12 | `python tools/package.py` / `package_seeds.py` | **[Phase B 回填]** |

原生修改保存重载、参数编辑、回滚证据：N10 六例成功项 `saved_file_reloaded_and_verified=true`（含编辑 rev 2→3 后重载）；N04 七例重载 true（`batch_mid_failure` 因整作业失败为 false，属预期，失败操作回滚成功）；N06 `ny_first` 重载 true、两例 fast-fail revision 不变且回滚成功；N08/N09 重载 true（N08 重载后 rev 2）；N01 relief 自由端墙重载 true、第三墙失败回滚后体积/revision 保持。参数编辑：N10 `edit_dimension_values` 用真实 dimension ID 14/13，回读 `[3.0, 7.0, 118.0, 10.0, 8.0, 25.0, 25.0]`。

未测模块、失败用例、兼容限制：N07 其余 4 非法例与恢复编辑未执行（`illegal_dir_zero` 判定未过，见 BUG-093）；N08 真多中心线夹具缺；N09 `id_renumbering` 只能观察拒绝；N10 通孔口径、出口沉头与双端沉孔、螺纹/标准孔未验；N01/T05 四壁不支持、`relief` 材料几何不可观测、`end_trim_mm` 语义未定；N04 单位矩阵与 `zero_delta` 仅离线；N11 原案回放缺原件；N12 large 未满 3 次重复；Creo 9 无 SDK、Creo 10 未复测（BUG-090 定向编译未验）；WorkBuddy 未执行；并发未验证（无真实并行调用）。

源码包及种子包 SHA256（文件名与完整哈希，写入 Release body）：**[Phase B 回填]**

发布候选验收结论：按上表范围通过（N07 反例与 N01 材料场景按实际状态披露，不改判）；开放项随版本说明披露。**[Phase B 回填：打包与解压检查结论]**

合入 main 的提交、版本标签及指向：**[Phase B 回填]**

GitHub Release 链接与发布状态：**[Phase B 回填]**

远端附件与 SHA256 核对结果（body 记载与远端附件逐项一致）：**[Phase B 回填]**

逐 ID 状态核对（候选态；发布后回填最后一列）：

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-052 | 本批交付（N01—N13 集成） | 0.10.0 | N13 发布流程由 Phase B 收尾 | DEV-052 | BACKLOG | RELEASE_NOTES_0.10.0 | DEVELOPMENT | （发布后回填） |
| FEAT-051 | 已交付（run2 七夹具实机通过） | 0.10.0 | `zero_delta` 离线专属；单位矩阵仅离线 | FEAT-051 | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-035/T12 | 已交付（tip 口径，六例实机通过） | 0.10.0 | 通孔口径、出口沉头/双端沉孔、螺纹孔 | FEAT-035 | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-034/T02 | 已交付（创建 5/5+编辑 3/3 实机） | 0.10.0 | `illegal_dir_zero` 反例待查（BUG-093）、恢复编辑未执行 | FEAT-034 | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-008/T09B | 已交付（entity_ids 与计数实机通过） | 0.10.0 | 真多中心线夹具未验；FEAT-008 其余范围开放 | FEAT-008 | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-023/T09A | 已交付（组件身份四例实机通过） | 0.10.0 | `id_renumbering` 半场景；jobs 日志/体量议题 | FEAT-023 | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-014/N06 | 有界能力已交付（adjacent_bend_ends 创建前拒绝） | 0.10.0 | 四壁/角部、relief 材料几何、end_trim_mm 语义 | FEAT-014 | BACKLOG | 同上 | 同上 | 同上 |
| BUG-049/N03 | 诊断子项已交付（max_endpoint_gap_mm 等） | 0.10.0 | 原件缺失、原案回放与内核容差未定 | BUG-049 | BACKLOG | 同上 | 同上 | 同上 |
| BUG-088/N11 | 文件级定因、图像复核通过 | 0.10.0 | I/O 根因未定（保持观察）；原案回放未执行 | BUG-088 | BACKLOG | 同上 | 同上 | 同上 |
| BUG-090/N01 | 离线修复交付（函数门控+统一实读回退） | 0.10.0 | Creo 10 定向编译与实机未验 | BUG-090 | BACKLOG | 同上 | 同上 | 同上 |
| BUG-091/N02 | 调查交付（时间线/缺证清单） | 0.10.0 | 根因未定；两次通道死亡新样本待取证 | BUG-091 | BACKLOG | 同上 | 同上 | 同上 |
| BUG-092 | 待处理（本轮新登记） | 未排期 | 子进程残留修复与驱动复验 | BUG-092 | BACKLOG | 同上 | 同上 | 同上 |
| BUG-093 | 待查（本轮新登记） | 未排期 | 拒绝后同源体积证据路径核对与反例复跑 | BUG-093 | BACKLOG | 同上 | 同上 | 同上 |

相对上一正式包核对（上一版本：0.9.0）：

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| native/third_party 原字节（含 json.hpp、第三方许可） | 未变 | 未变 | 无注册影响（`git diff v0.9.0..HEAD -- native/third_party/` 为空） |
| 回调指纹（sha256-repo-lf-v1） | `9d2c9641d695365f31476b0b9643aabc34ab6f869d3fc95361b4804ab0ecfcb8`（0.9.0 未留值；按同算法对 `v0.9.0` 树同输入重算） | `9d2c9641d695365f31476b0b9643aabc34ab6f869d3fc95361b4804ab0ecfcb8`（实测，与 `build/blend_sync_build.json` 一致） | 未变（loader 指纹 `de87b1457d7ca677a17c583136b2696406c22b5a221f742907c57d7bca4eab03` 亦未变，generation_key `695fdd07…` 保持；本轮 native 变更在 advanced.cpp/generic.cpp/sketch_edit.cpp，属 worker 侧） |
| loader DLL SHA256 | `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9`（DLL 生成于 2026-10-21，早于 0.8.5/0.9.0 发布，0.9.0 记录“未变”） | `9ea544642a02dca2fdedb2d7b198d546f1448c106985d84e0898261a64d386c9`（实测，与构建缓存一致） | 未变 |
| callback DLL SHA256 | `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662`（同上） | `71b1093a77c51aa09cbda000afe11e5fcb40227aff9f67b7f81a4cd33a447662`（实测，与构建缓存一致） | 未变 |
| worker SHA256 | 变更（0.9.0 未留哈希） | 变更：`42cbfc08aa16d7c9afed4262d3f13750146a16cf68e35e608e06611171230a77`（2026-10-31 14:26 构建，戳记 `build/source.sha256`=`993a4380…c6ff57` 与当前源码一致） | 需 `setup.ps1` 或 `bridge.py build` 重建执行器；本批 `tools/generate_constants.py` 增函数声明探测（BUG-090），影响生成 `constants.inc`（worker 侧） |
| protk.dat / 注册表路径 | 未变 | 未变 | 无（`setup.ps1`、`config.example.json`、`client-config.example.json` 的 `git diff v0.9.0..HEAD` 为空） |
| 实际注册影响 | — | — | 实测确认：loader/callback DLL 与注册路径均未变，无需重新注册；worker 变更，升级时重建执行器并重启 MCP 服务即可 |
