# GitHub 更新与源码发布（0.2.5 历史示例）

以下目录、附件名和升级检查仅适用于 v0.2.5。发布新版本请使用[现行发布流程](development/RELEASING.md)。

## 更新仓库文件

1. 使用 `MCP_CREO_MechDog-0.2.5-github-upload` 内的**内容**更新仓库根目录。根目录应直接看到 `README.md`、`server.py`、`setup.ps1`，不要再包一层目录，也不要把整个源码 ZIP 当成仓库源码上传。
2. 同步所有公开文件与目录，包括 `native/`、`tools/`、`tests/`、`examples/`、`docs/` 和完整 `seed_library/`。用 Git 或 GitHub Desktop 更新整个目录更便于核对；网页上传时可分批提交。[GitHub 上传文件说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
3. 提交说明可填写 `Release v0.2.5: native Blend, sketch stability and nine seeds`。不要上传本机 `config.json`、`client-config.json`、`.venv/`、`build/`、`jobs/`、`models/` 或 SDK/许可材料。
4. 检查根目录 `version.py` 为 `VERSION = "0.2.5"`；两个种子清单版本一致，均有九个条目。新 PRT 原文件名及 `.prt.N` 后缀保持不变。

## 新建 Release

仓库源码更新完成后，新建标签 **v0.2.5**，选择包含本次源码的提交。标题填写 **MCP_CREO_MechDog v0.2.5 — MIT 源码与九种子库**，说明使用 [release-notes/RELEASE_NOTES_0.2.5.md](release-notes/RELEASE_NOTES_0.2.5.md) 的内容。完整 Creo 覆盖尚未完成，建议保持 **Pre-release**。

v0.2.5 示例使用以下四个附件。

- `MCP_CREO_MechDog-0.2.5-source.zip`
- `MCP_CREO_MechDog-0.2.5-source.zip.sha256`
- `MCP_CREO_MechDog-0.2.5-seed-library.zip`
- `MCP_CREO_MechDog-0.2.5-seed-library.zip.sha256`

源码 ZIP 已内附九个种子；独立种子 ZIP 是迁移用途，不是额外必需下载。只有仓库也包含 `seed_library/` 时，GitHub 自动生成的 Source code ZIP 才包含这些 PRT；附件内容不会自动加入仓库。旧 v0.2.4 三种子附件保留为历史，不能替代新版库。发布操作见 [GitHub 官方说明](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。

## 用户升级

等待正在运行的任务完成，停止客户端中的 MCP 服务，保留本机配置、`models/` 和 `jobs/`，更新公开源码并重跑 `setup.ps1`。重启客户端，检查 `creo_capabilities.version == "0.2.5"`、80 个可用工具及九个种子。安装与跨电脑说明见 [INSTALL.md](INSTALL.md)、[MIGRATION.md](MIGRATION.md)。
