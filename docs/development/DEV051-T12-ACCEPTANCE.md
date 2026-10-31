# DEV-051 T12 验收卡：原生沉孔/沉头孔（FEAT-035）

日期：2026-10-29。阶段：**离线实现完成，待原生验收**。工作区 `E:\Projects\MCP_CREO_MechDog`，分支 `codex/dev051-feedback070`；依赖 HEAD `e152655`（含 T11），实现提交为本卡所在提交。另一会话的未提交文件及运行数据保持原样，工作区 `dirty=true`。

## 冻结契约与 SDK 依据

- 匹配 Creo 12.4 SDK `Common Files/protoolkit/includes/ProHole.h`：第 25–65 行列出 custom hole 元素树；第 340–348 行列出 custom hole 的 CBORE/CSINK 开关、直径、深度、角度；第 665–686 行说明 `PRO_HLE_CUSTOM_TYPE`；第 986–997 行定义开关枚举。`ProElemId.h` 第 1387–1390、1715–1716 行定义元素 ID。只使用本机 SDK 头文件，未提交 SDK 或生成常量表。
- 基本孔径 `diameter`、沉孔口径和深度、沉头口径均为模型长度（毫米契约）；沉头 `angle` 是夹角，度。沉孔与沉头互斥；两者口径须大于基本孔径。沉孔深度须大于零，盲孔时小于孔深。沉头角度严格在 0–180 度之间；由半径差和半角正切算出的锥深在盲孔时须小于孔深。`depth` 省略即通孔，提供正值即盲孔。螺纹、标准孔系列、出口沉头、双端沉孔均不在本批范围。
- 独立工具 `creo_hole` 增加两个可选对象，`execute_plan` 的 `hole` 操作共用同一校验。缺省请求字节级操作字段保持旧形态。编辑沿用 `creo_get_model` 查询真实 dimension ID 再调用 `creo_set_dimensions`，没有按请求字段推测 ID；具体孔尺寸 ID、重定义与再生行为待实机。

## 实现与修改文件

`src/creo_mechdog/schema.py`：两个严格参数对象和组合/几何约束。`server.py`：独立工具可选签名与操作转发。`native/generic.cpp`：有选项时构造一个 `PRO_FEAT_HOLE` 的 custom hole 元素树，旧请求保留 straight hole 分支，材料去除守卫与既有结果路径不变。`tests/unit/test_native_countersink.py`：契约、互斥、独立圆柱/锥台解析式和单特征静态断言。`tools/test_native_countersink.py`：默认离线唯一目录、报告与 SHA256；`--live` 明确拒绝。`docs/work-items/FEAT-035.md` 仅追加本阶段。

## 离线证据

