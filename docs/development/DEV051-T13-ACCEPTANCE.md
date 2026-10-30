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

## 2026-10-30 离线阶段：身份链路定因与最小修复（未实机）

阶段：**离线实现与回归完成；实机两件装配导出/回导仍未重跑，整项仍不通过**。工作区 `E:\Projects\MCP_CREO_MechDog`，分支 `codex/dev051-feedback070`，基线 HEAD `f4adc99`，本阶段改动**未提交**（提交由派发方统一做），`dirty=true`。未改 `version.py`、`schema.py`、`docs/BACKLOG.md`、`docs/validation/`、钣金相关代码与驱动，未连接 MCP/Toolkit、未启动 Creo、未擦任何会话模型、未改 git index。

### 一、根因：巡检名与磁盘名是两条不同的来源（已定因，带行号）

一条组件记录的名字要同时满足两件事：身份可判定、能定位自有源件。这两件事此前各自由**不同字符串**提供，因此永远对不上。

**（1）磁盘名来源——`insert_component` 自己生成的复制名。** `native/advanced.cpp:1101-1110`：

```cpp
std::wstring token = std::filesystem::path(generic_job).filename().wstring();
wchar_t copy_text[PRO_MDLNAME_SIZE] = {};
swprintf_s(copy_text, L"c_%s_%u", token.substr(0, 16).c_str(),
           (unsigned)generated_identity_index());
...
CK(ProMdlnameCopy(child, copy_name, &copy));
```

即 `c_<job_id 前16位>_<操作序号>`。Creo 的 `ProMdlnameBackup`（`native/generic.cpp:5177`，保存阶段）按**该字符串**把组件快照写进本模型 `output/`。实测对账：

| 来源 | 值 |
| --- | --- |
| 装配作业号 | `fec6a06a17f54953905512d39cbea214` |
| 生成的复制名 | `c_fec6a06a17f54953_0` / `c_fec6a06a17f54953_1`（`generated_identity_index()`=0/1） |
| 磁盘实际文件 | `models/c319d95a5e0c469786e8bc5754b7ec7f/output/c_fec6a06a17f54953_0.prt.1`、`_1.prt.1` |

另一例：`models/072e2254ed6d4e118f870cbe44101a9f/output/c_1f809c3532ce435c_0.._4.prt.1` 对应作业 `1f809c3532ce435c8d85e931a4e24fb9` 的操作序号 0–4。**文件名与我们生成的字符串逐字相同。**

**（2）巡检名来源——另一条完全独立的 SDK 读取，且用的是废弃接口。** `native/advanced.cpp:1225-1229`（修复前为 `1213-1214`）：

```cpp
ProName name;                       // wchar_t[32]，未初始化
CK(ProMdlNameGet(child, name));     // 自 Creo 3 起废弃
...
{"model_name", utf8(name)},
```

`ProName` 是 `wchar_t[PRO_NAME_SIZE]`（32，`ProSizeConst.h:25/63`，注释为"任何**其它** Creo 名字"），而模型名的正规类型是 `ProMdlName`（`wchar_t[PRO_MDLNAME_SIZE]`，180，`ProSizeConst.h:24/59`）。SDK 头 `ProMdl.h:591-598` 明确 `ProMdlNameGet` **DEPRECATED: Since Creo 3 / SUCCESSORS: ProMdlMdlnameGet**。

这条废弃调用正是本仓库**已经定因并修过一次**的同一缺陷：`native/worker.cpp:399-405` 的 BUG-070 注释——"the deprecated ProMdlNameGet left an uninitialized ProName untouched ... and stale stack bytes surfaced as a garbled model name. The successor fills a zeroed buffer"，修复是换用 `ProMdlMdlnameGet` + 清零的 `ProMdlName`。`assembly_inspection()` 与 `constraint_reference()`（`native/advanced.cpp:1141-1142` 修复前）没有跟上那次修复。

**（3）消费端因此判定身份不可解。** `src/creo_mechdog/assembly_bundle.py:47-56`（修复前）用 `[a-z][a-z0-9_]{0,30}` 校验 `model_name` 并据此找 `<名字>.prt.N`；外来字符串校验失败 → `unresolved_identity` → `complete=false`。拒绝本身是对的（残包确实不能算自包含），但功能目标没达到。

### 二、实测到的异常形状（只记录，不作映射规则）

