# MCP_CREO_MechDog 0.2.4

本地 Windows MCP 服务，连接已打开的 Creo Parametric 10，通过官方 C/C++ Toolkit 创建、查询和修改**原生参数化特征**。建模由任意支持的草图轮廓及顺序特征组成：新建零件 → 草图 → 拉伸/旋转 → 切除/孔 → 后续特征。原先的底板接口保留为快捷工具。

**本版为源码预发布候选版，尚未完成所有 Creo 操作的覆盖。** 当前本地开发版注册 **68 个工具，其中 67 个启用**。新增多截面原生混合种子复用工具 `creo_new_loft_part`；直接创建接口 `creo_loft` 仍禁用。使用官方 Python MCP SDK 2.3.0、stdio 传输，采用 [MIT 许可证](LICENSE)。每位使用者在自己的 Windows 电脑上安装依赖并编译 Toolkit 执行器，由本地 AI 客户端调用。

开发版包括工程图、坐标系/点、填充曲面、加厚、实体化、多实体布尔、筋和 UDF 库工具。当前版本为 **0.2.4**，使用方法和边界见 [版本说明](docs/RELEASE_NOTES_0.2.4.md)。多截面增量见 [多截面说明](docs/MULTISECTION_BLEND.md)、[验证摘要](docs/validation_multisection.json)；两截面普通放样见 [调用说明](docs/LOFT_SEED.md)、[直线验证摘要](docs/validation_loft_seed.json) 与 [平滑混合说明](docs/SMOOTH_BLEND.md)、[平滑验证摘要](docs/validation_loft_smooth.json)；其他模块的 [历史验证摘要](docs/validation_development.json) 单独保留。已发布的 GitHub v0.22 和旧源码包不会自动包含这些增量，0.2.4 需单独发布，已发布的 v0.2.3 不会自动更新。

另提供 **0.2.4 原生混合种子库**：两截面直线、两截面平滑、五截面平滑。项目原创模型及配套文件采用 MIT，作为独立 Release 附件提供，源码 ZIP 不含 PRT。普通混合用户应同时下载源码和 `MCP_CREO_MechDog-0.2.4-seed-library.zip`；详见 [种子库说明](docs/SEED_LIBRARY.md) 和 [换电脑、换 Agent](docs/MIGRATION.md)。安装器当前不会自动下载或注册种子库。

已发布 0.21 的历史验证见 [validation_0.21.json](docs/validation_0.21.json)，历史范围见 [COVERAGE_0.21.md](docs/COVERAGE_0.21.md)。测试环境为 Windows x64、Creo 10.0.0.0、Python 3.12、Visual Studio 2022 C++ Build Tools。0.2.0 的 41 个成功任务及 11 项输入验证单独保留为历史记录。这些摘要不能代替使用者自己机器的许可与运行验证。

历史 0.21 验证通过 20 项输入校验、64 个成功原生任务，其中 56 个修改任务通过保存重载。只读查询/导出不计入修改任务；禁用放样的拒绝行为不计为建模成功。

## 安装

准备 Windows x64、Python 3.12+ x64、Creo Parametric 10 及匹配的 Toolkit SDK、MSVC x64 C++ 构建工具和可用的 PTC 许可。Creo 软件、SDK、模板和许可需要自行取得；MIT 适用于本项目代码、文档及种子库的原创内容，不提供 PTC 软件授权。第三方依赖和 PTC 前置条件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

