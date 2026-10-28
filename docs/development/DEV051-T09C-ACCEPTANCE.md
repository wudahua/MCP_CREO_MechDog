# DEV-051 T09C 验收卡：cursor 协议复核（P3）

日期：2026-10-28。阶段：**离线协议调查完成，无不一致复现，未登记缺陷/未改业务实现**。工作区 `E:\Projects\MCP_CREO_MechDog`；分支 `codex/dev051-feedback070`。依赖提交 `a3d5b29`（T08C，包含 T08B `086249c` 与 T08A `0b26c66`）；实现提交为本卡所属 T09C 提交（提交号以交接回传为准，本卡不能自指）。

## 来源与隔离方式

外部 0.7.0 反馈 R2 §8.3 称首次调用 `creo_list_models(cursor:null)` 得 `Invalid query cursor`，省略可用；原始协议报文、服务进程身份和模型快照未交付。依据共同交接契约和总计划 T09 节，本次使用 `server.mcp.call_tool()` 走实际 MCP 工具签名、Pydantic 入参解析、返回 JSON 文本与 `structured_content` 序列化；用私有临时目录的 5 个 `model.json` 替换 `generic_bridge.MODELS`。不启动 server lifespan、MCP stdio 进程、Creo、Toolkit 或 native worker；不接触用户实际模型登记。夹具同时覆盖 `creo_list_models` 和 `creo_inspect_model`。这验证当前源码的进程内 MCP 协议层，**不**冒充外部 0.7.0 服务的原始报文重放。

## 协议结果与拒绝层

| 输入/条件 | 当前源码 MCP 结果 | 处理/拒绝层 |
| --- | --- | --- |
| 省略 `cursor` | 两工具均可返回第一页；清单 2/5，`complete=false` | 签名默认 `None` → 查询首查 |
| 显式 JSON `null` | 两工具与省略返回同一结构/内容；schema 为 `anyOf[string,null]`、default null | 入参校验接受，查询将 `None` 视为首查 |
| 有效 `next_cursor` | 清单 2+2+1；详情特征 2+2；末页 `next_cursor=null`、`complete=true`，无重漏 | 查询分页；MCP 文本 JSON 与 `structured_content` 相等 |
| 非法类型 `cursor:123` | `ToolError` 包含 `Input should be a valid string` | 签名/Pydantic 入参校验拒绝，未进入查询 |
| 非法串 `cursor:"invalid!"` | `ToolError: Error executing tool creo_list_models: Invalid query cursor`（详情同类） | 入参校验通过，`decode_cursor` 查询层拒绝 |
| 旧清单 cursor 改 `detail` 或模型 revision | `ToolError: ... Model list changed; restart listing without cursor` | 查询层快照/条件绑定拒绝 |
| 旧详情 cursor 改 `section` 或模型 revision | `ToolError: ... Snapshot or query changed; restart inspection without cursor` | 查询层快照/条件绑定拒绝 |

保存模型清单/详情的 cursor 没有按时间独立过期的承诺；这里“过期”是模型快照变更或查询条件不匹配。实际十分钟冻结过期属于其它列表接口，本任务未扩展。模型状态过滤是另列功能候选，未增加参数，也未用它改变分页。因当前源码中 `null` 与签名/生成 schema 一致，外部报错**未复现**，没有足够证据登记新缺陷或改动 `src/creo_mechdog/model_queries.py`/`server.py`/`generic_bridge.py`。T08B 的 `body_counts` 投影保持原样。

## 文件、身份与验证

实际修改文件：`tests/unit/test_model_query_cursor.py`（新增 4 项离线协议回归）和本卡。无业务接口变化，无原生改动，`bridge.py build` 不适用。受测 commit `a3d5b29` + 本批测试文件，dirty=true（含本任务与另一会话未提交文件）；与 T07 指纹方法一致，`git ls-files` 的 268 个 `*.py`/`native/*.h|*.hpp|*.cpp` 以 CRLF 归一化 SHA256 清单哈希计算 `source_fingerprint=7a6a20853c5af04efec2ea93663c5a10774dcd88a90b3e2826daf1be01b30652`。

环境：Windows x64、PowerShell、`.venv` Python 3.12.14，Ruff 0.17.0、clang-format 23.1.3。实际命令和结果：

| 命令 | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest tests.unit.test_model_query_cursor -v` | exit 0，Ran 4 tests，OK（新测试最终版） |
| `.venv\Scripts\ruff.exe check tests/unit/test_model_query_cursor.py` / `ruff format --check` | 首轮发现新测试的导入顺序、未使用 `asyncio` 和换行；仅修正该文件后再检查 |
| `.venv\Scripts\python.exe -m unittest discover -s tests` | exit 0，Ran 1258 tests in 254.077s，OK |
| `.venv\Scripts\python.exe tools\dev_check.py` | exit 0，`success=true`、`unit_tests=passed`、`native_validation=not_run`；lint 30 / unformatted 16 为存量基线计数，Python 234 / C++ 33 个文件受检 |

`dev_check.py` 报告 `build/development_check.json` SHA256 `05ad306bb07f4786c56d4a4d86c8d644bb042787cf228de884674abcd9b5386d`，`checked_source_sha256=68b034d0db4a3168e5bc86c6e37284ad192255da1a7ccee19245df6a9d8a7b14`，记录 commit `a3d5b2958675658882beef45405cdc4925caa88d`、dirty=true。全量测试中的 `WARNING:creo_startup:Creo startup failed (ValueError)` 来自启动相关单元夹具；测试最终 OK，无未处理失败。查询拒绝的原始错误见上表，本次没有产品修复错误。本卡不把历史源码的实机结果当本次证据。

## 未测与交接

未重放外部 0.7.0 的 `cursor:null` 原始报文，也未验证其具体客户端/服务版本组合；需报告方提供报文、工具 schema、服务版本与原始错误后再比较。真实 Creo 数据、job/model/revision、几何、保存重载、回滚均不适用（本次全为私有模型登记夹具）。给集成人：无冲突的业务代码文件；`model_queries.py`、签名和序列化均未变，新增测试会与任何后续 cursor 改动共同运行。另一会话的台账、两份 0.7.0 计划、0.7.2 归档与运行数据未改写、未暂存。
