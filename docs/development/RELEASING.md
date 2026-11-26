# 分支、版本与源码发布

`main` 保持可交付，开发使用 `codex/<条目>-<主题>` 短分支。提交标题指明 ID 和具体改变，例如 `BUG-002: retry atomic registry replacement`；无需引入复杂的长期分支或强制 Conventional Commits。

## 合入 main 必须同步发布

自 2026-10-16 起，每次将变更合入或直接提交到 `main`，必须在同一次交付流程中生成并发布对应版本的 GitHub Release。功能、修复、文档和工程配置变更均适用；开发分支上的普通提交不要求发布。

1. 合入前确定尚未发布的目标版本，按下述版本约定同步 `version.py`、相关版本元数据和版本说明；已有版本已发布时必须递增版本号，不能复用旧版本承载新的主干变更。
2. 合入前完成下述适用发布门槛和附件准备；合入后，以本次变更对应的实际主干提交建立 `v<版本号>` 标签，版本号必须与该提交的 `version.py` 一致。最终附件必须由该提交源码生成。
3. 发布同名版本的 GitHub Release，附版本说明、验收摘要、实际环境、未测范围、源码包、种子包及各自 SHA256。Pre-release 按项目成熟度设置；草稿不算已发布。
4. 核对远端主干提交、标签指向、Release 版本及附件校验和，并在 PR 或交付记录中回填提交号、版本号、Release 链接和附件校验结果。

仅完成合并、推送或标签不能视为交付完成。Release 发布失败或附件缺失时，记录原因并继续补齐；完成报告必须明确尚未交付，不能将发布另列为可选后续工作。历史发布与验收记录保留原日期和实际范围。

## 版本约定

当前版本为 0.47.1（2026-11-26 PATCH，交付 [BUG-187](../work-items/BUG-187.md) 主基准面偏移默认法线对齐与草图 `frame_mismatch` 告警及 [DEV-104](../work-items/DEV-104.md) 开发入口统一与台账复核，公开工具 112）。 [版本说明](../release-notes/RELEASE_NOTES_0.47.1.md) · [发布记录](../validation/RELEASE-0.47.1.md)

此前的 0.46.1（2026-11-26 PATCH，交付 [BUG-193](../work-items/BUG-193.md) 的提交前零锁 callback 预检，公开工具 111）。 [版本说明](../release-notes/RELEASE_NOTES_0.46.1.md) · [发布记录](../validation/RELEASE-0.46.1.md)

此前的 0.46.0（2026-11-26 MINOR，交付 [BUG-192](../work-items/BUG-192.md)、[FEAT-090](../work-items/FEAT-090.md)、[BUG-193](../work-items/BUG-193.md) 与 [DEV-102](../work-items/DEV-102.md)，公开工具 111）。 [版本说明](../release-notes/RELEASE_NOTES_0.46.0.md) · [发布记录](../validation/RELEASE-0.46.0.md)

此前的 0.45.2（2026-11-26 PATCH，交付 DEV-002 的服务包化、新安装入口与 AI Agent 兼容说明，公开工具 111）。 [版本说明](../release-notes/RELEASE_NOTES_0.45.2.md) · [发布记录](../validation/RELEASE-0.45.2.md)

此前的 0.45.1（2026-11-25 PATCH，交付 BUG-130 的 STL 细化、接缝与诊断，公开工具 111）。 [版本说明](../release-notes/RELEASE_NOTES_0.45.1.md) · [发布记录](../validation/RELEASE-0.45.1.md)

此前的 0.45.0（2026-11-25 MINOR，交付加料保护、实体包围盒、草图默认保真、拔模方向、基准面角度与启动探针，公开工具 111）。 [版本说明](../release-notes/RELEASE_NOTES_0.45.0.md) · [发布记录](../validation/RELEASE-0.45.0.md)

0.44.1 及更早版本的逐版约定记录已归档至 [版本约定历史流水账](../archive/RELEASING_HISTORY_2026.md)。

## 发布门槛