1. 下载源码，解压到较短的可写目录，例如 `C:\MCP_CREO_MechDog`；下列命令在该目录执行。
2. 运行安装脚本，填写自己的 Creo 安装根目录：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
   ```

   如果 Python 没有加入 PATH，可加 `-Python 'C:\Path\To\python.exe'`。如果编译器没有自动找到，可加 `-VcVars64 'C:\Path\To\vcvars64.bat'`。这两个示例路径需要替换。
3. 安装成功后，脚本生成本机 `config.json`、`.venv/`、`build/` 和 `client-config.json`。将 `client-config.json` 中的服务配置加入支持本地 stdio MCP 的 AI 客户端。
4. 打开一个 Creo 10 会话，让 AI 调用 `creo_check_environment` 和 `creo_session_status`；连接成功后再提交建模计划。成功建模及保存重载验证才证明相应操作在该环境可用。

脚本不修改全局客户端配置。完整安装与排错说明见 [docs/INSTALL.md](docs/INSTALL.md)；GitHub 源码发布步骤见 [docs/PUBLISH_GITHUB.md](docs/PUBLISH_GITHUB.md)。GitHub 仓库用于分发源码，服务在使用者的电脑运行。

## 建模能力

| 类别 | 工具及能力 |
| --- | --- |
| 零件与建模计划 | `creo_new_part`、`creo_execute_plan`：新建毫米零件，或对已有 MCP 零件逐步追加特征 |
| 草图 | `creo_create_sketch`：直线、中心线、圆、圆弧、矩形、多段线、样条、椭圆；显式尺寸和约束；剩余自由度自动标注尺寸 |
| 拉伸 | `creo_extrude`：实体增材、切除、贯穿切除、曲面、薄壁、正/反向、对称深度、新实体 |
| 旋转 | `creo_revolve`：实体旋转、旋转切除、指定角度，使用草图中心线或外部轴；提供曲面、薄壁和对称角度分支 |
| 孔 | `creo_hole`：原生直孔，平面定位，两条参考和有符号定位尺寸，通孔或指定深度盲孔 |
| 修饰特征 | `creo_round`、`creo_chamfer`、`creo_shell`：恒定半径圆角、等距倒角、恒定厚度抽壳；用查询得到的边/面 ID 选引用 |
| 基准与重复 | `creo_datum_plane`、`creo_datum_axis`、`creo_dimension_pattern`：偏移/角度基准面、基准轴、一方向尺寸阵列 |
| 镜像、扫掠、拔模 | `creo_mirror`：整体/几何镜像；`creo_sweep`：恒定截面及命名截面尺寸；`creo_draft`：恒角、不分割拔模 |
| 钣金 | `creo_new_sheetmetal`、`creo_sheetmetal_wall`、`creo_sheetmetal_flange`、`creo_sheetmetal_unbend`、`creo_sheetmetal_bend_back`、`creo_sheetmetal_flat_pattern`：首壁、弯曲法兰、展开、折弯回去和平展；保留原生特征树 |
| 装配 | `creo_new_assembly`、`creo_assemble_component`、`creo_component_placement`、`creo_component_constraints`、`creo_remove_component`、`creo_list_components`：组件版本副本、定位、约束、删除和查询 |
| 新增曲面与实体 | `creo_surface_fill`、`creo_thicken`、`creo_solidify`、`creo_boolean_bodies`、`creo_rib` |
| 新增基准 | `creo_datum_csys`、`creo_datum_points` |
| 原生工程图 | `creo_new_drawing`；图纸、一般/投影视图、尺寸显示、注释、表格及编辑/删除；原生 DRW 与 PDF 输出 |
| UDF 特征库 | `creo_inspect_udf`、`creo_create_udf`：查询并复用用户的 .gph，保留组内原生参数特征 |
| 普通混合种子复用 | `creo_new_loft_part`：按 2～20 张新 XY 草图创建新零件，支持 `straight` 和 `smooth`，要求种子数量和模式与请求一致；已验证五截面方形及样条翼型、中间尺寸/位置修改及保存重载；[调用说明](docs/LOFT_SEED.md) |
| 未完成的保留接口 | `creo_loft`：任务入队前明确拒绝，不作为可用功能 |
| 参数化修改 | `creo_set_dimensions`、`creo_set_sketch_dimensions`、`creo_set_parameters`、`creo_set_relations`：编辑特征尺寸/草图尺寸、零件参数、简单算术关系式，重新生成依赖特征 |
| 特征树与拓扑查询 | `creo_inspect_model`、`creo_refresh_model`、`creo_list_models`：特征 ID、名称、类型、状态、尺寸、草图尺寸、几何引用 ID、面/边/实体、体积、包围盒、参数和版本 |
| 高级原生特征接口 | `creo_create_feature_tree`、`creo_lookup_constants`、`creo_dump_feature_tree`：按照本机 SDK 的 Element Tree 结构创建特征，查询常量、导出特征 XML |
| 保存与导出 | `creo_regenerate`、`creo_save_model`、`creo_export_model`：保存原生 PRT/ASM，导出 STEP、IGES、STL、JPEG；装配的所有导出格式组合未验证 |
| 环境与任务 | `creo_check_environment`、`creo_session_status`、`creo_capabilities`、`creo_get_job`、`creo_list_jobs`：环境、实际 Toolkit 连接、能力和任务进度 |
| 快捷底板 | `creo_create_plate`：兼容此前矩形底板、角圆角、独立通孔接口 |

特征保存为 Creo 可编辑的草图、拉伸、旋转、孔、圆角等，保留尺寸及依赖。多段线和矩形会展开为原生直线，不能将 `polyline` 名字当作单个尺寸引用；例如 `box_0` 是矩形第一条边。

提供接口不等于所有参数组合都已验证。[直线混合摘要](docs/validation_loft_seed.json) 与 [平滑混合摘要](docs/validation_loft_smooth.json) 记录最新增量测试；[其他开发功能摘要](docs/validation_development.json) 和 `build/capability_evidence.json` 是此前测试的历史证据，本轮未重跑其完整套件。已测试非矩形支架、带内孔和沟槽的轴类件、多实体圆弧/椭圆实体、样条拉伸曲面、薄壁对称拉伸、抽壳、边圆角和倒角、尺寸阵列及参数关系驱动。高级树接口需要符合 SDK 的具体特征定义，不能自动补齐任意缺失的草图或集合。

## 接入与调用

保持一个 Creo 10 会话打开，把以下本地 stdio 服务配置加入支持 MCP 的客户端：

```json
{
  "command": "C:\\MCP_CREO_MechDog\\.venv\\Scripts\\python.exe",
  "args": ["C:\\MCP_CREO_MechDog\\server.py"]
}
```

上述路径仅为示例，以安装生成的实际路径为准。服务名称及客户端注册键为 `MCP_CREO_MechDog`。`client-config.json` 是同一配置的 `mcpServers` 格式；不同客户端的配置格式可能需要转换，必须保留相同的 command/args。服务启动后客户端可发现工具的完整 JSON Schema。服务从自然语言规划器接收结构化建模操作；自然语言理解由调用它的 AI 客户端完成。

典型流程：

1. 调用 `creo_check_environment`、`creo_session_status` 检查本机环境并实际连接。
2. 使用 `creo_execute_plan` 一次创建完整零件，或用 `creo_new_part` 后分步调用草图及特征工具。
3. 建模工具立即返回 `job_id`；查询 `creo_get_job`，等待 `status == "succeeded"`。修改任务还必须有 `result.saved_file_reloaded_and_verified == true`。
4. 保留 `model_id` 和最新 `revision`。修改已有零件时提供 `expected_revision`；版本不一致会拒绝旧请求。
5. 查询实际面/边/尺寸 ID 后追加特征。引用发生变化时重新查询，不复用猜测的拓扑 ID。

例如创建有原生特征树的圆柱：

```json
{
  "operations": [
    {"op":"sketch","label":"profile","plane":"XY",
     "entities":[{"type":"circle","name":"circle","center":[0,0],"radius":10}],
     "dimensions":[{"name":"diameter","type":"diameter","refs":[{"entity":"circle"}],"value":20,"position":[15,0]}]},
    {"op":"extrude","label":"solid","sketch":"profile","depth":30}
  ],
  "assertions":{"require_solid":true,"volume_mm3":9424.77796076938}
}
```

随后 `creo_set_sketch_dimensions` 使用 `sketch:"profile", values:{"diameter":24}` 修改直径；拉伸实体随之更新。`creo_set_dimensions` 接收查询结果中的模型尺寸 ID，例如 `values:[{"id":18,"value":40}]`；实际 ID 由 Creo 生成。

完整案例在 `examples/`；0.21 新增镜像、扫掠、拔模和钣金首壁计划。装配调用步骤见 [docs/MODELING_0.21.md](docs/MODELING_0.21.md)。尺寸阵列先建立引导孔，再查询其定位尺寸 ID，调用 `creo_dimension_pattern`，指定包含引导成员的总数量和每次增量。

## 坐标、引用与参数

长度使用毫米，角度使用度。草图输入是平面内的 `(u,v)`：

| 平面 | u | v | 正向法线 | offset |
| --- | --- | --- | --- | --- |
| XY | +X | +Y | +Z | 世界 Z 坐标 |
| XZ | +X | +Z | −Y | 世界 Y 坐标 |
| YZ | +Y | +Z | +X | 世界 X 坐标 |

`direction:"positive"` 沿表中正向法线，`negative` 反向。对称拉伸的 `depth` 是总深度。圆弧起止角以输入平面 u 轴为零度，沿 u→v 逆时针。

平面也可传入 `{"reference":{"kind":"surface","id":实际ID},"origin":[x,y,z],"u_axis":[x,y,z]}`，用于已有平面面或基准面。默认原点是世界原点到该平面的垂足；指定原点必须在平面内。基准面的方向和生成几何由 Toolkit 决定，应按查询结果使用。

常用引用：

```json
{"kind":"datum_plane","axis":"x","offset":0}
{"kind":"plane","axis":"z","offset":30}
{"kind":"surface","id":123}
{"kind":"edge","id":456}
{"kind":"axis","id":78}
{"kind":"datum_feature","label":"offset_plane"}
{"kind":"datum_axis_feature","label":"axis"}
```

`plane` 选择实际实体平面面，必须唯一；有多个匹配面时使用查询得到的 `surface` ID。`datum_plane` 的零偏移主平面选择模板中最早的对应基准，避免与 Creo 自动生成的内部基准混淆。非零偏移仍要求唯一。草图/拉伸等特征间用 `label` 引用；标签由小写字母、数字和下划线组成，以字母开头，最多 28 字符。

显式尺寸支持长度、半径、直径、点间距离/水平距离/垂直距离、线间距离、夹角、圆弧角度和椭圆半轴。约束接口包含水平、垂直、重合、点在线上、相切、垂直、等半径、平行、等长、共线；实测包括水平/垂直约束及驱动直径尺寸，其余组合由原生求解器验证。

关系式当前接受简单算术赋值，例如 `d18 = LENGTH / 2`；替换零件当前关系式集合。参数支持数字、布尔值和字符串。

## 验证、恢复与当前边界

每次修改成功后，执行器检查单位、所有原生特征的活动/完整状态及实体状态；保存 `.prt.N` 或 `.asm.N`，擦除该 MCP 零件的内存模型，从实际保存文件重载、重新生成，再对比特征 ID/类型/名称、尺寸值、实体数量、体积和参数。可额外提供 `require_solid`、`volume_mm3`、`volume_tolerance` 断言。体积计算临时使用密度 1，不修改材料。

`creo_inspect_model` 返回最近已验证的快照；人工在 Creo 修改后，用 `creo_refresh_model` 获取实况。实时查询不会替换已保存模型的基线，也不会保存或接受人工修改。已有模型修改前会检测模型与记录是否一致；因任务失败或人工修改而不一致时，不应盲目重复提交。

现有 MCP 零件任务失败，会尝试从任务开始前的保存文件恢复；只有 `rollback_succeeded` 确认成功才能继续。版本号不随失败增加。辅助进程崩溃、超时或结果不能确认时标记 `unknown_outcome`，保留现场供检查。新零件失败可能留下本任务的部分模型。

目前高层工具覆盖上述常见实体特征，仍有明确范围：

- 持续修改只支持本服务创建、登记的零件、钣金模型和装配；未提供直接接管用户现有模型的接口。
- 各类尺寸/约束的复杂组合、极端几何及外部人工修改的自动接管仍需后续扩展。
- 孔为直孔，尚未封装螺纹、沉头、沉孔标准孔；倒角为等距，阵列为一方向尺寸阵列。
- 普通放样支持 2～20 张平行 XY 截面的种子复用；仍需用户提供截面数及直线/平滑模式匹配的种子。五截面平滑方形与翼型已实测，数量上限不代表所有数量均已验证。不支持自动增减种子截面、转换连接模式、向已有零件追加、非平行截面或端点相切/曲率控制。`creo_loft` 直接创建路径仍禁用。
- 钣金已验证首壁、90° 法兰、高度编辑、展开、折弯回去和平展；其他形状和折弯规则未全部验证。镜像、扫掠、拔模、装配、筋和工程图各自具有明确范围，见开发版说明；复杂自由曲面及专业模块仍未完整封装。
- 装配插入源模型的版本快照，源模型后续修改不更新组件；子装配复制尚未开放。
- `creo_create_feature_tree` 可扩展符合本机 SDK 的特征结构，但无法保证所有 PTC 特征类型和选项均可创建。
- 不承诺任意文字描述都自动成功。AI 需要规划有效的轮廓、基准、尺寸和特征顺序；无效几何由 Creo 返回错误。

服务串行执行 Toolkit 操作，只连接已打开的唯一 Creo 会话，不自动关闭 Creo。输出保存在项目 `models/` 和 `jobs/` 内，不提供任意命令/代码执行工具，不输出许可服务器内容或修改安装目录。正在交互建模或有模态对话框时，应先处理该会话状态。

## 开发与测试

安装脚本创建虚拟环境、安装锁定依赖、读取本机 SDK 生成常量表、编译执行器并生成客户端配置。首次运行或原生源码改变时也会自动重新编译。`native/constants.inc` 由本机 SDK 生成；不随源码分发。源码包不含 Creo SDK 库、许可内容、虚拟环境、编译二进制或测试零件。第三方 JSON 头文件附带其原始 MIT 许可。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\test_mcp.py --classic
.\.venv\Scripts\python.exe tools\test_general.py
.\.venv\Scripts\python.exe tools\test_extended.py
.\.venv\Scripts\python.exe tools\test_guards.py
.\.venv\Scripts\python.exe tools\test_v021.py
.\.venv\Scripts\python.exe tools\test_unit.py
```

