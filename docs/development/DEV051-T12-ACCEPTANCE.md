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