1. 明确本版条目、验收范围及未完成项；完成条目链接本次证据。记录受测提交和源码指纹，工作区有修改时不得仅用提交号代表源码。
2. 运行 `tools/dev_check.py`，检查所有适用单元回归。存量风格基线需显式说明，不宣称全库严格格式通过。
3. 在本机 Windows x64 / Creo 12.4.0.0 / 匹配 SDK 和编译器环境运行原生发布回归。根据改动影响选择当前和历史套件，逐项记录命令、几何断言、参数编辑、保存擦除重载与适用回滚结果。完整回归未执行时列出具体未测模块，不把旧版本通过数改标为本版通过数。
4. 核对工具列表与 `capabilities.py`、`creo_capabilities` compact/full 的支持摘要、32 KiB 分页预算、文档、版本、种子数、种子指纹及兼容矩阵。本地 `release_status` 应符合 `version.py` 的候选后缀，完整覆盖声明与远端 `update.is_prerelease` 分开核对。新增单位相关接口应列出毫米、英寸、混合和未知单位证据，保留实际单位名、换算、原始查询码；未知为 null，不把未执行查询填成成功。按用户 2026-10-15 要求，Creo 10 独立复测和双版本验收不作为发布门槛；其他环境收到具体反馈后再登记跟进。Creo 9 与匹配 Toolkit 9 已按 2026-10-16 决定纳入支持/要求范围，BUG-033 编译探测修复已实现；本机无 Creo 9 SDK，实机编译与运行时均未验收；发布说明须如实标注该状态。已有不同版本的测试事实分别保留，不跨环境外推通过。
5. 使用 `tools/package.py` 与 `tools/package_seeds.py` 制作源码和种子附件；检查分发白名单、第三方许可、配置模板、开发配置、种子及 SHA256。两个打包脚本各自在 ZIP 同目录生成 `<zip>.sha256`（内容为 `<完整 SHA256>  <文件名>` 一行），该文件是发布附件的一部分，不是本地临时产物。种子附件与源码包必须成对发布，顺序固定：先用 `tools/package_seeds.py --output <new-seed.zip>` 确定性构建种子包，把实测 SHA256 显式回填到 `docs/seed_package.json` 的 `seed_archive_sha256`（同时写 `compatible_server_version`），再重建一次确认哈希不变，最后用 `tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip>` 制作源码包。**DEV-061 起 `tools/package_seeds.py` 构包后默认校验 `docs/seed_package.json`**：未回填或版本不符时保留归档、打印应回填的摘要并以非零退出（`--allow-record-mismatch` 只能用于准备回填，不得用于发布）；`tests/unit/test_seed_record_gate.py` 也在单元阶段守同一件事。`tools/package.py` 的 `--seed-archive` 是必填项：缺参、摘要不符、版本不符、两份种子清单不一致或 README 当前版本段滞后都在写出任何源码包或 stage 文件之前失败（exit 非零）。旧调用不静默猜选父目录 ZIP，须补该显式参数；从新目录解压并运行适用检查，随后在具备 SDK 的环境验收安装和建模。**DEV-075 起把「官方 `source.zip` 解压后跑全量单测」作为独立门禁**：解压目录没有 `.git/`，`local_provenance()` 等工作树来源记录允许降级为目录遍历并标记 `git_unavailable`，但测试结论必须与 git 工作树结果分开记录，不能用工作树的通过数代替源码包结论。
6. 核对实际验收源码与本次变更对应的 `main` 提交一致，从该提交建立版本标签并发布 GitHub Release，附版本说明、验收摘要、环境与范围限制。核对附件及校验和，并回填 Release 链接。发布平台标记 Pre-release 与项目成熟度一致。
7. **Release body 必须直接列出源码包与种子包的文件名及完整 SHA256，Release 附件必须固定为四个文件**（DEV-045：0.4.1～0.4.3 的好做法在 0.4.4 漏写，升级者只能去主干 `docs/validation/RELEASE-*.md` 另找一步；DEV-045/C01：0.11.7 与 0.12.0 只上传两个 ZIP，漏传两个 `.zip.sha256` sidecar）。四个附件是 `MCP_CREO_MechDog-<版本>-source.zip`、同名的 `.zip.sha256`、`MCP_CREO_MechDog-<版本>-seed-library.zip` 与同名的 `.zip.sha256`；sidecar 由打包脚本生成，文件名必须是 `<zip 文件名>.sha256`。上传命令须逐个列出四个文件，例如 `gh release create v<版本> <source.zip> <source.zip.sha256> <seed-library.zip> <seed-library.zip.sha256> --title ... --notes-file ...`；不要用 `*.zip` 通配代替清单（通配会漏掉 sidecar）。发布后用 `gh release view <tag> --json assets` 或 `tools/check_release_assets.py --tag <tag>` 核对远端恰有这四个附件、两个 sidecar 的哈希与对应远端 ZIP 摘要一致，再报告交付完成；核对结果写入发布记录。已发布 Release 与附件保持原样，不回填旧版本。
8. 文档与状态一致性逐 ID 核对：`version.py`、当前版本说明的标题与正文、[docs/DEVELOPMENT.md 当前入口](../DEVELOPMENT.md)、本文件「版本约定」段的「当前版本为 X」行、主台账（含完成档案）、本版交付 ID 的工作卡首页及远端 GitHub Release（已发布／草稿／不存在）必须一致。**“本版交付 ID”同时包含功能/接口卡（FEAT）、工程整理卡（DEV）与缺陷修复卡（BUG）**（DEV-077，对应 0.18.2 反馈 P1-1）：本版新增或扩展的能力，其 FEAT 卡首页状态与目标版本必须与 `capabilities.py`、README 和版本说明一致；DEV/工程卡与 BUG 卡同样按本版实际交付范围核对，能力已发布而卡仍写“开发中/未排期”或逐 ID 表写“无开放项 / 一致”却保留“开发中”均视为本项未通过（DEV-062，对应 0.11.0 反馈 F02 §4）。合入前按候选状态核对一次，发布后按实际状态再核对一次；不允许旧版本遗留的"未发布"描述继续出现在当前入口、主台账或版本说明首部。核对时对本版交付的每个 ID 分别记录：技术状态、实际交付版本、仍开放范围，以及卡首页／主台账／版本说明／开发入口／实际 Release 五处链接。**0.23.2 起状态只按五类比较**（DEV-083）：`delivered`（已交付）、`partial`（部分交付／待验收／待复现／已有修复／观察中／待核实）、`developing`（开发中）、`unplanned`（未排期／待规划）、`other`（技术描述，如「已实现并实机验收」，不参与一致性判定）。工作卡状态只读首页 `分类：` 行的粗体词，不读同行的证据句；逐 ID 表的「卡首页」「技术状态」按类比较，「主台账」列必须与真实台账单元格逐字一致。确需保留更保守的措辞时，在该行「差异说明」列写明原因，门禁放行并在发布记录中保留。除发布记录表内 ID 外，主台账所有 `work-items/` 活动行中状态类为 `partial`/`delivered` 的 ID 也必须与工作卡一致，不只检查本版列表。本项为手动清单核对，不为此编写新发布工具、不联网代替人工确认；`tools/check_backlog_counts.py` 只自检台账声明/表行/分类表计数一致，不替代逐 ID 人工核对（DEV-077）。
9. 相对上一正式包的身份核对：以最近一个已发布版本的正式源码包为基准，比较 `native/third_party/**` 原字节（至少含 `json.hpp` 与第三方许可）、回调指纹（沿用 `sha256-repo-lf-v1` 的 CRLF→LF 归一化算法，不因比较而改算法）、DLL 身份（loader／callback／worker 的 SHA256）与注册路径（`protk.dat`、实际注册表项及安装目录）。哈希相同只说明字节未变；内容确有变更时，按实际影响说明是否需要重新注册、迁移或重启，不以"所有哈希必须永远相同"阻止合理更新。本项同样为人工核对，不新增发布工具，不把外部报告中的字节数当作本机受测指纹。

