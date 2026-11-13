# MCP_CREO_MechDog 0.24.0

一句话：把"跑一趟才知道行不行"提前到"提交前就给结论"——只读导出不再被基线漂移误判、已知跑不通的放样在内核签名命中时直接拒绝、曲面放样多了一条模板路线、STEP/IGES 有了导入通道，并且计划可以自带包围盒与面积断言。

- 类型：MINOR（对外可见的行为增补，无破坏性改名）
- 日期：2026-11-13
- 公开工具：**107 个**，与 0.23.2 相同；变化在 `creo_execute_plan`、`creo_capabilities`、`creo_submit` 的输入/回执字段
- 主台账：[BACKLOG](BACKLOG.md) · 发布记录：[RELEASE-0.24.0](validation/RELEASE-0.24.0.md) · 跨版本复测：[Creo 10 交接包](development/CREO10-RETEST-0232-2026-11-13.md)

## 对外可见变化

### 1. 只读型计划自动按只读准入（BUG-121）

`export` / `dump_tree` / `mass_properties` / `surface_group_measure` / `surface_curvature` / `udf_inspect` 这类不写模型的操作，在 Python 侧自动按只读准入，并在作业清单里记 `readonly=true`、`readonly_source="inspection_only_plan"`。以往"GUI 保存过模型 → 基线漂移 → 只读导出被拦"的误伤不再出现。

写计划仍然要过基线校验；`model_reconciliation_required` 的失败消息现在附带 `creo_reconcile_model` 的动作指引，原生原文保留在 `native_message`。

注意：`creo_get_job` 的 `detail=compact` 不披露这两个只读字段，判定必须读作业清单 `job.json`。

### 2. 已知跑不通的放样在提交前被拒（BUG-122）

当同一 worker 已实测到"创建成功、元素树不可提取"的内核签名（`create_code=0` 且 `extract_code=-18`）时，第二次 `surface_loft` 在**提交前**就被拒绝：不建空壳、不建作业、模型不变。能力表新增 `runtime_admission=refused_before_job`，错误文本给出三条出路。

没有命中签名的环境（例如当前 12.4 实机连续两次都成功）行为不变。

### 3. 元素树模板路线（BUG-123）

`surface_loft` 新增 `template` 参数：`file`（`templates/elemtree/` 下的相对路径）、`sha256`、`sections`、`guides`。命中时 `tree_source="template_xml"`，输入树来自 XML 而非逐元素写入。两个负例分别报 `TEMPLATE_SHAPE_MISMATCH` 与 `TEMPLATE_TREE_LOAD_FAILED`，且都不留特征。

口径提醒：模板只换**输入树**，创建后仍会执行 `ProFeatureElemtreeExtract`，因此 `extract_code=-18` 不会因模板而消失。

### 4. STEP/IGES 导入通道（BUG-124）

计划里新增单操作 `import_geometry`：`format`（`step`/`iges`）、`profile`（绝对路径，扩展名须与 format 一致）、`sha256`（与 schema 内的 `file_sha256` 双摘要校验）。它必须单独成计划、不带 `model_id`，结果是一个新建的独立 part。许可与失败码原样透出（`PRO_TK_NO_LICENSE` 等都是环境结论，不是本功能失败）。

### 5. 计划级包围盒与面积断言（FEAT-067）

`assertions` 新增：

```json
{"assertions": {
  "bbox_mm": {"min": [0, 0, 0], "max": [40, 40, 10], "tolerance_mm": 0.001},
  "surface_area_mm2": 4800.0,
  "surface_area_tolerance_mm2": 0.5
}}
```

- `bbox_mm`：按 inspection 的每实体 bbox 求并集后换算毫米。
- `surface_area_mm2`：`ProSolidSurfaceVisit` 逐面求和后平方换算 mm²（40×40×10 方块为 4800 mm²）。
- 两者在**长度单位不可换算为毫米**时失败，而不是拿原生单位当毫米；失败都在末次操作后、保存重载前判定，模型回滚不变。

## 行为变化与升级注意

1. `surface_loft` 可能在提交前被拒（见第 2 条），客户端应把"没有 job_id 的拒绝"当正常分支处理。
2. `import_geometry` 只接受单操作计划；与其他操作混排会被准入拒绝。
3. 断言失败是**作业失败**，不是警告：需要重跑时改期望值或改模型。
4. 本版含 `native/*.cpp` 变更（`generic.cpp`、`surface_loft.cpp`、新增 `import_geometry.cpp`），升级后必须重编译 worker（`bridge.py build`）。

## 验证

- 离线：全量单测 3548 项通过（`tools/dev_check.py`，`success: true`），`bridge.py build` exit 0。
- Creo 12.4.0.0（`release_numeric=44`）实机六个驱动取得回执，其中本批 `tools/test_0232_live_acceptance.py --live` 为 14 项检查全 PASS：只读导出记 `readonly_source`、bbox 与面积的通过与失败两态、同一模型连续两次放样成功且无预拒绝。
- 导入：STEP 440.0 mm² 与 IGES 1540.0 mm² 两例均导入成功并保存重载。
- 模板：手写树与模板 XML 两条路线的面积相对 0.0，两个负例未留特征。
- **Creo 10 未复测**：跨版本结论只能由外部复测给出，步骤见[交接包](development/CREO10-RETEST-0232-2026-11-13.md)。

## 仍未验（本版不声称）

- Creo 10 上的模板解析、导入许可、只读导出与预拒绝。
- 未知单位（英寸等）模型上的两条断言。
- `surface_area_mm2` 的空模型与单面失败路径。
- GUI 保存造成的基线漂移（只读降级已覆盖，写计划仍按基线校验）。
- 12.4 上"先失败一次再成功"的误拒序列未构造。

## 源码包与校验

本版发布四个附件（逐个列出，不使用通配）：

- `MCP_CREO_MechDog-0.24.0-source.zip`
- `MCP_CREO_MechDog-0.24.0-source.zip.sha256`（源码包摘要记录在同名 sidecar 中，一行 `<64 位 SHA256>  文件名`）
- `MCP_CREO_MechDog-0.24.0-seed-library.zip`
- `MCP_CREO_MechDog-0.24.0-seed-library.zip.sha256`（种子包摘要同样在 sidecar 中）

- 种子包：24 个文件、9 个种子，SHA256 `c6d9a77b04ac397836464f8e12455a9b796e49b1193a796b2e1d28e782cd68f1`。
- Release：<https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.24.0>
- 发布后核对：`python tools/check_release_assets.py --tag v0.24.0`，四附件与两个 sidecar 逐一致，结果写回[发布记录](validation/RELEASE-0.24.0.md)与[POSTCHECK](development/RELEASE-POSTCHECK-2026-11-07.md)。

## 升级

1. 覆盖源码后运行 `python bridge.py build` 重编译 worker（本版改了原生代码）。
2. 种子库换成本版 `seed-library.zip`（`compatible_server_version=0.24.0`，与 0.23.x 的种子库不通用）。
3. 客户端若解析作业清单，注意新增 `readonly` / `readonly_source`，以及能力表的 `runtime_admission`。
