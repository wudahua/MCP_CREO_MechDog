# 发布 MIT 源码安装版

本项目已提供 MIT 许可证及第三方声明。公开内容为本项目源码、安装脚本、说明、示例和测试；使用者在自己的 Windows 电脑安装和运行。

## 当前开发版 0.22

当前新增能力位于 `MCP_CREO_MechDog-0.22-source.zip`。如需发布这次开发进展，上传这个包内的文件到仓库根目录，提交说明用 `Add 0.22 drawing, surface and UDF tools`；使用独立标签 `v0.22` 并标记 Pre-release，说明见 [开发版说明](RELEASE_NOTES_0.22.md)。不要替换已经发布的 v0.21 标签及其附件。所有新工具的支持范围及未完成项须保留。此处只提供发布操作方法；本轮开发没有自动修改 GitHub。

## 历史 0.21：用网页发布仓库

1. 登录 GitHub，点击 **New repository**。仓库名填写 **MCP_CREO_MechDog**，可见性选择 **Public**。描述可填写：`Local MCP server for native parametric modeling in Creo 10: sketches, extrude, revolve, holes and editable feature trees.`
2. 创建空仓库：不要勾选自动生成 README，也不要再选 `.gitignore` 或许可证模板；源码已经包含这些文件。
3. 解压 `MCP_CREO_MechDog-0.21-source.zip`。进入里面的 `MCP_CREO_MechDog` 文件夹，确认能看到 `LICENSE`、`README.md`、`server.py`、`setup.ps1`、`.gitignore` 等。
4. 在空仓库页面点击 **uploading an existing file**；已有仓库使用 **Add file → Upload files**。拖入该文件夹里面的文件和子文件夹，确保它们进入仓库根目录，避免多套一层 `MCP_CREO_MechDog/`。特别确认 `.gitignore` 也被上传。
5. 提交说明填写 `Add 0.21 modeling tools`，点击 **Commit changes**。检查仓库主页能显示 README，并且 LICENSE 被识别为 MIT。

浏览器上传有单文件大小和每批数量限制；本版源码包在相应限制内。[GitHub 官方上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)

仅上传上述公开包中的内容。工作环境的 `config.json`、`client-config.json`、`.venv/`、`build/`、`jobs/`、`models/`、生成的 `native/constants.inc` 不在公开包内。不要使用早期未清理的 ZIP。

已有 0.2.0 仓库时，用 0.21 公开源码更新仓库根目录中的文件，并上传新增的 `version.py`、`capabilities.py`、`native/advanced.cpp`、0.21 文档、示例和测试。提交说明填写 `Add 0.21 modeling tools`。不要把整个 `MCP_CREO_MechDog-0.21-source` 外层文件夹上传成仓库子目录。检查主页显示 0.21 的 README，随后再创建 `v0.21` 发布。

## 建立 0.21 Release

1. 在仓库页面进入 **Releases → Draft a new release**。
2. 新建标签 **v0.21**，Target 选择实际默认分支，标题填 **MCP_CREO_MechDog 0.21 — MIT 源码预发布候选版**。
3. 将 [RELEASE_NOTES_0.21.md](RELEASE_NOTES_0.21.md) 的内容复制到发布说明。
4. 附加 `MCP_CREO_MechDog-0.21-source.zip` 及对应 `.zip.sha256`。GitHub 也会自动提供仓库标签的 Source code 下载。
5. 将 0.21 标记 **Pre-release**：当前实测覆盖单台 Creo 10.0.0.0 环境，放样及所有 Creo 操作覆盖目标尚未完成。发布说明须保留能力边界。检查完成后点击 **Publish release**；需要稍后发布时使用 **Save draft**。

[GitHub 官方 Release 说明](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

## 别人怎么使用

分享仓库主页或 Releases 页面。使用者下载源码，按 [INSTALL.md](INSTALL.md) 安装并将生成的 `client-config.json` 接入自己的 AI 客户端。使用者需要自己的 Creo、匹配 SDK、编译工具和可用的 Toolkit 许可；项目 MIT 许可不提供 PTC 软件许可。

## 可选：Git 命令发布

已安装 Git 并完成 GitHub 身份认证时，在干净的公开源码文件夹执行以下命令。将 `YOUR_GITHUB_NAME` 替换为实际账号，并先创建同名空仓库：

```powershell
git init -b main
git add .
git commit -m "Add 0.21 modeling tools"
git remote add origin https://github.com/YOUR_GITHUB_NAME/MCP_CREO_MechDog.git
git push -u origin main
```

如果 Git 提示缺少姓名或邮箱，先配置自己的 Git 提交身份。认证时使用 GitHub 支持的方式，不把访问令牌写入项目文件。创建空仓库时不预先生成 README、许可证或 `.gitignore`，可避免初始提交冲突。[GitHub 官方本地代码导入说明](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github?platform=windows)
