# DEV-051 T13 验收卡：装配自包含打包（FEAT-031）

日期：2026-10-29。阶段：**离线受限实现完成；实机两件装配导出失败（组件身份无法解析，`complete=false`），回导未完成，整项不通过**。工作区 `E:\Projects\MCP_CREO_MechDog`，分支 `codex/dev051-feedback070`；依赖 T12 提交 `b320273`（T11 基线 `e152655`），实现提交为本卡所在提交。并发会话的未提交文件与本机运行数据保持原样，工作区 `dirty=true`。

## 交付契约

- `creo_export_model(format="native_bundle")` 是显式只读导出，只允许已登记的 assembly。默认 `step` 和现有 `step/stl/iges/jpeg/pdf` 分支与返回行为不变。原生侧只标记该导出操作、获取只读巡检；Python 在同一 Toolkit 锁内、终态发布前建立产物，不调用保存、再生或模型修改接口。`generic_bridge.py` 的只读成功分支不增加 `revision`。
- 源集合仅为已拥有模型的 `models/<id>/output` 下，根 `part_file` 指向的 `.asm.N` 及巡检可识别组件名对应的最高版本 `.prt.N`/`.asm.N`。名称限制 `[a-z][a-z0-9_]{0,30}`，不跟随目录/文件链接，不接受外部绝对路径；复制后的文件使用同名、去版本号的相对路径，与 manifest 一起放在本次 `jobs/<job>/output/native_bundle/`。
- `manifest.json` 含 `schema=1`、相对 `root`、`complete`、每文件相对路径/状态/字节数/SHA256、`unresolved_references` 和总字节。缺件标 `missing`，未知身份/未取得嵌套子级列表标不完整；绝不把不完整清单报告为可自包含打开。只读源件无需写权限。上限 128 个原生文件、512 MiB 文件内容、32 KiB manifest、32 层引用；超限明确失败。
- 本次 job 目录唯一；若 `native_bundle` 已存在则拒绝覆盖。复制/哈希/写 manifest 失败仅删除刚创建的本次 bundle 子目录，保留同 job 其他文件、模型源件和其他 job。失败结果沿用只读任务的 ready/revision 不变处理。
- 现有建模准入不支持插入嵌套装配；若会话中有嵌套装配而巡检未提供 `components` 子列表，清单标 `nested_closure_unknown`，`complete=false`。离线夹具证明给定完整子列表时递归闭包正确；真实嵌套装配闭包取得与新目录打开仍待实机，不宣称已自包含交付。

## 实际修改文件

`src/creo_mechdog/assembly_bundle.py` 新增拥有源件的收集、复制、哈希与清理；`src/creo_mechdog/schema.py`、`server.py` 增加显式格式；`generic_bridge.py` 在只读导出边界接入并将失败转成任务失败；`native/generic.cpp` 单独分支避免五种旧格式被解释；`native/advanced.cpp` 补组件类型及缺件节点供清单判断；`tests/unit/test_assembly_bundle.py`、`tools/test_assembly_bundle.py` 提供离线夹具和唯一报告目录；`docs/work-items/FEAT-031.md` 仅追加本阶段。没有更改 `version.py`、公共台账、并发会话文件或生成物。

## 离线证据

