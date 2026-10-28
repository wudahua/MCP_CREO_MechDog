# DEV-051 T08A 验收卡：预览输出文件缺失（BUG-088，离线阶段）

日期：2026-10-28（Asia/Shanghai）。阶段：**离线定因（诊断缺陷已修）/ 原发现象未复现 / 实机待指派**。分支：`codex/dev051-feedback070`；工作区：`E:\Projects\MCP_CREO_MechDog`。本次未连接 Creo、未启动 MCP/Creo、未提交任何 Toolkit 作业、未重跑建模。状态不是“预览缺失已修复”：报告人所见的两次 `failed`/`-4`/`bytes=-1` 仍不能在离线判定为文件缺失、占用还是路径问题，见“定因边界”。

## 输入与来源

- 必读：[AGENTS.md](../../AGENTS.md)、[派发表](0.7.0-FEEDBACK-TASKS-2026-10-28.md)（共同交接契约、T08A 节）、[BUG-088 工作卡](../work-items/BUG-088.md)、[DEV-047 T07 验收卡](DEV047-T07-ACCEPTANCE-2026-10-26.md)（共享截图步骤的交付来源），以及 [DEV051-T03](DEV051-T03-ACCEPTANCE.md)/[T05](DEV051-T05-ACCEPTANCE.md) 的交接格式。
- 反馈原文：`2026-10-27_CREO_0.7.0_钣金增料与四壁折边仍未修复验收报告.md` R1 N3（四次外部建模调用中两次 `preview_status="failed"`、`failed_step="output_file"`、`failed_code=-4`、`bytes=-1`，此前 display→raster 全 0，`view_matrix_matches=false`）。
- 原始 request/job/native JSON 与图像**未随报告交付**，本次也未新取得：无法逐字重放。
- 本次受派范围仅 T08A 离线阶段：不连接 Creo、不改版本、不合 main、不推标签/不 push、不发布、不做 T08C。工作区既有无关改动（`.gitattributes`、`docs/BACKLOG.md`、`docs/DEVELOPMENT.md`、两份 0.7.0 计划、`docs/work-items/BUG-032.md`、`DEV-051.md`、`FEAT-034.md`、`session_activity.json`、`session_erase/`、`examples/wb_unsaved_03.prt.1`、`.codebuddy/`、`.workbuddy/`、`.zcode/`、untracked 的 `0.7.2-FEEDBACK-*` 与 `docs/validation/feedback-0.7.2-2026-10-28/`）均未暂存、未改写、未删除。

## 路径定位（T08A 第 1 项）

单向调用链，只有一处产生 `failed_step="output_file"`：

| 层 | 位置 | 行为 |
| --- | --- | --- |
| 原生 | `native/preview.h` `capture_preview()` | 绑定窗口→当前窗口→视图矩阵→refit→refresh→repaint，全部为 0 后调 `ProRasterFileWrite`；返回 0 后**立即**在同一函数里查文件 |
| 原生 | 修改前：`std::filesystem::file_size(path, error)` | `error` 非空即 `file_bytes=-1`，`failed_step="output_file"`，`failed_code = error ? PRO_TK_E_NOT_FOUND : PRO_TK_GENERAL_ERROR` |
| 原生 | `preview_outcome_json()` / `preview_written()` | 只有 `failed_step` 为空、raster=0、`file_bytes>0` 才 `status="written"` |
| Python | `src/creo_mechdog/preview.py` `normalize_preview()` | 按原生 `status` 走；若原生声称 written 而本地 stat 失败/为空，降级为 `failed` |
| 消费 | `bridge.compact_job()` → `creo_get_job` | `preview` 整块进 compact 结果（32 KiB 预算） |

关键事实（离线可证，非推测）：

1. **报告的 `-4` 不是“文件不存在”的证据。** `ProToolkitErrors.h` 中 `PRO_TK_E_NOT_FOUND = -4`，但修改前代码把**任何** `std::filesystem` 错误都映射成 -4（共享冲突、拒绝访问、路径过长、I/O 失败同样得 -4）。因此 R1 N3 的 `failed_code=-4` 与“文件确实不存在”不可区分。
2. **修改前该阶段没有任何真实错误细节。** 只留 `bytes=-1`，`std::error_code` 的 value/category/message、目标路径是否绝对、父目录是否存在、路径是否存在、大小是否 0 全部丢弃。报告人只能看到 -4。
3. **落盘与确认是两个阶段**，但修改前二者共用一个 `failed_code` 空间；raster=0 只说明 Creo 接受了请求。
4. Python 侧另有一处自造码：原生说 written 而本地复检失败时，`failed_code` 会被写成 raster 码或 `-1`。`-1` 是 `PRO_TK_GENERAL_ERROR`，会被误读成 Toolkit 故障。

## 定因边界（T08A 第 3 项）

