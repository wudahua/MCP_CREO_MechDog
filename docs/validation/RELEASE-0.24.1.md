# 发布记录 0.24.1（2026-11-13）

本文件是 0.24.1 的发布记录。发布后结论以 [GitHub Release v0.24.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.24.1) 正文、[统一 POSTCHECK](../development/RELEASE-POSTCHECK-2026-11-07.md) 的 `## v0.24.1` 段与本文件「发布核对」段为准；源码包内的本文件是打包时点的快照。

## 版本与范围

- 版本：`0.24.1`（PATCH），源码版本以 [version.py](../../version.py) 为准。
- 公开工具：107（与 0.24.0 相同；无新增工具，`config.json` 新增 `creo_startup_args` 与 `creo_worker_launch` 两个可选键）。
- 交付内容：[BUG-125](../work-items/BUG-125.md) 启动参数经 `parametric.exe` 传给 `xtop.exe`；[BUG-126](../work-items/BUG-126.md) 无图形会话的 `ProWindowActivate` 失败只记 `window_activate_code`；[BUG-127](../work-items/BUG-127.md) `creo_worker_launch` 三段配置与 `-4` 时经 Explorer 隐藏复核一次 worker；[BUG-128](../work-items/BUG-128.md) `toolkit_hint` 区分 `-4`/`-38` 与探针退出码 20；[DEV-089](../work-items/DEV-089.md) 安装文档补编译工具链实物预检与 Creo 13.4 编译层实测分节。
- 反馈来源：下载目录 `0.23.1` 的 `2026-11-12-Creo13.4.0.0-MCP0.23.1-Toolkit连接-4与驱动蓝屏.md`；报告基于 0.23.1（107 工具），本轮在 0.24.0 代码线上重新实施并验收。
- 验收证据：[STARTUP-HEADLESS-2026-11-13](STARTUP-HEADLESS-2026-11-13.md)。

## 修复与门禁

- `creo_startup.py`：`Settings` 新增 `startup_args`，`config.json` 的 `creo_startup_args` 必须是字符串数组、元素为非空字符串、含 `\r`/`\n`/`\0` 时拒绝启动；参数加在 PSF 之后传给 `parametric.exe`，因为 PSF 的 `RUN=` 追加会被丢弃、复制 PSF 又会破坏 `%CREOAPP_DIRECTORY%` 推导。
- `native/worker.cpp`：`create_plate()` 末尾的 `ProWindowActivate` 从「必须成功」改为记录返回值，结果新增 `window_activate_code`（`0` 为正常会话、`-8` 为无图形会话）；成功判定仍要求几何断言与 `saved_file_reloaded_and_verified=true`。
- `desktop_worker.py`（新增）与 `creo_startup.py`：新增 `creo_worker_launch`（`auto`/`direct`/`desktop`，缺省 `auto`）。`auto` 先直连，仅当直连返回 `toolkit_code=-4` 时经同一个 Explorer 以隐藏窗口复核一次；桌面路径失败、超时或仍为 `-4` 时保留直连结果并附 `desktop_retry`。只影响状态探针，建模作业仍用直连子进程；许可值不写入临时脚本。
- `bridge.py`：`session_status` 返回值新增 `worker_launch` 与 `toolkit_hint`（`-4` 明确不是许可或版本问题、`-38` 指向模态框、`worker_exit_code=20` 说明是探针失败约定），文本不含本机路径、许可值或命令行。
- 打包白名单与运行时身份表补 `desktop_worker.py`：该模块由 `bridge.py` 延迟导入，此前既不在 `tools/package.py` 的显式白名单（源码包缺文件，包内桌面路径 `ImportError`），也不在 `server._SOURCE_NAMES`（源码变更指纹不覆盖它）；同时新增根级模块覆盖测试，防止同类遗漏再次进入发布包。
- 记录门禁：`docs/seed_manifest.json` 与 `seed_library/seed_manifest.json` 的 `compatible_server_version` 同步为 `0.24.1`；`docs/seed_package.json` 回填本版种子包名与摘要；`tools/check_release_records.py --version 0.24.1` 通过后打包。

## 验证

### 离线

- 全量单测 3570 项，3567 通过；`unit.test_inspection_only_admission` 3 项在本机因 `.tmp` 下 `runner.log` 被占用（`WinError 32`）失败，未含本版改动的基线同样复现，属本机环境问题。
- `tests/unit/test_creo_startup_args.py` 5 项通过（缺省为空、顺序保留、五类非法输入拒绝、两类参数拼接）。
- `tools/check_backlog_counts.py`：`consistent=true`、`problems=[]`，表行 185（BUG 83 / FEAT 64 / DEV 38）。
- `tools/check_release_records.py --version 0.24.1`：打包前记录门禁通过。

