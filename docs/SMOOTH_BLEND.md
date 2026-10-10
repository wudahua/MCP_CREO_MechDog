# 平滑混合：MCP 调用与验收

平滑混合已通过 Creo 10.0.0.0 的实际 MCP 调用验证：保留原生 Blend 特征、成功修改草图尺寸、保存后擦除并从 PRT 重载，原生连接模式仍为“平滑”。当前源码版本为 **0.2.3**，已发布的 GitHub v0.22 和旧压缩包不包含此增量。版本说明见 [RELEASE_NOTES_0.2.3.md](RELEASE_NOTES_0.2.3.md)。

## 调用方式

使用 `creo_new_loft_part`，传入 `interpolation: "smooth"`。完整参数示例见 [loft_smooth_seed.json](../examples/loft_smooth_seed.json)，把其中的 `seed_file` 与 `seed_feature_id` 换成自己的值。

种子必须是使用者保存的毫米制、单实体、两截面原生平滑混合零件。先建立下截面草图，再建立上截面草图；创建“混合”时依次选择两个完整闭合曲线链，在“选项”中选择“平滑”，确认并保存。种子准备及其他要求见 [LOFT_SEED.md](LOFT_SEED.md)。源码包不附带 PTC SDK 或测试 PRT。

此工具复制保存的种子，用两张新的参数草图替换其截面参照，并删除原截面草图。种子原文件保持不变。`interpolation` 用于核实种子模式，不能把直线种子自动改成平滑；不一致时任务失败。

等 `creo_get_job` 返回 `succeeded`，检查以下字段。示例使用 `label: "blend"`，其他标签对应不同键名。

```json
{
  "saved_file_reloaded_and_verified": true,
  "loft_checks": {
    "before_save": {"blend": {"interpolation": "smooth", "section_count": 2}},
    "after_reload": {"blend": {"interpolation": "smooth", "section_count": 2}}
  }
}
```

以上是 `result` 中需要检查的字段摘录，不是建模请求。执行器读取 Creo 官方 `PRO_FEAT_INFO` 特征报告中的“混合曲面：平滑”，并检查原生特征类型、子类型和截面数。后续参数修改与保存重载再次检查模式。

## 三项验收结果

| 验收项 | 实际结果 |
| --- | --- |
| 原生混合特征保留 | 矩形、圆、三角形三种截面均保留活动、完整的原生 Blend，特征类型 917、子类型“混合” |
| 参数修改成功 | 方台顶截面的 width、height 从 10 改为 12 mm，体积从 7000 变为 7840 mm³，模式仍为 smooth |
| 保存重载成功 | 五个成功修改任务均保存、擦除、实际重载、再生并核验几何；重载后原生模式均为 smooth |

此外，后续 Ø2 圆柱切除成功；故意错误的体积断言触发并成功回滚；不存在的种子特征 ID 和模式不匹配均按预期失败。种子文件哈希未变化。公开证据见 [validation_loft_smooth.json](validation_loft_smooth.json)，本机详细任务记录在 `build/loft_smooth_integration.json`。原生任务保留验收时的 0.22 标签；0.2.3 复用经哈希核对未变化的建模实现证据，另有当前版本的输入验证和 MCP 版本/连接检查。

## 当前范围

目前接收两张 Z 偏移递增的 XY 草图，创建独立的新零件。多截面、向已有零件追加混合、无种子直接创建仍未完成，`creo_loft` 保留接口仍禁用。

端点条件继承种子，尚无相切、曲率或起点对应关系控制。自由端点的两截面平滑混合可以与直线混合得到相同几何，因此不能以外形或体积区分模式。本轮证明原生平滑设置在创建、修改和重载后保留；其他轮廓和端点条件需单独验证。

## 复现

在源码目录保持 Creo 打开，依次执行，替换自己的种子路径与原生特征 ID：

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\test_unit.py
.\.venv\Scripts\python.exe -X utf8 tools\test_mcp.py
.\.venv\Scripts\python.exe -X utf8 tools\test_loft_seed.py --seed-file 'C:\my_library\smooth_seed.prt.1' --feature-id 60 --interpolation smooth
.\.venv\Scripts\python.exe -X utf8 tools\summarize_loft_seed.py --interpolation smooth
```

测试创建独立零件并保留结果，包含五个成功任务、三个预期失败任务。原生源码或执行器改变后应重新验证，再生成摘要。其他专业模块不属于本轮工作范围。
