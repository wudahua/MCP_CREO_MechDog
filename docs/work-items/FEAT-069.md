# FEAT-069：按稳定边界签名选择草绘区域切除

分类：**部分交付，剩余待验收**。类型：功能 / 区域选择切除。优先级：P2。目标版本：0.27.0（区域适配层子项）；原生选区未排期。

## 2026-11-16 0.26.0 复核：契约对真实 TXT 通过，仍未接 ExtrudeOp

外部报告用 `verify_arm7_region_v0260.py` 对真实 Arm7-S7 验证：frame 通过 `validate_yz_sketch_frame`，region 0/1/2 分别解析 4/4/6 段，两两不同，自匹配唯一。这证明契约层可用，但 `ExtrudeOp` 仍只接受整个 sketch，原生也没有区域选区元素，因此 T6c 的 `depth=3` 区域切除建不出来。

推进路线按 [0.26.0 完善计划](../archive/superpowers/plans/2026-11-16-feedback-0260-followup.md)：

1. 输入适配层从目标 `SketchOp` 的实体端点构造闭环，用现有 `match_region` 唯一匹配后，把该闭环实体原样复制成派生草图，再引用它做拉伸切除；
2. 派生草图保留父草图 label 与签名摘要，不修改原草图，不拼接近似曲线；
3. 原生「直接引用已有草图区域」只在取得目标机 trail/mapkey 或官方依据后实现，不得用全草图普通切除冒充。

### 2026-11-16 离线实现（派生草图路线）

- 新增 `src/creo_mechdog/sketch_regions.py`：按 `region.frame`（或命名 YZ 平面的原生帧）把实体端点映射到全局 YZ；对 line/centerline、arc、开放 polyline/spline、clamped b_spline 取端点；用端点聚类 + 有界简单环枚举构造闭环，再用 `segments_match` 做无序、容差内匹配，零命中或多命中都拒绝。
- 派生草图只复制命中闭环的实体（同一 plane/offset，实体 dict 原样深拷贝），不修改源草图；同一区域被多个 extrude 使用时只派生一次并共享。回执新增 `region_adaptation`（源草图、派生 label、签名 SHA256、实体名、段数与容差）。
- `ExtrudeOp.region` 已加入 schema：签名在入队前解析；数字 sketch 引用、surface 模式与非法签名提前拒绝。
- `generic_bridge.submit` 在准入前展开区域，worker 不会收到 `region` 字段；展开后的 operations 会写进 `request.json`/`job.json`。
- 明确限制：源草图必须是不依赖 dimensions/constraints/weld_pairs 的坐标草图；只支持简单闭环（不支持岛屿/嵌套区域）；圆/矩形/椭圆无法用边界签名表达；frame 必须落在 YZ 平面。
- 离线 24 项单测通过，未编译原生、未连接 Creo；Arm7 真实输入、共享边界包含关系和 Creo 10 实机仍待验证。原生区域选区未实现。

## 当前摘要（2026-11-16）

本批：0.26.0 交付子项（部分交付）交付 `region_selection` 契约与三套原始签名测试；原生选区创建/输出侧未证，未接 `ExtrudeOp`，能力保持不开放。2026-11-16 追加：`ProSurfReg.h` 的 “Surface Region” 实为 `PRO_FEAT_SPLIT_SURF`（草图/链分割曲面），不是拉伸截面里的区域复选，G1 仍不开放。

来源：[0.25.0 Arm7反馈原件](../validation/feedback-0.25.0-2026-11-16/arm7.md)，关联 DEV-090 T6c、T7；范围见[计划G1/G2](../archive/superpowers/plans/2026-11-16-feedback-0250.md#g1g2按稳定签名选区切除p1p2feat-069)。

新反馈补齐三套B-REGION端点签名和B-CUT depth=3/region_count=3；旧“作者未收到签名”前置已变化。完整TXT/Arm7-S7实体仍未附；端点集合不含完整弧形/样条。当前ExtrudeOp和native extrude没有按签名选区路径，官方创建路线及输出侧仍待核实。

## 范围

先规范签名/frame/容差和重复/歧义拒绝，核局部(u,v)→(1.5,v,-u)。region_index_hint=4,2,5仅追溯，不映射成固定Creo索引。先取得可用API/参照树、所有权与方向证据，再实现；不能把其它特征REGION常量套入拉伸，也不能用全草图普通切除冒充选区。

## 验收

离线：签名无序/反向等价、重复、歧义及坐标反例。获准后的Creo12.4：独立三区域算例，核恰选中三个目标、方向与3mm去料、未选区域保留、有效特征、保存重载、回滚及revision；compact/full保留匹配与材料量证据。

Arm7整件另需完整草图；最终体积还受未开放G2圆角影响。当前仅离线查证，原生路线及实机均未验证；路线不成立时保持不开放并记录具体缺口。
