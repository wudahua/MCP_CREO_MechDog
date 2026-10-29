# Release 0.8.1 发布验收记录

版本与条目：`0.8.1`，DEV-051 文档与归档 PATCH；公开工具 94 个，接口与原生实现均未变化。日期：2026-10-29（Asia/Shanghai）。环境：Windows x64 / PowerShell / `.venv` Python；未连接 Creo 或 WorkBuddy。

受测源码与工作区：开发分支 `codex/dev051-feedback070`，以 0.8.0 主干 `4b4aee59ef15fefff50bc3c3ddae6172ee13f011` 为起点。发布候选检查时工作区含本次允许的文档、归档及版本变更，另有用户保留的本机未跟踪/修改文件；只暂存允许清单。最终主干提交、标签对象及发布平台结果见 Release body 与交付报告，本文件不在标签后追加自指提交。

适用检查：`.venv\Scripts\python.exe tools\dev_check.py` exit 0，`success=true`、`unit_tests=passed`，1341 项单元测试、0 失败、0 错误；历史风格基线 30 lint／16 未格式化文件，`native_validation=not_run`。报告 `build/development_check.json` SHA256 `5eac8e2e78bd4ef7be51bcdd4592fc82747319384716d6024be62f576716fb6c`；受测源码指纹 `a16f4035910652a9bb3755aa66c271f58cecaa1c0fcba49c6ca7620f57b48938`，运行时 `commit=4b4aee5`、`dirty=true`（含本次文档与本机保留文件），不冒充干净主干指纹。0.7.2 四份原件逐件与 manifest 的字节数、SHA256 一致（4/4）；原件保持原字节。无原生改动，不重编。既有 `build/creo_worker.exe` SHA256 为 `f1d9990c7ac376b1007e49e1d87a3add76c10f5d192c3b9c3efe2655ad1f7305`，`build/source.sha256` 为 `5feaca7083bc704caa8dba36b5521b093dffbe8face8abd678f95e2dde9f2d88`，与 0.8.0 发布记录一致；本批未运行原生验收。

种子包：直接执行 `tools/package_seeds.py --output E:\Projects\MCP_CREO_MechDog-0.8.1-seed-library.zip` 时，因原 manifest 的 `compatible_server_version=0.8.0` 与 `version.py=0.8.1` 不同，断言失败（exit 1，未生成包）。本次种子库及 manifest 不变，因此使用同一脚本、仅在该打包进程内将版本参数设为 0.8.0，输出文件名仍为 0.8.1；ZIP 内保留 0.8.0 兼容种子目录，SHA256 `4ed63b3deb40f9a60f237cab949ac9cf5a4bd1f188d0b78f7795c5bdc9d3f12b`，与已发布 0.8.0 种子包完全一致。两次构建均得到 24 文件、9 种子与相同哈希；`seeds.py` 的 expected_digest 无需改动。此为原种子内容的补版附件，不宣称种子库版本升级。

未测与限制：全部 Creo 实机几何、revision、保存重载和回滚未执行；WorkBuddy、Creo 9/10 均未执行；BUG-085 根因未定。T04/T05/T06/T08C 是调查或替代夹具结果，不能视为原案修复。0.7.2 历史实机证据保持原归属。

候选结论：仅文档与归档收口，无新能力。源码与种子包的两次构建确定性、四附件实际 SHA256、下载回核、远端 main/标签/正式 Release 状态均在发布流程完成后记入 Release body 与交付报告；标签后的信息不写入本主干文件。
