# 平滑混合：MCP 调用与验收

**2026-10-11 增量**：源码内附 `two_smooth`、`five_smooth`，安装时自动注册、调用时自动匹配，用户不必填写路径和内部 ID。新翼型参数及定位流程见 [增量说明](PORTABLE_MODELING_2026-10-11.md)。

使用 `creo_new_loft_part`，传入 `interpolation: "smooth"`。从 **0.2.4** 起支持匹配种子的多截面工作流；五截面方形与样条翼型已通过实机验收。步骤见 [MULTISECTION_BLEND.md](MULTISECTION_BLEND.md)，两截面示例见 [loft_smooth_seed.json](../examples/loft_smooth_seed.json)。

独立发布的 [种子库](SEED_LIBRARY.md) 提供 `two_smooth` 与 `five_smooth` 原始 PRT，可直接复制到其他电脑使用，调用时更新本机路径并沿用对应清单 ID。迁移与客户端配置见 [MIGRATION.md](MIGRATION.md)。

种子须为毫米制、单实体、独立外部草图截面的原生平滑混合，按 Z 递增创建并选择完整曲线链。数量必须与输入匹配，不能用两截面种子接收五截面。源文件快照后复制，原件不修改；模式不一致会失败，不自动转换直线和平滑。

五截面成功结果应包含以下字段，标签和数量应随输入调整：

```json
{
  "saved_file_reloaded_and_verified": true,
  "loft_checks": {
    "before_save": {"blend": {"interpolation": "smooth", "section_count": 5}},
    "after_reload": {"blend": {"interpolation": "smooth", "section_count": 5}}
  }
}
```

执行器读取 Creo 官方 `PRO_FEAT_INFO` 的“混合曲面：平滑”，检查活动完整的特征、数量及模式；修改、重载和回滚后再次检查。两截面自由端点可与直线得到同样几何，不应以外形推断设置。

验收仍要求 **原生 Blend 保留、参数修改成功、实际保存擦除重载成功**。五截面还检查中间截面对实体的影响，并从 STL 核对每个截面，见 [validation_multisection.json](validation_multisection.json)。两截面回归见 [validation_loft_smooth.json](validation_loft_smooth.json)。

仅新建零件、平行 XY 截面、实体增材，端点条件继承种子。已有零件追加、无种子创建、起点对应及相切/曲率控制仍未完成；`creo_loft` 保留接口禁用，接口数量上限不代表任意轮廓均成功。
