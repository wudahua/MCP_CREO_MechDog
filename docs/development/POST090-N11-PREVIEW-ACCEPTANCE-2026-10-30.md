# N11 验收卡：空件预览、图像内容与原件回补（BUG-088/BUG-066，离线阶段）

日期：2026-10-30（Asia/Shanghai）。阶段：**离线材料核对 + 离线诊断完成 / 实机未执行**。分支 `codex/dev051-feedback070`，基线提交 `7198588`（DEV-052 N00 文档阶段）。本次**未连接 Creo、未创建 MCP 客户端、未运行任何 `--live`、未跑 `bridge.py build`、未跑全量单元**。

**本阶段最重要结论（本机离线可判定）**：空件预览失败在本机历史作业中**可复现且已定因到具体配置**——330 个"新建模型 + 零操作"作业中，**0 个**写出 `preview.jpg`，其中 46 个留下与外部报告逐字一致的签名 `failed_step="output_file"` / `failed_code=-4` / `bytes=-1`；942 个带操作的新建模型作业中，**0 个**出现该签名（841 个写出 `preview.jpg`，其余为作业失败/排队/装配与草图类）。判别量为"该作业是否有任何建模操作"，与模型名、模板、体积、面数、失败步骤以外的任何字段无关。**这不等于缺陷已修**：根因在 Creo 侧的栅格写入行为，本次未连接实机，未取得新的 `file_check` 现场。

## 一、依赖、身份与环境

| 项 | 值 |
| --- | --- |
| 依赖提交 | `7198588`（DEV-052：N00 归档七份 0.8.x 反馈并核号登记） |
| 分支 | `codex/dev051-feedback070`（未切换、未合并） |
| 工作区 | dirty；另一窗口未提交改动（`docs/validation/RELEASE-0.8.5.md`、`session_activity.json`、`session_erase/`、`.zcode/`、`.codebuddy/`、`.workbuddy/`）原样保留，未暂存、未改写 |
| 本次修改文件 | `tools/test_t07_preview.py`、`tests/unit/test_t07_preview.py`、本卡、`docs/work-items/BUG-088.md`、`docs/work-items/BUG-066.md` |
| 未改 | `native/preview.h`、`src/creo_mechdog/preview.py`、`version.py`、`server.py`、`bridge.py`、`generic_bridge.py`、主台账、任何 `docs/validation/` 原件 |
| 环境 | Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；ruff 0.17.0；本机 Creo 12.4.0.0 在机但**未连接、未探测** |

## 二、材料核对（可得 / 缺件两列）

