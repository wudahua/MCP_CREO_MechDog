# MCP_CREO_MechDog 0.47.1 版本说明

2026-11-26 PATCH，公开工具数 112。上一版本：0.47.0（`v0.47.0`，提交 `baeb3d66aa7166a874d474187fb73bfcfdf210f4`）。

- **默认主基准面偏移法线对齐与草图帧反向告警（[BUG-187](../work-items/BUG-187.md) 追加修复）**：回应 0.46.1 外部反馈（原件已逐字节归档至 [feedback-0.46.1-2026-11-26](../validation/feedback-0.46.1-2026-11-26/SOURCE_MANIFEST.json)）。`native/generic.cpp` 中 `offset_plane` 对主基准面（`axis="x"|"y"|"z"`）的非倾斜偏移面默认对齐至 `capabilities.frames` 规范法线（`YZ=+X`、`XZ=-Y`、`XY=+Z`），不再静默继承 Creo `TOP` 面的 `+Y` 法线而反转草图 `v_axis` 与拉伸方向；`datum_plane` 回执新增 `plane_frame`（含 `surface_id`、`origin`、`normal`、`requested_flip`、`effective_flip`、`canonical_frame_aligned`）；字典草图面未显式传 `v_axis`/`flip=true` 且实际法线与主平面规范法线相反时，输出 `frame_warning`（`code="frame_mismatch"`）；`compact_sections.py` 同步保留 `plane_frame` 与 `frame_warning`；`creo_capabilities` 新增 `frames_note` 明确偏移面法线约定、`geometry_tolerance_mm` 参数名、离散包围盒与批量质量查询入口。
- **开发入口统一与四批 P1/P2 台账复核（[DEV-104](../work-items/DEV-104.md)）**：统一 `CLAUDE.md`、`README.md`、`docs/DEVELOPMENT.md` 与 `docs/development/ARCHITECTURE.md` 入口，完成四批台账复核与分类校正（归档 `BUG-133`/`BUG-080`，对齐 `BUG-146/148/149/132/129/102/108/193`、`FEAT-078/001/009/055`、`DEV-076/081/095` 等归属与计数）。
- 实机验证环境为 Windows x64 / Python 3.12.10 / Creo Parametric 10.0.0.0（`release_numeric=42`）及匹配 Toolkit SDK：三组对照全链路实机通过并保存重载验证（默认 XZ 偏移 `-30` 作业 `2df364a78c39444db9118890cb015a5d`：`normal=[0,-1,0]`、`v_axis=[0,0,1]`、无告警、体积 `5600.0 mm³`、包围盒 `y∈[-37,-30]`；显式 `flip=true` 作业 `323445719f8046ee988c9294d864c201`：`normal=[0,1,0]`、触发 `frame_warning.code="frame_mismatch"`、包围盒 `y∈[-30,-23]`；显式 `v_axis=[0,0,1]` 覆盖作业 `d732c45a1a6349e88e104b08466b18e5`：`normal=[0,-1,0]`、无告警、包围盒 `y∈[-37,-30]`，三组均 `saved_file_reloaded_and_verified=True`）。
- 未测范围：Creo 9 / Creo 12.4 实机与外部 WorkBuddy 黑盒复测。 [发布记录](../validation/RELEASE-0.47.1.md)

## 附件

- `MCP_CREO_MechDog-0.47.1-source.zip`
- `MCP_CREO_MechDog-0.47.1-source.zip.sha256`
- `MCP_CREO_MechDog-0.47.1-seed-library.zip`
- `MCP_CREO_MechDog-0.47.1-seed-library.zip.sha256`

种子包 SHA256 为 `326eb7ac1c140fdf26205c2e17d282a326b34d2417b6bac459c53a9fde3e58d8`。两份同名 sidecar 分别记录各自 ZIP 的摘要。 [GitHub Release](https://github.com/wudahua/MCP_CREO_MechDog/releases/tag/v0.47.1)