环境：Windows x64、PowerShell、`.venv` Python 3.12、Creo 12.4 匹配 Toolkit SDK、MSVC x64；仅读取头文件并编译，**未连接 Creo、未启动 MCP 服务、未提交 Toolkit 作业**。

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe bridge.py build` | exit 0，生成 `build/creo_worker.exe`；不代表元素树运行成功 |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_native_countersink -v` | 4/4 OK |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_general_validation tests.unit.test_reference_contract tests.unit.test_sheetmetal_relief -q` | 56/56 OK |
| `.venv\Scripts\python.exe tools\test_native_countersink.py` | exit 0，内置 4/4 OK；报告 `build/native_countersink/20261029T101445_a2fe2889/report.json`，SHA256 `2aa4aa980b20e67a58e4b693aefc81046665dbc445350fa7fe72a34675e0c804`；此为提交前指纹，提交后另跑一次并在最终回传给出 |
| `.venv\Scripts\ruff.exe format --check` / `ruff check`（四个 Python 文件）、`.venv\Scripts\clang-format.exe --dry-run --Werror native/generic.cpp`、`git diff --check` | 全部通过 |

原始错误：系统 PATH 中无 `clang-format` 命令，改用 `.venv\Scripts\clang-format.exe` 后通过；最初新增测试/驱动未格式化，执行 `ruff format` 与 import 排序后通过。这些不是保留的失败。共同要求的最后全量 `unittest discover -s tests` 与 `tools/dev_check.py` 在 T13 后执行，结果以最终回传为准。

受测提交：提交前 `e152655` + 本任务未提交改动；`dirty=true`。提交后专项报告会记录本任务提交及 `source_fingerprint`。报告算法与 T11 一致：已跟踪 Python/native 源码及新测试/驱动的 CRLF 归一化 SHA256 清单再哈希。

## 待实机与交接

解析体积仅是完整实体内、平底孔的独立算式；真实钻尖、材料交集、轴向与尺寸由原生结果判定。待验：通孔/盲孔两孔型，单个原生特征及参数回读、圆柱/锥台几何、真实尺寸 ID 编辑、revision、保存重载 true、非法组合和无交集失败的真实回滚。实机 job/model/revision、体积、重载/回滚：**不适用，未运行**。不得把本阶段记录称为新孔型已验收。

给集成人：共享冲突面为 `native/generic.cpp` 的 `generic_hole`、`src/creo_mechdog/schema.py` 的 `HoleOp`、`server.py` 的 `creo_hole`；T09B/T11 的轴回显/relief 不应被覆盖。接口只增加两个可选对象；`capabilities.py` 工具数不变。T01 可补公共工具描述和能力页；T10 才决定版本与发布。本次不改版本、不合 main、不 push、不发布。

## 2026-10-29 实机：沉孔平座与 90° 沉头各一例

环境：手动打开的 Creo 12.4.0.0、`auto_start_creo=false`、唯一 dev 服务 0.8.4、`ready/connected=true`；每例一个新建 50×50×10 板（25 000 mm³），孔位由实测 `surfaces`/`datum_planes` 解析（顶面 id 58、基准面 id 2/4，offset 25/25 → 孔心 (25,25)），未重新提交任何作业，挂起预算 180 s。

```text
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable
```

报告：`build/native_countersink/20261029T231402_6e57e45d/report.json`，SHA256 `f58cd6af6451e1577d4273bdd76dedc53075cb62d3f4e9ddd5e22ae30318477c`，退出码 0，3/3 通过。

| 用例 | job / 模型 / rev | 体积 | 去料实测 | 独立 oracle | 误差 | 特征 |
| --- | --- | --- | --- | --- | --- | --- |
| 沉孔（counterbore Ø10×2，平座） | `16089ad0dff44c4f9a2f1b715f47865c` / `41f8d7a813bf41c9974ea56aa98913be` / 2 | 24 616.725 696 262 | **383.274 303 737 951** | 383.274 303 737 955 | 3.6e−12 | `hole +1`，`feature_id=78`，结果回显 `material_removed_mm3=383.2743`、轴 `start [25,25,0] → end [25,25,10]` |
| 沉头（countersink Ø10 @90°） | `3a7bfe73c43f4acb92b4b22a552b71f3` / `e3f8d5497e0a49428af93296a786367d` / 2 | 24 671.179 968 924 | **328.820 031 075 731** | 328.820 031 075 732 | 7.3e−12 | `hole +1`，`feature_id=78`，结果回显同一字段与轴 |
| 180° 沉头（契约边界） | 无 job | — | — | — | — | 入口拒绝：`operations.0.hole.countersink.angle Input should be less than 180` |

说明：

- “90°/180° 各一例”按契约拆成两件事：90° 沉头可建，**180° 沉头不可建**（schema 要求 `<180`），因此 180° 一侧用平座沉孔（counterbore，锥角等价于 180° 平底）作为几何对照，并把 180° 的拒绝单独作为第三例记录原码。这不是用沉孔冒充沉头：两者的去料 oracle 不同，实测分别对上。
- 两个孔型的去料量与独立解析式逐位一致（误差 1e−12 量级），说明 custom hole 元素树的孔径/沉台/锥角都真正生效，不是“建出特征但不切料”。
- 单位：模型为毫米；沉孔深度、口径按实测量纲生效（Ø6 通孔 + Ø10 沉台深 2；锥角 90°）。
- 未测：盲孔 + 沉台（深度约束）、真实尺寸 ID 编辑（`creo_set_dimensions` 对沉孔参数）、螺纹/标准孔、出口沉头与双端沉孔、保存重载后重开、非法组合的原生回滚、Creo 9/10。

## 2026-10-30 离线余项：盲孔、方向、编辑、失败回滚、保存重载

阶段：**离线实现完成，全部余项待原生验收**。分支 `codex/dev051-feedback070`，受测基线提交 `a8fbf40`（另一窗口已并入 T13/T09A 提交；本任务改动未提交，由派发方统一提交），工作区 `dirty=true`，受测源码指纹 `f12b8aaab3e6609899a145ce8f389bcc8dcdab891c945000fcbd183229b8d67f`。本阶段只覆盖 2026-10-29 三例（沉孔平座、90° 沉头、180° 契约拒绝）之外的余项，不重跑已通过用例。

### 范围解读与冻结口径

- “盲孔”即提供 `depth` 的孔（省略仍为通孔），沿用已冻结契约：`depth` 为自放置面起的总钻深（overall），沉孔/锥深须小于孔深。
- “方向（轴向/法向）”按既定契约解读为：孔沿**放置面法向**生成（`flip` 选侧），深度沿孔轴（轴向）量取；用独立几何（圆柱面 `axis`/`bbox`）判定，不看工具回显轴即判过。轴系放置（coaxial）不在既定契约内，本阶段不扩展。
- “可支持的编辑”限于：用 `creo_get_model`/inspection 取真实 dimension ID 后 `creo_set_dimensions` 修改孔自身尺寸值（基本径、孔深、沉孔径/深、沉头径/角），且改后仍满足合法尺寸关系。孔型/放置/`flip`/选项结构重定义的编辑**不承诺、不测试**。
- 失败回滚指：任务级失败必须 `rollback_succeeded=true` 且模型回到基线（体积/面数不变），其后合法操作仍可执行。

### 新增用例与独立 oracle（默认 live 运行集，6 例）

| 用例 | 输入 | 去料 oracle（平底/overall） | 面数增量 | 尺寸回读 | 几何判定（圆柱面） |
| --- | --- | --- | --- | --- | --- |
| `blind_straight` | Ø6 深 7（通孔对照为 10） | 197.920 337（63π） | +2 | {6, 7} | r=3，轴 ∥Z，bbox z∈[3,10]，中心 (25,25) |
| `blind_counterbore` | Ø6 深 8 + Ø10×2 | 326.725 636（104π） | +4 | {6, 8, 10, 2} | r=3 bbox z∈[2,8]；r=5 座面 bbox z∈[8,10] |
| `blind_countersink` | Ø6 深 8 + Ø10@90° | 272.271 363（260π/3） | +3 | {6, 8, 10, 90} | r=3 bbox z∈[2,8]（锥高 2 < 孔深 8） |
| `direction_side_normal` | Ø6 深 7 打在 x=0 侧面（y=25, z=5） | 197.920 337（63π） | +2 | {6, 7} | r=3，轴 ∥X（法向），bbox x∈[0,7]，中心 y=25, z=5 |
| `direction_flip_guard` | `flip=true` 于顶面（向外钻）+ 同模型恢复孔 | 首孔必须失败无去料；恢复孔 Ø6 深 7 → 197.920 337 | 首孔后面数=基线 6；恢复孔 +2 | 恢复孔 {6, 7} | 失败后体积/面数/特征数不变；`rollback_succeeded=true` |
| `edit_dimension_values` | 建 Ø6 深 8 + Ø10×2 后，真实 ID 编辑径 6→7、沉孔深 2→3 | 建后 326.725 636；编辑后 428.041 999（136.25π） | 前后均 +4 | 编辑后 {7, 8, 10, 3} | 编辑后 r=3.5 bbox z∈[2,7]；r=5 座面 z∈[7,10]；revision 必须变化 |

每例统一硬性检查：去料与契约 oracle 误差 ≤1 mm³、`hole +1`、面数增量、孔特征尺寸值覆盖、`saved_file_reloaded_and_verified=true` 且重载后快照的体积/尺寸与 oracle 一致（保存重载一致性逐例判定）。`matched_variant` 字段同时给出与 118° 钻尖、座面起量（shoulder）备选算式的贴合情况：**命中备选不通过**，但属契约相关发现，须带报告回改口径，不静默采用。

oracle 假设与风险：平底孔、深度自放置面 overall 量取、完整材料相交；面数按 B-rep 拓扑预测（孔壁/底面/座环/锥面）；bbox 取 `ProGeomitemdata` 的 `xyz_min/xyz_max` 修剪面范围（±0.5 容差），实机若为未修剪范围须按报告调整判定口径并记录。角度尺寸按度回读（90）待实机确认。

### 支持/拒绝边界

- 创建侧拒绝保持不变且有单元覆盖（互斥、口径≤基本径、角度 ∉(0,180)、沉孔/锥深 ≥ 盲孔深、负值/零深度），入口拒绝无 job、错误可读。
- `flip` 向外钻的失败是原生材料守卫（“Hole removes no material…”）任务级失败 + 回滚，不是入口拒绝；回滚失败须判失败。
- 编辑只承诺上表所列尺寸值编辑；孔型转换、放置/`flip` 重定义、螺纹/标准孔、出口沉头、双端沉孔、非线性放置、Creo 9/10 均不在本批，保持拒绝或不提供入口。

### 本阶段修改文件

- `tests/unit/test_native_countersink.py`：新增 `oracle_removed` 空选项（纯直孔）、`oracle_tip_extra`/`oracle_faces`/`oracle_variants`/`closest_variant`、面数/圆柱面/轴平行/孔尺寸回读等纯函数与 3 个新用例组（盲孔契约与数值 oracle、面数与备选算式、`judge_geometry` 判定分离）；旧用例与单特征静态断言不动。
- `tools/test_native_countersink.py`：默认 live 改跑 6 例余项（三例已通过项仅在 `--include-passed-cases` 时运行）；每例体积/面数/尺寸/圆柱轴与 bbox 独立判定、重载证据取自 job result 块；离线报告更新 oracle、`pending_live` 与 `out_of_scope`。
- 未改 `src/creo_mechdog/schema.py`（`depth`/`flip` 已在契约内）、未改 `native/generic.cpp` 与 `native/advanced.cpp`、未改 `capabilities.py`（工具数不变）。

### 离线证据

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_native_countersink -v` | 9/9 OK |
| `.venv\Scripts\python.exe -m unittest discover -s tests -q` | 1490 tests OK（249 s，全量单测一次通过） |
| `.venv\Scripts\python.exe tools\test_native_countersink.py` | exit 0，内置 9/9 OK；报告 `build/native_countersink/20261030T102226_76e75830/report.json`，SHA256 `ae785e6902aee1268104087a79a8f0b450feb2e298ea08319af64ee32fda5500` |
| `.venv\Scripts\python.exe bridge.py build` | exit 0，生成 `build/creo_worker.exe`；一次通过，未出现 `advanced.cpp` 编译错误（与 T13 窗口共享该文件，构建时其改动已在 `a8fbf40` 提交内） |
| `.venv\Scripts\ruff.exe format` / `ruff check`（两个 Python 文件）、`git diff --check` | 通过（初版新增文件执行过 `ruff format` 后干净） |

