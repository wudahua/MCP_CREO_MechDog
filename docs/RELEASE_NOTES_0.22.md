# 0.22：工程图、曲面、多实体和 UDF

本文件保留 0.22 阶段的历史开发记录。当前源码版本已更新为 **0.2.3**，最新说明见 [RELEASE_NOTES_0.2.3.md](RELEASE_NOTES_0.2.3.md)。

此源码在已发布的 0.21 上继续开发，版本为 **0.22**。已发布 v0.22 注册 67 个 MCP 工具、66 个启用；新增普通放样种子复用后，本地源码注册 **68 个工具、67 个启用**。增量尚未写入旧发布包。`creo_loft` 仍在入队前拒绝；新入口 `creo_new_loft_part` 的使用与实测边界见 [LOFT_SEED.md](LOFT_SEED.md)。支持 52 种计划操作，其中 51 种启用；新入口是零件初始化工具，不是新增计划操作。数量不等于覆盖所有 Creo 操作。

## 新增能力

| 模块 | 工具/计划操作 | 验证与边界 |
| --- | --- | --- |
| 坐标系 | `creo_datum_csys` / `datum_csys` | 相对坐标系的 XYZ 平移和 XYZ 旋转；平移为毫米、旋转为度。查询原点并验证原生尺寸编辑 |
| 基准点 | `creo_datum_points` / `datum_points` | 同一坐标系下的命名点数组，带原生偏移尺寸。多点特征引用具体点时使用查询获得的 point ID |
| 填充曲面 | `creo_surface_fill` / `surface_fill` | 闭合平面草图生成原生 Fill 曲面和 quilt |
| 加厚 | `creo_thicken` / `thicken` | quilt 的原生加厚；对称 2 → 3 mm 实测。单侧、切除和复杂曲面组合仍需单独验证 |
| 实体化 | `creo_solidify` / `solidify` | 原生实体化接口；已测基准平面切掉立方体的一半。封闭 quilt 增材未单独验证 |
| 多实体布尔 | `creo_boolean_bodies` / `boolean_bodies` | 并、差、交；显式 body ID。两个部分重叠的立方体验证了体积。多目标、多个工具和 keep_tools 未单独验证 |
| 筋 | `creo_rib` / `rib` | 开放轮廓驱动的原生 Profile Rib，支持厚度修改。草图需位于实体内并与相邻实体相交；flip 根据草图方向指定材料侧 |
| 工程图创建 | `creo_new_drawing` | 原生 DRW；来源为服务管理的 part/sheetmetal 已保存版本；使用独立模型副本 |
| 视图 | `creo_drawing_view`、`creo_drawing_projection`、`creo_drawing_view_update` | 一般视图、投影视图、比例、位置和显示样式；已测正视、顶部/右侧投影和轴测 |
| 图纸 | `creo_drawing_sheet` | 新增图纸、修改尺寸与名称；每张图纸分别再生 |
| 注释和表格 | `creo_drawing_note`、`creo_drawing_note_update`、`creo_drawing_table`、`creo_drawing_table_cell` | 可编辑原生多行注释、表格和单元格；支持毫米位置与尺寸 |
| 尺寸显示 | `creo_drawing_dimension` | 将模型已有驱动尺寸显示到视图中，使用来源模型的 dimension ID。不是创建任意测量尺寸、公差或 GD&T |
| 删除 | `creo_drawing_delete` | 删除视图、注释或表格；dimension 仅擦除显示。删除父视图前移除依赖投影视图和显示尺寸 |
| 工程图输出 | `creo_export_model(format="pdf")` | 原生 PDF 导出；JPEG 为当前图纸截图。DRW 修改也执行保存、擦除、重载和内容对比 |
| UDF 库查询 | `creo_inspect_udf` | 读取本机 .gph 的参照提示、参照类型及可变尺寸名称/默认值 |
| UDF 放置 | `creo_create_udf` | 根据提示映射参照、按名称设置可变尺寸，生成独立原生特征组；组内特征保留参数化尺寸 |

## 工程图用法

1. 创建并保存零件，取得 `model_id`。
2. 调用 `creo_new_drawing(source_model_id=...)`，查询返回的 job_id 至完成；得到新的工程图 model_id/revision。图纸来源标签为 `model`。
3. 调用 `creo_drawing_view`，例如 `label="front", position=[75,110], orientation="front", scale=1`。
4. 追加投影视图、注释、表格、已有模型尺寸；每次修改携带最近成功任务的 `expected_revision`。
5. `creo_export_model(model_id=工程图ID, format="pdf")` 返回任务，最终 PDF 路径在 `result.operations[].file`。

坐标从图纸左下角起，以毫米为单位。视图 move 是位移向量，note 的 position 是绝对位置。表格从指定位置向右、向下增长；行列从 1 开始。正视图为 XZ 投影，顶部为 XY。标准草图的 offset 指定对应世界坐标值，例如 XZ/offset=15 的平面是 Y=15。