环境：Windows x64、PowerShell、`.venv` Python 3.12、Creo 12.4 匹配 Toolkit SDK、MSVC x64；仅离线编译，不启动或连接 Creo/MCP，也不提交 Toolkit 作业。

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe bridge.py build` | exit 0，重新生成 `build/creo_worker.exe`；不能证明装配可从新目录打开 |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_assembly_bundle -v` | 6/6 OK |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_assembly_bundle tests.unit.test_assembly_pipeline_requests tests.unit.test_assembly_pose tests.unit.test_model_registry tests.unit.test_session_assembly -q` | 修改缺件分支前 67/67 OK；缺件分支与嵌套夹具完成后由集成人以 `test_assembly_bundle` 6/6、`test_driver_inspect_contract`+`test_model_queries`+`test_native_countersink` 30/30 复核通过 |
| `.venv\Scripts\python.exe tools\test_assembly_bundle.py` | 提交前驱动 5/5 OK，报告 `build/assembly_bundle/20261029T102117_a768600f/report.json`，SHA256 `eaf7c5a8426aaa01f72849784ccd218f559d9745755bdf5fc7fbc0a20a25f827`；集成人在最终源码上复跑得 `build/assembly_bundle/20261029T104409_f403612f/report.json`，SHA256 `63791afe25bae6e0c2e19ef903b92de9255bb7d6d0d817845d673867ce61c6f6`，`passed=true` |
| `ruff format/check`（六个 Python 文件）、`clang-format --dry-run --Werror`（两份原生文件） | 通过；先格式化再核对，旧五种格式分支仅被外层条件包裹 |

受测身份：提交前 `b320273` + 本任务未提交改动，`dirty=true`；提交后专项报告记录实现提交和 `source_fingerprint`。驱动指纹为所有已跟踪 Python/native 源码加本任务新测试/驱动的 CRLF 归一化 SHA256 清单哈希。共同要求的最后全量 `unittest discover -s tests` 与 `tools/dev_check.py` 在集成人窗口执行时被本机安全策略拦截（返回 guarded_live 报告，非测试失败），因此**本卡未取得本任务源码的整库通过数**；T10 集成阶段必须以最新集成源码重跑并通过后才能把本版记为可发布。

源码层面只读核对：`server.py` 以 `readonly=True` 提交；`generic_bridge.py` 对该格式要求 assembly，且只读成功分支只登记 `last_query_at`、不执行 `model["revision"] += 1`；`native/generic.cpp` 的 bundle 分支没有 `ProMdlSave`、`ProMdlnameBackup`、`ProSolidRegenerate`；`assembly_bundle.py` 只读源文件并向本 job 输出目录写文件。夹具还比较了全部源文件前后哈希和 revision 值。

## 未测、错误与交接

原始错误：无保留失败；新增的原生代码初次 `clang-format --dry-run --Werror` 报格式违规，执行 `.venv\Scripts\clang-format.exe -i` 后通过。实机 job/model/revision、组件实际解析、几何、保存重载/回滚：**不适用，未运行**。待验单层与嵌套装配新目录打开、缺失/外部/只读源件行为、引用快照/哈希、revision、模型源件不变及保存重载。现有限制是嵌套子级巡检没有可证明的完整列表，故这类包明确 `complete=false`；若需要完整嵌套交付，先补原生递归引用证据与文件来源核对，再扩展闭包。

给集成人：冲突文件 `native/generic.cpp`（T12/T09B 共用）、`native/advanced.cpp`（T11 共用）、`src/creo_mechdog/schema.py`、`server.py`、`generic_bridge.py`。接口只增加 `format=native_bundle` 和结果 `native_bundle{directory,manifest,complete,files,missing,sha256}`；清单内部不含本机绝对路径，结果中的产物位置是本机 job 路径。T01 可收口工具描述和能力边界；T10 才负责版本/发布。本次不改版本、不合 main、不 push、不发布。

## 2026-10-29 实机：两件装配导出失败（组件身份无法解析），回导未完成

环境：手动打开的 Creo 12.4.0.0、`auto_start_creo=false`、唯一 dev 服务 0.8.4、`ready/connected=true`；新建两个零件（50×40×10、20×20×5）与一个两组件装配（`part_alpha` 固定、`part_beta` 平移 [100,0,0]），未重提作业，挂起预算 180 s。

```text
.\.venv\Scripts\python.exe tools\test_assembly_bundle.py --live --confirm-session-usable
```

报告：`build/assembly_bundle/20261029T231622_7cbf542e/report.json`，SHA256 `8a50e8b0c3d425f9e4377693bd9b64065f4c8b43e708efc8cbc3619e85b00105`，退出码 1。

| 步骤 | 实测 |
| --- | --- |
| 装配 | `c319d95a5e0c469786e8bc5754b7ec7f`（job `fec6a06a17f54953905512d39cbea214`，rev 1），两组件 `feature_id` 40/43，`transform` 与 `initial_transform` 均 4×4 单位阵 + 平移，标签 `part_alpha`/`part_beta` 正确 |
| 导出 job | `0856a754151544f08bbd489d7d7398be` 成功，结果 `native_bundle.directory=jobs/0856…/output/native_bundle`、`complete=false`、`files=1`、`missing=2` |
| 清单 | `schema=1`、`root=t13_asm_ddb9e3.asm`（80 812 B，sha256 `789e6c05…32035`）、`unresolved_references=[{name:null,status:missing,reason:unresolved_identity} ×2]` |
| 产物 | 只有 `t13_asm_ddb9e3.asm`，**两个组件源件未入包** |
| 回导 | 复制 bundle 到 `build/assembly_bundle/<run>/reimport/` 后 `creo_open_file` 失败：`SESSION_NAME_CONFLICT: a assembly model with this name is already in the Creo session`（`failed_stage=open_file_session_check`、`toolkit_code=-1`），未取得组件数/变换回读 |

定因（本次可确定的部分）：装配作业号前 16 位是 `fec6a06a17f54953`，与磁盘上的副本名 `c_fec6a06a17f54953_0.prt.1` / `_1.prt.1` 完全对应（符合 `c_<token>_<n>` 契约）。但原生巡检回给 `model_name` 的是 `\u25a9C_FEC6A06A17F549530001` / `\u25a9C_FEC6A06A17F549530002`：带前导 U+25A9、全大写、后缀是 `0001/0002` 而不是 `_0/_1`。`assembly_bundle._references` 用 `[a-z][a-z0-9_]{0,30}` 校验失败，两条引用记为 `unresolved_identity`，`complete=false`。

未做的判断与动作：

- **没有**为通过本项放宽校验或猜测名字映射。`\u25a9` 极可能是原生 `ProName` 缓冲区读出的非名称字符，而" `0001` 对 `_0`"的差异说明巡检名与磁盘名不是同一字符串；在没有原生名称来源证据前做字符串修补会把"不完整包"伪装成"自包含"，正是本卡禁止的行为。
- **没有**执行 `creo_erase_session_models`。回导必须在同名装配已离开会话后才能打开；擦除会话模型属于会话级动作，本轮未获授权范围，故只记录冲突原文。
- 结论：**FEAT-031 的 native_bundle 在本机真实装配上不可用**（`complete=false`，缺 2 个源件），与卡面"绝不把不完整清单报告为可自包含打开"一致——拒绝是正确行为，但功能目标未达成。T13 实机不通过。

下一步（需另排期）：

1. 原生侧确认 `model_name` 的真实来源（`ProMdlNameGet` 缓冲区初始化/长度、是否需要 `ProMdlFileNameGet`），让巡检名与磁盘文件名同源；用 `tool dump` 或一次只读探针确认前导 U+25A9 是否未初始化内存。
2. 修好后重跑本驱动，再补 `creo_erase_session_models`（或另开会话）完成"新目录打开 + 组件数/变换/标签"回读。
3. 未测：嵌套装配闭包、缺件/外部/只读源件、revision 不变与保存重载、Creo 9/10。
