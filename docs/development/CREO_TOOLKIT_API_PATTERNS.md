# TOOLKIT 对象、遍历与引用：本项目的查证要点

遇到句柄、回调、装配引用或字符串问题时按需读取本文；完整开发链路见 [开发指南](CREO_TOOLKIT_GUIDE.md)。这里是根据本机 Creo **12.4.0.0** 头文件和现有实现独立整理的使用要点，不是现成代码模板，也不表示本次已运行相关 API。不同 SDK 仍需重新核对声明及说明。

## 按问题选择查证入口

以下头文件相对本机 `protoolkit/includes/`；具体路径与检索方法沿用开发指南。

| 问题 | 官方入口 | 本项目可对照的位置 |
| --- | --- | --- |
| 一个几何 ID 到底属于谁 | `ProObjects.h`、`ProModelitem.h`、对应 `ProSurface.h` / `ProGeomitem.h` | [surface_loft.cpp](../../native/surface_loft.cpp) 的引用存在性检查 |
| 同一零件的不同装配实例 | `ProSelection.h`、`ProAsmcomppath.h`、`ProReference.h` | [advanced.cpp](../../native/advanced.cpp) 的组件引用与装配引用处理 |
| 遍历提前结束或结果为空 | `ProSolid.h` 的 `ProFeatureVisitAction`、`ProFeatureFilterAction`、`ProSolidFeatVisit` | [assembly_walk.h](../../native/assembly_walk.h)、[quilt_query.h](../../native/quilt_query.h) |
| 中文名称、文件名或字符串错误 | `ProUtil.h` 的转换函数与 `ProSizeConst.h` 的容量定义 | [worker.cpp](../../native/worker.cpp) 的 UTF-8/宽字符串边界 |
| 多实体零件中漏面或不支持 | `ProSolid.h` 的旧遍历说明、`ProSolidBody.h` 的体级 API | [quilt_query.h](../../native/quilt_query.h) 及实际受影响操作的几何判定 |
| 示例函数找不到声明或无法链接 | 正式 `includes/` 与示例 `protk_appls/includes/` 分别查 | 核对本项目真实 include 与构建依赖，不仅看名字 |

## 1. 句柄与模型项身份

`ProObjects.h` 中，`ProMdl`、`ProSolid`、`ProSurface` 等为指针型句柄；`ProFeature`、`ProGeomitem` 等模型项则共享包含 `type`、`id`、`owner` 的结构。理解布局可以帮助查错，但不能据此把不同类型指针或模型项任意互换。

- 解析引用时同时核对模型所有者、对象类型和 ID；装配实例还需路径上下文。不同模型里相同的 ID 不是同一对象。
- 再生、删除、重定义、模型擦除或重载后，按具体 API 的有效期约定重新取得所需句柄，不把原始指针写进持久化回执。
- 模型项结构也不是跨会话永久身份保证；复用 ID 前要结合本项目的模型登记、revision 和当前存在性检查。不能用“数据库句柄”这一称呼绕过这些检查。
- 需要转换时查对应 Init/Get/转换 API。`ProModelitemInit` 的本机参数顺序为 **owner、item_id、item_type、输出模型项**，不能仅按名称猜参数顺序；模型类别也需在转换为实体等具体对象前确认。

只看编译不一定能发现把整数 ID 与枚举类型位置写反的问题，查声明时要逐一对齐语义。

## 2. Selection、装配路径和 Reference

`ProSelection` 携带的不只是一个几何 ID。`ProSelectionAlloc` 在 `ProSelection.h` 中列出了允许的参数组合；装配场景要提供正确的 `ProAsmcomppath`，不能把零件中的空路径用法直接搬到装配。

1. 确认引用对象属于哪个模型，以及它在目标装配的哪条组件路径上；同一模型的多个实例需要区分。
2. 从有效的顶层/上下文模型和组件 ID 序列构造路径，检查 `ProAsmcomppathInit` 的结果，不传未初始化的路径。
3. 分别核对 Selection 的分配、借用和复制约定。需要独立保存时查 `ProSelectionCopy`；由当前代码拥有的分配或副本按 `ProSelectionFree` 释放。
4. 元素树需要 Reference 时，查 `ProReference.h` 的 `ProSelectionToReference`。它的输出为单独分配的 `ProReference`，该接口明确要求使用 `ProReferenceFree`；不能只释放原 Selection 就认为两个对象都已释放。
5. Reference 赋给元素后，还要读元素 setter 的所有权/复制语义，再确定释放时点。不要从其他 setter 或另一 SDK 版本推断转移关系。

交互式 `ProSelect` 的返回数据有自己的存储约定，不能与上述手动分配统一处理。本项目 worker 接收 MCP 的显式输入，不为了复用 GUI 示例引入选择弹窗或当前鼠标选择依赖。

## 3. Visit：区分过滤、访问和外层结果

以下语义专指本机 `ProSolidFeatVisit` 及其回调定义，不扩展为所有名字带 Visit 的函数的统一规则。

| 位置 | SDK 行为 | 开发时要核对什么 |
| --- | --- | --- |
| filter 回调 | `PRO_TK_CONTINUE` 跳过本对象；其他值进入 action，并作为它的 `status` 参数 | 不把 filter 的其他非零值当成自动终止或自动跳过；action 需要处理收到的状态 |
| action 回调 | 返回 `PRO_TK_NO_ERROR` 继续；其他值终止并传回外层 | 若主动找到目标而结束，记录明确的命中标志及约定的结束值，外层按该约定识别 |
| 外层 `ProSolidFeatVisit` | `PRO_TK_E_NOT_FOUND` 可表示集合为空或全部被过滤 | 只有查询契约允许空结果时才按空处理；不把所有非零都改为成功，也不直接推断模型损坏 |