对 `jobs/**/inspection*.json` 全量取样：**1483 个 `model_name` 全部异常，0 个正常**，形状高度一致（不是随机栈残留）：

- 全部 23 字符，首字符恒为 **U+25A9**（UTF-8 `E2 96 A9`，原始字节已核对），其后为 ASCII 名字形字符串；
- 组件副本一律是 `C_<16位十六进制大写><4位数字>`，例如 `C_FEC6A06A17F549530001`、`C_FEC6A06A17F549530002`；
- 约束引用的 `owner` 字段（同一废弃调用）也带同一前缀，非副本模型则**名字本体不变**，例如 `U+25A9 T09_DST_20261026T20002`；
- 该值在"保存→擦除→重载"前后自比通过（`native/generic.cpp:3059` 的 `a["model_name"] != b["model_name"]` 判等，装配作业 `fec6a06a17f54953…` 成功），说明它是模型身份的确定性产物，而非未初始化内存的随机字节。

**未定因（不编映射规则）：** 该废弃入口究竟返回了什么（遗留/occurrence 显示名、还是缓冲区越界/偏移读）**无法在离线条件下证实**，需一次实机只读探针。已观测到的重拼形状（副本 `c_<16hex>_<n>` 变成 `C_<16HEX><%04d(n+1)>`，无 `_<n>` 结尾的名字原样通过）仅作现象记录，**未据此实现任何前缀裁剪、大小写折叠或后缀改写**。

### 三、最小修复：让身份与文件名出自同一字符串

不猜映射，改为让两侧引用**同一个已记录字符串**——`insert_component` 生成复制名时就把该字符串登记进组件的持久化别名记录（跨作业、跨 worker 进程可取回），打包时按 `feature_id` 取回它去定位自有源件。

| 文件 | 改动 |
| --- | --- |
| `native/advanced.cpp:1101-1110` | 复制名先落到 `std::wstring snapshot`（在 `ProMdlnameCopy` 之前捕获，因其 `ProMdlName` 入参非 const），再传给 SDK |
| `native/advanced.cpp:1128-1138` | `remember(...)` 追加 `snapshot_name` = 该字符串，随别名记录持久化 |
| `native/advanced.cpp:1141-1145` | `constraint_reference`：废弃 `ProMdlNameGet` + 未初始化 `ProName` → `ProMdlMdlnameGet` + 清零 `ProMdlName`（BUG-070 同款） |
| `native/advanced.cpp:1225-1237` | `assembly_inspection`：同上；名称读取失败改记 `missing=true`/`model_query_code`，不再 `CK` 抛掉整份巡检 |
| `src/creo_mechdog/assembly_bundle.py:36-114` | 新增 `_snapshot_identities(model)`：从持久化别名记录按 `feature_id` 取 `snapshot_name`（关联键沿用 `component_identity.py` 的 `model_identity+feature_id`）；`_references` 改用该身份定位源件，**逐字符精确匹配**，无前缀裁剪/大小写折叠/后缀改写；两条不同 `snapshot_name` 指向同一 `feature_id` 视为歧义 → `unresolved_identity` |
| `src/creo_mechdog/assembly_bundle.py:22-34` | `_latest` 增加**大小写精确**前缀核对（Windows glob 不区分大小写，此前会把不同大小写当作同一文件） |
| `src/creo_mechdog/assembly_bundle.py:127` | 根名去 `.lower()`，与文件名逐字一致 |
| `tools/test_assembly_bundle.py:200-255` | **残包不得回导**：`complete=false` 或清单有问题 → 立即记目标失败（`reimport.skipped=incomplete_bundle`），不复制、不 `creo_open_file`；只有完整包才准备新目录回导 |

保护面全部保留：目录/链接拒绝、`MAX_FILES=128`、`MAX_BYTES`、manifest 32 KiB、引用深度 32、只读源件不写回、失败只删本次新建的 bundle 子目录。缺件/身份异常/未知嵌套闭包仍一律 `complete=false`。

业务标签（`part_alpha`/`part_beta`）仍只存在于登记侧别名记录，**随包不保留**（`.prt/.asm` 原生文件不自带标签）；包内保留的是可回导的几何与引用身份，标签需由调用方按 `feature_id` 重新绑定。

### 四、回归与离线证据

新增/改造回归（`tests/unit/test_assembly_bundle.py`，9 例）：

