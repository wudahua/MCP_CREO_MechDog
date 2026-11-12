# 0.23.0 反馈映射（2026-11-13）

原件在 [originals](originals/)，字节与 SHA256 见 [manifest.json](manifest.json)。
本文件只记录本批处理结论，不改写原件。下载目录里同时含 0.23.0 与 0.23.1 两份报告，统一归档在本目录。

## 0.23.1 验证报告（门禁实质闭环但逐 ID 子检查不足）

| 反馈项 | 结论 | 处理 |
| --- | --- | --- |
| P2-1 逐 ID 状态子检查只在主台账恰为「开发中/未排期」时生效，FEAT-066 表卡矛盾连续两版 | 确认：门禁覆盖过窄，长摘要里的「已交付」还会把「待复现」卡误判为已交付 | [DEV-083](../../work-items/DEV-083.md)：状态归一化（delivered/partial/developing/unplanned）、主台账列精确比对、工作卡 `分类：` 粗体状态比对、全表扫描活动交付行、可选「差异说明」列 |
| P2-2 版本说明相对链接断链（0.23.0 旧链未修，0.23.1 新增同类） | 确认：`docs/` 下说明误用了 `../` 前缀 | 同一 ID：修正 0.23.0/0.23.1 版本说明两处链接；发布记录另修 `../version.py`；门禁新增本地链接存在性检查（根模式与 ZIP 模式） |
| P3-1 RELEASING「唯一入口」措辞 | 确认：包是快照，回填只在 `main` | 在 [RELEASING](../../development/RELEASING.md) 补快照说明与逐 ID 模板 |
| P3-2 0.22.0/0.23.0 反馈未归档 | 确认 | 本目录；0.22.0 原件已随上一轮处理，本轮只归档 0.23.0 目录 |
| P3-3 主台账最近复核仍是 0.23.1 | 未闭环 | 随 0.23.2 更新为 0.23.2 |
| P4 历史快照与当前事实区分 | 保持 | 历史标签/附件不重传，只在 `main` 加校订说明 |

## 0.23.1 报告（surface_loft 在 Creo 10 因提取失败完全不可用）

| 反馈项 | 结论 | 处理 |
| --- | --- | --- |
| `create_code=0`、`ProFeatureElemtreeExtract=-18`、`feature_incomplete=true`、`release_numeric=42` | 与 0.23.0 报告一致；Creo 10 内核可建空壳但拒绝回读 | 新增 [BUG-120](../../work-items/BUG-120.md)：回执新增 `feature_incomplete(_code)`、`extract_unsupported`、`kernel_completion`、`kernel_evidence`；提取失败消息改为 `SURFACE_LOFT_EXTRACT_UNSUPPORTED` |
| 建议 A：create 后立刻读 `ProFeatureIsIncomplete` | 采用为**诊断**，不用它在 12.4 上提前拒绝（INCOMPLETE 创建后该值本就可能为 true） | 只在提取失败分支消费该字段 |
| 建议 B：能力表加 `kernel_completion` | 采用「只披露」：按 worker SHA 持久化最近观测，`unknown/supported/unsupported`，不预拒绝 | BUG-120；`creo_capabilities` 与 `creo_session_status` 的 `worker_build_identity.features.surface_loft` 均可见 |
| 建议 C：12.4 导出模板 XML + `ProElemtreeFromXMLCreate` | 未做 | BUG-120 剩余范围（需 Creo 12.4 导出与实机授权） |
| 建议 D：STEP/IGES 导入通道 | 未做 | BUG-120 剩余范围 |
| 任意正交平面 YZ@X、XZ@Y | 0.23.1 已交付并实机通过 | 不再重复；Creo 10 无法复测的原因归 BUG-120 |

## 0.23.0 报告（门禁已修但 Creo 10 不支持元素树回读）

| 反馈项 | 结论 | 处理 |
| --- | --- | --- |
| POSTCHECK 门禁已实质闭环 | 确认 | 0.23.1 已关闭；本轮只补强逐 ID 与链接 |
| Creo 10 候选 13 个截面全部 `-18`、两个提取器均拒绝、`ProElemtreeVerify=-2`、GUI 手工特征同样失败 | 确认，说明不是 Python 计划或曲线引用问题 | BUG-120 证据；能力表不写「Creo 10 已支持」 |
| 逐 ID/差异说明/全表扫描建议 | 与 0.23.1 报告 P2-1 相同 | DEV-083 |

## 0.23.0 报告（边界混合仅存不可提取形态与程序化创建缺口）

| 反馈项 | 结论 | 处理 |
| --- | --- | --- |
| `Q1` 有没有可提取形态的边界混合特征 | 报告方结论：没有 | BUG-120 记录为「模板 XML/导入前无法在 Creo 10 运行期完成」 |
| `Q2` 12.4 模板 XML → `ProElemtreeFromXMLCreate` 是否值得尝试 | 未做 | BUG-120 剩余范围；本轮不新增原生路径 |
| `Q3` 精确复刻非均匀 B 样条曲面最稳通道 | 未定 | 留在 BUG-120 导入/模板评估，不与 `surface_loft` 混做 |
| `Q5` `b_spline` 增加 `dimensioning="coordinates"` | 未做 | 继续留在 [FEAT-066](../../work-items/FEAT-066.md) 未开放项；0.23.0 的坐标尺寸自动标注会引入 3.6 µm 刚体平移，需单独设计 |
| `Q6` 任意正交平面截面 | 0.23.1 已交付 YZ@X / XZ@Y | [FEAT-065](../../work-items/FEAT-065.md) |

## Creo 10 编译与运行期边界

连续四版（0.21.0—0.23.1）的 Creo 10 SDK 零补丁编译为报告方证据，本机未复现。
Creo 10 **运行期**边界混合元素树回读仍不可用，本轮只交付诊断与能力披露，
不宣称 Creo 10 运行期可用；详见 [COMPATIBILITY.md](../../COMPATIBILITY.md) 与 BUG-120。