环境：Windows x64、PowerShell、`.venv` Python 3.12.14、Creo 12.4 匹配 Toolkit SDK（仅读 `ProHole.h`：`PRO_E_HLE_DEPTH_DIM_TYPE` 盲深方案为 `PRO_HLE_DEP_SHOULDER_DIM_SCHEME`，运行语义仍未验）；**未连接 Creo、未启动 MCP、未提交 Toolkit 作业**。原始错误：初跑 `oracle_removed` 对无选项直孔 KeyError，补空选项分支后通过；PowerShell 包装层对 stderr 的 NativeCommandError 报 exit 1 属包装产物，以测试输出 `OK`/报告 `passed:true` 为准。

### 未测与实机待验

未测（全部余项）：6 例的元素树/几何/尺寸/回滚/重载均未实机；角度尺寸单位；bbox 语义；沉孔尺寸 ID 编辑的再生行为。三例 2026-10-29 证据仍有效，不并入本次。

实机步骤（会话前提同 BUG-001/AGENTS.md：手动打开 Creo 12.4、`auto_start_creo=false`、唯一 `MCP_CREO_MechDog_dev` 串行，不擅自启停 Creo/清 unknown/重提作业）：

```text
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable
```

（默认只跑 6 例余项；需要连同三例重跑时加 `--include-passed-cases`。）记录每例 job/model/revision、去料实测 vs oracle 误差、`matched_variant`、面数增量、尺寸回读、圆柱轴/bbox、`saved_file_reloaded_and_verified`；`direction_flip_guard` 另记原始失败信息、`rollback_succeeded` 与恢复孔；`edit_dimension_values` 记录 dimension ID、编辑前后 revision 与 oracle。任一 `matched_variant` 非 `contract_flat_overall`、或 bbox/角度单位与假设不符时，保留报告并在本卡回写口径修订，不静默改判。首次 unknown/挂起即停止新提交并交接。

## 2026-10-30：N10 实机余项的离线预检

阶段：**离线预检完成；实机未执行**。分支 `codex/dev051-feedback070`，接手时基线 `79b02ed`，本节提交前 HEAD `a6d4a3d`（并行 N03 窗口提交，非本节改动）。本节**未连接 MCP/Toolkit、未启动 Creo、未创建 MCP 客户端、未运行任何 `--live`、未运行 `bridge.py build`、未运行 `tools\dev_check.py`、未跑全量单测、未改 `schema.py`、未改 `native/`**。工作区 `dirty=true`（含并行窗口未提交文件，未暂存未改写）。

### 单元结果

`.\.venv\Scripts\python.exe -m unittest tests.unit.test_native_countersink -v` → exit 0，Ran 18，OK（原 9 → 新增 9）。

### 驱动覆盖缺口与是否已补

| 缺口 | 是否已补 | 说明 |
| --- | --- | --- |
| **无 `--case` 选择器**：本计划要求"先核当前 `--case` 选择器，避免误把旧3例当新增验收"，但驱动**根本没有该参数**——只有 `--include-passed-cases` 布尔开关，无法只跑 6 例中的指定子集，实机负责人无法分段复测 | **已补** | 新增 `--case NAME`（可重复）：只接受 6 个余项用例名，**2026-10-29 的三例不可选中**；未知名与重复名在连接前以退出码 2 拒绝 |
| 6 例余项集合未在离线产物中显式列出 | **已补** | 离线报告新增 `remainder_cases`/`selected_cases`/`accepted_2026_10_29_cases`/`case_selection_rule` 四字段，把"哪些是新增验收"写进产物；单测 `test_the_default_selection_is_the_six_remainder_cases` 钉死默认恰 6 例且顺序固定 |
| 余项 oracle 无独立单测 | **已补** | 新增 `RemainderExpectationTests`：盲孔 overall 口径、三种盲孔体积（197.920337 / 326.725636 / 272.271363 mm³）、面数增量（2/4/3）、编辑后 oracle（428.041999 mm³） |

核实结果（**原本已具备**）：