- **未定因**：没有原始 native JSON/图像，也没有本机复现，无法判定 R1 N3 是“文件未生成/路径不同/尚未落盘/被占用/权限/其他 I/O”。任务要求“不猜权限/占用”，因此本卡不写任何单一根因。
- **已定因并修复的是诊断缺陷**：错误码丢失 + 全错误映射 -4 + Python 自造码。它使“区分原生 raster 失败与文件系统检查失败”这一验收目标在修改前不可能达成。
- **未加有界文件检查重试。** 派发表要求“定因后才决定修复或有界文件检查重试”。现在没有真实 `error_code`，加 sleep 重试等于用重试掩盖未定根因，并会把“延迟后才出现的文件”当成稳定产物。重试留给实机阶段：若实测 `error_code` 为 32/33（共享冲突）或 5（拒绝访问），再按有界（次数/总时长固定、每次结果入 `file_check`）方案决策。本次改动**不含任何 sleep/重试/重跑**，单元测试对此有结构断言。

## 修复内容

`native/preview.h`：

1. 新增独立阶段 `preview_confirm_file()`，raster 返回 0 后调用；记录 `absolute`、`parent_exists`、`exists`、`is_file`、`size`、`error_code`、`error_category`、`error_message`（截断 160 字符以守响应预算）。
2. `failed_code` 只对“路径确实不存在”映射 `PRO_TK_E_NOT_FOUND`（`preview_is_missing()` 同时接受 generic/system 两类 ENOENT），其余错误映射 `PRO_TK_GENERAL_ERROR`，真实码保留在 `file_check`。
3. `preview_outcome_json()` 输出 `file_check` 块：raster 未成功时为 `null`（没有可确认的文件），成功时带 `stage="after_raster"`。
4. `preview_written()` 判据不变：仍要求 raster=0 且文件字节 >0。

`src/creo_mechdog/preview.py`：

1. `file_check` 白名单透传，未知形状降级为 `null`。
2. 新增 `verification_error`（本地 stat 的异常类型名，例如 `PermissionError`），**不**在本地再猜一个数字码。
3. 删掉“原生 written 但本地无法确认”时自造的 `failed_code`；该状态下 `failed_code=null`，真实证据在 `file_check` 与 `verification_error`。
4. 保留原生的 `failed_step`（例如 `output_file`）；只有原生没给步骤名时才用 `output_file_verification`。

## 隔离夹具覆盖（T08A 第 2 项）

全部在 `tests/unit/test_t07_preview.py::PreviewFileConfirmation`，私有临时目录，不连 Creo、不建作业：

| 场景 | 夹具 | 断言 |
| --- | --- | --- |
| 写入失败 | raster=-5、无文件、`file_check=null` | `failed`/`raster`/`-5`，`file_check` 必须为 null |
| 文件不存在 | raster=0、`exists=false`、`error_code=2`/`system` | `failed`/`output_file`/`-4` 保留，真实码 2 与 message 保留，`verification_error="FileNotFoundError"` |
| 空文件 | 路径存在、0 字节 | `failed`，`bytes=0`，原生 `size` 不被改写，`file_verified=false` |
| 检查失败 | 原生 written、本地 stat 抛 `PermissionError`、原生 `error_code=5` | 降级 `failed`、`failed_code=null`（不自造）、`error_code=5` 保留、`verification_error="PermissionError"` |
| 成功 | 非空文件 | `written`、`file_verified=true`、`file_check.stage="after_raster"` |

另有 3 项结构守卫：确认阶段必须发布上述字段与 `error.category().name()`/`error.message()`；`output_file` 分支必须用 `preview_is_missing()` 且不再出现 `error ? PRO_TK_E_NOT_FOUND`；确认阶段不得包含 `ProRasterFileWrite`/sleep 且必须位于 raster 调用之后。

## 本批修改文件

`native/preview.h`（新增确认阶段与 `file_check` 输出，clang-format 已过）；`src/creo_mechdog/preview.py`（透传与失败码语义）；`tools/test_t07_preview.py`（`check_preview` 记录 `file_check`/`verification_error`）；`tests/unit/test_t07_preview.py`（新增 3 个结构用例 + 5 个隔离夹具，既有用例未改）；本卡；`docs/work-items/BUG-088.md`（追加）。未改 `version.py`、`bridge.py`、`server.py`、schema、台账与另一会话文件；未做 T08C 内容/视角判断。

## 依赖提交、受测身份与指纹

- 依赖提交（基线）：`9f129c8d429512775a19a7b721ff7bf72579f1fa`（分支 HEAD，含 T07）。
- 实现提交：本卡所属 T08A 提交（提交号不能自指，以交接报告 `git rev-parse HEAD` 为准）。
- 受测 commit：`9f129c8d` 工作树 + 本批改动；dirty=true（含本批改动、另一会话未提交文件与本机运行数据）。
- `source_fingerprint`：`f1b021e052042906fefcb033e77e5788675e726ac0b082d04259da79bbb289c5`（与 T07 驱动 `local_provenance()` 同一算法：`git ls-files` 的全部 `*.py` 与 `native/*.h|*.hpp|*.cpp` 共 266 个文件，加本任务三个测试/驱动文件的 CRLF 归一化 SHA256 清单哈希）。
- `tools/dev_check.py --skip-unit` 的 `checked_source_sha256`：`7db09a78f05201ffc1fc3fc9e178c36bfee8feba319243fb0a6c9ac1764bf411`。

