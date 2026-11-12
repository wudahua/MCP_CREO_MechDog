# 0.21.0 反馈映射（2026-11-12）

原件在 [originals](originals/)，字节与 SHA256 见 [manifest.json](manifest.json)。
本文件只记录本批处理结论，不改写原件。

## 0.21.0 报告（导线放样被 Probbl.h 门禁误剔）

| 反馈项 | 结论 | 处理 |
| --- | --- | --- |
| P1 / §8-1 `surface_loft` 被 `Probbl.h` 门禁误剔 | 确认：`Probbl.h` 只有注释和 `PRO_E_DTM_SRF_TYPE_BND_BLEND 11`，五个 `PRO_E_BNBLN_*` 在 `ProElemId.h` | 归 [DEV-082](../../work-items/DEV-082.md)：门禁改为 `MECHDOG_HAS_BNBLN_TREE`，worker/能力文案同步 |
| P2-1 主台账未列 0.21.0、DEV-083/FEAT-009 未回填 | 已在 0.21.1 / 0.22.0 闭环 | 不动 |
| P2-2 POSTCHECK 缺 `## v0.21.0` | 已补 | 不动 |
| P3-3 `RELEASE-0.21.0.md` 发布核对仍是准备态 | 已回填 | 不动 |
| P3-4 `RELEASE-0.20.0.md` 的「不触及 native」 | 确认仍保留 | 本轮更正措辞 |
| P4 release notes「Creo 10 无 SDK」 | 历史快照 | 不改原件；在 COMPATIBILITY 新日期段说明 |
| §8-4 样条 NURBS 参数 | 未支持 | 新增 [FEAT-066](../../work-items/FEAT-066.md)：`b_spline` |
| §8-5 坐标尺寸支持 spline | 未支持 | 本轮不做，留在 FEAT-066 未开放项 |
| §8-6 Creo 版本 → 可用性速查 | 已有 worker 可用性投影 | 同步去头文件化文案 |
| §8-7 非平面边界曲面 | `surface_boundary_fill` 仍未发布 | 本轮不做 |
| §8-8 callback 程序化注册 | 未提供 | 本轮不做 |

## 0.20.0 报告（NURBS 样条精确复现缺失）

| 反馈项 | 处理 |
| --- | --- |
| 逐截面控制点/节点/权重无法从 TXT 复现 | [FEAT-066](../../work-items/FEAT-066.md) 的 `b_spline` |
| 导线放样框架描述与 `creo_surface_loft` 现状不符 | FEAT-065 M1—M4 已在 0.21.0/0.22.0 交付，文档按现状读取 |
| `surface_loft` 只接受 XY 截面等旧限制 | FEAT-065 M3 已交付曲线/边与 YZ 截面，本轮不重复 |

## Creo 10 零补丁编译报告

报告方结论：0.21.0 官方包在 Creo 10 SDK 上零补丁编译通过，元素树常量完备。
本轮未在本机复现（无 Creo 10 SDK）；门禁修复后 Creo 10 **运行期**元素树再生
仍未经本机验证，记录在 [COMPATIBILITY.md](../../COMPATIBILITY.md) 与 DEV-082。
