# MCP_CREO_MechDog 0.50.1 版本说明

2026-11-28 PATCH，公开工具数 112。上一版本：0.50.0（`v0.50.0`，提交 `16386157e477b424737cccf66076a3c8f204a036`）。

- **DEV-114**：`spawn_detached_runner` 改为比较实际选用的进程工厂与原始 `Popen`，而不是只认调用方是否传参。托管 Windows CI 的作业清理测试虽替换了工厂，却仍被判为真实启动并路由到 Explorer 桌面启动器，导致旧式作业原子写与板件/通用作业共享预留两项用例在 `TemporaryDirectory` 清理时报 `WinError 32/5`；修复后替换工厂只走替身，真实工厂仍由既有 BUG-199 用例覆盖 Explorer 脱离路径。
- 新增回归用例在 Windows Job Object 中显式模拟自动桌面启动条件，断言默认工厂被替换后不再调用 `launch_detached_command`，同时保留原子写、单通道互斥与失败清理断言。

验收环境为 Windows x64 / Python 3.12.10。复现两例于基线 `2eda43f7` 的托管 Windows CI 失败记录；开发分支上两项用例与 BUG-199 所在模块共 17 项通过，四个独立进程各循环 25 轮共 200 次为 0 错误、0 失败、0 次 Explorer 启动；本地与托管 Windows 全量开发检查均通过。本版仅涉及启动器与单元测试隔离，未进行 Creo 建模，Creo 9 / 12.4 实机与 WorkBuddy 黑盒不在本版范围。[发布记录](../validation/RELEASE-0.50.1.md)

## 附件

- `MCP_CREO_MechDog-0.50.1-source.zip`
- `MCP_CREO_MechDog-0.50.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.50.1-seed-library.zip`
- `MCP_CREO_MechDog-0.50.1-seed-library.zip.sha256`

种子包 SHA256 为 `db2adcbb8893dd64194a22b9079f2350d1f87797ce9d178bc0d57d7dc3565b35`。源码包和种子包的摘要分别记录在同名 sidecar。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.50.1)
