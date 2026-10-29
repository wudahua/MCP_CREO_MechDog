# Release 0.8.3 发布验收记录

日期：2026-10-29（Asia/Shanghai）。版本与条目：0.8.3 PATCH、[DEV-051](../work-items/DEV-051.md) T02/T06/T07/T08A，关联 FEAT-034、BUG-049、BUG-064/087、BUG-088。候选分支 `codex/dev051-feedback070`，基线 `4127a4a`；实机证据已在该分支提交，发布时不再连接 Creo 或 WorkBuddy。工作区含用户保留的本机未提交文件，`dirty=true`；受测源码身份以各 [T02](../development/DEV051-T02-ACCEPTANCE.md)、[T06](../development/DEV051-T06-ACCEPTANCE.md)、[T07](../development/DEV051-T07-ACCEPTANCE.md)、[T08A](../development/DEV051-T08A-ACCEPTANCE.md) 实机记录和本次 `dev_check.py` 的源码指纹分别追踪，不把历史受测树称为干净发布树。

环境：本机 Windows x64、PowerShell、`.venv` Python 3.12；先前实机阶段为 Creo 12.4.0.0 / 匹配 Toolkit SDK。本次仅文档、测试驱动与清单版本变更，不修改原生建模代码，也不重建或连接 Toolkit。公开工具数仍为 94；API 与几何语义不变。

## 实机证据与限制

- T02：`tools\test_arc_direction_live.py --live --confirm-session-usable` exit 0，4/4；旧 0→90 实测 142.69908169840258（oracle 142.69908169872414）、旧 90→0 实测 1428.09724510173（oracle 1428.0972450961724）mm³，两例 `dir=-1` 分别与相应反向旧例逐位相等；`source=native`、`query_code=0`、`frame=sketch_local`、`dir=1`、`sweep_deg=90`。本组无 save，`saved_file_reloaded_and_verified=null`。
- T06：`tools\test_t06_native.py --live --confirm-session-usable` exit 0；九例独立夹具全过，成功作业保存重载通过；另有一例真实失败且 `rollback_succeeded=true`、revision 未推进。原 30 段/星形材料缺失。
- T07：`tools\test_dev049_profile_replay.py --live --confirm-session-usable` exit 0；2 圆、5 环、10 环分别去料 125.66370614359039、706.8582848640717、353.42900085383553 mm³，均 revision 2、保存重载通过。仅为替代夹具，原 gear10 案未回放。
- T08A：`tools\test_t07_preview.py --live --confirm-session-usable` exit 0；四例输出文件均落盘且通过 `file_check`。BUG-088 原现象未复现，图像内容 `human_review_pending`。

未测：T02 保存重载/方向编辑/下游特征/非法编辑/busy；T06 原案材料与第二参照；T07 原案及失败路径；T08A 图像内容、空件/钣金件与间歇故障；其余 DEV-051 实机子项、WorkBuddy、Creo 9/10。BUG-085 根因未定。0.7.2 等历史验收保留各自版本归属。

## 0.8.3 离线检查与附件

- 未修改的 `.venv\Scripts\python.exe tools\package_seeds.py --output <新路径>` 构建三次，24 文件、9 种子；两次独立构建及回填 `seeds.py expected_digest` 后第三次均为 SHA256 `a5dfc704ba141a202222c765812fe9c0b2dc05abd0991807012838c08d8ecd61`。前版 0.8.2 种子包 SHA256 为 `4bdcccabb4cf384d546b8335283bb1c9424ad75cc6a450df58675cdbdb1a6e74`。
- `.venv\Scripts\python.exe tools\dev_check.py`：exit 0、`success=true`、`unit_tests=passed`；1343 项、0 失败、0 错误；`checked_source_sha256=aca40d06505daa467dbccc3d071332db0bb6e24621f0370fe806965566d58ad8`，报告 SHA256 `e7285560e364d161bbec79acdc1c432475b3379befdca5922ecee500dd303f65`。存量风格摘要 30 lint、16 个未格式化文件；未修改基线或跳过测试。运行时 `commit=4127a4a`、`dirty=true`，包含本版候选修改与用户本机文件。
- `.venv\Scripts\python.exe tools\package.py --output <新路径>` 两次构建一致，均为 1037 文件；ZIP 完整性检查通过，两份清单均为 0.8.3，第三方许可在包内，禁入路径为 0。两个 ZIP 的完整 SHA256 和四附件远端下载核对记录在 Release body 与交付报告，避免源包自指。

## 发布状态与逐 ID 核对

发布候选态：`version.py`、两份种子清单、README 标题及版本段、[开发入口](../DEVELOPMENT.md)、[主台账](../BACKLOG.md)、[版本说明](../RELEASE_NOTES_0.8.3.md)与本卡均指向 0.8.3。合入后的 main 提交、附注标签对象及剥离目标、正式 Release 链接和四附件远端哈希在 Release body 与交付报告记录；发布后不追加自指 main 提交。

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页／主台账／版本说明／开发入口／Release |
| --- | --- | --- | --- | --- |
| DEV-051 | T02/T06/T07/T08A 指定实机子项已验 | 0.8.3；原实现 0.8.0 | 原案缺件、其余实机、WorkBuddy | 本卡与四处当前入口一致；正式 Release 以 `v0.8.3` 为准 |
| FEAT-034 | T02 四例通过，整项验收中 | 实现 0.8.0、补证 0.8.3 | 编辑、重载、下游与跨环境 | [工作卡](../work-items/FEAT-034.md)、主台账、版本说明和开发入口按指定范围披露 |
| BUG-049 | T07 替代夹具通过，原案开放 | 补证 0.8.3 | 原 gear10 材料与回放 | [工作卡](../work-items/BUG-049.md)、主台账、版本说明和开发入口按指定范围披露 |
| BUG-088 | T08A 四例文件确认通过，原现象未复现 | 补证 0.8.3 | 间歇故障和图像内容 | [工作卡](../work-items/BUG-088.md)、主台账、版本说明和开发入口按指定范围披露 |

相对上一正式包 0.8.2：`git diff 8e2cc34 -- native/third_party native/protk.dat src/creo_mechdog native` 无差异；本版无生产或注册代码修改。现有 `build/creo_worker.exe` SHA256 为 `f1d9990c7ac376b1007e49e1d87a3add76c10f5d192c3b9c3efe2655ad1f7305`，与 0.8.2 发布记录相同；`build/source.sha256` 文件 SHA256 为 `f77a7e26cf43b6c5d0a6f050966522c80fedd84ba686cd9ef500a8bb731d2a56`，亦相同。回调指纹、loader/callback DLL 和实际注册表路径本次未独立读取，不外推已验证；源码层面无新的注册、迁移或重启要求。
