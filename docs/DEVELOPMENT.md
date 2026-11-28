# 开发入口

在[唯一台账](BACKLOG.md)按 ID 或关键词找到对应工作卡，看卡首页的当前结论和余项，再读相关源码。仓库约束见 [AGENTS](../AGENTS.md)，当前版本见 [version.py](../version.py)。

## 准入与日常维护

1. 先核对分支、工作树和现有 ID。从可交付的 `main` 建开发分支；集成批使用其他基点时在卡上记录原因与提交。新增工作先登记目标、范围、验收与环境，缺陷先复现，再区分现象与推测根因。
2. 台账每个 ID 一行，只写优先级、状态、目标版本、下一步和依赖。实测数值、作业号及历史过程留在工作卡或链接的证据中。小修复只补几行；复杂跨模块任务再使用[工作卡模板](templates/WORK_ITEM.md)。部分交付保留余项，整卡完成后移入[完成档案](BACKLOG_COMPLETED.md)。
3. 行为变更与格式整理、路径迁移分开提交。能力变化同步工具描述、README 与能力边界；PR 使用仓库模板。

## 架构与环境

- 查服务调用链、原生编译单元或模块职责，读[架构](development/ARCHITECTURE.md)。代码风格见[编码规范](development/CODING_STANDARD.md)。
- 查 Pro API、元素树或新增建模操作，按[Toolkit 指南](development/CREO_TOOLKIT_GUIDE.md)选择对应章节；Git 检出可使用 `$creo-mechdog-dev`。
- 开发使用 Windows x64 / Python 3.12+；原生构建另需匹配的 Creo、SDK、许可与 MSVC x64。版本支持和已测环境见[兼容矩阵](COMPATIBILITY.md)。本机 MCP 加载目录核对方法见[联调入口](../AGENTS.md#构建测试与开发命令)。

## 命令与检查

以下命令在仓库根目录用 PowerShell 执行。首次配置见[安装说明](INSTALL.md)。已有虚拟环境用 `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` 安装开发依赖；包布局变动后用 `-m pip install --no-deps -e .` 同步可编辑包。

| 改动或目的 | 命令 |
| --- | --- |
| 文档、台账 | `.\.venv\Scripts\python.exe tools\check_doc_links.py` 和 `.\.venv\Scripts\python.exe tools\check_backlog_counts.py` |
| Python / 原生源码统一检查 | `.\.venv\Scripts\python.exe tools\dev_check.py`；含语言、风格基线、离线验收与全部单测。`--skip-unit` 跳过单测，`--strict --skip-unit` 可查全部存量诊断 |
| 定位单个回归 | `.\.venv\Scripts\python.exe -m unittest tests.unit.<module>.<Case>.<test_method>`；根 `tests/` 下的历史用例用 `-m unittest discover -s tests -p test_job_query.py` |
| 单独运行全部单测 | `.\.venv\Scripts\python.exe tools\test_unit.py` 输出 `build/unit_test_report.json`；直接发现用 `-m unittest discover -s tests -v` |
| MCP 契约或会话 | `.\.venv\Scripts\python.exe tools\test_mcp.py --offline` 已纳入统一检查；`--legacy-entry` 测根入口，`--protocol-only` 仅测协议。默认模式等候会话就绪，`--create` 或 `--create --simple` 追加建模 |
| 原生构建、服务与建模 | `.\.venv\Scripts\python.exe bridge.py build` 编译或复用执行器；`.\.venv\Scripts\python.exe -m creo_mechdog` 启动服务。用 `.\.venv\Scripts\python.exe tools\test_general.py` 或相应特征驱动验收 |

统一报告在 `build/development_check.json`。单元阶段默认 900 秒，可用 `--unit-timeout-seconds 1200 --work-item <ID>` 调整。超时按未通过记录。单测隔离外部进程和 Toolkit 通道，冻结源码后的统一检查覆盖全量；定向运行用于定位问题。

实机驱动的开关以各自 `--help` 为准。例如 `tools/test_surface_chain.py` 需同时传 `--live --confirm-session-usable` 才进入实机模式；`tools/test_assembly_pose.py` 编译原生辅助头的用例只提供离线证据。

## 验收与交付

| 改动 | 必要证据 |
| --- | --- |
| 文档 | 链接、ID 唯一性、状态/工作卡、历史原件字节、冲突标记和打包引用；涉及工具或配置时加对应回归 |
| Python 校验/调度/保护 | 统一检查及专项回归；外部进程/会话行为另取实机证据 |
| C++/建模/单位 | 匹配 SDK 构建、对应驱动、实际几何/尺寸/单位、保存重载及适用失败回滚；mm/英寸/混合/未知单位分别声明 |
| 路径/布局迁移 | 安装/客户端/后台入口、资源和数据根、解压源码包验证；原生变化补实机 |
| 合入 main | 未发布新版本、版本元数据、适用验收和打包、标签/Release/附件及 SHA256 远端核对 |

原生成功须任务成功、特征有效、几何断言通过且 `saved_file_reloaded_and_verified=true`。拒绝、超时、unknown、编译通过均不能代替建模成功。证据记录日期、条目、版本、提交、dirty、受测指纹、命令、环境与未测范围；历史证据保留原日期，引用时说明复用边界。

发布步骤和附件核对见[发布流程](development/RELEASING.md)。历史版本按[版本说明](release-notes/)查询。

<a id="workbuddy-测试约定"></a>

WorkBuddy 操作和报告以[黑盒约定](../AGENTS.md#代码风格单位与测试约定)为准。提示词写明场景、输入、预期和报告要求；环境或版本无法通过公开接口确认时写“无法确认”，只有实际并发才记并发通过。
