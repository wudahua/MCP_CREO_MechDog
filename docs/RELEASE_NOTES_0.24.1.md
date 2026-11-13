# MCP_CREO_MechDog 0.24.1

一句话：把启动和连接这两步从"只能猜、只能重试"变成"可以配、可以复核"——Creo 能带 `-g:no_graphics` 启动并在无图形会话里完成建模，`-4` 可以经 Explorer 复核一次，错误码会自己说明它是进程上下文、模态框还是探针退出约定。

- 类型：PATCH（新增可选配置与只读诊断字段，不改既有取值与接口兼容性）
- 日期：2026-11-13
- 公开工具：**107 个**，与 0.24.0 相同
- 主台账：[BACKLOG](BACKLOG.md) · 发布记录：[RELEASE-0.24.1](validation/RELEASE-0.24.1.md) · 验收证据：[STARTUP-HEADLESS-2026-11-13](validation/STARTUP-HEADLESS-2026-11-13.md)

## 对外可见变化

### 1. `creo_startup_args`：把参数交给 parametric.exe（BUG-125）

`config.json` 新增 `creo_startup_args`（字符串数组，缺省 `[]`）。参数加在 PSF 之后传给 `parametric.exe`，因为 PSF 里的 `RUN=` 追加会被丢弃，复制 PSF 又会破坏 `%CREOAPP_DIRECTORY%` 推导。

```json
"creo_startup_args": ["-g:no_graphics", "-i:rpc_input"]
```

校验：必须是数组、元素为非空字符串、含 `\r`/`\n`/`\0` 时拒绝启动。改配置需重启 MCP 服务；该键与 `creo_worker_launch` 不参与原生构建指纹，改它们不会触发重编。Creo 12.4 实测 `xtop.exe` 命令行出现同名参数、无界面。

### 2. 无图形会话不再必然建模失败（BUG-126）

`create_plate()` 末尾的 `ProWindowActivate` 从"必须成功"改为记录返回值。无图形会话没有可激活窗口，返回 `-8`，此前会让几何、存盘、重载全部通过的任务被判失败。

结果新增 `window_activate_code`：`0` 表示正常 GUI 会话，`-8` 表示无图形会话（不是几何失败）。成功判定不变，仍要求几何断言与 `saved_file_reloaded_and_verified=true`。

### 3. `creo_worker_launch`：`-4` 时经 Explorer 复核一次（BUG-127）

新增 `creo_worker_launch`：`auto`（缺省）、`direct`、`desktop`。`auto` 先直连；仅当直连返回 `toolkit_code=-4`（`PRO_TK_BAD_CONTEXT`）时，再经同一个 Explorer 以隐藏窗口启动一次 worker 复核。

- 桌面路径失败、超时或仍返回 `-4` 时，保留直连结果并附 `desktop_retry`（`"unavailable"` 或 `{"connected", "toolkit_code"}`），不改变既有错误码语义。
- `session_status` 返回值新增 `worker_launch`，指明本次实际走的是哪条路径。
- 只影响状态探针；建模作业仍用直连子进程。许可值不写入临时脚本，许可环境与桌面不一致时直接放弃该路径。

这条路径用于区分"worker 进程上下文"与"Creo/许可"问题，不等于修复 [BUG-005](work-items/BUG-005.md)：报告宿主（Creo 13.4 + WorkBuddy）的 `-4` 是否因此清零仍未验证。

### 4. `toolkit_hint`：错误码自己说明含义（BUG-128）

`session_status` 返回值新增 `toolkit_hint`：`-4` 明确"不是许可或版本问题"，`-38` 明确"先看 `xtop.exe` 窗口标题，重试不能清除模态框"，`worker_exit_code=20` 说明是探针的失败约定而非独立 Creo 错误码。文本不含本机路径、许可值或命令行。

## 文档

`docs/INSTALL.md` 新增「编译工具链实物预检」（`cl.exe`、`windows.h`、`kernel32.lib` 三条 `Test-Path`，`vs_installer --quiet` 无输出不等于卡死，`-VcVars64` 包装脚本与 SDK 升级后同步修改），补 `creo_startup_args` 无图形示例与四条排错项；`docs/COMPATIBILITY.md` 新增 Creo 13.4.0.0 编译层实测分节，明确不作支持声明（DEV-089）。

## 兼容与迁移

- 无需迁移：新增配置均有缺省值，既有 `toolkit_code`、`connection_state` 取值与含义不变，`session_status` 只增字段。
- 本版改了 `native/worker.cpp`，升级后必须重编 worker（重跑 `setup.ps1` 或 `python bridge.py build`），旧 worker 不会报告 `window_activate_code`。
- 改了 `config.json` 的启动参数或 worker 启动方式后必须重启 MCP 服务。

## 验收范围与环境

- Windows x64 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 SDK / MSVC x64；`.venv` Python 3.13.14。
- GUI 会话：`direct` 与 `desktop` 两条探针均 `toolkit_code=0`；板件 100×60×5、R8、φ10 建模 `succeeded`，体积 29332.6105317228 / 29332.61056745 mm³，保存重载通过，`window_activate_code=0`。
- 无图形会话（`-g:no_graphics`、`-i:rpc_input`）：连接 `toolkit_code=0`，板件 80×40×4、R6、φ8 建模 `succeeded`，体积 12475.327397219 / 12475.3274122872 mm³，保存重载通过，`window_activate_code=-8`、预览生成。
- 单元回归：3570 项，其中 3567 项通过；`unit.test_inspection_only_admission` 3 项在本机因 `.tmp` 下 `runner.log` 被占用（`WinError 32`）失败，在未含本版改动的基线上同样复现，属本机环境问题，详见发布记录。

## 未测范围

- Creo 13.4.0.0 运行期（本机无该版本 SDK）、Creo 9/10 的启动参数与无图形行为。
- 报告宿主（WorkBuddy + Job Object）下 `creo_worker_launch="desktop"` 的实际效果。
- `generic.cpp`、`drawing.cpp` 等其它原生路径的同名窗口调用；无图形会话下的交互式界面操作（该模式无界面）。
- `-38` 与真实模态对话框的对照；非 mm 单位；WorkBuddy 黑盒。

四个发布附件（源码包、种子包及各自 `.zip.sha256`）的文件名与摘要见[发布记录](validation/RELEASE-0.24.1.md)。
