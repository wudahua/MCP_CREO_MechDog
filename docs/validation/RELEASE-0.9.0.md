# 0.9.0 发布记录（DEV-051 实机修复批次）

版本与条目：0.9.0；BUG-032/T03 板厚同步、FEAT-014/T05+T11 第三道折边定因、FEAT-031/T13 两段式回导、T09D 性能基准；另含 2026-10-30 的十个离线提交（T02/T09A/T09B/T12/BUG-085/T01 文档收口）。
提交、dirty 标志、受测源码指纹：分支 `codex/dev051-feedback070`；实机受测范围覆盖 `b5309ff`（板厚参数驱动）、`fff7b3a`+`17a1091`（T13 两段式）、`dd163f1`（能力边界文案）；合入 main 的提交与标签在发布时回填本节。打包时工作区 dirty 状态与指纹见下文“源码包”。
日期与 Windows/Python/Creo/SDK/MSVC 环境：2026-10-30；Windows 11 x64 / Python 3.12 venv / Creo 12.4.0.0（`release_numeric=44`）/ 本机匹配 Toolkit SDK / MSVC x64；`auto_start_creo=false`，会话由用户手工启动（12:21），14:11 重启用于 T13 隔离回导。

命令及结果（单元 / 原生 / 安装 / 源码包）：

| # | 命令 | 结果 |
| --- | --- | --- |
| 1 | `python -m unittest discover -s tests` | Ran 1490 tests，OK（T09D 驱动提交前） |
| 2 | `python tools/dev_check.py` | exit 0，`success=true`（格式化 2 个 T09D 文件后复跑） |
| 3 | `python bridge.py build` | exit 0；执行器重建（板厚参数驱动 + T11 释放回读 + T05 trim 分支） |
| 4 | `python tools/test_sheetmetal_contract.py --live --confirm-session-usable` | **通过**：5/5 矩阵体积误差 0.0，零件厚度 3.71/2.31 → 1.0/232.0，重载 true；首轮失败与修复见 T03 卡 |
| 5 | `python tools/test_sheetmetal_relief.py --live --confirm-session-usable` | 材料场景未成立：第三道折边再生失败（回滚成功）；自由端两道增量与 oracle 差 7e-7 |
| 6 | `build/t05_probe.py`（三组对照） | 整条 185 mm 自由边成功；181.46 / 177.92 均失败 → 定因“附着边端部相邻折弯” |
| 7 | `python tools/test_assembly_bundle.py --live --confirm-session-usable` | 导出通过；同会话回导 `SESSION_NAME_CONFLICT`（受管模型不可擦） |
| 8 | `python tools/test_assembly_bundle.py --live --confirm-session-usable --reimport <bundle> --expected <report>` | **通过**：空会话回导，组件 2/2、位姿一致、`occurrence_label` 保留 |
| 9 | `python tools/test_plan_performance.py --live --confirm-session-usable [--reps 1]` | small 19.5/11.3 s，large 261.0/138.7 s，等价校验全过；large 未达 3 次重复 |
| 10 | `python tools/package.py` / `package_seeds.py` | 见下文源码包 |

原生修改保存重载、参数编辑、回滚证据：T03 五例 `saved_file_reloaded_and_verified=true`；T11 两道自由端折边重载 true，第三道失败 `rollback_succeeded=true`、模型与 revision 不变；T13 导出与回导重载 true；T09D 全部作业重载 true。
未测模块、失败用例、兼容限制：T05/T11 角部能力未实现（四壁 3/4 上限）；`relief` 材料场景未验证；T02 弧方向、T09B 中心线计数、T12 沉孔余项为离线交付未实机；T09B 真多中心线夹具无法经本服务构造；T06/T07/T08C 外部原件缺；BUG-085 根因未定；WorkBuddy 未执行；Creo 9 无 SDK、Creo 10 未复测。
源码包及种子包 SHA256（文件名与完整哈希，写入 Release body）：见下。
发布候选验收结论：按上表范围通过；开放项随版本说明披露。
合入 main 的提交、版本标签及指向：见下。
GitHub Release 链接与发布状态：见下。
远端附件与 SHA256 核对结果（body 记载与远端附件逐项一致）：见下。

源码包（由标签 `v0.9.0` 指向的主干提交源码构建；本记录随该提交入库，附件哈希在打包后回填进 Release body 与本文件的发布后小节，回填提交不属于标签内容）：

```text
（发布后回填）
```

逐 ID 状态核对（候选态）：

| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-032/T03 | 实机通过 | 0.9.0 | 面距未单独量测 | DEV051-T03-ACCEPTANCE | BACKLOG | RELEASE_NOTES_0.9.0 | DEVELOPMENT | （发布后回填） |
| FEAT-014/T05 | 定因，能力未实现 | 0.9.0 | 四壁/角部 | DEV051-T05-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-014/T11 | 材料场景受阻 | 0.9.0 | relief 材料场景 | DEV051-T11-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-031/T13 | 实机通过（两段式） | 0.9.0 | 嵌套/外部引用 | DEV051-T13-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| T09D | 基准完成 | 0.9.0 | large ≥3 次重复 | DEV051-T09D-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-034/T02 | 离线交付 | 0.9.0 | 实机复测 | DEV051-T02-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| T09B | 离线交付 | 0.9.0 | 实机复测+多线夹具 | DEV051-T09B-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| T09A | 回归锁定（零改动） | 0.9.0 | 实机复验 | DEV051-T09A-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| FEAT-035/T12 | 离线交付 | 0.9.0 | 6 例余项实机 | DEV051-T12-ACCEPTANCE | BACKLOG | 同上 | 同上 | 同上 |
| BUG-085 | 调查完成，根因未定 | 0.9.0 | 实机取证 | BUG085-OFFLINE-EVIDENCE | BACKLOG | 同上 | 同上 | 同上 |

相对上一正式包核对（上一版本：0.8.5）：

| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| native/third_party 原字节（含 json.hpp、第三方许可） | 未变 | 未变 | 无注册影响 |
| 回调指纹（sha256-repo-lf-v1） | （打包后回填） | （打包后回填） | 变更来自 advanced.cpp/generic.cpp 修复 |
| loader DLL SHA256 | 未变 | 未变 | 无 |
| callback DLL SHA256 | 未变 | 未变 | 无 |
| worker SHA256 | 变更 | 变更 | 需 `setup.ps1` 重建执行器或沿用 `bridge.py build` |
| protk.dat / 注册表路径 | 未变 | 未变 | 无 |
| 实际注册影响 | — | — | 重启 MCP 服务并重建执行器即可，无需重新注册 |