| 用例 | 覆盖 |
| --- | --- |
| `test_unresolved_identity_never_marks_complete` | 异常身份 7 种：无记录、`▩C_ONE0001` 形状、路径名、大写名、非字符串、缺 `feature_id`、同一 `feature_id` 两个名字（歧义）——全部 `complete=false` 且 `reason=unresolved_identity` |
| `test_repeated_occurrences_share_verified_file` | 重复 occurrence 共用同一已验文件：清单只含一份 `c_one.prt`，`missing=0`，`complete=true` |
| `test_missing_and_nested_unknown_are_explicit` | 缺件 + 未知嵌套闭包 → `complete=false`，含 `nested_closure_unknown` |
| `test_read_only_source_is_copied_without_writing_back` | 只读源被复制、源字节与只读位不变 |
| `test_nested_reference_closure_when_children_are_known` | 已知子级时递归闭包正确 |
| 其余 4 例 | 哈希/相对路径/源不变、外部根拒绝、失败只清本次目录、导出格式契约 |

命令与结果（Windows x64 / PowerShell / `.venv` Python 3.12 / Creo 12.4 匹配 Toolkit SDK / MSVC x64，仅离线，不连 Creo）：

```text
.\.venv\Scripts\python.exe -m unittest tests.unit.test_assembly_bundle -v
    Ran 9 tests in 0.291s   OK

.\.venv\Scripts\python.exe -m unittest discover -s tests
    Ran 1482 tests in 279.395s   OK

.\.venv\Scripts\python.exe bridge.py build
    exit 0 -> build\creo_worker.exe

.\.venv\Scripts\python.exe tools\test_assembly_bundle.py
    Ran 9 tests ... OK
    {"report": "build\\assembly_bundle\\20261030T093807_ad9f17ff\\report.json",
     "sha256": "204baaf35137ecefd8ed27fddd81e9c3d1637402f97041f8ba0816e75babf30f",
     "passed": true}

.\.venv\Scripts\python.exe -m ruff format --check  ...  3 files already formatted
.\.venv\Scripts\python.exe -m ruff check          ...  All checks passed!
.\.venv\Scripts\clang-format.exe --dry-run --Werror native\advanced.cpp   (无输出，通过)
```

原始错误保留：本次唯一失败是首轮 6 个 `ValueError: native_bundle already exists for this job`（测试夹具对同一 job 目录重复建包，属夹具问题，改用每用例独立 job 输出目录后消除）；另有一条 `guard_live ... "status": "unknown_outcome"` 为本机安全策略的守卫产物（见 `guarded_live_*.json`），非测试失败，整套仍 `OK`。

### 五、实机回导待验步骤（本轮未执行，需另派实机阶段）

前提：唯一 dev 服务 `MCP_CREO_MechDog_dev` 指向 E 盘项目，满足 BUG-001 本次会话可操作条件；**不擅自启动/结束 Creo、不擦用户模型**。

1. **新目录打开**：两件装配（`part_alpha` 固定、`part_beta` 平移 [100,0,0]）建好后执行 `creo_export_model(format="native_bundle")`，把 `native_bundle/` 复制到**全新目录**再 `creo_open_file`。断言 `manifest.complete=true`、`files=3`（根 `.asm` + 两个唯一源件）、`missing=0`、`unresolved_references=[]`，清单 SHA256 与产物一致。
2. **组件/位姿/体积**：`creo_inspect_session_assembly` 回读组件数=2、两组件 `feature_id` 与导出前一致、`transform`/`initial_transform` 与导出前逐元素一致（容差 1e-7）、总体积与导出前一致（容差 0.01 mm³）。
3. **哈希与源件不变**：包内三个文件的 SHA256 与源目录对应文件逐一相等；导出前后 `models/<源件 id>/…` 的 `part_sha256` 与 `revision` 均不变（只读导出不加 revision，见 `generic_bridge.py` 只读成功分支）。
4. **同名冲突**：会话中仍有同名装配时必须报 `SESSION_NAME_CONFLICT` 而不是覆盖；**仅在明确指定的本轮测试模型范围或隔离可用会话内**处理同名，不得擦除用户模型。
5. **负例**：抽掉一个 `.prt` 后重导出 → `complete=false`、`missing=1`，且驱动记目标失败、`reimport.skipped=incomplete_bundle`，**不得**继续 `creo_open_file`。

未测范围（如实记录）：上述实机全部未跑；嵌套装配闭包实机、外部/缺失引用实机、保存重载 true、Creo 9/10 均未测。离线阶段不等于整项验收通过。
