# FEAT-082：JPEG 导出全正交视图（`right`/`left`/`back`/`bottom`）与自定义 3×3 `view_matrix`

- 类型：功能
- 优先级：P1

分类：**已有修复但待验收**（0.43.0 已交付并完成本机 Creo 10.0.0.0 实机验收；Creo 9/12 与 WorkBuddy 黑盒未验）

- 目标版本：0.43.0（MINOR）

来源：[0.40.0 原始反馈（B 样条除料「零除料」与无法渲染剖面正视图）](../validation/feedback-0.40.0-2026-11-24-bspline-view/originals/bspline-cut-zero-removal-and-section-view.md) §2。

## 修复内容

1. **全正交视图**：`JpegOptions.view`（`src/creo_mechdog/schema.py`）与 `native/generic.cpp` 从 `isometric | front | top` 扩展至 `isometric | front | back | top | bottom | left | right`，其中 `right` 沿 -X 正视 YZ 平面（+Y 向右、+Z 向上），解决平板类 YZ 剖面零件无法渲染轮廓正视图的问题。
2. **自定义 `view_matrix`**：`JpegOptions` 新增可选 `view_matrix`（3×3 右手正交旋转矩阵，行向量约定 `v_screen = v_model * M`，提交前校验正交性与 `det=+1`），支持任意基准面或自定义角度渲染；回执记录 `requested_view="custom_matrix"` 与 `requested_view_matrix`。
3. 同步更新 `server.py` 的 `creo_export_model(jpeg_options=...)` 参数说明。

## 验收证据（2026-11-24）

- 实机 `tools/test_feedback0430_live.py`（报告 `build/feedback0430_live_report.json`，Creo 10.0.0.0 / release 42）：
  - `S2_jpeg_orthographic_and_matrix`：3 mm 厚 60×40 mm YZ 薄板分别渲染 `right`（作业 `857a5d6fd3094303a166b10eee321236`，20,877 字节，肉眼核验呈现完整 60×40 正视轮廓）、`left`（`e8b942d5f6574f27a8f4b76c38838dff`）、`front`（`ed6dad6e9ce04c41a29b0f5d00ac3d0a`，呈 3 mm 薄边）及 45° 自定义 `view_matrix`（`24e16910e62e4f658cd0ee1ea812f65f`），四项均 `view_matrix_matches=true`。
- 单元测试：`tests/unit/test_feedback0400_bspline_view.py::Feat082JpegOrthographicAndMatrixTests` 全部通过。
- 2026-11-28（`0.50.0` 基线补充）：在 `creo_get_job` 文档中补充 `creo_export_model(format="jpeg", jpeg_options={"view": ...})` 视角引导提升可发现性；Creo 10 实机在非对称 `120×60×30` 零件（带偏置 Ø20 凸台与 `25×20` 角切口，模型 `61fa8cc0f2524817bd7134ba3832c9a3`）导出 `top` / `right` / `back`（`800×600`）三视图 `view_matrix_matches=true`，人工视觉核验三方向可清晰辨别。
- 未验范围：Creo 9/12、装配体多视角与 WorkBuddy 黑盒。
