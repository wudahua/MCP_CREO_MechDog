# Release 0.8.2 发布验收记录

日期：2026-10-29（Asia/Shanghai）。条目：[BUG-089](../work-items/BUG-089.md)。环境：Windows x64、PowerShell、仓库 `.venv` Python。工作分支 `codex/dev051-feedback070`，候选基线提交 `1d7d33b`；测试时工作区含本版允许的变更和用户保留的本机未提交文件，`dirty=true`。公开工具 94 个，无接口或建模能力变化。

## 缺陷与修复

0.8.1 两份种子清单仍声明 `compatible_server_version=0.8.0`，直接运行 `tools/package_seeds.py` 因 `manifest["compatible_server_version"] == VERSION` 断言失败（exit 1）。0.8.1 发布附件通过进程内版本覆盖构建，包内仍声明 0.8.0，SHA256 `4ed63b3deb40f9a60f237cab949ac9cf5a4bd1f188d0b78f7795c5bdc9d3f12b`。0.8.2 同步 `version.py` 和两份清单、增加仓库实物回归，并将 `seeds.py` 的 `expected_digest` 更新为新包哈希。种子列表、种子原始字节和各条 SHA256 未改。

## 离线验收

- 新测试先在 0.8.1 树运行：2 项中 1 项失败，实际为 `AssertionError: '0.8.0' != '0.8.1'`；改动后与相关 `test_seed_listing`、`test_seed_distribution` 合计 11 项通过。
- 原命令 `.venv\Scripts\python.exe tools\package_seeds.py --output <新路径>` 构建两次：每次 24 个文件、9 个种子；SHA256 均为 `4bdcccabb4cf384d546b8335283bb1c9424ad75cc6a450df58675cdbdb1a6e74`。回填 `expected_digest` 后第三次构建同哈希。0.8.2 种子包名为 `MCP_CREO_MechDog-0.8.2-seed-library.zip`。
- `.venv\Scripts\python.exe tools\dev_check.py`：首轮因新增测试文件导入顺序产生 `I001` 而 exit 1，单元阶段未运行；仅对该文件执行 Ruff 导入排序后重跑，exit 0、`success=true`、`unit_tests=passed`，单元报告 1343 项、0 失败、0 错误。存量风格摘要为 30 条 lint、16 个未格式化文件；未修改基线、未跳测试。
- `.venv\Scripts\python.exe tools\package.py --output <新路径>` 两次构建均包含 1034 个文件、SHA256 一致；包内 `version.py=0.8.2`、禁入路径 0、`feedback-0.7.2-2026-10-28` 文件 6 个，并包含两份声明 0.8.2 的种子清单。最终 ZIP 的完整 SHA256 与远端下载核对记录在 Release body 和交付报告，避免在源码包内形成自指哈希。
- 未修改原生源码，不重编。`build/creo_worker.exe` 起止 SHA256 均为 `f1d9990c7ac376b1007e49e1d87a3add76c10f5d192c3b9c3efe2655ad1f7305`；`build/source.sha256` 起止文件 SHA256 均为 `f77a7e26cf43b6c5d0a6f050966522c80fedd84ba686cd9ef500a8bb731d2a56`，文件内容 `5feaca7083bc704caa8dba36b5521b093dffbe8face8abd678f95e2dde9f2d88`。

全部 Creo 实机建模、Toolkit 连接、WorkBuddy、Creo 9/10 编译与运行均未执行；不将历史结果转作本版证据。主干提交、标签、正式 Release 和四附件远端下载核对将在 Release body 与交付报告记录，避免发布后追加自指 main 提交。
