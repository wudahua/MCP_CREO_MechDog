# v0.2.4 原生混合种子库

“种子”是保存了完整原生 Blend / 混合的简单 Creo PRT 模板。`creo_new_loft_part` 复制它，创建新的参数草图，将混合改接到新截面并删除旧截面草图。源文件不改动，结果保留原生混合特征。普通草图、拉伸、旋转及孔工具使用本机 Creo 标准模板，不要求这种专用混合种子。

2026-10-11 建模增量源码内含 `seed_library/`，安装器自动验证并注册三个项目原创 MIT 种子。此前独立 Release 附件 `MCP_CREO_MechDog-0.2.4-seed-library.zip` 和 `.zip.sha256` 继续有效，可通过 `creo_install_seed_library` 注册解压目录，或在随包库不存在时安装原 ZIP。老的发布源码包不含这些 PRT，也没有自动匹配接口；请确认下载的是本次增量。

## 已验证内容

| name | 截面数 | 模式 | 原始文件内混合 ID |
| --- | --- | --- | --- |
| two_straight | 2 | straight / 直线 | 60 |
| two_smooth | 2 | smooth / 平滑 | 60 |
| five_smooth | 5 | smooth / 平滑 | 93 |

三个原始 PRT 已逐字节核对 v0.2.4 实机测试输入。两截面直线和平滑的方形、圆、三角形以及五截面平滑方形和 NACA 0012 样条翼型通过原生特征、参数修改、保存擦除重载验证。证据见 [直线](validation_loft_seed.json)、[平滑](validation_loft_smooth.json)、[多截面](validation_multisection.json)。本机测试环境为 Creo 10.0.0.0，其他安装仍需验证。没有三截面直线种子，2～20 的接口数量范围不代表所有数量均已实测。

## 下载后使用

**最新源码优先流程**：完成 `setup.ps1`，调用 `creo_list_seeds` 确认可用数量为 3，随后调用 `creo_new_loft_part` 时省略 `seed_file` 和 `seed_feature_id`。数量和 `interpolation` 自动匹配。翼型还可直接调用 `creo_new_airfoil_blade`。详细说明见 [本次增量](PORTABLE_MODELING_2026-10-11.md)。以下保留旧调用兼容流程，适用于需要显式指定种子的用户。

1. 安装 0.2.4 源码，按 [INSTALL.md](INSTALL.md) 配好本机 Creo、Toolkit SDK、编译器、Python 和可用许可。
2. 解压种子库，进入能看到 `seed_manifest.json` 和 `resolve_seed.py` 的目录。原始文件名及 `.prt.N` 后缀保留，目录可自行选择。
3. 用标准 Python 运行以下命令；也可使用源码目录 `.venv\Scripts\python.exe`：

   ```powershell
   python .\resolve_seed.py five_smooth
   ```

   程序核对 SHA256，并输出此目录对应的本机种子参数。例如：

   ```json
   {
     "seed_file": "C:\\CreoSeeds\\seeds\\five_smooth\\mechdog_multi5_reference.prt.1",
     "seed_feature_id": 93,
     "interpolation": "smooth",
     "required_section_count": 5
   }
   ```

4. 将输出的 `seed_file`、`seed_feature_id`、`interpolation` 用于 `creo_new_loft_part`，另传入五张 XY 草图 `sections`，Z 偏移严格递增。`required_section_count` 只是提示，不是工具参数。[方形示例](../examples/loft_multisection_seed.json) 与 [翼型示例](../examples/loft_multisection_airfoil.json) 中的种子占位路径和 ID 应替换为上述实际值。两截面则选用 `two_straight` 或 `two_smooth`。
5. 提交一次并查询 `job_id`，验收 `succeeded`、`saved_file_reloaded_and_verified == true` 和重载后原生混合的截面数与模式。

复制同一个原始文件到新电脑时，清单内的特征 ID 仍适用；自动选择会计算本机路径。新建或改造种子后须显式核对 ID、数量及模式，不按原清单信任修改过的文件。种子端点设置、参数、关系及基准可能被继承，专用简单模型优先。安装器自动验证/注册随包库，不从网络下载库。

## MIT 与发布

种子库中的项目原创测试几何、脚本、清单及说明采用 MIT，库内保留 `LICENSE`。授权只适用于项目自身贡献，不提供 Creo、Toolkit 或其他第三方材料的权利。没有打包 PTC 安装程序、SDK、二进制或许可，也不是 PTC 官方样例库。

本次源码 ZIP 包含三个种子，也应将仓库 `seed_library/` 一同更新，才能让 GitHub 自动 Source code ZIP 包含它们。独立旧种子附件可继续提供，不必更改其内容或 SHA256。发布步骤见 [PUBLISH_GITHUB.md](PUBLISH_GITHUB.md)，跨电脑与跨 Agent 使用见 [MIGRATION.md](MIGRATION.md)。