- **待测 6 例**：`blind_straight`、`blind_counterbore`、`blind_countersink`、`direction_side_normal`、`direction_flip_guard`、`edit_dimension_values`（默认 live 恰跑这 6 例；三例旧项仅 `--include-passed-cases`）
- **`matched_variant` 备选公式不判通过**：`judge_geometry` 要求 `matched == "contract_flat_overall"`；命中备选（118° 钻尖 / 座面起量 shoulder）→ `problems.append("removal matches ... not the contract flat-bottom oracle")`。`oracle_variants` 把备选值**并列报告**但不用于判定
- **盲孔 depth 为 overall**：`depth` 为自放置面起的总钻深，`oracle_removed` 按平底 + overall 推导；沉孔/锥深须 < 孔深（schema 强制）
- **三种盲孔的体积/新增面/尺寸/圆柱轴与 bbox 预期**：`oracle_removed`/`oracle_faces`/期望尺寸集/`BLIND_CYLINDERS`（r=3、r=5 面的轴向与 bbox 区间）
- **翻向守卫失败后的恢复孔**：`direction_flip_guard` 要求首孔任务级失败 + `rollback_succeeded=true` + 体积/面数不变，随后同模型打**恢复孔**（Ø6 深 7 → 197.920337 mm³）

### 实机命令与预期判定（待指定）

```powershell
# 默认：6 例余项全跑
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable --output build\post090_live_<runid>\n10_countersink\report.json

# 分段（可选，例：先只跑翻向守卫一例）
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable --case direction_flip_guard --output build\post090_live_<runid>\n10_countersink\flip_guard\report.json
```

每例统一硬性检查：去料与契约 oracle 误差 ≤1 mm³、`hole +1` feature 增量、面数增量符合预期、孔特征尺寸值覆盖（直径/深度/沉孔径/深/沉头径/角）、**`saved_file_reloaded_and_verified=true`** 且重载后快照体积与尺寸与 oracle 一致。`matched_variant` 必须为 `contract_flat_overall`，非此值须保留报告并在本卡回写口径修订，**不静默改判**。`direction_flip_guard` 另记原始失败信息、`rollback_succeeded` 与恢复孔；`edit_dimension_values` 记录真实 dimension ID、编辑前后 revision 与 oracle。

### 未测范围与风险

全部 6 例余项未实机（元素树/几何/尺寸/回滚/重载均未观察）。2026-10-29 三例证据保留其历史时点，**不并入本次**。角度尺寸按度回读（90）待实机确认；bbox 语义（`ProGeomitemdata` 修剪面范围 vs 未修剪范围）待实机确认，实机若为未修剪范围须按报告调整判定口径并记录。盲深方案 `PRO_HLE_DEP_SHOULDER_DIM_SCHEME` 的运行语义仍未验（仅读 SDK 头文件）。不承诺孔型/放置/`flip` 重定义的编辑；螺纹、标准孔系列、出口沉头、双端沉孔、非线性放置不在范围；Creo 9/10 未测。

离线产物：`build/post090_live_precheck_20261030T212525_b09a058e/n10_countersink/report.json`（含 `remainder_cases`、`selected_cases`、`accepted_2026_10_29_cases`）。合并预检小结：同目录 `precheck.md`。

## 2026-10-30～31 N10 实机复测追加

分支 codex/dev051-feedback070，基线 7288f2f，runid 20261030T234952。3 盲孔重载 true，但严格几何 oracle 未通过；后续方向用例因 31 字符模型名约束中断，尺寸编辑与翻向回滚未执行。 完整 job_id/model_id/revision、原始错误、命令、报告路径与 SHA256 见 [七段实机总报告](../development/POST090-LIVE-SEVEN-SEGMENTS-2026-10-31.md)；原始 JSON 留在 build/post090_live_20261030T234952/，未入库。未重放已受理作业，会话保持运行。

## 2026-10-31 N10 离线：模型名修复与 oracle 定性（F3b）

分支 codex/dev051-feedback070，基线 5018f02。**离线驱动侧修复，未实机、未构建、未改 `native/` 或任何生产代码。**

### 1. 模型名超长（中断原因）

`tools/test_native_countersink.py` 原用 `unique_name(f"t12_{case_key}")` 生成模型名，`unique_name` 再追加 `_` + 6 位十六进制。`direction_side_normal` 因此拼出 `t12_direction_side_normal_193146`（32 字符），超出 `bridge.py` 的 `MODEL_NAME = [a-z0-9][a-z0-9_]{0,30}`（最多 31 字符），该作业被入口拒绝，方向用例及其后的翻向守卫、尺寸编辑均未执行。

修复：新增 `MODEL_NAME_TAGS` 短标签表与 `model_name_for(case_key)`。每个用例一个 ≤21 字符标签，`unique_name` 后总长 ≤28（`MODEL_NAME_MAX_LENGTH`）；未注册用例键直接 `ValueError`，不再静默生成长名。单元锁定 `tests/unit/test_native_countersink.py::ModelNameTests`（3 例）：生成名长度与字符集、标签 + 7 ≤ 28、未注册键被拒。

### 2. Oracle 定性结论：**真实缺陷**（生产侧语义与冻结契约矛盾），不是 oracle 写错

> **结论：契约「盲孔 depth 为 overall（自放置面到最深点）」与原生实测矛盾，属生产侧真实缺陷。按本卡「命中备选不通过……须带报告回改口径，不静默采用」的规则，本次只记录证据与结论交编排方决策，不修生产。**

#### 2.1 三种盲孔的实测数值（2026-10-30 runid 20261030T234952，板 50×50×10）

| 用例 | 参数 | 实测去料 (mm³) | `contract_flat_overall` | 差值 | `matched_variant` |
| --- | --- | --- | --- | --- | --- |
| `blind_straight` | Ø6，depth 7 | 197.92033717615413 | 197.92033717615698 | **2.8e−12** | `contract_flat_overall` ✓ |
| `blind_counterbore` | Ø6 depth 8 + Ø10×2 | 343.7145697324486 | 326.7256359733385 | **+16.98893375911** | `drill_tip_118_below_depth` |
| `blind_countersink` | Ø6 depth 8 + Ø10@90° | 289.26029707022826 | 272.2713633111154 | **+16.98893375911** | `drill_tip_118_below_depth` |

差值恰为 Ø6 的 118° 钻尖锥体：

```
tip_height = r / tan(59°) = 3 / tan(59°) = 1.8025818570826808 mm
tip_volume = π·r²·h/3    = π·9·1.8025818570826808/3 = 16.98893375911559 mm³

343.7145697324486 − 326.7256359733385 = 16.98893375911007   (残差 5.5e−12)
289.26029707022826 − 272.2713633111154 = 16.988933759112854 (残差 2.7e−12)
```

