# DEV-051 T08C 验收卡：预览图像与视角复核（BUG-066/FEAT-041）

日期：2026-10-28。阶段：**离线替代图像复核完成；原案缺件、未复现、未关闭**。工作区 `E:\Projects\MCP_CREO_MechDog`，分支 `codex/dev051-feedback070`。本次未连接 Creo、MCP 或 Toolkit，未运行实机驱动。

## 输入与缺件

依赖提交 `086249c`（含 T08A `0b26c66`、T08B）。依据共同交接契约、T08C 派发节、总计划 T08 节、BUG-066、T08A/T08B 验收卡，以及 `build/t07_preview_acceptance.json` 和 `build/t07-preview/` 留存物。仅在仓库与 `C:\Users\Administrator\Downloads\0.7.0` 查找原件；下载目录只有四份 `.md`。未找到 BUG-066 的 Part1 星形架/斜槽或 Part2 原模型、原始 `preview.jpg`、同作业 native JSON。原报告的“圆盘消失、7~8 根分离长条”和“近空白”无法逐字/逐像素重放。替代场景明确为 **T07 本机盘体→单贯通孔→四孔阵列**，与原构型不同。

## 替代图像逐张复核

历史报告 `build/t07_preview_acceptance.json` SHA256 `e65b88ebb1c2975f357647515ca86ae43d9ee53069d7ff323c2f8c0f1e170551`，生成时 commit `402821ef`、dirty=true、`source_fingerprint=bda91b09bc27b30bed74eeda79d187665f3a53609f327942de87772cbc8ba2b8`；它是历史实机数据，**不是本次源码的实机验收**。下表图像经本次实际目视打开；SHA256 为当前留存文件实算值。三次建模为同一 model_id `a0a3300a06354c96a3bd321f186f458d`，revision 依次 1/2/3；导出使用同一模型。每次预览的窗口均为 `1001`，`window_matches_model=true`、`current_window_matches=true`，全部捕获步骤码均为 0。`view_matrix_set/get=0`，但 `view_matrix_matches=false`；未存实际回读矩阵，无法判断偏差角度或其与图像内容的因果。

| 图像（`build/t07-preview/`） | 同作业 job_id | SHA256 | 历史体积 mm³ | 本次目视与几何预期 |
| --- | --- | --- | ---: | --- |
| `disk.jpg` | `be6d87619ab646728f8fc7d60c5b8053` | `891b6afa6a695d10a4622fc3c2cd8f08a029496d33a1e942a82a872ec8eacf4d` | 60318.5789 | 连续圆盘、无孔，顶面和侧面可见；基准线叠显 |
| `disk_cut.jpg` | `d181afc8d6b5471485eda65b0b00071c` | `66513f8fb036a4a69e2d770bbbfbcfb20a153bf1b0db0e2bf39b46ef497b6d70` | 56548.6678 | 圆盘保持连续，右前部出现一个圆孔；未见分离长条 |
| `disk_cut_pattern.jpg` | `c9b16d2bf624409d97c952b2b637f5f1` | `52c219494d49f29c36b7ed35745a2bf383140b402f5c4813e6e5a8b43022c25b` | 45238.9342 | 连续圆盘与四个圆孔均可见，孔位呈四象限；未见盘面缺失 |
| `export_job_preview.jpg` / `explicit_jpeg_export.jpg` | `96a00394d27d4173af6a479ba66f3b1d` | 两者均 `52c219494d49f29c36b7ed35745a2bf383140b402f5c4813e6e5a8b43022c25b` | 未在该导出记录给出 | 两张均目视为同一连续盘体和四孔；与阵列图逐字节相同 |

原生面/槽/孔数：历史报告仅提供体积及图像，未保存可用于独立数面的原生几何明细；替代夹具没有斜槽。因而上表的孔数是**图像目视**与夹具预期的比对，不声称完成原案的原生面数核对。体积递减只是旁证，不能单独证明图像正确；`written`、非空及文件哈希也不能替代目视。

`native/preview.h` 当前请求固定 3/4 视图矩阵（行：`[0.70710678,-0.40824829,0.57735027,0]`、`[0.70710678,0.40824829,-0.57735027,0]`、`[0,0.81649658,0.57735027,0]`、`[0,0,0,1]`）。历史输出只保留旋转匹配布尔值，不包含实际回读矩阵。`view_matrix_matches=false` 同时出现在上述视觉完整的图像，故它本身不足以证明画面失真，更不能解释 BUG-088 的文件缺失。FEAT-041 的可选正交/上下/前视仍是独立功能候选，本次未新增视角参数。

## 修改、测试与结论

本批只新增本卡并在 `docs/work-items/BUG-066.md` 追加结论；**没有复现内容缺失或断裂，未改** `native/preview.h`、`src/creo_mechdog/preview.py`、`tools/test_t07_preview.py`、`tests/unit/test_t07_preview.py`，保留 T08A 的 `file_check`/`verification_error` 和 T08B 接口。对应单元命令 `.venv\Scripts\python.exe -m unittest tests.unit.test_t07_preview -v`：exit 0，Ran 27 tests，OK；无原始错误。未改原生源码，故无需 `bridge.py build`。受测 commit `086249c` + 本卡工作树，dirty=true（含另一会话未提交文件）；按 T07 `local_provenance()` 算法对 267 个受跟踪 Python/原生源文件求得 `source_fingerprint=08f230e4b8b714b5d74b43414e9af92e183ac857ee499b0900a1d6d345cb1042`。环境 Windows x64、PowerShell、`.venv` Python 3.12.14；本批不访问 Creo。

原始失真未复现，BUG-066 维持**待复现**。触发下一阶段的材料是原 Part1/Part2 模型、原作业 request/native JSON 与原图，或另一次在唯一 dev 服务的受控实机复现。届时逐作业保存窗口/模型身份、**实际回读**视图矩阵、图像、原生面/槽/孔与体积，再定位显示/投影路径。无原件时替代图像只证明本替代构型在历史运行中可见，不能关闭原案。实机 job/model/revision、重载与回滚：本次不适用；表中 ID/体积均为历史记录。

给集成人：冲突面仅 `docs/work-items/BUG-066.md` 追加段；预览四个共享代码文件未改，接口变化：无。另一会话的台账、两份 0.7.0 计划、0.7.2 归档等未改写、未暂存。