### 实机

- 环境：Windows x64 / Creo 12.4.0.0（`release_numeric=44`）/ 匹配 SDK / MSVC x64；`.venv` Python 3.13.14；受测源码为 0.24.0 提交 `03b884d` 加本轮工作树改动（`dirty=true`）。
- GUI 会话：板件 100×60×5、R8、φ10，job `3e57c202ec71417d92d92d2538789797` `succeeded`，体积 29332.6105317228 / 29332.61056745 mm³（相对差 3.6e-5），保存重载通过，`window_activate_code=0`。
- 无图形会话（`creo_startup_args=["-g:no_graphics","-i:rpc_input"]`）：板件 80×40×4、R6、φ8，job `907995ee2b394ec4ad9348cbbb64b912` `succeeded`，体积 12475.327397219 / 12475.3274122872 mm³（相对差 1.5e-5），预览生成，保存重载通过，`window_activate_code=-8`。
- `creo_worker_launch` 两路径各探针一次：`direct` 与 `desktop` 均 `connected=true`、`toolkit_code=0`、`release_numeric=44`、`desktop_retry=null`。
- 启动参数核对：配置后 `xtop.exe` 命令行含 `-g:no_graphics -i:rpc_input -ppid <pid>`，未配置时为 `-ppid <pid>`；参数没有写进 PSF。

## 未测范围

- Creo 13.4.0.0 运行期（本机无该版本 SDK，仅编译层由报告方证实）；Creo 9/10 的启动参数与无图形行为。
- 报告宿主（WorkBuddy + Job Object）下 `creo_worker_launch="desktop"` 的实际效果；[BUG-005](../work-items/BUG-005.md) 的 `-4` 是否因此清零仍未验证。
- `generic.cpp`、`drawing.cpp` 等其它原生路径的同名窗口调用；无图形会话下的交互式界面操作。
- `-38` 与真实模态对话框的对照；非毫米单位；WorkBuddy 黑盒。

## 打包

- 顺序：`tools\package_seeds.py --output build\dist\MCP_CREO_MechDog-0.24.1-seed-library.zip` → 回填 `docs/seed_package.json` → 重建确认摘要不变 → `tools/package.py`（内置四附件与发布记录门禁）→ 打标签并发布 → `tools\check_release_assets.py --tag v0.24.1`。
- 种子包 SHA256 `ee15813b935e14f7f84c49ea80160c28b45b18947f8b87bcdd5a297a40ce365d`（24 个文件、9 个种子、493 442 字节）；回填后本地重算摘要一致，包内 `seed_manifest.json` 的 `compatible_server_version` 为 `0.24.1`。
- 源码包 `MCP_CREO_MechDog-0.24.1-source.zip` 由发布提交源码构建，字节数与 SHA256 只写入同名 sidecar 与 Release 正文，不写入包内文件（ZIP 不能包含自身摘要）。
- 本版改了 `native/worker.cpp`，升级后必须重编 worker（重跑 `setup.ps1` 或 `python bridge.py build`），旧 worker 不会报告 `window_activate_code`；改了 `creo_startup_args` 或 `creo_worker_launch` 后必须重启 MCP 服务，两个键不参与原生构建指纹。

## 发布核对

本版发布四个附件（逐个列出，不使用通配）：

- `MCP_CREO_MechDog-0.24.1-source.zip`
- `MCP_CREO_MechDog-0.24.1-source.zip.sha256`（源码包摘要记录在同名 sidecar 中，内容为一行 `<64 位 SHA256>  文件名`）
- `MCP_CREO_MechDog-0.24.1-seed-library.zip`
- `MCP_CREO_MechDog-0.24.1-seed-library.zip.sha256`（种子包摘要同样在 sidecar 中）

- 种子包 SHA256：`ee15813b935e14f7f84c49ea80160c28b45b18947f8b87bcdd5a297a40ce365d`（24 个文件、9 个种子、493 442 字节，与 `docs/seed_package.json` 一致）。
- Release：[v0.24.1](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.24.1)，id `444282824`，非 draft、非 prerelease，`created_at=2026-11-13T13:46:35Z`，`published_at=2026-11-13T13:47:10Z`，target `main`（提交 `39c54ccf7689ac16e489082cd035082950f16de0`，标签对象 `f1f08ee3cb562279e45c4e57ac33a9d679497a8c`）。
- 核对命令：`tools\check_release_assets.py --tag v0.24.1` → exit 0，「four assets downloaded and verified; both sidecars match」；该命令同时解压源码包运行记录门禁并通过。
- 四附件（逐个上传，不用通配；远端 `sha256:` digest、本地重算与 sidecar 内容逐一致）：

