# MCP_CREO_MechDog 0.8.3

0.8.3 是 [DEV-051](work-items/DEV-051.md) 的 PATCH：交付 2026-10-29 已完成的实机验收证据、T02/T07 测试驱动，以及种子清单的版本同步。公开工具仍为 **94** 个；无生产代码、API、能力或几何语义变更。两份种子清单现声明 `compatible_server_version=0.8.3`，种子列表及原始 PRT 字节未变。升级请使用 0.8.3 种子包。

本机 Windows x64 / Creo 12.4.0.0 的既有实机结果如下；本次发布操作没有再连接 Creo：

| 子项 | 已验范围 | 仍待验 |
| --- | --- | --- |
| [T02 弧方向](development/DEV051-T02-ACCEPTANCE.md) | 四个弧加弦拉伸例 4/4；两种旧输入体积分别为 142.69908169840258、1428.09724510173 mm³，与独立 oracle 对应；两例 `dir=-1` 与反向旧例逐位相等；原生回显含 `source=native`、`query_code=0`、局部帧端点/切向与扫角。 | 本组无保存操作，重载标志为 `null`；方向编辑、下游特征、非法编辑及 busy 行为。 |
| [T06 新件倾斜草图](development/DEV051-T06-ACCEPTANCE.md) | 九个独立夹具通过；成功作业保存重载通过，另有一例真实失败且回滚成功。 | 原 30 段/星形附件缺失，第二参照选择和原案回放。 |
| [T07 多环切除](development/DEV051-T07-ACCEPTANCE.md) | 2 圆、5 环、10 环替代夹具 3/3；去料分别为 125.66370614359039、706.8582848640717、353.42900085383553 mm³，revision 均为 2，均保存重载通过。驱动修复 `CallToolResult` 解包，并将环布局约束在板内。 | 原 `gear10.json`/`sketch_entities.json` 缺失，原案回放与失败路径；不主张轮廓数上限。 |
| [T08A 预览文件](development/DEV051-T08A-ACCEPTANCE.md) | 四例输出文件均写出并通过 `file_check`；[BUG-088](work-items/BUG-088.md) 原 `raster=0 → output_file=-4` 未复现。 | 图像内容仍为 `human_review_pending`；间歇故障根因、空件/钣金件路径。 |

其余 DEV-051 实机范围没有因上述夹具通过而视作已验。WorkBuddy 未执行；Creo 9 SDK 本机不可用，Creo 9 编译和建模未验，Creo 10 未独立复测；BUG-085 断连根因仍未确定。完整命令、受测身份与发布附件核对见 [发布验收记录](validation/RELEASE-0.8.3.md)。
