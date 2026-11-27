# 开发入口

从 [统一台账](BACKLOG.md) 定位 ID，读取工作卡的当前摘要，再查相关源码；历史证据按需打开。根级 [AGENTS.md](../AGENTS.md) 是仓库约束，架构与入口分工见 [ARCHITECTURE](development/ARCHITECTURE.md)，编码规则见 [CODING_STANDARD](development/CODING_STANDARD.md)。当前版本以 [version.py](../version.py) 为准。

## 准入与日常维护

Creo TOOLKIT 的官方资料导航、API/元素树查证及接入方法见 [中文开发指南](development/CREO_TOOLKIT_GUIDE.md)。Git 检出的本项目可使用 [creo-mechdog-dev skill](../.agents/skills/creo-mechdog-dev/SKILL.md)（显式调用 `$creo-mechdog-dev`，也允许按开发任务匹配）；实机授权和 WorkBuddy 黑盒规则继续以 AGENTS 为准。

1. 开始前核对分支、工作树、未提交改动、合并现场和已有 ID，避免覆盖其他任务。默认从可交付 main 创建 `codex/<条目>-<主题>`；关联集成批以指定提交为基点时，在工作卡记录原因与源码身份。
2. BACKLOG 是唯一当前台账。新增工作先登记未占用 ID、目标、范围、验收及环境。小修复沿用工作卡和证据链接，几行即可；复杂跨模块任务才使用[工作卡模板](templates/WORK_ITEM.md)和完整计划，不另建总台账或第二份待办。
3. 已报告缺陷先复现，分别记录现象和推测根因。诊断交付与根因修复、部分子项交付与整卡完成分别记录；缺其他版本测试不等于代码未修。观察项仅在收到同类新证据后重开调查。
4. BACKLOG 每个 ID 只有一行：优先级、当前状态、目标版本、简短剩余工作、工作卡链接。工作卡首页维护当前结论、剩余范围、依赖和最新证据，旧过程保留日期。无保留范围的完成项移至[完成档案](BACKLOG_COMPLETED.md)，部分完成不关整卡。
5. 实现最小完整改动；格式整理、路径迁移与行为修改分开提交。能力变化同步工具描述、README 和能力边界。PR 使用仓库模板；开发分支提交本身不要求发布。

按版本查阅[版本说明](release-notes/)和[历史开发记录](archive/DEVELOPMENT_LOG_2026.md)。各版本的交付范围与验证环境见对应发布记录。

## 架构与环境

MCP stdio 通过 `python -m creo_mechdog` 或根 `server.py` 启动，经 `creo_mechdog.bridge` 和 `creo_mechdog.generic_bridge` 校验、登记和单通道调度，再由原生 Toolkit 执行器调用 Creo 计算几何。新业务实现进入 `src/creo_mechdog/`，根级兼容入口与包内共享模块或类型。入口及资源和生成物边界见 AGENTS 与 ARCHITECTURE。

服务 stdout 只承载 MCP。通道忙碌立即拒绝（`isError=true`、`status=busy`、`blocking_*`），不排队、不自动重试；已接受任务只轮询 `creo_get_job`，不能重复提交。现有并发边界见 [BUG-009](archive/work-items/BUG-009.md)。长度为 mm、角度为度；特征 label 小写字母起始，仅小写字母、数字、下划线，最多 28 字符。

开发环境为 Windows x64 / Python 3.12+。语言与单元检查不需要 Creo SDK。建模需 Creo 9/10/12、匹配 SDK、许可和 MSVC x64；当前本机原生验收环境为 Creo 12.4.0.0。Creo 9 编译探测已有修复，本机无 SDK，实机编译/运行未验；其他环境范围见[兼容矩阵](COMPATIBILITY.md)。不要求全项目 Creo 10 独立复测或双版本发布门槛，也不把本机成功外推至其他环境。