| 附件 | 字节 | SHA256 |
| --- | ---: | --- |
| `MCP_CREO_MechDog-0.24.1-source.zip` | 10 125 185 | `b74672b5915f8733fd1e950e76aebbe25fe37bd988a72d23796a5584d3b2712b` |
| `MCP_CREO_MechDog-0.24.1-source.zip.sha256` | 101 | `b2d8b116d7288dcb429018491d197de4d692c39410536ebb05ea2ff6b59b7dfa` |
| `MCP_CREO_MechDog-0.24.1-seed-library.zip` | 493 442 | `ee15813b935e14f7f84c49ea80160c28b45b18947f8b87bcdd5a297a40ce365d` |
| `MCP_CREO_MechDog-0.24.1-seed-library.zip.sha256` | 107 | `98d9a250872b84c6a7dbb04f049177d4fda39b536b5902c131fcc063a0e45ced` |

- 重建核对：在发布提交的干净克隆中重跑两个打包脚本，种子包摘要仍为 `ee15813b…`（确定性构建）；源码包 1853 个成员中 1851 个 CRC 与发布包相同，差异仅 `native/third_party/json.hpp` 与 `LICENSE.nlohmann-json` —— 工作树保留供应商 CRLF 原件、仓库 blob 为 LF，第三方原件未改动，与 0.24.0 包的处理一致。ZIP 内文件时间戳不参与摘要比对。
- 本版未连接 Creo 复跑、未在报告宿主（WorkBuddy）上验证 `desktop` 路径；实机数据属于 0.24.1 交付前取得的当次会话，实际发布结果只回填到 `main` 的本段与 POSTCHECK `## v0.24.1` 段，不回写包内快照。

## 逐 ID 状态核对

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 差异说明 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [BUG-005](../work-items/BUG-005.md) | 观察中（本版不涉及：`desktop` 复核只提供对照路径，不清零宿主 `-4`） | 未排期 | 新现场再查 | 观察中 | 观察中 | 无 | 已列入 | 已列入 | `v0.24.1` |

## 归档项交付核对

本批五项无保留范围，按台账规则直接归档至[完成档案](../BACKLOG_COMPLETED.md)；金额、job 与体积数据见 [STARTUP-HEADLESS-2026-11-13](STARTUP-HEADLESS-2026-11-13.md)。

| 工作卡 | 交付版本 | 技术状态 | 剩余范围 |
| --- | --- | --- | --- |
| [BUG-125](../work-items/BUG-125.md) | 0.24.1 | 已交付：`creo_startup_args` 经 `parametric.exe` 传到 `xtop.exe`，`test_creo_startup_args.py` 5 项通过 | 无 |
| [BUG-126](../work-items/BUG-126.md) | 0.24.1 | 已交付：`window_activate_code` 只记录不判失败，无图形与 GUI 两态均 `succeeded` | 其它原生路径的同类窗口调用 |
| [BUG-127](../work-items/BUG-127.md) | 0.24.1 | 已交付：`creo_worker_launch` 三段配置与 `-4` 复核，两路径均 `toolkit_code=0` | 报告宿主下的实际效果（未测） |
| [BUG-128](../work-items/BUG-128.md) | 0.24.1 | 已交付：`toolkit_hint` 区分 `-4`/`-38`/退出码 20，文本不含本机路径与许可值 | `-38` 与真实模态框对照 |
| [DEV-089](../work-items/DEV-089.md) | 0.24.1 | 已交付：`INSTALL.md` 编译工具链实物预检与 `COMPATIBILITY.md` Creo 13.4 编译层实测分节 | 无 |

## 相对上一正式包核对（上一版本：0.24.0）

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| `native/third_party` 原字节（含 `json.hpp`、第三方许可） | 0.24.0 源码包 | 未改动 | 无需重新注册 |
| 回调指纹（`sha256-repo-lf-v1`） | 0.24.0 源码包 | 未改动 | 无需重新注册 |
| loader DLL SHA256 | 未单独留存 | 未单独留存 | 本版未改 loader；安装后随 worker 重建 |
| callback DLL SHA256 | 未单独留存 | 未单独留存 | 本版未改 callback；安装后随 worker 重建 |
| worker SHA256 | 未单独留存 | 由本次源码重新编译 | 本版含 `native/worker.cpp` 变更，升级后必须重建 |
| `protk.dat` / 注册表路径 | 0.24.0 | 未改动 | 无需迁移 |
| 种子库 | 9 个种子（`compatible_server_version=0.24.0`） | 9 个种子（`compatible_server_version=0.24.1`） | 文件集不变，仅清单版本号随包 |
| 单测 | 3548 | 3570 | `tools/dev_check.py` 全量运行 |
