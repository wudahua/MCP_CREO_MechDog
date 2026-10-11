# 种子自动化、翼型参数和原生定位（2026-10-11）

本次先完成三个增量：种子自动安装/发现/匹配；原生翼型截面及原位参数修改；通用原生移动、分组、重排及轴阵列。版本号沿用 **0.2.4**。旧 GitHub 下载文件不会随本地修改更新；本说明以包含 `seeds.py`、`airfoil.py`、`native/placement.cpp` 的源码为准。

## 1. 不必向 Agent 提供种子路径和内部 ID

源码内附 `seed_library/`，保留项目 MIT 许可证和三个原始 PRT 的 SHA256。`setup.ps1` 自动验证并注册本地库；不会下载 Creo 或 SDK。

- `creo_list_seeds()`：可用文件、本机路径、数量、模式及哈希核对结果。
- `creo_validate_seed(seed_name)`：核对清单和哈希；实际原生类型、截面数及模式在新建零件时验证。
- `creo_install_seed_library()`：验证并注册随源码的库；`directory` 可注册外部原始库目录；`archive_file` 可安装原来发布的 MIT 种子 ZIP，要求原包 SHA256，不覆盖现有库。
- `creo_new_loft_part(sections=..., interpolation="smooth")`：省略 `seed_file` 和 `seed_feature_id` 时按数量和模式自动匹配。显式提供两个参数的旧调用继续可用。

当前自动匹配 **2/straight、2/smooth、5/smooth**。其他数量仍需显式兼容种子。缺失、哈希不匹配或数量/模式不支持会在排队前给出错误。这解决了新安装缺少文件的问题，直接从无种子创建 Blend、向既有零件插入 Blend 仍未开放。

## 2. 原生 NACA 00xx 翼型和原位修改

`creo_create_airfoil_section` 创建独立原生草图；`creo_new_airfoil_blade` 用多个截面创建原生实体平滑/直线 Blend。参数包括：

| 参数 | 含义 |
| --- | --- |
| `chord` | 弦长，mm |
| `thickness_ratio` | 最大厚度/弦长，例如 0.12 对应 NACA 0012 |
| `twist_deg` | 截面内逆时针扭转角，度 |
| `origin` | 扭转中心在草图中的坐标，mm，默认 `[0,0]` |
| `pivot_fraction` | 扭转中心位于弦长的比例，默认 0.25 |
| `points_per_side` | 每侧余弦采样点数，默认 41 |
| `offset` | 截面沿 Z 的位置，mm，混合时严格递增 |

采用对称 NACA 00xx 厚度公式，上下表面为原生样条，尾缘用短直线封闭。没有弯度参数，也不提供气动性能判断。创建后通过 `creo_set_airfoil_parameters(model_id, expected_revision, sketch, values)` 修改弦长、厚度比、角度、原点或扭转中心；点数在创建时固定。草图和 Blend 特征 ID 保持不变，下游分组/阵列重新生成。

参数定义保存在受管模型的 MCP 元数据中；修改时重定义同一个 Creo 草图。并非 Creo 内建关系式驱动的翼型命名尺寸，因此不要在 Creo 的“参数”窗口修改同名数值来替代此工具。普通原生草图尺寸工具仍可用于带命名尺寸的其他草图。

`creo_update_sketch_geometry` 提供通用原位几何修改：直线、多段线、矩形、圆及样条。展开后的实体名称、类型和数量须匹配；原有尺寸/约束替换为自动尺寸，清除命名尺寸别名和翼型定义。圆弧、椭圆和中心线的原位替换未开放。此工具用于主动替换几何，调用方须接受尺寸/约束变化。

五截面示例见 [airfoil_blade.json](../examples/airfoil_blade.json)。调用时提交一次，查询 `creo_get_job`，读取当前 `model_id` 和 `revision` 后再修改。

## 3. 通用定位、分组和轴阵列

- `creo_transform_geometry`：对完整实体 body 或 quilt/受支持基准及曲线进行原生刚体变换。按固定参考坐标系依次绕 X、Y、Z 旋转，再沿其 X、Y、Z 平移；这改变几何，不是改变相机。坐标系引用默认 `{"kind":"default_csys"}`。
- `creo_set_geometry_transform`：原位修改变换的角度和位移，保留特征 ID，下游几何重生成。要恢复原位可全部设为零。
- `creo_group_features`：创建原生局部特征组。成员需连续；`include_between=true` 明确允许包含中间特征。自动包含所选草图的支持基准面可关闭。
- `creo_reorder_features`：移动原生特征到指定锚点前/后，恰好指定 `before` 或 `after` 一个参数；依赖冲突失败后恢复检查点。
- `creo_axis_pattern`：原生特征或上述局部组的轴阵列，数量和有符号增量角。轴需先于阵列对象，优先采用独立基准轴；必要时先重排。

实体变换采用附着的原生 FlexMove，可受本机 Flexible Modeling 许可限制；quilt 等使用原生 Move，并生成绑定参考坐标系的参数点和支持轴。`references` 必须使用实际查询到的 body/几何 ID 或受管别名。实体与 quilt 不能混在同一次变换中。

已验收的定位分支是整个实体移动（`keep_original=false`）、平面 quilt 移动后加厚及再次修改。保留原几何的复制、多个 body、自定义坐标系、复杂非平面 quilt 和各类基准/曲线组合仍需安装环境下验证；接口可接收不代表全部组合已实测。分组与轴阵列已在五截面翼型、轮毂组成的双叶件上验证，包括阵列完成后继续修改翼型。

## 验收与复现

新增接口均沿用受管模型、revision、防覆盖、失败回滚和实际保存/擦除/重载检查。原生接口返回成功之外，定位用实际包围盒核对；翼型用 STL 截面轮廓核对。证据与测试步骤见 [validation_portable_modeling.json](validation_portable_modeling.json) 和 `tools/test_portable_modeling.py`。

在已完成安装且 Creo 空闲时运行 `.\.venv\Scripts\python.exe tools\test_portable_modeling.py`，会创建新的独立验证件，不修改用户原模型。程序输出完整私有报告目录；中断后用 `--output-dir` 指定原目录并加 `--resume` 查询已有任务，未知结果不会重复创建。完整私有报告含本机路径，不作为公开附件。

这是三个增量的完成范围。VSS、Swept Blend、Boundary Blend、曲面合并/修剪，以及报告中的嵌套截面和跨接缝圆角问题不属于本次 1→2→3 的范围；完整 Creo 覆盖仍未完成。
