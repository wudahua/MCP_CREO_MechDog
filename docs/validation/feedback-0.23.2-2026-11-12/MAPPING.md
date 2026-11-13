# 0.23.2 球鼻艏反馈映射（2026-11-13）

原件在 [originals](originals/)，字节与 SHA256 见 [manifest.json](manifest.json)。本文件只记录本批处理结论，不改写原件。

反馈包：`C:\Users\Administrator\Downloads\反馈包-球鼻艏-20261112\反馈包-球鼻艏-20261112`（报告日期 2026-11-12，报告方环境 Creo 10.0.0.0 / `release_numeric=42` / MCP 0.23.2）。

## 归档核对

- 30 个文件的 SHA256 与包内 `MANIFEST-SHA256.txt` 逐条一致；`MANIFEST-SHA256.txt` 自身不列入该清单，按归档副本另记（`ea71293d…`）。
- 包内 `历史反馈文档/` 的 0.23.0 两份与仓库既有 [feedback-0.23.0-2026-11-12](../feedback-0.23.0-2026-11-12/MAPPING.md) 的原件**字节不同**（例如 0.23.0 门禁报告 15487 B vs 14647 B）。本轮以包内副本为准存档，未替换上一批原件；两批都保留，不外推"内容相同"。
- `源数据/简易护卫舰_跨软件三维建模自然语言说明.txt`（135198 B）与 `_bulb_sections.json`（175646 B）属输入资料，随包归档，不进入源码包。

## 主问题（B030 导线曲面放样不可用）

| 反馈项 | 结论 | 处理 |
| --- | --- | --- |
| `create_code=0` 但 `feature_incomplete=true`、几何项 0、`extract_code=-18` | 与 [BUG-120](../../work-items/BUG-120.md) 记录一致，本轮不重复调查根因 | 沿用 BUG-120；0.23.2 诊断字段已在报告 E9 确认生效 |
| 12.1 `kernel_completion=unsupported` 仍建空壳 | 确认可离线修；不采纳"按 `release_numeric` 推断" | 新增 [BUG-122](../../work-items/BUG-122.md)：同一 worker 实测签名（`create_code=0` + `extract_code=-18`）才在提交前拒绝，已离线交付 |
| 12.2 `export`/`inspect` 被基线漂移拦住 | 现象确认，根因需修正：Python `validate_baseline` 只在非只读时调用，拦住的是原生准入 | 新增 [BUG-121](../../work-items/BUG-121.md)：只读型计划自动按只读准入；写计划失败消息补动作指引，已离线交付 |
| 12.3 低版本 `boundary_conditions` 无法验证 | 维持不可用，本轮不排期 | 记入 BUG-120/BUG-123 边界；不猜 `PRO_E_BNBLN_TAN_COND` 形态 |
| 13.2 建议用包围盒作自动断言 | 当前 `Assertions` 无该字段，值得补 | 新增 [FEAT-067](../../work-items/FEAT-067.md)：`bbox_mm` 已交付；`surface_area_mm2` 未交付 |
| 11.1 路线 C（模板 XML + `FromXMLCreate`） | SDK 声明层成立，仓库缺"XML→特征"路径；跨版本可移植性未验 | 登记 [BUG-123](../../work-items/BUG-123.md)，待用户当次确认后先导模板 |
| 11.2 路线 D（STEP/IGES 导入） | SDK 声明层成立，许可与导入后语义未验 | 登记 [BUG-124](../../work-items/BUG-124.md) |

## 本批红线

未连接 Toolkit、未启动或结束 Creo、未清锁/unknown 保护、未改用户模型、未重发版本。`bridge.py build` 为本地编译，exit 0；Creo 10 运行期结论全部保留为"未验证"。
