# DEV-051 T06 验收卡：倾斜草图顺序对照（BUG-064/087，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线夹具就绪 / 原案未验证 / 污染假说未复现**。工作区 `E:/Projects/MCP_CREO_MechDog`，分支 `codex/dev051-feedback070`。本次无生产代码变更、无 Creo 连接或 Toolkit 作业；不把历史六例通过记为本轮实机结果。

## 依赖、材料与范围

依赖提交 `26b24c6c444ce6d7a12f57cf0edb303b4cc8abde`（含 T05）；已读 AGENTS、0.7.0 两份计划 T06/共同交接契约、BUG-064/087、DEV051-T03/T04/T05 验收卡。项目内与 `C:/Users/Administrator/Downloads/0.7.0` 只找到四份反馈 Markdown 和既有 DEV-049 矩形驱动；报告声称的 `scripts/sketchgen.py`、`sketch_entities.json`、原星形 30 段请求、原 PRT、对应 job/native 文件均未找到。仓库其他 PRT 与运行 job 不能被证实为该原案，未冒用。原案重放状态为 `not_possible_missing_attachments`。

替代案例明确命名 `regular_30gon_30_independent_lines_r5mm`：半径 5 mm 的正 30 边形，各边独立 line，闭合无缝。独立面积基准由 30 个等腰三角形计算：`30/2 × 5² × sin(2π/30) = 77.96688405665974 mm²`；单测另用鞋带公式交叉核对。该面积**不**取自反馈报告的 `15.57317477042468 mm²`，两者不是同一截面。

## 驱动与实机待验判据

新增 `tools/test_tilted_sketch_lifecycle.py` 与 `tests/unit/test_tilted_sketch_lifecycle.py`。默认仅生成带唯一模型名的 32 行输入矩阵（4 顺序 × 2 标注策略 × 2 引用方式 × 2 第二参照目标），每行都要求独立 `creo_new_part`；不实例化 MCP，`--live` 和 `--confirm-session-usable` 均立即拒绝。四顺序为矩形→30线、30线→矩形、同件新倾斜面矩形、全新件矩形。ID=911/912 仅是离线校验占位值；实机必须按新件实际 datum_planes 的法向、原点和标签解析 ID，绝不能照搬。第二参照 `available/unavailable_candidate` 是待检目标，离线无法强制 Toolkit 选取或缺失第二条参照；实机必须以原生参考线几何/数量核实并在不满足目标时记“未覆盖”。

实机每步需保留输入、job/model、revision 基线及终态；检查真实支撑面、U/V/N、参考线几何/数量、solve/section 码、轮廓面积、保存重载及几何。自然合法失败时先确认真实回滚、模型/revision/别名与基线，再提交同面矩形；若没有这种失败，**不**执行该分支，记录“污染假说未复现”。busy、断连、unknown、超时或 GUI 不可操作时停止新提交，已受理作业只轮询，不重提。不能用替代 30 边形通过关闭原星形案；无第二参照分支的可构造性仍待实机确认。

## 实测身份、命令与结果

