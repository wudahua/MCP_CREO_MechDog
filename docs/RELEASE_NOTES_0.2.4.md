# 0.2.4：多截面原生实体混合

**2026-10-11 增量更新**：新增种子自动安装/发现/选择、NACA 00xx 原生截面与原位参数修改、通用原生定位、分组/重排/轴阵列；源码内附三个 MIT 种子 PRT。当前注册 80 个工具、79 个启用，版本仍为 0.2.4。当前使用及验收见 [增量说明](PORTABLE_MODELING_2026-10-11.md)。下文的 68 工具、种子独立下载等描述记录最初 v0.2.4 发布时的状态。

`creo_new_loft_part` 从两截面扩展为 **2～20 张平行 XY 草图**，要求 Z 偏移严格递增，种子的截面数及直线/平滑模式与输入一致。支持草图整体和完整复合曲线参照，保留原生 Blend 及每张参数草图。MIT 源码安装版，仍为 Pre-release；注册 68 个工具，67 个启用。

本版验收包括五截面平滑方形与 NACA 0012 样条翼型：原生混合保留，中间尺寸或位置修改成功，实际保存擦除重载成功。原生截面数和模式通过 Toolkit 与 `PRO_FEAT_INFO` 核对；STL 核验全部截面。故意失败后的回滚、数量/模式不匹配的拒绝也通过。完整结果见 [validation_multisection.json](validation_multisection.json)，步骤见 [MULTISECTION_BLEND.md](MULTISECTION_BLEND.md)。

两截面直线与平滑的矩形、圆、三角形回归另见 [validation_loft_seed.json](validation_loft_seed.json)、[validation_loft_smooth.json](validation_loft_smooth.json)。当前输入验证及 MCP 协议检查使用 0.2.4。其他专业模块保留历史证据，没有重跑完整套件。

本轮三截面直线参考件尚未形成原生混合种子，因此没有将其列为验收通过。

另提供 **原生混合种子库**，包含两截面直线、两截面平滑、五截面平滑的项目原创 PRT，配套 MIT 许可证、截面数/模式/内部 ID 清单、SHA256、路径解析器、使用及迁移说明。原始文件逐字节核对实机测试输入；复制到另一目录后的参数解析也通过。详情见 [SEED_LIBRARY.md](SEED_LIBRARY.md)、[MIGRATION.md](MIGRATION.md)。此增补更新发布资料与模型附件，建模执行代码、版本号及原生验收结果保持 0.2.4。

范围仍为匹配种子创建新零件，不能自动增加/删除种子截面、转换模式、追加到已有零件或无种子创建；非平行、切除/曲面、起点对应和相切/曲率控制尚未封装。2～20 是输入限制，不代表所有数量与任意轮廓均实测。完整螺旋桨、完整 Creo 操作覆盖均未完成。

源码包 `MCP_CREO_MechDog-0.2.4-source.zip` 及 `.zip.sha256` 不含本机配置、许可、SDK、二进制和测试模型。更新本地源码并重启 MCP 后确认 `creo_capabilities.version == "0.2.4"`。GitHub 新标签使用 **v0.2.4**，旧版本保持原状；本地打包不会自动发布到 GitHub。

发布时同时提供 `MCP_CREO_MechDog-0.2.4-seed-library.zip` 与其 `.zip.sha256`。普通混合用户需下载源码及种子两个包；GitHub 自动生成的 Source code ZIP 不包含仅上传到 Release 附件的种子库。安装器当前不会自动下载或注册种子。项目原创模型及配套文件采用 MIT，不授予 Creo、Toolkit 或其他第三方材料的权利；目标机仍需满足本机环境和实际运行许可条件。保留 Pre-release 标记。