第三备选 `shoulder_measured_drilldepth`（沉孔钻深自沉台底计，383.274303737955）与实测残差 39.56 mm³，已排除。**主备选公式没有标反**：`contract_flat_overall` 是"平底、depth 自放置面"，`drill_tip_118_below_depth` 是"平底 + 118° 钻尖"，两者定义与本卡的冻结契约一致。

#### 2.2 面数与几何证据（与"肩深 + 钻尖超出"一致）

以 6 面板为基准：

| 用例 | 实测面数 | 实测面增量 | 旧预期面增量 | 旧预期错在哪 |
| --- | --- | --- | --- | --- |
| `blind_straight` | 9 | **+3** | +2 | 回转面沿过孔轴的缝裂成两个半面；旧预期按"回转面 = 1 面"计 |
| `blind_counterbore` | 13 | **+7** | +4 | 同上，另漏 118° 钻尖的两个半锥面 |
| `blind_countersink` | 12 | **+6** | +3 | 同上 |

沉孔例实测 surface 拓扑（job `3d425e823e1f450ba2ee03b0d8d17541`）：Ø6 孔壁两半 z∈[2,8]、Ø10 沉台壁两半 z∈[8,10]、沉台底平面 z=8、118° 锥面两半（type 37）z∈[0.19741814291731785, 2]。

```
锥顶 z = 0.19741814291731785
总深   = 10 − 0.19741814291731785 = 9.802581857082682 mm = 8 (请求 depth) + 1.8025818570826808 (钻尖)
孔轴向 = z 10 → z 2，即 8 mm = 请求的 depth
```

即请求的 depth 8 对应**沉台底（肩面）**所在深度，钻尖再往下 1.8026 mm。

#### 2.3 与原生实现、SDK 的对应

`native/generic.cpp:2296` 在 custom hole 分支写入 `PRO_E_HLE_DEPTH_DIM_TYPE = PRO_HLE_DEP_SHOULDER_DIM_SCHEME`。Creo 12.4 `ProHole.h:1040-1041`：

```
PRO_HLE_DEP_SHOULDER_DIM_SCHEME = -1, /* Dimension till shoulder */
PRO_HLE_DEP_TIP_DIM_SCHEME      = 18  /* Dimension till tip */
```

`ProHole.h:589-595` 说明该元素在 `PRO_E_HLE_DEPTH == PRO_HLE_STD_VAR_DEPTH` 时保存盲钻深度标注方案，**默认即 till-shoulder**。原生明确选了"自肩面量"，与冻结契约"depth 为 overall（自放置面到最深点）"相反。

两条分支须分开看：custom 分支（沉孔/沉头）走 `PRO_HLE_CUSTOM_TYPE` + `PRO_E_HLE_DEPTH`/`PRO_E_HLE_DRILLDEPTH`，带钻尖；plain 分支（直孔）走 `PRO_HLE_NEW_TYPE_STRAIGHT` 的旧直孔语义，实测平底、深度自放置面起算，与 overall 一致（残差 2.8e−12）——但 plain 分支并不是本卡 custom hole 契约所描述的对象。

#### 2.4 判定与待决事项（交编排方）

- 若契约 "depth = overall" 保持不变 → 需改生产：custom 分支改用 `PRO_HLE_DEP_TIP_DIM_SCHEME`，或明确 depth 的计法。
- 若生产行为保持不变 → 需改契约文档与主 oracle：depth 语义改为"肩深"，主 oracle 改为钻尖变体。
- **本次两者都不改**：驱动仍以 `contract_flat_overall` 为唯一判定基准，`matched_variant` **不放松**；`drill_tip_118_below_depth` 只作诊断上报。实机重跑时这三例仍会判失败——这是有意的，等口径决策。

### 3. 配套的驱动/夹具修正（不改判定语义）

- **面数 oracle 拆分**：`oracle_faces`（契约形状，平底）与 `oracle_faces_native`（原生形状，钻尖两半锥面）分开。判定用 native 形状，因为面数是**实测拓扑**而非契约语义；契约形状保留在离线报告中作对照。
- **圆柱几何改用并集 bbox**：原生把每个回转面沿过孔轴的缝裂成两个半面，单个半面的 bbox 中心并不在孔轴上（旧驱动因此误报 "center axis1 26.5 != 25.0"）。新增 `cylinder_groups`，按（半径，轴向符号无关）分组后取**并集 bbox**，才是真正框住孔的盒子。
- **新增深度语义探针**：`hole_depth_evidence` / `depth_semantics` 从实测 surface 的 bbox 直接算孔深（bore 深、锥深、总深），并判定读法为 `overall_flat` / `shoulder_plus_tip` / `other`，写入报告的 `depth_evidence` / `depth_semantics` 字段。实机重跑可直接看到口径结论，不必再手工反推。
- 六例保留，`matched_variant` 判定与体积判定分开且均未放松。

### 4. 离线证据

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_native_countersink -v` | 29/29 OK，退出码 0 |
| `.venv\Scripts\python.exe tools\test_native_countersink.py` | 退出码 0；离线报告 `build/native_countersink/<runid>/report.json`（含 `faces_added_over_plate.contract` / `.native`、`depth_semantics_measured_2026_10_30`） |

### 5. 实机重跑命令与预期判定

```powershell
# 默认：6 例余项全跑
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable --output build\post090_live_<runid>\n10_countersink\report.json

