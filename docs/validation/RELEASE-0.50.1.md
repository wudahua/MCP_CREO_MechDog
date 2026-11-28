# 发布记录 v0.50.1

2026-11-28 PATCH，公开工具数 112。上一版本：0.50.0（`v0.50.0`，提交 `16386157e477b424737cccf66076a3c8f204a036`）。

## 验收范围

交付 [DEV-114](../work-items/DEV-114.md)：`spawn_detached_runner` 以实际选用的进程工厂判断是否需要经 Explorer 脱离 Job Object。此前只检查调用方是否显式传入 `popen`，托管 Windows CI 的作业清理测试在替换工厂后仍被判为真实启动并走桌面启动器，导致 `TemporaryDirectory` 清理报 `WinError 32/5`。

本机 Windows x64 / Python 3.12.10（进程处于 Windows Job Object）：

- 在干净基线 `2eda43f7` 上通过 `python -m unittest tests.test_registry_io.RegistryJobs.test_legacy_job_queue_and_terminal_use_atomic_writer tests.unit.test_toolkit_channel.ToolkitChannel.test_plate_and_generic_submissions_share_one_reservation` 复现 2 项清理错误；仅拦截 `desktop_worker.launch_detached_command` 时两例均通过，各捕获一次以对应临时目录为 cwd 的 `bridge.py run-job`。
- 修复后两项复现用例与 BUG-199 所在模块共 17 项通过；四个独立 Python 进程各循环 25 轮上述两例共 200 次，0 错误、0 失败、0 次 Explorer 启动。新增回归在 Job Object 中显式模拟自动桌面启动条件，验证默认工厂被替换后仅调用替身；原有 BUG-199 正向用例继续验证真实工厂的 Explorer 路由，原子写、单通道互斥与失败清理断言保留。
- 本版仅涉及启动器与单元测试隔离，未进行 Creo 建模。

单元回归：本轮 `tools/test_unit.py` 全量通过（4,615 项，6 跳过，0 失败，0 错误，`success=true`，`run_id=8ef443c4c1a147cd8639ea450cff591c`，`source_fingerprint=3910ee201388159f4bdca4d0a8186ef352eb9031be2714d2e0caf26d07937549`，受测提交 `d9d8a3c26b5f15d8e89799016028f0fa29dfb950`，`dirty=true`）。

静态与离线门禁：`tools/dev_check.py --skip-unit --work-item DEV-114` 通过（`dirty=true`、`checked_source_sha256=32562da41a2a7bc05e36003a23f2bde2f9ec9e045b5ebb469ec04f1df08696b3`、0 lint / 0 unformatted、71 个 C++ 与 617 个 Python 文件、`3/3` 离线验收通过）。

制作源码包的条件是本轮全量单测通过，打包时核验报告、运行 ID 及提交对应的源码指纹。另执行完整 `tools/dev_check.py`（含风格、链接、计数、契约门禁），并在源码 ZIP 解包后独立运行 `tools/test_unit.py`。最终受测提交、命令、运行标识及结果见 Release 正文和[发布后核对记录](../development/RELEASE-POSTCHECK-2026-11-07.md)。

未测范围：Creo 9 / 12.4 实机与外部 WorkBuddy 黑盒；本版未改动几何或建模路径，不复用历史版本的建模验收结论。

## 逐 ID 状态核对

[主台账](../BACKLOG.md) · [开发入口](../DEVELOPMENT.md) · [版本说明](../release-notes/RELEASE_NOTES_0.50.1.md)

| ID | 交付版本 | 实际 Release | 技术状态 | 卡首页 | 主台账 | 差异说明 |
| --- | --- | --- | --- | --- | --- | --- |
| DEV-114 | 0.50.1 | v0.50.1 | 已有修复但待验收 | 已有修复但待验收 | 已有修复但待验收 | 修正 runner 工厂识别，Windows 两项清理用例并发 200 次 0 错误；托管 Windows CI 全量复核进行中。 |

## 附件与远端核对

- `MCP_CREO_MechDog-0.50.1-source.zip`
- `MCP_CREO_MechDog-0.50.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.50.1-seed-library.zip`
- `MCP_CREO_MechDog-0.50.1-seed-library.zip.sha256`

种子包 SHA256 为 `db2adcbb8893dd64194a22b9079f2350d1f87797ce9d178bc0d57d7dc3565b35`。两份同名 sidecar 分别记录各自 ZIP 的摘要。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.50.1)
