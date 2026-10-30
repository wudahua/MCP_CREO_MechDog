# DEV-052 / N05 实机预检中止记录

日期：2026-10-30 23:28（Asia/Shanghai）。分支 `codex/dev051-feedback070`，受测源码提交 `d2a6888d43e25180472cdfdb92f082af81033405`；执行前工作区已有他人未提交内容，故提交号不能单独代表本机状态。`build/source.sha256=47a6591d17b8ef6b81530963ea2096e2b424892be3e4b1dba378c64cd93a1d8b`，本次未构建或替换 worker。

## 会话准备与停止点

- 执行前 `tasklist` 未见 `parametric.exe`、`xtop.exe`、`nmsd.exe`、`pro_comm_msg.exe`。本机 `config.json` 位于 E 盘工作目录，`creo_root=C:\Program Files\PTC\Creo 12.4.0.0`；`auto_start_creo` 前后均为 `false`，未改配置。`client-config.json` 只有 `MCP_CREO_MechDog_dev`，command/args 均指向 E 盘此仓库。
- `creo_startup.py` 协调器在该守卫值下不自动拉起。调用同模块 `Settings.load()` 和受限 `launch_creo()`，经当前用户 Explorer 以安装内 `parametric.psf` **请求启动一次**，没有重复请求。23:26:24—27 出现 `parametric.exe` PID 25596、`xtop.exe` PID 21968、`nmsd.exe` PID 11824、`pro_comm_msg.exe` PID 23448。23:27:20 的只读窗口观察为 `xtop` 有 1 个可见顶层窗口、`IsHungAppWindow=false`；这不证明菜单、视图或模态框可操作。
- GUI 控制接口报原始错误 `Computer Use native pipe is unavailable: failed to connect native pipe: 系统找不到指定的文件。 (os error 2)`。无法完成 BUG-091 所要求的人工 GUI 可操作核对。只读模型登记扫描还发现两个既存 `unknown_outcome`：`b8006f902e1e4d5f8a2ad7cd0123952b`（文件修改时间 10/14）、`d4e276f3cab74755a2ddf0e830571e73`（10/21）。未判断其处置状态，未清除保护。历史 `build/toolkit_health.json` 的检查时间是当日 14:20:10 +08:00，不作为此新会话就绪证据。
- 依 BUG-001 / BUG-091 前置与立即停止条件，**实机未验—会话不可用性未排除**。未调用 `creo_startup_status` / `creo_session_status`，未进行新 Toolkit 连接；没有以“进程存在”代替 `ready/connected=true`。Creo 进程保持运行，未结束、重启或清 unknown。

## N05 判定

预定命令 `.\.venv\Scripts\python.exe tools\test_sheetmetal_box_live.py --live --confirm-session-usable --output build\post090_n05_live_<runid>\report.json` **未执行**。独立预检报告为 `build/post090_n05_live_20261030T232751/report.json`，SHA256 `61AA5FF83CEC3277D30E3A61646553BA4D8867161FD8F0E603CEAB65E4C04E88`；该文件是本次预检记录，不是驱动结果，不入库。

trim 的 `setback_from_ends`、`length_from_section`、`length_both_sides`、`trim_ignored` 四候选均**未实测**；trimmed_20 未提交。`ny_first`、`px_then_ny`、`px_nx_then_ny` 均未运行，job_id/model_id/revision/终态/几何量测/`FLANGE_FAILURE_EVIDENCE`/保存重载均无本次值。触发条件本次未复现也未反证；四壁能力未完成。N06 的内部机理仍未定，本次没有新原生字段可用于判定截面越界或相邻料重叠。

本次未测：全部 N05 live 项、Creo 9/10、WorkBuddy 黑盒。后续实机负责人须先独立核对 GUI、当前保护状态与会话就绪，再决定是否允许新提交；不得把本报告当作放行依据。
