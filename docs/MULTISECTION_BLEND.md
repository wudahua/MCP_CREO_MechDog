# 多截面原生实体混合

从 0.2.4 起，`creo_new_loft_part` 接收 **2～20 张** Z 偏移严格递增的 XY 草图。**种子的截面数与直线/平滑模式必须匹配输入**；执行器依次替换原生 Blend 的截面参照，不会给两截面种子自动增加截面。

本机 Creo 10.0.0.0 已验证五截面平滑方形混合和 NACA 0012 样条翼型。输入数量上限不代表每个数量与轮廓均经过验证。公开结果见 [validation_multisection.json](validation_multisection.json)。

| 截面数 | 模式 | 本轮实机验收 |
| --- | --- | --- |
| 2 | 直线、平滑 | 方形、圆、三角形回归通过 |
| 5 | 平滑 | 方形及 NACA 0012 样条翼型通过 |

三截面直线种子尚未完成，未纳入本轮实测记录。其他数量与模式组合须准备匹配种子并逐项验证。

## 准备种子

需要两截面直线、两截面平滑或五截面平滑时，可直接使用独立发布的 [种子库](SEED_LIBRARY.md)，不用重新手画。以下步骤用于自行准备其他种子。

1. 新建毫米制零件，按 Z 从低到高创建独立、闭合、平行 XY 草图。
2. 创建实体“混合”，使用“选定截面”，按相同顺序选择每张草图的完整闭合曲线链。支持草图特征整体及其完整复合曲线参照；不支持部分边、外部模型曲线或内部草绘截面混用。
3. 选择需要的“直线”或“平滑”模式，确认生成一个实体并保存原生 PRT。
4. 查询混合的原生特征 ID；显示序号不能代替内部 ID，不可套用另一份模型的 ID。随种子库原文件复制时，可沿用其清单中的 ID，并更新本机绝对路径。

种子只应包含一个实体混合、截面草图及必要基准。源文件快照后复制，原件不修改。端点条件、参数、关系及未使用基准可能被继承，建议专用简单种子。源码包不含本机测试 PRT、PTC 模型或 SDK。

## 使用与修改

将 [五截面示例](../examples/loft_multisection_seed.json) 作为 `creo_new_loft_part` 参数，替换 `seed_file` 和 `seed_feature_id`。示例截面边长为 12、26、34、22、8 mm，Z=0、20、50、80、100 mm，要求五截面平滑种子。

提交一次，查询 `job_id` 到 `succeeded`，检查 `result.saved_file_reloaded_and_verified == true`，以及 `loft_checks.before_save.blend` 与 `after_reload.blend` 中的模式与截面数。自定义标签时字段名随标签改变。全部草图及活动、完整的原生 Blend 应保留。

中间方形截面可用 `creo_set_sketch_dimensions` 修改：传入最新模型 ID、revision、`sketch: "section_2"`，以及 `values: {"width": 40, "height": 40}`。基准面尺寸通过模型查询取得真实 ID，再用 `creo_set_dimensions` 修改。

五截面翼型测试将中间基准面由 Z=50 改为 55 mm，体积约 5682.892315→5787.897729 mm³。五个实际截面均从导出 STL 核对：采用到 NACA 0012 参考轮廓的最近距离，0.15 mm 容差，避免前缘接近竖直时纵向误差放大。翼型由每侧 41 个余弦分布点生成原生样条，包含有限厚度尾缘；公式参考 [NASA CR-145194 式 39b](https://ntrs.nasa.gov/api/citations/19770017113/downloads/19770017113.pdf)。不是精确解析曲线或完整螺旋桨性能验收。

## 复现

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\test_multisection_blend.py --seed-file 'C:\my_library\five_section_smooth.prt.1' --feature-id 123 --sections 5 --interpolation smooth
```

路径和 ID 必须替换。测试包含原生创建、中间尺寸/位置修改、保存擦除重载、全部截面 STL 核对、故意失败后回滚、数量和模式不匹配的拒绝；五截面还包含样条翼型及 STEP 导出。超时或 `unknown_outcome` 先检查已有任务，不重复提交；`--resume` 读取同一失败测试中已完成的任务。

## 限制

- 仅创建新零件、平行 XY 截面、实体增材；已有零件追加和无种子创建仍未完成。
- 数量与模式须匹配种子，不能自动增加/删除截面或转换模式。
- 不提供非平行、切除/曲面、起点对应及相切/曲率控制。
- 本轮修改中间翼型的位置，没有封装弦长或扭转角的专用编辑工具。
- 完整螺旋桨的轮毂连接、第二叶片复制尚不属于验收范围。
- `creo_loft` 和计划操作 `loft` 仍禁用；完整 Creo 覆盖未完成。