检索范围（均为只读，不无限遍历、不推测重建）：
(a) `git ls-files` 全部已跟踪文件；(b) `git log --all` 按文件名与 `-S` 文本检索，含 `--diff-filter=D` 的删除历史；(c) `docs/validation/` 各归档目录；(d) `C:\Users\Administrator\Downloads\` 下 `0.6.0`/`0.6.1`/`0.7.0`/`0.7.2`/`0.8.x` 全部下载目录；(e) `build/` 下 29 个压缩包的成员名；(f) 本机 `jobs/`（35 424 个文件）与 `models/` 的实际产物；(g) 仓库内 `.jpg/.png/.prt` 全部散落文件。

### 可得（本机自有材料，可用于离线判定）

| 材料 | 位置 | 用途 | 数量/事实 |
| --- | --- | --- | --- |
| 空件预览失败现场记录 | `jobs/<job_id>/{request.json,job.json,native_result.json,native.log}` | 复现并定因空件 `output_file/-4` 签名 | 46 个带 `preview` 块的作业；时间 2026-10-27T04:11 → 2026-10-28T10:46 |
| 零操作 vs 带操作的对照语料 | 同上（`jobs/` 全量） | 判别量为"是否有建模操作" | 零操作 330 个（`preview.jpg` 写出 0 个）；带操作 942 个（写出 841 个，出现该签名 0 个） |
| 同会话同模型的后续实体预览 | `jobs/` 内同一 `model_id` 的后续作业 | 证明失败不随会话或模型持续 | 288 个模型的空件首作业之后有后续带操作作业，其中 786 个后续作业写出 `preview.jpg` |
| 空件作业的原生日志 | `jobs/<job_id>/native.log` | 确认栅格各步返回码全 0 后才落到 `output_file` | 46 份均含 `PHASE=display_preview` 与 `PREVIEW={...}` 行 |
| 历史 T07/T13 留存图 | `build/t07-preview/*.jpg`（5 张） | 仅作历史图像内容复核基线 | 本机 2026-10-27 正常渲染，**非**外部原案构型 |
| 空件失败的现成诊断字段 | `docs/validation/feedback-0.8.x-2026-10-30/`（R80x-3、R80x-6、R80x-7 原件） | 外部侧 `file_check` 与 `verification_error` 现场 | 原件已逐字节归档，SHA256 见 manifest.json |

### 缺件（外部原件，均未取得）

| 缺件 | 用途 | 检索结果 |
| --- | --- | --- |
| 原 Part1 星形架 / Part2 模型（PRT/ASM） | 原案几何回放与图像内容对照 | 仓库、下载目录、全部归档、压缩包成员名均无命中；模型名 `part1_star_v2`/`assem1_iris_v2` 仅作为文本出现 |
| 原始 `preview.jpg`（外部失真图） | 原案图像内容基线 | 无命中；本机 5 张图为本机 2026-10-27 产出，构型不同 |
| 外部同作业 request / native / job JSON | 逐字回放外部作业 | 未随 0.8.x 七份 Markdown 交付 |
| T06 原 30 段截面 JSON、平面/帧、前置模型 | T06 原案倾斜草图回放 | 无命中 |
| T07 `gear10.json` / `gear10_snapped.json` / `mc_rings10.json` | 多轮廓原案与近容差端点判据 | 无命中（N00 已列，本轮复核仍无） |
| `scripts/mc_prep.py`、`mc_rings.py`、`sketchgen.py`、`sketch_entities.json` | 链序求解器与端点吸附生成器 | 无命中 |
| 外部探针模型（`probe_gear5_sk`、`probe_mc_v085`/`v085b`、`acc82_sm`、`acc85_sm` 等） | 外部会话内实测载体 | 属外部会话对象，本仓库不存在 |

## 三、离线诊断：空件 `output_file` 失败的定因

**判别量**：该作业是否为"新建模型且无任何建模操作"。100% 分离，无一例外。

| 分组 | 作业数 | 写出 `preview.jpg` | 出现 `output_file` / `-4` 签名 | 有 `file_check` 诊断 |
| --- | ---: | ---: | ---: | ---: |
| 新建 + 零操作 | 330 | **0** | **46** | 0（全部早于 T08A 诊断） |
| 新建 + 有操作 | 942 | 841 | **0** | 240（有操作组含更晚作业） |

**关键区分事实**（原报告与既往结论均未区分）：

1. **不是随机的 I/O 抖动**。同一配置下 46/46 复现，另 284 个零操作作业连 `preview` 块都没有（`preview_code=0`、`preview_file` 有路径但文件不存在）。全部零操作作业**无一**写出图像。
2. **不是"空件失败后该会话就坏了"**。288 个模型在空件首作业之后继续带操作作业，786 个后续作业正常写出 `preview.jpg`。失败随**该作业的配置**走，不随会话、模型或 `model_id` 走。
3. **失败发生在栅格调用成功之后**。46 份 `native.log` 显示 `display`/`refit`/`refresh`/`repaint`/`raster` 全部返回 0，随后才落到 `output_file`；`window=1001`、`window_matches_model=true`、`current_window_matches=true`。即"Creo 接受了截图请求并返回成功，但目标路径上没有文件"。
4. **既有 46 个作业全部早于 T08A 诊断提交**（`0b26c66`，2026-10-28 23:12），因此**没有一个带 `file_check`**。本机至今**没有**取得过空件失败时的 `file_check` / `verification_error` 现场。本轮新增的 `file_check` 只在有操作的作业上出现过（240 个，全部 `parent_exists=true`、`error_code` 全空）。
5. **外部侧现场与本机签名逐字一致**：R80x-3/R80x-6 记录空件 `failed_step=output_file`、`failed_code=-4`、`file_check.exists=false`、`file_check.error_code=2`、`error_category=system`、`error_message="The system cannot find the file specified."`、`verification_error=FileNotFoundError`，且同样声明 `view_matrix_matches` 全程 false。本机 46 个作业的 `view_matrix_matches` 也全为 false——**该布尔值在失败与成功两侧同为 false，因此不能作为失真判据**，与 BUG-066/T08C 既有结论一致。

**未定因（本次不修复、不加重试）**：Creo 为何在零操作的新模型上返回栅格成功却不落文件，本机离线无法判定；既有 `file_check` 诊断需要实机在该配置上重跑才能取到。按派发表"有真实可复现 I/O 原因才做最小修复"，**本次不改 `native/preview.h` 与 `src/creo_mechdog/preview.py`，不加入任何自动重试或落盘确认轮询**。

## 四、单测结果

命令 `.\.venv\Scripts\python.exe -m unittest tests.unit.test_t07_preview -v`：**exit 0，Ran 36 tests，OK**（原 27 项 + 本次新增 9 项）。

覆盖要点：raster/file_check/verification_error 透传；失败阶段原码（`-4` 与 `file_check.error_code=2`）保留；**缺失图像不能通过**（`expect_written=True` 遇 failed 块必须断言失败）；空件失败被记录而不掩盖（`expect_written=False` 记录 `failed_step`/`file_check`/`verification_error` 且 `image=None`）；实体验证成功时保留图像并标记 `human_review_pending`；报告与图像目录按 run_id 唯一且拒绝覆盖既有报告。

ruff：`tools/test_t07_preview.py`、`tests/unit/test_t07_preview.py` 均 `All checks passed!` 且 `2 files already formatted`。

## 五、驱动覆盖（读代码为主）

`tools/test_t07_preview.py` 修改前只覆盖"盘体→切除→阵列→显式导出"，全部是**带操作**的模型，因此结构上**不可能**触发空件场景——这正是 0.8.3 实机"未复现"的原因：夹具里根本没有空件。

| 场景 | 修改前 | 修改后 |
| --- | --- | --- |
| 空件→同会话实体预览 | 无 | `empty_part`（`creo_new_part`，允许失败并记录）+ `empty_part_solid`（同一 `model_id` 续建实体），报告内 `empty_part_file_outcome` 并列两者 |
| 独立 JPEG | 已有 `explicit_jpeg_export` | 保留，图像随本次运行目录留存 |
| 钣金对照 | 无 | `sheetmetal_wall`（XZ 面 185 mm 单线 + `sheetmetal_wall` 232×1 mm），与实体盘体对照 |
| 报告/图像唯一路径 | 固定 `build/t07_preview_acceptance.json` 与 `build/t07-preview/`（会覆盖历史） | `build/post090_n11_preview/<run_id>/`，`--output` 显式指定，**既有报告拒绝覆盖**（退出码 2，连接前拒绝） |

离线运行 `.\.venv\Scripts\python.exe tools\test_t07_preview.py --output build\post090_n11_<runid>\report.json`：exit 0，只打印 OFFLINE ONLY 与夹具体积，未创建 MCP 客户端、未连接。

## 六、离线两栏结论

| 栏目 | 本阶段结论 | 状态 |
| --- | --- | --- |
| **文件写出**（可离线判定） | 空件（新建模型 + 零操作）预览文件**必然不写出**，本机 330/330；判别量为"该作业是否有建模操作"；失败发生在栅格返回 0 之后；失败不随会话或模型持续 | **本机已定因（配置级）**；Creo 侧为何不落文件仍未定因，需实机补 `file_check` 现场 |
| **图像内容**（需实机/人工复核） | 无原案模型与原图，无法逐像素复现外部"分离长条/近空白"形态；本机 5 张历史图构型不同，不能代替原案；`view_matrix_matches=false` 在成功侧同样出现，不能作判据 | **未验证**，仍需实机产出可审查图像 + 人工复核 |

## 七、三类交付状态

| 状态 | 内容 |
| --- | --- |
| **文件验收** | 空件文件缺失的**配置级判别**已由本机历史作业离线确定并有单元锁定；外部报告的 `file_check` 现场与之逐字一致。实机仍需在当前源码上重跑空件以取得带 `file_check` 的现场 |
| **内容人工复核** | 未开始。需实机跑 `empty_part`/`empty_part_solid`/`sheetmetal_wall` 后由人工看图；本阶段无任何图像内容结论 |
| **原案回放** | **不可执行**，缺件见第二节（原 Part1/Part2 模型、原图、外部同作业 JSON、T06 原截面/帧/前置模型、T07 gear10 原始/精确版）。替代夹具**不得**当作原案通过 |

## 八、未测与未做

- 未连接 Creo、未创建 MCP 客户端、未运行 `--live`、未提交任何 Toolkit 作业、未做故障注入。
- 未跑 `bridge.py build`（原生源码未改，无需构建）；未跑 `tools/dev_check.py` 与全量单元（按并行约束留给 N01 窗口）。
- 未修改 `native/preview.h`、`src/creo_mechdog/preview.py`：本阶段无可判定的 I/O 根因，不做猜测性修复、不加重试。
- 未改 `version.py`、未合 `main`、未 push、未发布、未改主台账。
- 本机 Creo 9/10 未验（本卡不涉及 SDK 兼容）。

## 九、实机阶段需要的具体命令与前提

前提：用户点名实机阶段；`MCP_CREO_MechDog_dev` 指向 `E:\Projects\MCP_CREO_MechDog`；按 AGENTS.md 与 BUG-001 纪律人工确认会话可操作（不得以历史 `ready` 或 `--confirm-session-usable` 代替）；`config.json` 的 `auto_start_creo=false`；由唯一负责人串行执行，实机期间不重建 worker。

```powershell
# 1) 空件 + 同会话实体 + 钣金对照（唯一新输出路径，禁止覆盖历史）
.\.venv\Scripts\python.exe tools\test_t07_preview.py --live --confirm-session-usable `
  --output build\post090_n11_preview\<run_id>\report.json

# 2) 离线复跑（本阶段已验证，可重复）
.\.venv\Scripts\python.exe -m unittest tests.unit.test_t07_preview -v
```

实机阶段须分别取得并分开报告：空件作业的 `preview.file_check` / `verification_error` / 原始 `failed_step`+`failed_code`（**不得**由 `view_matrix_matches=false` 直接判失真）；`empty_part_solid` 与 `sheetmetal_wall` 是否写出文件及文件大小；每例的 `job_id`/`model_id`/`revision`/`saved_file_reloaded_and_verified`；以及**人工目视**的图像内容结论。文件写出与图像内容必须分两栏判定。失败或 unknown 时保留现场，不重提已受理作业。

## 十、给集成人

- 冲突面：`tools/test_t07_preview.py` 与 `tests/unit/test_t07_preview.py` 为 T07/T08A/T08C 共用文件，本次为**追加**空件/钣金夹具与唯一输出目录，未改既有四例的断言与顺序；`native/preview.h` 与 `src/creo_mechdog/preview.py` **未改**，接口无变化。
- 报告路径：本次离线证据在 `build/post090_n11/`（材料核对与作业语料扫描 JSON），属本机生成物，不入源码包。