# 分段（可选）
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable --case blind_counterbore --output build\post090_live_<runid>\n10_countersink\cbore\report.json
```

预期：

- 模型名不再超长，方向、翻向守卫、尺寸编辑三例**首次获得执行机会**（此前被入口拒绝阻断）。
- `blind_straight`：`matched_variant=contract_flat_overall`、`depth_semantics=overall_flat`、面增量 +3、Ø6 并集 bbox z∈[3,10] 且中心 (25,25) —— **预期通过**。
- `blind_counterbore` / `blind_countersink`：`matched_variant=drill_tip_118_below_depth`、`depth_semantics=shoulder_plus_tip`、面增量 +7 / +6、Ø6 并集 bbox z∈[2,8]、Ø10 z∈[8,10] —— **体积与 `matched_variant` 两项预期仍判失败**（契约口径未定，按卡规则不静默采用备选）；面数与轴/中心项预期通过。
- `direction_side_normal`：轴平行 +X，Ø6 并集 bbox x∈[0,7]、中心 (25,5)。
- `direction_flip_guard`：作业级失败 + `rollback_succeeded=true` + 模型体积/面数不变 + 恢复孔通过。
- `edit_dimension_values`：真实 dimension ID 编辑直径 6→7、沉台深 2→3，编辑后 revision 变化；**注意**该例同为 custom 分支，其 create/edit 两阶段的体积与 `matched_variant` 项预期同样受第 2 节口径影响。

**未实机**：本次未连接 Creo，未提交任何 Toolkit 作业。

## 2026-10-31 生产修复：T12 盲孔深度口径 = overall（量到钻尖顶点）

阶段：**离线修复完成（生产侧 + 判定侧 + 回归），实机未执行**。分支 `codex/dev051-feedback070`，受测基线提交 `d17c494`（本节改动未提交，由派发方统一提交）。本节**未连接 Creo、未启动 MCP、未创建 MCP 客户端、未运行任何 `--live`**。

### 1. 判定依据（编排方裁定）

编排方裁定：**T12 盲孔深度语义 = "overall"（量到钻尖顶点）**，即请求的 `depth` 是自放置面到**钻尖顶点**的总深。据此**修生产侧**，`docs/work-items/FEAT-035.md` 的契约文档**不改**。

第 2 节记录的生产侧缺陷（custom 分支写 `PRO_HLE_DEP_SHOULDER_DIM_SCHEME`，导致 depth 量到肩面、钻尖再往下伸一个锥高）正是本裁定要消除的对象。契约文档的"depth 为 overall"表述本来就是对的，错的是生产实现。

### 2. SDK 核实（`ProHole.h` 原文摘录）

本机 SDK `C:\Program Files\PTC\Creo 12.4.0.0\Common Files\protoolkit\includes\ProHole.h`：

```c
/* PRO_E_HLE_DEPTH_DIM_TYPE */
typedef enum pro_hle_dep_dim_scheme
{
  PRO_HLE_DEP_SHOULDER_DIM_SCHEME = -1, /* Dimension till shoulder */
  PRO_HLE_DEP_TIP_DIM_SCHEME      = 18  /* Dimension till tip */
}ProHleDepDimScheme;
```

同文件 589–595 行（元素语义说明）：

```
|          : PRO_E_HLE_DEPTH_DIM_TYPE   : Available when PRO_E_HLE_DEPTH is  |
|          :                            : PRO_HLE_STD_VAR_DEPTH              |
|          :                            : Stores the information of blind    |
|          :                            : drill depth dimensioning scheme.   |
|          :                            : PRO_HLE_DEP_SHOULDER_DIM_SCHEME is |
|          :                            : default. PRO_HLE_DEP_TIP_DIM_SCHEME|
|          :                            : can be used to dimension till tip. |
```

同文件 244 行确认元素类型映射：`PRO_E_HLE_DEPTH_DIM_TYPE | ProHleDepDimScheme`。

**核实结论**：SDK 存在可用的 tip 枚举 `PRO_HLE_DEP_TIP_DIM_SCHEME = 18`，且该元素恰在 `PRO_E_HLE_DEPTH == PRO_HLE_STD_VAR_DEPTH`（盲孔）时可用——与本修复的写入条件完全一致。故无需退回备选方案。`native/constants.inc` 已含该常量（6209–6210 行），构建无需重新生成常量表。

### 3. 生产侧改动（`native/generic.cpp`，仅 custom 分支）

```diff
         if (op.contains("depth")) {
             real(com, PRO_E_HLE_DRILLDEPTH, op.at("depth"));
-            integer(com, PRO_E_HLE_DEPTH_DIM_TYPE, PRO_HLE_DEP_SHOULDER_DIM_SCHEME);
+            // FEAT-035/T12: the blind depth is the overall depth from the
+            // placement face down to the drill tip, so the custom hole
+            // dimensions till the tip. The plain straight-hole branch keeps
+            // its own element tree and its flat-bottomed overall depth.
+            integer(com, PRO_E_HLE_DEPTH_DIM_TYPE, PRO_HLE_DEP_TIP_DIM_SCHEME);
         }