图纸引用的是源模型的**版本快照**，修改源零件不会自动更新图纸。当前不支持装配工程图。DRW 备份同时保存引用模型；移动或分享工程图时须一并保留相应目录中的 PRT。重载核验覆盖 DRW 的图纸、视图变换、文字、表格和显示尺寸；引用模型在该会话中可能继续驻留，不宣称已经执行全新 Creo 进程的冷启动重载测试。

## UDF 用法与许可

先在 Creo 中准备合适的 `.gph`，再调用 `creo_inspect_udf(model_id=..., file_path="C:\\my_library\\feature.gph")`。元数据位于完成任务的 `result.operations[].metadata`。

将每个 `references[].prompt` 原样作为 `references` 字典键，将每个 `dimensions[].name` 原样作为 `dimensions` 字典键。例如某库要求 REF_CSYS、可变尺寸名为 d11：

```json
{
  "label": "library_feature",
  "file_path": "C:\\my_library\\feature.gph",
  "references": {"REF_CSYS": {"kind": "default_csys"}},
  "dimensions": {"d11": 10}
}
```

调用 `creo_create_udf` 时还需要 model_id 和 expected_revision。库文件复制进任务输入目录，使用 independent 依赖和相同尺寸模式。缺少/多余的参照、类型不匹配、未知可变尺寸均明确报错，关闭交互放置与模型修复菜单。操作失败按现有原生模型检查点回滚。

`aliases[label].group_id` 为原生组 ID，`member_feature_ids` 为成员特征。用成员 feature ID 查询尺寸、修改尺寸或导出特征树。标签用于 MCP 跟踪，当前不更改库自动生成的组名称。不同 UDF 所需的材料底体、方向、许可和特征支持范围不同；需满足其自身前提。族表 instance 参数、象限定位、变量参数、装配/制造 UDF 等未完成全面测试。

**UDF 复用不等于已经实现任意普通放样。** 它能够复用库里已定义的原生特征，但不能把任意若干草图自动变为所有形式的放样。PTC 软件、SDK、许可和特征库不随源码分发；MIT 仅覆盖本项目代码。

## 尚未完成的范围

| 类别 | 当前缺口 |
| --- | --- |
| 普通放样 | 新增 `creo_new_loft_part`，支持两张新 XY 草图驱动种子中的原生直线或平滑混合，创建独立新零件；已验证模式保留、尺寸修改和保存重载。仍需匹配模式的种子，未覆盖模式自动转换、已有零件追加、更多截面、非平行或端点相切/曲率控制。`creo_loft` 直接创建仍禁用。Element Tree 提取在本机已测混合返回 `PRO_TK_INVALID_TYPE (-18)`，不外推为所有版本或路径均不可行 |
| 高级曲面 | 边界混合、曲面合并/修剪、Style、自由曲面和完整连续性控制 |
| 高级实体 | 变截面/螺旋扫掠、变半径圆角、分割/可变拔模、更多阵列、标准螺纹孔等 |
| 工程图/MBD | 剖视/局部/详细视图、新建任意尺寸、GD&T、公差、表面粗糙度、符号库、BOM、模型注解、实时源关联 |
| 钣金/装配 | 钣金成形、折弯表、卷边/偏移折弯；子装配、机构、骨架、柔性组件和源关联更新 |
| 专业模块 | 模具、NC 制造、仿真、线缆/管道、复合材料等仍没有专用高层工具；不能用通用树或 UDF 工具代替其完整模块覆盖声明 |

`creo_capabilities.complete_creo_coverage` 保持 false。此前模块的测试记录见 [validation_development.json](validation_development.json)，最新直线、平滑测试分别见 [validation_loft_seed.json](validation_loft_seed.json)、[validation_loft_smooth.json](validation_loft_smooth.json)，平滑调用说明见 [SMOOTH_BLEND.md](SMOOTH_BLEND.md)；本轮未重跑此前模块的完整套件。

## 运行验证

所有命令在源码目录运行，保持 Creo 打开，依次执行以避免 Toolkit 争用：

```powershell
.venv\Scripts\python.exe tools\test_unit.py
.venv\Scripts\python.exe tools\test_surface_features.py
.venv\Scripts\python.exe tools\test_udf.py
.venv\Scripts\python.exe tools\test_development.py
.venv\Scripts\python.exe tools\test_mcp.py
.venv\Scripts\python.exe tools\summarize_development.py
```

UDF 集成测试需要本机安装 PTC 自带的 node.gph 示例，不随仓库提供。本机该文件实际生成圆柱切除，测试按原生几何和体积进行校验。工程图测试包含故意失败后的回滚；失败作业不计为建模成功。PDF 必须额外渲染检查，数据检查不能发现所有版面问题。

配置可选 `creo_session_id`（默认空）。不指定时需要唯一可连接的 Creo 会话；指定时核对实际连接 ID，拒绝 Toolkit 回退到其他会话。会话重启后旧 ID 会失效。不要把本机 config.json、会话 ID、许可、模型或测试任务上传到公开仓库。


## 本轮版本信息

最初发布 0.22 时仅修正版本标签和发布资料，原生建模记录保留当时的开发标签。本次普通放样增量已改变建模实现，版本标签暂保持 0.22；它具有独立验证摘要，不沿用“实现未改变”的结论。旧 GitHub Release 和源码包保留原状。
