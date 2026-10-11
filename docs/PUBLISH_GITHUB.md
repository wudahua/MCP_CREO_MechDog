# 发布 MIT 源码安装版

本项目已提供 MIT 许可证及第三方声明。公开内容为本项目源码、安装脚本、说明、示例和测试；使用者在自己的 Windows 电脑安装和运行。

## 2026-10-11 建模增量

版本暂沿用 0.2.4，本次增量的公开源码包包含 `seed_library/` 下三个项目原创 MIT PRT。更新仓库时把完整上传目录的内容放入仓库根目录，包括 `seeds.py`、`airfoil.py`、`native/placement.cpp`、`native/sketch_edit.cpp`、新测试及说明。使用本次新命名 ZIP 和校验码，保留旧发布附件和标签。新 Release 的标签/版本由维护者决定，不自动改写旧标签；当前能力见 [增量说明](PORTABLE_MODELING_2026-10-11.md)。

## 原始 0.2.4 发布流程（历史）

`MCP_CREO_MechDog-0.2.4-source.zip` 收录当前源码，包括2～20 张平行 XY 截面的原生实体混合种子复用工具，种子数量和模式须匹配，详见 [LOFT_SEED.md](LOFT_SEED.md)。已发布的旧 `MCP_CREO_MechDog-0.22-source.zip` 和 GitHub v0.22 保留为历史版本。

更新仓库根目录的公开源码后，新建标签 **v0.2.4**，标题填写 **MCP_CREO_MechDog 0.2.4 — MIT 源码与混合种子库**，发布说明使用 [RELEASE_NOTES_0.2.4.md](RELEASE_NOTES_0.2.4.md)。当前仍有未完成操作，保留 **Pre-release** 标记。本地生成源码包不会自动上传 GitHub。

本次 Release 上传四个附件：

- `MCP_CREO_MechDog-0.2.4-source.zip`
- `MCP_CREO_MechDog-0.2.4-source.zip.sha256`
- `MCP_CREO_MechDog-0.2.4-seed-library.zip`
- `MCP_CREO_MechDog-0.2.4-seed-library.zip.sha256`

在 Releases 中新建发布，或在允许编辑附件的已有发布中添加种子库 ZIP 和校验码，上传到附件区域后发布或更新。使用附带的 `GITHUB_RELEASE_说明.md` 可给现有说明追加种子库内容。GitHub 自动生成的 Source code ZIP 不含仅作为 Release 附件上传的种子，说明中应明确要求普通混合用户同时下载源码和种子两个包。[GitHub 官方发布说明](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

种子库包括项目原创 PRT、MIT 许可证、清单、校验、路径解析器和迁移说明，详见 [SEED_LIBRARY.md](SEED_LIBRARY.md)。也可把种子库目录里的内容放到仓库 `seed_library/`，但仍推荐保留独立 Release 附件。公开源码包及 GitHub 源码上传目录保持源码内容，不自动混入原生 PRT。安装器不会自动下载或注册种子；使用者或 Agent 需读取库清单并填写本机绝对路径。跨电脑、跨 Agent 步骤见 [MIGRATION.md](MIGRATION.md)。

## 历史 0.21：用网页发布仓库

1. 登录 GitHub，点击 **New repository**。仓库名填写 **MCP_CREO_MechDog**，可见性选择 **Public**。描述可填写：`Local MCP server for native parametric modeling in Creo 10: sketches, extrude, revolve, holes and editable feature trees.`
2. 创建空仓库：不要勾选自动生成 README，也不要再选 `.gitignore` 或许可证模板；源码已经包含这些文件。
3. 解压 `MCP_CREO_MechDog-0.21-source.zip`。进入里面的 `MCP_CREO_MechDog` 文件夹，确认能看到 `LICENSE`、`README.md`、`server.py`、`setup.ps1`、`.gitignore` 等。
4. 在空仓库页面点击 **uploading an existing file**；已有仓库使用 **Add file → Upload files**。拖入该文件夹里面的文件和子文件夹，确保它们进入仓库根目录，避免多套一层 `MCP_CREO_MechDog/`。特别确认 `.gitignore` 也被上传。
5. 提交说明填写 `Add 0.21 modeling tools`，点击 **Commit changes**。检查仓库主页能显示 README，并且 LICENSE 被识别为 MIT。

浏览器上传有单文件大小和每批数量限制；本次完整目录为 113 个文件，网页上传应分批，或使用 Git/GitHub Desktop 上传完整目录。[GitHub 官方上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)

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
