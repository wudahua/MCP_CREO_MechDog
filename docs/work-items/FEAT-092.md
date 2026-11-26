# FEAT-092：新增 `creo_server_info` 只读工具与 `ExtrudeOp.region.closed_chain` 封闭链选区

类型：功能。优先级：P3。

分类：**已有修复但待验收**。0.47.0 交付 `creo_server_info` 与 `region.closed_chain`；`closed_chain` Creo 10 实机与 4548 项单测通过。 [发布记录](../validation/RELEASE-0.47.0.md)

## 来源与现象

2026-11-26 外部 0.45.1 / Creo 10.0.0.0 反馈 §10、§11、§14.8–14.9：

1. **§10**：CREO 侧缺少只读 `creo_server_info` 工具来查询服务版本、工具数、单通道模式与已知 Creo 版本，只能从 `creo_get_job` 间接读取。
2. **§11**：`ExtrudeOp.region` 除 `signature_yz_mm` 与 `interior_point_yz_mm` 外，建议直接支持按草图实体引用组成的 `closed_chain`（`[{"geo": i, "reversed": bool}, {"spline": j, "reversed": bool}, ...]`）选区，无需签名匹配。

## 范围与验收

1. `src/creo_mechdog/server.py` 新增只读无锁工具 `creo_server_info`，同步更新 `capabilities.py` 与 `mcp_contract.py`/契约测试。
2. `SketchRegionSelector`（`schema.py`）与 `sketch_regions.py` 支持 `closed_chain`（按源草图实体顺序索引/名称提取并校验端点首尾闭合），与已有 `signature_yz_mm`/`interior_point_yz_mm` 互斥或协同。
3. 补充单元测试并通过 `tools/dev_check.py` 与 `tools/test_mcp.py --offline`。