- 受测提交（运行时 HEAD）：`26b24c6c444ce6d7a12f57cf0edb303b4cc8abde`；dirty=true，包含本 T06 新文件及另一个会话未提交文件；驱动报告的 `source_fingerprint=0c05b4ceef515ad439c051d2005520f6bc2ae2f561e22323d0fb05cc75e94282`。算法为已跟踪 Python/native 源码加本任务两个新增文件的 CRLF 归一化 SHA256 清单哈希。
- 环境：Windows x64 / PowerShell / `.venv` Python 3.12.14。没有 build 原生源码（本任务无原生改动）。
- `.venv\Scripts\python.exe -m unittest tests.unit.test_tilted_sketch_lifecycle -v`：3 项 OK；首轮矩阵模型名重复报 `ValueError: duplicate model name`，修正编码后复跑通过。
- `.venv\Scripts\python.exe tools\test_tilted_sketch_lifecycle.py`：exit 0，32 行离线输入验证通过；报告 `build/tilted_sketch_lifecycle/ecda2ed1/report.json`，SHA256 `1c8263e71e54756c5952f1dccfbcadd7416dd462152eabf91dd754403edff70d`。旧草稿报告 `b1bf4527` 是格式化前的不同指纹，不作为最终证据。
- `.venv\Scripts\python.exe -m unittest discover -s tests`：exit 0，1229 项 OK（256.841 s）；输出含测试中的 `Creo startup failed (ValueError)` 模拟/拒绝路径警告及 loader DLL 临时构建消息，未取得实机连接或建模结果。
- `.venv\Scripts\python.exe tools\dev_check.py`：首次 exit 1，仅新增文件格式问题（`I001` 与两个 formatter 报告）；已用 Ruff 修正。复跑 exit 0、`success=true`、`unit_tests=passed`、`regressions=[]`，`style_summary` 中 30 lint / 16 unformatted 均为存量基线；`checked_source_sha256=0f8f6f622c2caf688ca69565f2221154222be075458a4102842f47a34e722744`。报告 `build/development_check.json`，SHA256 `ff965fecd13827f1a5767b919ec84c6acd89ab0b13307c498eaf62f5f75f5b89`。未跳过检查、未改基线。

实机 job/model/revision、几何与保存重载/回滚：**不适用（未连接 Creo）**。无合法自然失败与真实回滚，污染假说未复现。下一步仅在另行指派实机、会话和 BUG-001 条件确认后由唯一 dev 服务串行执行；原 30 段材料取得后独立回放。生产路径若需改动，先实机复现新根因，并回归 BUG-087 六例与 Right ±Z。

## 给集成人

仅精确提交本卡、两份新增 Python 文件、BUG-064/087 两卡的追加段落。未触及共享 `native/generic.cpp`、schema、版本、主台账、两份计划或另一个会话文件；接口无变化。该矩阵是离线准备，实机执行器和第二参照缺失构型仍待后续实现/核实。

提交后追溯：实现提交 `6a09f00b50e9bcce5f4a68d936c66701a8041654`；上述两份报告均在该提交前、相同受测源码内容上运行，因此报告内的 `commit` 字段仍为依赖提交 `26b24c6`，`dirty=true`。本段仅补充提交身份，不把离线结果升级为实机验收。工作区仍有另一会话与本机运行数据的未提交文件，未暂存或改写。

## 实机阶段（2026-10-29，Creo 12.4.0.0）

用户 2026-10-29 授权直接操作 Creo；会话由用户手动打开，`auto_start_creo=false`，驱动未启动/关闭 Creo、未注入故障、未清保护。在同一会话串行执行 `tools\test_t06_native.py --live --confirm-session-usable`，**exit 0**，报告 `build/t06_native_acceptance.json`。

- `native_acceptance=passed`，`toolkit_serial=true`，`pending_native_acceptance=[]`。
- 9 个独立夹具全部通过：7 个 add（含 2/5/10 环与倾斜面矩形构型）+ 2 个 cut；每个都 `saved_file_reloaded_and_verified=true`。示例（2 圆 add）：期望 452.3893421169302 mm³，实测 452.389346693283 mm³，`protrusion` +1、`datum_plane` +1，model `89246772c063468cb8fe4cc615cff4f7`。
- `failure_recovery`：一次同面矩形 cut 真实失败（`Extrude cut removes no material…`，原生 section 5 闭合环/0 开口），`rollback_succeeded=true`，revision 未推进。
- `external_case_replay=not_applicable_missing_attachments`：原 30 段/星形材料仍未提供，**原案不因此关闭**。
- 未测：真实第二参照选择（夹具只覆盖独立新件的顺序模式）、`dir` 交互、WorkBuddy、Creo 9/10。

给集成人：本段只追加卡与实机记录，不改生产代码。