本机开发联调入口（`MCP_CREO_MechDog` / `MCP_CREO_MechDog_dev`）以当前 Git 主检出 `D:\my\MCP_CREO_MechDog` 为准，目标目录与运行期加载路径核查方法见根级 [AGENTS.md](../AGENTS.md#构建测试与开发命令)。启动、重启、建模与异常恢复的授权范围见[本机实机常设授权](../AGENTS.md#配置许可与本机实机常设授权)。BUG-001 的历史现场见[恢复记录](validation/BUG-001-recovery-2026-10-17.md)。

## 命令与检查

在仓库根目录 PowerShell 执行；正式安装步骤见 [INSTALL](INSTALL.md)。`requirements-dev.txt` 包含锁定依赖及 editable 安装，变更包布局后同步安装入口、资源路径和分发。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe tools\dev_check.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\test_unit.py
.\.venv\Scripts\python.exe tools\dev_check.py --skip-unit
.\.venv\Scripts\python.exe tools\dev_check.py --strict --skip-unit
.\.venv\Scripts\python.exe tools\test_mcp.py --offline
.\.venv\Scripts\python.exe tools\test_mcp.py --protocol-only
.\.venv\Scripts\python.exe tools\test_mcp.py
```

`tools\test_mcp.py --offline` 经包入口做真实 stdio 检查，隔离 Creo 启动与网络，已纳入 `tools\dev_check.py` 的离线门禁。追加 `--legacy-entry` 可验证根 `server.py`。`--protocol-only` 启动服务并跳过会话与建模检查。默认模式等待 `creo_startup_status` 就绪，再核验 `ready_to_build`、`connected` 与无效几何拒绝，可用 `--create` 或 `--create --simple` 追加实机建模。契约期望位于 `src/creo_mechdog/mcp_contract.py`，由 `tests/unit/test_mcp_contract.py` 守门（BUG-151）。

统一检查覆盖 Ruff、Python/C++ 格式、存量基线比较及全部单元，报告为 `build/development_check.json`、`build/unit_test_report.json`。`--skip-unit` 只提供语言证据，`--strict` 暴露全部欠账。[风格基线](development/style-baseline.json) 按诊断及内容身份容许存量，不能掩盖工具/配置错误、单测失败或新增问题；正常开发与 CI 不重建基线，不新增豁免。

单元阶段默认 900 秒，可用 `--unit-timeout-seconds 1200 --work-item <ID>` 调整；报告区分 passed/failed/timed_out，超时不算通过。单测必须 mock 外部通道和进程，真实 busy 时修夹具，不绕过产品保护。新增用例放 `tests/unit/test_*.py`，使用 unittest；校验或保护变化补回归。冻结源码后执行最终全量，不能用分拆测试代替统一检查。

原生构建与实机验收可使用以下命令。

```powershell
.\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
.\.venv\Scripts\python.exe bridge.py build
.\.venv\Scripts\python.exe -m creo_mechdog
.\.venv\Scripts\python.exe tools\test_general.py
```

`native/constants.inc` 必须由本机 SDK 生成，不复制、不提交、不分发。DEV-049 的默认离线驱动与双开关门槛见 [T04](archive/development/DEV049-T04-ACCEPTANCE.md)、[T05](archive/development/DEV049-T05-ACCEPTANCE.md)、[T06](archive/development/DEV049-T06-ACCEPTANCE.md)，历史结果不等于新源码已测。

## 验收与交付

| 改动 | 必要证据 |
| --- | --- |
| 文档 | 链接、ID 唯一性、状态/工作卡、历史原件字节、冲突标记和打包引用；涉及工具或配置时加对应回归 |
| Python 校验/调度/保护 | 统一检查及专项回归；外部进程/会话行为另取实机证据 |
| C++/建模/单位 | 匹配 SDK 构建、对应驱动、实际几何/尺寸/单位、保存重载及适用失败回滚；mm/英寸/混合/未知单位分别声明 |
| 路径/布局迁移 | 安装/客户端/后台入口、资源和数据根、解压源码包验证；原生变化补实机 |
| 合入 main | 未发布新版本、版本元数据、适用验收和打包、标签/Release/附件及 SHA256 远端核对 |

原生成功须任务成功、特征有效、几何断言通过且 `saved_file_reloaded_and_verified=true`。拒绝、超时、unknown、编译通过均不能代替建模成功。证据记录日期、条目、版本、提交、dirty、受测指纹、命令、环境与未测范围；历史证据保留原日期，引用时说明复用边界。

每次合入或直接提交 main（包括文档）都须同次完成对应 GitHub Release；仅合并、推送、标签或草稿不算交付。`version.py` 递增至未发布版本，标签指向合入后的主干提交，附件由该提交生成；旧标签与同名附件不可覆盖，细则见 [RELEASING](development/RELEASING.md)。独立开发分支可以按用户要求只交付本地提交。

<a id="workbuddy-测试约定"></a>

WorkBuddy 一律指公开 MCP 黑盒验收：仅给操作场景、输入、预期和报告要求，不读取源码/配置/Git、不跑本地测试。环境和版本由 MCP 公开接口确认，未提供则“无法确认”；只有实际并发才能报并发通过。内部文件占用/重试预算不纳入黑盒结论。开发者证据与 WorkBuddy 分别记录，完整约定见 AGENTS。

`docs/validation/` 历史原件逐字节保留。稳定契约、安装说明、兼容矩阵和第三方许可继续沿用；`tools/package.py` 递归收集 docs 的 Markdown/JSON，归档不会缩小分发范围，本批不改打包协议。
