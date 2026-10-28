# DEV-051 T00 验收卡：共同基线、原件归档与工作卡

日期：2026-10-28（Asia/Shanghai）。阶段：**T00 文档与证据基线完成**；T01—T09、T11—T13 未实施，T10 未指派。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。依赖提交：`2b677f53422102fc14109871f1794b627274a09f`（本地/远端 main 与 `v0.7.2^{}`）。实现提交：本卡所属 T00 共同提交，以交接报告和 `git rev-parse HEAD` 为准；提交号不能自指写入同一提交中的文件。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)、[总计划](0.7.0-FEEDBACK-PLAN-2026-10-28.md)，按此顺序读取；当前 [BACKLOG](../BACKLOG.md) 与既有工作卡。
- `C:\Users\Administrator\Downloads\0.7.0\` 的四份 Markdown；总计划的四个字节数与 SHA256 为冻结期望。复制后档案见 [manifest](../validation/feedback-0.7.0-2026-10-28/manifest.json)和[章节映射](../validation/feedback-0.7.0-2026-10-28/MAPPING.md)。原请求 JSON、PRT、图像和脚本未随附。
- 0.7.2 比较基线：`git rev-parse` / `git ls-remote` 与 GitHub Releases API 只读核对；Release 非 draft/prerelease，四附件存在。未重新下载附件或复验附件哈希，已发布附件事实沿用既有 [0.7.2 发布验收](../validation/RELEASE-0.7.2.md)。

## 实际修改文件

`.gitattributes`；`docs/BACKLOG.md`；两份 `docs/development/0.7.0-FEEDBACK-*.md`；本卡；`docs/work-items/DEV-051.md`、`BUG-088.md`、`FEAT-014.md`；`docs/validation/feedback-0.7.0-2026-10-28/` 内四份原件、`manifest.json` 和 `MAPPING.md`。未改生产代码、`version.py`、旧版原件或运行数据。提交仅按这些精确路径暂存；工作区原有 `session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/` 保留且不提交。

## 环境、命令与逐项结果

Windows x64 / PowerShell；Git 只读远端核对使用 `git rev-parse HEAD/main/refs/remotes/origin/main/v0.7.2^{}`、`git ls-remote origin refs/heads/main refs/tags/v0.7.2^{}`。Release 用 `Invoke-RestMethod https://api.github.com/repos/wudahua/MCP_CREO_MechDog/releases/tags/v0.7.2`；原先尝试 `gh release view`，本机 `gh` 不在 PATH，原始错误为“无法将‘gh’项识别为 cmdlet”。随后官方 API 核对成功，未构成基线缺口。

| 核对项 | 实际结果 |
| --- | --- |
| main / tag / Release | 本地和远端 main、peeled tag 均为 `2b677f53422102fc14109871f1794b627274a09f`；正式 Release 四附件，版本入口仍为 0.7.2 |
| ID | DEV-051、BUG-088 在现有台账/卡未占用，分别新登；FEAT-014 已有一条台账行，复用并补卡 |
| 原件 | 4/4 复制后长度和 SHA256 与总计划一致；原件未解码、重排或改行尾；`.gitattributes` 仅 `2026*.md -text`，MAPPING 为正常 text |
| 映射 | 四份报告全部 69 个标题/章节及作者回复请求已有主 ID 与任务；静态、实机、推测、缺件分列；文件缺失 BUG-088 与内容失真 BUG-066 分列 |
| 台账 | 新增两条唯一 ID，123→125 行；开发中 3→4、待复现 21→22；FEAT-014 原行链接工作卡；0.7.2 已完成事项没有重登 |
| 边界 | 弧缺省 CCW、单通道 busy、未知实际轴/单位不可回填请求值、rolled_back 前置须重建均在卡/映射落档 |
| 工作区 | 既有无关文件未暂存、提交、删除或改写；本次未发现无关删除/覆盖风险 |

文档核对命令：`Get-FileHash -Algorithm SHA256`、`Get-ChildItem`、`rg`、`git check-attr text`、`git diff --check`、精确路径 `git add` 与 `git diff --cached --check`。归档报告本身为外部证据，不是 T00 执行的实机测试。受测 commit：不适用（无代码/建模测试）；dirty：提交前含本批文档和上述既有无关文件，提交后仍含无关文件；`source_fingerprint`：不适用（未构建或连接执行器）。本卡与 manifest 的最终 SHA256 以交接报告为准。

## 未测与下一步

未运行建模、单元测试、开发检查、构建、WorkBuddy；未连接 Creo，故无 job/model/revision、几何、保存重载或回滚结果。原 `gear10.json`、`sketch_entities.json`、`sketchgen.py`、30 段截面请求、新旧星形 PRT、失败 request/job/native JSON 和原始预览图缺失。后续窗口先取得 T00 共同提交，再只执行获指派任务；实机与发布均需另行指派并满足项目条件。T01 收口当前入口，T10 仅在被指派时集成所选范围。
