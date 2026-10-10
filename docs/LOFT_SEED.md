# 普通放样：原生混合种子复用

`creo_new_loft_part` 复制保存的专用 PRT 种子，创建独立的新零件，保留可编辑的原生 **Blend / 混合**。从 **0.2.4** 起接收 **2～20 张** Z 偏移严格递增的 XY 草图，数量和 `straight` / `smooth` 模式必须与种子匹配。多截面步骤及验证见 [MULTISECTION_BLEND.md](MULTISECTION_BLEND.md)。

执行器创建全新的参数草图，将复制出的混合参照改接到新草图，并删除旧截面草图；支持草图整体及完整复合曲线参照。源文件不修改，会话中未保存内容不参与复制。必须使用毫米制、单实体、独立外部草图的专用简单种子，端点设置、参数、关系和基准可能继承。

## 两截面种子与调用

可以直接下载独立发布的 [种子库](SEED_LIBRARY.md)，选用 `two_straight` 或 `two_smooth`。种子原文件可以在不同电脑复制，调用时改为本机绝对路径，清单中的内部 ID 适用于同一份原文件。

先创建 Z=0 的 20×20 正方形，再创建 Z=30 的 10×10 正方形；创建实体“混合”，使用“选定截面”，按顺序选取完整闭合曲线链。在“选项”设置直线或平滑，确认保存并查询原生特征 ID。源码包不含测试 PRT、PTC 模型或 SDK。

将 [loft_seed.json](../examples/loft_seed.json) 或 [loft_smooth_seed.json](../examples/loft_smooth_seed.json) 作为工具参数，替换种子绝对路径与 ID。示例方台体积 7000 mm³。种子库两份原始两截面种子的内部 ID 为 60；自行新建或改造的模型须重新查询，不能套用该值。

任务成功后确认 `result.saved_file_reloaded_and_verified == true`，检查 `result.loft_checks.before_save.blend` 与 `after_reload.blend` 的模式和截面数。自定义标签时键名跟随标签。模式通过 Creo 官方 `PRO_FEAT_INFO` 核对，修改、重载和回滚后再次检查；两截面自由端点的直线和平滑可能产生相同几何。

上截面可调用 `creo_set_sketch_dimensions`：最新模型 ID、revision、`sketch: "top"`、`values: {"width": 12, "height": 12}`。体积变为 7840 mm³，后续仍能通过通用工具追加拉伸切除等特征。

## 两截面回归案例

| 案例 | 参数 | 体积 mm³ |
| --- | --- | ---: |
| 方台 | 正方形 20→10，间距 30 | 7000 |
| 圆台 | 半径 10→5，间距 30 | 5497.787143782138 |
| 三角台 | 直角等腰三角形边长 20→10，间距 30 | 3500 |
| 修改方台 | 上截面 10→12 | 7840 |
| 后续切除 | 修改后的方台扣除 Ø2、高 30 的圆柱 | 7745.752220392307 |

直线和平滑分别运行上述案例；另检查故意错误断言的回滚、无效 ID 及模式不匹配。公开摘要为 [validation_loft_seed.json](validation_loft_seed.json)、[validation_loft_smooth.json](validation_loft_smooth.json)，其他模块保留历史证据，不推定完整 Creo 覆盖。

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\blend_seed.prt.1' --feature-id 60 --interpolation straight
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\smooth_seed.prt.1' --feature-id 60 --interpolation smooth
```

路径和 ID 必须替换。超时或未知结果先检查原任务，不重复提交。数量扩展不会自动扩大向已有零件追加、无种子创建、非平行、切除/曲面以及相切/曲率控制的范围。`creo_loft` 与计划操作 `loft` 仍禁用。