```

**只改 custom 分支**（`PRO_HLE_CUSTOM_TYPE`，即带沉孔/沉头的孔）。plain 直孔分支（`PRO_HLE_NEW_TYPE_STRAIGHT` + `PRO_E_HOLE_STD_DEPTH` / `PRO_HLE_STRGHT_BLIND_DEPTH`）**一行未动**：它本来就没有钻尖、实测已是平底且 depth 自放置面起算（残差 2.8e−12 mm³），符合 overall，无需改动。

### 4. 新 oracle 的推导（并记录一处算术更正）

钻尖几何：118° 夹角，`tip_height = r / tan(59°)`；锥体体积 `V_cone = π r² h / 3`；**锥体所在的整圆柱**体积 `V_body = π r² h`。

till-tip 下，depth 量到钻尖顶点，故：
- 钻尖顶点在 z = 10 − depth（放置面 z = 10）；
- 全径孔壁（Ø6 段）止于 z = 10 − depth + h（比顶点高一个锥高）；
- 锥体占据最后这 h 高度。

去料量 = 平底参考 **− (2/3)·V_body**（等价于 **− 2·V_cone**）：平底参考的最后 h 高度是一段整圆柱 `V_body`，till-tip 把它换成锥体 `V_cone = V_body/3`，差值 `V_body − V_body/3 = (2/3)·V_body`。

> **算术更正**：任务书给的算例 "Ø6/118°：326.7256 − 11.32596 = 315.3997" 中的减数用错了量。`11.32596 = (2/3)·V_cone` 把"锥体体积"当成了"锥体整圆柱体积"；(2/3) 应乘在 **V_body = 50.96680127734677 mm³** 上，减数是 **33.97786751823118 mm³**，不是 11.32596。
>
> 两种独立方式确认正确值：
> 1. **正向重建**：按 till-tip 几何逐段积分（Ø10 沉台 + Ø6 柱体 + 118° 锥体）得 `292.7477684551073`，与代数式残差 5.7e−14 mm³；
> 2. **回归实测**：修复前的 till-shoulder 实测值 343.7145697324486 mm³，减去整个锥体整圆柱 `V_body = 50.96680127734677` 得 `292.74776845510183`，与代数式残差 5.5e−12 mm³。
>
> 也就是说，till-shoulder 实测 = 平底参考 + V_cone，till-tip 应得 = 平底参考 − 2·V_cone = 实测 − V_body。**本卡与代码一律采用几何正确的 292.74776845510735**，不采用 315.3997。

各例新 oracle（平底参考仍作为推导基线保留）：

| 用例 | 参数 | 平底参考 (mm³) | **新契约 oracle (till-tip)** | 差值 |
| --- | --- | --- | --- | --- |
| `blind_straight` | Ø6 深 7（plain 分支，无钻尖） | 197.920 337 176 156 98 | **197.920 337 176 156 98**（不变） | 0 |
| `blind_counterbore` | Ø6 深 8 + Ø10×2 | 326.725 635 973 338 5 | **292.747 768 455 107 35** | −33.977 867 518 231 18 |
| `blind_countersink` | Ø6 深 8 + Ø10@90° | 272.271 363 311 115 4 | **238.293 495 792 884 24** | −33.977 867 518 231 18 |
| `edit_dimension_values`（编辑后） | Ø7 深 8 + Ø10×3 | 428.041 999 051 609 3 | **374.086 403 872 195 9** | −53.955 595 179 413 4 |

（编辑后用例直径为 7，锥高 `3.5/tan(59°) = 2.103012166596461`，`V_body = 67.44449397426675`，故差值为其 2/3。）

### 5. 判定侧改动（`tools/test_native_countersink.py` + 夹具 `tests/unit/test_native_countersink.py`）

- **主 oracle 换成 tip-overall**：`oracle_contract()` 按分支给出判定值——blind custom 分支取 till-tip 值，plain 分支与通孔保持平底参考。夹具新增 `oracle_tip_body()`（锥体整圆柱）与 `oracle_removed_tip()`。
- **`matched_variant` 矩阵调整**：判定键由写死的 `contract_flat_overall` 改为按分支取 `contract_tip_overall`（blind custom）/ `contract_flat_overall`（其他），经 `contract_variant_key()` 传递。**"shoulder+below"（till-shoulder 读法）降级为 `defect_till_shoulder_below_tip` 缺陷形态**，只并列上报、永不判过；座面起量读法同样降级为 `defect_seat_measured_drilldepth`。
- **深度语义判定改为期望锥尖顶点在 z = 10 − depth**：`depth_semantics()` 在总深等于 `expected_depth` 时按有无锥面区分 `overall_tip`（custom 分支，须有锥面）与 `overall_flat`（plain 分支，无锥面）；`shoulder_plus_tip`（总深 = depth + 锥高）保留为缺陷读法。`judge_geometry()` 新增一项硬判定：实测语义必须等于 `expected_depth_semantics()`，否则判失败。
- **面数与圆柱轴并集判定不变**：仍按实测拓扑判定（`oracle_faces_native`），+3 / +7 / +6 未动；圆柱面仍用并集 bbox 分组，未动。
- **孔壁 bbox 随新几何更新**：till-tip 下 Ø6 全径段止于一个锥高之上，故 `blind_counterbore` / `blind_countersink` 的 Ø6 并集 bbox 由 z∈[2,8] 改为 **z∈[3.802 582, 8]**（锥尖顶点在 z=2）；`blind_straight` 仍为 z∈[3,10]；编辑后 Ø7 段为 z∈[4.103 012, 7]。这些值由夹具 `oracle_bore_span()` 统一推导，不写死。

### 6. 离线证据

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_native_countersink -v` | exit 0，**36/36 OK**（原 29 → 新增 7） |
| `.venv\Scripts\python.exe tools\test_native_countersink.py` | exit 0，内置 36/36 OK；报告 `build/native_countersink/20261031T110827_808aaadb/report.json`，SHA256 `e329279a3e1427261b11991ea93fd4661ce71a67735da4571cf8f64da272073a` |
| `.venv\Scripts\python.exe tools\dev_check.py --work-item FEAT-035` | exit 0，`"success": true`；`unit_tests: passed`、`native_validation: not_run`（该工具不跑实机） |
| `.venv\Scripts\python.exe bridge.py build` | exit 0，生成 `build/creo_worker.exe` |
| `.venv\Scripts\ruff.exe format --check` / `ruff check`（两个 Python 文件）、`.venv\Scripts\clang-format.exe --dry-run --Werror native/generic.cpp` | 全部通过 |

新增单测 7 例：`test_the_custom_branch_dimensions_till_the_tip`（源码守卫：custom 分支必须写 tip 枚举、全文不得再出现 shoulder 枚举、plain 分支不得写 `DEPTH_DIM_TYPE`）、`test_the_tip_oracle_is_the_flat_reference_less_two_thirds_of_the_cone_body`（并显式断言"不是 (2/3)·锥体体积"）、`test_the_tip_oracle_values_are_locked`（新 oracle 数值锁）、`test_the_contract_variant_follows_the_branch`、`test_the_bore_span_stops_one_tip_height_above_the_tip`、`test_the_depth_reading_of_a_till_tip_drill_point_hole`、`test_the_pre_fix_measurement_is_far_from_the_fixed_contract`；改写 `test_the_depth_reading_of_a_drill_point_hole` → `test_the_till_shoulder_reading_is_the_defect_form`（保留旧读法为缺陷形态证据）。

**未实机**：本次未连接 Creo、未启动 MCP、未提交任何 Toolkit 作业；实机语义是否与 till-tip 一致仍待验证。

### 7. 实机重跑命令与逐例预期

```powershell
# 默认：6 例余项全跑
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable --output build\post090_live_<runid>\n12_countersink\report.json

# 分段（可选，例：先只跑两个 custom 盲孔）
.\.venv\Scripts\python.exe tools\test_native_countersink.py --live --confirm-session-usable --case blind_counterbore --case blind_countersink --output build\post090_live_<runid>\n12_countersink\custom\report.json
```

**六例全部按 tip-overall 口径判定**（方向、编辑、翻向回滚三例**首次获得执行机会**）：

| 用例 | 期望 `matched_variant` | 期望 `depth_semantics` | 期望去料 (mm³) | 面增量 | Ø 圆柱并集 bbox | 预期结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `blind_straight` | `contract_flat_overall` | `overall_flat` | 197.920 337 176 157 (±1) | +3 | r=3，z∈[3,10]，中心 (25,25) | **预期通过**（plain 分支不受本修复影响） |
| `blind_counterbore` | `contract_tip_overall` | `overall_tip` | 292.747 768 455 107 (±1) | +7 | r=3 z∈[3.802 582,8]；r=5 座面 z∈[8,10] | **预期通过**（本次修复的目标） |
| `blind_countersink` | `contract_tip_overall` | `overall_tip` | 238.293 495 792 884 (±1) | +6 | r=3 z∈[3.802 582,8] | **预期通过**（本次修复的目标） |
| `direction_side_normal` | `contract_flat_overall` | `overall_flat` | 197.920 337 176 157 (±1) | +3 | r=3，轴 ∥X，x∈[0,7]，中心 (25,5) | **预期通过**（首次执行） |
| `direction_flip_guard` | `contract_flat_overall` | `overall_flat` | 恢复孔 197.920 337 176 157 (±1) | +3 | 恢复孔 r=3，z∈[3,10] | **预期通过**（首次执行：作业级失败 + `rollback_succeeded=true` + 体积/面数不变） |
| `edit_dimension_values` | `contract_tip_overall` | `overall_tip` | 建后 292.747 768 455 107；编辑后 374.086 403 872 196 (±1) | 均 +7 | 建后 r=3 z∈[3.802 582,8]；编辑后 r=3.5 z∈[4.103 012,7]、r=5 z∈[7,10] | **预期通过**（首次执行；revision 必须变化） |