本地构建或检查不等于已发布。GitHub 操作和附件示例见 [原发布说明](../PUBLISH_GITHUB.md)；其 0.2.5 文件名为历史示例，未来按实际新版本生成，不重新发布相同版本的修改内容。

### DEV-072：逐 ID 回填与发布后证据

第 8 步沿用人工清单，但必须逐行填值，不能仅写“文档已同步”。对本版涉及的每个 ID，读取主台账该行第 3 列（状态）、第 4 列（目标版本）及卡首页的状态/目标版本；在下表记录字面值与开放范围。已交付子项而整卡仍有余项时，主台账写“已交付 <版本> 子项；<具体余项> 未排期”。卡或台账仍把已发布实现写成“未实现/待规划”、已实机范围写成“未实机”，均不通过。候选态与发布后各核一次。

| ID | 主台账状态 / 目标版本 | 卡首页状态 / 目标版本 | 本版实际交付 | 仍开放范围 | 差异说明 | 一致 / 待修正 |
| --- | --- | --- | --- | --- | --- | --- |
| [DEV-075](../work-items/DEV-075.md) | 已交付 0.18.2 子项；本分支后续修复未发布 / 0.18.2（已发布子项） | 已交付 0.18.2 子项（离线门禁及来源降级）；本分支后续离线修复已完成、未发布 / 0.18.2（已发布子项）；后续未排期 | t07 provenance 无 git 降级、附件 asset API 二级通道、发布规范与逐 ID/POSTCHECK 回填、FEAT-059 措辞 | 本分支后续离线修复未发布；Creo 实机与远端余项开放 | — | 一致（DEV-077 回填） |
| [DEV-066](../work-items/DEV-066.md) | 部分交付，剩余待规划 / 未排期 | 部分交付 / t07 子项 0.18.2，剩余未排期 | `tools/test_t07_preview.py` 降级与源码包解压全量门禁 | 其余 `tools/` 离线驱动的 git 依赖、负例输出与前置说明 | — | 一致 |
| [FEAT-059](../work-items/FEAT-059.md) | 其它 agent 处理范围（已交付 0.18.0 子项）/ 未排期（剩余范围） | 已交付 0.18.0 子项 / 0.18.0（已发布）；剩余未排期 | 多模型事务日志底座（0.18.0） | 原生骨架创建、受管身份/依赖、完整多模型事务 | 「其它 agent」行按 `other` 不计入一致性比较 | 一致 |