## 环境

Windows 11 Enterprise x64 / PowerShell；Python 3.12.14（`.venv`）；ruff 0.17.0；clang-format 23.1.3；本机 Creo 12.4.0.0 + 匹配 Toolkit SDK 仅用于编译，**未连接 Creo、未启动 MCP/Creo、未提交 Toolkit 作业**。服务版本入口仍为 0.7.2，未改。

## 命令与真实结果

| # | 命令 | 真实结果 |
| --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m unittest tests.unit.test_t07_preview -v` | 首轮 exit 1：2 错误，均为本批新用例自身缺陷（顺序断言取到 raster 失败分支的 `return outcome;`；缺失文件夹具同时给 `status="written"` 与 `failed_step="output_file"` 两处互相矛盾）。修正断言与修正投影保留原生 `failed_step` 后 exit 0：**Ran 27 tests, OK**；格式/重建后复跑仍 Ran 27, OK |
| 2 | `.venv\Scripts\python.exe bridge.py build` | exit 0，输出 `E:\Projects\MCP_CREO_MechDog\build\creo_worker.exe`；`creo_worker.exe` mtime `2026-10-28 23:04:50` 晚于 `native/preview.h` `23:04:29`，确认重新编译（非复用旧执行器） |
| 3 | `.venv\Scripts\python.exe tools\test_t07_preview.py`（默认离线） | exit 0；`OFFLINE ONLY: no MCP client, connection or preview capture executed … disk=60318.579, after_cut=56548.668, after_pattern=45238.934 mm3`；离线模式按设计不产出报告文件 |
| 4 | `.venv\Scripts\python.exe -m unittest discover -s tests` | exit 0，**Ran 1241 tests in 254.346s, OK**（T07 基线 1233 + 本批 8） |
| 5 | `.venv\Scripts\python.exe tools\dev_check.py --skip-unit` | exit 0，`success=true`、`native_validation=not_run`、`lint_findings=30`/`unformatted_files=16`（均为存量基线计数，未新增）、`cpp_files_checked=33`/`python_files_checked=232`；报告 `build/development_check.json`，SHA256 `1A890949CC1B3B5133F1D54DA37521E5FF9468AF0006FB08A542CB882A94E101` |
| 6 | clang-format 自检 | 格式化后 `clang-format --style=file --fallback-style=none native/preview.h` 输出与文件内容一致（MATCH），仅重排本批新增的两行 JSON 初始化 |

全量 `tools/dev_check.py`（含单元阶段）在 T08B 结束后统一执行一次，结果记入 [DEV051-T08B-ACCEPTANCE.md](DEV051-T08B-ACCEPTANCE.md)；本卡不引用其它指纹的通过数。

## 未测项与下一步

- 未测（需实机，另按共同契约指派并在唯一 dev 服务串行执行）：空件/实体/钣金三种新输出路径下的真实 `file_check`（`exists`/`size`/`error_code`/`category`/`message`）、`job_id`/`model_id`/`revision`、`saved_file_reloaded_and_verified`、失败时的真实回滚；`preview_status` 与实际文件是否一致；显式 JPEG 导出分支是否同样受益。
- 未定因：R1 N3 的两次失败仍不能归到某个具体 filesystem 结果；`view_matrix_matches=false` 与文件缺失的因果关系仍未证实（属 T08C 范围，本次不做）。
- 下一步：实机阶段先用本次新增字段抓一份真实的 `file_check`；若 `error_code` 落在共享冲突/拒绝访问，再提交“有界复查”单独决策；若恒为 `exists=false, error_code=2`，按“文件确实未生成”方向继续查 raster 输出路径（不改 raster 语义）。内容是否正确交 T08C。

## 给集成人的冲突文件与接口变化

- 冲突面：`native/preview.h` 与 T08C 共用（本批只改文件确认阶段与结果 JSON，未动截图顺序/视图矩阵）；`src/creo_mechdog/preview.py` 与 T07 投影同源；`tools/test_t07_preview.py`、`tests/unit/test_t07_preview.py` 为 T07/T08A 共用文件，如需 T08C 扩展请在同一文件追加而非复制。
- 接口变化（只增不改）：
  - 原生 preview 结果新增 `file_check`（raster 未成功时为 `null`）；`failed_code` 语义收紧：只有“路径不存在”才是 `-4`，其余 filesystem 失败为 `-1`，真实码在 `file_check.error_code`。
  - 投影块新增 `file_check`、`verification_error`；原生 claimed-written 但复检失败时 `failed_code` 由自造的 `-1`/raster 码改为 `null`（下游不得再把该字段当作“必有数字”）。
  - `preview_status`/`preview_file`/`preview_code`/`codes` 语义未变；未新增工具、未改 schema、未改 32 KiB 预算算法（`error_message` 截断 160 字符）。
