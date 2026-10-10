# v0.2.4 原生混合种子库

“种子”是保存了完整原生 Blend / 混合的简单 Creo PRT 模板。`creo_new_loft_part` 复制它，创建新的参数草图，将混合改接到新截面并删除旧截面草图。源文件不改动，结果保留原生混合特征。普通草图、拉伸、旋转及孔工具使用本机 Creo 标准模板，不要求这种专用混合种子。

种子库是独立 Release 附件 `MCP_CREO_MechDog-0.2.4-seed-library.zip`，配套 `.zip.sha256`。源码 ZIP 只含说明及 [清单副本](seed_manifest.json)，不含种子 PRT。库中的 `seed_manifest.json`、`LICENSE`、`README.md`、迁移说明、路径解析脚本及验证摘要配套提供。

## 已验证内容

| name | 截面数 | 模式 | 原始文件内混合 ID |
| --- | --- | --- | --- |
| two_straight | 2 | straight / 直线 | 60 |
| two_smooth | 2 | smooth / 平滑 | 60 |
| five_smooth | 5 | smooth / 平滑 | 93 |

三个原始 PRT 已逐字节核对 v0.2.4 实机测试输入。两截面直线和平滑的方形、圆、三角形以及五截面平滑方形和 NACA 0012 样条翼型通过原生特征、参数修改、保存擦除重载验证。证据见 [直线](validation_loft_seed.json)、[平滑](validation_loft_smooth.json)、[多截面](validation_multisection.json)。本机测试环境为 Creo 10.0.0.0，其他安装仍需验证。没有三截面直线种子，2～20 的接口数量范围不代表所有数量均已实测。

## 下载后使用

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

复制同一个原始文件到新电脑时，可沿用清单内的特征 ID，只需改变路径；新建或改造种子后重新核对 ID、数量及模式。种子端点设置、参数、关系及基准可能被继承，专用简单模型优先。安装器当前不会自动下载、查找或注册种子库，Agent 需知道本机库路径。

## MIT 与发布

种子库中的项目原创测试几何、脚本、清单及说明采用 MIT，库内保留 `LICENSE`。授权只适用于项目自身贡献，不提供 Creo、Toolkit 或其他第三方材料的权利。没有打包 PTC 安装程序、SDK、二进制或许可，也不是 PTC 官方样例库。

建议在同一个 v0.2.4 Release 中同时上传源码 ZIP、种子库 ZIP 及各自校验码。GitHub 自动生成的 Source code ZIP 不包含仅作为 Release 附件上传的种子，用户应同时下载两个包。发布步骤见 [PUBLISH_GITHUB.md](PUBLISH_GITHUB.md)，跨电脑与跨 Agent 使用见 [MIGRATION.md](MIGRATION.md)。
