# 0.24.1 启动参数、桌面复核与无图形建模证据（2026-11-13）

来源报告：`C:\Users\Administrator\Downloads\0.23.1\2026-11-12-Creo13.4.0.0-MCP0.23.1-Toolkit连接-4与驱动蓝屏.md`。报告基于 0.23.1（107 工具）；本轮在 0.24.0 代码线上重新实施并验收，条目见 [BUG-125](../work-items/BUG-125.md)、[BUG-126](../work-items/BUG-126.md)、[BUG-127](../work-items/BUG-127.md)、[BUG-128](../work-items/BUG-128.md) 与 [DEV-089](../work-items/DEV-089.md)。

环境：Windows x64 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 SDK，编译器由 `vcvars64_local.cmd` 提供；`.venv` Python 3.13.14。受测源码为 0.24.0 提交 `03b884d` 加本轮工作树改动（dirty=true），指纹与提交号以 [发布记录](RELEASE-0.24.1.md)为准。

## BUG-125：启动参数

- 配置 `"creo_startup_args": ["-g:no_graphics", "-i:rpc_input"]` 后重启服务，实际进程命令行：
  `"C:\Program Files\PTC\Creo 12.4.0.0\Common Files\x86e_win64\obj\xtop.exe"  -g:no_graphics -i:rpc_input -ppid 5100`。
- 对照未配置时：`...xtop.exe"  -ppid 20248`。参数确实由 `parametric.exe` 传到 `xtop.exe`，没有写进 PSF。
- 启动 `state=ready`、`toolkit_code=0`、`worker_launch=direct`；`parametric.exe` 与 `xtop.exe` 的 `MainWindowHandle` 均为 0。
- 离线回归：`tests/unit/test_creo_startup_args.py` 5 项通过（缺省为空、顺序保留、五类非法输入拒绝、两类参数拼接）。

## BUG-126：无图形会话的窗口激活容错

| 会话 | 规格 | job_id | 终态 | 体积 mm³ / 解析值 | 误差 | `window_activate_code` | `preview_code` | 保存重载 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 修复前（0.3.1 分支，见下） | 80×40×4，R6，φ8 | 0d7d3a5c034c469f8bc28ed37e6488e2 | failed（`toolkit_code=-8`） | 内存实测 12475.327397218973 / 12475.3274122872 | — | 未记录（旧实现直接判失败） | -1 | false |
| 0.24.1 无图形 | 80×40×4，R6，φ8 | 907995ee2b394ec4ad9348cbbb64b912 | succeeded | 12475.327397219 / 12475.3274122872 | 1.5e-5 | -8 | 0 | true |
| 0.24.1 GUI | 100×60×5，R8，φ10 | 3e57c202ec71417d92d92d2538789797 | succeeded | 29332.6105317228 / 29332.61056745 | 3.6e-5 | 0 | 0 | true |

失败会话的旧日志（0.3.1 分支）末尾依次为 `ProMdlDisplay=0`、`ProMdlWindowGet=0`、`ProWindowCurrentSet=0`、`ProViewMatrixSet=0`、`ProWindowRefit=0`、`ProWindowRepaint=0`，只有 `ProWindowActivate(win)=-8`，随后 `BUILD_FAILED=-8`。0.24.1 中该调用只写 `window_activate_code`，几何断言与保存重载仍是成功条件。

产物：无图形 `jobs/907995ee2b394ec4ad9348cbbb64b912/output/ai_plate_907995ee2b39.prt.2` 与 `preview.jpg`；GUI `jobs/3e57c202ec71417d92d92d2538789797/output/ai_plate_3e57c202ec71.prt.2`。

## BUG-127：worker 桌面复核

同一 Creo 12.4 会话内分别强制两条路径各探针一次（`bridge.session_status(5)`）：

| 路径 | connected | toolkit_code | release_numeric | worker_launch | desktop_retry |
| --- | --- | --- | --- | --- | --- |
| `direct` | true | 0 | 44 | direct | null |
| `desktop` | true | 0 | 44 | desktop | null |

另在无 Creo 会话时（0.3.1 分支与本轮切换间隙）验证过回退语义：直连 `-4`、桌面同样 `-4` 时保留直连结果并写 `desktop_retry={"connected": false, "toolkit_code": -4}`；桌面不可用写 `"unavailable"`。报告宿主（Creo 13.4 + WorkBuddy）的 `-4` 是否因此清零仍未验证，[BUG-005](../work-items/BUG-005.md) 保持原状。

## BUG-128：返回码提示

无会话探针返回的 `toolkit_hint`：

> `PRO_TK_BAD_CONTEXT: this worker process has no Toolkit context. That is a worker process-context failure, not a license or Creo version problem; compare creo_worker_launch modes before retrying. The probe exited 20; exit 20 is its convention for any failed connection, not a separate Creo error`

连接成功时返回 `Toolkit connection verified`。文本不含本机路径、许可值或命令行。`-38` 与真实模态对话框的对照未做。

## DEV-089：安装文档

`docs/INSTALL.md` 新增「编译工具链实物预检」（`cl.exe`、`um\windows.h`、`um\x64\kernel32.lib` 三条 `Test-Path`；`vs_installer.exe modify --quiet` 无输出不等于卡死；`-VcVars64` 包装脚本与 SDK 升级后同步修改）、`creo_startup_args` 无图形示例、`creo_worker_launch` 说明、四条排错项；`docs/COMPATIBILITY.md` 新增 Creo 13.4 编译层实测分节，明确不作支持声明。

## 未测范围

- Creo 13.4.0.0 运行期：仅编译层由报告方证实，本机无该版本 SDK。
- 报告宿主（WorkBuddy + Job Object）下 `creo_worker_launch="desktop"` 的实际效果。
- Creo 9/10 的启动参数与无图形行为；`generic.cpp`、`drawing.cpp` 等其它原生路径的同名窗口调用。
- 无图形会话下的交互式界面操作（该模式无界面）；`-38` 模态框对照。
