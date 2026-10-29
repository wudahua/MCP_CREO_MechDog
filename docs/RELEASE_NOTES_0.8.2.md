# MCP_CREO_MechDog 0.8.2

0.8.2 是 BUG-089 的 PATCH 版本，仅修复种子清单版本一致性与原发布工具可用性。公开工具仍为 **94** 个，无接口或建模能力变化。

0.8.1 的 `seed_library/seed_manifest.json` 和 `docs/seed_manifest.json` 仍声明 `compatible_server_version=0.8.0`，直接运行文档中的 `tools/package_seeds.py --output` 会因版本断言失败。已发布的 0.8.1 种子附件内部也声明 0.8.0。0.8.2 将两份清单同步到 0.8.2，新增离线回归测试，并用未经修改的打包命令重新生成种子包。种子列表及每个种子的 SHA256 保持不变；升级用户应换用 **0.8.2 种子包**，不要沿用 0.8.1 附件。

本版只进行离线单元与发布打包验证。全部实机 Creo、WorkBuddy、Creo 9/10 均未执行；0.8.0 新增原生能力的实机验收仍未完成。详见 [发布记录](validation/RELEASE-0.8.2.md) 与 [BUG-089](work-items/BUG-089.md)。
