# FEAT-093 ExtrudeOp 双向不等深 depth2、`datum_planes[].name` 与 cut_scope 文档边界

分类：**已有修复但待验收**。功能，P1，目标版本 0.49.0。

来源为 [0.47.1 反馈](../validation/feedback-0.47.1-0.48.3-2026-11-27/SOURCE_MANIFEST.json) `v0471-runner-disconnect-panel-lock.md` §3（问题 C）、§3.6（问题 C3）、§9（问题 I.1）。

## 范围

- `src/creo_mechdog/schema.py`、`src/creo_mechdog/server.py`、`src/creo_mechdog/capabilities.py`、`src/creo_mechdog/operation_results.py`、`native/generic.cpp`：
  - `ExtrudeOp` 与 `creo_extrude` 新增可选 `depth2: Positive | None = None`（仅支持 `depth_type="blind"` 且 `direction != "symmetric"`），原生侧按 Creo 10 `ProExtrude.h` 写入 `PRO_E_EXT_DEPTH_FROM_TYPE = PRO_EXT_DEPTH_FROM_BLIND` 与 `PRO_E_EXT_DEPTH_FROM_VALUE`；`extrude_depth_report` 回读 `effective_depth2_mm` 与 `effective_total_depth_mm`；`annotate_cut_volume_check` 汇总双向深度。
  - `creo_capabilities` 披露 `extrude_two_sided_asymmetric: true`，并在 `known_limitations.cut_scope` 明确说明原生 `PRO_E_BODY_SELECT` 仅支持实体级作用域，单实体内按特征限制需通过独立体再布尔合并替代。
- `native/geometry.cpp`、`native/generic.cpp`：
  - 采集基准面时读取特征名称（`ProModelitemNameGet`）与 `feature_id`，在 `creo_inspect_model` 的 `datum_planes[]` 中输出 `name` 与 `feature_id`。

## 验收

- 单元测试与全量门禁：`tools/dev_check.py --unit-timeout-seconds 1800` 通过（`depth2` schema 校验、`cut_volume_check` 双向深度计算及 `normalize_extrude_depth` 保真）。
- 本机 Creo 10.0.0.0（`model_id=0c347e63075942eba0f290462c903df7`、`part_sha256=32fcdc1d6698f3f5d4897178c7bedb3684835ed067a0621a9307044882511a91`、`worker_sha256=73354279ce7016b3573f37a50213dc55439078d6f40dc7c96b83f0a0b07073c1`）实机验收：`add`（`depth=10.0, depth2=3.0`）实测 `volume_mm3=2600.0`、`bounding_box_mm.z=[-3.0, 10.0]`、`extrude_depth`（`effective_depth_mm=10.0, effective_depth2_mm=3.0, effective_total_depth_mm=13.0`）且 `datum_planes[]` 返回 `PL_TEST_NAME` (`feature_id=78, id=79`) 与 `RIGHT`/`TOP`/`FRONT`；后续 `cut`（`depth=8.4, depth2=1.0`）实测终体积 `2449.6 mm³`（`material_removed_mm3=150.4`）、`cut_volume_check.effective_depth_mm=9.4`，`saved_file_reloaded_and_verified=true`。
- 未测范围：Creo 9 / 12.4 与 WorkBuddy 黑盒验收。