第 7 步的发布后核对必须执行 `python tools/check_release_assets.py --tag v<版本>`；`gh` 不可用或失败时，工具使用 GitHub API 精确 tag 的下载备用路线。自动下载未成功时，人工下载四附件并用 `--dir` 检查，只能记“本地下载目录已校验”，远端发布元数据和 Release body 另行核对。

将发布后结果保存为新的交付记录（例如 `docs/development/RELEASE-<版本>-POSTCHECK-<日期>.md`）或 PR/Release body，逐件列出：实际查询时间（含时区）、tag 指向与 main 提交、Release 链接与状态、附件名/大小/API digest、下载后本地实算 SHA256、sidecar 与正文比对结论、命令与失败范围。API digest 与本地实算不得混称。`docs/validation/` 已成历史的发布前记录及原始反馈保持字节不变，新记录链接旧记录并明确“准备发布”为当时时点。

发布后标签与同名附件冻结；发现已上传内容不一致时保留原物和已知旧/新摘要、大小、取值方式与时间，并在新交付记录说明事实和未确认处。修复通过新版本发布；不能删除重传同名附件或移动旧 tag。缺少取值时间的历史 API 摘要，不得推断其必定对应某个替换前包。

### 0.23.1 起：回填前移（DEV-083）

0.22.0 与 0.23.0 都是先打标签、后回填 POSTCHECK，已发布的 `source.zip` 内因此留下准备态记录。从 0.23.1 起按以下顺序执行，任何一步不通过都不得发布：

