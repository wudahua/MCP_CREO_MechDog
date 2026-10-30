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