除输入验证外，上述集成测试会实际连接 Creo 并创建或修改独立测试模型。`test_v021.py` 默认验证启用功能和禁用接口的拒绝行为；禁用接口的拒绝测试不是建模成功证明。日志位于任务 `native.log`/`runner.log`/`job.json` 和 `build/build.log`；证据在 `build/*integration_test.json`。保存目录较长时应缩短项目路径。

实现依据：[PTC 草图特征 Element Tree 文档](https://support.ptc.com/help/creo_toolkit/protoolkit_plus/usascii/creo_toolkit/user_guide/Element_Tree_for_Sketched_Features.html)、本机 Creo 10 Toolkit 头文件与示例、[官方 MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。实际本机建模成功、保存重载成功的记录才证明该路径可用，SDK/许可环境文件存在本身不能证明许可可用。

完成普通放样实机测试后，可生成它的独立摘要；打包会重新生成本地同版本压缩包：

```powershell
.\.venv\Scripts\python.exe tools\summarize_loft_seed.py
.\.venv\Scripts\python.exe tools\summarize_loft_seed.py --interpolation smooth
.\.venv\Scripts\python.exe tools\package.py
```

摘要命令需要已经完成相应的实机测试；打包命令只选择公开源码及文档。`config.json`、`client-config.json`、虚拟环境、构建结果、任务和模型目录已在 `.gitignore` 中排除。
