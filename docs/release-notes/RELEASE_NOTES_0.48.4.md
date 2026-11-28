# MCP_CREO_MechDog 0.48.4 版本说明

2026-11-28 PATCH，公开工具数 112。上一版本：0.48.3（`v0.48.3`，提交 `718b477f0bd1c54f32989eda57085db7df9144e4`）。

- 开发入口、仓库约束和 Claude 说明合计从 200 行缩至 91 行；原生编译单元与建模进程链可按需查阅。
- 七条台账长摘要从 4,906 字符减至 400 字符。BUG-120 的摘要同步工作卡实测结论，接缝相切达标，健康实体保存仍受阻。
- Toolkit 指南与项目技能引用本机常设授权并指向包内实现。发布指南统一了发布后核对记录的位置。

本版改动为文档与版本元数据。验收环境为 Windows x64 / Python 3.12.10。未运行 Creo 9、10、12.4 实机建模或外部 WorkBuddy 黑盒。 [发布记录](../validation/RELEASE-0.48.4.md)

## 附件

- `MCP_CREO_MechDog-0.48.4-source.zip`
- `MCP_CREO_MechDog-0.48.4-source.zip.sha256`
- `MCP_CREO_MechDog-0.48.4-seed-library.zip`
- `MCP_CREO_MechDog-0.48.4-seed-library.zip.sha256`

种子包 SHA256 为 `7607128038de9ce304f12ecb7196bcf8f47580ab5d0c93290e0f65d7d5373220`。源码包和种子包的摘要分别记录在同名 sidecar。远端校验发布后执行，当前未验证。[GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.48.4)
