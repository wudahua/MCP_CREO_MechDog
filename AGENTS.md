# Repository Guidelines

## 项目结构与模块职责

新业务放在 `src/creo_mechdog/`，根级 Python 入口只转发或启动 CLI。服务 stdout 仅承载 MCP 协议。原生执行器采用 C++17；模块分工与进程链见[架构](docs/development/ARCHITECTURE.md)。

`.venv/`、`build/`、`jobs/`、`models/`、根 `seed_registry.json`、`toolkit.lock` 及下文列出的本机配置与生成物不得进入源码包或发布附件。

## 运行时边界与开发准入

- **Toolkit 单通道**：通道忙碌时立即拒绝新提交（`isError=true`、`status="busy"`，携带 `blocking_job_id`/`blocking_model_id`/`blocking_operation` 与重试指引），不排队、不自动重试；已接受任务只轮询 `creo_get_job`。未新增队列前（参见 BUG-009）不要假设 FIFO 或容量保证。
- **台账与指南**：以 `docs/DEVELOPMENT.md` 为开发入口、`docs/BACKLOG.md` 为唯一工作台账；功能/缺陷/整理在实现前登记固定 ID 与验收方式（复杂条目使用 `docs/templates/WORK_ITEM.md`）。先复现缺陷再修复，优先处理 P1 稳定性问题。Toolkit API 查证见 [中文开发指南](docs/development/CREO_TOOLKIT_GUIDE.md) 与 `.agents/skills/creo-mechdog-dev/SKILL.md`。
- **文档规范**：历史演进与背景说明见 [GOVERNANCE_HISTORY.md](docs/development/GOVERNANCE_HISTORY.md)；文档归档与防膨胀规则见 [docs/README.md](docs/README.md)。

## 构建、测试与开发命令

按改动类型选择[开发命令与检查](docs/DEVELOPMENT.md#命令与检查)。

服务标识统一为 `MCP_CREO_MechDog`；当前本机 Git 主检出目录为 `D:\my\MCP_CREO_MechDog`（原 `E:\Projects\MCP_CREO_MechDog` 路径已不存在）。本机开发联调若使用独立调试项 `MCP_CREO_MechDog_dev`（或直接配置 `MCP_CREO_MechDog`），应指向 `D:\my\MCP_CREO_MechDog` 并禁用旧 C 盘副本和 test 项；不得擅自改动其他 agent 正在使用的客户端配置或会话。核查当前服务实际加载目录与入口的只读方法：1) 查看客户端 MCP 配置的 `command`/`args`/`cwd`（如 `C:\Users\Administrator\.workbuddy\mcp.json`、`C:\Users\Administrator\.codex\config.toml`）；2) 用 `Get-CimInstance Win32_Process` 查看运行中 Python MCP 进程命令行；3) 调用 MCP 工具 `creo_capabilities(detail="full", section="runtime")` 或 `creo_server_info` 核对 `code_root`、`server_entry`、`python_executable` 与 `source_changed_since_startup`。

## 代码风格、单位与测试约定

- **代码风格**：Python 4 空格缩进（`snake_case` / `PascalCase`，Ruff 配置见 `pyproject.toml`）；C++17 与 Toolkit 命名（`.clang-format`）；详见 `docs/development/CODING_STANDARD.md`。`docs/development/style-baseline.json` 仅记录历史存量，禁止新增诊断或自动重建；`docs/validation/` 历史反馈原件保持逐字节一致（已在 Ruff 排除）。
- **单位与标签**：长度 mm，角度度；特征标签以小写字母开头，仅含小写字母、数字和下划线，最多 28 字符。
- **单元测试**：`tests/unit/test_*.py`，修改校验或保护逻辑时补充回归用例。修改原生代码后需运行对应 `tools/test_*.py`，确认几何断言与 `saved_file_reloaded_and_verified=true`。证据须记录提交号、dirty 状态、源码指纹、命令、环境与未测范围，不得用历史证据替代当前验证。
- **WorkBuddy 黑盒约定**：用户提到“WorkBuddy 测试”或索要测试提示词时，指通过 WorkBuddy 直接调用已连接 MCP 工具做黑盒验收——不查看/修改源码，不执行本地 `tools/test_*.py`、`dev_check.py`、单测或源码探针，不读本机配置补齐细节；无法由 MCP 观察的内部机制记为“未验证”。开发者测试与 WorkBuddy 验收分别记录，互不替代。

## 提交、合入 main 与 Release（项目全局）

- 开发使用 `codex/<条目>-<主题>` 短分支，提交标题指明条目 ID 与变更。能力变化同步更新文档。
- 合入或直接提交 `main`（含文档、工程配置）必须同流程发布新版本 GitHub Release，并核对远端提交、标签、附件及 SHA256。版本以 `version.py` 为准；准备、验收及收尾见[发布流程](docs/development/RELEASING.md)。

## 配置、许可与本机实机常设授权

- `config.json`、`client-config.json`、`native/constants.inc`（由 `tools/generate_constants.py` 生成）不得提交或进入发布包；保留第三方许可，不提交 PTC SDK/许可数据（DEV-092 `references/creo13.4.0.0-sdk/` 仅作本地查证例外，见 [GOVERNANCE_HISTORY.md](docs/development/GOVERNANCE_HISTORY.md)）。
- **本机实机常设授权（2026-11-19）**：无需逐次确认，即可新建 Toolkit 连接、启动/重启 Creo 与 nmsd、结束卡死或异常 Creo/worker 进程（先确认无残留 worker 并记录原因）、清理残留 `toolkit.lock` 与 `unknown` 保护状态、编译执行器、建模、GUI 操作及几何/保存重载验收；不得删除或改写用户模型、历史证据与已发布产物。
