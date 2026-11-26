# 渐进布局与模块边界

DEV-002 将服务、任务与通用桥接、Creo 启动协调和桌面 worker 移入 `src/creo_mechdog/`。新安装的客户端通过 `python -m creo_mechdog` 启动服务，已有客户端可继续使用根 `server.py`。根 `bridge.py` 承接构建与后台任务命令。

```text
src/creo_mechdog/     Python 包：服务、输入校验、任务调度、模型登记与建模辅助
native/include/      模块声明、执行上下文与资源包装
native/src/          执行器入口、基础设施与特征实现
native/third_party/  第三方代码与许可
tests/unit/          Python 单元测试
tests/integration/   Creo 实机验收
tools/               构建、发布与证据汇总
docs/                功能台账、开发、安装、版本与验收记录
examples/            可运行建模计划
seed_library/        原生种子和清单
```

## Python 边界

服务层声明 MCP 工具并处理协议输入输出；校验层定义模型和保护；任务层负责通道准入、子进程、终态与诊断；模型层负责登记、revision 和恢复；建模辅助层处理种子、翼型和轮廓。当前 Toolkit 通道忙时立即拒绝新提交，不排队、不自动重试，不提供 FIFO 或容量保证。布局迁移不隐含新增调度能力，按实际规模分包，避免仅为凑目录拆出空层。

DEV-002 区分代码包、只读分发资源与可写数据的位置。`bridge.ROOT` 从 `paths.SOURCE_PATHS` 取得安装根，模型、任务、构建、配置和 Toolkit 锁仍使用该位置。根入口会核对 editable 安装属于同一安装根。MCP 运行信息同时记录两个根入口和五个包内实现的源码指纹。

服务 lifespan 调用 `creo_mechdog.creo_startup` 进行后台初始化。GUI 工作目录为安装根下的 `build/creo_session`，跨源码副本的启动锁、预留和诊断位于当前用户的 LocalAppData，按 Windows 会话、安装和 PSF 定位。

根 `server.py`、`bridge.py` 直接执行时转发包内入口，导入时复用同一个包内模块实例。单元与实机测试路径分批迁移时，同时更新发现入口和文档命令。

## C++ 边界

DEV-003 提取 Toolkit 连接、当前模型、输出目录、特征别名、操作结果等执行上下文，明确资源归属和函数声明。现有 `.cpp` 的 `static` 状态因文本包含而共享；移动文件不能消除这种依赖，也不能据此推断当前存在并发数据竞争。

DEV-004 在上下文明确后逐个模块转为独立编译，维护头文件依赖、符号可见性、SDK include 顺序、执行器与同步 DLL 的边界。改动构建脚本、源码指纹和打包规则，并验证重建缓存。是否引入 CMake 在该条目中按实际需要决定，首批继续使用已有 MSVC 构建桥接。

## 迁移批次

| 条目 | 范围 | 完成条件 |
| --- | --- | --- |
| DEV-001 | 文档、检查、风格基线、CI、打包同步 | 检查入口与回归通过；当前源码包包含全部开发配置；无原生行为变更 |
| DEV-002 | 路径边界、Python 包化、测试路径 | 安装、兼容入口、后台任务、种子及登记定位正确；解压包可验证 |
| DEV-003 | C++ 执行上下文、资源与声明 | 模块边界明确；匹配 SDK 构建和受影响实机用例通过 |
| DEV-004 | 逐模块独立编译、原生测试归档 | 取消相应文本包含；构建缓存正确；保存重载及回滚验收通过 |

## DEV-002 当前批次

当前进度、剩余验收与依赖见 [DEV-002 工作卡](../work-items/DEV-002.md)。

早期包化验收按批次查阅[第一批记录](../validation/DEV-002-batch1.md)、[第二批记录](../validation/DEV-002-batch2.md)和[第三批记录](../validation/DEV-002-batch3.md)。第二批另有 [WorkBuddy 验收记录](../validation/DEV-002-batch2-WorkBuddy-acceptance-20261015.md)。第三批的迁移设计见[已归档的历史计划](../archive/superpowers/plans/2026-11-02-dev002-batch3-package-migration.md)。