回调中的 `status`、外层结果和“有没有找到目标”是不同信息，应分别保留。检查 `app_data` 指向的上下文在遍历期间有效；回调内使用 C++ 容器或可能抛出的助手时，沿编码规范在 SDK 边界内处理异常，不让异常跨 C 回调传播。

`ProSolidFeatVisit` 会遍历内部特征；是否通过 `ProFeatureVisibilityGet` 过滤，应由这次查询需要的对象范围决定，不默认把内部特征都当成用户建模特征，也不默认全跳过。

## 4. 函数返回类型与字符串边界

函数以 `Pro` 开头并不保证返回 `ProError`。本机 `ProUtil.h` 中的 `ProStringToWstring` 返回 `wchar_t*`，`ProWstringToString` 返回 `char*`，调用方提供目标缓冲区。这两个名字不是一组分配/释放函数，不能套用错误码检查宏或自动 Free。

- 查真实返回类型、目标缓冲区由谁提供、容量按字节还是字符计算，以及终止符要求。固定名称容量不能代替 UTF-8 多字节容量核算。
- 上述 SDK 转换函数使用 Toolkit 应用当前编码，不保证把任意 UTF-8 正确转换。MCP JSON 的 UTF-8 与 Creo 宽字符串之间优先沿用 `native/worker.cpp` 已有边界方法，新增边界再核对无效输入、长度和返回条件。
- 标准输出属于 MCP 协议。外部示例的 `printf` 或交互提示不能直接放入服务输出路径；日志位置和诊断方式沿用现有实现。

## 5. 多实体与弃用 API

本机 `ProSolid.h` 明确将 `ProSolidSurfaceVisit` 标为自 Creo 7.0 弃用，并注明它不处理多实体零件；列出的后继是 `ProSolidBodySurfaceVisit`。所以找到“遍历全部面”的旧示例，不足以证明覆盖当前模型的全部面。

设计面级查询时先说明对象范围：一个体、全部材料体、独立 quilt，还是特征拥有的几何。`ProSolidBody.h` 可作为 `ProSolidBodiesCollect`、体状态及 `ProSolidBodySurfaceVisit` 的核对入口；旧版 SDK 的编译门控与空结果仍需分别处理。

体级 Visit 的签名不能套用旧的实体级 Visit：本机 `ProSolidBodySurfaceVisit` 接受 body、action 和 app_data，没有旧接口的 filter 参数。是否采用体级路线、怎样覆盖 quilt 及保持原有查询行为，由目标操作的契约决定；本次只整理该注意点，不更换现有实现。

## 6. 区分正式 API、示例辅助代码和项目助手

按**具体声明与实现位置**判断，不只看前缀：

- `protoolkit/includes/ProUtil.h` 是本机正式 SDK 头文件，其中有官方工具函数；不能因为名称中有 Util 就一概判为示例代码。
- `ProUtilVectorCopy`、`ProUtilVectorLength` 可在本机 `protk_appls/includes/UtilMath.h` 找到，是示例辅助代码的查证入口；使用前还需找到实现及链接依赖，不能假定正式 Toolkit 库自动提供。
- 本项目的 `create`、`resolve`、错误包装等属于仓库助手，按真实作用域和失败路径使用；不要从通用样例另建一套未接入的辅助框架。

缺少某个示例 helper 时，先确认是否能用项目已有助手或正式 API 完成。引用官方示例用于理解，不把整份示例辅助实现搬入 MIT 源码包。

## 检索与来源

在仓库根目录设置开发指南中的 `$sdkRoot` 后，可只读搜索：

```powershell
rg -n -A 24 'ProModelitemInit' "$sdkRoot\includes\ProModelitem.h"
rg -n -A 24 'ProSelectionAlloc|ProSelectionCopy' "$sdkRoot\includes\ProSelection.h"
rg -n -A 20 'ProSelectionToReference' "$sdkRoot\includes\ProReference.h"
rg -n -A 25 'ProFeatureVisitAction|ProFeatureFilterAction|ProSolidFeatVisit' "$sdkRoot\includes\ProSolid.h"
rg -n -A 18 'ProStringToWstring|ProWstringToString' "$sdkRoot\includes\ProUtil.h"
rg -n -A 24 'ProSolidBodiesCollect|ProSolidBodySurfaceVisit' "$sdkRoot\includes\ProSolidBody.h"
rg -n 'ProUtilVectorCopy|ProUtilVectorLength' "$sdkRoot\protk_appls\includes\UtilMath.h"
```

主题缺口评估参考了 [CSCTACG/creo-dev 的固定审阅版本](https://github.com/CSCTACG/creo-dev/tree/5014ee50db80f69053e129ba0e4cd271325fafb7)。其 [CC BY-NC 4.0 LICENSE](https://github.com/CSCTACG/creo-dev/blob/5014ee50db80f69053e129ba0e4cd271325fafb7/LICENSE) 与本项目的 MIT 分发不同；本文未引入其原文或示例代码。技术说明以本机头文件、对应官方帮助及项目实际实现独立核对，见 [DEV-085](../work-items/DEV-085.md) 的来源、取舍、验证及未测范围。
