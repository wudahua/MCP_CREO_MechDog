# 普通放样：两截面原生混合

`creo_new_loft_part` 已在 Creo 10.0.0.0 通过实机验证：根据两张新草图创建新零件，结果包含可编辑的原生 **Blend / 混合** 特征。支持 `interpolation: "straight"` 和 `"smooth"`，草图尺寸修改能够驱动实体更新，也可继续追加拉伸切除等特征。

当前源码版本为 **0.2.3**，收录 0.22 发布后完成的直线、平滑混合种子复用增量。已发布的 GitHub v0.22 与旧源码压缩包不自动包含这些改动。当前源码注册 68 个工具，其中 67 个启用，版本说明见 [RELEASE_NOTES_0.2.3.md](RELEASE_NOTES_0.2.3.md)。

## 工作方式与范围

首次使用需要一份使用者自己保存的原生混合种子 `.prt` 或 `.prt.N`。执行器复制该文件，建立两张全新的参数草图，将复制出的混合特征参照改接到新草图，然后删除两张旧截面草图。种子原文件不修改；当前会话中同名模型的未保存内容不参与复制。

已验证矩形→矩形、圆→圆、三角形→三角形。输入采用通用 `SketchOp`，可以提供显式尺寸及约束；其他轮廓组合仍需逐例验证，不能据此承诺任意拓扑均可混合。

- 当前入口只创建新零件，接收两张 XY 草图，第二张的 Z 偏移必须大于第一张。
- 使用单实体的实体混合种子。`interpolation` 默认为 `straight`；传 `smooth` 时必须提供已保存为“平滑”的种子。执行器核实种子中的原生模式，不自动转换直线和平滑。端点条件继承种子，接口不提供切除、曲面、起点对应关系或相切/曲率控制。
- 初始种子须先创建底部草图、再创建顶部草图，并按同样顺序选取混合截面。执行器按种子草图的特征顺序映射新截面。
- 种子内可保留基准和坐标系；多实体、其他实体特征、外部模型参照会被拒绝。未使用的基准面可能留在输出特征树中；种子的参数和关系式也会被继承，建议使用专用简单种子。
- 此入口不把混合追加到已有零件，不支持三截面以上或非平行截面。原 `creo_loft` 和计划操作 `loft` 仍禁用；Element Tree 直接创建路径尚未通过验证。
- 原生混合类型识别目前支持中文和英文 Creo。完整 Creo 覆盖仍未完成。

## 准备一次种子

1. 在毫米零件中先画 Z=0 的 20×20 闭合正方形，再画 Z=30 的 10×10 闭合正方形。
2. 创建实体混合，使用“选定截面”，依次选择底部、顶部草图的完整闭合曲线链。在“选项”中设置要使用的连接方式：直线或平滑。
3. 确认生成一个实体，保存原生 PRT。记录混合的原生特征 ID；它不是模型树中的显示序号。
4. 使用保存文件的绝对路径和实际特征 ID 调用工具。源码包不附带测试 PRT、PTC 示例模型或 SDK。

本机参考模型 `MECHDOG_LOFT_REFERENCE` 和独立平滑副本 `MECHDOG_SMOOTH_REFERENCE` 的混合 ID 为 **60**。其他人新建的种子不可照抄这个 ID。平滑模式的准备与验收见 [SMOOTH_BLEND.md](SMOOTH_BLEND.md)。

## 调用示例

将 [loft_seed.json](../examples/loft_seed.json) 或 [loft_smooth_seed.json](../examples/loft_smooth_seed.json) 作为 `creo_new_loft_part` 的参数。先替换 `seed_file` 和 `seed_feature_id`，匹配种子的连接模式，其余参数会创建底边 20 mm、顶边 10 mm、高 30 mm 的方台。此自由端点种子两种模式的预期体积均为 7000 mm³。

返回 `job_id` 后，调用 `creo_get_job` 至 `succeeded`，确认 `result.saved_file_reloaded_and_verified == true`，并检查 `result.loft_checks.before_save.blend.interpolation` 与 `result.loft_checks.after_reload.blend.interpolation` 均为请求模式。示例将混合命名为 `blend`；自定义 `label` 时此字段名随之变化。保存返回的 `model_id` 与 `revision`。

修改上截面边长时，调用 `creo_set_sketch_dimensions`，传入该 `model_id`、最新的 `expected_revision`、`sketch: "top"` 和 `values: {"width": 12, "height": 12}`。实体体积更新为 7840 mm³。后续特征沿用通用 MCP 的版本检查和回滚机制。

## 验证结果

本轮实际使用 MCP stdio 调用，而非只运行独立 C++ 原型。

| 案例 | 截面与间距 | 原生体积 mm³ |
| --- | --- | ---: |
| 方台 | 正方形边长 20→10，间距 30 | 7000 |
| 圆台 | 半径 10→5，间距 30 | 5497.787143782138 |
| 三角台 | 直角等腰三角形直角边 20→10，间距 30 | 3500 |
| 修改方台 | 上截面两个尺寸 10→12 | 7840 |
| 后续切除 | 修改后的方台，Ø2、高 30 的圆柱切除 | 7745.752220392307 |

上表案例分别在直线、平滑模式运行。每种模式的五个成功修改任务均通过保存、擦除、重载、再生及几何核验。每种模式另有三个预期失败任务：体积断言故意失败并回滚、不存在的种子特征 ID、请求模式与种子不一致。源文件 SHA-256 前后相同。输入校验 28 项通过，MCP 发现 68 个工具并成功连接 Creo。

平滑模式依据 Creo 官方 `PRO_FEAT_INFO` 导出的原生特征信息核验“混合曲面”设置，而不以外形或体积推断。两截面、自由端点条件下，平滑与直线可以得到相同几何；本轮确认的是原生平滑设置保留，不承诺曲线侧面或指定的 G1/G2 连续性。修改和保存重载都会再次核验模式；本增量之前创建、未记录 `interpolation` 的旧 MCP 模型不纳入该额外模式检查。

公开摘要见 [validation_loft_seed.json](validation_loft_seed.json) 和 [validation_loft_smooth.json](validation_loft_smooth.json)，本机详细任务证据分别在 `build/loft_seed_integration.json`、`build/loft_smooth_integration.json`。原生建模记录保留验收时的 0.22 标签；更新为 0.2.3 时核对建模运行代码与执行器未变化，并重新执行输入验证和 MCP 版本/连接检查。此前其他模块的验证是历史记录，本轮没有重跑其完整集成套件。

复现命令（在源码目录，保持 Creo 打开）：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\test_unit.py
.\.venv\Scripts\python.exe -X utf8 tools\test_mcp.py
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\blend_seed.prt.1' --feature-id 60 --interpolation straight
.\.venv\Scripts\python.exe -X utf8 tools\summarize_loft_seed.py
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\smooth_seed.prt.1' --feature-id 60 --interpolation smooth
.\.venv\Scripts\python.exe -X utf8 tools\summarize_loft_seed.py --interpolation smooth
```

命令中的路径和特征 ID 必须替换。测试会创建独立零件并保留结果；超时或 `unknown_outcome` 时先检查原任务，不重复提交。
