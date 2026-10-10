# 0.2.3：两截面直线与平滑实体混合

MCP_CREO_MechDog 当前版本为 **0.2.3**。此源码版收录已发布 v0.22 之后完成的普通混合增量，注册 **68 个 MCP 工具、67 个启用**。采用 MIT 许可证，使用者在自己的 Windows 电脑上安装依赖并编译 Creo Toolkit 执行器。

## 本版混合能力

`creo_new_loft_part` 根据两张参数草图创建新零件，保留原生 Blend 特征。支持 `interpolation: "straight"` 与 `"smooth"`，两种模式分别完成矩形、圆、三角形案例验证，均通过以下验收：

- 原生混合特征保持活动、完整且可编辑。
- 顶截面尺寸 10→12 mm 成功驱动实体，体积 7000→7840 mm³。
- 保存后擦除、从实际 PRT 重载并再生，几何与原生连接模式均保持正确。

每种模式另验证了后续圆柱切除、故意失败后的回滚、无效种子特征 ID 和模式不匹配的拒绝。调用说明见 [LOFT_SEED.md](LOFT_SEED.md)、[SMOOTH_BLEND.md](SMOOTH_BLEND.md)，完整参数示例见 [loft_seed.json](../examples/loft_seed.json)、[loft_smooth_seed.json](../examples/loft_smooth_seed.json)。

## 范围与证据

目前要求使用者提供匹配模式的毫米制、单实体、两截面混合种子；输入为两张 Z 偏移递增的平行 XY 草图。模式参数核实种子设置，不转换连接模式。多截面、向已有零件追加混合、无种子直接创建、非平行截面和端点相切/曲率控制仍未完成；`creo_loft` 直接创建接口仍禁用。自由端点的两截面平滑混合可以与直线混合产生相同几何，模式核验读取 Creo 原生特征报告。

本次版本更新保留原生任务的 **0.22** 验收标签，核对建模运行代码与执行器哈希未变化，并重新执行 **0.2.3** 的输入验证及 MCP 版本/连接检查。直线、平滑公开摘要分别为 [validation_loft_seed.json](validation_loft_seed.json)、[validation_loft_smooth.json](validation_loft_smooth.json)，摘要明确区分当前发布版本和原生建模验证版本。

工程图、曲面、多实体、UDF 等既有工具继续保留；其历史功能说明见 [RELEASE_NOTES_0.22.md](RELEASE_NOTES_0.22.md)，历史测试见 [validation_development.json](validation_development.json)，本次版本更新未重跑这些模块的完整集成套件。`complete_creo_coverage` 保持 false。

## 安装与发布

下载 `MCP_CREO_MechDog-0.2.3-source.zip`，按 [INSTALL.md](INSTALL.md) 安装或升级，重启 MCP 服务后确认 `creo_capabilities.version == "0.2.3"`。源码包不含本机配置、许可、PTC SDK、编译产物或测试零件。

GitHub 使用新标签 **v0.2.3**，发布说明保留上述范围并标记 **Pre-release**。已发布的 v0.22 标签和旧源码包保持原状；本地版本更新与打包不会自动发布到 GitHub。
