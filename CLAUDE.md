# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

与用户沟通一律使用中文（2026-11-11 用户要求）。

上面导入的 AGENTS.md 是仓库约束的权威来源（台账准入、Creo 实机放行确认制、WorkBuddy 黑盒约定、合入 main 必须同次发布 Release 等），本文件只补充它没写的操作细节，不重复其规则。开发入口见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)，唯一台账见 [docs/BACKLOG.md](docs/BACKLOG.md)，发布流程见 [docs/development/RELEASING.md](docs/development/RELEASING.md)。

## 命令（本会话 shell 是 Git Bash）

AGENTS.md 中的命令是 PowerShell 写法；在 Bash 中改用正斜杠：

```bash
.venv/Scripts/python.exe tools/dev_check.py --work-item <ID>                  # 统一门禁：Ruff/格式/基线比较 + 全量单测（3300+ 项，约 6–18 分钟）
.venv/Scripts/python.exe tools/dev_check.py --skip-unit                        # 只做语言检查
.venv/Scripts/python.exe -m unittest tests.unit.test_backlog_counts -v         # 单个 tests/unit 模块
.venv/Scripts/python.exe -m unittest tests.unit.<module>.<Case>.<test_method>  # 单个用例
.venv/Scripts/python.exe -m unittest discover -s tests -p test_job_query.py    # 根 tests/ 下待迁移模块（tests/ 不是包）
.venv/Scripts/python.exe -m ruff check <file>; .venv/Scripts/python.exe -m ruff format <file>
.venv/Scripts/clang-format.exe -i --style=file native/<file>.cpp
.venv/Scripts/python.exe tools/check_backlog_counts.py                         # CI 同样执行：台账计数自检
.venv/Scripts/python.exe bridge.py build                                       # 编译原生执行器（需本机 SDK + MSVC，不建模）
```

- 分拆运行的单测不能代替最终 `dev_check.py` 全量结论；单元阶段默认 900 s（`--unit-timeout-seconds` 调整），超时按未通过记。
- `tools/test_*.py` 是集成/离线驱动：多数默认只做离线契约检查，加 `--live --confirm-session-usable` 才会通过公开 MCP 工具驱动真实 Creo，必须先得到用户当次确认。部分驱动（如 `tools/test_assembly_pose.py`）用 `config.json` 的 vcvars64 编译 `tests/native/*.cpp`，只测与 SDK 无关的原生辅助头文件，不算建模证据。
- 从仓库根全量 Glob/Grep 容易超时（`jobs/`、`models/`、`build/`、`.venv/` 很大）；把搜索限定在 `src/`、`native/`、`tools/`、`tests/`、`docs/` 或根 `*.py`。`docs/validation/` 是逐字节冻结的历史原件，只读。

## 一次建模任务的进程链

1. `server.py`（FastMCP stdio）注册工具；lifespan 启动 `creo_startup.py` 的后台 Creo 协调器，客户端通过 `creo_startup_status` 等待 `ready`。
2. 提交类工具（如 `creo_execute_plan`）进入 `generic_bridge.py`：Pydantic 校验（`src/creo_mechdog/schema.py`）、能力准入（`capabilities.require_available`）、`expected_revision` 检查，然后在 `jobs/<job_id>/` 写 `request.json` 和 `job.json`、登记通道占用，派生一个**脱离的** `python bridge.py run-job <job_id>` 进程，立即返回 `job_id`。
3. runner（`bridge._run_job_dispatch`）按 `job.json` 的 `kind` 分派：`generic` → `generic_bridge.run_generic_job`；`adoption`、`adoption_file`、`open_file`、`session_erase`、`reconciliation` → `src/creo_mechdog/` 中对应模块的 `run()`。
4. runner 持 Toolkit 锁调用 `bridge.build_native()`：每次先重新生成 `native/constants.inc`，再用 LF 归一化后的原生源码、SDK 头和配置计算指纹；指纹变化时重编 `build/creo_worker.exe` 及回调 DLL（`creo_blend_sync.dll`、`creo_blend_loader.dll`），否则复用。
5. 运行 `creo_worker.exe generic <job_dir>`（有超时预算）；worker 连接 Creo、建特征、保存、重载核验，写出 `native_result.json`、`native.log` 和 `output/` 下的模型文件。
6. runner 收尾：无结果文件、断连或超时记 `unknown_outcome`（保留现场，禁止盲目重试）；`success` 且 `saved_file_reloaded_and_verified` 记 `succeeded` 并推进 model 的 revision；其余记 `failed` 并回滚。客户端只轮询 `creo_get_job`；`compact` 回执受 32 KiB 预算（`model_queries.RESPONSE_BUDGET`）裁剪，不可被裁的测量标量列在 `operation_results.OUTCOME_OPERATION_KEYS`。

## 原生代码的编译单元

`native/worker.cpp` 是执行器唯一的翻译单元：它文本 `#include` 了 `geometry.cpp`（再包含生成的 `constants.inc`）、`generic.cpp` 和 `drawing.cpp`；`generic.cpp` 又在文件中段和末尾 `#include` 几乎全部特征 `.cpp`（`advanced.cpp`、`surface_*.cpp`、`planar_wall.cpp`、`sketch_*.cpp` 等）。因此：

- 新特征 `.cpp` 要挂进 `generic.cpp` 的 include 序列，不能单独加入构建；文件之间共享 `static` 状态并依赖 include 顺序。这是迁移债务，由 DEV-003/004 处理，不要一次性拆分。
- 操作分派是 `generic.cpp` 中按 `kind == "<op>"` 展开的 if/else 链。
- `blend_sync.cpp`、`blend_loader.cpp` 是例外，单独编译成直接混合回调 DLL，见 [docs/CALLBACK_LIFECYCLE.md](docs/CALLBACK_LIFECYCLE.md)。
- 实际被包含的原生文本（含 `native/third_party/` 协作头）都计入构建指纹。

## 新增或扩展建模操作通常涉及的位置

可以参照 `surface_loft` 的链路：

- `src/creo_mechdog/schema.py`：操作模型。
- `src/creo_mechdog/capabilities.py`：`REGISTERED_OPERATIONS`、限值、`KNOWN_LIMITATIONS`/`PLAN_EXAMPLES`；依赖 worker 编译特性的操作放进 `WORKER_CONDITIONAL_OPERATIONS`。
- `generic_bridge.py`：计划校验。
- `server.py`：需要独立公开工具时注册一层薄包装。
- 原生：`generic.cpp` 分派加特征 `.cpp`。
- 结果投影：`operation_results.py`、`job_projection.py`。
- 测试：`tools/test_<feature>.py` 驱动和 `tests/unit/` 回归。
- 文档：README 工具数、[REFERENCE_SYNTAX](docs/REFERENCE_SYNTAX.md)、[COMPATIBILITY](docs/COMPATIBILITY.md)。

公开工具数以 `creo_capabilities` 返回的 `tool_count` 为准，单测会核对它与实际注册的工具一致。
