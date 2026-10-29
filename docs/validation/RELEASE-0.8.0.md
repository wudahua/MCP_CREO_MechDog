# Release 0.8.0 发布验收记录

版本与条目：`0.8.0`（MINOR），DEV-051 T00—T13 的本次已提交范围；公开工具 94 个。日期：2026-10-29（Asia/Shanghai）。Windows x64 / PowerShell / `.venv` Python 3.12；本机 Creo 12.4 匹配 SDK 与 MSVC 仅用于离线构建，**未连接 Creo**。

提交、dirty 标志、受测源码指纹：集成起点 `a1a1db7`，T01 提交 `ae66b91`；本文件随 T10 定稿提交入库，自指主干提交与标签对象见 GitHub Release body。运行检查时工作区包含另一会话未提交文件，`dirty=true`；`tools/dev_check.py` 的 `checked_source_sha256=e69881a335b7f18b7f2ffb80da6b05aa331df8dc95628bd5b32a3e6a1dc7d3f9`（代码为 0.8.0 候选版），报告 `build/development_check.json` SHA256 `661c95fb563edbebfa41c9c87ca370730a56c78d113bdf7013b4594d9851dfbf`。

命令及结果：`.venv\Scripts\python.exe tools\dev_check.py` exit 0，`success=true`、`unit_tests=passed`，`build/unit_test_report.json` 记载 1341 项、0 失败、0 错误；风格 30 项 lint／16 个未格式化文件均为既有基线，`native_validation=not_run`。`.venv\Scripts\python.exe bridge.py build` exit 0，`build/creo_worker.exe` SHA256 `f1d9990c7ac376b1007e49e1d87a3add76c10f5d192c3b9c3efe2655ad1f7305`，原生源码指纹 `5feaca7083bc704caa8dba36b5521b093dffbe8face8abd678f95e2dde9f2d88`。`tools/package_seeds.py` 两次构建 24 文件／9 种子，SHA256 一致；源码包与新目录解包结果由 Release body 报告。实机修改、保存重载、参数编辑、回滚：**未执行**；不能由离线结果推断。

源码包及种子包 SHA256：种子包首次构建 `MCP_CREO_MechDog-0.8.0-seed-library.zip` 为 `4ed63b3deb40f9a60f237cab949ac9cf5a4bd1f188d0b78f7795c5bdc9d3f12b`；最终四附件及下载回核以 Release body 为准。源码包须从最终 main 提交的干净源码生成；本文件不能自指其哈希。

未测与限制：全部 Creo 实机（含原生几何、revision、保存重载、回滚）未执行；WorkBuddy 未执行；Creo 9/10 未验。BUG-085 根因未定；原件和原始请求缺失的调查仅有替代离线夹具，不能关闭原案。新增沉孔／沉头、钣金 relief、装配 native_bundle、回转轴等仅离线完成，真实运行和安装需后续核对。0.7.2 BUG-087 六例及 FEAT-030 种子 15+2 的历史实机证据保持原归属。

发布候选验收结论：离线全量检查与匹配 SDK 构建通过，九种子包确定性通过；新增原生行为仍待实机。合入 main 的提交、附注标签对象、正式 Release URL、四件远端下载 SHA256 核对均在 Release body 与交付回传中记录，不为自指信息追加 main 提交。

**已知文档滞后**：主台账 `docs/BACKLOG.md`、开发入口 `docs/DEVELOPMENT.md` 的当前批次描述仍由另一并发窗口持有，尚未并入本版。T01 验收卡列有待回填清单；本次受禁止修改这些路径的约束，不把其旧状态当作 0.8.0 已完成证据。

逐 ID 状态核对（候选态）：DEV-051 T01 为文档收口；T02/T03/T09A/T09B/T11/T12/T13 为离线实现、待原生验收；T04/T05/T06/T07/T08A/T08B/T08C/T09C 为调查或离线诊断阶段，原案仍按各卡开放；BUG-085 根因未定。卡首页与本版说明可核；主台账／开发入口尚待并发窗口回填，实际 Release 待发布后核。

相对 v0.7.2：`git diff v0.7.2 -- native/third_party` 为空，`json.hpp` 和第三方许可未变；回调指纹算法 `sha256-repo-lf-v1` 不变。当前本机 loader/callback DLL 哈希与 v0.7.2 发布记录相同（`9ea54464…`／`71b1093a…`）；worker 因本版原生源码变化已重建，需随升级替换并重启服务。`protk.dat`／实际注册表项及目标安装路径本批未连接 Creo、未执行新目录运行时验收，不能声称已重新注册或验证运行时。