判定失败信号（任一出现即为不通过，不得静默改判）：

- `matched_variant` 为 `defect_till_shoulder_below_tip`（= 平底参考 + 锥体体积 = 343.714 569 732 454 / 289.260 297 070 231）或 `defect_seat_measured_drilldepth`（= 383.274 303 737 955）→ 说明仍读作 till-shoulder 或座面起量；
- `depth_semantics` 为 `shoulder_plus_tip`（总深 = depth + 锥高 = 9.802 581 857）→ 修复未生效；
- `depth_semantics` 为 `other` → 深度不在任何已知读法上；
- 去料超出新 oracle ±1 mm³ → 形状与 till-tip 解析式不符。

若实机实测与上表不符（例如 Creo 对 `PRO_E_HLE_DEPTH_DIM_TYPE` 的实际作用与 SDK 注释不符、或编辑后锥高随直径变化的规律不同），**保留报告并在本卡回写口径修订，不静默改判**。

### 8. 2026-10-31：N10 第二轮实机复测（编排方串行）

原始报告 `build/post090_live2_20261031T115830/n10/run1/report.json`，SHA256 `6056a0974968518dda2e1a7c7281a8878a49dc5d5d6787960a85b4c5d7a76119`，`run_id=20261031T134447_69136d19`，`mode=live`，`passed=true`，`stopped=null`。六例**均首次获得执行机会**并全部通过。

| 用例 | 底板作业 / 孔作业 | rev | 去料实测 (mm³) | `matched_variant` | `depth_semantics` |
| --- | --- | --- | --- | --- | --- |
| `blind_straight` | `d67dc571359242618f1d54c8518b49af` / `4a2733102e234ca083a380bc694e1fdb` | 2 | 197.92033717615413 | `contract_flat_overall` | `overall_flat` |
| `blind_counterbore` | `b9225dea1ced40cd98f7be119feecbff` / `37aae7ae58ae4a5f9557266fab2eeeec` | 2 | 292.7477684551013 | `contract_tip_overall` | `overall_tip` |
| `blind_countersink` | `468d5a79b60f4b47abb154d01d648864` / `64de562c50174e25990e688076c78687` | 2 | 238.293495792881 | `contract_tip_overall` | `overall_tip` |
| `direction_side_normal` | `7570b713bac347d69a75917452772fa4` / `076503e1e58c4f0cac52b9f11161c534` | 2 | 197.92033717615777 | `contract_flat_overall` | `overall_flat` |
| `direction_flip_guard` | `29616cb6534e4d34967856ab1bb5084f` / `c9e9ff90226a41c8baab8cdca24bedf1` | — | 翻向作业 failed（守卫按设计） | 恢复孔 `contract_flat_overall` | `overall_flat` |
| `edit_dimension_values` | `f23ff0e51dc641db9fa167e1428bb87d` / `1d755a950cb343df95dee70d8b40c719` → 编辑 `fc2ecd45c1884a958699ab2c53b799bc` | 2→3 | 292.7477684551013 → 374.0864038721993 | `contract_tip_overall` | `overall_tip` |

#### 判定要点

1. **tip 口径生产修复（`0f1844a`）实机验证成立**。沉孔与沉头两例均命中 `contract_tip_overall` 且 `depth_semantics=overall_tip`，**未**落到任何 defect 变体（`defect_till_shoulder_below_tip`＝343.7145697324541 / 289.260297070231，`defect_seat_measured_drilldepth`＝383.27430373795477）。`depth_evidence` 侧：沉孔与沉头均 `cone_depth_max=8.0`、`total_depth=8.0`、`bore_depth_max=6.19741814291732`（钻孔段止于锥底），与 till-tip 解析式自洽；直孔分支仍为 `bore_depth_max=7.0`、`total_depth=7.0`。
2. **方向例**：`direction_side_normal` 去料 197.92033717615777 对 oracle 197.92033717615698（误差 8.0e-13），`matched_variant=contract_flat_overall`；孔轴实测 `(25,25,5)→(25,25,3)`，即沿放置面法向而非默认 Z，尺寸回读 `[6.0, 7.0, 25.0, 5.0]`。
3. **翻向守卫**：`direction_flip_guard` 的翻向作业按设计失败——`toolkit_code=-1`、`failed_stage=execute_hole`、`rollback_succeeded=true`、`effect_status=rolled_back`，原生消息 "Hole removes no material; check reference offsets, placement, flip and overlap with existing holes"；失败后模型体积 `24999.999999999993`、面数 6，与底件一致（未留半成品几何）。随后恢复作业 `4762ea0f692e420a8a19d831b5a29fe9` succeeded，rev 2，去料 197.92033717615413（`contract_flat_overall`，误差 2.8e-12），保存重载 true。
4. **尺寸编辑**：编辑走真实 dimension ID（`diameter=14`、`counterbore_depth=13`），编辑后 rev 3、去料 374.0864038721993 对 oracle 374.0864038721959（误差 3.4e-12），`depth_evidence` 的 `cone_depth_max` 仍为 8.0、`bore_depth_max=5.896987833403539`（随孔径 3→3.5 变化，符合编辑后锥高规律），尺寸回读 `[3.0, 7.0, 118.0, 10.0, 8.0, 25.0, 25.0]`，保存重载 true。
5. **其余一致性**：全部成功例 `saved_file_reloaded_and_verified=true`、`missing_dimensions=[]`、`problems=[]`；面数增量与 oracle 相符（直孔 +3、沉孔 +7、沉头 +6）；`feature_delta` 均为 `hole=+1`、其余类别 0。

#### 未测范围

通孔口径、出口沉头与双端沉孔、螺纹/标准孔、Creo 9/10、WorkBuddy 黑盒。本节不改写 2026-10-29 的三例实机结论，也不据此关闭 FEAT-035 整卡。
