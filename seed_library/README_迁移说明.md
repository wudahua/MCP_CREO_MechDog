# 换电脑、换 Agent：种子与 MCP 使用说明

种子是包含原生“混合/Blend”的简单 Creo PRT 模板。v0.2.4 的普通混合会复制种子，
创建新的参数草图，再将原生混合改接到这些草图。源文件不改动，最终保留原生特征树。
草图、拉伸、旋转、孔等普通工具不要求此类混合种子，使用本机 Creo 的标准模板。

## 本包包含的已验证种子

| name | 截面数 | 模式 | 混合内部 ID |
| --- | --- | --- | --- |
| two_straight | 2 | straight/直线 | 60 |
| two_smooth | 2 | smooth/平滑 | 60 |
| five_smooth | 5 | smooth/平滑 | 93 |

这些文件逐字节核对过 v0.2.4 实机测试输入；公开摘要在 validation/。
只要沿用随包原始文件，清单中的内部 ID 可以复用；电脑目录改变时需要更新绝对路径。
重新创建或改造种子后须重新核对 ID、数量和模式。文件名和版本后缀请保留。
本包不包含三截面直线种子，不代表其他数量均已验证。

## 换电脑

1. 在目标 Windows x64 电脑安装 Creo 10、匹配的 Toolkit SDK、MSVC x64/Windows SDK、Python 3.12+ x64；
   本轮验证使用 Creo 10.0.0.0，其他版本组合需要重新验证。目标机必须有可用于实际 Toolkit 调用的许可。
2. 解压 0.2.4 源码到例如 C:\MCP_CREO_MechDog，在该目录执行：

   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'

   按本机真实 Creo 路径替换参数。安装脚本重建本地环境和执行器，生成 config.json 与 client-config.json。
   不要从另一台电脑直接复制 .venv、编译二进制、本机配置或 Creo 会话 ID。
3. 将本种子包解压到例如 C:\CreoSeeds；种子与源码可以分开放。
4. 在目标 Agent 的 MCP 设置中导入源码安装后生成的 client-config.json，支持本地 stdio 执行即可。
   客户端配置格式不同时，保留相同的 Python command 和 server.py args。
5. 打开一个 Creo 会话。调用 creo_check_environment、creo_session_status；连接成功后先运行一个原生建模任务，
   验证 succeeded 与 saved_file_reloaded_and_verified == true，确认本机运行和许可实际可用。
6. 普通混合需提供本机 seed_file、seed_feature_id、interpolation，截面数与种子一致。

可用标准 Python 从本包生成与目标机目录匹配的种子参数，例如：

python C:\CreoSeeds\resolve_seed.py five_smooth

输出的 required_section_count 是提示字段，不是 creo_new_loft_part 的参数；其余三项可直接用作该工具参数。
工具还需要 sections（此例为五张 XY 草图，Z 偏移严格递增）。清单和 PRT 可供不同 Agent 共用，不依赖聊天记录。

## 换同一电脑上的 Agent

每个支持本地 stdio MCP 的客户端配置相同的安装目录和启动命令即可。
同一安装目录的 models/ 与 jobs/ 保存受管模型及任务记录，继续修改时查询最新 model_id/revision，顺序提交任务。
不要假定旧聊天记录中的 revision 仍有效。2026-10-11 增量源码内附本库，安装器自动注册；旧发布源码包不含本库，迁移旧版本时仍需带两个包。

## 云端 Agent 和既有模型

目前服务以本地 stdio 运行，没有公开 HTTP 远程入口。纯云端 Agent 需要能在目标 Windows 电脑运行工具的执行端；
仅填 GitHub 仓库 URL 无法连接 Creo。当前未封装远程 HTTP 网关。
本包用于在新电脑创建新模型。既有 MCP 任务记录含绝对路径，不能把旧 model_id 当成新电脑上已注册模型；
仅复制 PRT 可以用 Creo 打开，但当前没有完整的受管模型跨目录导入/重定位工具。

本包提供项目自行创建的测试模型、辅助脚本和说明，项目自身贡献采用 MIT，可与源码包分开发布。它不含 Creo、SDK、二进制、配置或许可，
不提供或转移 PTC 软件授权。目标电脑的 Creo 和 Toolkit 运行条件仍需自行满足。