1. 提交版本、版本说明、发布记录与 POSTCHECK 段。预发布阶段就要写满：版本、范围、验证命令与结果、四个附件名、种子包 SHA256、两份 sidecar 是各自 ZIP 摘要的说明、Release URL 模板。包内不写 `source.zip` 自身 SHA256（ZIP 不能包含自身摘要），也不写打包时还不存在的 Release id/发布时间。**0.23.2 起这三份文档的本地相对链接必须可解析**：门禁同时检查工作树与源码 ZIP 内的同一批链接，外链、纯锚点和站点绝对路径跳过，`..` 逃出包根的链接直接判失败。
2. `tools/package_seeds.py --output <new-seed.zip>` → 把实测摘要回填 `docs/seed_package.json` → 再构建一次确认哈希不变 → `tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip>`。`package.py` 写出源码 ZIP 和 stage 前检查当前源码的发布记录及适用的单测证据，写出后复核四附件及 ZIP 内记录。
3. 打标签、发布、逐个上传四个附件；**不重传、不改 tag**。
4. `tools/check_release_assets.py --tag vX.Y.Z` 必须 exit 0；版本 ≥ 0.23.1 时该命令会解压源码包并再次运行记录门禁。Release id 与发布时间只回填到 `main` 的 POSTCHECK，不要求进入已冻结的包。
5. 发布说明或发布记录声明全量单测通过时，先运行 `tools/test_unit.py --report <本轮新路径>`，再将同一路径作为 `--unit-report` 传给 `tools/package.py` 和可选预检 `tools/check_release_records.py --version X.Y.Z`。每次尝试使用一个新报告路径；测试中断时报告保持 `running`，重新运行会拒绝覆盖旧报告。门禁核对完成状态、统计、版本、提交和受测源码指纹。常规 `build/unit_test_report.json` 继续提供开发诊断。只校验远端附件时，源码 ZIP 不包含本机报告，仍按包内记录和四附件检查。版本低于 0.23.1 时记录门禁跳过。

### 打包调用迁移（DEV-053 P04 / BUG-089 防复发）

`tools/package.py` 新增必填 `--seed-archive`，源码包不再在缺少种子附件时生成：

| 旧调用 | 新调用 |
| --- | --- |
| `python tools/package.py --output <new-source.zip>` | `python tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip>` |
| `python tools/package.py --output <new-source.zip> --stage <dir>` | `python tools/package.py --seed-archive <new-seed.zip> --output <new-source.zip> --stage <dir>` |

`--seed-archive` 接受本地 ZIP 路径。校验不通过时命令 exit 非零，不创建源码 ZIP、不写 stage 目录，也不回退为警告继续；既有"拒绝覆盖既有输出"和"stage 目录必须为空且与工程分离"的保护保持不变。

## 发布回归记录模板

每个发布候选在 `docs/validation/` 保存可审查摘要，完整机器日志保留在忽略的 `build/`。

```text
版本与条目：
提交、dirty 标志、受测源码指纹：
日期与 Windows/Python/Creo/SDK/MSVC 环境：
命令及结果（单元 / 原生 / 安装 / 源码包）：
原生修改保存重载、参数编辑、回滚证据：
未测模块、失败用例、兼容限制：
源码包及种子包 SHA256（文件名与完整哈希，写入 Release body）：
Release 附件清单（四个：两个 ZIP 及各自的 `.zip.sha256`；逐个记录远端名称与存在性）：
发布候选验收结论：
合入 main 的提交、版本标签及指向：
GitHub Release 链接与发布状态：
远端附件与 SHA256 核对结果（四个附件逐项一致，含 sidecar 内容与对应 ZIP 摘要）：

逐 ID 状态核对（候选态 / 发布后各一次）：
| ID | 技术状态 | 交付版本 | 剩余范围 | 卡首页 | 主台账 | 差异说明 | 版本说明 | 开发入口 | 实际 Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

发布说明、发布记录与 POSTCHECK 的本地相对链接核对（0.23.2 起，必须全部可解析；外链与纯锚点跳过，逃出包根的链接直接判失败）：
相对上一正式包核对（上一版本：____）：
| 项目 | 上一版 | 本版 | 结论 / 注册影响 |
| --- | --- | --- | --- |
| native/third_party 原字节（含 json.hpp、第三方许可） | | | |
| 回调指纹（sha256-repo-lf-v1） | | | |
| loader DLL SHA256 | | | |
| callback DLL SHA256 | | | |
| worker SHA256 | | | |
| protk.dat / 注册表路径 | | | |
| 实际注册影响（未变 / 需重新注册 / 需迁移 / 需重启） | — | — | |
```

## DEV-076：唯一发布后核对入口与收尾

发布后核对唯一入口为[RELEASE-POSTCHECK-2026-11-07.md](RELEASE-POSTCHECK-2026-11-07.md)。分散在validation的旧核对原件保持字节不变，在入口逐版链接实证；不能只留“见发布记录/待回填”。每版分别记录来源和实际检查时间（UTC及+08:00）、本地/远端标签与提交、四件名称/大小/API digest/实算SHA256/sidecar/body、命令和退出码；本地标签与报告方陈述不能充当本轮远端核对。**0.23.1 起，包内 POSTCHECK 与发布记录是打包时点快照**：已冻结包内的同版本段落不再回改，完整结论与后续补记以 `main` 上的同名段为准；新增证据只追加到 `main`，不重传或覆盖已发布附件。

交付ID核对同时包含FEAT能力卡、DEV工程卡和BUG修复卡，逐卡检查首页状态/已交付版本/开放余项与完成档案。核对时间未知时明确unknown，不把准备时间或近似00:5x改写成虚构的发布后时刻。exit0后必须将结果和来源加入上述入口并消除当前收尾记录占位，才能报告交付完成。历史发布前模板保留原貌，用入口所链的新勘误补记，不回写已发布tag或附件。

## 0.26.0 起：交付快照、审定 TXT 与发布前后证据

本节规则从首次采用交付快照的版本生效；没有 `docs/releases/<version>.json` 的历史版本继续按 0.23.1—0.25.0 的旧检查核验，不回补、不重打包。

### 交付范围快照

- 打包前由人/开发 AI 从本次实际变更、`docs/BACKLOG.md`（或完成档案）和工作卡冻结 `docs/releases/<version>.json`：`schema_version=1`、`version`、`previous_version`、`previous_release_tag`、`previous_release_commit`、`remote_verification`、无重复的 `delivery_ids`。
- 快照是发布范围记录，**不得**从待检查的逐 ID 表自行推导；它也不取代 BACKLOG 的当前状态。
- 门禁要求逐 ID 表的 ID 集合与快照完全相等，`交付版本` 列必须精确等于本版，`实际 Release` 列必须为 `v<version>`。替换成合法但非交付的 ID、漏行、多行都会拒绝。
- 已移入 `docs/BACKLOG_COMPLETED.md` 的交付 ID 视为有效来源，但归档状态必须是已交付/部分交付类；未知状态不会被当作已交付。
- 「差异说明」只解释明确的技术状态/卡首页类别差异，不再豁免主台账字面比对。
- 表外的活动行同样扫描：主台账为开发中/未排期而工作卡首页已写已交付，视为矛盾。

### 上一版本基线

- `previous_version/tag/commit` 在冻结时显式审核；`previous_release_tag` 必须为 `v<previous_version>`，`previous_release_commit` 为 40 位提交号。
- 版本说明与发布记录中的每个 `上一版本：X` 都必须等于快照的前版；`main` 上要保留「与直接前版」和「跨版功能对照」的区别，不能只改标题而沿用不相符的 worker 摘要。

### 发布前后证据

- 冻结包的 `remote_verification` 为 `pending`，发布记录必须写「发布后执行，当前未验证」；包内不得出现 `--tag … exit 0`、「four assets downloaded and verified」等远端已验措辞，也不得虚构 Release id/时间。
- 发布后把真实列表、标签指向、附件摘要和 `exit 0` 结果追加到 `main` 的 POSTCHECK；冻结包内快照不回写。发布后检查按「打包阶段快照 + 远端独立证据」两段记录，避免流程互锁。

### 审定 TXT 分发

- `docs/distribution_evidence.json` 是 TXT 的唯一白名单，每项记录 `path`、`bytes`、`sha256`；路径必须位于 `docs/` 下、以 `.txt` 结尾、不得逃根或指向符号链接。
- `tools/package.py` 在打包前逐文件校验字节与摘要；缺失或变更即拒绝。未列入的 TXT 一律不入包，仍不扩大到配置、日志、用户模型、SDK/许可数据。
- 新增证据只追加清单，不改写历史 manifest；已发布包的附件不重传。
